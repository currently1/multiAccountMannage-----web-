# encoding: UTF-8

'''
修改多品种数据提取以及回测。
增加多品种参数字典Param_setting_dict/self.contract_dict
增加日度周期回测模式。
增加持仓缓存字典，请在策略端补充该逻辑。
增加策略展示按日统计。
                                ---by zjh
'''
from __future__ import division

from datetime import datetime, timedelta
from collections import OrderedDict
from itertools import product
import multiprocessing
import pymongo
from collections import defaultdict
from ctaTemplate import Logger
from ctaBase import *
# from ctaSetting import *
# from ctaTemplate import CtaTemplate
import copy
import path
from vnpy.trader.vtGlobal import globalSetting
from vnpy.trader.vtObject import VtTickData, VtBarData
from vnpy.trader.vtConstant import *
from vnpy.trader.vtGateway import VtOrderData, VtTradeData
from vtFunction import loadMongoSetting
import csv
import pandas as pd
from Data import Param_setting_dict
import matplotlib.pyplot as plt
import sqlalchemy
import re
import time
import sys
import os 
reload(sys)
sys.setdefaultencoding('utf8')

from queue import Queue
from threading import Thread
from pyecharts import Line

########################################################################
class BacktestingEngine(object):
    """
    CTA回测引擎
    函数接口和策略引擎保持一样，
    从而实现同一套代码从回测到实盘。
    """

    TICK_MODE = 'tick'
    BAR_MODE = 'bar'
    DAILY_MODE = 'daily'

    # ----------------------------------------------------------------------
    def __init__(self,queue):
        """Constructor"""
        self.queue=queue
        # 本地停止单编号计数
        
        self.stopOrderCount = 0
        # stopOrderID = STOPORDERPREFIX + str(stopOrderCount)
        self.capital = 10000000  # 回测时的起始本金（默认100万）
        # 本地停止单字典
        # key为stopOrderID，value为stopOrder对象
        self.stopOrderDict = {}  # 停止单撤销后不会从本字典中删除
        self.workingStopOrderDict = {}  # 停止单撤销后会从本字典中删除
        self.tickStrategyDict = {}
        # 引擎类型为回测
        self.engineType = ENGINETYPE_BACKTESTING
        
        self.marginrate = 0.08        
        # 回测相关
        self.strategy = None  # 回测策略

        self.mode = self.BAR_MODE  # 回测模式，默认为K线

        self.startDate = ''
        self.initDays = 0
        self.endDate = ''

        self.slippage = 0  # 回测时假设的滑点
        self.rate = 0  # 回测时假设的佣金比例（适用于百分比佣金）
        self.size = 1  # 合约大小，默认为1

        self.dbClient = None  # 数据库客户端
        self.dbCursor = None  # 数据库指针

        # self.historyData = []       # 历史数据的列表，回测用
        self.initData = []  # 初始化用的数据
        self.backtestingData = []  # 回测用的数据

        self.dbName = ''  # 回测数据库名
        self.symbol = ''  # 回测集合名
        self.contractName = ''  # 回测合约名 （由参数读取）
        self.dataStartDate = None  # 回测数据开始日期，datetime对象
        self.dataEndDate = None  # 回测数据结束日期，datetime对象
        self.strategyStartDate = None  # 策略启动日期（即前面的数据用于初始化），datetime对象

        self.limitOrderDict = OrderedDict()  # 限价单字典
        self.workingLimitOrderDict = OrderedDict()  # 活动限价单字典，用于进行撮合用
        self.limitOrderCount = 0  # 限价单编号

        self.tradeCount = 0  # 成交编号
        self.tradeDict = OrderedDict()  # 成交字典

        self.logList = []  # 日志记录
        self.logger = Logger(logname='log.txt', loglevel=1, logger="Backtesting").getlog()

        # key为vtSymbol，value为PositionBuffer对象
        self.posBufferDict = {}

        # 多合约使用参数字典
        self.contract_dict = defaultdict(dict)
        # 日线回测结果计算用
        self.dailyResultDict = OrderedDict()
        # 当前最新数据，用于模拟成交用
        self.tick = None
        self.bar = None
        self.dt = None  # 最新的时间
        self.daily = None
        self.mapping = {}  # 一个合约对应一个回测模式

        self.rollingContract = []  # 有持仓换月list
        self.rollingFlag = []  # 无持仓换月
        self.lastDate = ''

        # 保存vtOrderID和strategy对象映射的字典（用于推送order和trade数据）
        # key为vtOrderID，value为strategy对象
        self.orderStrategyDict = defaultdict(dict)

        self.Param_setting_dict = Param_setting_dict

        self.stopCount = defaultdict(dict)

        # ----------------------------------------------------------------------

    def setStartDate(self, startDate='20100416', initDays=1):
        """设置回测的启动日期"""
        self.startDate = startDate
        self.initDays = initDays

        self.dataStartDate = datetime.strptime(startDate, '%Y-%m-%d')
        initTimeDelta = timedelta(initDays)
        self.strategyStartDate = self.dataStartDate + initTimeDelta

    # ----------------------------------------------------------------------
    def setEndDate(self, endDate=''):
        """设置回测的结束日期"""
        self.endDate = endDate
        if endDate:
            self.dataEndDate = datetime.strptime(endDate, '%Y-%m-%d')
            # 若不修改时间则会导致不包含dataEndDate当天数据
            self.dataEndDate.replace(hour=23, minute=59)

            # ----------------------------------------------------------------------

    def setBacktestingMode(self, mode):
        """设置回测模式"""
        self.mode = mode

    # ----------------------------------------------------------------------
    def setInitialPos(self, initialPos):
        """设置初始仓位"""
        self.strategy.pos = initialPos
        trade = VtTradeData()
        trade.vtSymbol = self.contractName
        if initialPos > 0:
            trade.direction = DIRECTION_LONG
        elif initialPos < 0:
            trade.direction = DIRECTION_SHORT
        trade.volume = initialPos
        trade.offset = OFFSET_OPEN
        if trade.vtSymbol:
            posBuffer = self.posBufferDict.get(trade.vtSymbol, None)
            if not posBuffer:
                posBuffer = PositionBuffer()
                posBuffer.vtSymbol = trade.vtSymbol
                self.posBufferDict[trade.vtSymbol] = posBuffer
            posBuffer.updateTradeData(trade)

            # ----------------------------------------------------------------------

    def setContractName(self, name):

        self.contractName = name

    # ----------------------------------------------------------------------
    def setDatabase(self, symbolList):
        contract_dict = Param_setting_dict
        self.symbolList = symbolList
        for symbol in symbolList:
            symbol = [symbol]
            self.dbClient = sqlalchemy.create_engine(str(r"mssql+pymssql://sa:qwert!@#$%@10.3.135.33:1433/COMMODITY"),
                                                     deprecate_large_types=True)
            dominantDF = pd.read_sql(
                "SELECT [DATE],[COMMODITY],[DOMINANT] FROM [%s].[dbo].[%s] where COMMODITY in (%s) and DATE BETWEEN '%s' and '%s' order by DATE"
                % ('COMMODITY', 'adj_dominantcontract', str(symbol)[1:-1], self.startDate, self.endDate),
                self.dbClient)

            def subdomiantFilter(symbol, dominantDF):

                # 取次主力合约数据
                getmax2 = lambda x: x.sort_values(ascending=False).index[1]
                # 提取合约基础信息表
                contract_basicinfoDF = pd.read_sql("SELECT * FROM [{0}].[dbo].[{1}] where {2} in ({3})".format(
                    *['COMMODITY', 'contract_basicinfo', b'交易代码_末值', str(symbol)[1:-1]]), self.dbClient)
                # deocde中文乱码
                # contract_basicinfoDF['上市地_末值'] = self.contract_basicinfoDF['上市地_末值'].map(lambda x: x.encode('latin1').decode('gbk'))

                # 取所选品种所有合约信息
                allcontractDF = pd.read_sql(
                    u"SELECT * FROM [%s].[dbo].[%s] where COMMODITY in (%s) and DATE BETWEEN '%s' and '%s'order by DATE"
                    % ('COMMODITY', 'commodity_contracts_day', str(symbol)[1:-1], self.startDate,
                       self.endDate),
                    self.dbClient)
                # 合并所有合约表与合约基础信息表
                futureDateDF = pd.merge(allcontractDF[['DATE', 'COMMODITY', 'CONTRACT']],
                                        contract_basicinfoDF[[unicode('代码'), unicode('变动日_末值'), unicode('最后交易日_末值')]],
                                        how='left',
                                        left_on=['CONTRACT'], right_on=[unicode('代码')])
                futureDateDF[unicode('最后交易日_末值')] = pd.to_datetime(futureDateDF[unicode('最后交易日_末值')])

                # 计算临近交割合约
                spotDF = pd.merge(
                    futureDateDF.groupby(['DATE', 'COMMODITY'], as_index=False).agg({unicode('最后交易日_末值'): 'min'}),
                    futureDateDF, how='left', left_on=['DATE', 'COMMODITY', unicode('最后交易日_末值')],
                    right_on=['DATE', 'COMMODITY', unicode('最后交易日_末值')])

                # 删除近月合约，不交易当月合约！
                spotDetailDF = allcontractDF.set_index(['DATE', 'CONTRACT']).loc[
                    spotDF.set_index(['DATE', 'CONTRACT']).index].reset_index()
                allcontracts_noSpot = allcontractDF.append(spotDetailDF).drop_duplicates(subset=['DATE', 'CONTRACT'],
                                                                                         keep=False).sort_values(
                    by='DATE').reset_index(drop=True)

                subDominant1 = allcontracts_noSpot.loc[
                    allcontracts_noSpot.groupby(['DATE', 'COMMODITY'], as_index=False)['OPENINT'].apply(
                        getmax2)].reset_index(drop=True)
                subDominant2 = allcontractDF.loc[
                    allcontractDF.groupby(['DATE', 'COMMODITY'], as_index=False)['OPENINT'].idxmax()].reset_index(
                    drop=True)
                subDominant3 = pd.concat([subDominant1, subDominant2], ignore_index=True,sort=True)
                dominantSelectDF = pd.merge(allcontractDF, dominantDF[['DATE', 'DOMINANT']], how='left',
                                            left_on=['DATE', 'CONTRACT'], right_on=['DATE', 'DOMINANT']).dropna().drop(
                    ['DOMINANT'], axis=1).reset_index(drop=True)
                # 确定实际自主定义的次主力合约
                subDominant = subDominant3.append(dominantSelectDF).drop_duplicates(subset=['DATE', 'CONTRACT'],
                                                                                    keep=False).sort_values(
                    by='DATE').reset_index(drop=True)
                # 3合约来回切换调整
                subDominant_adj = subDominant.loc[
                    subDominant.groupby(['DATE', 'COMMODITY'], as_index=False)['OPENINT'].idxmax()].reset_index(
                    drop=True)
                subDominant_adj.rename(
                    columns={'CLOSE': 'CLOSE_subdominant', 'HIGH': 'HIGH_subdominant', 'LOW': 'LOW_subdominant',
                             'MARGIN': 'MARGIN_subdominant', 'OPEN': 'OPEN_subdominant',
                             'OPENINT': 'OPENINT_subdominant',
                             'SETTLEMENT': 'SETTLEMENT_subdominant', 'VOL': 'VOL_subdominant',
                             'CONTRACT': 'SUBDOMINANT'}, inplace=True)
                return subDominant_adj[['DATE', 'COMMODITY', 'SUBDOMINANT']]

            subDomiantDF = subdomiantFilter(symbol, dominantDF)
            contractList = []
            contractList = pd.merge(dominantDF, subDomiantDF, how='left', on=['DATE', 'COMMODITY'])
            contractList.index = contractList['DATE']
            # if self.contract_dict=={}:
            #     self.contract_dict=dict(zip(contractList['DATE'],[{}]*len(contractList['DATE'])))
            """设置历史数据所用的数据库"""
            for day in contractList['DATE']:
                tradecontracts = pd.Series(contractList.loc[day]['DOMINANT']).append(
                    pd.Series(contractList.loc[day]['SUBDOMINANT'])).values
                codeDict = {}
                for code in tradecontracts:

                    commodityCode = re.findall("[A-Za-z]+", code)[0].upper()
                    if code in contractList.loc[day]['DOMINANT']:
                        contractProperty = 'DOMINANT'
                    else:
                        contractProperty = 'SUBDOMINANT'
                        if self.strategy.contractMode == 'Dominant':  # 如果策略的contractMode为主力合约，则不取次主力合约
                            continue
                    if contract_dict[commodityCode]['term'].lower() == 'bar':
                        DB_NAME = MINUTE_DB_NAME
                    if contract_dict[commodityCode]['term'].lower() == 'tick':
                        DB_NAME = TICK_DB_NAME
                    if contract_dict[commodityCode]['term'].lower() == 'daily':
                        DB_NAME = DAILY_DB_NAME
                    codeDict.update({code: {'symbol': code, 'term': contract_dict[commodityCode]['term'],
                                            'dbName': DB_NAME,
                                            'symbolInit': commodityCode,
                                            'initDays': contract_dict[commodityCode]['initDays'],
                                            'size': contract_dict[commodityCode]['size'],
                                            'rate': contract_dict[commodityCode]['rate'],
                                            'slip': contract_dict[commodityCode]['slip'],
                                            'property': contractProperty}})

                    # self.contract_dict[day].append(codeDict)

                    self.contract_dict[day].update(codeDict)

    # ---------------------------------------------------------------------
    
    def appendFunc(self,backtestingDataAppend, dbCursor):
            for d in dbCursor:
                  backtestingDataAppend(d)    
    def loadDailyHistoryData(self):
        """按照交易日分批载入历史数据,然后回放数据"""
        host, port = loadMongoSetting()
        self.initData = []  # 清空initData列表
        self.dbClient = pymongo.MongoClient(host, port)
        self.dbClient.admin.authenticate("htquant", "htgwf@2018", mechanism='SCRAM-SHA-1')
        co = 0
        # firstInsert = True
        # 寻找参数中最小最大的日期
        # self.findMdate()

        self.minDate = self.startDate
        self.maxDate = self.endDate
        # 得到日期列表 ，准备去掉假日
        dateList = self.getEveryDay(self.minDate, self.maxDate)
        dataStartDate = self.dataStartDate.strftime('%Y-%m-%d')
        strategyStartDate = self.strategyStartDate.strftime('%Y-%m-%d')
        dataEndDate = self.dataEndDate.strftime('%Y-%m-%d')
        self.strategy.onInit()
        
        #保存一个self.contract_dict确定rollingFlag不重复叠加
        self.contract_dict_ori=copy.deepcopy(self.contract_dict)        
        # 遍历该列表

        for date in dateList:
            #  遍历合约参数字典
            #  首先清空之前的回测行情数据内存
            self.backtestingData = []
            if date in self.contract_dict.keys():  # 判断是否交易日
                for contractCode, detail in self.contract_dict[date].items():

                    self.dbName = detail['dbName']
                    self.symbol = detail['symbol']
                    self.symbolCollection = 'TS_' + detail['symbolInit'] + '_TickDatas'
                    self.mode = detail['term'].lower()
                    self.mapping[self.symbol] = self.mode
                    collection = self.dbClient[self.dbName][self.symbolCollection]

                    # 如果当前日期不满足该合约日期则跳出
                    if date < strategyStartDate or date > dataEndDate:  # 其实日期fei
                        continue  # 可加入前置数据计算

                    flt = {'date': date, 'vtSymbol': self.symbol}
                    getItem = { 'vtSymbol': 1, 'exchange': 1 ,'lastPrice':1,'date':1,'time':1,'datetime':1,'bidPrice1':1,'askPrice1':1,'bidVolume1':1,'askVolume1':1,'openInterest':1,'volume':1}
        

                    # 载入当日新合约数据
                    if flt:
                        self.dbCursor = collection.find(flt,getItem)
                        co = co + self.dbCursor.count()
                        symbollist = []
                        timelist = []
                        # due to id and correct this
                        self.strategy.writeCtaLog(u'载入%s回测数据\\n' % (self.symbol))
                        # self.output(u'载入%s回测数据\\n' % (self.symbol))
                        backtestingDataAppend = self.backtestingData.append
                        #for d in self.dbCursor:
                            #backtestingDataAppend(d)
                        self.appendFunc(backtestingDataAppend,self.dbCursor) 
                        # del self.dbCursor
                        # gc.collect()

                # 每天初始化，主要为了导入持仓
                # self.strategy.inited = True
                # self.strategy.onInit()
                # 检查无是否有品种换月（无持仓）,主力次主力互换
                self.rollingFlag=[]
                if self.lastDate:
                    # self.rollingFlag =[x for x in [y.keys()[0] for y in self.contract_dict[self.lastDate]] if
                    #                      x not in [z.keys()[0] for z in self.contract_dict[date]]]

                    self.rollingFlag = [x for x in self.contract_dict_ori[self.lastDate].keys() if
                                        x not in self.contract_dict_ori[date].keys()]

                # 载入已有持仓数据

                # 找出已有持仓和当日订阅合约的差集
                if self.rollingContract or self.rollingFlag:
                    diffcontractList=list(set(self.rollingContract + self.rollingFlag))
                    for diffcontract in diffcontractList:
                         #附加旧合约contract_dict
                        oldcontract = self.contract_dict[self.lastDate][diffcontract]


                        oldcontract['property'] = 'old'
                        #except Exception as e:
                            #pass
                        #self.contract_dict[date][diffcontract] = oldcontract
                        # 更新订阅合约
                        self.contract_dict[date].update({diffcontract:oldcontract})
                        
                        self.dbName = self.contract_dict[self.lastDate][diffcontract]['dbName']
                        self.symbol = self.contract_dict[self.lastDate][diffcontract]['symbol']
                        self.symbolCollection = 'TS_' + self.contract_dict[self.lastDate][diffcontract][
                            'symbolInit'] + '_TickDatas'
                        self.mode = self.contract_dict[self.lastDate][diffcontract]['term'].lower()
                        self.mapping[self.symbol] = self.mode
                        collection = self.dbClient[self.dbName][self.symbolCollection]

                        flt = {'date': date, 'vtSymbol': self.symbol}

                        # 载入当日新合约数据
                        if flt:
                            self.dbCursor = collection.find(flt)
                            co = co + self.dbCursor.count()
                            symbollist = []
                            timelist = []
                            # due to id and correct this
                            self.strategy.writeCtaLog(u'载入%s回测数据\\n' % (self.symbol))
                            # self.output(u'载入%s回测数据\\n' % (self.symbol))
                            backtestingDataAppend = self.backtestingData.append
                            for d in self.dbCursor:
                                backtestingDataAppend(d)

                start = time.time()
                self.strategy.writeCtaLog(u'载入%s日数据' % (date) + u'当日数据量%s:' % co)
                # self.output(u'载入%s日数据' %(date))
                if date=='2017-10-16':
                    pass
                # self.output(u'当日数据量%s:'%co)
                dataSort = sorted(self.backtestingData, key=lambda e: e.__getitem__('datetime'))
                self.strategy.writeCtaLog(u'交易日 %s开始回测' % (date))
                # self.output(u'交易日 %s开始回测'%(date))
                self.strategy.trading = True
                self.strategy.onStart()
                self.output(u'交易日 %s开始回放数据' % (date))
                for d in dataSort:
                    dataClass = CtaTickData
                    func = self.newTick
                    data = dataClass()
                    data.__dict__ = d
                    func(data)
                self.output(u'日期%s天数据回放结束' % (date))
                end = time.time()
                elapsed = end - start
                print "Time taken: ", elapsed, "seconds."
                self.lastDate = date
                self.queue.put(date)   
    def getEveryDay(self, begin_date, end_date):
        date_list = []
        import datetime
        begin_date = datetime.datetime.strptime(begin_date, "%Y-%m-%d")
        end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        while begin_date <= end_date:
            date_str = begin_date.strftime("%Y-%m-%d")
            date_list.append(date_str)
            begin_date += datetime.timedelta(days=1)
        return date_list

        # ----------------------------------------------------------------------

    def newBar(self, bar):
        """新的K线"""
        self.bar = bar
        self.dt = bar.datetime
        self.crossLimitOrder()  # 先撮合限价单
        self.crossStopOrder()  # 再撮合停止单
        self.strategy.onBar(bar)  # 推送K线到策略中

        self.updateDailyClose(bar.vtSymbol, bar.datetime, bar.close)

    # ----------------------------------------------------------------------
    def newTick(self, tick):
        """新的Tick"""
        self.tick = tick
        self.dt = tick.datetime
        self.crossLimitOrder()
        self.crossStopOrder()
        # self.strategy.onTick_only(tick)
        self.strategy.onTick(tick)

        self.updateDailyClose(tick.vtSymbol, tick.datetime, tick.lastPrice)  # 这里需要加入合约名称，用来区分对应的收盘价格

    def newDaily(self, daily):
        """新的daily"""
        self.daily = daily
        self.dt = daily.datetime
        self.crossLimitOrder()
        self.crossStopOrder()
        self.strategy.onTick(daily)

        self.updateDailyClose(daily.vtSymbol, daily.datetime, daily.close)  # 这里需要加入合约名称，用来区分对应的收盘价格

    # ----------------------------------------------------------------------
    def initStrategy(self, strategyClass, setting=None):
        """
        初始化策略
        setting是策略的参数设置，如果使用类中写好的默认设置则可以不传该参数
        """
        self.strategy = strategyClass(self, setting)
        self.strategy.name = self.strategy.className

    # ----------------------------------------------------------------------
    def sendOrder(self, vtSymbol, orderType, price, volume, strategy):
        """发单"""
        self.limitOrderCount += 1
        orderID = str(self.limitOrderCount)

        order = VtOrderData()
        order.vtSymbol = vtSymbol
        order.price = price
        order.totalVolume = volume
        order.status = STATUS_NOTTRADED  # 刚提交尚未成交
        order.orderID = orderID
        order.vtOrderID = orderID
        order.orderTime = str(self.dt)

        # CTA委托类型映射
        if orderType == CTAORDER_BUY:
            order.direction = DIRECTION_LONG
            order.offset = OFFSET_OPEN
        elif orderType == CTAORDER_SELL:
            order.direction = DIRECTION_SHORT
            order.offset = OFFSET_CLOSE
        elif orderType == CTAORDER_SHORT:
            order.direction = DIRECTION_SHORT
            order.offset = OFFSET_OPEN
        elif orderType == CTAORDER_COVER:
            order.direction = DIRECTION_LONG
            order.offset = OFFSET_CLOSE

            # 保存到限价单字典中
        self.workingLimitOrderDict[orderID] = order
        self.limitOrderDict[orderID] = order

        self.orderStrategyDict[orderID].update({self.strategy.className: self.strategy.signalName})

        # 保存到下单目标持仓到数据库内
        self.strategy.updatePosTarget(order, self.strategy.signalName)

        return [orderID]

    # ----------------------------------------------------------------------
    def cancelOrder(self, vtOrderID):
        """撤单"""
        if vtOrderID in self.workingLimitOrderDict:
            order = self.workingLimitOrderDict[vtOrderID]
            order.status = STATUS_CANCELLED
            order.cancelTime = str(self.dt)
            self.strategy.cancelDBorder(vtOrderID, self)
            del self.workingLimitOrderDict[vtOrderID]

    # ----------------------------------------------------------------------
    def sendStopOrder(self, vtSymbol, orderType, price, volume, strategy):
        """发停止单（本地实现）"""
        self.stopOrderCount += 1
        stopOrderID = STOPORDERPREFIX + str(self.stopOrderCount)

        so = StopOrder()
        so.vtSymbol = vtSymbol
        so.price = price
        so.volume = volume
        so.strategy = strategy
        so.stopOrderID = stopOrderID
        so.status = STOPORDER_WAITING

        if orderType == CTAORDER_BUY:
            so.direction = DIRECTION_LONG
            so.offset = OFFSET_OPEN
        elif orderType == CTAORDER_SELL:
            so.direction = DIRECTION_SHORT
            so.offset = OFFSET_CLOSE
        elif orderType == CTAORDER_SHORT:
            so.direction = DIRECTION_SHORT
            so.offset = OFFSET_OPEN
        elif orderType == CTAORDER_COVER:
            so.direction = DIRECTION_LONG
            so.offset = OFFSET_CLOSE

            # 保存stopOrder对象到字典中
        self.stopOrderDict[stopOrderID] = so
        self.workingStopOrderDict[stopOrderID] = so

        return [stopOrderID]

    # ----------------------------------------------------------------------
    def cancelStopOrder(self, stopOrderID):
        """撤销停止单"""
        # 检查停止单是否存在
        if stopOrderID in self.workingStopOrderDict:
            so = self.workingStopOrderDict[stopOrderID]
            so.status = STOPORDER_CANCELLED
            del self.workingStopOrderDict[stopOrderID]

    # ----------------------------------------------------------------------
    def crossLimitOrder(self):
        """基于最新数据撮合限价单"""
        # 先确定会撮合成交的价格
        if self.mode == self.BAR_MODE:
            contractCode = self.bar.vtSymbol
            buyCrossPrice = self.bar.low  # 若买入方向限价单价格高于该价格，则会成交
            sellCrossPrice = self.bar.high  # 若卖出方向限价单价格低于该价格，则会成交
            buyBestCrossPrice = self.bar.open  # 在当前时间点前发出的买入委托可能的最优成交价
            sellBestCrossPrice = self.bar.open  # 在当前时间点前发出的卖出委托可能的最优成交价
        else:
            contractCode = self.tick.vtSymbol
            buyCrossPrice = self.tick.askPrice1
            sellCrossPrice = self.tick.bidPrice1
            buyBestCrossPrice = self.tick.askPrice1
            sellBestCrossPrice = self.tick.bidPrice1
            askVolume = self.tick.askVolume1
            bidVolume = self.tick.bidVolume1

        # 遍历限价单字典中的所有限价单
        for orderID, order in self.workingLimitOrderDict.items():
            # 判断是否会成交
            if contractCode == order.vtSymbol:
                buyCross = order.direction == DIRECTION_LONG and order.price >= buyCrossPrice and askVolume != 0
                sellCross = order.direction == DIRECTION_SHORT and order.price <= sellCrossPrice and bidVolume != 0

                # 如果发生了成交
                if buyCross or sellCross:
                    # 推送成交数据
                    self.tradeCount += 1  # 成交编号自增1
                    tradeID = str(self.tradeCount)
                    trade = VtTradeData()
                    trade.vtSymbol = order.vtSymbol
                    trade.tradeID = tradeID
                    trade.vtTradeID = tradeID
                    trade.orderID = order.orderID
                    trade.vtOrderID = order.orderID
                    trade.direction = order.direction
                    trade.offset = order.offset

                    # 以买入为例：
                    # 1. 假设当根K线的OHLC分别为：100, 125, 90, 110
                    # 2. 假设在上一根K线结束(也是当前K线开始)的时刻，策略发出的委托为限价105
                    # 3. 则在实际中的成交价会是100而不是105，因为委托发出时市场的最优价格是100
                    tradedStatus = []
                    if buyCross:
                        trade.price = min(order.price, buyBestCrossPrice)
                        self.strategy.pos += order.totalVolume
                        if (order.totalVolume - order.tradedVolume) > askVolume:
                            tradeVolume = askVolume
                            tradedStatus = STATUS_PARTTRADED
                        else:
                            tradeVolume = (order.totalVolume - order.tradedVolume)
                            tradedStatus = STATUS_ALLTRADED

                    else:
                        trade.price = max(order.price, sellBestCrossPrice)
                        self.strategy.pos -= order.totalVolume
                        if (order.totalVolume - order.tradedVolume) > bidVolume:
                            tradeVolume = bidVolume
                            tradedStatus = STATUS_PARTTRADED
                        else:
                            tradeVolume = (order.totalVolume - order.tradedVolume)
                            tradedStatus = STATUS_ALLTRADED

                    trade.volume = tradeVolume
                    trade.tradeTime = str(self.dt)
                    trade.dt = self.dt
                    order.status = tradedStatus
                    self.strategy.onTrade(trade)

                    self.tradeDict[tradeID] = trade

                    if tradedStatus == STATUS_PARTTRADED:
                        # 推送委托数据
                        order.tradedVolume += tradeVolume
                        self.strategy.onOrder(order)
                    else:
                        # 推送委托数据
                        order.tradedVolume += tradeVolume
                        self.strategy.onOrder(order)
                        del self.workingLimitOrderDict[orderID]

        # #更新持仓缓存数据
        #        if trade.vtSymbol :
        #           posBuffer = self.posBufferDict.get(trade.vtSymbol, None)
        #           if not posBuffer:
        #              posBuffer = PositionBuffer()
        #              posBuffer.vtSymbol = trade.vtSymbol
        #              self.posBufferDict[trade.vtSymbol] = posBuffer
        #           posBuffer.updateTradeData(trade)
        #         #从字典中删除该限价单

    # ----------------------------------------------------------------------
    def crossStopOrder(self):
        """基于最新数据撮合停止单"""
        # 先确定会撮合成交的价格，这里和限价单规则相反
        if self.mode == self.BAR_MODE:
            contractCode = self.bar.vtSymbol
            buyCrossPrice = self.bar.high  # 若买入方向停止单价格低于该价格，则会成交
            sellCrossPrice = self.bar.low  # 若卖出方向限价单价格高于该价格，则会成交
            bestCrossPrice = self.bar.open  # 最优成交价，买入停止单不能低于，卖出停止单不能高于
        else:
            contractCode = self.tick.vtSymbol
            buyCrossPrice = self.tick.lastPrice
            sellCrossPrice = self.tick.lastPrice
            bestCrossPrice = self.tick.lastPrice

        # 遍历停止单字典中的所有停止单
        for stopOrderID, so in self.workingStopOrderDict.items():
            # 判断是否会成交
            if contractCode == order.vtSymbol:
                buyCross = so.direction == DIRECTION_LONG and so.price <= buyCrossPrice
                sellCross = so.direction == DIRECTION_SHORT and so.price >= sellCrossPrice
            else:
                continue

            # 如果发生了成交
            if buyCross or sellCross:
                # 更新停止单状态，并从字典中删除该停止单
                so.status = STOPORDER_TRIGGERED
                if stopOrderID in self.workingStopOrderDict:
                    del self.workingStopOrderDict[stopOrderID]

                    # 推送成交数据
                self.tradeCount += 1  # 成交编号自增1
                tradeID = str(self.tradeCount)
                trade = VtTradeData()
                trade.vtSymbol = self.contractName
                trade.tradeID = tradeID
                trade.vtTradeID = tradeID

                if buyCross:
                    self.strategy.pos += so.volume
                    trade.price = max(bestCrossPrice, so.price)
                else:
                    self.strategy.pos -= so.volume
                    trade.price = min(bestCrossPrice, so.price)

                self.limitOrderCount += 1
                orderID = str(self.limitOrderCount)
                trade.orderID = orderID
                trade.vtOrderID = orderID
                trade.direction = so.direction
                trade.offset = so.offset
                trade.volume = so.volume
                trade.tradeTime = str(self.dt)
                trade.dt = self.dt
                self.strategy.onTrade(trade)

                self.tradeDict[tradeID] = trade

                # 推送委托数据
                so.status = STOPORDER_TRIGGERED

                order = VtOrderData()
                order.vtSymbol = so.vtSymbol
                order.symbol = so.vtSymbol
                order.orderID = orderID
                order.vtOrderID = orderID
                order.direction = so.direction
                order.offset = so.offset
                order.price = so.price
                order.totalVolume = so.volume
                order.tradedVolume = so.volume
                order.status = STATUS_ALLTRADED
                order.orderTime = trade.tradeTime
                self.strategy.onOrder(order)

                self.limitOrderDict[orderID] = order

        # 更新持仓缓存数据
        #         if trade.vtSymbol :
        #            posBuffer = self.posBufferDict.get(trade.vtSymbol, None)
        #            if not posBuffer:
        #               posBuffer = PositionBuffer()
        #               posBuffer.vtSymbol = trade.vtSymbol
        #               self.posBufferDict[trade.vtSymbol] = posBuffer
        #            posBuffer.updateTradeData(trade)

    # ----------------------------------------------------------------------

    def insertData(self, dbName, collectionName, data):
        """考虑到回测中不允许向数据库插入数据，防止实盘交易中的一些代码出错"""
        pass

    # ----------------------------------------------------------------------
    def loadBar(self, dbName, collectionName, startDate):
        """直接返回初始化数据列表中的Bar"""
        return self.initData

    # ----------------------------------------------------------------------
    def loadTick(self, dbName, collectionName, startDate):
        """直接返回初始化数据列表中的Tick"""
        return self.initData

    # ----------------------------------------------------------------------
    def writeCtaLog(self, content):
        """记录日志"""
        self.logger.info(content)
        # log = str(self.dt) + ' ' + content
        #         # self.logList.append(log)

    # ----------------------------------------------------------------------
    def readParam_Setting(self):
        """读取多合约品种策略的参数"""
        mapping = {'tick': 'tick', 'bar': 'bar', 'daily': 'daily'}
        for Param_id, detail in Param_setting_dict.items():
            Mode_type = (detail['term']).lower()
            if Mode_type not in mapping:
                print u"回测模式输入错误"

    # ----------------------------------------------------------------------

    def output(self, content):
        """输出内容"""
        print str(datetime.now()) + "\t" + content
        # ----------------------------------------------------------------------

    def createDictCSV(self, fileName="", dataDict={}):
        with open(fileName, "wb") as csvFile:
            csvWriter = csv.writer(csvFile)
            for k, v in dataDict.items():
                csvWriter.writerow(
                    [k, v.vtSymbol, v.tradeTime, str(v.direction).encode('GBK'), str(v.offset).encode('GBK'), v.volume,
                     v.price])
            csvFile.close()
            # ----------------------------------------------------------------------

    def calculateBacktestingResult(self):
        """
        计算回测结果
        """
        self.output(u'计算回测结果')

        # 首先基于回测后的成交记录，计算每笔交易的盈亏
        resultList = {}  # 交易结果字典

        longTrade = []  # 未平仓的多头交易
        shortTrade = []  # 未平仓的空头交易
        tradeTimeList = []  # 每笔成交时间戳
        posList = [0]  # 每笔成交后的持仓情况

        # self.createDictCSV("tradeDictSave.csv",self.tradeDict)######################################
        # pd.DataFrame(list(self.tradeDict.items()) , columns=self.tradeDict.keys())
        newDict = {}
        for id, detail in self.tradeDict.items():
            newDict[id] = detail.vtSymbol
            # newDict[id] = {'symbol': detail['vtSymbol'],'tradeTime':detail['tradeTime'],
            # 'vtTradeID': detail['vtTradeID'], 'price':detail['price'],
            # 'offset' : detail['offset'], 'volume': detail['volume']}

        tradeFrame = pd.DataFrame.from_dict(newDict, orient='index')
        # if not tradeFrame :
        # self.output(u'没有交易结果')

        tradeFrame.columns = ['symbol']

        # for trade in self.tradeDict.values():
        # 根据遍历的合约分组计算
        for name, group in tradeFrame.groupby('symbol'):
            # 遍历分组合约的group
            # ix = []
            # ix = list (group('symbol').index)

            # for trade in  self.tradeDict.get(ix)
            self.mode = self.mapping[name]
            resultList[name] = []
            self.output(u'整理%s的回测结果' % name)
            for id, detail in self.contract_dict.items():
                if id == name:
                    self.rate = detail['rate']
                    self.slippage = detail['slip']
                    self.size = detail['size']

            for ix in group.index:

                # 复制成交对象，因为下面的开平仓交易配对涉及到对成交数量的修改
                # 若不进行复制直接操作，则计算完后所有成交的数量会变成0
                trade = self.tradeDict[ix]
                trade = copy.copy(trade)
                # 多头交易
                if trade.direction == DIRECTION_LONG:
                    # 如果尚无空头交易
                    if not shortTrade:
                        longTrade.append(trade)
                    # 当前多头交易为平空
                    else:
                        while True:
                            entryTrade = shortTrade[0]
                            exitTrade = trade

                            # 清算开平仓交易
                            closedVolume = min(exitTrade.volume, entryTrade.volume)
                            result = TradingResult(entryTrade.price, entryTrade.dt,
                                                   exitTrade.price, exitTrade.dt,
                                                   -closedVolume, self.rate, self.slippage, self.size)
                            resultList[name].append(result)
                            ########
                            posList.extend([-1, 0])
                            tradeTimeList.extend([result.entryDt, result.exitDt])

                            # 计算未清算部分
                            entryTrade.volume -= closedVolume
                            exitTrade.volume -= closedVolume

                            # 如果开仓交易已经全部清算，则从列表中移除
                            if not entryTrade.volume:
                                shortTrade.pop(0)

                            # 如果平仓交易已经全部清算，则退出循环
                            if not exitTrade.volume:
                                break

                            # 如果平仓交易未全部清算，
                            if exitTrade.volume:
                                # 且开仓交易已经全部清算完，则平仓交易剩余的部分
                                # 等于新的反向开仓交易，添加到队列中
                                if not shortTrade:
                                    longTrade.append(exitTrade)
                                    break
                                # 如果开仓交易还有剩余，则进入下一轮循环
                                else:
                                    pass

                # 空头交易
                else:
                    # 如果尚无多头交易
                    if not longTrade:
                        shortTrade.append(trade)
                    # 当前空头交易为平多
                    else:
                        while True:
                            entryTrade = longTrade[0]
                            exitTrade = trade

                            # 清算开平仓交易
                            closedVolume = min(exitTrade.volume, entryTrade.volume)
                            result = TradingResult(entryTrade.price, entryTrade.dt,
                                                   exitTrade.price, exitTrade.dt,
                                                   closedVolume, self.rate, self.slippage, self.size)
                            resultList[name].append(result)
                            ##############
                            posList.extend([1, 0])
                            tradeTimeList.extend([result.entryDt, result.exitDt])
                            # 计算未清算部分
                            entryTrade.volume -= closedVolume
                            exitTrade.volume -= closedVolume

                            # 如果开仓交易已经全部清算，则从列表中移除
                            if not entryTrade.volume:
                                longTrade.pop(0)

                            # 如果平仓交易已经全部清算，则退出循环
                            if not exitTrade.volume:
                                break

                            # 如果平仓交易未全部清算，
                            if exitTrade.volume:
                                # 且开仓交易已经全部清算完，则平仓交易剩余的部分
                                # 等于新的反向开仓交易，添加到队列中
                                if not longTrade:
                                    shortTrade.append(exitTrade)
                                    break
                                # 如果开仓交易还有剩余，则进入下一轮循环
                                else:
                                    pass
                            self.mode = (self.mapping.get(name)).lower()
                            # 到最后交易日尚未平仓的交易，则以最后价格平仓
            if self.mode == self.BAR_MODE:
                endPrice = self.bar.close
            else:
                endPrice = self.tick.lastPrice

            for trade in longTrade:
                result = TradingResult(trade.price, trade.dt, endPrice, self.dt,
                                       trade.volume, self.rate, self.slippage, self.size)
                resultList[name].append(result)

            for trade in shortTrade:
                result = TradingResult(trade.price, trade.dt, endPrice, self.dt,
                                       -trade.volume, self.rate, self.slippage, self.size)
                resultList[name].append(result)

                # 检查是否有交易
        if not resultList:
            self.output(u'%s无交易结果' % name)
            return {}

        # 然后基于每笔交易的结果，我们可以计算具体的盈亏曲线和最大回撤等
        # 根据resultList字典 区分合约统计
        countResult = {}
        for name in resultList.keys():

            capital = 0  # 资金
            maxCapital = 0  # 资金最高净值
            drawdown = 0  # 回撤

            totalResult = 0  # 总成交数量
            totalTurnover = 0  # 总成交金额（合约面值）
            totalCommission = 0  # 总手续费
            totalSlippage = 0  # 总滑点

            timeList = []  # 时间序列
            pnlList = []  # 每笔盈亏序列
            capitalList = []  # 盈亏汇总的时间序列
            drawdownList = []  # 回撤的时间序列

            winningResult = 0  # 盈利次数
            losingResult = 0  # 亏损次数
            totalWinning = 0  # 总盈利金额
            totalLosing = 0  # 总亏损金额

            for result in resultList[name]:
                capital += result.pnl
                maxCapital = max(capital, maxCapital)
                drawdown = capital - maxCapital

                pnlList.append(result.pnl)
                timeList.append(result.exitDt)  # 交易的时间戳使用平仓时间
                capitalList.append(capital)
                drawdownList.append(drawdown)

                totalResult += 1
                totalTurnover += result.turnover
                totalCommission += result.commission
                totalSlippage += result.slippage

                if result.pnl >= 0:
                    winningResult += 1
                    totalWinning += result.pnl
                else:
                    losingResult += 1
                    totalLosing += result.pnl

            # 计算盈亏相关数据
            winningRate = winningResult / totalResult * 100  # 胜率

            averageWinning = 0  # 这里把数据都初始化为0
            averageLosing = 0
            profitLossRatio = 0

            if winningResult:
                averageWinning = totalWinning / winningResult  # 平均每笔盈利
            if losingResult:
                averageLosing = totalLosing / losingResult  # 平均每笔亏损
            if averageLosing:
                profitLossRatio = -averageWinning / averageLosing  # 盈亏比

            # 返回回测结果
            d = {}
            d['capital'] = capital
            d['maxCapital'] = maxCapital
            d['drawdown'] = drawdown
            d['totalResult'] = totalResult
            d['totalTurnover'] = totalTurnover
            d['totalCommission'] = totalCommission
            d['totalSlippage'] = totalSlippage
            d['timeList'] = timeList
            d['pnlList'] = pnlList
            d['capitalList'] = capitalList
            d['drawdownList'] = drawdownList
            d['winningRate'] = winningRate
            d['averageWinning'] = averageWinning
            d['averageLosing'] = averageLosing
            d['profitLossRatio'] = profitLossRatio
            countResult[name] = d
        return countResult

    # ----------------------------------------------------------------------
    def showBacktestingTotalResult(self):
        countResult = self.calculateBacktestingResult()
        for id, detail in countResult.items():
            self.output(u'对于合约%s的交易结果:' % id)
            self.showBacktestingResult(detail)

            # ----------------------------------------------------------------------

    # ----------------------------------------------------------------------
    def putStrategyEvent(self, name):
        """发送策略更新事件，回测中忽略"""
        pass

    # ----------------------------------------------------------------------
    def setSlippage(self, slippage):
        """设置滑点点数"""
        self.slippage = slippage

    # ----------------------------------------------------------------------
    def setSize(self, size):
        """设置合约大小"""
        self.size = size

    # ----------------------------------------------------------------------
    def setRate(self, rate):
        """设置佣金比例"""
        self.rate = rate

    # -----------------------------------------------------------------------
    def updateDailyClose(self, symbol, dt, price):
        """更新每日收盘价"""
        if dt.hour <= 15:
            date = dt.date()

            if date not in self.dailyResultDict:
                self.dailyResultDict[date] = DailyResult(symbol, date, price, self.contract_dict)  #
            else:
                self.dailyResultDict[date].closePrice.update({symbol: price})

    # ----------------------------------------------------------------------
    def calculateDailyResult(self):
        """计算按日统计的交易结果"""
        self.output(u'计算按日统计结果')
        # 处理夜盘下单收益计算
        # 工作日序列排序
        workingDays = sorted(self.contract_dict.keys())

        # 将成交添加到每日交易结果中
        for trade in self.tradeDict.values():
            if trade.dt.hour > 15:

                try:
                    nextWorkingDay = workingDays[workingDays.index(trade.dt.strftime('%Y-%m-%d')) + 1]
                except:
                    nextWorkingDay = workingDays[workingDays.index(trade.dt.strftime('%Y-%m-%d'))]
                # if trade.dt.hour > 15:
                newTradeDay = datetime.strptime(nextWorkingDay, '%Y-%m-%d')
            else:
                newTradeDay = trade.dt

            date = newTradeDay.date()

            dailyResult = self.dailyResultDict[date]

            dailyResult.addTrade(trade)

        # 遍历计算每日结果
        previousClose = {}
        openPosition = {}
        for dictDay in self.dailyResultDict.keys():
            previousClose[str(dictDay)] = dict(
                zip(self.contract_dict[str(dictDay)].keys(), [0] * len(self.contract_dict[str(dictDay)].keys())))
            openPosition[str(dictDay)] = dict(
                zip(self.contract_dict[str(dictDay)].keys(), [0] * len(self.contract_dict[str(dictDay)].keys())))

        for dailyResult in self.dailyResultDict.values():
            # 求下一交易日，存前收盘价
            try:
                nextWorkingDay = workingDays[workingDays.index(dailyResult.date.strftime('%Y-%m-%d')) + 1]
            except:
                nextWorkingDay = []

            # 按照symbol 进行区分统计
            for id, detail in self.contract_dict[str(dailyResult.date)].items():
                if id in dailyResult.closePrice.keys():
                    dailyResult.previousClose[id] = previousClose[str(dailyResult.date)][id]
                    # 如果有下一工作日才赋值
                    if nextWorkingDay:
                        previousClose[nextWorkingDay][id] = dailyResult.closePrice[id]
                    # 带入该合约的乘数和滑点
                    dailyResult.calculatePnl(id, openPosition[str(dailyResult.date)][id], detail['size'],
                                             detail['rate'], detail['slip'])
                    if nextWorkingDay:
                        openPosition[nextWorkingDay][id] = dailyResult.closePosition[id]

            # 对于不同合约的当日结果进行求和计算
            for pnl in dailyResult.netPnl.values():
                dailyResult.totalAllPnl += pnl
            for commission in dailyResult.commission.values():
                dailyResult.totalCommission += commission
            for slippage in dailyResult.slippage.values():
                dailyResult.totalSlippage += slippage
            for turnover in dailyResult.turnover.values():
                dailyResult.totalTurnover += turnover

        # 生成DataFrame
        resultDict = {k: [] for k in dailyResult.__dict__.keys()}
        for dailyResult in self.dailyResultDict.values():
            for k, v in dailyResult.__dict__.items():
                resultDict[k].append(v)

        resultDf = pd.DataFrame.from_dict(resultDict)

        # 计算衍生数据
        resultDf = resultDf.set_index('date')

        return resultDf

    # ----------------------------------------------------------------------
    def showDailyResult(self, df=None):
        """显示按日统计的交易结果"""
        if df is None:
            df = self.calculateDailyResult()
        df.to_excel('resultsDF.xlsx')
        import numpy as np
        df['balance'] = df['totalAllPnl'].cumsum() + self.capital
        df['return'] = (np.log(df['balance']) - np.log(df['balance'].shift(1))).fillna(0)
        df['highlevel'] = df['balance'].rolling(min_periods=1, window=len(df), center=False).max()
        df['drawdown'] = df['balance'] - df['highlevel']

        # 计算统计结果
        startDate = df.index[0]
        endDate = df.index[-1]

        totalDays = len(df)
        profitDays = len(df[df['totalAllPnl'] > 0])
        lossDays = len(df[df['totalAllPnl'] < 0])

        endBalance = df['balance'].iloc[-1]
        maxDrawdown = df['drawdown'].min()

        totalNetPnl = df['totalAllPnl'].sum()
        dailyNetPnl = totalNetPnl / totalDays

        totalCommission = df['totalCommission'].sum()
        dailyCommission = totalCommission / totalDays

        totalSlippage = df['totalSlippage'].sum()
        dailySlippage = totalSlippage / totalDays

        totalTurnover = df['totalTurnover'].sum()
        dailyTurnover = totalTurnover / totalDays

        totalTradeCount = df['tradeCount'].sum()
        dailyTradeCount = totalTradeCount / totalDays

        totalReturn = (endBalance / self.capital - 1) * 100
        dailyReturn = df['return'].mean() * 100
        returnStd = df['return'].std() * 100

        if returnStd:
            sharpeRatio = dailyReturn / returnStd * np.sqrt(240)
        else:
            sharpeRatio = 0

        # 输出统计结果
        self.output('-' * 30)
        self.output(u'首个交易日：\t%s' % startDate)
        self.output(u'最后交易日：\t%s' % endDate)

        self.output(u'总交易日：\t%s' % totalDays)
        self.output(u'盈利交易日\t%s' % profitDays)
        self.output(u'亏损交易日：\t%s' % lossDays)

        self.output(u'起始资金：\t%s' % self.capital)
        self.output(u'结束资金：\t%s' % formatNumber(endBalance))

        self.output(u'总收益率：\t%s' % formatNumber(totalReturn))
        self.output(u'总盈亏：\t%s' % formatNumber(totalNetPnl))
        self.output(u'最大回撤: \t%s' % formatNumber(maxDrawdown))

        self.output(u'总手续费：\t%s' % formatNumber(totalCommission))
        self.output(u'总滑点：\t%s' % formatNumber(totalSlippage))
        self.output(u'总成交金额：\t%s' % formatNumber(totalTurnover))
        self.output(u'总成交笔数：\t%s' % formatNumber(totalTradeCount))

        self.output(u'日均盈亏：\t%s' % formatNumber(dailyNetPnl))
        self.output(u'日均手续费：\t%s' % formatNumber(dailyCommission))
        self.output(u'日均滑点：\t%s' % formatNumber(dailySlippage))
        self.output(u'日均成交金额：\t%s' % formatNumber(dailyTurnover))
        self.output(u'日均成交笔数：\t%s' % formatNumber(dailyTradeCount))

        self.output(u'日均收益率：\t%s%%' % formatNumber(dailyReturn))
        self.output(u'收益标准差：\t%s%%' % formatNumber(returnStd))
        self.output(u'Sharpe Ratio：\t%s' % formatNumber(sharpeRatio))

        # 绘图
        fig2 = plt.figure(figsize=(10, 16))

        pBalance = plt.subplot(4, 1, 1)
        pBalance.set_title('Balance')
        df['balance'].plot(legend=True)

        pDrawdown = plt.subplot(4, 1, 2)
        pDrawdown.set_title('Drawdown')
        pDrawdown.fill_between(range(len(df)), df['drawdown'].values)

        pPnl = plt.subplot(4, 1, 3)
        pPnl.set_title('Daily Pnl')
        df['totalAllPnl'].plot(kind='bar', legend=False, grid=False, xticks=[])

        pKDE = plt.subplot(4, 1, 4)
        pKDE.set_title('Daily Pnl Distribution')
        df['totalAllPnl'].hist(bins=50)

        plt.show()

    # ----------------------------------------------------------------------
    def runOptimization(self, strategyClass, optimizationSetting):
        """优化参数"""
        # 获取优化设置
        settingList = optimizationSetting.generateSetting()
        targetName = optimizationSetting.optimizeTarget

        # 检查参数设置问题
        if not settingList or not targetName:
            self.output(u'优化设置有问题，请检查')

        # 遍历优化
        resultList = []
        for setting in settingList:
            self.clearBacktestingResult()
            self.output('-' * 30)
            self.output('setting: %s' % str(setting))
            self.initStrategy(strategyClass, setting)
            self.runBacktesting()
            d = self.calculateBacktestingResult()
            try:
                targetValue = d[targetName]
            except KeyError:
                targetValue = 0
            resultList.append(([str(setting)], targetValue))

        # 显示结果
        resultList.sort(reverse=True, key=lambda result: result[1])
        self.output('-' * 30)
        self.output(u'优化结果：')
        for result in resultList:
            self.output(u'%s: %s' % (result[0], result[1]))
        return result

    # ----------------------------------------------------------------------
    def clearBacktestingResult(self):
        """清空之前回测的结果"""
        # 清空限价单相关
        self.limitOrderCount = 0
        self.limitOrderDict.clear()
        self.workingLimitOrderDict.clear()

        # 清空停止单相关
        self.stopOrderCount = 0
        self.stopOrderDict.clear()
        self.workingStopOrderDict.clear()

        # 清空成交相关
        self.tradeCount = 0
        self.tradeDict.clear()

    # ----------------------------------------------------------------------
    def runParallelOptimization(self, strategyClass, optimizationSetting):
        """并行优化参数"""
        # 获取优化设置
        settingList = optimizationSetting.generateSetting()
        targetName = optimizationSetting.optimizeTarget

        # 检查参数设置问题
        if not settingList or not targetName:
            self.output(u'优化设置有问题，请检查')

        # 多进程优化，启动一个对应CPU核心数量的进程池
        pool = multiprocessing.Pool(multiprocessing.cpu_count())
        l = []

        for setting in settingList:
            l.append(pool.apply_async(optimize, (strategyClass, setting,
                                                 targetName, self.mode,
                                                 self.startDate, self.initDays, self.endDate,
                                                 self.slippage, self.rate, self.size,
                                                 self.dbName, self.symbol)))
        pool.close()
        pool.join()

        # 显示结果
        resultList = [res.get() for res in l]
        resultList.sort(reverse=True, key=lambda result: result[1])
        self.output('-' * 30)
        self.output(u'优化结果：')
        for result in resultList:
            self.output(u'%s: %s' % (result[0], result[1]))

            # -----------------------------------------------------------------------

    def updateTradeData(self, trade):
        """更新成交数据"""
        if trade.direction == DIRECTION_LONG:
            # 多方开仓，则对应多头的持仓和今仓增加
            if trade.offset == OFFSET_OPEN:
                self.longPosition += trade.volume
                self.longToday += trade.volume
            # 多方平今，对应空头的持仓和今仓减少
            elif trade.offset == OFFSET_CLOSETODAY:
                self.shortPosition -= trade.volume
                self.shortToday -= trade.volume
            # 多方平昨，对应空头的持仓和昨仓减少
            else:
                self.shortPosition -= trade.volume
                self.shortYd -= trade.volume
        else:
            # 空头和多头相同
            if trade.offset == OFFSET_OPEN:
                self.shortPosition += trade.volume
                self.shortToday += trade.volume
            elif trade.offset == OFFSET_CLOSETODAY:
                self.longPosition -= trade.volume
                self.longToday -= trade.volume
            else:
                self.longPosition -= trade.volume
                self.longYd -= trade.volume

            ########################################################################
    #----------------------------------------------------------------------------------
    def drawLine(self,title,df):
          from pyecharts import Line
          line=Line(title)
          dates=df.index
          for name in df.columns:
              line.add(name,dates,df.loc[:,name])
          paramFilename='examples/WebTrader/app/templates/'+title +'.html'
          path=os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))))
          path=os.path.join(path,paramFilename)   
          #删除之前的
          if os.path.exists(path):
                os.remove(path)
          line.render(path)
      
    def drawBar(self,title,df):
          from pyecharts import Bar
          bar=Bar(title)
          dates=df.index
          paramFilename='examples/WebTrader/app/templates/'+title +'.html'
          path=os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))))
          path=os.path.join(path,paramFilename)
          #删除之前的
          if os.path.exists(path):
                os.remove(path)          
          for name in df.columns:
              bar.add(name,dates,df.loc[:,name])
          bar.render(path)
  # ---------------------------------------------------------------------
    def hedgeResult(self,df=None):
            import numpy as np
    
            if df is None:
                df = self.calculateDailyResult()
    
            
    
    
    
            spot=self.strategy.spot
            future=self.strategy.future
            spotvol=self.strategy.Qs
            period=self.strategy.period
            rF=self.strategy.rF
            rS=self.strategy.rS
            hr=self.strategy.hedgeDF
            hr=(hr.reindex(future.index).fillna(method="ffill")).dropna()
            num=self.strategy.num
            num_unit=self.strategy.num_unit
            numDF=pd.concat([num,num_unit],axis=1)
            numDF.columns=["OPT","Unit"]
            numDF=(numDF.reindex(future.index).fillna(method="ffill")).dropna()
            df=df.iloc[(len(df)-len(hr)-2):,:]
            spotposition=spot*spotvol
            self.capital=spotposition[hr.index[0]]
    
            if self.strategy.direction=='LongHedging':
                rHedged=(-rS+hr*rF).dropna()/period
                rUnit=(-rS[hr.index]+rF[hr.index]).dropna()/period
                rUnhedged=-rS[hr.index]/period
    
            elif self.strategy.direction=='ShortHedging':
                rHedged=(rS-hr*rF).dropna()/period
                rUnit=(rS[hr.index]-rF[hr.index]).dropna()/period
                rUnhedged=rS[hr.index]/period
    
            returnDF=pd.concat([rHedged,rUnit,rUnhedged],axis=1)
            returnDF.columns=["OPT","Unit","Unhedged"]
            #--------------准备入库returnDF
            returnDF.to_excel('resultsDF.xlsx')
            #--------------
            nvOPT=rHedged.shift(1).fillna(0).cumsum()+1
            nvUnit=rUnit.shift(1).fillna(0).cumsum()+1
            nvUnhedged=rUnhedged.shift(1).fillna(0).cumsum()+1
            nvDF=pd.concat([nvOPT,nvUnit,nvUnhedged],axis=1)
            nvDF.columns=["OPT","Unit","Unhedged"]
            pnlOPT=rHedged*spotposition.shift(1)[hr.index[0]]
            pnlUnit=rUnit*spotposition.shift(1)[hr.index[0]]
            pnlUnhedged=rUnhedged*spotposition.shift(1)[hr.index[0]]
            pnlDF=pd.concat([pnlOPT,pnlUnit,pnlUnhedged],axis=1)
            pnlDF.columns=["OPT","Unit","Unhedged"]
            positionDF=pnlDF.cumsum()+self.capital
            varDF=pd.DataFrame([],columns=["OPT","Unit","Unhedged"],index=[1,5,10])
            for dd in varDF.index:
                for case in varDF.columns:
                    varDF.loc[dd,case]=np.percentile(pnlDF.loc[:,case].dropna(),5)*np.sqrt(dd)
            marginDF=positionDF[["OPT","Unit"]]*self.marginrate
            self.drawLine("NetValue",nvDF)
            self.drawBar("Var",varDF)
            self.drawBar("ContractVol",numDF)
            self.drawLine("Margin",marginDF)
    
            resultDict={}
            for case in nvDF.columns:
                d={}
                d["FirstTradeDate"]=nvDF.index[0]
                d["LastTradeDate"]=nvDF.index[-1]
                d["ProfitDays"]= len(returnDF[returnDF[case] > 0])
                d["LossDays"]= len(returnDF[returnDF[case] < 0])
                d["AnnualReturn"]=(nvDF.loc[nvDF.index[-1],case]-1)/len(nvDF)*250
                d["AnnualVol"]=(returnDF[case]*period).std()*np.sqrt(250/period)
                resultDict[case]=d
    
            for case in nvDF.columns:
                    resultDict[case]["HedgeEffect"]=round(1-resultDict[case]["AnnualVol"]/resultDict["Unhedged"]["AnnualVol"],4)
        
            HedgeResult=pd.DataFrame(resultDict)
                
            lastdayDict={}
            lastdayDict["LastDate"]=df.index[-1]
            lastdayDict["Position"]=df.iloc[-1,0]
            lastdayDict["LastPrice"]=df.iloc[-1,1]
            lastdayDict["DailyPnL"]=df.iloc[-1,3]
            lastdayDict["SpotPosition"]=round(positionDF["Unhedged"][-1],2)
            lastdayDict["FuturePosition"]=round((positionDF["OPT"]-positionDF["Unhedged"])[-1],2)
            lastdayDict["HedgeRatio"]=round(hr[-1],2)
            lastdayDF=pd.DataFrame(lastdayDict)
            import csv
            HedgeFilename='vnpy/trader/app/ctaStrategy/HedgeResult.csv'
            LastTradeFilename='vnpy/trader/app/ctaStrategy/lastdayDF.csv'
            path=os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))))
            pathHedge=os.path.join(path,HedgeFilename)   
            pathlast = os.path.join(path,LastTradeFilename)   
            HedgeResult.to_csv(pathHedge)
            lastdayDF.to_csv(pathlast)
            # for key in df.columns:
            #     lastdayDict[key]=df[key][-1]
    
            self.drawLine("NetValue",nvDF)
            self.drawBar("Var",varDF)
            self.drawBar("ContractVol",numDF)
            self.drawLine("Margin",marginDF)
            

class TradingResult(object):
    """每笔交易的结果"""

    # ----------------------------------------------------------------------
    def __init__(self, entryPrice, entryDt, exitPrice,
                 exitDt, volume, rate, slippage, size):
        """Constructor"""
        self.entryPrice = entryPrice  # 开仓价格
        self.exitPrice = exitPrice  # 平仓价格

        self.entryDt = entryDt  # 开仓时间datetime
        self.exitDt = exitDt  # 平仓时间

        self.volume = volume  # 交易数量（+/-代表方向）

        self.turnover = (self.entryPrice + self.exitPrice) * size * abs(volume)  # 成交金额
        self.commission = self.turnover * rate  # 手续费成本
        self.slippage = slippage * 2 * size * abs(volume)  # 滑点成本
        self.pnl = ((self.exitPrice - self.entryPrice) * volume * size
                    - self.commission - self.slippage)  # 净盈亏


########################################################################
class OptimizationSetting(object):
    """优化设置"""

    # ----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        self.paramDict = OrderedDict()

        self.optimizeTarget = ''  # 优化目标字段

    # ----------------------------------------------------------------------
    def addParameter(self, name, start, end=None, step=None):
        """增加优化参数"""
        if end is None and step is None:
            self.paramDict[name] = [start]
            return

        if end < start:
            print u'参数起始点必须不大于终止点'
            return

        if step <= 0:
            print u'参数布进必须大于0'
            return

        l = []
        param = start

        while param <= end:
            l.append(param)
            param += step

        self.paramDict[name] = l

    # ----------------------------------------------------------------------
    def generateSetting(self):
        """生成优化参数组合"""
        # 参数名的列表
        nameList = self.paramDict.keys()
        paramList = self.paramDict.values()

        # 使用迭代工具生产参数对组合
        productList = list(product(*paramList))

        # 把参数对组合打包到一个个字典组成的列表中
        settingList = []
        for p in productList:
            d = dict(zip(nameList, p))
            settingList.append(d)

        return settingList

    # ----------------------------------------------------------------------
    def setOptimizeTarget(self, target):
        """设置优化目标字段"""
        self.optimizeTarget = target


# ----------------------------------------------------------------------
def formatNumber(n):
    """格式化数字到字符串"""
    rn = round(n, 2)  # 保留两位小数
    return format(rn, ',')  # 加上千分符


# ----------------------------------------------------------------------
def optimize(strategyClass, setting, targetName,
             mode, startDate, initDays, endDate,
             slippage, rate, size,
             dbName, symbol):
    """多进程优化时跑在每个进程中运行的函数"""
    engine = BacktestingEngine()
    engine.setBacktestingMode(mode)
    engine.setStartDate(startDate, initDays)
    engine.setSlippage(slippage)
    engine.setRate(rate)
    engine.setSize(size)
    engine.setDatabase(dbName, symbol)

    engine.initStrategy(strategyClass, setting)
    engine.runBacktesting()
    d = engine.calculateBacktestingResult()
    try:
        targetValue = d[targetName]
    except KeyError:
        targetValue = 0
    return (str(setting), targetValue)


# ------------------------------------------

########################################################################
class DailyResult(object):
    """每日交易的结果"""
    """改写为合约组合的结果"""
    """需要把之前的数据结构改写为字典"""

    # ----------------------------------------------------------------------
    def __init__(self, symbol, date, closePrice, contract_dict):
        """Constructor"""
        self.date = date  # 日期
        # 多合约收盘价列表
        self.closePrice = {symbol: closePrice}
        # self.closePrice = closePrice    # 当日收盘价
        self.previousClose = {}  # 昨日收盘价

        self.tradeList = []  # 成交列表
        self.tradeListDict = []  # 成交列表记录，回测查看订单详情用
        self.tradeCount = 0  # 成交数量,这里成交数量没有区分合约,为所有总数

        self.openPosition = {}  # 开盘时的持仓
        dictSample = dict(zip(contract_dict[str(date)].keys(), [0] * len(contract_dict[str(date)].keys())))
        self.closePosition = dictSample.copy()  # 收盘时的持仓

        self.tradingPnl = dictSample.copy()  # 交易盈亏
        self.positionPnl = {}  # 持仓盈亏
        self.totalPnl = dictSample.copy()  # 总盈亏

        self.turnover = dictSample.copy()  # 成交量
        self.commission = dictSample.copy()  # 手续费
        self.slippage = dictSample.copy()  # 滑点
        self.netPnl = dictSample.copy()  # 净盈亏
        #####
        self.totalAllPnl = 0  # 多个合约的总pnl
        self.totalCommission = 0  # 多个合约的总commission
        self.totalSlippage = 0  # 多个合约的总slippage
        self.totalTurnover = 0  # 多个合约的总turnover

    # ----------------------------------------------------------------------
    def addTrade(self, trade):
        """添加交易"""
        self.tradeList.append(trade)
        self.tradeListDict.append(trade.__dict__)

    # ----------------------------------------------------------------------
    def calculatePnl(self, symbol, openPosition=0, size=1, rate=0, slippage=0):
        """
        计算盈亏
        size: 合约乘数
        rate：手续费率
        slippage：滑点点数
       """
        # 持仓部分
        #self.openPosition[symbol] = openPosition
        #self.positionPnl[symbol] = self.openPosition[symbol] * (
                    #self.closePrice[symbol] - self.previousClose[symbol]) * size
        #self.closePosition[symbol] = self.openPosition[symbol]
        self.openPosition.update({symbol:openPosition})
        self.positionPnl.update({symbol:self.openPosition[symbol] * (self.closePrice[symbol] - self.previousClose[symbol]) * size})
        self.closePosition.update({symbol:self.openPosition[symbol]})
        # 交易部分
        self.tradeCount = len(self.tradeList)

        for trade in self.tradeList:
            if symbol == trade.vtSymbol:
                if trade.direction == DIRECTION_LONG:
                    posChange = trade.volume
                else:
                    posChange = -trade.volume

    
                self.tradingPnl.update({symbol:self.tradingPnl[symbol] + posChange * (self.closePrice[symbol] - trade.price) * size})
                self.closePosition.update({symbol:self.closePosition[symbol] + posChange})
                self.turnover.update({symbol:self.turnover[symbol] + trade.price * trade.volume * size})
                self.commission.update({symbol:self.commission[symbol] + trade.price * trade.volume * size * rate})
                self.slippage.update({symbol:self.slippage[symbol] + trade.volume * size * slippage})

        # 汇总
        self.totalPnl.update({symbol: self.tradingPnl[symbol] + self.positionPnl[symbol]})
        self.netPnl.update({symbol: self.totalPnl[symbol] - self.commission[symbol] - self.slippage[symbol]})

    #-------------------------------------------------------------
    
if __name__ == '__main__':
    # 以下内容是一段回测脚本的演示，用户可以根据自己的需求修改
    # 建议使用ipython notebook或者spyder来做回测
    # 同样可以在命令模式下进行回测（一行一行输入运行）
    # from statisticAbr import statisticAbr
    #from strategyDemo import strategyDemo
    #from strategyHedge import strategyHedge
    from vnpy.trader.app.ctaStrategy.strategy.strategyHedge import strategyHedge
    queue = Queue()
    # 创建回测引擎
    engine = BacktestingEngine(queue=queue)     

    # 读取策略参数字典，为下一步读取合约做准备
    engine.readParam_Setting()
    # 设置回测日期
    engine.setStartDate('2017-01-01', 0)
    engine.setEndDate('2017-05-30')
    # 设置手续费
    engine.setRate(0.3 / 10000)  # 万0.3
    # 在引擎中创建策略对象
    engine.initStrategy(strategyHedge, {})
    # 读取参数
    symbolList = ['I']
    engine.setDatabase(symbolList)
    # 设置初始仓位
    engine.setInitialPos(0)
    engine.loadDailyHistoryData()
    engine.hedgeResult()

