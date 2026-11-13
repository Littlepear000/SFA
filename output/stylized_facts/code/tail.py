import sys, pandas as pd, numpy as np
sys.path.insert(0,"/mnt/user-data/uploads/SFA/code")
from gapfill_panel_coverage_report import load_rows, ALL_HIERARCHIES
from check_coverage_database import country_key, SOURCE_ORDER
F="/mnt/user-data/uploads/SFA/output/final/final_all_batches_with_gapfill_20261028.csv"
raw=pd.read_csv(F,dtype=str)
df=load_rows(F, ALL_HIERARCHIES)
df["json_file"]=raw.loc[df.index,"json_file"]; df["label"]=raw.loc[df.index,"label_verbatim"]; df["framework"]=raw.loc[df.index,"framework"]
df["country_key"]=df.country.map(country_key)
rank={r:i for i,(r,_) in enumerate(SOURCE_ORDER)}
df["_rank"]=df.source_round.map(rank).fillna(9)
df=df.sort_values("_rank",kind="stable")
P=pd.read_csv("panel_full.csv")
P=P[(P.year>=2001)&(P.year<=2024)]
# chosen row (report) for h5/h6, plus h1,h3,h4 from the SAME report
def pick(h):
    return df[df.hierarchy_id==h].drop_duplicates(["country_key","effective_year"])[["country_key","effective_year","json_file","source_round","framework"]].rename(columns={"effective_year":"year"})
res={}
for v,h in [("h5","5"),("h6","6")]:
    s=P.dropna(subset=[v]); thr=s[v].quantile(.95)
    top=s[s[v]>=thr].merge(pick(h),on=["country_key","year"],how="left")
    # companions from same report & year
    same=df[df.hierarchy_id.isin(["1","3","4"])][["json_file","effective_year","hierarchy_id","value_num"]]
    comp=same.pivot_table(index=["json_file","effective_year"],columns="hierarchy_id",values="value_num",aggfunc="first").reset_index()
    comp.columns=["json_file","year","h1_change_debt","h3_primary_deficit","h4_auto_dynamics"]
    top=top.merge(comp,on=["json_file","year"],how="left")
    if v=="h5":
        ch=df[df.hierarchy_id.str.match(r"^5\.\d+$")][["json_file","effective_year","label","value_num"]].rename(columns={"effective_year":"year"})
        ch=ch.loc[ch.value_num.abs().groupby([ch.json_file,ch.year]).idxmax()]
        top=top.merge(ch.rename(columns={"label":"largest_subitem","value_num":"subitem_value"}),on=["json_file","year"],how="left")
    top["share_of_debt_change"]=top[v]/top.h1_change_debt
    res[v]=(thr,top.sort_values(v,ascending=False),s)
    print(f"\n==== {v}: top5% threshold {thr:.2f}, n={len(top)}, countries={top.country.nunique()}")
    comp_g=pd.DataFrame({"top5":top.group.value_counts(normalize=True),"sample":s.group.value_counts(normalize=True)})
    comp_g["ratio"]=comp_g.top5/comp_g["sample"]; print(comp_g.round(2))
    print("source round top:",top.source_round.value_counts(normalize=True).round(2).to_dict())
    print("source round all:",df[df.hierarchy_id==h].drop_duplicates(["country_key","effective_year"]).source_round.value_counts(normalize=True).round(2).to_dict())
    print("framework top:",top.framework.value_counts().to_dict())
    print("by year:",top.year.value_counts().sort_index().to_dict())
    print("repeat countries:",top.country.value_counts().head(12).to_dict())
    print("median h1 in top:",top.h1_change_debt.median(), " sample median h1? ; median share:",top.share_of_debt_change.median())
    print(top[["country","year","group",v,"h1_change_debt","source_round"]+(["largest_subitem","subitem_value"] if v=="h5" else [])].head(30).to_string())
import pickle; pickle.dump(res,open("tail.pkl","wb"))
# h1 for whole sample
allc=df[df.hierarchy_id=="1"].drop_duplicates(["country_key","effective_year"])
print("sample median h1:",allc.value_num.median())
