import pandas as pd, numpy as np, pickle, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
C={"AE":"#2a78d6","EMMIE":"#eb6834","LIDC":"#1baf7a"}; INK="#0b0b0b"; INK2="#52514e"; GRID="#e6e5e1"; SURF="#fcfcfb"
NAMES={"AE":"Advanced economies","EMMIE":"Emerging & middle-income","LIDC":"Low-income developing"}
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10,"axes.edgecolor":GRID,"axes.labelcolor":INK2,"xtick.color":INK2,"ytick.color":INK2,"figure.facecolor":SURF,"axes.facecolor":SURF})
def style(ax):
    for s in ["top","right","left"]: ax.spines[s].set_visible(False)
    ax.grid(axis="y",color=GRID,lw=.8); ax.axhline(0,color=INK2,lw=.8); ax.tick_params(length=0)
def trend(v,title,fname):
    fig,axs=plt.subplots(1,2,figsize=(13,4.6),sharey=True)
    n=pd.read_csv(f"t_{v}_n.csv",index_col=0)
    for ax,kind,sub in zip(axs,["simple","weighted"],["Simple average","GDP-weighted average (USD)"]):
        d=pd.read_csv(f"t_{v}_{kind}.csv",index_col=0)
        for g in ["AE","EMMIE","LIDC"]:
            y=d[g].where(n[g]>=10)
            ax.plot(d.index,y,color=C[g],lw=2,marker="o",ms=3.5,label=NAMES[g])
        style(ax); ax.set_title(sub,loc="left",color=INK,fontsize=11)
        for x0,x1 in [(2008,2009),(2020,2020)]: ax.axvspan(x0-.5,x1+.5,color="#000",alpha=.04,lw=0)
    axs[0].set_ylabel("% of GDP")
    axs[0].legend(frameon=False,loc="lower right",fontsize=9)
    fig.suptitle(title,x=.01,ha="left",color=INK,fontsize=13,weight="bold")
    fig.text(.01,-.02,"Country-year panel 2001-2024 from final_all_batches_with_gapfill_20261028 (Round 1 > 2 > 3 > gap fill). Points with <10 countries hidden. Shaded: 2008-09, 2020.\nGDP weights: World Bank GDP current USD (2023 carried to 2024). Groups: IMF AE / EMMIE / LIDC.",fontsize=8,color=INK2)
    fig.tight_layout(); fig.savefig(fname,dpi=160,bbox_inches="tight"); plt.close()
trend("h5","Other identified debt-creating flows (h5) by country group","fig1_h5_trend.png")
trend("h6","Residual (h6) by country group","fig2_h6_trend.png")
# fig3: tail anatomy
res=pickle.load(open("tail.pkl","rb"))
fuel="DZA AGO AZE BHR BRN TCD COG ECU GNQ GAB IRN IRQ KAZ KWT LBY NGA OMN QAT RUS SAU SSD TLS TTO TKM ARE VEN YEM".split()
fig,axs=plt.subplots(2,2,figsize=(13,8.6))
# (a) over-representation
ax=axs[0,0]; cats=["AE","EMMIE","LIDC","Fuel exporters","Gap-fill rows"]
x=np.arange(len(cats)); w=.36
for i,(v,lab,col) in enumerate([("h5","h5 other flows","#2a78d6"),("h6","h6 residual","#eb6834")]):
    thr,top,s=res[v]
    import pandas as pd
    allrows=pd.read_csv("panel_full.csv")
    src=top.source_round.eq("gapfill").mean()
    base_src={"h5":.29,"h6":.29}[v]
    r=[top.group.eq(g).mean()/s.group.eq(g).mean() for g in ["AE","EMMIE","LIDC"]]+[top.iso3.isin(fuel).mean()/s.iso3.isin(fuel).mean(), src/base_src]
    b=ax.bar(x+(i-.5)*w,r,w-.04,color=col,label=lab)
    for xi,ri in zip(x+(i-.5)*w,r): ax.text(xi,ri+.04,f"{ri:.1f}x",ha="center",fontsize=8,color=INK2)
ax.axhline(1,color=INK2,lw=1,ls="--"); ax.set_xticks(x,cats,fontsize=9); style(ax); ax.grid(False)
ax.set_title("(a) Over-representation in the top 5%  (share in top 5% / share in sample)",loc="left",color=INK,fontsize=10.5); ax.legend(frameon=False,fontsize=9)
# (b) h5 drivers
ax=axs[0,1]; t=res["h5"][1]; dc=pd.crosstab(t.driver,t.group).reindex(columns=["AE","EMMIE","LIDC"],fill_value=0)
dc=dc.loc[dc.sum(1).sort_values().index]; left=np.zeros(len(dc))
for g in ["AE","EMMIE","LIDC"]:
    ax.barh(dc.index,dc[g],left=left,color=C[g],height=.62,label=NAMES[g],edgecolor=SURF,lw=2); left+=dc[g].values
for yi,tot in enumerate(left): ax.text(tot+.8,yi,str(int(tot)),va="center",fontsize=8,color=INK2)
for s_ in ["top","right","bottom"]: ax.spines[s_].set_visible(False)
ax.tick_params(length=0); ax.set_xticks([]); ax.legend(frameon=False,fontsize=8,loc="lower right")
ax.set_title("(b) h5 top 5%: what is the largest sub-item?  (count of country-years)",loc="left",color=INK,fontsize=10.5)
# (c,d) by year
for ax,v,ttl in [(axs[1,0],"h5","(c) h5 top-5% cases by year"),(axs[1,1],"h6","(d) h6 top-5% cases by year")]:
    t=res[v][1]; ct=pd.crosstab(t.year,t.group).reindex(range(2001,2025),fill_value=0).reindex(columns=["AE","EMMIE","LIDC"],fill_value=0)
    bot=np.zeros(len(ct))
    for g in ["AE","EMMIE","LIDC"]:
        ax.bar(ct.index,ct[g],bottom=bot,color=C[g],width=.75,edgecolor=SURF,lw=1.5,label=NAMES[g]); bot+=ct[g].values
    style(ax); ax.set_title(ttl+f"  (threshold {res[v][0]:.1f}% of GDP)",loc="left",color=INK,fontsize=10.5)
axs[1,0].legend(frameon=False,fontsize=8,loc="upper left")
fig.suptitle("Anatomy of the top 5% country-years",x=.01,ha="left",color=INK,fontsize=13,weight="bold")
fig.tight_layout(); fig.savefig("fig3_top5_anatomy.png",dpi=160,bbox_inches="tight"); plt.close()
print("ok")
