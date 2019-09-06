# encoding: UTF-8

from __future__ import print_function
import sys
try:
    reload(sys)  # Python 2
    sys.setdefaultencoding('utf8')
except NameError:
    pass         # Python 3

import multiprocessing
from time import sleep
from datetime import datetime, time
import path 
from vnpy.event import EventEngine2
from vnpy.trader.vtEvent import EVENT_LOG, EVENT_ERROR
from vnpy.trader.vtEngine import MainEngine, LogEngine 
from vnpy.trader.gateway import ctpGateway
from vnpy.trader.app import ctaStrategy
from vnpy.trader.app.ctaStrategy.ctaBase import EVENT_CTA_LOG

import time

#----------------------------------------------------------------------

def processErrorEvent(event):

    error = event.dict_['data']

    print(u'错误代码：%s，错误信息：%s' %(error.errorID, error.errorMsg))
    
    
#----------------------------------------------------------------------

    
class traderProcess(multiprocessing.Process):
    def __init__(self,name):
        multiprocessing.Process.__init__(self)
        #self.fileName = fileName
        #self.ee = EventEngine2() #成员变量
        # 创建日志引擎
        self.name = name
        le = LogEngine()
        le.setLogLevel(le.LEVEL_INFO)
        le.addConsoleHandler()
        le.addFileHandler() 
        self.le = le 
        ee = EventEngine2()
        self.le.info(u'事件引擎创建成功')

        me = MainEngine(ee)
        me.addGateway(ctpGateway)
        me.addApp(ctaStrategy)
        self.le.info(u'主引擎创建成功')

        ee.register(EVENT_LOG, self.le.processLogEvent)
        ee.register(EVENT_CTA_LOG, self.le.processLogEvent)
        ee.register(EVENT_ERROR, processErrorEvent)
        self.le.info(u'注册日志事件监听')   
        self.me = me

    def accountLogin (self,q,userID, password , brokerID,tdAddress,mdAddress):

        ## 创建日志引擎
        #le = LogEngine()
        #le.setLogLevel(le.LEVEL_INFO)
        #le.addConsoleHandler()
        #le.addFileHandler()

        self.le.info(u'启动CTA策略运行子进程')

        self.le.info(u'连接CTP接口')    

        self.me.connectJson(userID, password , brokerID,tdAddress,mdAddress)  # 修改登录部分函数 改为由请求参数登录
        
        sleep(3)  # 等待CTP接口初始化

        # 推送到queue
        self.me.dataEngine.putMsg(q)
        accountDict = q.get()
        q.put(accountDict)
        self.me.dataEngine.saveContracts()  # 保存合约信息到文件

        self.cta = self.me.getApp(ctaStrategy.appName)


    #def runChildProcess(self,q):
        #print('-'*20)
            
            ## 创建日志引擎
        #le = LogEngine()
        #le.setLogLevel(le.LEVEL_INFO)
        #le.addConsoleHandler()
        #le.addFileHandler()
            
        #le.info(u'启动CTA策略运行子进程')
        
        #ee = EventEngine2()
        #le.info(u'事件引擎创建成功')
        
        #me = MainEngine(ee)           
        #me.addGateway(ctpGateway)
        #me.addApp(ctaStrategy)
        #le.info(u'主引擎创建成功')
            
        #ee.register(EVENT_LOG, le.processLogEvent)
        #ee.register(EVENT_CTA_LOG, le.processLogEvent)
        #ee.register(EVENT_ERROR, processErrorEvent)
        #le.info(u'注册日志事件监听')

        #me.connectAnother(self.fileName)
        #self.me = me 
        #le.info(u'连接CTP接口')
        
        #sleep(3)                       # 等待CTP接口初始化
        
        ## 推送到queue 
        #me.dataEngine.putMsg(q)  
        
        #me.dataEngine.saveContracts()   # 保存合约信息到文件
        
        #self.cta = me.getApp(ctaStrategy.appName)
        #self.le = le
    def accountInfo(self,q):
        # 推送到queue 
        self.me.dataEngine.putMsg(q)
    def strategyStart(self,strategyName):
        self.cta.loadSetting()
        self.le.info(u'CTA策略载入成功')

        self.cta.initStrategy(strategyName)
        self.le.info (u'CTA策略初始化成功')

        self.cta.startStrategy(strategyName)
        self.le.info (u'CTA策略启动成功')   
            
    def strategyStop(self,strategyName):  
        self.cta.stopStrategy(strategyName)
        infoContent = u"停止策略"+strategyName
        self.le.info(infoContent)
    def strategyAllstop(self):
        self.cta.stopAll()
        self.le.info(u'所有策略停止成功')
    def putStrategyMsg(self,name, q):
        self.cta.putStrategyMsg(name,q)
    def positionInfo(self , q):
        self.me.dataEngine.putPos(q)
        
       

if __name__ == '__main__':
    #fileName_1 = 'CTP_connect.json'
    #fileName_2 = "CTP_connect_other.json"
    Process_names = locals()
    q = multiprocessing.Queue()
    # 使用manager 共享内存
    from multiprocessing import  Manager
    with Manager() as manager:
          d = manager.dict()   
    #根据类的字符串名实例化对象
    name =  "053941"
    name2 = "097675"
    Process_names[name] = traderProcess(name)
    Process_names[name2] = traderProcess(name2)
   # p1 =eval('traderProcess()')
    Process_names[name].daemon = True
    #p1.runChildProcess(q)
    
    #p2 = traderProcess() 
    #p2.daemon = True
    #p2.runChildProcess(q) 
    
    
    Process_names[name].accountLogin(q,userID="053941", password = "19900809", brokerID = "9999",tdAddress ="tcp://180.168.146.187:10030" , \
                 mdAddress ="tcp://180.168.146.187:10031" )

    Process_names[name2].accountLogin (q,userID="097675", password = "xyy961024", brokerID = "9999",tdAddress ="tcp://180.168.146.187:10030" , \
                 mdAddress ="tcp://180.168.146.187:10031")
    
    #while True:
        #p1.accountInfo(q)
        #sleep(1)    

        #num = q.get() 
        #print (num) 
        
        #p2.accountInfo(q)
        #sleep(1)    

        #num = q.get() 
        #print (num) 
    strategyName = "DualThrust"
    Process_names[name].strategyStart(strategyName)
    #p2.strategyStart(strategyName)
    sleep(2)
    Process_names[name].strategyStop(strategyName) 

        
        



    

