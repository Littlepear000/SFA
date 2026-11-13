import pandas as pd, numpy as np
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.comments import Comment
from openpyxl.utils import get_column_letter as L
f="SFA_stylized_facts_h5_h6_20261028.xlsx"; wb=load_workbook(f)
F="Arial"; H=Font(name=F,bold=True,color="FFFFFF"); HF=PatternFill("solid",fgColor="1F3864"); B=Font(name=F); BB=Font(name=F,bold=True)
ps=wb["Panel"]; n=ps.max_row
st=wb.create_sheet("Trim_settings",1)
st["A1"]="Outlier trimming settings (edit the blue cells; trimmed tables update)"; st["A1"].font=BB
rows=[("Lower percentile",0.01),("Upper percentile",0.99)]
for i,(k,v) in enumerate(rows,3):
    st.cell(i,1,k).font=B; c=st.cell(i,2,v); c.font=Font(name=F,color="0000FF"); c.fill=PatternFill("solid",fgColor="FFFF00"); c.number_format="0%"
st["A6"]="Thresholds (% of GDP), pooled 2001-2024"; st["A6"].font=BB
for j,h in enumerate(["","h5","h6"],1):
    x=st.cell(7,j,h or None); 
    if h: x.font=H; x.fill=HF
st["A8"]="Lower cut"; st["A9"]="Upper cut"; st["A10"]="Obs dropped"
for col,src in [("B","F"),("C","G")]:
    R=f"Panel!${src}$2:${src}${n}"
    st[f"{col}8"]=f"=PERCENTILE({R},$B$3)"; st[f"{col}9"]=f"=PERCENTILE({R},$B$4)"
    st[f"{col}10"]=f'=COUNTIF({R},"<"&{col}8)+COUNTIF({R},">"&{col}9)'
    for r in (8,9): st[f"{col}{r}"].number_format="0.00"
for r in range(8,11): st[f"A{r}"].font=B
st["A12"]="Percentile uses Excel PERCENTILE (linear interpolation, same as pandas quantile). Country-years outside [lower, upper] are blanked in Panel columns I-J."
st.column_dimensions["A"].width=24
# trimmed columns in Panel
for j,(h,src,cut) in enumerate([("h5_trim","F","B"),("h6_trim","G","C")],9):
    x=ps.cell(1,j,h); x.font=H; x.fill=HF; ps.column_dimensions[L(j)].width=9
    for i in range(2,n+1):
        ps.cell(i,j,f'=IF({src}{i}="","",IF(AND({src}{i}>=Trim_settings!${cut}$8,{src}{i}<=Trim_settings!${cut}$9),{src}{i},""))').font=B
rng=lambda c:f"Panel!${c}$2:${c}${n}"
G,Y,W=rng("C"),rng("E"),rng("H")
groups=["AE","EMMIE","LIDC"]; years=range(2001,2025)
def table(name,title,f,after):
    s=wb.create_sheet(name,wb.sheetnames.index(after)+1); s["A1"]=title; s["A1"].font=BB
    s["A2"]="% of GDP; outliers trimmed per Trim_settings"; s["A2"].font=Font(name=F,italic=True,color="52514E")
    for j,h in enumerate(["year"]+groups,1): x=s.cell(4,j,h); x.font=H; x.fill=HF
    for i,y in enumerate(years,5):
        s.cell(i,1,y).font=B
        for j,g in enumerate(groups,2):
            c=s.cell(i,j,f(f"$A{i}",f"{L(j)}$4")); c.font=B; c.number_format="0.00;-0.00;0.00"
    for j,w in zip(range(1,5),[8,11,11,11]): s.column_dimensions[L(j)].width=w
    s.freeze_panes="B5"
for v,col in [("h5","I"),("h6","J")]:
    V=rng(col); vn={"h5":"h5 other flows","h6":"h6 residual"}[v]
    table(f"{v}_simple_trim",f"{vn}: simple average, trimmed",lambda y,g,V=V:f'=IFERROR(AVERAGEIFS({V},{G},{g},{Y},{y}),"")',f"{v}_weighted")
    table(f"{v}_weighted_trim",f"{vn}: GDP-weighted average, trimmed",
      lambda y,g,V=V:f'=IFERROR(SUMPRODUCT(({G}={g})*({Y}={y})*ISNUMBER({V})*ISNUMBER({W}),{V},{W})/SUMPRODUCT(({G}={g})*({Y}={y})*ISNUMBER({V})*ISNUMBER({W}),{W}),"")',f"{v}_simple_trim")
# dropped list (at default 1/99)
s=wb.create_sheet("Dropped_1_99")
s["A1"]="Country-years removed at the default 1%/99% cut (static list; does not follow Trim_settings)"; s["A1"].font=BB
cc=["variable","country","group","year","value"]
for j,h in enumerate(cc,1): x=s.cell(3,j,h); x.font=H; x.fill=HF
r=4
for v in ["h5","h6"]:
    d=pd.read_csv(f"dropped_{v}.csv").sort_values(v)
    for t in d.itertuples():
        for j,x in enumerate([v,t.country,t.group,int(t.year),float(getattr(t,v))],1): s.cell(r,j,x).font=B
        r+=1
s.column_dimensions["B"].width=26
rd=wb["README"]; rd.cell(rd.max_row+1,1,"Trimmed version: sheets *_trim drop country-years outside the pooled 1st/99th percentile of each variable (set in Trim_settings; list of removed obs in Dropped_1_99).").font=B
wb.save(f)
