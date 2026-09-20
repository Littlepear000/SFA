"""
Build the input files for the gap-year API run (offline, no PDFs needed).

Reads the outputs of build_panel_gap_flags.py and writes, next to them:
  gapfill_targets_<stamp>.csv       one row per gap year; run_flag=False rows are held out
  gapfill_skip_reports_<stamp>.csv  reports that must never be used as a source

Copy both files to the machine that runs gapfill_run_api.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
DEFAULT_DIR = BASE / "output" / "2016-2020" / "gap_year_check"
STAMP = "20260918_v1"

HOLD_CAUSE = "errors_file_report_in_between"


def main(check_dir: Path = DEFAULT_DIR, stamp: str = STAMP) -> None:
    gaps = pd.read_csv(check_dir / f"gap_years_{stamp}.csv")
    inv = pd.read_csv(check_dir / f"report_inventory_{stamp}.csv")

    targets = pd.DataFrame({
        "gap_id": gaps["gap_id"],
        "country": gaps["country"],
        "gap_year": gaps["gap_year"],
        "gap_span": gaps["gap_span"],
        "primary_cause": gaps["primary_cause"],
        "audit_fill_status": gaps["fill_status"],
        "audit_expected_source_report": gaps["preferred_source_report"],
    })
    held = gaps["all_causes"].fillna("").str.contains(HOLD_CAUSE)
    targets["run_flag"] = ~held
    targets["hold_reason"] = held.map({True: "errors_sa file report between the bounding reports; verify it first", False: ""})
    targets = targets.sort_values(["country", "gap_year"])
    targets.to_csv(check_dir / f"gapfill_targets_{stamp}.csv", index=False, encoding="utf-8-sig")

    skip = inv[inv["report_status"].isin(["errors_file_not_used", "no_table", "excluded_non_country"])].copy()
    skip["reason"] = skip["report_status"].map({
        "errors_file_not_used": "report is in the errors_sa file (not run for now)",
        "no_table": "Step 1 found no DSA table",
        "excluded_non_country": "multi-country document",
    })
    skip[["pdf_file_name", "reason"]].sort_values("pdf_file_name").to_csv(
        check_dir / f"gapfill_skip_reports_{stamp}.csv", index=False, encoding="utf-8-sig"
    )

    print(f"gap years: {len(targets)} | to run: {int(targets.run_flag.sum())} | held out: {int((~targets.run_flag).sum())}")
    print(f"reports never used as a source: {len(skip)}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DIR)
