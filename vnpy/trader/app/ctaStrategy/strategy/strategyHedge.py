# encoding: UTF-8

"""
套保策略
"""

import math
import time
#-------------------------------------------------------------------
from vnpy.trader.vtObject import VtBarData
from vnpy.trader.vtConstant import EMPTY_STRING
from vnpy.trader.app.ctaStrategy.ctaTemplate import (CtaTemplate, 
                                                     BarGenerator, 
                                                     ArrayManager)
from vnpy.trader.vtGateway import VtOrderData
#-------------------------------------------------------------------
from vnpy.trader.app.ctaStrategy.ctaBase import *
from datetime import datetime, timedelta
import datetime
import time
import math
from scipy.integrate import quad
import pandas as pd             #导入pandas模块
import string                   #导入string模块S
import csv
#from Data import Param_setting_dict
from numba import jit
#import ctaBacktesting
import os
import sys
# 临时调用
#from vtConstant import *
import numpy as np
from sklearn.linear_model import LinearRegression
import re
from collections import defaultdict,OrderedDict
import json
########################################################################
class strategyHedge(CtaTemplate):
    """European"""
    className = 'strategyDemo_syt'
    author = u'syt'

    # 策略参数
    takeProfitPoint = 2  #止赢点数
    stopLossPoint = 1   #止损点数
    # 策略变量
    longPosition = 0
    shortPosition = 0
    # 参数列表，保存了参数的名称
    paramList = ['name',
                 'className',
                 'author',
                 'vtSymbol']

    # 变量列表，保存了变量的名称
    varList = ['inited',
               'trading',
               'pos',
               'hedgeratio']
    posAdd = 0
    paramFilename='strategyHedge_Param_Setting.json'
    path=os.path.abspath(os.path.dirname(__file__))
    path1=os.path.join(path,paramFilename)    
    #----------------------------------------------------------------------
    def __init__(self, ctaEngine, setting):
        """Constructor"""
        self.paramSetting()
        super(strategyHedge, self).__init__(ctaEngine, setting)

        # self.contractMode='Double'     #主力合约与次主力合约模式
        self.contractMode='Dominant'  #主力合约模式
        self.num=pd.Series([])
        self.num_unit=pd.Series([])       
        self.lastOrder = None
        self.lastTrade = None

        self.orderType = ''
        self.contractname =  ''
        self.contractnameAdd = ''
        self.initialFlag=True
        self.PositionCodeList=[]
        self.signalGroupList=[]
        self.rollingDays=0
        #开单条件：远-近 价差大于10，开仓
        self.isBuySign = False
        self.isShortSign = False
        self.isBuyCoverSign = False
        self.isShortCoverSign = False

        #记录价格序列
        self.tickListPrice=[]
        self.tickListAddPrice=[]

        self.dayList=[]
        self.dayListPrice=[]
        self.dayDates=[]
        self.spot=pd.Series([])
        self.bg = BarGenerator(self.onDay,1,self.onXminDay)
        self.am = ArrayManager()

        self.future=pd.Series([])
        self.period=10 #套保周期
        self.Qs=10000 #现货数量
        self.direction="LongHedging"
        #self.datastartdate="2015-01-01"
        #self.startdate="2015-03-01"
        #self.enddate="2015-05-01"

        self.contractList = defaultdict(dict)
        self.LongHedging_openSignal= defaultdict(dict)
        self.LongHedging_CloseSignal= defaultdict(dict)
        self.ShortHedging_openSignal= defaultdict(dict)
        self.ShortHedging_CloseSignal= defaultdict(dict)
        self.adjdates=[]
        self.hedgeDF=pd.Series([])
        self.numDF=pd.Series([])
        self.hedgeratio = 0




    #----------------------------------------------------------------------
    def paramSetting(self):
        #策略参数写入名为“strategyHedge_Param_Setting”的文件中
        with open(self.path1) as f:
            param=json.load(f)
            d=self.__dict__
            for key in param:
                d[key]=param[key]
   #----------------------------------------------------------------------               
    def onInit(self):
        """初始化策略（必须由用户继承实现）"""
        if self.initialFlag:
            # 初始化仓位
            self.initialStrategyPos(self.className)
            self.initialFlag=False
            # plt.ion()
            # fig1 = plt.figure()
        self.writeCtaLog(u'商品套期保值策略初始化')

    #----------------------------------------------------------------------
    def onStart(self):
        """启动策略（必须由用户继承实现）"""
        self.isNewDay = True
        self.isRollingClose = True
        #每天检查持仓
        self.PositionCodeList=self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].distinct("vtSymbol")
        self.signalGroupList = self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].distinct("signalGroup")

        if self.adjdates==[]:
            self.dateList(self.period, startdate=self.startdate)
        if len(self.spot)==0:
            self.spot=self.spotDF(self.spotID)
        self.writeCtaLog(u'商品套期保值策略启动')
        self.check_loggerPosition()

        self.putEvent()

    #----------------------------------------------------------------------
    def onStop(self):
        """停止策略（必须由用户继承实现）"""
        self.writeCtaLog(u'追涨Tick演示策略停止')
        self.putEvent()

    #----------------------------------------------------------------------
    def confirmDominant(self,tick):
         # 确定主力合约与次主力合约
        for key, details in self.ctaEngine.contract_dict[tick.date].items():

            if details['property'] == 'DOMINANT':
                self.contractList[details['symbolInit']].update({'DOMINANT':key})
            if details['property'] == 'SUBDOMINANT':
                self.contractList[details['symbolInit']].update({'SUBDOMINANT': key})

    def onTick(self, tick):
        #检查是否还有挂单，并处理,回测与模拟盘检查挂单方式有差异，待解决
        if self.ctaEngine.workingLimitOrderDict.keys():
            self.killOrder(tick,60,3)

        '''推送行情前，先检查最新主力合约，否则isNewDay会错误关闭'''
        if self.isNewDay:  # 每天判断一次
            symbolInit=self.ctaEngine.contract_dict[tick.date][tick.vtSymbol]['symbolInit']
            if self.contractList=={} or self.rollingDays != 0 or self.ctaEngine.rollingFlag:
                self.confirmDominant(tick)
            self.isNewDay = False

        """收到行情TICK推送（必须由用户继承实现）"""
        self.bg.updateTick(tick)

    def beta(self,x,y):
        if len(x)==len(y):
            rho=np.corrcoef(x,y)[0][1]
            hedgeratio=np.std(y)*rho/np.std(x)
        else:
            print(u"自变量与因变量序列长度不匹配")
            exit()
        return hedgeratio

    def linear(self,x,y):
        model=LinearRegression()

        try:
            model.fit(x,y)
        except:
            # model.fit(x.values.reshape(-1,1),y)
            X=[]
            Y=[]
            for xx,yy in zip(x.values,y.values):
                X.append([float(xx)])
                Y.append([float(yy)])
            model.fit(X,Y)
        hedgeratio=model.coef_[0]
        return hedgeratio

    def spotDF(self,ID):  #ID是现货指标的wind代码，字符串格式
        commodity=self.symbol
        spotcollection=self.ctaEngine.dbClient["SPOT_DB"][commodity]
        ID = str(ID)
        datelist = sorted(self.ctaEngine.contract_dict.keys())
        datadf=pd.DataFrame(list(spotcollection.find({"ID":ID,"Date":{"$gte":datelist[0]}})))
        spotdf=datadf["Price"]
        #spotdf.index=datadf["Date"]
        #spotdf=spotdf.sort_index()
        spotdf=spotdf[0:len(datelist)]
        spotdf.index=datelist 
        return spotdf

    def dateList(self,period,initdelta=None,startdate=None,fixdate=10):
        if period % 20 != 0:
            fixdate = None
        datelist = sorted(self.ctaEngine.contract_dict.keys())
        if startdate in datelist:
            dateList = datelist[datelist.index(startdate):]
        else:
            while startdate not in datelist:
                startdate = (datetime.datetime.strptime(startdate, "%Y-%m-%d") + datetime.timedelta(days=1)).strftime(
                    "%Y-%m-%d")
            dateList = datelist[datelist.index(startdate):]
        if (datetime.datetime.strptime(startdate, "%Y-%m-%d") - datetime.datetime.strptime(datelist[0],
                                                                                           "%Y-%m-%d")).days > period + 10:
            adj = []
            testDf =  pd.DataFrame([])
            if fixdate:
                #dateDF = pd.DataFrame([], index=dateList, columns=[["Year", "Month", "Day"]])
                for date in dateList:
                    #dateDF.loc[date, "Year"] = date.split("-")[0]
                    testDf.ix[date,'Year'] = date.split("-")[0]
                    testDf.ix[date,'Month'] = date.split("-")[1]
                    testDf.ix[date,'Day'] = date.split("-")[2]
                for name, group in testDf.groupby(["Year", "Month"]):
                    if fixdate > len(group):
                        fixdate = len(group)
                    adj.append(group.index[fixdate - 1])
                adjdates = adj[0::int(period / 20)]
                self.adjdates = adjdates[1:]
            else:
                self.adjdates = dateList[0::period]
        else:
            print(u"回测时间太短，请重新设置startdate")
            exit()


    #----------------------------------------------------------------------
    def onBar(self, bar):
        """收到Bar推送（必须由用户继承实现）"""
        self.bg.updateBar(bar)
    #----------------------------------------------------------------------
    def onDay(self, bar):
        """收到Bar推送（必须由用户继承实现）"""
        self.bg.updateDay(bar)

    #----------------------------------------------------------------------
    def onXminDay(self, bar):
        """收到Tick推送（必须由用户继承实现）"""
        symbolInit = re.findall("[A-Za-z]+", bar.vtSymbol)[0].upper()
        if self.isRollingClose:
             # 检查是否有换月，编写处理逻辑，全平或设定相关条件或移仓
            for code in self.ctaEngine.rollingContract:
                # 找出涉及换月的合约
                dbCusor = self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].find({'vtSymbol': code})

                for contract in dbCusor:
                    # 找出涉及换月的singalGroup所有合约
                    dbCusor2 = self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].find(
                        {'signalGroup': contract['signalGroup']})
                    if contract['signalGroup'].split('_')[0] == 'LongHedging':
                        self.LongHedging_openSignal.update({symbolInit: True})
                    elif contract['signalGroup'].split('_')[0] == 'ShortHedging':
                        self.ShortHedging_openSignal.update({symbolInit: True})
                    for d in dbCusor2:
                        self.oneKeyClean_Bar(bar, d, contract['signalGroup'])


                    # 关闭信号
                    if contract['signalGroup'].split('_')[0] == 'LongHedging':
                        self.LongHedging_openSignal.update({contract['signalGroup'].split('_')[1]: True})
                    if contract['signalGroup'].split('_')[0] == 'ShortHedging':
                        self.ShortHedging_openSignal.update({contract['signalGroup'].split('_')[1]: True})
            self.isRollingClose=False

        DominantCode=self.contractList[symbolInit]['DOMINANT']

        self.future[bar.date]=bar.close
        # self.adjdates=self.dateList(self.period,startdate=self.startdate)



        if bar.date in self.adjdates[0:]:
            self.rF=(np.log(self.future).diff(self.period)).dropna()
            self.rS=(np.log(self.spot[self.future.index]).diff(self.period)).dropna()
            hedgeratio=self.beta(self.rF,self.rS)
            self.hedgeDF[bar.date]=hedgeratio
            mult=self.ctaEngine.contract_dict[bar.date][bar.vtSymbol]["size"]
            self.n=int((hedgeratio*self.Qs*self.spot[bar.date])/(mult*self.future[bar.date]))
            self.n_unit=int((self.Qs*self.spot[bar.date])/(mult*self.future[bar.date]))
            self.num[bar.date]=self.n
            self.num_unit[bar.date]=self.n_unit
            
            if self.direction=="LongHedging":
                self.LongHedging_openSignal.update({symbolInit: True})
                #如果旧持仓信号则平仓开启
                if self.direction+'_'+symbolInit in self.signalGroupList:
                    self.LongHedging_CloseSignal.update({symbolInit: True})

            if self.direction=="ShortHedging":
                self.ShortHedging_openSignal.update({symbolInit: True})
                # 如果旧持仓信号则平仓开启
                if self.direction+'_'+symbolInit in self.signalGroupList:
                    self.ShortHedging_CloseSignal.update({symbolInit: True})

        # self.hedgeDF = (self.hedgeDF.reindex(self.rF.index).fillna(method="ffill")).dropna()
        # if bar.date in adjdates[0:]:
        #     if self.direction=="LongHedging" not in self.signalGroupList:
        #         self.LongHedging_openSignal.update({symbolInit: True})
        #     if self.direction=="ShortHedging" not in self.signalGroupList:
        #         self.ShortHedging_openSignal.update({symbolInit: True})

        MinimumPriceChange = self.ctaEngine.Param_setting_dict[symbolInit]['MinimumPriceChange'] #最小跳价
        if self.LongHedging_CloseSignal[symbolInit] == True:
            # 买入套保平仓
            # 净头寸调仓待优化
            self.signalName = 'LongHedging_%s' % symbolInit
            dbCusorOrder = self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].find(
                {'signalGroup': self.signalName})
            for d in dbCusorOrder:
                self.oneKeyClean_Bar(bar, d, self.signalName, info='套期保值到期平仓')
            self.LongHedging_CloseSignal.update({symbolInit: False})

        if self.ShortHedging_CloseSignal[symbolInit] == True:
            # 卖出套保平仓
            # 待优化同步平仓
            self.signalName = 'ShortHedging_%s' % symbolInit
            dbCusorOrder = self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].find(
                {'signalGroup': self.signalName})
            for d in dbCusorOrder:
                self.oneKeyClean_Bar(bar, d, self.signalName, info='套期保值到期平仓')

            self.ShortHedging_CloseSignal.update({symbolInit: False})



        #买入套保开仓
        if self.LongHedging_openSignal[symbolInit]== True:
            self.signalName = 'LongHedging_%s' % symbolInit
            self.ctaEngine.sendOrder(DominantCode, CTAORDER_BUY, bar.close + MinimumPriceChange, self.n, self)
            self.writeCtaLog(
                u'信号' + self.signalName + ': '+ u'下单时间:'+str(self.ctaEngine.dt)+ u' 合约 ' + DominantCode + u' 买入套保开仓 ' + str(
                    self.n) + u' 手 '+' u价格: '+ str(bar.close + MinimumPriceChange))
            self.LongHedging_openSignal.update({symbolInit:False})

        # 卖出套保开仓
        if self.ShortHedging_openSignal[symbolInit]== True:
            self.signalName = 'ShortHedging_%s' % symbolInit
            self.ctaEngine.sendOrder(DominantCode, CTAORDER_SHORT, bar.close - MinimumPriceChange, self.n,self)
            self.writeCtaLog(
                '信号' + self.signalName + ': '+ '下单时间:'+str(self.ctaEngine.dt)+ ' 合约 ' + DominantCode + ' 卖出套保开仓 ' + str(
                    self.n) + ' 手 '+' 价格: '+ str(bar.close + MinimumPriceChange))
            self.ShortHedging_openSignal.update({symbolInit:False})


    #----------------------------------------------------------------------
    def onOrder(self, order):
        """收到委托变化推送（必须由用户继承实现）"""
        # 对于无需做细粒度委托控制的策略，可以忽略onOrder
        self.lastOrder = order
        self.writeCtaLog(
            self.ctaEngine.orderStrategyDict[order.orderID][self.className] + '委托订单成交' + ': '
            + '下单时间:'+ str(order.orderTime)
            + ' 合约 ' + order.vtSymbol + ' ' + order.direction + ' ' + order.offset + str(order.totalVolume)
            + ' 手 ' + ' 委托订单状态: '+ order.status)

        # print self.ctaEngine.orderStrategyDict[order.orderID][self.className],order.vtSymbol, order.direction, order.offset, order.totalVolume, '手', order.status

        #更新持仓列表,没有考虑是否成交
        self.PositionCodeList = self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].distinct("vtSymbol")
        self.signalGroupList = self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].distinct("signalGroup")

        self.check_loggerPosition()

    def check_loggerPosition(self):
        dbCursor=self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].aggregate(
            [{'$group': {'_id': '$vtSymbol', 'shortTd': {'$sum': '$shortTd'}, 'longTd': {'$sum': '$longTd'},
                            'longPosTarget': {'$sum': '$longPosTarget'}, 'shortPosTarget': {'$sum': '$shortPosTarget'}}}])
        for d in dbCursor:
            self.writeCtaLog(
                '持仓：' + ' 合约 ' + d['_id'] + ' 多头目标持仓 ' + str(d['longPosTarget']) + ' 多头可用持仓： ' + str(d['longTd'])
                +' 空头目标持仓 ' + str(d['shortPosTarget']) + ' 空头可用持仓： ' + str(d['shortTd']))

        self.writeCtaLog('持有信号：' + str(self.signalGroupList)[1:-1])

    #----------------------------------------------------------------------
    def onTrade(self, trade):
        """收到成交推送（必须由用户继承实现）"""
        self.lastTrade = trade
        order=self.ctaEngine.workingLimitOrderDict[str(trade.orderID)]
        # 对于无需做细粒度委托控制的策略，可以忽略onTrade
        self.writeCtaLog(
            self.ctaEngine.orderStrategyDict[trade.orderID][self.className] + '成交' + ': '
            + '成交时间:'+ str(trade.tradeTime)
            + ' 合约 ' + trade.vtSymbol + ' ' + order.direction + ' ' + order.offset + str(trade.volume)
            + ' 手 ' + ' 价格: ' + str(trade.price))
        signalName=self.ctaEngine.orderStrategyDict[order.orderID][self.className]
        self.updateTradedPos(trade,signalName,order.status)
        #清空0持仓数据库文档
        self.cleanDataBasePos(order,signalName)

    def oneKeyClean(self,tick,d,signalName):
        if tick.vtSymbol == d['vtSymbol']:
            shortPos = d['shortTd'] + d['shortYd']
            longPos = d['longTd'] + d['longYd']
            signalList = []
            self.signalName = d['signalGroup']

            if longPos < shortPos:
                signalList.extend(self.ctaEngine.sendOrder(d['vtSymbol'], CTAORDER_COVER, tick.askPrice1 + 10,
                                                           shortPos,self))  # 下单并返回orderID
                # self.updatePosTarget(signalList, d['signalGroup'])
                # self.sType = 0
                print    u'换月强平',tick.datetime, signalName, u'买入平仓', d['vtSymbol'], shortPos, u'手'
            else:
                signalList.extend(self.ctaEngine.sendOrder(d['vtSymbol'], CTAORDER_SELL, tick.bidPrice1 - 10, longPos,self))
                # self.updatePosTarget(signalList, d['signalGroup'])
                # self.bType = 0
                print   u'换月强平', tick.datetime, signalName, u'卖出平仓', d['vtSymbol'], longPos, u'手'

    def oneKeyClean_Bar(self, bar, d, signalName,info='换月强平 '):
        shortPos = d['shortTd'] + d['shortYd']
        longPos = d['longTd'] + d['longYd']
        self.signalName=d['signalGroup']

        if longPos < shortPos:
            self.ctaEngine.sendOrder(d['vtSymbol'], CTAORDER_COVER, self.bg.lastTick[d['vtSymbol']].askPrice1,
                                                       shortPos,self)# 下单并返回orderID
            self.writeCtaLog(
                '信号' + signalName + ':' + str(bar.datetime)+ info  + ' 合约 ' + d['vtSymbol'] + ' 买入平仓 ' + str(
                    shortPos) + ' 手')
            # print   u'换月强平',bar.datetime, signalName, u'买入平仓', d['vtSymbol'], shortPos, u'手'
        else:
           try: 
               self.ctaEngine.sendOrder(d['vtSymbol'], CTAORDER_SELL, self.bg.lastTick[d['vtSymbol']].bidPrice1, longPos,self)
               self.writeCtaLog(
                '信号' + signalName + ':' + str(bar.datetime)+ info  + ' 合约 ' + d['vtSymbol'] + ' 卖出平仓 ' + str(
                    longPos) + ' 手')
           except:
               self.writeCtaLog(u'error: ' )           



    #----------------------------------------------------------------------
    def fixedTakeProfit(self):
        """固定止赢处理,以股指示例，2个点止赢"""
        if self.bType == 1 and self.pos > 0:
            if self.tickList[3].askPrice1 - self.lastOrder.price > self.takeProfitPoint: #如果多单赢利大于2个点
                self.sell(self.tickList[3].bidPrice1, 1)
                self.bType = 0
                self.writeCtaLog(u'多单固定止盈,--平仓价：' + str(self.tickList[3].bidPrice1) + u'--赢利点数：' + str(self.tickList[3].bidPrice1-self.lastOrder.price))
        elif self.sType == 1 and self.pos < 0:
            if self.lastOrder.price - self.tickList[3].askPrice1 > self.takeProfitPoint: #如果空单赢利大于2个点
                self.cover(self.tickList[3].askPrice1, 1)
                self.sType = 0
                self.writeCtaLog(u'空单固定止盈,--平仓价：' + str(self.tickList[3].askPrice1) + u'--赢利点数：' + str(self.lastOrder.price-self.tickList[3].askPrice1) )

    #----------------------------------------------------------------------
    def fixedStopLoss(self):
        """固定止损处理,以股指示例，1个点止损"""
        if self.bType == 1 and self.pos > 0:
            if  self.lastTrade.price - self.tickList[3].lastPrice > self.stopLossPoint: #如果多单亏损大于1个点
                self.sell(self.tickList[3].bidPrice1, 1)
                self.bType = 0
                self.writeCtaLog(u'多单固定止损,--平仓价：' + str(self.tickList[3].bidPrice1) + u'--亏损点数：' + str(self.tickList[3].bidPrice1-self.lastTrade.price))
        elif self.sType == 1 and self.pos < 0:
            if self.tickList[3].lastPrice - self.lastTrade.price > self.stopLossPoint: #如果空单亏损大于1个点
                self.cover(self.tickList[3].askPrice1, 1)
                self.sType = 0
                self.writeCtaLog(u'空单固定止损,--平仓价：' + str(self.tickList[3].askPrice1) + u'--亏损点数：' + str(self.lastTrade.price-self.tickList[3].askPrice1) )
    #----------------------------------------------------------------------
    def calculateDailyResult(self):
        self.hedgeDF=(self.hedgeDF.reindex(self.rF.index).fillna(method="ffill")).dropna()
        if self.direction=='买入套保':
            rHedged=(-self.rS+self.hedgeDF*self.rF).dropna()
            rUnit=(-self.rS[self.hedgeDF.index]+self.rF[self.hedgeDF.index]).dropna()
            rUnhedged=-self.rS[self.hedgeDF.index]

        elif self.direction=='卖出套保':
            rHedged=(self.rS-self.hedgeDF*self.rF).dropna()
            rUnit=(self.rS[self.hedgeDF.index]-self.rF[self.hedgeDF.index]).dropna()
            rUnhedged=self.rS[self.hedgeDF]

        nvHedged=rHedged.shift(1).fillna(0).cumsum()+1
        nvUnit=rUnit.shift(1).fillna(0).cumsum()+1
        nvUnhedged=rUnhedged.shift(1).fillna(0).cumsum()+1

        line=Line("套保方案净值图")
        line.add("最优套保",nvHedged.index,nvHedged.values)
        line.add("传统套保",nvUnit.index,nvUnit.values)
        line.add("未套保",nvUnhedged.index,nvUnhedged.values)
        # line.show_config()
        line.render()

