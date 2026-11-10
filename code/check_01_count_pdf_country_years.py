"""
Count the unique country-years in a folder of staff-report PDFs.
    Run by hand | no API, no network | reads only file names, never opens a PDF

Each PDF name starts with "<Country>_<YYYY-MM-DD>", e.g. "Argentina_2019-07-15.pdf" or
"Haiti_2020-04-20_CR2020-123.pdf". The year is the PUBLICATION year from that date, not the DSA's
last actual year. A country-year is one (country, publication year) pair, however many reports it has.

Country names are cleaned with normalize_country() from gapfill_lib_core.py (plus a few old names
below), so "St.Vincent" / "St. Vincent" or "Swaziland" / "Kingdom of Eswatini" count as one country,
the same way as in summary/dsa_extraction_summary.html. Reports that are not about one country
(cluster, multi-country, euro area, and regional unions such as CEMAC, WAEMU and ECCU) are left out
and listed separately.

When PANEL_CSV exists, only the panel's countries are counted (every country in that merged CSV, the
same 190 as the summary page), so the per-year numbers match the page. Countries outside the panel
(e.g. Macao SAR, Anguilla) are listed separately. Use --all-countries to count every country.

Output
    Printed: number of PDFs, unique countries, unique country-years, a per-year table, and every file
    whose name could not be parsed.
    Written to OUT_DIR (skipped when OUT_DIR is None):
        pdf_country_years_<folder name>.csv   one row per country-year: country, year, n_reports,
                                              pdf_file_names (";"-separated)
        pdf_counts_by_year_<folder name>.csv  one row per year: n_reports, n_countries

Usage
    python check_01_count_pdf_country_years.py "D:/path/to/pdf staff reports"
    python check_01_count_pdf_country_years.py "D:/path/to/pdf staff reports" --years 2001 2025 --no-recursive
    or set PDF_FOLDER (and the other constants) below and run the file from a console.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------- settings
PDF_FOLDER = Path(r"staff_reports/pdf staff reports/2011-2015")  # the folder to count
RECURSIVE = True       # also look inside sub-folders (e.g. the 5-year batch folders)
YEARS = None           # e.g. (2001, 2025) to keep only those publication years; None = every year
OUT_DIR = Path(r"output/pdf_inventory")  # where the two CSVs go; None = print only
# Count only the panel's countries (every country in this merged CSV). None, or a missing file = all.
PANEL_CSV = Path(r"output/gapfill/final_all_batches_with_gapfill_20261028.csv")

# Old or alternative names that normalize_country() does not merge yet -> the panel's name (lower case)
EXTRA_ALIASES = {
    "azerbaijan republic": "azerbaijan",
    "islamic state of afghanistan": "afghanistan",
    "socialist people's libyan arab jamahiriya": "libya",
    "swaziland": "eswatini",
    "federal republic of yugoslavia": "serbia and montenegro",
}
# File-name prefixes that are not a single country (matched case-insensitively)
NOT_A_COUNTRY = re.compile(
    r"cluster|multi-country|central and eastern europe|euro area|monetary (?:community|union)|currency union", re.I)

NAME_RE = re.compile(r"^(?P<country>.+?)_(?P<year>\d{4})-\d{2}-\d{2}")

# gapfill_lib_core.py sits next to this script; find it even when run from a console
_here = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
for _p in (_here, _here / "code"):
    if (_p / "gapfill_lib_core.py").exists():
        sys.path.insert(0, str(_p))
        break
try:
    from gapfill_lib_core import normalize_country
except ImportError:  # still works without it, just with less name cleaning
    print("NOTE: gapfill_lib_core.py not found; country names are only trimmed, not normalized")

    def normalize_country(raw: str) -> str:
        return str(raw).strip()


def country_key(raw: str) -> tuple[str, str]:
    """(merge key, readable label) for a file-name country prefix."""
    label = normalize_country(raw)
    key = label.casefold()
    key = EXTRA_ALIASES.get(key, key)
    return key, label


def panel_countries(panel_csv) -> set | None:
    """Country keys of every country in the merged panel CSV, or None when there is no such file."""
    if panel_csv is not None and not Path(panel_csv).exists() and not Path(panel_csv).is_absolute():
        panel_csv = _here.parent / panel_csv  # relative to the repo root, wherever the script is run from
    if panel_csv is None or not Path(panel_csv).exists():
        if panel_csv is not None:
            print(f"NOTE: PANEL_CSV not found, counting every country: {panel_csv}")
        return None
    names = pd.read_csv(panel_csv, usecols=["country"], dtype=str)["country"].dropna().unique()
    return {country_key(n)[0] for n in names}


def scan(folder: Path, recursive: bool = RECURSIVE, years: tuple | None = YEARS, panel: set | None = None):
    """Returns (reports DataFrame, list of unparsed file names, DataFrame of left-out reports)."""
    folder = Path(folder)
    if not folder.is_dir():
        raise FileNotFoundError(f"PDF folder not found: {folder.resolve()}")
    files = sorted(folder.rglob("*.pdf") if recursive else folder.glob("*.pdf"))
    files = [f for f in files if f.is_file() and not f.name.startswith("~$")]

    rows, unparsed = [], []
    for f in files:
        m = NAME_RE.match(f.name)
        if not m:
            unparsed.append(str(f.relative_to(folder)))
            continue
        key, label = country_key(m.group("country"))
        rows.append({"pdf_file_name": f.name, "subfolder": str(f.parent.relative_to(folder)),
                     "country_raw": m.group("country"), "country_key": key, "country_label": label,
                     "year": int(m.group("year"))})
    df = pd.DataFrame(rows, columns=["pdf_file_name", "subfolder", "country_raw", "country_key",
                                     "country_label", "year"])
    if years is not None:
        df = df[df["year"].between(years[0], years[1])]

    # The same PDF can sit in two sub-folders (e.g. a copy of a batch); count it once
    dup = df.duplicated("pdf_file_name")
    if dup.any():
        print(f"NOTE: {int(dup.sum())} file name(s) appear in more than one sub-folder; each counted once")
        df = df[~dup]

    df = df.assign(left_out=None)
    df.loc[df["country_raw"].str.contains(NOT_A_COUNTRY), "left_out"] = "not a single country"
    if panel is not None:
        df.loc[df["left_out"].isna() & ~df["country_key"].isin(panel), "left_out"] = "not in the panel"
    left_out = df[df["left_out"].notna()]
    df = df[df["left_out"].isna()].drop(columns="left_out")
    # one readable name per country: the most common cleaned spelling
    labels = df.groupby("country_key")["country_label"].agg(lambda s: s.value_counts().index[0])
    df = df.assign(country=df["country_key"].map(labels))
    return df, unparsed, left_out


def summarize(df: pd.DataFrame):
    country_years = (df.groupby(["country", "year"])
                       .agg(n_reports=("pdf_file_name", "size"),
                            pdf_file_names=("pdf_file_name", lambda s: "; ".join(sorted(s))))
                       .reset_index().sort_values(["country", "year"]))
    by_year = (df.groupby("year")
                 .agg(n_reports=("pdf_file_name", "size"), n_countries=("country_key", "nunique"))
                 .reset_index())
    return country_years, by_year


def main(folder=PDF_FOLDER, recursive: bool = RECURSIVE, years: tuple | None = YEARS, out_dir=OUT_DIR,
         panel_csv=PANEL_CSV):
    folder = Path(folder)
    panel = panel_countries(panel_csv)
    df, unparsed, left_out = scan(folder, recursive, years, panel)
    country_years, by_year = summarize(df)

    print(f"\nFolder: {folder.resolve()}  ({'with' if recursive else 'without'} sub-folders"
          f"{'' if years is None else f', years {years[0]}-{years[1]}'})")
    print(f"  Countries ............... " + (f"only the {len(panel)} panel countries in {panel_csv}"
                                               if panel is not None else "all"))
    print(f"  PDFs counted ............ {len(df):,}")
    print(f"  Unique countries ........ {df['country_key'].nunique():,}")
    print(f"  Unique country-years .... {len(country_years):,}")
    print(f"  Country-years with 2+ reports: {int((country_years['n_reports'] > 1).sum()):,}")
    for reason, g in left_out.groupby("left_out"):
        print(f"  Left out, {reason}: {len(g)} PDF(s)")
        for name in sorted(g["pdf_file_name"]):
            print(f"    {name}")
    if unparsed:
        print(f"  File names not in '<Country>_<YYYY-MM-DD>' form: {len(unparsed)}")
        for name in unparsed:
            print(f"    {name}")
    print("\nBy publication year:")
    print(by_year.to_string(index=False))

    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        tag = re.sub(r"[^\w\-]+", "_", folder.resolve().name).strip("_") or "pdfs"
        p1 = out_dir / f"pdf_country_years_{tag}.csv"
        p2 = out_dir / f"pdf_counts_by_year_{tag}.csv"
        country_years.to_csv(p1, index=False, encoding="utf-8-sig")
        by_year.to_csv(p2, index=False, encoding="utf-8-sig")
        print(f"\nWrote {p1}\nWrote {p2}")
    return country_years, by_year


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Count unique country-years in a folder of staff-report PDFs.")
    ap.add_argument("folder", nargs="?", default=PDF_FOLDER, help="PDF folder (default: PDF_FOLDER in the script)")
    ap.add_argument("--no-recursive", action="store_true", help="do not look inside sub-folders")
    ap.add_argument("--years", nargs=2, type=int, metavar=("FIRST", "LAST"), help="keep only these publication years")
    ap.add_argument("--out-dir", default=OUT_DIR, help="where to write the CSVs")
    ap.add_argument("--no-csv", action="store_true", help="print only, write no CSV")
    ap.add_argument("--all-countries", action="store_true", help="count every country, not only the panel's")
    a, _ = ap.parse_known_args()  # parse_known_args: consoles can pass their own extra arguments
    main(a.folder, recursive=RECURSIVE and not a.no_recursive,
         years=tuple(a.years) if a.years else YEARS, out_dir=None if a.no_csv else a.out_dir,
         panel_csv=None if a.all_countries else PANEL_CSV)
