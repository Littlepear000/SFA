"""
[ad hoc] Append one more Gap Fill run's values to the merged "final all batches with gap fill" CSV.
    Run by hand | no API, no network | reads the previous merged CSV + the new run's values_long CSV

Why
    The first Gap Fill run (STAMP 202601022) only targeted years missing BETWEEN a country's own first and
    last observed years. A second run (STAMP 202601028, 3a with FULL_RANGE = (2001, 2025)) targeted the
    remaining missing country-years of the full 2001-2025 panel, incrementally (it skips every gap the
    first run already listed). This script adds the second run's rows to the merged CSV the first run
    produced, in the same layout.

Layout of a gap-fill row (copied from how the 20261026 file stores the first run's rows)
    json_file, pdf_file_name, country, top_category, hierarchy_id, level, parent_label, label_verbatim,
    value are taken from values_long as is; last_actual_year = the gap year; source_round = "gapfill";
    every other report-metadata column is left blank.

    One column is added: gapfill_run = the Gap Fill STAMP that produced the row (blank for round1/2/3
    rows). The previous file's gap-fill rows all came from PRIOR_RUN_STAMP (checked: the row count must
    match that run's values_long exactly).

Usage
    python gapfill_append_run.py        (edit CONFIG first)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
BASE = HERE.parent if HERE.name == "code" else HERE
GAPFILL_DIR = BASE / "output" / "gapfill"

# ------------------------------------------------------------------ CONFIG
PREV_MERGED_CSV = GAPFILL_DIR / "final_all_batches_with_gapfill_20261026.csv"
PRIOR_RUN_STAMP = "202601022"
PRIOR_VALUES_LONG = GAPFILL_DIR / "output" / f"all_{PRIOR_RUN_STAMP}" / f"gapfill_values_long_{PRIOR_RUN_STAMP}.csv"
NEW_RUN_STAMP = "202601028"
NEW_VALUES_LONG = GAPFILL_DIR / "output" / f"all_{NEW_RUN_STAMP}" / f"gapfill_values_long_{NEW_RUN_STAMP}.csv"
OUT_CSV = GAPFILL_DIR / "final_all_batches_with_gapfill_20261028.csv"
# ==============================================================================

COPY_COLS = ["json_file", "pdf_file_name", "country", "top_category", "hierarchy_id", "level",
             "parent_label", "label_verbatim", "value"]


def to_merged_rows(values_long: pd.DataFrame, columns: list, stamp: str) -> pd.DataFrame:
    out = pd.DataFrame(index=values_long.index, columns=columns, dtype=object)
    for c in COPY_COLS:
        out[c] = values_long[c]
    out["last_actual_year"] = values_long["year"]
    out["source_round"] = "gapfill"
    out["gapfill_run"] = stamp
    return out


def main(prev_csv: Path = PREV_MERGED_CSV, prior_long: Path = PRIOR_VALUES_LONG, prior_stamp: str = PRIOR_RUN_STAMP,
         new_long: Path = NEW_VALUES_LONG, new_stamp: str = NEW_RUN_STAMP, out_csv: Path = OUT_CSV) -> pd.DataFrame:
    prev = pd.read_csv(prev_csv, dtype=str, keep_default_na=False, na_values=[""])
    if "gapfill_run" not in prev.columns:
        n_prev_gap = int((prev["source_round"] == "gapfill").sum())
        n_prior = len(pd.read_csv(prior_long, dtype=str))
        if n_prev_gap != n_prior:
            raise SystemExit(f"{prev_csv.name} has {n_prev_gap} gapfill rows but {prior_long.name} has {n_prior}; "
                             f"cannot label them all as run {prior_stamp}")
        prev["gapfill_run"] = None
        prev.loc[prev["source_round"] == "gapfill", "gapfill_run"] = prior_stamp
    if (prev["gapfill_run"] == new_stamp).any():
        raise SystemExit(f"{prev_csv.name} already contains run {new_stamp}")

    new = pd.read_csv(new_long, dtype=str, keep_default_na=False, na_values=[""])
    added = to_merged_rows(new, list(prev.columns), new_stamp)
    merged = pd.concat([prev, added], ignore_index=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"{prev_csv.name}: {len(prev)} rows; + {len(added)} rows from run {new_stamp} -> {out_csv} ({len(merged)} rows)")
    print(merged.groupby(["source_round", "gapfill_run"], dropna=False).size().to_string())
    return merged


if __name__ == "__main__":
    main()
