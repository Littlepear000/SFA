import pandas as pd, country_converter as coco, logging
logging.getLogger("country_converter").setLevel(logging.ERROR)
p=pd.read_csv("panel_h5h6.csv")
names=sorted(p.country.unique())
iso=coco.convert(names,to="ISO3",not_found=None)
m=pd.DataFrame({"country":names,"iso3":iso})
fix={"Kosovo":"XKX","Serbia and Montenegro":"SCG","Curaçao and Sint Maarten":"CUW","Netherlands Antilles":"ANT","Micronesia":"FSM"}
m["iso3"]=[fix.get(c,i) for c,i in zip(m.country,m.iso3)]
bad=m[m.iso3.isna()|m.iso3.astype(str).str.len().ne(3)]
print("unmapped:",bad.to_string())
AE="AND AUS AUT BEL CAN HRV CYP CZE DNK EST FIN FRA DEU GRC HKG ISL IRL ISR ITA JPN KOR LVA LTU LUX MAC MLT NLD NZL NOR PRT PRI SMR SGP SVK SVN ESP SWE CHE TWN GBR USA".split()
LIDC="AFG BGD BEN BTN BFA BDI KHM CMR CAF TCD COM COD COG CIV DJI ERI ETH GMB GHA GIN GNB HTI HND KEN KIR KGZ LAO LSO LBR MDG MWI MLI MRT MDA MOZ MMR NPL NIC NER NGA PNG RWA STP SEN SLE SLB SOM SSD SDN TJK TZA TLS TGO UGA UZB VNM YEM ZMB ZWE".split()
print(len(AE),len(LIDC))
m["group"]=m.iso3.map(lambda x:"AE" if x in AE else ("LIDC" if x in LIDC else "EMMIE"))
# DSA framework most used, as a data-internal cross-check
import sys; sys.path.insert(0,"/mnt/user-data/uploads/SFA/code")
from check_coverage_database import country_key
f=pd.read_csv("/mnt/user-data/uploads/SFA/output/final/final_all_batches_with_gapfill_20261028.csv",usecols=["country","json_file","framework"]).drop_duplicates("json_file")
f["country_key"]=f.country.map(country_key)
fw=f.groupby("country_key").framework.agg(lambda s:s.value_counts().idxmax())
ck=p.drop_duplicates("country")[["country","country_key"]]
m=m.merge(ck,on="country"); m["main_framework"]=m.country_key.map(fw)
print(pd.crosstab(m.group,m.main_framework))
print(m.group.value_counts())
print("LIDC w/o LIC_DSF:",m[(m.group=="LIDC")&(m.main_framework!="LIC_DSF")].country.tolist())
print("EMMIE with LIC_DSF:",m[(m.group=="EMMIE")&(m.main_framework=="LIC_DSF")].country.tolist())
m.to_csv("country_groups.csv",index=False)
g=pd.read_csv("gdp.csv"); print(g.columns.tolist(), g.Year.max())
