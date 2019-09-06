# encoding: UTF-8

"""
包含一些开发中常用的函数
"""

import os
import decimal
import json
from datetime import datetime
import pymongo
MAX_NUMBER = 10000000000000
MAX_DECIMAL = 4

#----------------------------------------------------------------------
def safeUnicode(value):
    """检查接口数据潜在的错误，保证转化为的字符串正确"""
    # 检查是数字接近0时会出现的浮点数上限
    if type(value) is int or type(value) is float:
        if value > MAX_NUMBER:
            value = 0
    
    # 检查防止小数点位过多
    if type(value) is float:
        d = decimal.Decimal(str(value))
        if abs(d.as_tuple().exponent) > MAX_DECIMAL:
            value = round(value, ndigits=MAX_DECIMAL)
    
    return unicode(value)

#----------------------------------------------------------------------
def loadMongoSetting():
    """载入MongoDB数据库的配置"""
    fileName = 'VT_setting.json'
    path = os.path.abspath(os.path.dirname(__file__)) 
    fileName = os.path.join(path, fileName)  
    
    try:
        f = file(fileName)
        setting = json.load(f)
        host = setting['mongoHost']
        port = setting['mongoPort']
    except:
        host = '10.3.135.33'
        port = 57012
        
    return host, port

#----------------------------------------------------------------------
def todayDate():
    """获取当前本机电脑时间的日期"""
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)    

if __name__ == '__main__': 
    host, port = loadMongoSetting()
    initData  = []
    dbClient = pymongo.MongoClient(host, port)
    collection = dbClient['tick_DB']['TS_CU_TickDatas']
    dataStartDate ="2016-01-04"
    strategyStartDate = "2016-01-07"
    flt = {'date':{'$gte':dataStartDate,
                    '$lt':strategyStartDate}}        #$gte:大于或等于,$lt:小于
    
    initCursor = collection.find(flt)
    print initCursor
    backtestingData = []
 # 将数据从查询指针中读取出，并生成列表
    for d in initCursor:
                #data = dataClass()
                #data._dict_ = d
                #print d 
                backtestingData.append(d)
    
    import sys
    sys.getsizeof(backtestingData)
