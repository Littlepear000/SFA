import sys, pandas as pd, numpy as np
sys.path.insert(0, "/mnt/user-data/uploads/SFA/code")
from gapfill_panel_coverage_report import load_rows
F="/mnt/user-data/uploads/SFA/output/final/final_all_batches_with_gapfill_20261028.csv"
df=load_rows(F, {"5","6"})
from check_coverage_database import country_key, SOURCE_ORDER
df["country_key"]=df["country"].map(country_key)
rank={r:i for i,(r,_) in enumerate(SOURCE_ORDER)}
df["_rank"]=df["source_round"].map(rank).fillna(len(rank))
print("rows",len(df), "dup groups", df.duplicated(["hierarchy_id","country_key","effective_year"]).sum())
d=df.sort_values("_rank",kind="stable").drop_duplicates(["hierarchy_id","country_key","effective_year"])
lab=df.groupby("country_key")["country_label"].agg(lambda s:s.value_counts().idxmax())
p=d.pivot_table(index=["country_key","effective_year"],columns="hierarchy_id",values="value_num",aggfunc="first").reset_index()
p.columns=["country_key","year","h5","h6"]; p["country"]=p.country_key.map(lab)
p.to_csv("panel_h5h6.csv",index=False)
print(p.shape, p.country_key.nunique()); print(p.year.value_counts().sort_index().to_string())
print(p[["h5","h6"]].describe(percentiles=[.01,.05,.5,.95,.99]).to_string())
