import os 
HedgeFilename='vnpy/trader/app/ctaStrategy/HedgeResult.csv'
LastTradeFilename='vnpy/trader/app/ctaStrategy/lastdayDF.csv'
path=os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))))
pathHedge=os.path.join(path,HedgeFilename)   
pathlast = os.path.join(path,LastTradeFilename)   
import numpy as np
import pandas as pd
HedgeResult = pd.read_csv(pathHedge)
print HedgeResult