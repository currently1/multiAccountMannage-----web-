def hedgeResult(self,df=None):
        import numpy as np

        if df is None:
            df = self.calculateDailyResult()

        df.to_excel('resultsDF.xlsx')



        spot=self.strategy.spot
        future=self.strategy.future
        spotvol=self.strategy.Qs
        period=self.strategy.period
        rF=self.strategy.rF
        rS=self.strategy.rS
        hr=self.strategy.hedgeDF
        hr=(hr.reindex(future.index).fillna(method="ffill")).dropna()
        num=self.strategy.num
        num_unit=self.strategy.num_unit
        numDF=pd.concat([num,num_unit],axis=1)
        numDF.columns=["OPT","Unit"]
        numDF=(numDF.reindex(future.index).fillna(method="ffill")).dropna()
        df=df.iloc[(len(df)-len(hr)-2):,:]
        spotposition=spot*spotvol
        self.capital=spotposition[hr.index[0]]

        if self.strategy.direction=='LongHedging':
            rHedged=(-rS+hr*rF).dropna()/period
            rUnit=(-rS[hr.index]+rF[hr.index]).dropna()/period
            rUnhedged=-rS[hr.index]/period

        elif self.strategy.direction=='ShortHedging':
            rHedged=(rS-hr*rF).dropna()/period
            rUnit=(rS[hr.index]-rF[hr.index]).dropna()/period
            rUnhedged=rS[hr.index]/period

        returnDF=pd.concat([rHedged,rUnit,rUnhedged],axis=1)
        returnDF.columns=["OPT","Unit","Unhedged"]
        nvOPT=rHedged.shift(1).fillna(0).cumsum()+1
        nvUnit=rUnit.shift(1).fillna(0).cumsum()+1
        nvUnhedged=rUnhedged.shift(1).fillna(0).cumsum()+1
        nvDF=pd.concat([nvOPT,nvUnit,nvUnhedged],axis=1)
        nvDF.columns=["OPT","Unit","Unhedged"]
        pnlOPT=rHedged*spotposition.shift(1)[hr.index[0]]
        pnlUnit=rUnit*spotposition.shift(1)[hr.index[0]]
        pnlUnhedged=rUnhedged*spotposition.shift(1)[hr.index[0]]
        pnlDF=pd.concat([pnlOPT,pnlUnit,pnlUnhedged],axis=1)
        pnlDF.columns=["OPT","Unit","Unhedged"]
        positionDF=pnlDF.cumsum()+self.capital
        varDF=pd.DataFrame([],columns=["OPT","Unit","Unhedged"],index=[1,5,10])
        for dd in varDF.index:
            varDF.loc[dd,:]=pnlDF.apply(lambda x :np.percentile(x,5))*np.sqrt(dd)
        marginDF=positionDF[["OPT","Unit"]]*self.marginrate
        self.drawLine("NetValue",nvDF)
        self.drawBar("Var",varDF)
        self.drawBar("ContractVol",numDF)
        self.drawLine("Margin",marginDF)

        resultDict={}
        for case in nvDF.columns:
            d={}
            d["FirtTradeDate"]=nvDF.index[0]
            d["LastTradeDate"]=nvDF.index[-1]
            d["ProfitDays"]= len(returnDF[returnDF[case] > 0])
            d["LossDays"]= len(returnDF[returnDF[case] < 0])
            d["AnnualReturn"]=(nvDF.loc[nvDF.index[-1],case]-1)/len(nvDF)*250
            d["AnnualVol"]=(returnDF[case]*period).std()*np.sqrt(250/period)
            resultDict[case]=d

        lastdayDict={}
        for key in df.columns:
            lastdayDict[key]=df[key][-1]

        print resultDict
        print lastdayDict
