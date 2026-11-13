"""
5a -- Other identified debt-creating flows (h5): year-by-year trend and distribution by income group
    Run by hand | no API, no network | reads the final CSV and the two files in raw/country_codes_dummy

What it does
    1. Builds the country-year panel of one hierarchy (default h5 = other identified flows) from the final
       CSV, with the same rules as check_coverage_database.py: the year a value is FOR (effective year), and
       when several rounds give a value for the same country and year, Round 1 > Round 2 > Round 3 > Gap fill.
    2. Classifies every country:  country name in the final CSV
           -> "Country Codes.xlsx", sheet name_to_code (all name variants -> IFS code)
           -> "Dummy_<date>.xlsx" (one row per IFS code: income = AE / EM / LIC, region, and other dummies)
       Names that do not match are listed in sheet 5a_unmatched; add them to NAME_ALIASES below.
    3. Per year and income group: number of countries, mean, median, standard deviation, percentiles
       (5/25/75/95), min, max, and the share of country-years that are exactly 0 / positive / negative.
    4. Charts (PNG next to the workbook, and pasted into sheet 5a_charts): mean and median by group;
       the distribution (median, 25-75 and 5-95 percentile bands) per group; share of zeros by group.

Output
    OUT_XLSX (default output/analysis/5_other_identified_flows/5_other_identified_flows_analysis.xlsx),
    sheets starting with "5a_". 5b_h5_zero_streaks.py writes its own "5b_" sheets into the same workbook;
    each script only replaces its own sheets, so they can be run in any order.

Usage
    python 5a_h5_by_income_group.py
    or edit the settings below and run the file from a console.

5b_h5_zero_streaks.py imports load_groups() / build_panel() / classify() / write_sheets() from this file,
so the two analyses always use the same panel and the same country classification.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
if not (HERE / "core.py").exists() and (HERE / "code" / "core.py").exists():
    HERE = HERE / "code"
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from core import load_rows  # noqa: E402
from check_coverage_database import SOURCE_ORDER, country_key  # noqa: E402

# ================================================================= settings
FINAL_CSV = ROOT / "output" / "final" / "final_all_batches_with_gapfill_20261028.csv"
CODES_XLSX = ROOT / "raw" / "country_codes_dummy" / "Country Codes.xlsx"
CODES_SHEET = "name_to_code"                 # columns: country, ifscode, iso3, iso2
DUMMY_XLSX = ROOT / "raw" / "country_codes_dummy" / "Dummy_20260115.xlsx"
DUMMY_SHEET = 0                              # first sheet

HIERARCHY_ID = "5"                           # "5" = other identified flows; "6" = residual also works
VAR_LABEL = "Other identified flows (h5)"
YEARS = (2001, 2024)                         # first and last year kept (2025 is still thin: ~45 countries)

GROUP_COL = "income"                         # column of the Dummy file used for the groups
GROUPS = ["AE", "EM", "LIC"]                 # groups shown, in this order (others / unclassified dropped)
GROUP_NAMES = {"AE": "Advanced economies", "EM": "Emerging markets", "LIC": "Low-income countries"}

# Trim outliers before the statistics? None = keep everything; (0.01, 0.99) = drop country-years below the
# pooled 1st / above the 99th percentile of the variable (pooled over all years and groups)
TRIM = None

MIN_N_CHART = 10                             # a group-year with fewer countries is not drawn in the charts

OUT_DIR = ROOT / "output" / "analysis" / "5_other_identified_flows"
OUT_XLSX = OUT_DIR / "5_other_identified_flows_analysis.xlsx"

# Names in the final CSV that are not in name_to_code -> the IFS code to use
NAME_ALIASES = {
    "republic of congo": 634,
    "curaçao and sint maarten": 354,
    "kingdom of the netherlands-curacao and sint maarten": 354,
    "kingdom of the netherlands-curaçao and sint maarten": 354,
}
# ===========================================================================

COLORS = {"AE": "#2a78d6", "EM": "#eb6834", "LIC": "#1baf7a"}
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"


# ---------------------------------------------------------------- classification
def _clean(name) -> str:
    """Spelling-insensitive key for matching names: casefold, one kind of dash, single spaces."""
    s = str(name).strip().replace("’", "'").replace("–", "-").replace("—", "-")
    s = " ".join(s.split())
    return s.replace(" - ", "-").casefold()


def load_groups(codes_xlsx: Path = CODES_XLSX, dummy_xlsx: Path = DUMMY_XLSX) -> tuple[dict, pd.DataFrame]:
    """(name -> IFS code dict, Dummy table indexed by IFS code)."""
    codes = pd.read_excel(codes_xlsx, sheet_name=CODES_SHEET)
    name_to_ifs = {_clean(n): int(c) for n, c in zip(codes["country"], codes["ifscode"]) if pd.notna(c)}
    for k, v in NAME_ALIASES.items():
        name_to_ifs[_clean(k)] = int(v)
    dummy = pd.read_excel(dummy_xlsx, sheet_name=DUMMY_SHEET)
    dummy = dummy.dropna(subset=["ifscode"]).astype({"ifscode": int}).drop_duplicates("ifscode")
    dummy = dummy.rename(columns={"country": "country_dummy"}).set_index("ifscode")
    return name_to_ifs, dummy


def classify(names: pd.Series, name_to_ifs: dict, dummy: pd.DataFrame) -> pd.DataFrame:
    """One row per distinct name: ifscode, iso3 and every Dummy column (NaN when unmatched)."""
    from core import normalize_country
    out = []
    for raw in pd.Series(names).dropna().unique():
        ifs = name_to_ifs.get(_clean(raw))
        if ifs is None:
            ifs = name_to_ifs.get(_clean(normalize_country(str(raw))))
        out.append({"name": raw, "ifscode": ifs})
    out = pd.DataFrame(out)
    return out.merge(dummy, left_on="ifscode", right_index=True, how="left")


# ---------------------------------------------------------------- panel
def build_panel(final_csv: Path = FINAL_CSV, hierarchy_id: str = HIERARCHY_ID, years=YEARS) -> pd.DataFrame:
    """One value per country and effective year (Round 1 > 2 > 3 > Gap fill), plus the source round."""
    df = load_rows(final_csv, {hierarchy_id})
    df["country_key"] = df["country"].map(country_key)
    rank = {r: i for i, (r, _) in enumerate(SOURCE_ORDER)}
    df["_rank"] = df["source_round"].map(rank).fillna(len(rank))
    df = df.sort_values("_rank", kind="stable").drop_duplicates(["country_key", "effective_year"])
    label = df.groupby("country_key")["country_label"].agg(lambda s: s.value_counts().idxmax())
    p = df[["country_key", "effective_year", "value_num", "source_round"]].rename(
        columns={"effective_year": "year", "value_num": "value"})
    p["country"] = p["country_key"].map(label)
    if years:
        p = p[p["year"].between(*years)]
    return p.sort_values(["country", "year"]).reset_index(drop=True)


def panel_with_groups(final_csv: Path = FINAL_CSV, hierarchy_id: str = HIERARCHY_ID, years=YEARS):
    """Panel + classification columns; also returns the table of unmatched / unclassified countries."""
    panel = build_panel(final_csv, hierarchy_id, years)
    name_to_ifs, dummy = load_groups()
    cls = classify(panel["country"], name_to_ifs, dummy).rename(columns={"name": "country"})
    panel = panel.merge(cls, on="country", how="left")
    issues = cls[cls["ifscode"].isna() | cls[GROUP_COL].isna()].copy()
    issues["problem"] = np.where(issues["ifscode"].isna(), "name not in name_to_code (add to NAME_ALIASES)",
                                 f"IFS code has no '{GROUP_COL}' in the Dummy file")
    issues = issues[["country", "ifscode", "problem"]].sort_values("country")
    return panel, issues


# ---------------------------------------------------------------- statistics
def trim(panel: pd.DataFrame, bounds) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not bounds:
        return panel, panel.iloc[0:0]
    lo, hi = panel["value"].quantile(list(bounds))
    keep = panel["value"].between(lo, hi)
    print(f"Trim {bounds}: keep values in [{lo:.2f}, {hi:.2f}], dropped {int((~keep).sum())} country-years")
    return panel[keep], panel[~keep]


def year_group_stats(panel: pd.DataFrame) -> pd.DataFrame:
    def stats(s: pd.Series) -> pd.Series:
        return pd.Series({
            "n_countries": s.size, "mean": s.mean(), "median": s.median(), "std": s.std(),
            "p5": s.quantile(.05), "p25": s.quantile(.25), "p75": s.quantile(.75), "p95": s.quantile(.95),
            "min": s.min(), "max": s.max(),
            "share_zero": (s == 0).mean(), "share_positive": (s > 0).mean(), "share_negative": (s < 0).mean(),
        })
    sub = panel[panel[GROUP_COL].isin(GROUPS)]
    out = sub.groupby(["year", GROUP_COL])["value"].apply(stats).unstack()
    out = out.reset_index().rename(columns={GROUP_COL: "group"})
    out["group"] = pd.Categorical(out["group"], GROUPS, ordered=True)
    out = out.sort_values(["group", "year"]).reset_index(drop=True)
    out["n_countries"] = out["n_countries"].astype(int)
    return out


def wide(stats: pd.DataFrame, col: str) -> pd.DataFrame:
    return stats.pivot(index="year", columns="group", values=col)[GROUPS].reset_index()


# ---------------------------------------------------------------- charts
def make_charts(stats: pd.DataFrame, out_dir: Path, tag: str) -> list[Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9.5, "axes.edgecolor": GRID,
                         "xtick.color": INK2, "ytick.color": INK2, "axes.labelcolor": INK2,
                         "figure.facecolor": SURF, "axes.facecolor": SURF})
    s = stats[stats["n_countries"] >= MIN_N_CHART]
    note = (f"{VAR_LABEL}, % of GDP. Panel {YEARS[0]}-{YEARS[1]} from {Path(FINAL_CSV).name}; "
            f"groups from {Path(DUMMY_XLSX).name} ({GROUP_COL}). Group-years with <{MIN_N_CHART} countries hidden."
            + (f" Trimmed at pooled {TRIM[0]:.0%}/{TRIM[1]:.0%} percentiles." if TRIM else ""))

    def style(ax, zero=True):
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.grid(axis="y", color=GRID, lw=.8)
        ax.tick_params(length=0)
        if zero:
            ax.axhline(0, color=INK2, lw=.7)

    paths = []
    # 1. mean and median
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.5), sharey=True)
    for ax, col, ttl in zip(axs, ["mean", "median"], ["Mean", "Median"]):
        for g in GROUPS:
            d = s[s["group"] == g]
            ax.plot(d["year"], d[col], color=COLORS.get(g), lw=2, marker="o", ms=3, label=GROUP_NAMES.get(g, g))
        style(ax)
        ax.set_title(ttl, loc="left", color=INK, fontsize=11)
    axs[0].set_ylabel("% of GDP")
    axs[0].legend(frameon=False, fontsize=9)
    fig.suptitle(f"{VAR_LABEL}: mean and median by income group", x=.01, ha="left", color=INK,
                 fontsize=13, weight="bold")
    fig.text(.01, -.03, note, fontsize=8, color=INK2)
    fig.tight_layout()
    paths.append(out_dir / f"5a_fig1_mean_median{tag}.png")
    fig.savefig(paths[-1], dpi=150, bbox_inches="tight")
    plt.close(fig)

    # 2. distribution bands per group
    fig, axs = plt.subplots(1, len(GROUPS), figsize=(14, 4.5), sharey=True)
    for ax, g in zip(np.atleast_1d(axs), GROUPS):
        d = s[s["group"] == g]
        c = COLORS.get(g)
        ax.fill_between(d["year"], d["p5"], d["p95"], color=c, alpha=.13, lw=0, label="5th-95th pct")
        ax.fill_between(d["year"], d["p25"], d["p75"], color=c, alpha=.32, lw=0, label="25th-75th pct")
        ax.plot(d["year"], d["median"], color=c, lw=2, label="Median")
        ax.plot(d["year"], d["mean"], color=INK2, lw=1.2, ls="--", label="Mean")
        style(ax)
        ax.set_title(GROUP_NAMES.get(g, g), loc="left", color=INK, fontsize=11)
    np.atleast_1d(axs)[0].set_ylabel("% of GDP")
    np.atleast_1d(axs)[0].legend(frameon=False, fontsize=8, loc="lower left")
    fig.suptitle(f"{VAR_LABEL}: distribution across countries, by year", x=.01, ha="left", color=INK,
                 fontsize=13, weight="bold")
    fig.text(.01, -.03, note, fontsize=8, color=INK2)
    fig.tight_layout()
    paths.append(out_dir / f"5a_fig2_distribution{tag}.png")
    fig.savefig(paths[-1], dpi=150, bbox_inches="tight")
    plt.close(fig)

    # 3. share of zeros
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for g in GROUPS:
        d = s[s["group"] == g]
        ax.plot(d["year"], d["share_zero"] * 100, color=COLORS.get(g), lw=2, marker="o", ms=3,
                label=GROUP_NAMES.get(g, g))
    style(ax, zero=False)
    ax.set_ylim(0, 100)
    ax.set_ylabel("% of countries reporting exactly 0")
    ax.legend(frameon=False, fontsize=9)
    fig.suptitle(f"{VAR_LABEL}: share of countries reporting 0", x=.01, ha="left", color=INK,
                 fontsize=13, weight="bold")
    fig.text(.01, -.05, note, fontsize=7.5, color=INK2, wrap=True)
    fig.tight_layout()
    paths.append(out_dir / f"5a_fig3_share_zero{tag}.png")
    fig.savefig(paths[-1], dpi=150, bbox_inches="tight")
    plt.close(fig)
    return paths


# ---------------------------------------------------------------- Excel
def write_sheets(xlsx: Path, sheets: dict, images: dict | None = None, prefix: str | None = None) -> None:
    """Write {sheet name: DataFrame or list of text lines} into xlsx, replacing only these sheets (and, if
    prefix is given, any older sheet starting with it). Other scripts' sheets in the workbook are kept.
    images: {sheet name: [png paths]} pasted one under another."""
    from openpyxl import Workbook, load_workbook
    from openpyxl.drawing.image import Image as XLImage
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    xlsx.parent.mkdir(parents=True, exist_ok=True)
    wb = load_workbook(xlsx) if xlsx.exists() else Workbook()
    if not xlsx.exists():
        wb.remove(wb.active)
    for ws in list(wb.worksheets):
        if ws.title in sheets or (images and ws.title in images) or (prefix and ws.title.startswith(prefix)):
            wb.remove(ws)
    head_font, head_fill, body = Font(name="Arial", bold=True, color="FFFFFF"), \
        PatternFill("solid", fgColor="1F3864"), Font(name="Arial")
    for name, content in sheets.items():
        ws = wb.create_sheet(name[:31])
        if isinstance(content, list):          # notes
            for i, line in enumerate(content, 1):
                c = ws.cell(i, 1, line)
                c.font = Font(name="Arial", bold=(i == 1))
                c.alignment = Alignment(wrap_text=True, vertical="top")
            ws.column_dimensions["A"].width = 130
            continue
        df = content
        for j, col in enumerate(df.columns, 1):
            c = ws.cell(1, j, str(col))
            c.font, c.fill = head_font, head_fill
        for i, row in enumerate(df.itertuples(index=False), 2):
            for j, v in enumerate(row, 1):
                if isinstance(v, (float, np.floating)) and not np.isfinite(v):
                    v = None
                elif isinstance(v, np.generic):
                    v = v.item()
                c = ws.cell(i, j, v)
                c.font = body
                if isinstance(v, float):
                    c.number_format = "0.0%" if str(df.columns[j - 1]).startswith("share") else "0.00"
        for j, col in enumerate(df.columns, 1):
            width = max([len(str(col))] + [len(str(x)) for x in df.iloc[:200, j - 1].tolist()])
            ws.column_dimensions[get_column_letter(j)].width = min(max(8, width + 2), 45)
        ws.freeze_panes = "B2"
    for name, pngs in (images or {}).items():
        ws = wb.create_sheet(name[:31])
        row = 1
        for p in pngs:
            img = XLImage(str(p))
            scale = 900 / img.width
            img.width, img.height = img.width * scale, img.height * scale
            ws.add_image(img, f"A{row}")
            row += int(img.height / 20) + 2
    # order: 5a_ sheets before 5b_; within a script notes, then charts, then the order written
    def _rank(t):
        return (t[:3], 0 if t.endswith("notes") else 1 if t.endswith("charts") else 2)
    wb._sheets.sort(key=lambda w: _rank(w.title))
    wb.save(xlsx)


# ---------------------------------------------------------------- main
def main() -> None:
    panel, issues = panel_with_groups()
    print(f"Panel: {len(panel):,} country-years, {panel['country'].nunique()} countries, years {YEARS}")
    print("Countries by group:", panel.drop_duplicates("country")[GROUP_COL].fillna("unclassified")
          .value_counts().to_dict())
    if len(issues):
        print("Not classified (see sheet 5a_unmatched):", issues["country"].tolist())
    used, dropped = trim(panel, TRIM)
    stats = year_group_stats(used)
    tag = "" if not TRIM else f"_trim{int(TRIM[0]*100)}_{int(TRIM[1]*100)}"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pngs = make_charts(stats, OUT_DIR, tag)

    overall = used[used[GROUP_COL].isin(GROUPS)].groupby(GROUP_COL)["value"].describe(
        percentiles=[.05, .25, .5, .75, .95]).reindex(GROUPS).reset_index().rename(columns={GROUP_COL: "group"})
    zero = used[used[GROUP_COL].isin(GROUPS)].groupby(GROUP_COL)["value"].apply(lambda s: (s == 0).mean())
    overall["share_zero"] = overall["group"].map(zero)

    notes = [
        f"5a -- {VAR_LABEL}: trend and distribution by {GROUP_COL} group",
        f"Run: {datetime.now():%Y-%m-%d %H:%M}",
        f"Final CSV: {FINAL_CSV}",
        f"Hierarchy id: {HIERARCHY_ID}; years {YEARS[0]}-{YEARS[1]}; one value per country-year "
        "(effective year; Round 1 > Round 2 > Round 3 > Gap fill, same rule as check_coverage_database.py).",
        f"Classification: {Path(CODES_XLSX).name} [{CODES_SHEET}] name -> IFS code -> {Path(DUMMY_XLSX).name} "
        f"column '{GROUP_COL}'. Groups shown: {', '.join(GROUPS)}. Unclassified countries: sheet 5a_unmatched.",
        f"Trim: {TRIM if TRIM else 'none (all values kept)'}"
        + (f"; {len(dropped)} country-years dropped, listed in 5a_trimmed_out." if TRIM else ""),
        "Units: % of GDP as reported in the DSA tables. share_zero = share of countries reporting exactly 0.",
        "Sheets: 5a_stats_long (every statistic, year x group), 5a_mean / 5a_median / 5a_std / 5a_share_zero / "
        "5a_n (year x group), 5a_overall (all years pooled), 5a_panel (the country-year data), 5a_charts.",
    ]
    sheets = {
        "5a_notes": notes,
        "5a_stats_long": stats,
        "5a_mean": wide(stats, "mean"),
        "5a_median": wide(stats, "median"),
        "5a_std": wide(stats, "std"),
        "5a_share_zero": wide(stats, "share_zero"),
        "5a_n": wide(stats, "n_countries"),
        "5a_overall": overall,
        "5a_panel": panel[["country", "ifscode", "isocode", GROUP_COL, "region",
                           "year", "value", "source_round"]].rename(columns={"value": f"h{HIERARCHY_ID}"}),
        "5a_unmatched": issues if len(issues) else pd.DataFrame({"country": ["(none)"]}),
    }
    if TRIM:
        sheets["5a_trimmed_out"] = dropped[["country", GROUP_COL, "year", "value"]]
    write_sheets(OUT_XLSX, sheets, images={"5a_charts": pngs}, prefix="5a_")
    print(f"Wrote {OUT_XLSX}")
    for p in pngs:
        print(f"Wrote {p}")


if __name__ == "__main__":
    main()
