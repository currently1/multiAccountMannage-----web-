# encoding: UTF-8

'''
本文件包含了CTA引擎中的策略开发用模板，开发策略时需要继承CtaTemplate类。
'''

from ctaBase import *
from vtConstant import *
# import talib
import numpy as np
from collections import defaultdict
import datetime
import logging
from numba import jit


########################################################################
class CtaTemplate(object):
    """CTA策略模板"""

    # 策略类的名称和作者
    className = 'CtaTemplate'
    author = EMPTY_UNICODE

    # MongoDB数据库的名称，K线数据库默认为1分钟
    tickDbName = TICK_DB_NAME
    barDbName = MINUTE_DB_NAME

    # 策略的基本参数
    name = EMPTY_UNICODE  # 策略实例名称
    vtSymbol = EMPTY_STRING  # 交易的合约vt系统代码
    productClass = EMPTY_STRING  # 产品类型（只有IB接口需要）
    currency = EMPTY_STRING  # 货币（只有IB接口需要）

    # 策略的基本变量，由引擎管理
    inited = False  # 是否进行了初始化
    trading = False  # 是否启动交易，由引擎管理
    pos = 0  # 持仓情况

    # 参数列表，保存了参数的名称
    paramList = ['name',
                 'className',
                 'author',
                 'vtSymbol']

    # 变量列表，保存了变量的名称
    varList = ['inited',
               'trading',
               'pos']

    # ----------------------------------------------------------------------
    def __init__(self, ctaEngine, setting):
        """Constructor"""
        self.ctaEngine = ctaEngine

        # 设置策略的参数
        if setting:
            d = self.__dict__
            for key in self.paramList:
                if key in setting:
                    d[key] = setting[key]

    # ----------------------------------------------------------------------
    def onInit(self):
        """初始化策略（必须由用户继承实现）"""
        raise NotImplementedError

    # ----------------------------------------------------------------------
    def onStart(self):
        """启动策略（必须由用户继承实现）"""
        raise NotImplementedError

    # ----------------------------------------------------------------------
    def onStop(self):
        """停止策略（必须由用户继承实现）"""
        raise NotImplementedError

    # ----------------------------------------------------------------------
    def onTick(self, tick):
        """收到行情TICK推送（必须由用户继承实现）"""
        raise NotImplementedError

    # ----------------------------------------------------------------------
    def onOrder(self, order):
        """收到委托变化推送（必须由用户继承实现）"""
        raise NotImplementedError

    # ----------------------------------------------------------------------
    def onTrade(self, trade):
        """收到成交推送（必须由用户继承实现）"""
        raise NotImplementedError

    # ----------------------------------------------------------------------
    def onBar(self, bar):
        """收到Bar推送（必须由用户继承实现）"""
        raise NotImplementedError

    # ----------------------------------------------------------------------
    def buy(self, price, volume, stop=False):
        """买开"""
        return self.sendOrder(CTAORDER_BUY, price, volume, stop)

    # ----------------------------------------------------------------------
    def sell(self, price, volume, stop=False):
        """卖平"""
        return self.sendOrder(CTAORDER_SELL, price, volume, stop)

        # ----------------------------------------------------------------------

    def short(self, price, volume, stop=False):
        """卖开"""
        return self.sendOrder(CTAORDER_SHORT, price, volume, stop)

        # ----------------------------------------------------------------------

    def cover(self, price, volume, stop=False):
        """买平"""
        return self.sendOrder(CTAORDER_COVER, price, volume, stop)

    # ----------------------------------------------------------------------
    def sendOrder(self, orderType, price, volume, stop=False):
        """发送委托"""
        if self.trading:
            # 如果stop为True，则意味着发本地停止单
            if stop:
                vtOrderID = self.ctaEngine.sendStopOrder(self.vtSymbol, orderType, price, volume, self) + '10000'
            else:
                vtOrderID = self.ctaEngine.sendOrder(self.vtSymbol, orderType, price, volume, self) + '10000'
            return vtOrderID
        else:
            # 交易停止时发单返回空字符串
            return ''

            # ----------------------------------------------------------------------

    def cancelOrder(self, vtOrderID):
        """撤单"""
        # 如果发单号为空字符串，则不进行后续操作
        if not vtOrderID:
            return

        if STOPORDERPREFIX in vtOrderID:
            self.ctaEngine.cancelStopOrder(vtOrderID)
        else:
            self.ctaEngine.cancelOrder(vtOrderID)

    # ----------------------------------------------------------------------
    def insertTick(self, tick):
        """向数据库中插入tick数据"""
        self.ctaEngine.insertData(self.tickDbName, self.vtSymbol, tick)

    # ----------------------------------------------------------------------
    def insertBar(self, bar):
        """向数据库中插入bar数据"""
        self.ctaEngine.insertData(self.barDbName, self.vtSymbol, bar)

    # ----------------------------------------------------------------------
    def loadTick(self, days):
        """读取tick数据"""
        return self.ctaEngine.loadTick(self.tickDbName, self.vtSymbol, days)

    # ----------------------------------------------------------------------
    def loadBar(self, days):
        """读取bar数据"""
        return self.ctaEngine.loadBar(self.barDbName, self.vtSymbol, days)

    # ----------------------------------------------------------------------
    def writeCtaLog(self, content):
        """记录CTA日志"""
        content = self.name + ':' + content
        self.ctaEngine.writeCtaLog(content)

    # ----------------------------------------------------------------------
    def putEvent(self):
        """发出策略状态变化事件"""
        self.ctaEngine.putStrategyEvent(self.name)

    # ----------------------------------------------------------------------
    def getEngineType(self):
        """查询当前运行的环境"""
        return self.ctaEngine.engineType

    def initialStrategyPos(self, strategyName):
        self.ctaEngine.dbClient[POSITION_DB_NAME][strategyName].drop()

    def cancelDBorder(self, orderID, strategy):
        trade = self.ctaEngine.workingLimitOrderDict[orderID]
        # 初始化
        PositionDetails = CtaMongodbPositon()
        dbCusor = self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].find(
            {'signalGroup': self.ctaEngine.orderStrategyDict[orderID][self.className], 'vtSymbol': trade.vtSymbol})

        # 如果寻回结果大于0
        if dbCusor.count() > 0:
            for d in dbCusor:
                PositionDetails.__dict__ = d

        alterTargetVolume = -(trade.totalVolume - trade.tradedVolume)
        # 多头
        if trade.direction == DIRECTION_LONG:
            # 开仓
            if trade.offset is OFFSET_OPEN:
                PositionDetails.longPosTarget += alterTargetVolume
            # 平今
            elif trade.offset is OFFSET_CLOSETODAY:
                PositionDetails.shortPosTarget -= alterTargetVolume
            # 平昨
            elif trade.offset is OFFSET_CLOSEYESTERDAY:
                PositionDetails.shortPosTarget -= alterTargetVolume
            # 平仓
            elif trade.offset is OFFSET_CLOSE:
                # 上期所等同于平昨
                if PositionDetails.exchange is EXCHANGE_SHFE:
                    PositionDetails.shortPosTarget -= alterTargetVolume
                # 非上期所，优先平今
                else:
                    PositionDetails.shortPosTarget -= alterTargetVolume

                    if PositionDetails.shortTd < 0:
                        PositionDetails.shortYd += PositionDetails.shortTd
                        PositionDetails.shortTd = 0

        # 空头
        elif trade.direction is DIRECTION_SHORT:
            # 开仓
            if trade.offset is OFFSET_OPEN:
                PositionDetails.shortPosTarget += alterTargetVolume
            # 平今
            elif trade.offset is OFFSET_CLOSETODAY:
                PositionDetails.longPosTarget -= alterTargetVolume
            # 平昨
            elif trade.offset is OFFSET_CLOSEYESTERDAY:
                PositionDetails.longPosTarget -= alterTargetVolume
            # 平仓
            elif trade.offset is OFFSET_CLOSE:
                # 上期所等同于平昨
                if PositionDetails.exchange is EXCHANGE_SHFE:
                    PositionDetails.longPosTarget -= alterTargetVolume
                # 非上期所，优先平今
                else:
                    PositionDetails.longPosTarget -= alterTargetVolume

                    if PositionDetails.longTd < 0:
                        PositionDetails.longYd += PositionDetails.longTd
                        PositionDetails.longTd = 0

        self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].update(
            {'signalGroup': self.ctaEngine.orderStrategyDict[orderID][self.className], 'vtSymbol': trade.vtSymbol},
            PositionDetails.__dict__,
            upsert=True)

    def updatePosTarget(self, order, signalName):
        # signalGroup根据下单ID记录入数据库得目标持仓

        trade = order
        # 初始化
        PositionDetails = CtaMongodbPositon()

        # 查找数据库是否存在已有持仓
        dbCusor = self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].find(
            {'signalGroup': signalName, 'vtSymbol': trade.vtSymbol})

        # 如果寻回结果大于0
        if dbCusor.count() > 0:
            for d in dbCusor:
                PositionDetails.__dict__ = d

        # 持仓贴标签
        PositionDetails.signalGroup = signalName
        PositionDetails.vtSymbol = trade.vtSymbol

        # 多头
        if trade.direction == DIRECTION_LONG:
            # 开仓
            if trade.offset is OFFSET_OPEN:
                PositionDetails.longPosTarget += trade.totalVolume
            # 平今
            elif trade.offset is OFFSET_CLOSETODAY:
                PositionDetails.shortPosTarget -= trade.totalVolume
            # 平昨
            elif trade.offset is OFFSET_CLOSEYESTERDAY:
                PositionDetails.shortPosTarget -= trade.totalVolume
            # 平仓
            elif trade.offset is OFFSET_CLOSE:
                # 上期所等同于平昨
                if PositionDetails.exchange is EXCHANGE_SHFE:
                    PositionDetails.shortPosTarget -= trade.totalVolume
                # 非上期所，优先平今
                else:
                    PositionDetails.shortPosTarget -= trade.totalVolume

                    if PositionDetails.shortTd < 0:
                        PositionDetails.shortYd += PositionDetails.shortTd
                        PositionDetails.shortTd = 0

        # 空头
        elif trade.direction is DIRECTION_SHORT:
            # 开仓
            if trade.offset is OFFSET_OPEN:
                PositionDetails.shortPosTarget += trade.totalVolume
            # 平今
            elif trade.offset is OFFSET_CLOSETODAY:
                PositionDetails.longPosTarget -= trade.totalVolume
            # 平昨
            elif trade.offset is OFFSET_CLOSEYESTERDAY:
                PositionDetails.longPosTarget -= trade.totalVolume
            # 平仓
            elif trade.offset is OFFSET_CLOSE:
                # 上期所等同于平昨
                if PositionDetails.exchange is EXCHANGE_SHFE:
                    PositionDetails.longPosTarget -= trade.totalVolume
                # 非上期所，优先平今
                else:
                    PositionDetails.longPosTarget -= trade.totalVolume

                    if PositionDetails.longTd < 0:
                        PositionDetails.longYd += PositionDetails.longTd
                        PositionDetails.longTd = 0
            # self.ctaEngine.dbClient[POSITION_DB_NAME].update({'longPnl': 0}, PositionDetails.__dict__, upsert=True)
            # 插入或更新数据库相应持仓
        # if PositionDetails.shortPosTarget < 0:
        #     pass
        self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].update(
            {'signalGroup': signalName, 'vtSymbol': trade.vtSymbol}, PositionDetails.__dict__,
            upsert=True)

        # #打标签
        #
        # self.ctaEngine.workingLimitOrderDict[order.orderID].signalGroup = signalName

    def updateTradedPos(self, trade, signalName,status):

        vtSymbol = trade.vtSymbol

        # 有成交记录的时候更新数据库
        if status in [STATUS_PARTTRADED, STATUS_ALLTRADED]:
            # 查找数据库是否存在已有持仓
            dbCusor = self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].find(
                {'signalGroup': signalName, 'vtSymbol': vtSymbol})
            if dbCusor.count() > 0:
                # 读取数据库上的持仓情况
                PositionDetails = CtaMongodbPositon()
                for d in dbCusor:
                    PositionDetails.__dict__ = d

                # 整合实际成交

                # 多头
                if trade.direction == DIRECTION_LONG:
                    # 开仓
                    if trade.offset is OFFSET_OPEN:
                        PositionDetails.longTd += trade.volume
                    # 平今
                    elif trade.offset is OFFSET_CLOSETODAY:
                        PositionDetails.shortTd -= trade.volume
                    # 平昨
                    elif trade.offset is OFFSET_CLOSEYESTERDAY:
                        PositionDetails.shortYd -= trade.volume
                    # 平仓
                    elif trade.offset is OFFSET_CLOSE:
                        # 上期所等同于平昨
                        if PositionDetails.exchange is EXCHANGE_SHFE:
                            PositionDetails.shortYd -= trade.volume
                        # 非上期所，优先平今
                        else:
                            PositionDetails.shortTd -= trade.volume

                            if PositionDetails.shortTd < 0:
                                PositionDetails.shortYd += PositionDetails.shortTd
                                PositionDetails.shortTd = 0

                # 空头
                elif trade.direction is DIRECTION_SHORT:
                    # 开仓
                    if trade.offset is OFFSET_OPEN:
                        PositionDetails.shortTd += trade.volume
                    # 平今
                    elif trade.offset is OFFSET_CLOSETODAY:
                        PositionDetails.longTd -= trade.volume
                    # 平昨
                    elif trade.offset is OFFSET_CLOSEYESTERDAY:
                        PositionDetails.longYd -= trade.volume
                    # 平仓
                    elif trade.offset is OFFSET_CLOSE:
                        # 上期所等同于平昨
                        if PositionDetails.exchange is EXCHANGE_SHFE:
                            PositionDetails.longYd -= trade.volume
                        # 非上期所，优先平今
                        else:
                            PositionDetails.longTd -= trade.volume

                            if PositionDetails.longTd < 0:
                                PositionDetails.longYd += PositionDetails.longTd
                                PositionDetails.longTd = 0
                # 插入或更新数据库相应持仓
                self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].update(
                    {'signalGroup': signalName, 'vtSymbol': vtSymbol}, PositionDetails.__dict__,
                    upsert=True)

            else:
                # 成交过快，可能数据库持仓已经被清理
                print u'没有找到对应数据库持仓'

    def cleanDataBasePos(self, order, signalName):

        trade = order
        dbCusor = self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].find(
            {'signalGroup': signalName, 'vtSymbol': trade.vtSymbol})
        for d in dbCusor:
            # 可以整合成longPso+longFrozen
            longPos = d['longTd'] + d['longYd'] + d['longTdFrozen'] + d['longYdFrozen'] + d['longPosTarget']
            shortPos = d['shortTd'] + d['shortYd'] + d['shortTdFrozen'] + d['shortYdFrozen'] + d['shortPosTarget']
            # 持仓全为0，则删除文档
            if longPos + shortPos == 0:
                self.ctaEngine.dbClient[POSITION_DB_NAME][self.className].remove(
                    {'signalGroup': signalName, 'vtSymbol': trade.vtSymbol})

    def killOrder(self,bar,counts,gap):

        for key, value in self.ctaEngine.workingLimitOrderDict.items():
            if value.vtSymbol==bar.vtSymbol:
                #记录TICK追单数
                if not self.ctaEngine.stopCount[key]:
                    self.ctaEngine.stopCount[key]=1
                else:
                    self.ctaEngine.stopCount[key]+=1
                #10个TICK未成交，撤单and追单
                if self.ctaEngine.stopCount[key]>counts:
                    self.cancelOrder(key)            #删除workingLimitOrder
                    # self.cancelDBorder(key, self)    #删除服务器目标仓位
                    self.writeCtaLog(
                        '撤单信号：' + '时间:' + str(bar.datetime) + ' 委托单号 '
                        + str(key) + ' 合约： ' + value.vtSymbol +' 委托方向：' +value.direction + ' 委托信号： '+ value.offset
                        +str((value.totalVolume - value.tradedVolume)) + ' 手 ' +' 委托价格' +str(value.price))

                    print u'Order %s Cancelled'%key
                    del self.ctaEngine.stopCount[key]

                    if value.direction == DIRECTION_LONG:
                        slipSign = 1
                        # 开仓
                        if value.offset == OFFSET_OPEN:
                           orderType=CTAORDER_BUY
                        # 平今
                        elif value.offset == OFFSET_CLOSETODAY:
                            orderType = CTAORDER_COVER
                        # 平昨
                        elif value.offset == OFFSET_CLOSEYESTERDAY:
                            orderType = CTAORDER_COVER
                        # # 没有区分平今平昨
                        elif value.offset == OFFSET_CLOSE:
                            # 上期所等同于平昨
                            if value.exchange == EXCHANGE_SHFE:
                                orderType = CTAORDER_COVER
                            # 非上期所，优先平今
                            else:
                                orderType = CTAORDER_COVER


                    elif value.direction == DIRECTION_SHORT:
                        slipSign =-1
                        # 开仓
                        if value.offset == OFFSET_OPEN:
                           orderType=CTAORDER_SHORT
                        # 平今
                        elif value.offset == OFFSET_CLOSETODAY:
                            orderType = CTAORDER_SELL
                        # 平昨
                        elif value.offset == OFFSET_CLOSEYESTERDAY:
                            orderType = CTAORDER_SELL
                        # 没有区分平今平昨
                        elif value.offset == OFFSET_CLOSE:
                            # 上期所等同于平昨
                            if value.exchange == EXCHANGE_SHFE:
                                orderType = CTAORDER_SELL
                            # 非上期所，优先平今
                            else:
                                orderType = CTAORDER_SELL


                    symbolInit = self.ctaEngine.contract_dict[bar.date][bar.vtSymbol]['symbolInit']

                    MinimumPriceChange=self.ctaEngine.Param_setting_dict[symbolInit]['MinimumPriceChange']
                    self.signalName=self.ctaEngine.orderStrategyDict[key][self.className]
                    self.ctaEngine.sendOrder(value.vtSymbol,orderType,bar.lastPrice+MinimumPriceChange*slipSign*3,(value.totalVolume-value.tradedVolume),self)
                    self.writeCtaLog(
                        '追单信号' + self.signalName + ': ' + '下单时间:'
                        + str(bar.datetime) + ' 合约 ' + value.vtSymbol + ' 委托方向：' +value.direction
                        + ' 委托信号： '+ value.offset  + str((value.totalVolume - value.tradedVolume)) + ' 手 '
                        + ' 价格: ' + str(bar.lastPrice+MinimumPriceChange*slipSign*gap))


class BarGenerator(object):
    """
    K线合成器，支持：
    1. 基于Tick合成1分钟K线
    2. 基于1分钟K线合成X分钟K线（X可以是2、3、5、10、15、30	）
    """

    # ----------------------------------------------------------------------
    def __init__(self, onBar, xmin=0, onXminBar=None):
        """Constructor"""
        self.bar = {}  # 1分钟K线对象
        self.onBar = onBar  # 1分钟K线回调函数

        self.xminBar = {}  # X分钟K线对象
        self.xmin = xmin  # X的值
        self.onXminBar = onXminBar  # X分钟K线的回调函数

        self.lastTick = defaultdict(dict)  # 上一TICK缓存对象
        self.lastBar = defaultdict(dict) # 上一BAR缓存对象
        self.sameDay = True

    # ----------------------------------------------------------------------
    def updateDay(self, bar):
        """日线级别更新"""
        newDay = False  # 默认不是新的一分钟
        # 尚未创建对象
        if bar.vtSymbol not in self.xminBar.keys():
            self.xminBar[bar.vtSymbol] = CtaDailyData()
            self.xminBar[bar.vtSymbol].vtSymbol = bar.vtSymbol
            self.xminBar[bar.vtSymbol].symbol = bar.symbol
            self.xminBar[bar.vtSymbol].exchange = bar.exchange

            self.xminBar[bar.vtSymbol].open = bar.open
            self.xminBar[bar.vtSymbol].high = bar.high
            self.xminBar[bar.vtSymbol].low = bar.low

            self.xminBar[bar.vtSymbol].datetime = bar.datetime  # 以第一根分钟K线的结束时间戳作为X分钟线的时间戳
            # newDay=True

        elif (bar.datetime.time() >= datetime.datetime.strptime('20:59:00', '%H:%M:%S').time() and self.lastBar[bar.vtSymbol].datetime.time()< datetime.datetime.strptime('16:00:00', '%H:%M:%S').time()):
            # 推送

            self.xminBar[bar.vtSymbol].datetime = self.lastBar[bar.vtSymbol].datetime.replace(hour=15, minute=0,
                                                                                              second=0,
                                                                                              microsecond=0)  # 将秒和微秒设为0
            self.xminBar[bar.vtSymbol].date = self.lastBar[bar.vtSymbol].datetime.strftime('%Y-%m-%d')
            self.xminBar[bar.vtSymbol].time = self.lastBar[bar.vtSymbol].datetime.strftime('%H:%M:%S.%f')


            self.onXminBar(self.xminBar[bar.vtSymbol])

            # 清空老K线缓存对象
            del self.xminBar[bar.vtSymbol]
            newDay=True
            # self.sameDay=False

        elif bar.datetime.time() >= datetime.datetime.strptime('08:59:00','%H:%M:%S').time() \
                and self.lastBar[bar.vtSymbol].datetime.time() >= datetime.datetime.strptime('09:00:00','%H:%M:%S').time() \
                and self.lastBar[bar.vtSymbol].datetime.time() <= datetime.datetime.strptime('16:00:00', '%H:%M:%S').time()\
                and self.lastBar[bar.vtSymbol].datetime.day != bar.datetime.day:
            self.xminBar[bar.vtSymbol].datetime = self.lastBar[bar.vtSymbol].datetime.replace(hour=15, minute=0,
                                                                                              second=0,
                                                                                              microsecond=0)  # 将秒和微秒设为0
            self.xminBar[bar.vtSymbol].date = self.lastBar[bar.vtSymbol].datetime.strftime('%Y-%m-%d')
            self.xminBar[bar.vtSymbol].time = self.lastBar[bar.vtSymbol].datetime.strftime('%H:%M:%S.%f')

            # 推送
            self.onXminBar(self.xminBar[bar.vtSymbol])

            # 清空老K线缓存对象
            del self.xminBar[bar.vtSymbol]
            newDay=True
            # self.sameDay = True


        # 累加老K线
        else:
            self.xminBar[bar.vtSymbol].high = max(self.xminBar[bar.vtSymbol].high, bar.high)
            self.xminBar[bar.vtSymbol].low = min(self.xminBar[bar.vtSymbol].low, bar.low)


        if newDay:
            self.xminBar[bar.vtSymbol] = CtaDailyData()
            self.xminBar[bar.vtSymbol].vtSymbol = bar.vtSymbol
            self.xminBar[bar.vtSymbol].symbol = bar.symbol
            self.xminBar[bar.vtSymbol].exchange = bar.exchange
            self.xminBar[bar.vtSymbol].open = bar.open
            self.xminBar[bar.vtSymbol].high = bar.high
            self.xminBar[bar.vtSymbol].low = bar.low
            self.xminBar[bar.vtSymbol].datetime = bar.datetime  # 以第一根分钟K线的结束时间戳作为X分钟线的时间戳
        else:
            # 通用部分
            self.xminBar[bar.vtSymbol].close = bar.close
            self.xminBar[bar.vtSymbol].openInterest = bar.openInterest
            self.xminBar[bar.vtSymbol].volume += int(bar.volume)


        # if self.xminBar[bar.vtSymbol].datetime.day != bar.datetime.day: #夜盘推送DAY开关，大于15点只推送一次
        #     self.sameDay=True



        #
        # if self.lastBar[bar.vtSymbol]:
        #     volumeChange = bar.volume - self.lastBar[bar.vtSymbol].volume  # 当前K线内的成交量
        #     self.xminBar[bar.vtSymbol].volume += max(volumeChange, 0) # 避免夜盘开盘lastTick.volume为昨日收盘数据，导致成交量变化为负的情况
        #
        # 缓存Bar
        self.lastBar[bar.vtSymbol] = bar




    # ----------------------------------------------------------------------

    def updateTick(self, tick):
        """TICK更新"""
        newMinute = False  # 默认不是新的一分钟

        # 尚未创建对象
        if tick.vtSymbol not in self.bar:
            self.bar[tick.vtSymbol] = CtaBarData()
            newMinute = True
        # 新的一分钟
        elif self.bar[tick.vtSymbol].datetime.minute != tick.datetime.minute:
            # 生成上一分钟K线的时间戳
            self.bar[tick.vtSymbol].datetime = self.bar[tick.vtSymbol].datetime.replace(second=0,microsecond=0)  # 将秒和微秒设为0，时间戳为上一分钟走完
            # (self.bar[tick.vtSymbol].datetime + datetime.timedelta(minutes=1)).replace(second=0, microsecond=0)
            self.bar[tick.vtSymbol].date = self.bar[tick.vtSymbol].datetime.strftime('%Y-%m-%d')
            self.bar[tick.vtSymbol].time = self.bar[tick.vtSymbol].datetime.strftime('%H:%M:%S.%f')

            # 推送已经结束的上一分钟K线
            self.onBar(self.bar[tick.vtSymbol])

            # 创建新的K线对象
            self.bar[tick.vtSymbol] = CtaBarData()
            newMinute = True

        # 初始化新一分钟的K线数据
        if newMinute:
            self.bar[tick.vtSymbol].vtSymbol = tick.vtSymbol
            # self.bar[tick.vtSymbol].symbol = tick.symbol
            self.bar[tick.vtSymbol].exchange = tick.exchange

            self.bar[tick.vtSymbol].open = tick.lastPrice
            self.bar[tick.vtSymbol].high = tick.lastPrice
            self.bar[tick.vtSymbol].low = tick.lastPrice
        # 累加更新老一分钟的K线数据
        else:
            self.bar[tick.vtSymbol].high = max(self.bar[tick.vtSymbol].high, tick.lastPrice)
            self.bar[tick.vtSymbol].low = min(self.bar[tick.vtSymbol].low, tick.lastPrice)

        # 通用更新部分
        self.bar[tick.vtSymbol].close = tick.lastPrice
        self.bar[tick.vtSymbol].datetime = tick.datetime
        self.bar[tick.vtSymbol].openInterest = tick.openInterest
        self.bar[tick.vtSymbol].volume += tick.volume

        # if self.lastTick[tick.vtSymbol]:
        #     volumeChange = tick.volume - self.lastTick[tick.vtSymbol].volume  # 当前K线内的成交量
        #     self.bar[tick.vtSymbol].volume += max(volumeChange, 0)  # 避免夜盘开盘lastTick.volume为昨日收盘数据，导致成交量变化为负的情况

        # 缓存Tick
        self.lastTick[tick.vtSymbol] = tick

    # ----------------------------------------------------------------------
    def updateBar(self, bar):
        """1分钟K线更新"""
        # 尚未创建对象
        if bar.vtSymbol not in self.xminBar.keys():
            self.xminBar[bar.vtSymbol] = CtaBarData()

            self.xminBar[bar.vtSymbol].vtSymbol = bar.vtSymbol
            self.xminBar[bar.vtSymbol].symbol = bar.symbol
            self.xminBar[bar.vtSymbol].exchange = bar.exchange

            self.xminBar[bar.vtSymbol].open = bar.open
            self.xminBar[bar.vtSymbol].high = bar.high
            self.xminBar[bar.vtSymbol].low = bar.low

            self.xminBar[bar.vtSymbol].datetime = bar.datetime
        # 累加老K线
        else:
            self.xminBar[bar.vtSymbol].high = max(self.xminBar[bar.vtSymbol].high, bar.high)
            self.xminBar[bar.vtSymbol].low = min(self.xminBar[bar.vtSymbol].low, bar.low)

        # 通用部分
        self.xminBar[bar.vtSymbol].close = bar.close
        self.xminBar[bar.vtSymbol].openInterest = bar.openInterest
        self.xminBar[bar.vtSymbol].volume += int(bar.volume)

        # X分钟已经走完
        if not (bar.datetime.minute+1) % self.xmin:  # 可以用X整除2
            # 生成上一X分钟K线的时间戳
            self.xminBar[bar.vtSymbol].datetime = self.xminBar[bar.vtSymbol].datetime.replace(second=0,
                                                                                          microsecond=0)  # 将秒和微秒设为0
            self.xminBar[bar.vtSymbol].date = self.xminBar[bar.vtSymbol].datetime.strftime('%Y-%m-%d')
            self.xminBar[bar.vtSymbol].time = self.xminBar[bar.vtSymbol].datetime.strftime('%H:%M:%S.%f')

            # 推送
            self.onXminBar(self.xminBar[bar.vtSymbol])

            # 清空老K线缓存对象
            del self.xminBar[bar.vtSymbol]


########################################################################
class ArrayManager(object):
    """
    K线序列管理工具，负责：
    1. K线时间序列的维护
    2. 常用技术指标的计算
    """

    # ----------------------------------------------------------------------
    def __init__(self, size=100):
        """Constructor"""
        self.count = 0  # 缓存计数
        self.size = size  # 缓存大小
        self.inited = False  # True if count>=size

        self.openArray = np.zeros(size)  # OHLC
        self.highArray = np.zeros(size)
        self.lowArray = np.zeros(size)
        self.closeArray = np.zeros(size)
        self.volumeArray = np.zeros(size)

    # ----------------------------------------------------------------------
    def updateBar(self, bar):
        """更新K线"""
        self.count += 1
        if not self.inited and self.count >= self.size:
            self.inited = True

        self.openArray[0:self.size - 1] = self.openArray[1:self.size]
        self.highArray[0:self.size - 1] = self.highArray[1:self.size]
        self.lowArray[0:self.size - 1] = self.lowArray[1:self.size]
        self.closeArray[0:self.size - 1] = self.closeArray[1:self.size]
        self.volumeArray[0:self.size - 1] = self.volumeArray[1:self.size]

        self.openArray[-1] = bar.open
        self.highArray[-1] = bar.high
        self.lowArray[-1] = bar.low
        self.closeArray[-1] = bar.close
        self.volumeArray[-1] = bar.volume

    # ----------------------------------------------------------------------
    @property
    def open(self):
        """获取开盘价序列"""
        return self.openArray

    # ----------------------------------------------------------------------
    @property
    def high(self):
        """获取最高价序列"""
        return self.highArray

    # ----------------------------------------------------------------------
    @property
    def low(self):
        """获取最低价序列"""
        return self.lowArray

    # ----------------------------------------------------------------------
    @property
    def close(self):
        """获取收盘价序列"""
        return self.closeArray

    # ----------------------------------------------------------------------
    @property
    def volume(self):
        """获取成交量序列"""
        return self.volumeArray

    # ----------------------------------------------------------------------
    def sma(self, n, array=False):
        """简单均线"""
        result = talib.SMA(self.close, n)
        if array:
            return result
        return result[-1]

    # ----------------------------------------------------------------------
    def std(self, n, array=False):
        """标准差"""
        result = talib.STDDEV(self.close, n)
        if array:
            return result
        return result[-1]

    # ----------------------------------------------------------------------
    def cci(self, n, array=False):
        """CCI指标"""
        result = talib.CCI(self.high, self.low, self.close, n)
        if array:
            return result
        return result[-1]

    # ----------------------------------------------------------------------
    def atr(self, n, array=False):
        """ATR指标"""
        result = talib.ATR(self.high, self.low, self.close, n)
        if array:
            return result
        return result[-1]

    # ----------------------------------------------------------------------
    def rsi(self, n, array=False):
        """RSI指标"""
        result = talib.RSI(self.close, n)
        if array:
            return result
        return result[-1]

    # ----------------------------------------------------------------------
    def macd(self, fastPeriod, slowPeriod, signalPeriod, array=False):
        """MACD指标"""
        macd, signal, hist = talib.MACD(self.close, fastPeriod,
                                        slowPeriod, signalPeriod)
        if array:
            return macd, signal, hist
        return macd[-1], signal[-1], hist[-1]

    # ----------------------------------------------------------------------
    def adx(self, n, array=False):
        """ADX指标"""
        result = talib.ADX(self.high, self.low, self.close, n)
        if array:
            return result
        return result[-1]

    # ----------------------------------------------------------------------
    def boll(self, n, dev, array=False):
        """布林通道"""
        mid = self.sma(n, array)
        std = self.std(n, array)

        up = mid + std * dev
        down = mid - std * dev

        return up, down

        # ----------------------------------------------------------------------

    def keltner(self, n, dev, array=False):
        """肯特纳通道"""
        mid = self.sma(n, array)
        atr = self.atr(n, array)

        up = mid + atr * dev
        down = mid - atr * dev

        return up, down

    # ----------------------------------------------------------------------
    def donchian(self, n, array=False):
        """唐奇安通道"""
        up = talib.MAX(self.high, n)
        down = talib.MIN(self.low, n)

        if array:
            return up, down
        return up[-1], down[-1]


# 开发一个日志系统， 既要把日志输出到控制台， 还要写入日志文件
class Logger(object):
    def __init__(self, logname, loglevel, logger):
        '''
           指定保存日志的文件路径，日志级别，以及调用文件
           将日志存入到指定的文件中
        '''

        # 创建一个logger
        self.logger = logging.getLogger(logger)
        self.logger.setLevel(logging.DEBUG)

        # 创建一个handler，用于写入日志文件
        fh = logging.FileHandler(logname)
        fh.setLevel(logging.DEBUG)

        # 再创建一个handler，用于输出到控制台
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)

        # 定义handler的输出格式
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        # formatter = format_dict[int(loglevel)]
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        # 给logger添加handler
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

    def getlog(self):
        return self.logger
