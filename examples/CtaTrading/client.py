#!/usr/bin/env python 
# -*- coding: utf-8 -*-
 
from suds.client import Client  # 导入suds.client 模块下的Client类
from time import sleep  
#wsdl_url = "http://localhost:8000/?wsdl"
wsdl_url = "http://localhost:8000/?wsdl"
from suds.xsd.doctor import ImportDoctor,Import
imp = Import("http://www.w3.org/2001/XMLSchema",location="http://www.w3.org/2001/XMLSchema.xsd")
imp.filter.add("http://WebXml.com.cn/")
doctor=ImportDoctor(imp)

def getPositionInfo(url,accountID):
    client = Client(url,doctor=doctor)                      # 创建一个webservice接口对象
    #client.service.pushLogin()   # 调用这个接口下的getMobileCodeInfo方法，并传入参数
    response = client.service.positionInfo(accountID)
    #req = str(client.last_sent())           # 保存请求报文，因为返回的是一个实例，所以要转换成str
    #response = str(client.last_received())  # 保存返回报文，返回的也是一个实例
    #print req       # 打印请求报文
    print response.string  # 打印返回报文
    return (response.string)
def getAccountInfo(url,accountID):
    client = Client(url,doctor=doctor)                  # 创建一个webservice接口对象,wsdl中没有使用import标签将 http://www.w3.org/2001/XMLSchema命名空间引入
    #client.service.pushLogin()   # 调用这个接口下的getMobileCodeInfo方法，并传入参数
    response = client.service.pushAccountInfo(accountID)
    #req = str(client.last_sent())           # 保存请求报文，因为返回的是一个实例，所以要转换成str
    #response = str(client.last_received())  # 保存返回报文，返回的也是一个实例
    
     #解析返回的XML字符串
    #import xml.etree.ElementTree as ET
    #str_value = ET.fromstring(r)
    #resultCode = str_value.find("resultCode").text  
    
    #print req       # 打印请求报文
    print response.string  # 打印返回报文 list类型
    return response.string
def getlogin(url,accountID, password , brokerID,tdAddress  ,  mdAddress ):
    client = Client(url,doctor=doctor)                       # 创建一个webservice接口对象
    response = client.service.accountLogin(accountID=accountID, password = password,brokerID= brokerID ,tdAddress=tdAddress , mdAddress=mdAddress )   # 调用这个接口下的getMobileCodeInfo方法，并传入参数
    # response = client.service.accountLogin(accountID=accountID, password = "19900809", brokerID = "9999",tdAddress ="tcp://218.202.237.33 :10002" , \
    #              mdAddress ="tcp://218.202.237.33 :10012")   # 调用这个接口下的getMobileCodeInfo方法，并传入参数
    #req = str(client.last_sent())           # 保存请求报文，因为返回的是一个实例，所以要转换成str
    #response = str(client.last_received())  # 保存返回报文，返回的也是一个实例
    #print req       # 打印请求报文
    return  accountID  # 打印返回报文
def getloginout(url):
    client = Client(url,doctor=doctor)                      # 创建一个webservice接口对象
    response = client.service.accountLoginout(accountID="053941")   # 调用这个接口下的getMobileCodeInfo方法，并传入参数
    #req = str(client.last_sent())           # 保存请求报文，因为返回的是一个实例，所以要转换成str
    #response = str(client.last_received())  # 保存返回报文，返回的也是一个实例
    #print req       # 打印请求报文
    print response.string  # 打印返回报文
def getStrategyStart(url):

    client = Client(url,doctor=doctor)                       # 创建一个webservice接口对象
    response = client.service.strategyStart("053941","DualThrust")   # 调用这个接口下的getMobileCodeInfo方法，并传入参数
    #req = str(client.last_sent())           # 保存请求报文，因为返回的是一个实例，所以要转换成str
    #response = str(client.last_received())  # 保存返回报文，返回的也是一个实例
    #print req       # 打印请求报文
    print response.string  # 打印返回报文
    
def getStrategyStop(url):

    client = Client(url,doctor=doctor)                     # 创建一个webservice接口对象
    response = client.service.strategyStop("053941","DualThrust")   # 调用这个接口下的getMobileCodeInfo方法，并传入参数
    #req = str(client.last_sent())           # 保存请求报文，因为返回的是一个实例，所以要转换成str
    #response = str(client.last_received())  # 保存返回报文，返回的也是一个实例
    #print req       # 打印请求报文
    print response.string  # 打印返回报文    
def pushStrategyVar(url):

    client = Client(url,doctor=doctor)                      # 创建一个webservice接口对象
    response = client.service.pushStrategyVar("053941","DualThrust")   # 调用这个接口下的getMobileCodeInfo方法，并传入参数
    #req = str(client.last_sent())           # 保存请求报文，因为返回的是一个实例，所以要转换成str
    #response = str(client.last_received())  # 保存返回报文，返回的也是一个实例
    #print req       # 打印请求报文
    print response.string  # 打印返回报文
if __name__ == '__main__':
    #getlogin(wsdl_url)
    # while True :
    #
    #    getlogin(wsdl_url)
    #    sleep(1)
    getlogin(wsdl_url)
    getAccountInfo(wsdl_url)
    sleep(1)
    getStrategyStart(wsdl_url)
    while True :
        
        pushStrategyVar(wsdl_url)
        sleep(1)   
        getPositionInfo(wsdl_url)
        sleep(1)
    # getStrategyStart(wsdl_url)
    # sleep(1)
    # pushStrategyVar(wsdl_url)
