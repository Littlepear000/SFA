import pandas as pd, numpy as np, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
C={"AE":"#2a78d6","EMMIE":"#eb6834","LIDC":"#1baf7a"}; INK="#0b0b0b"; INK2="#52514e"; GRID="#e6e5e1"; SURF="#fcfcfb"; FULL="#a9a8a2"
NAMES={"AE":"Advanced economies","EMMIE":"Emerging & middle-income","LIDC":"Low-income developing"}
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":9.5,"axes.edgecolor":GRID,"xtick.color":INK2,"ytick.color":INK2,"axes.labelcolor":INK2,"figure.facecolor":SURF,"axes.facecolor":SURF})
info=pd.read_csv("trim_info.csv").set_index("var")
for v,title,fn in [("h5","Other identified debt-creating flows (h5): full sample vs. 1%/99% trimmed","fig4_h5_full_vs_trimmed.png"),("h6","Residual (h6): full sample vs. 1%/99% trimmed","fig5_h6_full_vs_trimmed.png")]:
    n=pd.read_csv(f"t_{v}_n.csv",index_col=0) if v=="h5" else pd.read_csv("t_h5_n.csv",index_col=0)
    fig,axs=plt.subplots(2,3,figsize=(14,7.2),sharex=True,sharey="row")
    for r,k in enumerate(["simple","weighted"]):
        a=pd.read_csv(f"t_{v}_{k}.csv",index_col=0); b=pd.read_csv(f"t_{v}_{k}_trim.csv",index_col=0)
        for c,g in enumerate(["AE","EMMIE","LIDC"]):
            ax=axs[r,c]; ok=n[g]>=10
            ax.plot(a.index,a[g].where(ok),color=FULL,lw=1.6,ls="--",label="Full sample")
            ax.plot(b.index,b[g].where(ok),color=C[g],lw=2,marker="o",ms=3,label="Trimmed (1%/99%)")
            for s in ["top","right","left"]: ax.spines[s].set_visible(False)
            ax.grid(axis="y",color=GRID,lw=.8); ax.axhline(0,color=INK2,lw=.7); ax.tick_params(length=0)
            if r==0: ax.set_title(NAMES[g],loc="left",color=INK,fontsize=11)
            if c==0: ax.set_ylabel(("Simple average" if k=="simple" else "GDP-weighted (USD)")+"\n% of GDP",color=INK2)
            if r==0: ax.legend(frameon=False,fontsize=8,loc="lower right" if v=="h5" else "upper right")
    lo,hi,nd=info.loc[v,["p1","p99","n_dropped"]]
    fig.suptitle(title,x=.01,ha="left",color=INK,fontsize=13,weight="bold")
    fig.text(.01,-.015,f"Trimmed = country-years with {v} below the pooled 1st percentile ({lo:.1f}) or above the 99th ({hi:.1f}) % of GDP removed ({int(nd)} obs). Points with <10 countries hidden.\nSame panel, groups and GDP weights as figures 1-2.",fontsize=8,color=INK2)
    fig.tight_layout(); fig.savefig(fn,dpi=160,bbox_inches="tight"); plt.close()
print("ok")
