"""
Year-by-year coverage: staff reports in the raw PDF folders vs. countries with data for one indicator.
    Run by hand | no API, no network | reads PDF file names (never opens a PDF) and the merged CSV

Output: one Excel sheet named after INDICATOR (e.g. "Residual"), one row per year:
    Year
    Number of reports                    PDFs published that year (date in the file name)
    Number of countries with reports     panel countries with at least one of those PDFs; a country
                                         with several reports in a year is counted once
    Number of countries with data        panel countries with a value for INDICATOR for that year
                                         (same as "Available" in the coverage chart of
                                         summary/dsa_extraction_summary.html)
A second sheet, "<Indicator> by source" (e.g. "Residual by source"; just "By source" when the name
would pass Excel's 31-character limit), is the table behind the
"Country coverage by year and source" chart of the summary page: one row per year (DATA_YEARS), the
number of panel countries, and how many of them got their value from Round 1 / Round 2 / Round 3
(human review) / Gap fill, or are Unavailable (these five add up to the panel count). It always covers
the whole panel, whichever batches are read. Plus a Notes sheet. The tables are also printed.

Note on "Year": reports are counted by PUBLICATION year, data by the year the value is FOR. A report
published in year P usually gives the actual value for P-1 or P-2, so the two are not the same year.

Reading the PDFs
    PDF_ROOT holds one sub-folder per batch (1999-2005, 2006-2010, ...). BATCHES picks which ones to
    read: all of them for the full count, or one (e.g. ["2011-2015"]) for a single batch. Other
    folders under PDF_ROOT (e.g. "ad-hoc run") are ignored unless listed. A PDF that sits in two
    batch folders is counted once.

Countries
    Names are cleaned with normalize_country() from gapfill_lib_core.py plus EXTRA_ALIASES below, so
    "St.Vincent" / "St. Vincent" or "Swaziland" / "Kingdom of Eswatini" count as one country.
    Only the panel's countries are counted (every country in FINAL_CSV, the same 190 as the summary
    page). Regional and cluster reports (CEMAC, WAEMU, ECCU, euro area, multi-country) and places
    outside the panel (e.g. Macao SAR, Anguilla) are left out and listed when the script runs.

Usage
    python check_coverage.py
    python check_coverage.py --batches 2011-2015
    python check_coverage.py --indicator other_identified_flows
    or edit the settings below and run the file from a console.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
if not (HERE / "gapfill_lib_core.py").exists() and (HERE / "code" / "gapfill_lib_core.py").exists():
    HERE = HERE / "code"
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from gapfill_lib_core import normalize_country  # noqa: E402
from gapfill_panel_coverage_report import FIELDS, load_rows  # noqa: E402
from gapfill_panel_source_breakdown import breakdown, country_universe  # noqa: E402

# ---------------------------------------------------------------- settings
INDICATOR = "other_identified_flows"            # a name in FIELDS: "residual" (hierarchy_id 6) or "other_identified_flows" (5)
PDF_ROOT = ROOT / "staff_reports" / "pdf staff reports"
BATCHES = ["1996-2000", "2001-2005", "2006-2010", "2011-2015", "2016-2020", "2021-2026"]  # batch folders under PDF_ROOT
FINAL_CSV = ROOT / "output" / "final" / "final_all_batches_with_gapfill_20261028.csv"
DATA_YEARS = (2001, 2025)         # years the panel covers; "countries with data" is left blank outside them
OUT_DIR = ROOT / "output" / "coverage"  # workbook: check_coverage_<indicator>_<batches>.xlsx

# Old or alternative names that normalize_country() does not merge -> the panel's name (lower case)
EXTRA_ALIASES = {
    "azerbaijan republic": "azerbaijan",
    "islamic state of afghanistan": "afghanistan",
    "socialist people's libyan arab jamahiriya": "libya",
    "swaziland": "eswatini",
    "federal republic of yugoslavia": "serbia and montenegro",
}
# File-name prefixes that are not one country (matched case-insensitively)
NOT_A_COUNTRY = re.compile(
    r"cluster|multi-country|central and eastern europe|euro area|monetary (?:community|union)|currency union", re.I)
NAME_RE = re.compile(r"^(?P<country>.+?)_(?P<year>\d{4})-\d{2}-\d{2}")


def country_key(raw: str) -> str:
    key = normalize_country(str(raw).strip()).casefold()
    return EXTRA_ALIASES.get(key, key)


def hierarchy_id(indicator: str) -> str:
    by_name = {name: hid for hid, name in FIELDS.items()}
    if indicator not in by_name:
        raise ValueError(f"INDICATOR must be one of {sorted(by_name)}, got {indicator!r}")
    return by_name[indicator]


# ================================================================= reports
def read_pdfs(pdf_root: Path = PDF_ROOT, batches=BATCHES) -> pd.DataFrame:
    """Every PDF in the chosen batch folders, one row per file name, with country key and year."""
    rows, unparsed = [], []
    for b in batches:
        folder = Path(pdf_root) / b
        if not folder.is_dir():
            raise FileNotFoundError(f"batch folder not found: {folder}")
        for f in sorted(folder.rglob("*.pdf")):
            if not f.is_file() or f.name.startswith("~$"):
                continue
            m = NAME_RE.match(f.name)
            if not m:
                unparsed.append(f"{b}/{f.relative_to(folder)}")
                continue
            rows.append({"pdf_file_name": f.name, "batch": b, "country_raw": m.group("country"),
                         "country_key": country_key(m.group("country")), "year": int(m.group("year"))})
    df = pd.DataFrame(rows, columns=["pdf_file_name", "batch", "country_raw", "country_key", "year"])
    dup = df.duplicated("pdf_file_name")
    if dup.any():
        print(f"NOTE: {int(dup.sum())} PDF(s) found in more than one batch folder; each counted once")
        df = df[~dup]
    if unparsed:
        print(f"NOTE: {len(unparsed)} file name(s) not in '<Country>_<YYYY-MM-DD>' form, not counted:")
        for name in unparsed:
            print(f"    {name}")
    return df


def panel_countries(final_csv: Path = FINAL_CSV) -> set:
    names = pd.read_csv(final_csv, usecols=["country"], dtype=str)["country"].dropna().unique()
    return {country_key(n) for n in names}


def keep_panel_reports(pdfs: pd.DataFrame, panel: set) -> pd.DataFrame:
    """Drop regional/cluster reports and places outside the panel, and say which."""
    regional = pdfs["country_raw"].str.contains(NOT_A_COUNTRY)
    outside = ~regional & ~pdfs["country_key"].isin(panel)
    for label, mask in (("regional or cluster report", regional), ("not in the panel", outside)):
        if mask.any():
            print(f"Left out, {label}: {int(mask.sum())} PDF(s)")
            for name in sorted(pdfs.loc[mask, "pdf_file_name"]):
                print(f"    {name}")
    return pdfs[~regional & ~outside]


# ================================================================= table
def coverage_table(pdfs: pd.DataFrame, indicator: str = INDICATOR, final_csv: Path = FINAL_CSV,
                   data_years: tuple | None = DATA_YEARS, all_batches: bool = True) -> pd.DataFrame:
    rep = pdfs.groupby("year").agg(reports=("pdf_file_name", "size"), countries=("country_key", "nunique"))

    data = load_rows(final_csv, {hierarchy_id(indicator)})
    with_data = data.groupby("effective_year")["country_key"].nunique()
    if data_years is not None:
        with_data = with_data[(with_data.index >= data_years[0]) & (with_data.index <= data_years[1])]

    # rows: the years of the PDFs read; when every batch is read, also every year with data
    years = sorted(set(rep.index) | (set(with_data.index) if all_batches else set()))
    return pd.DataFrame({
        "Year": years,
        "Number of reports": [int(rep["reports"].get(y, 0)) for y in years],
        "Number of countries with reports": [int(rep["countries"].get(y, 0)) for y in years],
        "Number of countries with data": [with_data.get(y) for y in years],
    }).astype({"Number of countries with data": "Int64"})


def source_table(indicator: str = INDICATOR, final_csv: Path = FINAL_CSV,
                 data_years: tuple | None = DATA_YEARS) -> pd.DataFrame:
    """Panel countries per year by where the indicator's value came from -- the same numbers as
    gapfill_panel_source_breakdown.py's availability CSV and the summary page's coverage chart."""
    t = breakdown(load_rows(final_csv, {hierarchy_id(indicator)}), country_universe(final_csv), years=data_years)
    return pd.DataFrame({
        "Year": t["year"],
        "Countries in panel": t["total_countries"],
        "Round 1": t["n_round1"],
        "Round 2": t["n_round2"],
        "Round 3 (human review)": t["n_round3_human_review"],
        "Gap fill": t["n_gapfill"],
        "Unavailable": t["n_unavailable"],
    }).reset_index(drop=True)


def notes(indicator: str, batches, n_panel: int) -> pd.DataFrame:
    return pd.DataFrame([
        ("Year", "Calendar year. Reports are counted by publication year, data by the year the value is for; "
                 "a report published in year P usually gives the actual value for P-1 or P-2."),
        ("Number of reports", "Staff-report PDFs published that year, in batch folder(s): " + ", ".join(batches)
         + ". Regional and cluster reports, and places outside the panel, are left out."),
        ("Number of countries with reports", f"Countries (of the {n_panel} in the panel) with at least one report "
                                             "that year; several reports in one year count once."),
        ("Number of countries with data", f"Countries (of the {n_panel}) with a value for {indicator} that year "
                                          f"in {Path(FINAL_CSV).name}. Blank outside {DATA_YEARS[0]}-{DATA_YEARS[1]}."),
        ("By source: Round 1 ... Gap fill", f"Countries whose {indicator} value for that year came from this step. "
                                            "If several steps cover the same country-year, one is counted, in the "
                                            "order Round 1 > Round 2 > Round 3 > Gap fill."),
        ("By source: Unavailable", f"Countries with no {indicator} value for that year. Round 1 + Round 2 + Round 3 "
                                   "+ Gap fill + Unavailable = Countries in panel."),
    ], columns=["Column", "Meaning"])


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
                letter = get_column_letter(i)
                ws.column_dimensions[letter].width = 90 if name == "Notes" and i == 2 else max(10, min(len(col) * 0.75, 32))
                if name == "Notes":
                    for cell in ws[letter][1:]:
                        cell.alignment = Alignment(wrap_text=True, vertical="top")


def main(indicator: str = INDICATOR, batches=BATCHES, pdf_root: Path = PDF_ROOT, final_csv: Path = FINAL_CSV,
         out_dir: Path | None = OUT_DIR) -> pd.DataFrame:
    batches = list(batches)
    hierarchy_id(indicator)  # fail early on a bad name
    panel = panel_countries(final_csv)
    pdfs = keep_panel_reports(read_pdfs(pdf_root, batches), panel)
    all_batches = sorted(batches) == sorted(BATCHES)
    table = coverage_table(pdfs, indicator, final_csv, all_batches=all_batches)
    by_source = source_table(indicator, final_csv)

    print(f"\nIndicator: {indicator} | batches: {', '.join(batches)} | panel: {len(panel)} countries")
    print(f"PDFs counted: {len(pdfs):,}\n")
    print(table.to_string(index=False))
    print(f"\n{indicator} by source:\n")
    print(by_source.to_string(index=False))

    if out_dir is not None:
        tag = "all_batches" if all_batches else "_".join(batches)
        path = Path(out_dir) / f"check_coverage_{indicator}_{tag}.xlsx"
        sheet = indicator.replace("_", " ").capitalize()
        src_sheet = f"{sheet} by source" if len(sheet) <= 21 else "By source"  # Excel: 31 characters max
        write_workbook({sheet[:31]: table, src_sheet: by_source,
                        "Notes": notes(indicator, batches, len(panel))}, path)
        print(f"\nWrote {path}")
    return table


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Reports vs. countries with data, by year.")
    ap.add_argument("--indicator", default=INDICATOR, choices=sorted(FIELDS.values()))
    ap.add_argument("--batches", nargs="+", default=BATCHES, help="batch folder name(s) under PDF_ROOT")
    ap.add_argument("--pdf-root", default=PDF_ROOT, help="folder holding the batch folders")
    ap.add_argument("--no-excel", action="store_true", help="print only, write no workbook")
    a, _ = ap.parse_known_args()  # parse_known_args: consoles can pass their own extra arguments
    main(a.indicator, a.batches, Path(a.pdf_root), out_dir=None if a.no_excel else OUT_DIR)
