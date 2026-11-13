import pandas as pd, numpy as np
P=pd.read_csv("panel_full.csv"); T=P[(P.year>=2001)&(P.year<=2024)].copy()
order=["AE","EMMIE","LIDC"]; info=[]
def wavg(x,v):
    s=x.dropna(subset=[v,"gdp"]); return np.average(s[v],weights=s.gdp) if len(s) else np.nan
for v in ["h5","h6"]:
    lo,hi=T[v].quantile([.01,.99]); keep=T[v].between(lo,hi)
    t=T.copy(); t.loc[~keep,v]=np.nan
    drop=T[T[v].notna()&~keep]
    info.append((v,lo,hi,len(drop)))
    print(v,f"lo={lo:.2f} hi={hi:.2f} dropped={len(drop)}", drop.group.value_counts().to_dict())
    print("  biggest dropped:",drop.reindex(drop[v].abs().sort_values(ascending=False).index)[["country","year",v]].head(8).values.tolist())
    t.pivot_table(index="year",columns="group",values=v,aggfunc="mean")[order].to_csv(f"t_{v}_simple_trim.csv")
    t.groupby(["year","group"]).apply(lambda x:wavg(x,v),include_groups=False).unstack()[order].to_csv(f"t_{v}_weighted_trim.csv")
    drop.to_csv(f"dropped_{v}.csv",index=False)
pd.DataFrame(info,columns=["var","p1","p99","n_dropped"]).to_csv("trim_info.csv",index=False)
for v in ["h5","h6"]:
  for k in ["simple","weighted"]:
    a=pd.read_csv(f"t_{v}_{k}.csv",index_col=0); b=pd.read_csv(f"t_{v}_{k}_trim.csv",index_col=0)
    print(v,k,"full SD by group",a.std().round(2).to_dict(),"trim SD",b.std().round(2).to_dict())
    print("  trim mean over years",b.mean().round(2).to_dict(), "full",a.mean().round(2).to_dict())
