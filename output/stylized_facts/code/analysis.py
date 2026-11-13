import sys, pandas as pd, numpy as np
sys.path.insert(0,"/mnt/user-data/uploads/SFA/code")
from check_coverage_database import country_key
p=pd.read_csv("panel_h5h6.csv"); m=pd.read_csv("country_groups.csv")
p=p.merge(m[["country","iso3","group","main_framework"]],on="country",how="left")
g=pd.read_csv("gdp.csv").rename(columns={"Country Code":"iso3","Year":"year","Value":"gdp"})[["iso3","year","gdp"]]
g["iso3"]=g.iso3.replace({})
# carry 2023 GDP forward to 2024-25
last=g[g.year==g.year.max()]
ext=pd.concat([last.assign(year=y) for y in (2024,2025)])
g=pd.concat([g,ext])
p=p.merge(g,on=["iso3","year"],how="left")
print("GDP missing country-years:",p.gdp.isna().sum(), sorted(p[p.gdp.isna()].country.unique()))
p.to_csv("panel_full.csv",index=False)
T=p[(p.year>=2001)&(p.year<=2024)]
order=["AE","EMMIE","LIDC"]
def wavg(x,v):
    s=x.dropna(subset=[v,"gdp"]); return np.average(s[v],weights=s.gdp) if len(s) else np.nan
out={}
for v in ["h5","h6"]:
    out[f"{v}_simple"]=T.pivot_table(index="year",columns="group",values=v,aggfunc="mean")[order]
    out[f"{v}_median"]=T.pivot_table(index="year",columns="group",values=v,aggfunc="median")[order]
    out[f"{v}_weighted"]=T.groupby(["year","group"]).apply(lambda x:wavg(x,v),include_groups=False).unstack()[order]
    out[f"{v}_n"]=T.dropna(subset=[v]).pivot_table(index="year",columns="group",values=v,aggfunc="count")[order]
for k,d in out.items(): d.to_csv(f"t_{k}.csv")
pd.set_option("display.width",200)
for k in ["h5_simple","h5_weighted","h6_simple","h6_weighted","h5_median","h6_median","h5_n"]:
    print(k); print(out[k].round(2).T.to_string())
# who dominates weights
for grp in order:
    s=T[T.group==grp].dropna(subset=["gdp"]).groupby("country").gdp.sum(); print(grp,(s/s.sum()).nlargest(4).round(2).to_dict())
