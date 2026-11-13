import pickle,re,pandas as pd
res=pickle.load(open("tail.pkl","rb"))
def cat(l):
    l=str(l).lower()
    if l=="nan": return "No sub-item reported"
    if re.search(r"contingent|bank|recap|financial sector|guarantee|soe|state[- ]owned|bodens",l): return "Contingent liab. / bank recap / SOE"
    if re.search(r"privati",l): return "Privatization"
    if re.search(r"deposit|financial assets|drawdown|net lend|equity|investment fund|asset accum|liquid assets|selected assets|esm|euro ?area loans",l): return "Deposits / asset accumulation"
    if re.search(r"hipc|mdri|relief|forgive|restructur|arrears|haircut",l): return "Debt relief / restructuring / arrears"
    if re.search(r"exchange|valuation|inflation",l): return "Valuation / exchange rate"
    return "Other / unspecified"
t=res["h5"][1]; t["driver"]=t.largest_subitem.map(cat)
print(t.driver.value_counts().to_string())
print(t[t.driver=="Other / unspecified"].largest_subitem.value_counts().head(15).to_string())
print(pd.crosstab(t.driver,t.group))
fuel="DZA AGO AZE BHR BRN TCD COG ECU GNQ GAB IRN IRQ KAZ KWT LBY NGA OMN QAT RUS SAU SSD TLS TTO TKM ARE VEN YEM".split()
P=pd.read_csv("panel_full.csv"); P=P[(P.year>=2001)&(P.year<=2024)]
for v in ["h5","h6"]:
    tt=res[v][1]; s=res[v][2]
    print(v,"fuel share top",round(tt.iso3.isin(fuel).mean(),2),"sample",round(s.iso3.isin(fuel).mean(),2))
pickle.dump(res,open("tail.pkl","wb"))
