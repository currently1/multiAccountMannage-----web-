#!/usr/bin/env python 
# -*- coding: utf-8 -*-

# Application is the glue between one or more service definitions, interface and protocol choices.
from spyne import Application
# @rpc decorator exposes methods as remote procedure calls
# and declares the data types it accepts and returns
from spyne import rpc
# spyne.service.ServiceBase is the base class for all service definitions.
from spyne import ServiceBase
# The names of the needed types for implementing this service should be self-explanatory.
from spyne import Iterable, Integer, Unicode ,Array, String
 
from spyne.protocol.soap import Soap11
# Our server is going to use HTTP as transport, It’s going to wrap the Application instance.
from spyne.server.wsgi import WsgiApplication
import multiprocessing
from dataType import accountInfo
import path 
from time import sleep
# step1: Defining a Spyne Service
q = multiprocessing.Queue()
#locals()函数来完成动态变量命名及赋值
Process_names = locals() 
# 使用manager 共享内存
from multiprocessing import  Manager


class HelloWorldService(ServiceBase):
    @rpc(Unicode, Integer, _returns=Iterable(Unicode))
    def say_hello(self, name, times):
        """Docstrings for service methods appear as documentation in the wsdl.
        <b>What fun!</b>
        @param name: the name to say hello to
        @param times: the number of times to say hello
        @return  When returning an iterable, you can use any type of python iterable. Here, we chose to use generators.
        """
 
        for i in range(times):
            yield u'Hello, %s' % name

# 定义一个启动获取账户信息的service类
class TradeInfoService(ServiceBase):
         #账户登录service
        @rpc(Unicode,Unicode,Unicode,Unicode,Unicode,_returns=Iterable(Unicode))
        def accountLogin(self,accountID, password , brokerID ,tdAddress, mdAddress ):
             from processingTesting import traderProcess
             # 还没有加先判断是否该账户以及启动登录

             accountID = accountID.encode('utf-8')
             if accountID in Process_names.keys():
                 yield "have logined!!"
             else:
                Process_names[accountID] = traderProcess(accountID)
             
             # 启动登录 
                Process_names[accountID].accountLogin(q,accountID.encode('utf-8') , password.encode('utf-8')  , brokerID.encode('utf-8')  ,tdAddress.encode('utf-8') , mdAddress.encode('utf-8') )
             # 这里直接返回登录成功  事实上要根据回调进行判断 准备在ctpgateway里面修改
             # 因为没有监听登录事件 所以这里直接根据账户信息判断是否登陆成功
                accountDict = q.get()
            # id = accountDict.keys()[0].split('.')[1] # 去掉CTP
                if accountDict and accountDict.keys()[0].split('.')[1] ==accountID :

                      yield '%s' % (accountID)
                else :
                    yield "please wait"
        # 返回账户动态权益
        @rpc(Unicode,_returns=Iterable(Unicode))
        def pushAccountInfo(self,accountID):
            accountID = accountID.encode('utf-8')
            Process_names[accountID].accountInfo(q)
            num = q.get() 
            # webservice 的数据类型必须是unicode 不能是字典
            if num and str(type(num.values()[0]))!= "<class 'vnpy.trader.vtEngine.PositionDetail'>":
                
                accountID = num.keys()[0]
                # 数值相关
                preBalance = getattr(num[accountID],'preBalance')           # 昨日账户结算净值
                balance = getattr(num[accountID],'balance')              # 账户净值
                available = getattr(num[accountID],'available')            # 可用资金
                commission = getattr(num[accountID],'commission')           # 今日手续费
                margin = getattr(num[accountID],'margin')               # 保证金占用
                closeProfit = getattr(num[accountID],'closeProfit')          # 平仓盈亏
                positionProfit = getattr(num[accountID],'positionProfit')       # 持仓盈亏
                yield accountID
                # yield 'the balance of accountID  %s  is  %s.' % (accountID, balance)
                # yield 'the margin of accountID  %s  is  %s.' % (accountID, margin)
                # yield 'the available of accountID  %s  is  %s.' % (accountID, available)
                # yield 'the commission of accountID  %s  is  %s.' % (accountID, commission)
                # yield 'the closeProfit of accountID  %s  is  %s.' % (accountID, closeProfit)
                # yield 'the positionProfit of accountID  %s  is  %s.' % (accountID, positionProfit)
                # yield 'the preBalance of accountID  %s  is  %s.' % (accountID, preBalance)
                yield '%s' % (balance)
                yield '%s' % ( margin)
                yield ' %s' % ( available)
                yield '%s' % (commission)
                yield ' %s' % (closeProfit)
                yield ' %s' % (positionProfit)
                yield ' %s' % (preBalance)
            else :
                yield  "please wait"
                
      # 定义一个启动策略的service
        @rpc(Unicode,Unicode,_returns=Iterable(Unicode))
        def strategyStart(self,accountID,name):
            Process_names[accountID].strategyStart(name) 
            yield 'Strategy %s of %s start successful!' % (name,accountID)
            
       # 定义一个返回策略参数的service
        @rpc(Unicode,Unicode,_returns=Iterable(Unicode))
        def pushStrategyVar(self ,accountID , name):
            accountID = accountID.encode('utf-8')
            Process_names[accountID].putStrategyMsg(name,q)
            vara = q.get()
            if vara and str(type(vara.values()[0]))!= "<class 'vnpy.trader.vtEngine.PositionDetail'>" and str(type(vara.values()[0]))!= "<class 'vnpy.trader.vtObject.VtAccountData'>":            
                for key,value in vara.items(): 
                       yield '{%s : %s}' %(key , value)
            else :
                yield 'no message'

      # 定义一个停止策略的service
        @rpc(Unicode,Unicode,_returns=Iterable(Unicode))
        def strategyStop(self ,accountID,name):
            accountID = accountID.encode('utf-8')
            Process_names[accountID].strategyStop(name)
            yield 'Strategy %s of accountID stop successful!' % (name,accountID)

       # 定义一个返回持仓信息的service
        @rpc(Unicode,_returns=Iterable(Unicode))
        def positionInfo(self ,accountID):
            accountID = accountID.encode('utf-8')
            Process_names[accountID].positionInfo(q)
            info = q.get()
            if info.values():
               if str(type(info.values()[0])) == "<class 'vnpy.trader.vtObject.VtAccountData'>" :

                  yield "please wait" 
               else :
                  for key,value in info.items(): 
                      vtSymbol = getattr(value,'vtSymbol')
                      exchange = getattr(value,'exchange')
                      name = getattr(value,'name')
                      longPos = getattr(value,'longPos')    
                      longYd = getattr(value,'longYd')
                      longTd = getattr(value,'longTd')
                      shortPos = getattr(value,'shortPos')
                      shortYd = getattr(value,'shortYd')                        
                      shortTd = getattr(value,'shortTd') 
                      # yield 'the vtSymbol of  %s  is  %s' % (vtSymbol, vtSymbol)
                      # yield 'the exchange of  %s  is  %s' % (vtSymbol, exchange)
                      # #yield 'the name of   %s  is  %s.' % (vtSymbol, name.decode('utf8').encode('gb2312'))
                      # yield 'the longPos of  %s  is  %s' % (vtSymbol, longPos)
                      # yield 'the longYd of  %s  is  %s' % (vtSymbol, longYd)
                      # yield 'the longTd of  %s  is  %s' % (vtSymbol, longTd)
                      # yield 'the shortPos of  %s  is  %s' % (vtSymbol, shortPos)
                      # yield 'the shortYd of  %s  is  %s' % (vtSymbol, shortYd)
                      # yield 'the shortTd of  %s  is  %s' % (vtSymbol, shortTd)
                      yield '%s' % (accountID)
                      yield '%s' % ( vtSymbol)
                      yield '%s' % ( exchange)
                      # yield 'the name of   %s  is  %s.' % (vtSymbol, name.decode('utf8').encode('gb2312'))
                      yield '%s' % ( longPos)
                      yield '%s' % (longYd)
                      yield '%s' % (longTd)
                      yield '%s' % ( shortPos)
                      yield '%s' % (shortYd)
                      yield '%s' % (shortTd)

               # step2: Glue the service definition, input and output protocols
            else:
                yield '%s has nothing' % (accountID)
soap_app = Application([TradeInfoService], 'spyne.examples.hello.soap',
                       in_protocol=Soap11(validator='lxml'),
                       out_protocol=Soap11())
 
# step3: Wrap the Spyne application with its wsgi wrapper
wsgi_app = WsgiApplication(soap_app)
 
if __name__ == '__main__':
    
    #from processingTesting import traderProcess
    #fileName_1 = 'CTP_connect_F.json'
    #fileName_2 = "CTP_connect_other_F.json"
        
    #p1 = traderProcess(fileName_1) 
    #p1.daemon = True
    #p1.runChildProcess(q)

    #p2 = traderProcess(fileName_2) 
    #p2.daemon = True
    #p2.runChildProcess(q)     
        
    import logging
    
    from wsgiref.simple_server import make_server
   
    # configure the python logger to show debugging output
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('spyne.protocol.xml').setLevel(logging.DEBUG)
 
    logging.info("listening to http://127.0.0.1:8000")
    logging.info("wsdl is at: http://localhost:8000/?wsdl")
 
    # step4:Deploying the service using Soap via Wsgi
    # register the WSGI application as the handler to the wsgi server, and run the http server
    server = make_server('127.0.0.1', 8000, wsgi_app)
    server.serve_forever()