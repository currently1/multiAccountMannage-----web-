# encoding: UTF-8

"""
高频交易跨品种套利策略
"""
from __future__ import division
import math
import time


from vnpy.trader.vtObject import VtBarData
from vnpy.trader.vtConstant import EMPTY_STRING
from vnpy.trader.app.ctaStrategy.ctaTemplate import (CtaTemplate, 
                                                     BarGenerator, 
                                                     ArrayManager)

from vnpy.trader.app.ctaStrategy.ctaBase import *
from datetime import datetime, timedelta
import datetime
import time
import math
from scipy.integrate import quad
from vnpy.trader.vtGateway import VtOrderData
import pandas as pd             #导入pandas模块
import string                   #导入string模块S
import csv
#from .Data import Param_setting_dict
from numba import jit

# 临时调用
from vnpy.trader.vtConstant import *
import numpy as np

########################################################################
class strategyDemo(CtaTemplate):
    """European"""
    className = 'strategyDemo'
    author = u'zjh'

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
               'pos']
    posAdd = 0

    #----------------------------------------------------------------------
    def __init__(self, ctaEngine, setting):
        """Constructor"""
        super(strategyDemo, self).__init__(ctaEngine, setting)

        self.contractMode='Double'     #主力合约与次主力合约模式
        # self.contractMode='Dominant'  #主力合约模式

        self.lastOrder = None
        self.lastTrade = None
        self.tickList = [] #初始一个tick列表
        self.tickListAdd = []#初始第二个tick列表
        self.bType = 0 #买的状态，1表示买开委托状态，0表示非买开委托状态.目的是判断当前委托的状态，不要发生重复发单的事情
        self.sType = 0 #买的状态，1表示卖开委托状态，0表示非卖开委托状态
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

        self.bg = BarGenerator(self.onBar, 5, self.onXminBar)
        self.am = ArrayManager()




    #----------------------------------------------------------------------
    def onInit(self):
        """初始化策略（必须由用户继承实现）"""
        if self.initialFlag:
            # 初始化仓位
            self.initialStrategyPos(self.className)
            self.initialFlag=False
        #每天检查持仓
        self.PositionCodeList=self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].distinct("vtSymbol")
        self.signalGroupList = self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].distinct("signalGroup")


        self.writeCtaLog(u'追涨Tick演示策略初始化')

    #----------------------------------------------------------------------
    def onStart(self):
        """启动策略（必须由用户继承实现）"""
        self.isNewDay=True

        self.writeCtaLog(u'追涨Tick演示策略启动')
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
                contractname = key
            if details['property'] == 'SUBDOMINANT':
                contractnameAdd = key
        return contractname, contractnameAdd

    def onTick(self, tick):
        """收到行情TICK推送（必须由用户继承实现）"""
        self.bg.updateTick(tick)

        if self.isNewDay:  # 每天判断一次
            self.isNewDay = False
            if self.contractname == '' or self.rollingDays != 0 or self.ctaEngine.rollingFlag:
                self.contractname, self.contractnameAdd = self.confirmDominant(tick)


    def onTick_only(self,tick):
        # print u"收到tick%s" , tick.symbol

        # try:
        #     #print "updateShortPosA"
        #     #print  self.ctaEngine.posBufferDict[self.contractname].shortPosition
        #     self.shortPosition = self.ctaEngine.posBufferDict[self.contractname].shortPosition
        #
        # except Exception, e:
        #     print Exception, ":", e
        #
        # try:
        #     #print "updatelongPosA"
        #     #print  self.ctaEngine.posBufferDict[self.contractname].longPosition
        #     self.longPosition = self.ctaEngine.posBufferDict[self.contractname].longPosition
        #
        #
        # except Exception, e:
        #     print Exception, ":", e
        #
        # self.pos = self.longPosition -self.shortPosition
        #
        # try:
        #     #print "updateShortPosB"
        #     #print  self.ctaEngine.posBufferDict[self.contractnameAdd].shortPosition
        #     self.shortPosition = self.ctaEngine.posBufferDict[self.contractnameAdd].shortPosition
        #
        # except Exception, e:
        #     print Exception, ":", e
        #
        # try:
        #     #print "updatelongPosB"
        #     #print  self.ctaEngine.posBufferDict[self.contractnameAdd].longPosition
        #     self.longPosition = self.ctaEngine.posBufferDict[self.contractnameAdd].longPosition
        #
        #
        # except Exception, e:
        #     print Exception, ":", e
        #
        # self.posAdd = self.longPosition -self.shortPosition

        # 换月的时候，第一天清零tickList，tickListAdd
        if self.ctaEngine.rollingContract:
            self.rollingDays += 1
            if self.rollingDays == 1:  # 换月当天，tickList请0
                self.tickList = []
                self.tickListAdd = []
                self.tickListAddPrice = []
                self.tickListPrice = []
        else:
            self.rollingDays = 0

        # 检查是否有换月，编写处理逻辑，全平或设定相关条件或移仓
        for code in self.ctaEngine.rollingContract:
            # 找出涉及换月的合约
            dbCusor = self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].find({'vtSymbol': code})
            for contract in dbCusor:
                # 找出涉及换月的singalGroup所有合约
                dbCusor2 = self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].find(
                    {'signalGroup': contract['signalGroup']})
                for d in dbCusor2:
                    self.oneKeyClean(tick, d, contract['signalGroup'])

        if self.isNewDay:  # 每天判断一次
            self.isNewDay = False
            if self.contractname == '' or self.rollingDays != 0 or self.ctaEngine.rollingFlag:
                self.contractname, self.contractnameAdd = self.confirmDominant(tick)

        days = 1000
        if tick.symbol == self.contractname:
            # 当新tick来的时候进行数据保存，保存4个tick的数据，
            self.tickList.append(tick)
            self.tickListPrice.append(tick.lastPrice)
            # 往列表后面增加新tick数据
            if len(self.tickList) > days:  # 如果数据长度大于4，则要进行删除动作
                del self.tickList[0]  # 老数据从列表头部删掉
                del self.tickListPrice[0]

        if tick.symbol == self.contractnameAdd:
            self.tickListAdd.append(tick)
            self.tickListAddPrice.append(tick.lastPrice)
            if len(self.tickListAdd) > days:  # 如果数据长度大于4，则要进行删除动作
                del self.tickListAdd[0]  # 老数据从列表头部删掉
                del self.tickListAddPrice[0]

        if len(self.tickList) < days or len(self.tickListAdd) < days:
            return

        # 过去60TICKS价差均值与标准差

        # meanGap=np.mean([x.bidPrice1 - y.askPrice1 for x, y in zip(self.tickList[:-1], self.tickListAdd[:-1])])
        # stdGap=np.std([x.bidPrice1 - y.askPrice1 for x, y in zip(self.tickList[:-1], self.tickListAdd[:-1])])
        meanGap = (np.array(self.tickListPrice) - np.array(self.tickListAddPrice)).mean()
        stdGap = (np.array(self.tickListPrice) - np.array(self.tickListAddPrice)).std()

        if (self.tickList[-1].bidPrice1 - self.tickListAdd[-1].askPrice1) > (
                meanGap + stdGap) and u'反向套利' not in self.signalGroupList:
            self.isShortSign = True  # 反向套利

        if (self.tickList[-1].askPrice1 - self.tickListAdd[-1].bidPrice1) < (
                meanGap - stdGap) and u'正向套利' not in self.signalGroupList:
            self.isBuySign = True  # 正向套利

        # 反向套利平仓
        if (self.tickList[-1].askPrice1 - self.tickListAdd[-1].bidPrice1) < (
        meanGap) and u'反向套利' in self.signalGroupList:
            self.isBuyCoverSign = True  # 平仓

        # 正向套利平仓
        if (self.tickListAdd[-1].bidPrice1 - self.tickList[-1].askPrice1) > (
        meanGap) and u'正向套利' in self.signalGroupList:
            self.isShortCoverSign = True  # 平仓

        # 正向套利
        if self.isBuySign:
            # 如果买开时手头没有持仓，则直接对价做多
            # if self.bType == 0 and self.sType == 0 and self.posAdd == 0 and self.pos == 0:
            # if self.bType == 0 and self.sType == 0:
            signalList = []
            self.signalName = u'正向套利'
            signalList.extend(
                self.ctaEngine.sendOrder(self.contractname, CTAORDER_BUY, self.tickList[-1].askPrice1 + 10, 1,self))
            print  tick.datetime, signalName, u'买入开仓', self.contractname, 1, u'手'
            # self.bType = 1
            signalList.extend(
                self.ctaEngine.sendOrder(self.contractnameAdd, CTAORDER_SHORT, self.tickListAdd[-1].bidPrice1 - 10, 1,self))
            print tick.datetime, signalName, u'卖出开仓', self.contractnameAdd, 1, u'手'
            # self.sType = 1
            # self.writeCtaLog(u'近月买开价：' + str(self.tickList[-1].askPrice1 + 10) + u'远月卖开价：' + str(
            #     self.tickListAdd[-1].bidPrice1 - 10))

            # self.updatePosTarget(signalList, signalName)
            self.isBuySign = False

        # 反向套利
        if self.isShortSign:
            # if self.bType == 0 and self.sType == 0 and self.posAdd == 0 and self.pos == 0:
            # if self.bType == 0 and self.sType == 0:
            signalList = []
            self.signalName = u'反向套利'
            signalList.extend(
                self.ctaEngine.sendOrder(self.contractname, CTAORDER_SHORT, self.tickList[-1].bidPrice1 - 10, 1,self))
            print  tick.datetime, signalName, u'卖出开仓', self.contractname, 1, u'手'
            self.sType = 1
            signalList.extend(
                self.ctaEngine.sendOrder(self.contractnameAdd, CTAORDER_BUY, self.tickListAdd[-1].askPrice1 + 10, 1,self))
            print   tick.datetime, signalName, u'买入开仓', self.contractnameAdd, 1, u'手'
            # self.bType = 1
            # self.writeCtaLog(u'近月卖开价：' + str(self.tickList[-1].bidPrice1 - 10) + u'远月买开价：' + str(
            #     self.tickListAdd[-1].askPrice1 + 10))
            #
            # self.updatePosTarget(signalList, signalName)
            self.isShortSign = False
            # collection.update({'longPnl': 0}, testDict.__dict__, upsert=True)

        if self.isBuyCoverSign:
            # 反向套利平仓

            # 待优化同步平仓
            self.signalName = u'反向套利'
            # 找出涉及换月的singalGroup所有合约
            dbCusor = self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].find({'signalGroup': signalName})
            if dbCusor.count() == 0:
                self.isBuyCoverSign = False
                return
            for d in dbCusor:
                self.oneKeyClean(tick, d, signalName)

        if self.isShortCoverSign:
            # 正向套利平仓

            # 待优化同步平仓
            self.signalName = u'正向套利'
            # 找出涉及换月的singalGroup所有合约
            dbCusor = self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].find({'signalGroup': signalName})

            if dbCusor.count() == 0:
                self.isShortCoverSign = False
                return
            for d in dbCusor:
                self.oneKeyClean(tick, d, signalName)


    def onXminBar(self, bar):

        # print u"收到tick%s" , tick.symbol

        # try:
        #     #print "updateShortPosA"
        #     #print  self.ctaEngine.posBufferDict[self.contractname].shortPosition
        #     self.shortPosition = self.ctaEngine.posBufferDict[self.contractname].shortPosition
        #
        # except Exception, e:
        #     print Exception, ":", e
        #
        # try:
        #     #print "updatelongPosA"
        #     #print  self.ctaEngine.posBufferDict[self.contractname].longPosition
        #     self.longPosition = self.ctaEngine.posBufferDict[self.contractname].longPosition
        #
        #
        # except Exception, e:
        #     print Exception, ":", e
        #
        # self.pos = self.longPosition -self.shortPosition
        #
        # try:
        #     #print "updateShortPosB"
        #     #print  self.ctaEngine.posBufferDict[self.contractnameAdd].shortPosition
        #     self.shortPosition = self.ctaEngine.posBufferDict[self.contractnameAdd].shortPosition
        #
        # except Exception, e:
        #     print Exception, ":", e
        #
        # try:
        #     #print "updatelongPosB"
        #     #print  self.ctaEngine.posBufferDict[self.contractnameAdd].longPosition
        #     self.longPosition = self.ctaEngine.posBufferDict[self.contractnameAdd].longPosition
        #
        #
        # except Exception, e:
        #     print Exception, ":", e
        #
        # self.posAdd = self.longPosition -self.shortPosition


        #换月的时候，第一天清零tickList，tickListAdd
        if self.ctaEngine.rollingContract:
            self.rollingDays += 1
            if self.rollingDays == 1:  #换月当天，tickList请0
                self.tickList=[]
                self.tickListAdd=[]
                self.tickListAddPrice=[]
                self.tickListPrice=[]
        else:
            self.rollingDays=0

        # 检查是否有换月，编写处理逻辑，全平或设定相关条件或移仓
        for code in self.ctaEngine.rollingContract:
            #找出涉及换月的合约
            dbCusor = self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].find({'vtSymbol': code})
            for contract in dbCusor:
                #找出涉及换月的singalGroup所有合约
                dbCusor2 = self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].find({'signalGroup': contract['signalGroup']})
                for d in dbCusor2:
                    self.oneKeyClean_Bar(bar, d, contract['signalGroup'])





        days=5
        if bar.symbol == self.contractname :
          #当新tick来的时候进行数据保存，保存4个tick的数据，
            self.tickList.append(bar)
            self.tickListPrice.append(bar.close)
          #往列表后面增加新tick数据
            if len(self.tickList) > days:   #如果数据长度大于4，则要进行删除动作
                del self.tickList[0]     #老数据从列表头部删掉
                del self.tickListPrice[0]

        if  bar.symbol == self.contractnameAdd :
            self.tickListAdd.append(bar)
            self.tickListAddPrice.append(bar.close)
            if len(self.tickListAdd) > days:   #如果数据长度大于4，则要进行删除动作
                del self.tickListAdd[0]     #老数据从列表头部删掉
                del self.tickListAddPrice[0]





        if len(self.tickList)<days or len(self.tickListAdd) <days :
            return


        # 过去60TICKS价差均值与标准差

        # meanGap=np.mean([x.bidPrice1 - y.askPrice1 for x, y in zip(self.tickList[:-1], self.tickListAdd[:-1])])
        # stdGap=np.std([x.bidPrice1 - y.askPrice1 for x, y in zip(self.tickList[:-1], self.tickListAdd[:-1])])
        meanGap=(np.array(self.tickListPrice)-np.array(self.tickListAddPrice)).mean()
        stdGap=(np.array(self.tickListPrice)-np.array(self.tickListAddPrice)).std()



        if (self.tickList[-1].close - self.tickListAdd[-1].close) > (meanGap +stdGap) and '反向套利' not in self.signalGroupList:
            self.isShortSign = True  # 反向套利

        if (self.tickList[-1].close - self.tickListAdd[-1].close) < (meanGap - stdGap)and '正向套利' not in self.signalGroupList:
            self.isBuySign = True  # 正向套利

        #反向套利平仓
        if (self.tickList[-1].close - self.tickListAdd[-1].close)< (meanGap) and '反向套利' in self.signalGroupList:
            self.isBuyCoverSign = True   # 平仓

        #正向套利平仓
        if (self.tickListAdd[-1].close - self.tickList[-1].close) > (meanGap) and  '正向套利' in self.signalGroupList:
            self.isShortCoverSign = True   # 平仓


            
        #正向套利
        if self.isBuySign:
            # 如果买开时手头没有持仓，则直接对价做多
            # if self.bType == 0 and self.sType == 0 and self.posAdd == 0 and self.pos == 0:
            # if self.bType == 0 and self.sType == 0:
            signalList=[]
            self.signalName='正向套利'
            signalList.extend(self.ctaEngine.sendOrder(self.contractname,CTAORDER_BUY, self.tickList[-1].close+10, 1,self))
            print  bar.datetime,self.signalName,u'买入开仓', self.contractname, 1, u'手'
            # self.bType = 1
            signalList.extend(self.ctaEngine.sendOrder(self.contractnameAdd,CTAORDER_SHORT, self.tickListAdd[-1].close-10, 1,self))
            print bar.datetime,self.signalName,u'卖出开仓', self.contractnameAdd, 1, u'手'
            # self.sType = 1
            self.writeCtaLog(u'近月买开价：'+str(self.tickList[-1].close+10) + u'远月卖开价：'+ str(self.tickListAdd[-1].close-10))

            # self.updatePosTarget(signalList, signalName)
            self.isBuySign = False



        # 反向套利
        if self.isShortSign:
            # if self.bType == 0 and self.sType == 0 and self.posAdd == 0 and self.pos == 0:
            # if self.bType == 0 and self.sType == 0:
            signalList=[]
            self.signalName='反向套利'
            signalList.extend(self.ctaEngine.sendOrder(self.contractname,CTAORDER_SHORT, self.tickList[-1].close-10, 1,self))
            print  bar.datetime,self.signalName,u'卖出开仓', self.contractname, 1, u'手'
            self.sType = 1
            signalList.extend(self.ctaEngine.sendOrder(self.contractnameAdd,CTAORDER_BUY, self.tickListAdd[-1].close+10, 1,self))
            print   bar.datetime,self.signalName,u'买入开仓', self.contractnameAdd, 1, u'手'
            self.bType = 1
            self.writeCtaLog(u'近月卖开价：'+str( self.tickList[-1].close-10) + u'远月买开价：'+ str(self.tickListAdd[-1].close+10))

            # self.updatePosTarget(signalList, signalName)
            self.isShortSign=False
                # collection.update({'longPnl': 0}, testDict.__dict__, upsert=True)


        if self.isBuyCoverSign:
            # 反向套利平仓

            #待优化同步平仓
            self.signalName = '反向套利'
            #找出涉及换月的singalGroup所有合约
            dbCusor = self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].find({'signalGroup': self.signalName})
            if dbCusor.count()==0:
                self.isBuyCoverSign=False
                return
            for d in dbCusor:
                self.oneKeyClean_Bar(bar, d, self.signalName)



        if self.isShortCoverSign:
            # 正向套利平仓

            # 待优化同步平仓
            self.signalName = '正向套利'
            #找出涉及换月的singalGroup所有合约
            dbCusor = self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].find({'signalGroup': self.signalName})

            if dbCusor.count()==0:
                self.isShortCoverSign=False
                return
            for d in dbCusor:
                self.oneKeyClean_Bar(bar, d, self.signalName)


            
        # # CTA委托类型映射
        # if self.lastOrder != None and self.lastOrder.direction == u'多' and self.lastOrder.offset == u'开仓':
        #     self.orderType = u'买开'
        #
        # elif self.lastOrder != None and self.lastOrder.direction == u'多' and self.lastOrder.offset == u'平仓':
        #     self.orderType = u'买平'
        #
        # elif self.lastOrder != None and self.lastOrder.direction == u'空' and self.lastOrder.offset == u'开仓':
        #     self.orderType = u'卖开'
        #
        # elif self.lastOrder != None and self.lastOrder.direction == u'空' and self.lastOrder.offset == u'平仓':
        #     self.orderType = u'卖平'
        #
        # # 不成交，即撤单，并追单
        # if (self.lastOrder != None and self.lastOrder.status == u'未成交') or (self.lastOrder != None and self.lastOrder.status == u'部分成交'):
        #     #print int(self.lastOrder.orderTime[-2:]),float(tick.time[6:]) 打印报单时间和tick时间
        #     #         报单时间的秒数
        #     iInsertTime=int(self.lastOrder.orderTime[-2:])
        #     #         行情时间的秒数
        #     MDtime_last2=float(tick.time[6:])
        #     #         行情时间最后两位小于委托时间的最后两位
        #     if(MDtime_last2<iInsertTime):
        #     #         行情时间加60秒
        #          MDtime_last2= MDtime_last2+60.0
        #     #         委托大于6秒未成交
        #     if(MDtime_last2-iInsertTime>6):
        #             self.cancelOrder(self.lastOrder.vtOrderID)
        #             self.lastOrder = None
        # # 固定止赢处理
        # self.fixedTakeProfit()
        # # 固定止损处理
        # self.fixedStopLoss()
    #----------------------------------------------------------------------
    def onBar(self, bar):
        """收到Bar推送（必须由用户继承实现）"""
        self.bg.updateBar(bar)

    #----------------------------------------------------------------------
    def onDay(self, bar):
        """收到Bar推送（必须由用户继承实现）"""
        self.bg.updateDay(bar)

    #----------------------------------------------------------------------
    def onOrder(self, order):
        """收到委托变化推送（必须由用户继承实现）"""
        # 对于无需做细粒度委托控制的策略，可以忽略onOrder
        self.lastOrder = order
        signalName=self.ctaEngine.orderStrategyDict[order.orderID][self.className]
        self.updateTradedPos(order,signalName)
        #清空0持仓数据库文档
        self.cleanDataBasePos(order,signalName)
        #更新持仓列表
        self.PositionCodeList = self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].distinct("vtSymbol")
        self.signalGroupList = self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].distinct("signalGroup")










    #----------------------------------------------------------------------
    def onTrade(self, trade):
        """收到成交推送（必须由用户继承实现）"""
        self.lastTrade = trade 
        # 对于无需做细粒度委托控制的策略，可以忽略onTrade


    def oneKeyClean(self,tick,d,signalName):
        if tick.symbol == d['vtSymbol']:
            shortPos = d['shortTd'] + d['shortYd']
            longPos = d['longTd'] + d['longYd']
            signalList = []

            if longPos < shortPos:
                signalList.extend(self.ctaEngine.sendOrder(d['vtSymbol'], CTAORDER_COVER, tick.askPrice1 + 10,
                                                           shortPos,self))  # 下单并返回orderID
                self.updatePosTarget(signalList, d['signalGroup'])
                self.sType = 0
                print   tick.datetime, signalName, u'买入平仓', d['vtSymbol'], shortPos, u'手'
            else:
                signalList.extend(self.ctaEngine.sendOrder(d['vtSymbol'], CTAORDER_SELL, tick.bidPrice1 - 10, longPos,self))
                self.updatePosTarget(signalList, d['signalGroup'])
                self.bType = 0
                print   tick.datetime, signalName, u'卖出平仓', d['vtSymbol'], longPos, u'手'

    def oneKeyClean_Bar(self, bar, d, signalName):
        if bar.symbol == d['vtSymbol']:
            shortPos = d['shortTd'] + d['shortYd']
            longPos = d['longTd'] + d['longYd']
            signalList = []

            if longPos < shortPos:
                signalList.extend(self.ctaEngine.sendOrder(d['vtSymbol'], CTAORDER_COVER, bar.close + 10,
                                                           shortPos,self))  # 下单并返回orderID
                # self.updatePosTarget(signalList, d['signalGroup'])
                # self.sType = 0
                print   bar.datetime, signalName, u'买入平仓', d['vtSymbol'], shortPos, u'手'
            else:
                signalList.extend(self.ctaEngine.sendOrder(d['vtSymbol'], CTAORDER_SELL, bar.close - 10, longPos,self))
                # self.updatePosTarget(signalList, d['signalGroup'])
                # self.bType = 0
                print   bar.datetime, signalName, u'卖出平仓', d['vtSymbol'], longPos, u'手'

                      

			        
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

 
