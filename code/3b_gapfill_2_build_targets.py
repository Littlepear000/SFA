"""
[3b_gapfill_2] Build the task list for the API run, and the Step 2 candidate map.
    Step 2 | run by hand | does not call the API; scans the selected-PDF folders on disk

Purpose
    Turn the gap list produced by Step 1 into the files Step 3 needs, and -- the actual "map of gap
    year -> candidate report" -- persist it as its own CSV so it can be sanity-checked before Step 3
    spends any API calls. The candidate order (T+2 first, then T+3, latest publication date first) is
    computed with the exact same gapfill_lib_core.build_candidates() that Step 3 uses, so this map is
    an honest preview of what Step 3 will actually try, not a separate guess.

Input
    gap_years_<STAMP>.csv, report_inventory_<STAMP>.csv   Step 1's output, under CHECK_DIR
    SELECTED_PDF_DIRS                                     Step 1's selected_pdf_pages folders (same
                                                          config as 3c; a report is only a candidate if
                                                          it already has a selected PDF there)

Output (written to CHECK_DIR)
    gapfill_targets_<STAMP>.csv        one row per gap year: gap_id, country, gap_year, gap_span, primary_cause,
                                       audit_fill_status (Step 1's prediction), audit_expected_source_report
                                       (the predicted source report)
    gapfill_skip_reports_<STAMP>.csv   reports that cannot be used as a source: those where Step 1 found no
                                       DSA table, and multi-country documents (pdf_file_name, reason)
    gapfill_candidate_map_<STAMP>.csv  one row per (gap year, candidate rank): country, gap_year, rank,
                                       candidate_report, offset_years (2 or 3), publication_date. A gap
                                       year with no candidate report at all gets one row with rank empty.
    -> these three files are the input to Step 3.

Core steps
    1. Read gap_years, turn each gap year into one row of targets.
    2. Read report_inventory, pick out reports with no DSA table and multi-country documents, list them
       under skip.
    3. Scan SELECTED_PDF_DIRS and, for every gap year, build its ordered candidate list with
       gapfill_lib_core.build_candidates() -- the same function Step 3 calls at run time.
    4. Write out the three CSVs.

Usage
    python 3b_gapfill_2_build_targets.py [--check-dir <Step 1's output folder>] [--stamp <version tag>]
    or just edit CHECK_DIR / STAMP / SELECTED_PDF_DIRS at the top of the file and run. STAMP must match
    Step 1's.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List

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
sys.path.insert(0, str(HERE))
from gapfill_lib_core import index_by_country_year, index_selected_pdfs, reports_from_selected, build_candidate_map_rows  # noqa: E402

# ------------------------------------------------------------------ CONFIG
CHECK_DIR = BASE / "output" / "2016-2020" / "gap_year_check"  # folder with the step-1 outputs
STAMP = "20260920_v2"  # must match the STAMP used by 3a_gapfill_1_build_panel_gap_flags.py

# Same folders as 3c's SELECTED_PDF_DIRS (keep the two lists in sync): Step 1's "selected_pdf_pages"
# folders, one per batch. The first folder that holds a report's selected PDF wins, so list re-run
# folders before the original ones.
SELECTED_PDF_DIRS: List[Path] = [
    BASE / "output" / "2011-2015" / "round1_20260921_run1" / "selected_pdf_pages",
    BASE / "output" / "2016-2020" / "round2_20260921_run1" / "selected_pdf_pages",
    BASE / "output" / "2016-2020" / "round1_20260921_run1" / "selected_pdf_pages",
    BASE / "output" / "2021-2026" / "round1_20260921_run1" / "selected_pdf_pages",
]


def main(check_dir: Path = CHECK_DIR, stamp: str = STAMP, selected_pdf_dirs: List[Path] = SELECTED_PDF_DIRS) -> None:
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

    skip_df = inv[inv["report_status"].isin(["no_table", "excluded_non_country"])].copy()
    skip_df["reason"] = skip_df["report_status"].map({
        "no_table": "Step 1 found no DSA table",
        "excluded_non_country": "multi-country document",
    })
    skip_df[["pdf_file_name", "reason"]].sort_values("pdf_file_name").to_csv(
        check_dir / f"gapfill_skip_reports_{stamp}.csv", index=False, encoding="utf-8-sig"
    )

    selected_index = index_selected_pdfs([Path(d) for d in selected_pdf_dirs])
    reports = reports_from_selected(selected_index)
    pub_year_idx = index_by_country_year(reports)
    skip = set(skip_df["pdf_file_name"])
    gap_items = targets.to_dict("records")
    candidate_map = pd.DataFrame(build_candidate_map_rows(gap_items, pub_year_idx, skip))
    candidate_map.to_csv(check_dir / f"gapfill_candidate_map_{stamp}.csv", index=False, encoding="utf-8-sig")

    # build_candidate_map_rows() writes exactly one row (rank=None) for a gap year with no candidate at
    # all, and one row per candidate (rank=1, 2, ...) otherwise, so counting null ranks counts gap years.
    n_no_candidate = int(candidate_map["rank"].isna().sum()) if len(candidate_map) else 0
    print(f"gap years to fill: {len(targets)}")
    print(f"reports never used as a source: {len(skip_df)}")
    print(f"reports with a selected PDF available as a candidate source: {len(reports)}")
    print(f"gap years with no candidate report at all: {n_no_candidate}")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--check-dir", default=None)
    ap.add_argument("--stamp", default=None)
    a, _ = ap.parse_known_args()  # tolerant of extra args injected by IPython/Spyder
    main(Path(a.check_dir) if a.check_dir else CHECK_DIR, a.stamp or STAMP)
