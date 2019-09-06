gatewayName='CTP'

fileName = gatewayName + '_connect.json'
filePath = getJsonPath(fileName, __file__)   
import json 
print filePath
setting = json.load(f)