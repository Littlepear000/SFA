"""
5c -- Contribution of the sub-items of other identified debt-creating flows (h5 = hierarchy 5)
    Run by hand | no API, no network

Breakdown (each sub-line of h5 is put in an item BY ITS LABEL, not by its number):
            Privatization            label matches ITEM_PATTERNS["Privatization"]
            Contingent liabilities   label matches ITEM_PATTERNS["Contingent liabilities"]
            Debt relief              label matches ITEM_PATTERNS["Debt relief"]
            Asset accumulation       label matches ITEM_PATTERNS["Asset accumulation"] (deposits, liquid /
                                     financial assets acquired or drawn down)
            Other                    = h5 - the four items above   -> every row adds up to h5
                                       (all other sub-lines, plus any part of h5 a report did not break down)
Why by label: the numbers 5.1, 5.2, ... are only the position of the line in that report's table and differ
between DSA templates (5.3 is "Debt relief" in the LIC DSF but "Other transactions" in newer MAC tables).
Sheet 5c_sublines has every sub-line with the new column `category` (the item its label was matched to);
sheet 5c_labels summarises it by label, so the keyword rules can be checked.

Part 1 -- data
    1. Read the final CSV: h5 and its direct sub-lines (5.1, 5.2, ...), the year each value is FOR.
    2. Put every sub-line in a category by its label (new column `category`, written to sheet 5c_sublines).
    3. One row per report and year: h5, Privatization, Contingent liabilities, Debt relief, Asset accumulation,
       Other.
    4. One row per country and year: AVERAGE over the reports of that country-year.
    5. Country group (AE / EM / LIC) from raw/country_codes_dummy: name -> IFS code -> income.
    6. Per group (All, AE, EM, LIC), all years pooled: each item's share of the gross flows
       = sum of |item| / sum over the five items of sum of |item|  (sign does not matter).
    7. Write the sheets 5c_* into output/analysis/5_other_identified_flows/5_other_identified_flows_analysis.xlsx
       (the 5a / 5b sheets in the same workbook are kept).
Part 2 -- chart
    100% stacked horizontal bars: share of gross flows by item, one bar per group. Saved as PNG and pasted
    into sheet 5c_chart.

Usage
    python 5c_h5_contribution.py      (edit the settings below first if needed)
"""
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook, Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ---- paths: this file sits in SFA/code; shared helpers (core.py, check_coverage_database.py) are there too
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from core import ALL_HIERARCHIES, load_rows, normalize_country   # noqa: E402
from check_coverage_database import country_key                   # noqa: E402

# ============================================================================ settings
FINAL_CSV = ROOT / "output" / "final" / "final_all_batches_with_gapfill_20261028.csv"
CODES_XLSX = ROOT / "raw" / "country_codes_dummy" / "Country Codes.xlsx"     # sheet name_to_code
DUMMY_XLSX = ROOT / "raw" / "country_codes_dummy" / "Dummy_20260115.xlsx"     # column income = AE / EM / LIC

YEARS = (2001, 2024)                                   # years kept (year the value is for)
TOTAL_ID = "5"                                         # h5 total; its direct sub-lines are 5.1, 5.2, ...

# Sub-line label -> category (case-insensitive regular expressions; checked in this order, first match wins;
# no match -> Other). Privatization comes first so combined lines like "Privatization/Drawdown of Deposits"
# count as privatization.
# EXCLUDE is applied on top: template placeholders such as "Please specify (1) (e.g., drawdown of deposits)"
# or "Other (specify, e.g. bank recapitalization)" say nothing about what was filled in, so they stay in Other.
EXCLUDE = r"e\.g\.?,?\s*(?:privati|contingent|debt relief|drawdown of deposit|deposit)"
ITEM_PATTERNS = {
    "Privatization": r"privati",
    "Contingent liabilities": r"contingent|implicit liabilit|implicit or contingent",
    "Debt relief": r"debt relief|hipc|mdri",
    "Asset accumulation": r"asset accum|accumulation of|liquid asset|deposit|financial asset",
}

GROUPS = ["All", "AE", "EM", "LIC"]                    # "All" = every country, classified or not
GROUP_NAMES = {"All": "All countries", "AE": "Advanced economies", "EM": "Emerging markets",
               "LIC": "Low-income countries"}

# Names in the final CSV that are not in name_to_code -> IFS code
NAME_ALIASES = {"republic of congo": 634, "curaçao and sint maarten": 354}

OUT_DIR = ROOT / "output" / "analysis" / "5_other_identified_flows"
OUT_XLSX = OUT_DIR / "5_other_identified_flows_analysis.xlsx"
OUT_PNG = OUT_DIR / "5c_share_of_gross_flows.png"
# =====================================================================================

NAMED = list(ITEM_PATTERNS)                            # the four named categories
ITEMS = NAMED + ["Other"]                              # the columns that add up to h5


# #####################################################################################
# PART 1 -- DATA
# #####################################################################################

# ---- 1. read h5 and its direct sub-lines ---------------------------------------------
# load_rows (core.py) gives one row per value with: effective_year (the year the value is for), value_num
# (numeric value; rows without a number are dropped) and country_label (one spelling per country).
rows = load_rows(FINAL_CSV, ALL_HIERARCHIES)
raw = pd.read_csv(FINAL_CSV, dtype=str, usecols=["json_file", "label_verbatim"])
rows["json_file"] = raw.loc[rows.index, "json_file"]           # which report the value comes from
rows["label"] = raw.loc[rows.index, "label_verbatim"]          # the line's label in that report
rows = rows[rows["hierarchy_id"].str.fullmatch(r"5(\.\d+)?", na=False)]   # 5 and 5.x (5.x.y are inside 5.x)
rows = rows[rows["effective_year"].between(*YEARS)]
rows["country_key"] = rows["country"].map(country_key)          # same country matching as the coverage database

# ---- 2. category of every sub-line, by label (new column "category") -----------------
rows["item"] = None
is_sub = rows["hierarchy_id"] != TOTAL_ID
for item, pattern in ITEM_PATTERNS.items():                    # first match wins
    hit = is_sub & rows["item"].isna() & rows["label"].str.contains(pattern, case=False, regex=True, na=False)
    rows.loc[hit, "item"] = item
rows.loc[is_sub & rows["label"].str.contains(EXCLUDE, case=False, regex=True, na=False), "item"] = "Other"
rows.loc[is_sub & rows["item"].isna(), "item"] = "Other"

# the sub-line table with its new category column (written to sheet 5c_sublines)
sublines = (rows[is_sub][["country_label", "effective_year", "json_file", "source_round", "hierarchy_id",
                          "label", "value_num", "item"]]
            .rename(columns={"country_label": "country", "effective_year": "year", "value_num": "value",
                             "item": "category"})
            .sort_values(["country", "year", "json_file", "hierarchy_id"]).reset_index(drop=True))
print("Sub-lines by category:", sublines["category"].value_counts().to_dict())

# ---- 3. one row per report and year -----------------------------------------------------
# A report is identified by json_file + source_round (the same PDF can be in Round 1 and Gap fill).
report_key = ["country_key", "json_file", "source_round", "effective_year"]
total = rows[~is_sub].drop_duplicates(report_key).set_index(report_key)["value_num"].rename("h5")
named = (rows[is_sub & rows["item"].isin(NAMED)]
         .pivot_table(index=report_key, columns="item", values="value_num", aggfunc="sum")
         .reindex(columns=NAMED))
report = total.to_frame().join(named, how="left")              # keep reports that give the h5 total
report[NAMED] = report[NAMED].fillna(0.0)                       # item not in the report -> 0
report["Other"] = report["h5"] - report[NAMED].sum(axis=1)      # everything else in h5 (incl. not broken down)
report = report.reset_index()

# ---- 4. one row per country and year: average over reports -------------------------
country_year = (report.groupby(["country_key", "effective_year"])[["h5"] + ITEMS].mean()
                .join(report.groupby(["country_key", "effective_year"]).size().rename("n_reports"))
                .reset_index().rename(columns={"effective_year": "year"}))
name_of = rows.groupby("country_key")["country_label"].agg(lambda s: s.value_counts().idxmax())
country_year["country"] = country_year["country_key"].map(name_of)

# ---- 5. country group: name -> IFS code -> income ------------------------------------
codes = pd.read_excel(CODES_XLSX, sheet_name="name_to_code")
clean = lambda s: " ".join(str(s).replace("–", "-").replace("—", "-").split()).replace(" - ", "-").casefold()
name_to_ifs = {clean(n): int(c) for n, c in zip(codes["country"], codes["ifscode"]) if pd.notna(c)}
name_to_ifs.update({clean(k): v for k, v in NAME_ALIASES.items()})
dummy = pd.read_excel(DUMMY_XLSX).dropna(subset=["ifscode"]).astype({"ifscode": int}).drop_duplicates("ifscode")
income_of = dict(zip(dummy["ifscode"], dummy["income"]))

country_year["ifscode"] = [name_to_ifs.get(clean(c), name_to_ifs.get(clean(normalize_country(c))))
                           for c in country_year["country"]]
country_year["income"] = country_year["ifscode"].map(income_of)
country_year = country_year[["country", "ifscode", "income", "year", "n_reports", "h5"] + ITEMS]
country_year = country_year.sort_values(["country", "year"]).reset_index(drop=True)
unclassified = sorted(country_year.loc[country_year["income"].isna(), "country"].unique())
print(f"Country-years: {len(country_year):,}, countries: {country_year['country'].nunique()}, "
      f"averaged over 2+ reports: {int((country_year['n_reports'] > 1).sum())}; not classified: {unclassified}")
print("Balance check, max |sum of items - h5|:", (country_year[ITEMS].sum(axis=1) - country_year["h5"]).abs().max())

# ---- 6. share of gross flows by group, all years pooled ------------------------------
share_rows = []
for g in GROUPS:
    members = country_year if g == "All" else country_year[country_year["income"] == g]
    gross = members[ITEMS].abs().sum()                                     # sum of |item|
    row = {"group": g, "n_countries": members["country"].nunique(), "n_country_years": len(members)}
    for item in ITEMS:
        row[f"share_{item}"] = gross[item] / gross.sum()                   # share of gross flows
    for item in ITEMS:
        row[f"gross_{item}"] = gross[item]                                 # sum of |item|, % of GDP
    for item in ITEMS:
        row[f"net_mean_{item}"] = members[item].mean()                     # average with sign
    for item in ITEMS:
        row[f"n_nonzero_{item}"] = int((members[item].abs() > 1e-9).sum())
    share_rows.append(row)
share = pd.DataFrame(share_rows)
print(share[["group"] + [f"share_{i}" for i in ITEMS]].round(3).to_string(index=False))

# label check: every sub-line label, the item it went to, how often it is non-zero, by group
sub = rows[is_sub].copy()
sub["group"] = [income_of.get(name_to_ifs.get(clean(c), name_to_ifs.get(clean(normalize_country(c)))))
                for c in sub["country_label"]]
sub["group"] = sub["group"].fillna("unclassified")
sub = sub.rename(columns={"item": "category"})
labels = (sub.groupby(["category", "label", "group"])["value_num"]
          .agg(n_rows="size", n_nonzero=lambda s: int((s != 0).sum()), gross=lambda s: s.abs().sum())
          .unstack("group", fill_value=0))
labels.columns = [f"{stat}_{grp}" for stat, grp in labels.columns]
labels["gross_total"] = labels[[c for c in labels.columns if c.startswith("gross_")]].sum(axis=1)
labels = labels.reset_index().sort_values(["category", "gross_total"], ascending=[True, False])

# ---- 7. write the Excel sheets ------------------------------------------------------------
notes = [
    "5c -- share of gross flows of the items of other identified debt-creating flows (h5)",
    f"Run: {datetime.now():%Y-%m-%d %H:%M}; source: {FINAL_CSV}",
    f"Years {YEARS[0]}-{YEARS[1]} (year the value is for). Units: % of GDP as reported.",
    "Categories by LABEL of each direct sub-line of h5 (column `category` in 5c_sublines, checked in this order): "
    + "; ".join(f"{k}: /{v}/" for k, v in ITEM_PATTERNS.items())
    + f"; labels matching /{EXCLUDE}/ (template placeholders) and all other labels go to Other.",
    "Other = h5 minus the four named categories, so every row adds up to h5 (it also holds any part of h5 a report "
    "did not break down). A missing category counts as 0. Check the rules in 5c_sublines / 5c_labels.",
    "Several reports for one country-year: average of the reports (n_reports in 5c_country_year).",
    f"Groups: All = every country; AE / EM / LIC = column income of {DUMMY_XLSX.name}. "
    f"Not classified (in All only): {', '.join(unclassified) or 'none'}.",
    "share_X = sum over country-years of |X| / sum over the five items of the same: what drives h5 regardless of sign. "
    "gross_X, net_mean_X (average with sign) and n_nonzero_X are given next to it.",
]
sheets = {"5c_notes": notes, "5c_share": share, "5c_country_year": country_year, "5c_sublines": sublines,
          "5c_labels": labels}

OUT_DIR.mkdir(parents=True, exist_ok=True)
wb = load_workbook(OUT_XLSX) if OUT_XLSX.exists() else Workbook()
for ws in list(wb.worksheets):                       # drop old 5c sheets (and the empty default sheet)
    if ws.title.startswith("5c_") or (ws.title == "Sheet" and ws.max_row == 1):
        wb.remove(ws)
head_font = Font(name="Arial", bold=True, color="FFFFFF")
head_fill = PatternFill("solid", fgColor="1F3864")
for name, content in sheets.items():
    ws = wb.create_sheet(name)
    if isinstance(content, list):                    # notes sheet: one line per row
        for i, line in enumerate(content, 1):
            ws.cell(i, 1, line).font = Font(name="Arial", bold=(i == 1))
            ws.cell(i, 1).alignment = Alignment(wrap_text=True)
        ws.column_dimensions["A"].width = 130
        continue
    for j, col in enumerate(content.columns, 1):     # header
        c = ws.cell(1, j, col)
        c.font, c.fill = head_font, head_fill
        ws.column_dimensions[get_column_letter(j)].width = max(10, min(45, len(str(col)) + 2))
    for i, values in enumerate(content.itertuples(index=False), 2):   # body
        for j, v in enumerate(values, 1):
            if isinstance(v, (float, np.floating)):
                v = None if not np.isfinite(v) else float(v)
            elif isinstance(v, np.integer):
                v = int(v)
            c = ws.cell(i, j, v)
            c.font = Font(name="Arial")
            if isinstance(v, float):
                c.number_format = "0.0%" if str(content.columns[j - 1]).startswith("share") else "0.00"
    ws.freeze_panes = "B2"


# #####################################################################################
# PART 2 -- CHART: share of gross flows by item, one 100% bar per group
# #####################################################################################
colors = {"Privatization": "#2a78d6", "Contingent liabilities": "#eb6834", "Debt relief": "#1baf7a",
          "Asset accumulation": "#eda100", "Other": "#a9a8a2"}
INK, INK2, SURF = "#0b0b0b", "#52514e", "#fcfcfb"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "figure.facecolor": SURF,
                     "axes.facecolor": SURF})

fig, ax = plt.subplots(figsize=(11, 4.4))
y = np.arange(len(GROUPS))
left = np.zeros(len(GROUPS))
for item in ITEMS:
    pct = share.set_index("group").loc[GROUPS, f"share_{item}"].to_numpy() * 100
    ax.barh(y, pct, 0.62, left=left, color=colors[item], edgecolor=SURF, lw=1.5, label=item)
    for yi, (x0, p) in enumerate(zip(left, pct)):        # label segments of at least 5%
        if p >= 5:
            ax.text(x0 + p / 2, yi, f"{p:.0f}%", ha="center", va="center", fontsize=9, color="white")
    left += pct

ax.set_yticks(y, [GROUP_NAMES[g] for g in GROUPS])
ax.invert_yaxis()                                         # "All countries" on top
ax.set_xlim(0, 100)
ax.set_xticks([])
for side in ("top", "right", "bottom", "left"):
    ax.spines[side].set_visible(False)
ax.tick_params(length=0)
ax.legend(ncol=5, frameon=False, fontsize=9, loc="lower left", bbox_to_anchor=(0, 1.0))
fig.suptitle(f"Other identified debt-creating flows (h5): share of gross flows by item, {YEARS[0]}-{YEARS[1]}",
             x=0.01, ha="left", color=INK, fontsize=13, weight="bold")
fig.text(0.01, -0.06,
         "Share = sum of |item| over country-years / sum over the five items. Categories by the label of each "
         "sub-line of h5; Other = h5 minus the four named categories.\n"
         f"Country-year = average of reports. Source: {FINAL_CSV.name}; groups from {DUMMY_XLSX.name}.",
         fontsize=8, color=INK2)
fig.tight_layout(rect=(0, 0, 1, 0.97))
fig.savefig(OUT_PNG, dpi=150, bbox_inches="tight")
plt.close(fig)

# paste the chart into the workbook and save
ws = wb.create_sheet("5c_chart")
img = XLImage(str(OUT_PNG))
scale = 900 / img.width
img.width, img.height = img.width * scale, img.height * scale
ws.add_image(img, "A1")
wb._sheets.sort(key=lambda w: (w.title[:3], 0 if w.title.endswith("notes") else 1 if w.title.endswith("chart") else 2))
wb.save(OUT_XLSX)
print(f"Wrote {OUT_XLSX}\nWrote {OUT_PNG}")
