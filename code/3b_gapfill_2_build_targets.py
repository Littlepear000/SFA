"""
[3b_gapfill_2] Build the task list for the API run.
    Step 2 | run by hand | does not read PDFs, does not call the API, runs in seconds

Purpose
    Turn the gap list produced by Step 1 into the two files Step 3 needs.

Input (Step 1's output, under CHECK_DIR, filenames carry STAMP)
    gap_years_<STAMP>.csv
    report_inventory_<STAMP>.csv

Output (written to the same folder)
    gapfill_targets_<STAMP>.csv        one row per gap year: gap_id, country, gap_year, gap_span, primary_cause,
                                       audit_fill_status (Step 1's prediction), audit_expected_source_report
                                       (the predicted source report)
    gapfill_skip_reports_<STAMP>.csv   reports that cannot be used as a source: those where Step 1 found no
                                       DSA table, and multi-country documents (pdf_file_name, reason)
    -> these two files are the input to Step 3.

Core steps
    1. Read gap_years, turn each gap year into one row of targets.
    2. Read report_inventory, pick out reports with no DSA table and multi-country documents, list them
       under skip.
    3. Write out the two CSVs.

Usage
    python 3b_gapfill_2_build_targets.py [--check-dir <Step 1's output folder>] [--stamp <version tag>]
    or just edit CHECK_DIR / STAMP at the top of the file and run. STAMP must match Step 1's.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def _here() -> Path:
    """Folder holding the gapfill scripts. Uses __file__ when the file is run
    normally; in an IPython / PyCharm console (no __file__) it looks for the
    folder that contains gapfill_lib_core.py, starting from the working folder."""
    try:
        return Path(__file__).resolve().parent
    except NameError:
        cwd = Path.cwd()
        for cand in (cwd, cwd / "code", cwd.parent / "code", cwd.parent):
            if (cand / "gapfill_lib_core.py").exists():
                return cand
        return cwd

HERE = _here()
BASE = HERE.parent if HERE.name == "code" else HERE

# ------------------------------------------------------------------ CONFIG
CHECK_DIR = BASE / "output" / "2016-2020" / "gap_year_check"  # folder with the step-1 outputs
STAMP = "20260920_v2"  # must match the STAMP used by 3a_gapfill_1_build_panel_gap_flags.py


def main(check_dir: Path = CHECK_DIR, stamp: str = STAMP) -> None:
    check_dir = Path(check_dir)
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
    }).sort_values(["country", "gap_year"])
    targets.to_csv(check_dir / f"gapfill_targets_{stamp}.csv", index=False, encoding="utf-8-sig")

    skip = inv[inv["report_status"].isin(["no_table", "excluded_non_country"])].copy()
    skip["reason"] = skip["report_status"].map({
        "no_table": "Step 1 found no DSA table",
        "excluded_non_country": "multi-country document",
    })
    skip[["pdf_file_name", "reason"]].sort_values("pdf_file_name").to_csv(
        check_dir / f"gapfill_skip_reports_{stamp}.csv", index=False, encoding="utf-8-sig"
    )

    print(f"gap years to fill: {len(targets)}")
    print(f"reports never used as a source: {len(skip)}")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--check-dir", default=None)
    ap.add_argument("--stamp", default=None)
    a, _ = ap.parse_known_args()  # tolerant of extra args injected by IPython/Spyder
    main(Path(a.check_dir) if a.check_dir else CHECK_DIR, a.stamp or STAMP)
