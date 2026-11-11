"""
Data-coverage database: one row per panel country and year, Yes/No for every piece of data we have.
    Run by hand | no API, no network | reads PDF file names (never opens a PDF) and the merged CSV

Part 1 -- "Coverage" sheet (190 countries x 2001-2025 = 4,750 rows)
    country, year
    has_staff_report   Yes if the country has at least one staff report PUBLISHED that year
    has_dsa_table      Yes if at least one report published that year has a DSA table in the final data
                       (Round 1/2/3 rows in FINAL_CSV)
    h<id>_<name>       one column per hierarchy_id in FINAL_CSV: Yes if the country has a value for it
                       for that year (the year the value is FOR, from any round or Gap fill)
                       e.g. h5_other_identified_flows, h6_residual, h3_1_revenue_and_grants
Every cell after country/year is "Yes" or "No".

Part 2 -- "By year" sheet: per year, the number of panel countries, and how many of them have a staff
    report, a DSA table, and a value for each indicator in ANALYSIS_INDICATORS (default: h5 and h6).

Also an "Indicators" sheet (column name -> hierarchy_id, level, top category, the most common labels,
how many country-years have it) and a "Notes" sheet.

Read this before comparing columns
    - has_staff_report / has_dsa_table go by PUBLICATION year; the h* columns go by the year the value
      is for. A report published in year P usually gives the actual value for P-1 or P-2.
    - Top-level ids (h1-h6) mean the same thing in every DSA table. Sub-level ids (e.g. 5.1, 5.2) are
      numbered by position inside their category, so their meaning can change with the DSA template
      (5.1 is "Privatization receipts" in some tables and "Contingent liabilities" in others). Each
      sub-level column is named after its most common label; the Indicators sheet lists the others.

Where the reports come from (REPORT_SOURCE)
    "pdf_folders"        the raw PDFs in the BATCHES sub-folders of PDF_ROOT (same as check_coverage.py)
    "round1_summaries"   the report list in each batch's round1_check_report_summary_*.csv (works
                         without the PDFs; it is the list of reports that went through extraction)
    Either way, only the panel's countries are counted; regional reports and places outside the panel
    are left out and listed when the script runs.

Usage
    python check_coverage_database.py
    python check_coverage_database.py --report-source round1_summaries
    or edit the settings below and run the file from a console.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
if not (HERE / "check_coverage.py").exists() and (HERE / "code" / "check_coverage.py").exists():
    HERE = HERE / "code"
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from check_coverage import (  # noqa: E402
    BATCHES, NAME_RE, PDF_ROOT, country_key, keep_panel_reports, panel_countries, read_pdfs, write_workbook,
)
from gapfill_panel_coverage_report import ALL_HIERARCHIES, load_rows  # noqa: E402

# ---------------------------------------------------------------- settings
FINAL_CSV = ROOT / "output" / "gapfill" / "final_all_batches_with_gapfill_20261028.csv"
YEARS = (2001, 2025)                      # panel years, one row per country per year
REPORT_SOURCE = "pdf_folders"             # "pdf_folders" or "round1_summaries" (see the docstring)
ANALYSIS_INDICATORS = ["5", "6"]          # hierarchy_ids counted in the "By year" sheet
OUT_XLSX = ROOT / "output" / "coverage" / "coverage_database.xlsx"


# ================================================================= reports
def reports_from_round1_summaries(batches=BATCHES) -> pd.DataFrame:
    """Every report in each batch's Round 1 check summary, in the same shape as read_pdfs()."""
    rows = []
    for b in batches:
        found = sorted((ROOT / "output" / b).glob("round1_check_*/round1_check_report_summary_*.csv"))
        if not found:
            raise FileNotFoundError(f"no round1_check_report_summary_*.csv under output/{b}")
        for name in pd.read_csv(found[-1], dtype=str)["pdf_file_name"].dropna():
            m = NAME_RE.match(name)
            if m:
                rows.append({"pdf_file_name": name, "batch": b, "country_raw": m.group("country"),
                             "country_key": country_key(m.group("country")), "year": int(m.group("year"))})
    return pd.DataFrame(rows).drop_duplicates("pdf_file_name")


def report_country_years(source: str, panel: set) -> set:
    if source == "pdf_folders":
        pdfs = read_pdfs(PDF_ROOT, BATCHES)
    elif source == "round1_summaries":
        pdfs = reports_from_round1_summaries(BATCHES)
    else:
        raise ValueError(f"REPORT_SOURCE must be 'pdf_folders' or 'round1_summaries', got {source!r}")
    pdfs = keep_panel_reports(pdfs, panel)
    print(f"Staff reports ({source}): {len(pdfs):,} PDFs of panel countries")
    return set(zip(pdfs["country_key"], pdfs["year"]))


def dsa_country_years(final: pd.DataFrame) -> set:
    """(country, publication year) of every report with Round 1/2/3 rows in the final data."""
    names = final.loc[final["source_round"] != "gapfill", "pdf_file_name"].dropna().unique()
    out = set()
    for name in names:
        m = NAME_RE.match(name)
        if m:
            out.add((country_key(m.group("country")), int(m.group("year"))))
    return out


# ================================================================= indicators
def _id_sort_key(hid: str):
    return [int(p) if p.isdigit() else 999 for p in str(hid).split(".")]


def _slug(label: str, max_len: int = 40) -> str:
    s = str(label).lower()
    s = re.sub(r"\b\d+/", " ", s)                 # footnote markers like 2/
    s = re.sub(r"\([^)]*\)", " ", s)              # bracketed notes like (4+7+12)
    s = re.sub(r"^\s*\d+\.?\s+", "", s)           # leading line numbers like "12 "
    s = re.sub(r"^\s*(?:of which|o/w)\s*:?\s*", "", s)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    if len(s) > max_len:  # cut at a word boundary
        s = s[:max_len + 1].rsplit("_", 1)[0]
    return s.strip("_") or "item"


def indicator_columns(final: pd.DataFrame) -> pd.DataFrame:
    """One row per hierarchy_id: the column name and what it holds."""
    rows = []
    for hid, g in final.dropna(subset=["hierarchy_id"]).groupby("hierarchy_id"):
        top = g["top_category"].value_counts().index[0]
        labels = g["label_verbatim"].dropna().value_counts()
        level = pd.to_numeric(g["level"], errors="coerce").mode()
        level = int(level.iloc[0]) if len(level) else None
        name = top if "." not in hid else (_slug(labels.index[0]) if len(labels) else "item")
        rows.append({"column": f"h{hid.replace('.', '_')}_{name}", "hierarchy_id": hid, "level": level,
                     "top_category": top, "most_common_labels": " | ".join(labels.index[:3]),
                     "n_rows_in_final_csv": len(g)})
    out = pd.DataFrame(rows)
    return out.iloc[sorted(range(len(out)), key=lambda i: _id_sort_key(out["hierarchy_id"].iloc[i]))]


# ================================================================= build
def yes_no(mask) -> list:
    return ["Yes" if v else "No" for v in mask]


def build(final_csv: Path = FINAL_CSV, years: tuple = YEARS, report_source: str = REPORT_SOURCE):
    final = pd.read_csv(final_csv, usecols=["country", "pdf_file_name", "source_round", "hierarchy_id", "level",
                                            "top_category", "label_verbatim"], dtype=str)
    panel = panel_countries(final_csv)
    values = load_rows(final_csv, ALL_HIERARCHIES)            # rows with a numeric value and a parsed year
    labels = values.groupby("country_key")["country_label"].agg(lambda s: s.value_counts().index[0])
    panel_years = list(range(years[0], years[1] + 1))

    grid = pd.MultiIndex.from_product([sorted(panel, key=lambda k: labels.get(k, k)), panel_years],
                                      names=["country_key", "year"]).to_frame(index=False)
    keys = list(zip(grid["country_key"], grid["year"]))
    reports = report_country_years(report_source, panel)
    dsa = dsa_country_years(final)

    cov = pd.DataFrame({"country": grid["country_key"].map(lambda k: labels.get(k, k)), "year": grid["year"],
                        "has_staff_report": yes_no(k in reports for k in keys),
                        "has_dsa_table": yes_no(k in dsa for k in keys)})
    ind = indicator_columns(final)
    have = {hid: set(zip(g["country_key"], g["effective_year"])) for hid, g in values.groupby("hierarchy_id")}
    for hid, col in zip(ind["hierarchy_id"], ind["column"]):
        cov[col] = yes_no(k in have.get(hid, set()) for k in keys)
    ind["country_years_with_value"] = [int((cov[c] == "Yes").sum()) for c in ind["column"]]

    odd = sum(1 for k in keys if k in dsa and k not in reports)
    if odd:
        print(f"NOTE: {odd} country-year(s) have a DSA table in the final data but no staff report in the "
              f"report list ({report_source}); check whether those PDFs are missing from it")
    return cov, ind


def by_year(cov: pd.DataFrame, ind: pd.DataFrame, analysis=ANALYSIS_INDICATORS) -> pd.DataFrame:
    col_of = dict(zip(ind["hierarchy_id"], ind["column"]))
    missing = [h for h in analysis if h not in col_of]
    if missing:
        raise ValueError(f"ANALYSIS_INDICATORS not in the final data: {missing}")
    g = cov.groupby("year")
    out = pd.DataFrame({"Year": g.size().index, "Countries in panel": g.size().values,
                        "Countries with staff report": g["has_staff_report"].apply(lambda s: (s == "Yes").sum()).values,
                        "Countries with DSA table": g["has_dsa_table"].apply(lambda s: (s == "Yes").sum()).values})
    for h in analysis:
        out[f"Countries with {col_of[h]}"] = g[col_of[h]].apply(lambda s: (s == "Yes").sum()).values
    return out


def notes(report_source: str) -> pd.DataFrame:
    return pd.DataFrame([
        ("Coverage", f"One row per panel country and year ({YEARS[0]}-{YEARS[1]}). Every cell after country/year is Yes or No."),
        ("has_staff_report", "Yes if the country has at least one staff report published that year "
                             f"(source: {report_source}). Regional reports and places outside the panel are left out."),
        ("has_dsa_table", "Yes if at least one report published that year has a DSA table in the final data "
                          f"(Round 1/2/3 rows in {Path(FINAL_CSV).name})."),
        ("h<id>_<name>", "Yes if the country has a value for that hierarchy_id for that year (the year the value is "
                         "for), from any round or Gap fill. See the Indicators sheet for what each column holds."),
        ("Years", "has_staff_report and has_dsa_table go by publication year; the h columns by the year the value "
                  "is for. A report published in year P usually gives the actual value for P-1 or P-2."),
        ("Sub-levels", "Sub-level ids (e.g. 5.1) are numbered by position inside their category, so their meaning "
                       "can differ between DSA templates. Top-level ids (h1-h6) are comparable across all tables."),
        ("By year", "Counts of countries with Yes in each column, per year."),
    ], columns=["Item", "Meaning"])


def main(final_csv: Path = FINAL_CSV, report_source: str = REPORT_SOURCE, out_xlsx: Path | None = OUT_XLSX):
    cov, ind = build(final_csv, YEARS, report_source)
    summary = by_year(cov, ind)
    print(f"\nCoverage: {len(cov):,} rows ({cov['country'].nunique()} countries x {cov['year'].nunique()} years), "
          f"{len(ind)} indicator columns\n")
    print(summary.to_string(index=False))
    if out_xlsx is not None:
        write_workbook({"Coverage": cov, "By year": summary, "Indicators": ind, "Notes": notes(report_source)},
                       Path(out_xlsx))
        print(f"\nWrote {out_xlsx}")
    return cov, summary, ind


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Country-year data-coverage database (Yes/No).")
    ap.add_argument("--report-source", default=REPORT_SOURCE, choices=["pdf_folders", "round1_summaries"])
    ap.add_argument("--no-excel", action="store_true", help="print only, write no workbook")
    a, _ = ap.parse_known_args()  # parse_known_args: consoles can pass their own extra arguments
    main(report_source=a.report_source, out_xlsx=None if a.no_excel else OUT_XLSX)
