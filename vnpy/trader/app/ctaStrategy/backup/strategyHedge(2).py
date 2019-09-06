# encoding: UTF-8

"""
套保策略
"""

import math
import time
from ctaBase import *
from ctaTemplate import CtaTemplate,BarGenerator,ArrayManager
from datetime import datetime, timedelta
import datetime
import time
import math
from scipy.integrate import quad
from vtGateway import VtOrderData
import pandas as pd             #导入pandas模块
import string                   #导入string模块S
import csv
from Data import Param_setting_dict
from numba import jit
import ctaBacktesting
# 临时调用
from vtConstant import *
import numpy as np
from sklearn.linear_model import LinearRegression
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
               'pos']
    posAdd = 0

    #----------------------------------------------------------------------
    def __init__(self, ctaEngine, setting):
        """Constructor"""
        super(strategyHedge, self).__init__(ctaEngine, setting)

        # self.contractMode='Double'     #主力合约与次主力合约模式
        self.contractMode='Dominant'  #主力合约模式

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

        self.dayList=[]
        self.dayListPrice=[]
        self.dayDates=[]

        self.bg = BarGenerator(self.onDay,5,self.onXminBar)
        self.am = ArrayManager()
        self.spot=self.spotDF()
        self.future=pd.Series([])
        self.period=10 #套保周期
        self.Qs=10000 #现货数量
        self.direction="买入套保"
        self.startdate="2018-02-01"








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
        return contractname

    def onTick(self, tick):
        """收到行情TICK推送（必须由用户继承实现）"""
        self.bg.updateTick(tick)

        # if self.isNewDay:  # 每天判断一次
        #     self.isNewDay = False
        #     if self.contractname == '' or self.rollingDays != 0 or self.ctaEngine.rollingFlag:
        #         self.contractname, self.contractnameAdd = self.confirmDominant(tick)



    def linear(self,x,y):

        model=LinearRegression()

        try:
            model.fit(x,y)
        except:
            X=[]
            Y=[]
            for xx,yy in zip(x.values,y.values):
                X.append([float(xx)])
                Y.append([float(yy)])
            model.fit(X,Y)
        hedgeratio=model.coef_[0]
        return hedgeratio

    def spotDF(self):
        spotdf=pd.read_excel(u"D:\Huatai\套保专题\热卷中厚板套保\热轧现货.xlsx")
        spot=pd.Series(spotdf["Spot"])
        spot.index=spotdf["Date"]
        return spot

    def dateList(self,period,initdelta=None,startdate=None):
        datelist=[]
        for keys in self.ctaEngine.contract_dict:
            datelist.append(keys)
        datelist.sort()
        if startdate:
            datelist=datelist[datelist.index(startdate):]
        if initdelta:
            datelist=datelist[initdelta:]
        coverdates=datelist[0::period]
        adjdates=datelist[1::period]


        return coverdates,adjdates


    #----------------------------------------------------------------------
    def onBar(self, bar):
        """收到Bar推送（必须由用户继承实现）"""
        self.bg.updateDay(bar)
    #----------------------------------------------------------------------
    def onDay(self, bar):
        """收到Bar推送（必须由用户继承实现）"""
        self.bg.updateDay(bar)

    #----------------------------------------------------------------------
    def onXminBar(self, bar):
        """收到Tick推送（必须由用户继承实现）"""
        self.future[bar.date]=bar.close
        # self.future=self.future.append(pd.Series({"bar.date": bar.close}))

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
                    self.oneKeyClean_Bar(bar, d, contract['signalGroup'])
        coverdates,adjdates=self.dateList(self.period,startdate=self.startdate)



        if bar.date in coverdates[0:]:
            # print ("Future")
            # print(self.future)
            # print("Spot")
            # start=self.future[0]
            # end=bar.date
            # print(self.spot[self.future.index[0]:bar.date])
            # print(self.spot[self.future[0]:bar.date])
            x=(np.log(self.future.diff(self.period))).dropna()
            y=(np.log(self.spot[self.future.index[0]:bar.date].diff(self.period))).dropna()
            hedgeratio=self.linear(x,y)

            mult=self.ctaEngine.contract_dict[bar.date][bar.vtSymbol]["size"]
            self.n=int((hedgeratio*self.Qs*self.spot[bar.date])/(mult*self.future[bar.date]))
            if self.direction=="买入套保" and "正向套利" in self.signalGroupList:
                self.isShortCoverSign=True
                # self.bType=0
            if self.direction=="卖出套保" and "反向套利" in self.signalGroupList:
                self.isBuyCoverSign=True
                # self.sType=0
        if bar.date in adjdates[0:]:
            if self.direction=="买入套保" and "正向套利" not in self.signalGroupList:
                self.isBuySign=True
            if self.direction=="卖出套保" and "反向套利" not in self.signalGroupList:
                self.isShortSign=True


        #正向套利
        if self.isBuySign:

            signalList=[]
            self.signalName='正向套利'
            signalList.extend(self.ctaEngine.sendOrder(bar.vtSymbol,CTAORDER_BUY, bar.close+10, self.n,self))
            print  bar.datetime,self.signalName,u'买入开仓', bar.vtSymbol, self.n, u'手'
            self.writeCtaLog(bar.vtSymbol + u'买入价：'+str(bar.close+10) )
            # self.updatePosTarget(signalList, self.signalName)
            # i=0
            # while i<=self.n:
            #     signalList.extend(self.ctaEngine.sendOrder(bar.vtSymbol,CTAORDER_BUY, bar.close+10, 1,self))
            #     # print  bar.datetime,self.signalName,u'买入开仓', bar.vtSymbol, 1, u'手'
            #     self.writeCtaLog(bar.vtSymbol + u'买入价：'+str(bar.close+10) )
            #     # self.updatePosTarget(signalList, self.signalName)
            #     i=i+1
            # # self.bType = 1
            self.isBuySign = False




        # 反向套利
        if self.isShortSign:
            signalList=[]
            self.signalName='反向套利'
            signalList.extend(self.ctaEngine.sendOrder(bar.vtSymbol,CTAORDER_SHORT, bar.close-10, self.n,self))
            print  bar.datetime,self.signalName,u'卖出开仓', bar.vtSymbol, self.n, u'手'
            self.sType = 1

            self.writeCtaLog(bar.vtSymbolv + u'卖出价：'+str( bar.close-10))

            # self.updatePosTarget(signalList, self.signalName)
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
                                                           shortPos))  # 下单并返回orderID
                self.updatePosTarget(signalList, d['signalGroup'])
                self.sType = 0
                print   tick.datetime, signalName, u'买入平仓', d['vtSymbol'], shortPos, u'手'
            else:
                signalList.extend(self.ctaEngine.sendOrder(d['vtSymbol'], CTAORDER_SELL, tick.bidPrice1 - 10, longPos))
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
                                                           shortPos))  # 下单并返回orderID
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


