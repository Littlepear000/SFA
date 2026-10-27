"""
[ad hoc report] Country-year coverage of the final merged panel (Round 1/2/3 + Human Review + Gap Fill),
for two headline variables: residual (hierarchy_id "6") and other_identified_flows (hierarchy_id "5").
    Run by hand | no API, no network | reads the one merged CSV a colleague built, writes two summary CSVs

Why this needed more than a straight groupby
    1. Per-row year: the merged file keeps the original "last_actual_year" column from Round 1/2/3 AND a
       separate "year" column from Gap Fill, but it was never unified into one column during the merge --
       "year" is populated only for source_round == "gapfill" rows; it is blank for round1/round2/round3
       rows, which carry their year in "last_actual_year" instead. This script coalesces the two
       (year if present, else last_actual_year) into one effective year per row.
    2. Country spelling: the "country" column has ~280 distinct raw strings for what normalize_country()
       resolves to only ~194 real countries/territories once run through it (alias map + casefold for
       the plain case-variant spellings, e.g. "Bosnia And Herzegovina" vs "Bosnia and Herzegovina", that
       the alias map itself does not need to know about). Counting raw strings instead of normalized
       countries overstates coverage by roughly 40%.
    3. A country can have more than one row for the same (field, year): two reports in the same year can
       each carry an actual/historical value for that year (one of them often via Gap Fill, sourcing a
       different report than the one that gave the country's own last_actual_year row). This is counted
       once per country per year either way, but is also flagged so a genuine disagreement between two
       reports' numbers is visible rather than silently resolved by picking whichever row happened to
       sort first.

What counts as "available"
    hierarchy_id is exactly "5" or "6" (the headline total, not one of its sub-components, e.g. "5.1"),
    the effective year parses to an integer, and "value" is non-blank and parses to a float.

Output (written next to the input CSV by default)
    panel_coverage_residual.csv              one row per year: n_countries, n_rows, n_duplicate_countries
                                              (more than one row that year), n_conflicting_countries (more
                                              than one row that year with genuinely different values)
    panel_coverage_other_identified_flows.csv   the same, for hierarchy_id "5"
    panel_coverage_duplicates_detail.csv     one row per (field, year, country) that had more than one
                                              row -- every value seen, so a flagged conflict can be
                                              spot-checked directly instead of re-deriving it by hand

Usage
    python gapfill_panel_coverage_report.py
    or edit INPUT_CSV / OUT_DIR at the top of the file and run (also works from a console).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(HERE))
import gapfill_lib_core as core  # noqa: E402

# ------------------------------------------------------------------ CONFIG
INPUT_CSV = HERE.parent / "output" / "gapfill" / "final_all_batches_with_gapfill.csv"
OUT_DIR = INPUT_CSV.parent

FIELDS = {"6": "residual", "5": "other_identified_flows"}
# values within this far apart are treated as the same observation re-reported, not a genuine conflict
# (e.g. a typo-level rounding difference), well inside the identity-check tolerance used elsewhere
VALUE_TOLERANCE = 0.05


def _parsed_year(label: str) -> float:
    """y1 (the single year, or a fiscal-year label's end year) from gapfill_lib_core's own parser, or
    NaN if unparseable. A pandas-missing cell reads back as the float NaN here, not the string "nan" --
    `pd.Series.fillna("")` upstream is what prevents the classic `nan or default` truthiness trap (NaN is
    truthy in Python, so a bare `or` never falls through to the fallback column)."""
    kind, _y0, y1, _note = core.parse_year_label(label)
    return float(y1) if kind != "invalid" else float("nan")


def load_rows(input_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(
        input_csv,
        usecols=["country", "hierarchy_id", "value", "year", "last_actual_year", "source_round"],
        dtype=str,
    )
    df = df[df["hierarchy_id"].isin(FIELDS)].copy()

    year_s = df["year"].fillna("").str.strip()
    lay_s = df["last_actual_year"].fillna("").str.strip()
    effective_label = year_s.where(year_s != "", lay_s)  # year if present, else last_actual_year
    df["effective_year"] = effective_label.map(_parsed_year)

    df["value_num"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["effective_year", "value_num"])
    df["effective_year"] = df["effective_year"].astype(int)

    df["country_norm"] = df["country"].map(lambda c: core.normalize_country(str(c).strip()))
    df["country_key"] = df["country_norm"].str.casefold()
    # canonical display label per casefold group: the most common normalized spelling seen for it
    label_by_key = (
        df.groupby("country_key")["country_norm"]
        .agg(lambda s: s.value_counts().idxmax())
    )
    df["country_label"] = df["country_key"].map(label_by_key)
    return df


def summarize(df: pd.DataFrame, hierarchy_id: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    sub = df[df["hierarchy_id"] == hierarchy_id]
    years = sorted(sub["effective_year"].unique())
    rows, detail_rows = [], []
    for year in years:
        at_year = sub[sub["effective_year"] == year]
        n_rows = len(at_year)
        n_countries = at_year["country_key"].nunique()
        n_dup = n_conflict = 0
        for key, group in at_year.groupby("country_key"):
            if len(group) <= 1:
                continue
            n_dup += 1
            vals = sorted(group["value_num"].tolist())
            conflicting = (vals[-1] - vals[0]) > VALUE_TOLERANCE
            if conflicting:
                n_conflict += 1
            detail_rows.append({
                "field": FIELDS[hierarchy_id], "year": year, "country": group["country_label"].iloc[0],
                "n_rows": len(group), "values": "; ".join(f"{v:g}" for v in vals),
                "source_rounds": "; ".join(group["source_round"].fillna("")),
                "conflicting": conflicting,
            })
        rows.append({
            "year": year, "n_countries_available": n_countries, "n_rows": n_rows,
            "n_countries_with_duplicate_rows": n_dup, "n_countries_with_conflicting_values": n_conflict,
        })
    return pd.DataFrame(rows), pd.DataFrame(detail_rows)


def main(input_csv: Path = INPUT_CSV, out_dir: Path = OUT_DIR) -> None:
    df = load_rows(input_csv)
    print(f"Rows with an available value for hierarchy_id in {sorted(FIELDS)}: {len(df)}")
    print(f"Distinct countries (after normalize_country + casefold): {df['country_key'].nunique()}")
    print(f"Effective-year range: {df['effective_year'].min()}-{df['effective_year'].max()}")

    out_dir.mkdir(parents=True, exist_ok=True)
    all_detail = []
    for hid, name in FIELDS.items():
        summary, detail = summarize(df, hid)
        p = out_dir / f"panel_coverage_{name}.csv"
        summary.to_csv(p, index=False, encoding="utf-8-sig")
        print(f"{name}: {len(summary)} year(s) -> {p}")
        all_detail.append(detail)

    detail = pd.concat(all_detail, ignore_index=True) if all_detail else pd.DataFrame()
    dp = out_dir / "panel_coverage_duplicates_detail.csv"
    detail.to_csv(dp, index=False, encoding="utf-8-sig")
    n_conflict = int(detail["conflicting"].sum()) if len(detail) else 0
    print(f"Country-years with more than one row: {len(detail)} (of which genuinely conflicting values: {n_conflict}) -> {dp}")


if __name__ == "__main__":
    main()
