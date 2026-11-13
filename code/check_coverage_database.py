"""
Data-coverage database: one row per panel country and year, Yes/No for every piece of data we have.
    Run by hand | no API, no network | reads PDF file names (never opens a PDF) and the merged CSV

Part 1 -- "Coverage" sheet (190 countries x 2001-2025 = 4,750 rows)
    country, year
    has_staff_report   Yes if the country has at least one staff report PUBLISHED that year, from the
                       raw PDFs in every batch folder of PDF_ROOT (BATCHES), read together
    has_dsa_table      Yes if at least one report published that year has a DSA table in the final data
                       (Round 1/2/3 rows in FINAL_CSV)
    h<id>_<name>       one column per hierarchy_id in FINAL_CSV: Yes if the country has a value for it
                       for that year (the year the value is FOR, from any round or Gap fill)
                       e.g. h5_other_identified_flows, h6_residual, h3_1_revenue_and_grants
Every cell after country/year is "Yes" or "No".

Part 2 -- "By year" sheet: per year, the number of panel countries, and how many of them have a staff
    report, a DSA table (these four columns are always there), then one column per indicator in
    INDICATORS: how many countries have a value for it. INDICATORS is one Coverage column name or a list
    of them, e.g. "h5_other_identified_flows" or ["h5_other_identified_flows", "h6_residual"]
    (default). Case and spaces do not matter ("H5 other identified flows" works), and the short form
    "h5" / "h3_1" picks that hierarchy_id's column.

Part 3 -- "Sources" sheet: the same rows as Coverage; for every indicator column, where the value came
    from: Round 1, Round 2, Round 3 or Gap fill (empty = no value). When rows from more than one round give
    a value for the same country and year, one is picked in the order Round 1, Round 2, Round 3, Gap fill
    (the same rule as the archived gapfill_panel_source_breakdown.py).

Part 4 -- "Report years" sheet: every (country, publication year) with at least one staff report, for
    ALL years in the PDF folders (not only the panel years), so the coverage app can check whether a
    country had a report in the years after a missing year (T+1 ... T+4).

Also an "Indicators" sheet (column name -> hierarchy_id, level, top category, the most common labels,
how many country-years have it) and a "Notes" sheet, which starts with the run's stamp and the full
paths of the inputs (final CSV, PDF folder and batches), as a record of what the workbook was built from.

The workbook is OUT_DIR/coverage_database_<STAMP>.xlsx. STAMP is set in the settings (or --stamp);
None = date and time of the run, YYYYMMDD_HHMM. Next to it, coverage_database_<STAMP>.json records the run (time, the
final CSV's path / size / modified time / SHA-256, the PDF folder and batches); the coverage web app
(coverage_app/) lists these records as its version history.

Read this before comparing columns
    - has_staff_report / has_dsa_table go by PUBLICATION year; the h* columns go by the year the value
      is for. A report published in year P usually gives the actual value for P-1 or P-2.
    - Top-level ids (h1-h6) mean the same thing in every DSA table. Sub-level ids (e.g. 5.1, 5.2) are
      numbered by position inside their category, so their meaning can change with the DSA template
      (5.1 is "Privatization receipts" in some tables and "Contingent liabilities" in others). Each
      sub-level column is named after its most common label; the Indicators sheet lists the others.

Staff reports
    Read from the PDF file names in the batch folders under PDF_ROOT (1999-2005, 2006-2010, ...), all
    batches together (read_pdfs() below). Only the panel's countries are counted;
    regional reports and places outside the panel are left out and listed when the script runs.

Usage
    python check_coverage_database.py
    python check_coverage_database.py --pdf-root "D:/path/to/pdf staff reports"
    python check_coverage_database.py --indicators h5_other_identified_flows
    python check_coverage_database.py --indicators h5_other_identified_flows h6_residual h1_change_in_debt
    python check_coverage_database.py --stamp 20261111_v2
    or edit the settings below and run the file from a console.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
if not (HERE / "core.py").exists() and (HERE / "code" / "core.py").exists():
    HERE = HERE / "code"
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from core import ALL_HIERARCHIES, load_rows, normalize_country  # noqa: E402

# ---------------------------------------------------------------- settings
FINAL_CSV = ROOT / "output" / "final" / "final_all_batches_with_gapfill_20261028.csv"
PDF_ROOT = ROOT / "staff_reports" / "pdf staff reports"   # holds one sub-folder per batch
BATCHES = ["1996-2000", "2001-2005", "2006-2010", "2011-2015", "2016-2020", "2021-2026"]  # batch folders read, all together
YEARS = (2001, 2025)                      # panel years, one row per country per year
# Indicator column(s) shown in the "By year" sheet: one name or a list (see the docstring)
INDICATORS = ["h5_other_identified_flows"]
OUT_DIR = ROOT / "output" / "coverage"   # the workbook: OUT_DIR / coverage_database_<STAMP>.xlsx
STAMP = None                             # e.g. "20261111_1203" or "final_v2"; None = date and time of the run (YYYYMMDD_HHMM)

# Old or alternative names that normalize_country() does not merge -> the panel's name (lower case)
EXTRA_ALIASES = {
    "azerbaijan republic": "azerbaijan",
    "islamic state of afghanistan": "afghanistan",
    "socialist people's libyan arab jamahiriya": "libya",
    "swaziland": "eswatini",
    "federal republic of yugoslavia": "serbia and montenegro",
    "hong kong special administrative region": "hong kong sar, china",   # file names without the China prefix
    "macao special administrative region": "macao sar, china",
}
# File-name prefixes that are not one country (matched case-insensitively)
NOT_A_COUNTRY = re.compile(
    r"cluster|multi-country|central and eastern europe|euro area|monetary (?:community|union)|currency union", re.I)
# A staff-report file name: "<Country>_<YYYY-MM-DD>...pdf", e.g. "Haiti_2020-04-20_CR2020-123.pdf"
NAME_RE = re.compile(r"^(?P<country>.+?)_(?P<year>\d{4})-\d{2}-\d{2}")


def country_key(raw: str) -> str:
    """One spelling per country, so different spellings in file names and in the final CSV match."""
    key = normalize_country(str(raw).strip()).casefold()
    return EXTRA_ALIASES.get(key, key)


def panel_countries(final_csv: Path = FINAL_CSV) -> set:
    """The panel: every country in the final CSV (190)."""
    names = pd.read_csv(final_csv, usecols=["country"], dtype=str)["country"].dropna().unique()
    return {country_key(n) for n in names}


# ================================================================= reports
def read_pdfs(pdf_root: Path = PDF_ROOT, batches=BATCHES) -> pd.DataFrame:
    """List every PDF in the batch folders (all of them together) and read country and publication year
    from its file name. One row per file name: a PDF found in two batch folders counts once."""
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


def keep_panel_reports(pdfs: pd.DataFrame, panel: set) -> pd.DataFrame:
    """Drop regional/cluster reports and places outside the panel, and list them."""
    regional = pdfs["country_raw"].str.contains(NOT_A_COUNTRY)
    outside = ~regional & ~pdfs["country_key"].isin(panel)
    for label, mask in (("regional or cluster report", regional), ("not in the panel", outside)):
        if mask.any():
            print(f"Left out, {label}: {int(mask.sum())} PDF(s)")
            for name in sorted(pdfs.loc[mask, "pdf_file_name"]):
                print(f"    {name}")
    return pdfs[~regional & ~outside]


def report_country_years(panel: set, pdf_root: Path = PDF_ROOT, batches=BATCHES) -> pd.DataFrame:
    """One row per (country, publication year) with at least one raw staff-report PDF, every year found,
    and n_reports = how many PDFs. Feeds has_staff_report and the Report years sheet."""
    pdfs = keep_panel_reports(read_pdfs(pdf_root, batches), panel)
    print(f"Staff reports: {len(pdfs):,} PDFs of panel countries in {pdf_root} ({', '.join(batches)})")
    return pdfs.groupby(["country_key", "year"]).size().rename("n_reports").reset_index()


def dsa_country_years(final: pd.DataFrame) -> set:
    """(country, publication year) of every report with Round 1/2/3 rows in the final data."""
    names = final.loc[final["source_round"] != "gapfill", "pdf_file_name"].dropna().unique()
    out = set()
    for name in names:
        m = NAME_RE.match(name)
        if m:
            out.add((country_key(m.group("country")), int(m.group("year"))))
    return out


# Where a value came from, best first: a country-year with values from more than one round keeps the first
SOURCE_ORDER = [("round1", "Round 1"), ("round2", "Round 2"), ("round3", "Round 3"), ("gapfill", "Gap fill")]


def value_sources(values: pd.DataFrame) -> dict:
    """hierarchy_id -> {(country_key, year): "Round 1" | "Round 2" | "Round 3" | "Gap fill"}."""
    rank = {r: i for i, (r, _) in enumerate(SOURCE_ORDER)}
    label = dict(SOURCE_ORDER)
    v = values.assign(_rank=values["source_round"].map(rank).fillna(len(rank)))
    v = v.sort_values("_rank", kind="stable").drop_duplicates(["hierarchy_id", "country_key", "effective_year"])
    out = {}
    for hid, g in v.groupby("hierarchy_id"):
        out[hid] = {k: label.get(r, str(r)) for k, r in zip(zip(g["country_key"], g["effective_year"]), g["source_round"])}
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


def _step(progress, fraction: float, label: str) -> None:
    """Report progress to a caller (e.g. the coverage web app): progress(fraction 0-1, label)."""
    if progress is not None:
        progress(fraction, label)


def build(final_csv: Path = FINAL_CSV, years: tuple = YEARS, pdf_root: Path = PDF_ROOT, batches=BATCHES,
          progress=None):
    _step(progress, 0.05, "Reading the final CSV")
    final = pd.read_csv(final_csv, usecols=["country", "pdf_file_name", "source_round", "hierarchy_id", "level",
                                            "top_category", "label_verbatim"], dtype=str)
    panel = panel_countries(final_csv)
    values = load_rows(final_csv, ALL_HIERARCHIES)            # rows with a numeric value and a parsed year
    labels = values.groupby("country_key")["country_label"].agg(lambda s: s.value_counts().index[0])
    panel_years = list(range(years[0], years[1] + 1))
    _step(progress, 0.40, "Reading the staff-report PDF folders")

    grid = pd.MultiIndex.from_product([sorted(panel, key=lambda k: labels.get(k, k)), panel_years],
                                      names=["country_key", "year"]).to_frame(index=False)
    keys = list(zip(grid["country_key"], grid["year"]))
    report_years = report_country_years(panel, pdf_root, batches)
    reports = set(zip(report_years["country_key"], report_years["year"]))
    dsa = dsa_country_years(final)
    _step(progress, 0.60, "Building the coverage table")

    cov = pd.DataFrame({"country": grid["country_key"].map(lambda k: labels.get(k, k)), "year": grid["year"],
                        "has_staff_report": yes_no(k in reports for k in keys),
                        "has_dsa_table": yes_no(k in dsa for k in keys)})
    ind = indicator_columns(final)
    sources = value_sources(values)
    src = cov[["country", "year"]].copy()
    for hid, col in zip(ind["hierarchy_id"], ind["column"]):
        got = sources.get(hid, {})
        cov[col] = yes_no(k in got for k in keys)
        src[col] = [got.get(k, "") for k in keys]
    ind["country_years_with_value"] = [int((cov[c] == "Yes").sum()) for c in ind["column"]]

    odd = sum(1 for k in keys if k in dsa and k not in reports)
    if odd:
        print(f"NOTE: {odd} country-year(s) have a DSA table in the final data but no staff report in the "
              f"raw PDF folders; check whether those PDFs are missing there")
    report_years = pd.DataFrame({"country": report_years["country_key"].map(lambda k: labels.get(k, k)),
                                 "year": report_years["year"], "n_reports": report_years["n_reports"]}
                                ).sort_values(["country", "year"], ignore_index=True)
    return cov, ind, src, report_years


def pick_indicator_columns(ind: pd.DataFrame, indicators) -> list:
    """Coverage column names for INDICATORS (one name or a list), matched loosely: case and spaces do not
    matter, and "h5" / "h3_1" stands for that hierarchy_id's column."""
    if isinstance(indicators, str):
        indicators = [indicators]
    columns = list(ind["column"])
    short = {"h" + hid.replace(".", "_"): col for hid, col in zip(ind["hierarchy_id"], ind["column"])}
    picked, unknown = [], []
    for name in indicators:
        key = re.sub(r"[\s\-]+", "_", str(name).strip().lower())
        col = key if key in columns else short.get(key)
        if col is None:
            unknown.append(name)
        elif col not in picked:
            picked.append(col)
    if unknown:
        raise ValueError(f"INDICATORS not found: {unknown}. Available columns: {', '.join(columns)}")
    return picked


def by_year(cov: pd.DataFrame, ind: pd.DataFrame, indicators=INDICATORS) -> pd.DataFrame:
    def n_yes(col):
        return g[col].apply(lambda s: (s == "Yes").sum()).values

    g = cov.groupby("year")
    out = pd.DataFrame({"Year": g.size().index, "Countries in panel": g.size().values,
                        "Countries with staff report": n_yes("has_staff_report"),
                        "Countries with DSA table": n_yes("has_dsa_table")})
    for col in pick_indicator_columns(ind, indicators):
        out[f"Countries with {col}"] = n_yes(col)
    return out


def notes(stamp: str, final_csv: Path, pdf_root: Path, batches=BATCHES) -> pd.DataFrame:
    return pd.DataFrame([
        ("Run stamp", f"{stamp} (built {datetime.now():%Y-%m-%d %H:%M})"),
        ("Input: final CSV", str(Path(final_csv).resolve())),
        ("Input: staff-report PDFs", f"{Path(pdf_root).resolve()}  -- batch folders: {', '.join(batches)}"),
        ("Coverage", f"One row per panel country and year ({YEARS[0]}-{YEARS[1]}). Every cell after country/year is Yes or No."),
        ("has_staff_report", "Yes if the country has at least one staff report published that year "
                             "(raw PDFs in all batch folders). Regional reports and places outside the panel are left out."),
        ("has_dsa_table", "Yes if at least one report published that year has a DSA table in the final data "
                          f"(Round 1/2/3 rows in {Path(FINAL_CSV).name})."),
        ("h<id>_<name>", "Yes if the country has a value for that hierarchy_id for that year (the year the value is "
                         "for), from any round or Gap fill. See the Indicators sheet for what each column holds."),
        ("Years", "has_staff_report and has_dsa_table go by publication year; the h columns by the year the value "
                  "is for. A report published in year P usually gives the actual value for P-1 or P-2."),
        ("Sub-levels", "Sub-level ids (e.g. 5.1) are numbered by position inside their category, so their meaning "
                       "can differ between DSA templates. Top-level ids (h1-h6) are comparable across all tables."),
        ("By year", "Counts of countries with Yes in each column, per year."),
        ("Sources", "Same rows as Coverage. For each indicator: where the value came from (Round 1, Round 2, Round 3 or "
                    "Gap fill; empty = no value). With values from several rounds, the first in that order is shown."),
        ("Report years", "Every (country, publication year) with at least one staff report in the PDF folders, all "
                         "years (also outside the panel years); n_reports = number of PDFs."),
    ], columns=["Item", "Meaning"])


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


def file_fingerprint(path: Path) -> dict:
    """Size, last-modified time and a short SHA-256 of a file, so a run records exactly which file it used."""
    path = Path(path)
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    st = path.stat()
    return {"path": str(path.resolve()), "size_bytes": st.st_size,
            "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
            "sha256_16": h.hexdigest()[:16]}


def main(final_csv: Path = FINAL_CSV, pdf_root: Path = PDF_ROOT, out_dir: Path | None = OUT_DIR,
         indicators=INDICATORS, stamp: str | None = STAMP, batches=BATCHES, progress=None):
    """Build the coverage database. With out_dir, also writes coverage_database_<STAMP>.xlsx and, next to
    it, coverage_database_<STAMP>.json: the run record (when, which final CSV and PDF folders) that the
    coverage web app lists as the version history."""
    started = datetime.now()
    stamp = stamp or started.strftime("%Y%m%d_%H%M")
    batches = list(batches)
    cov, ind, src, report_years = build(final_csv, YEARS, pdf_root, batches, progress)
    summary = by_year(cov, ind, indicators)
    print(f"\nCoverage: {len(cov):,} rows ({cov['country'].nunique()} countries x {cov['year'].nunique()} years), "
          f"{len(ind)} indicator columns\n")
    print(summary.to_string(index=False))
    if out_dir is not None:
        path = Path(out_dir) / f"coverage_database_{stamp}.xlsx"
        _step(progress, 0.80, "Writing the workbook")
        write_workbook({"Coverage": cov, "By year": summary, "Sources": src, "Report years": report_years,
                        "Indicators": ind, "Notes": notes(stamp, final_csv, pdf_root, batches)}, path)
        record = {
            "stamp": stamp,
            "created": started.isoformat(timespec="seconds"),
            "seconds": round((datetime.now() - started).total_seconds(), 1),
            "workbook": path.name,
            "final_csv": file_fingerprint(final_csv),
            "pdf_root": str(Path(pdf_root).resolve()),
            "batches": batches,
            "years": list(YEARS),
            "n_countries": int(cov["country"].nunique()),
            "n_indicator_columns": int(len(ind)),
            "country_years_with_staff_report": int((cov["has_staff_report"] == "Yes").sum()),
            "country_years_with_dsa_table": int((cov["has_dsa_table"] == "Yes").sum()),
        }
        path.with_suffix(".json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        print(f"\nWrote {path}\nWrote {path.with_suffix('.json')}")
    _step(progress, 1.0, "Done")
    return cov, summary, ind


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Country-year data-coverage database (Yes/No).")
    ap.add_argument("--pdf-root", default=PDF_ROOT, help="folder holding the batch folders")
    ap.add_argument("--indicators", nargs="+", default=INDICATORS,
                    help='indicator column(s) for the "By year" sheet, e.g. h5_other_identified_flows h6_residual')
    ap.add_argument("--stamp", default=STAMP, help="added to the workbook name; default: date and time of the run (YYYYMMDD_HHMM)")
    ap.add_argument("--no-excel", action="store_true", help="print only, write no workbook")
    a, _ = ap.parse_known_args()  # parse_known_args: consoles can pass their own extra arguments
    main(pdf_root=Path(a.pdf_root), out_dir=None if a.no_excel else OUT_DIR, indicators=a.indicators,
         stamp=a.stamp)
