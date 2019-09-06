# encoding: UTF-8
from flask import Flask, render_template

import json
from time import sleep
import os
from pandas.core.frame import DataFrame
import numpy as np
app = Flask(__name__)

from client import getStrategyStart , getlogin,getAccountInfo,getPositionInfo,pushStrategyVar
from flask import request,flash,jsonify
from setting import gateway_setting_dict
wsdl_url = "http://localhost:8000/?wsdl"

@app.route('/mydict', methods=['GET', 'POST'])
def mydict():
    print('login all account')
    accountstr = ''
    for id,value in gateway_setting_dict.items():
        accountID = value['accountID']
        password = value['password']
        brokerID = value['brokerID']
        tdAddress = value['tdAddress']
        mdAddress = value['mdAddress']
        a = "'" + str(accountID) + ', '+"'"
        accountstr = a  +accountstr
        info = getlogin(wsdl_url,accountID=accountID,password=password,brokerID=brokerID,tdAddress=tdAddress,mdAddress=mdAddress)

    if request.method == 'POST':
        a = request.form['mydata']
        print(a)
    a = "'" + str(accountID) + "'"
    d = {'name': ',login successful', 'age': accountstr}
    return jsonify(d)

# 查询所有账户
@app.route ('/mytable',methods = ['GET', 'POST'])
def mytable():
    table = []
    table.append(
        ('accountID', 'balance', 'margin', 'available', 'commission', 'closeProfit', 'positionProfit', 'preBalance'))
    for id, value in gateway_setting_dict.items():
        info = getAccountInfo(wsdl_url, accountID=id)
        table.append(info)
    accountInfo = table[1:]
    total = []
    accountInfonew = []
    for i in accountInfo :
         accoutSt = i[1:]
         accountInfonew.append(accoutSt)
    for i in accountInfonew :
         for j in i:
             j = float(j)
    for i in accountInfonew :
          m =0
          temp = []
          for j in i:
             temp.append(float(j))
             if len(total)>6 :
                total[m] =total[m] +temp[m]
             else :
                 total.append(float(j))
             m= m+1
    total.insert(0,'账户信息汇总')
    table.append(total)
    data = json.dumps(table)
    print(data)
    return data

@app.route('/mytable2', methods=['GET', 'POST'])  # 仓位获取
def mytable2():
    table = []
    n = 9
    table.append(
       ('账号','合约代码', '交易所代码', '多单持仓量', '多单上日持仓', '多单今日持仓', '空单持仓量', '空单上日持仓', '空单今日持仓'))
    for id, value in gateway_setting_dict.items():
        info = getPositionInfo(wsdl_url, accountID=id)
        #info_cell =  [info[i:i+n] for i in range(0, len(info), n)]
        if len(info)>9:
            for i in range(0, len(info), n ):
                info_cell = info[i:i+n]
                table.append(info_cell)
        else:
            table.append(info)
    positionInfo = table[1:]
    total = []
    positionInfonew = []
    for i in positionInfo :
       if len(i)>2 :
         accoutSt = i[1:]
         positionInfonew.append(accoutSt)
    # for i in positionInfonew :
    #      for j in i[2:]:
    #          j = float(j)
    df = DataFrame(positionInfonew)
    traindata  = np.array(df[[2, 3, 4, 5, 6, 7]],dtype= np.float)
    traindata = DataFrame(traindata)
    traindata['symbol']=df[0]
    traindata['exchange'] = df[1]
    newdf = traindata.groupby(['symbol','exchange']).sum()

    for index, row in newdf.iterrows():
        totalpositon = row.tolist()
        totalpositon.insert(0,index[1])
        totalpositon.insert(0, index[0])
        totalpositon.insert(0,u'按照标的汇总')
        table.append(totalpositon)


    data = json.dumps(table)
    positionDf = DataFrame(table)
    print(data)
    return data




@app.route('/')
def index():
    return render_template('index.html')


if __name__ == "__main__":

    app.run(host='10.3.135.28',debug=True)
