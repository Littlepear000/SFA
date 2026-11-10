"""
Build the year tables behind two charts in summary/dsa_extraction_summary.html, as one Excel workbook
to share with colleagues.
    Run by hand | no API, no network | reads CSVs only

Sheets
    Coverage by source   "Country coverage by year and source": every country in the panel, per year,
                         split by where its residual value came from (Round 1 / 2 / 3 / Gap fill) or
                         Unavailable. Read from gapfill_panel_source_breakdown.py's output CSV.
    Reports by pub year  "Staff reports and DSA tables, by publication year": per publication year, how
                         many staff reports there are, how many countries have one, and how many of
                         those have a DSA table in the final data. Computed here from each batch's
                         round1_check_report_summary_*.csv (the full report list) and the merged
                         final CSV.
    Notes                what each column means.

Definitions for "Reports by pub year"
    Year = publication year, from the date in pdf_file_name (not the DSA's last actual year).
    A report is
        "DSA table in final data"  it has Round 1/2/3 rows in FINAL_CSV;
        "Table detected, not used" otherwise, at least one Round 1 run found a DSA table;
        "No DSA table"             otherwise.
    A country with several reports in a year is counted once, under its best report (order above).
    Countries = the panel's country universe (every country in FINAL_CSV, same as the coverage
    chart). Reports for anything outside it (countries that never had a DSA table, cluster reports)
    are left out and listed when the script runs.

Usage
    python check_02_summary_chart_tables.py
    or edit the paths below and run the file from a console.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
if not (HERE / "gapfill_lib_core.py").exists() and (HERE / "code" / "gapfill_lib_core.py").exists():
    HERE = HERE / "code"
sys.path.insert(0, str(HERE))
from check_01_count_pdf_country_years import country_key  # noqa: E402
from gapfill_panel_source_breakdown import country_universe  # noqa: E402

ROOT = HERE.parent
# ---------------------------------------------------------------- settings
FINAL_CSV = ROOT / "output" / "gapfill" / "final_all_batches_with_gapfill_20261028.csv"
COVERAGE_CSV = (ROOT / "output" / "gapfill" / "summary_stats" / "20261028_gapfill_run1_run2"
                / "availability" / "panel_source_breakdown_residual.csv")
BATCHES = ["1999-2005", "2006-2010", "2011-2015", "2016-2020", "2021-2026"]  # folders under output/
OUT_XLSX = ROOT / "summary" / "dsa_extraction_summary_tables.xlsx"


# ================================================================= coverage by source
def coverage_table(path: Path = COVERAGE_CSV) -> pd.DataFrame:
    c = pd.read_csv(path)
    t = pd.DataFrame({
        "Year": c["year"],
        "Countries in panel": c["total_countries"],
        "Round 1": c["n_round1"],
        "Round 2": c["n_round2"],
        "Round 3 (human review)": c["n_round3_human_review"],
        "Gap fill": c["n_gapfill"],
        "Unavailable": c["n_unavailable"],
        "Available": c["n_available"],
    })
    t["Available %"] = (t["Available"] / t["Countries in panel"]).round(3)
    return t


# ================================================================= reports by publication year
def report_list(batches=BATCHES) -> pd.DataFrame:
    """Every report in every batch's Round 1 check summary, with its publication year and country key."""
    frames = []
    for b in batches:
        found = sorted((ROOT / "output" / b).glob("round1_check_*/round1_check_report_summary_*.csv"))
        if not found:
            raise FileNotFoundError(f"no round1_check_report_summary_*.csv under output/{b}")
        d = pd.read_csv(found[-1], dtype=str)
        d["batch"] = b
        frames.append(d)
    inv = pd.concat(frames, ignore_index=True).drop_duplicates("pdf_file_name")
    inv["pub_year"] = inv["pdf_file_name"].str.extract(r"_(\d{4})-\d{2}-\d{2}")[0].astype("Int64")
    prefix = inv["pdf_file_name"].str.replace(r"_\d{4}-\d{2}-\d{2}.*$", "", regex=True)
    inv["country_key"] = prefix.map(lambda s: country_key(s)[0])
    return inv


def reports_table(final_csv: Path = FINAL_CSV, batches=BATCHES) -> pd.DataFrame:
    universe = country_universe(final_csv)
    inv = report_list(batches)

    outside = inv[~inv["country_key"].isin(universe)]
    if len(outside):
        print(f"Left out, not in the {len(universe)}-country panel: {len(outside)} report(s)")
        for name, n in outside["country_key"].value_counts().items():
            print(f"    {name}: {n}")
    inv = inv[inv["country_key"].isin(universe)].copy()

    fin = pd.read_csv(final_csv, usecols=["pdf_file_name", "source_round"], dtype=str)
    in_final = set(fin.loc[fin["source_round"] != "gapfill", "pdf_file_name"])
    inv["dsa_final"] = inv["pdf_file_name"].isin(in_final)
    detected = inv["dsa_final"] | inv["table_found_by_run"].fillna("").str.contains("True")
    # 3 = DSA table in final data, 2 = table detected but not used, 1 = no DSA table
    inv["status"] = 1 + detected.astype(int) + inv["dsa_final"].astype(int)

    rows = []
    for y, g in inv.dropna(subset=["pub_year"]).groupby("pub_year"):
        best = g.groupby("country_key")["status"].max()
        rows.append({
            "Publication year": int(y),
            "Reports": len(g),
            "Reports: DSA table in final data": int((g["status"] == 3).sum()),
            "Reports: table detected, not used": int((g["status"] == 2).sum()),
            "Reports: no DSA table": int((g["status"] == 1).sum()),
            "Countries in panel": len(universe),
            "Countries with a report": len(best),
            "Countries: DSA table in final data": int((best == 3).sum()),
            "Countries: table detected, not used": int((best == 2).sum()),
            "Countries: report, no DSA table": int((best == 1).sum()),
            "Countries: no report this year": len(universe) - len(best),
        })
    t = pd.DataFrame(rows)
    t["Share of countries with a DSA table"] = (t["Countries: DSA table in final data"] / len(universe)).round(3)
    return t


NOTES = [
    ("Sheet", "Column", "Meaning"),
    ("Coverage by source", "Year", "Panel year (the year the value is for)."),
    ("Coverage by source", "Round 1 ... Gap fill",
     "Countries whose residual value (hierarchy_id 6) for that year came from this step. If several "
     "steps cover the same country-year, one is counted, in the order Round 1 > Round 2 > Round 3 > Gap fill."),
    ("Coverage by source", "Unavailable", "Countries with no residual value for that year."),
    ("Coverage by source", "Source", str(COVERAGE_CSV.relative_to(ROOT))),
    ("Reports by pub year", "Publication year",
     "Year the staff report was published (date in the PDF file name). A report published in year P "
     "usually gives the actual value for P-1 or P-2, so this is not the panel year."),
    ("Reports by pub year", "Reports: ...",
     "Number of staff reports. 'DSA table in final data' = the report has Round 1/2/3 rows in the final "
     "file; 'table detected, not used' = a Round 1 run found a DSA table but the report has no rows in "
     "the final file; 'no DSA table' = no run found one."),
    ("Reports by pub year", "Countries: ...",
     "Each panel country counted once per year, under its best report (same order as above). The four "
     "'Countries:' columns add up to 'Countries in panel'."),
    ("Reports by pub year", "Source",
     "Each batch's round1_check_report_summary_*.csv and " + str(FINAL_CSV.relative_to(ROOT))),
]


def write_workbook(sheets: dict, path: Path) -> None:
    from openpyxl.styles import Alignment, Font
    from openpyxl.utils import get_column_letter

    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name, index=False)
            ws = xw.sheets[name]
            ws.freeze_panes = "B2"
            for cell in ws[1]:
                cell.font = Font(bold=True)
                cell.alignment = Alignment(wrap_text=True, vertical="bottom")
            for i, col in enumerate(df.columns, start=1):
                width = 60 if name == "Notes" and i == 3 else min(max(len(str(col)) * 0.6, 9), 22)
                ws.column_dimensions[get_column_letter(i)].width = width
                if col.endswith("%") or col.startswith("Share"):
                    for cell in ws[get_column_letter(i)][1:]:
                        cell.number_format = "0.0%"
                if name == "Notes":
                    for cell in ws[get_column_letter(i)][1:]:
                        cell.alignment = Alignment(wrap_text=True, vertical="top")
            ws.row_dimensions[1].height = 45


def main(final_csv: Path = FINAL_CSV, coverage_csv: Path = COVERAGE_CSV, out_xlsx: Path = OUT_XLSX):
    cov = coverage_table(coverage_csv)
    rep = reports_table(final_csv)
    notes = pd.DataFrame(NOTES[1:], columns=NOTES[0])
    write_workbook({"Coverage by source": cov, "Reports by pub year": rep, "Notes": notes}, Path(out_xlsx))
    print(f"Coverage by source: {len(cov)} years ({cov['Year'].min()}-{cov['Year'].max()})")
    print(f"Reports by pub year: {len(rep)} years, {rep['Reports'].sum():,} reports")
    print(f"Wrote {out_xlsx}")
    return cov, rep


if __name__ == "__main__":
    main()
