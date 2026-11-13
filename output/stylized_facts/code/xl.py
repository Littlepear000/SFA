import pandas as pd, numpy as np, pickle
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter as L
P=pd.read_csv("panel_full.csv"); P=P[(P.year>=2001)&(P.year<=2024)].sort_values(["group","country","year"])
res=pickle.load(open("tail.pkl","rb")); m=pd.read_csv("country_groups.csv")
F="Arial"; H=Font(name=F,bold=True,color="FFFFFF"); HF=PatternFill("solid",fgColor="1F3864"); B=Font(name=F); BB=Font(name=F,bold=True)
wb=Workbook(); rd=wb.active; rd.title="README"
notes=[("Stylized facts: h5 (other identified debt-creating flows) and h6 (residual)",),
("Source: output/final/final_all_batches_with_gapfill_20261028.csv",),
("Panel: one value per country-year (year the value is for), picked Round 1 > Round 2 > Round 3 > Gap fill, same rule as check_coverage_database.py. 190 countries, 2001-2024 (2025 dropped: only 45 countries).",),
("Units: % of GDP, as reported in the DSA tables.",),
("Groups (static, current classification): AE = IMF WEO advanced economies; LIDC = IMF Fiscal Monitor low-income developing countries; EMMIE = everyone else. Lists typed in from IMF publications, not downloaded - check sheet Country_groups.",),
("GDP weights: World Bank GDP, current USD (NY.GDP.MKTP.CD, via github.com/datasets/gdp), 2023 carried forward to 2024. 11 small economies lack GDP and drop out of weighted averages only.",),
("Tables h5_simple / h5_weighted / h6_simple / h6_weighted are formulas over sheet Panel: edit Panel (e.g. a group) and they update. Check N_obs: LIDC before 2003 and AE around 2005-07 rest on few countries.",),
("Weighted averages are dominated by the US (45% of AE GDP) and China (42% of EMMIE GDP).",),
("Top 5% sheets: pooled 2001-2024 country-years at or above the 95th percentile of the variable; h1/h3/h4 come from the same report as the h5/h6 value; largest_subitem = the 5.x line with the largest absolute value.",)]
for i,(t,) in enumerate(notes,1):
    c=rd.cell(i,1,t); c.font=BB if i==1 else B; c.alignment=Alignment(wrap_text=True)
rd.column_dimensions["A"].width=140
ps=wb.create_sheet("Panel"); cols=["country","iso3","group","main_framework","year","h5","h6","gdp"]
for j,c in enumerate(cols,1): x=ps.cell(1,j,c); x.font=H; x.fill=HF
for i,r in enumerate(P[cols].itertuples(index=False),2):
    for j,v in enumerate(r,1):
        if isinstance(v,float) and np.isnan(v): v=None
        ps.cell(i,j,v).font=B
n=len(P)+1; ps.freeze_panes="A2"
for j,w in zip(range(1,9),[26,7,8,12,7,8,8,18]): ps.column_dimensions[L(j)].width=w
for i in range(2,n+1): ps.cell(i,8).number_format="#,##0"
rng=lambda col:f"Panel!${col}$2:${col}${n}"
G,Y,V5,V6,W=rng("C"),rng("E"),rng("F"),rng("G"),rng("H")
years=list(range(2001,2025)); groups=["AE","EMMIE","LIDC"]
def table(name,title,f):
    s=wb.create_sheet(name); s["A1"]=title; s["A1"].font=BB; s["A2"]="% of GDP"; s["A2"].font=Font(name=F,italic=True,color="52514E")
    for j,h in enumerate(["year"]+groups,1): x=s.cell(4,j,h); x.font=H; x.fill=HF
    for i,y in enumerate(years,5):
        s.cell(i,1,y).font=B
        for j,g in enumerate(groups,2):
            c=s.cell(i,j,f(f"$A{i}",f'{L(j)}$4')); c.font=B; c.number_format="0.00;-0.00;0.00"
    for j,w in zip(range(1,5),[8,11,11,11]): s.column_dimensions[L(j)].width=w
    s.freeze_panes="B5"
for v,V in [("h5",V5),("h6",V6)]:
    vn={"h5":"Other identified debt-creating flows (h5)","h6":"Residual (h6)"}[v]
    table(f"{v}_simple",f"{vn}: simple average by group",lambda y,g,V=V:f'=IFERROR(AVERAGEIFS({V},{G},{g},{Y},{y}),"")')
    table(f"{v}_weighted",f"{vn}: GDP-weighted average (USD) by group",
      lambda y,g,V=V:f'=IFERROR(SUMPRODUCT(({G}={g})*({Y}={y})*({V}<>"")*({W}<>""),{V},{W})/SUMPRODUCT(({G}={g})*({Y}={y})*({V}<>"")*({W}<>""),{W}),"")')
table("N_obs","Number of countries with an h5 value (h6 is nearly identical)",lambda y,g:f'=COUNTIFS({G},{g},{Y},{y},{V5},"<>")')
for r in wb["N_obs"].iter_rows(min_row=5): 
    for c in r[1:]: c.number_format="0"
# medians (values)
s=wb.create_sheet("Medians"); s["A1"]="Medians by group (computed in Python; for comparison with the averages)"; s["A1"].font=BB
hdr=["year"]+[f"h5 {g}" for g in groups]+[f"h6 {g}" for g in groups]
for j,h in enumerate(hdr,1): x=s.cell(3,j,h); x.font=H; x.fill=HF
md5=pd.read_csv("t_h5_median.csv",index_col=0); md6=pd.read_csv("t_h6_median.csv",index_col=0)
for i,y in enumerate(years,4):
    s.cell(i,1,y)
    for j,g in enumerate(groups): s.cell(i,2+j,float(md5.loc[y,g])); s.cell(i,5+j,float(md6.loc[y,g]))
# top 5%
for v in ["h5","h6"]:
    thr,t,_=res[v]; s=wb.create_sheet(f"{v}_top5")
    s["A1"]=f"{v} top 5% country-years (>= {thr:.2f}% of GDP), {len(t)} obs, {t.country.nunique()} countries"; s["A1"].font=BB
    cc=["country","group","year",v,"h1_change_debt","h3_primary_deficit","h4_auto_dynamics","share_of_debt_change","framework","source_round","json_file"]
    if v=="h5": cc[4:4]=["largest_subitem","subitem_value","driver"]
    for j,h in enumerate(cc,1): x=s.cell(3,j,h); x.font=H; x.fill=HF
    for i,r in enumerate(t[cc].itertuples(index=False),4):
        for j,x in enumerate(r,1):
            if isinstance(x,float) and (np.isnan(x) or np.isinf(x)): x=None
            c=s.cell(i,j,x); c.font=B
            if isinstance(x,float): c.number_format="0.00"
    s.freeze_panes="B4"
    for j in range(1,len(cc)+1): s.column_dimensions[L(j)].width=14
    s.column_dimensions["A"].width=24
    if v=="h5": s.column_dimensions["E"].width=45; s.column_dimensions["G"].width=30
cg=wb.create_sheet("Country_groups")
for j,h in enumerate(["country","iso3","group","main_framework"],1): x=cg.cell(1,j,h); x.font=H; x.fill=HF
for i,r in enumerate(m[["country","iso3","group","main_framework"]].itertuples(index=False),2):
    for j,x in enumerate(r,1): cg.cell(i,j,x).font=B
cg.column_dimensions["A"].width=30
wb.save("SFA_stylized_facts_h5_h6_20261028.xlsx")
