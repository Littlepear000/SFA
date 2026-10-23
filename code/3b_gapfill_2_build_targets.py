"""
[3b_gapfill_2] Build the task list for the API run, and the Step 2 candidate map.
    Step 2 | run by hand | does not call the API; scans STAFF_REPORTS_DIR and the selected-PDF folders on disk

Purpose
    Turn the gap list produced by Step 1 into the files Step 3 needs, and -- the actual "map of gap
    year -> candidate report" -- persist it as its own CSV so it can be sanity-checked before Step 3
    spends any API calls. The candidate order (T+2 first, then T+3, then T+4, latest publication date first) is
    computed with the exact same gapfill_lib_core.build_candidates() that Step 3 uses, so this map is
    an honest preview of what Step 3 will actually try, not a separate guess.

Input
    gap_years_<STAMP>.csv, report_inventory_<STAMP>.csv   Step 1's output, under CHECK_DIR
    STAFF_REPORTS_DIR                                     root of the ORIGINAL staff-report PDFs, one
                                                          subfolder per batch (e.g.
                                                          staff_reports/pdf staff reports/2016-2020/...).
                                                          This is the candidate universe: every real PDF
                                                          found under it counts as a candidate, whether
                                                          or not Step 1 ever located a table in it in any
                                                          run, and regardless of which batch it is in --
                                                          a T+2/T+3/T+4 candidate from an adjacent batch is
                                                          found exactly the same way as one from the
                                                          batch being checked.
    SELECTED_PDF_DIRS                                     same config as 3c: Step 1's selected_pdf_pages
                                                          folders. Not used to decide what counts as a
                                                          candidate (STAFF_REPORTS_DIR does that); only
                                                          to report, per candidate, whether Step 3 will
                                                          take the fast cached-selection path or will
                                                          need to locate the table fresh from the
                                                          original PDF.

Output (written to CHECK_DIR)
    gapfill_targets_<STAMP>.csv        one row per gap year: gap_id, country, gap_year, gap_span, primary_cause,
                                       audit_fill_status (Step 1's prediction), audit_expected_source_report
                                       (the predicted source report), has_candidate_report (does at least
                                       one real T+2/T+3/T+4 report exist under STAFF_REPORTS_DIR),
                                       audit_vs_real_candidate_mismatch (Step 1 predicted fillable but no
                                       such report actually exists on disk at all -- unusual; normally
                                       means the predicted report's filename/date could not be parsed, or
                                       it genuinely is not among the PDFs under STAFF_REPORTS_DIR)
    gapfill_skip_reports_<STAMP>.csv   reports that cannot be used as a source: those where Step 1 found no
                                       DSA table, and multi-country documents (pdf_file_name, reason)
    gapfill_candidate_map_<STAMP>.csv  one row per (gap year, candidate rank): country, gap_year, rank,
                                       candidate_report, offset_years (2 or 3), publication_date,
                                       has_cached_selected_pdf (does this specific candidate already have
                                       a selected PDF in SELECTED_PDF_DIRS -- if not, Step 3 will locate
                                       it fresh from the original PDF, which costs one extra API call). A
                                       gap year with no candidate report at all gets one row with rank
                                       empty.
    -> these three files are the input to Step 3.

Core steps
    1. Read gap_years, turn each gap year into one row of targets.
    2. Read report_inventory, pick out reports with no DSA table and multi-country documents, list them
       under skip.
    3. Scan STAFF_REPORTS_DIR for the candidate universe, and SELECTED_PDF_DIRS for which of them
       already have a cached selected PDF; for every gap year, build its ordered candidate list with
       gapfill_lib_core.build_candidates() -- the same function Step 3 calls at run time.
    4. Write out the three CSVs.

Usage
    python 3b_gapfill_2_build_targets.py [--check-dir <Step 1's output folder>] [--stamp <version tag>]
    or just edit CHECK_DIR / STAMP / STAFF_REPORTS_DIR / SELECTED_PDF_DIRS at the top of the file and
    run. STAMP must match Step 1's.
"""
from __future__ import annotations

import importlib
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
# A long-lived IPython/Spyder console keeps gapfill_lib_core cached in sys.modules across repeated runs
# of this script via 0_run_gapfill.py -- without this, a code change (e.g. a git pull) would not take
# effect until the console itself is restarted. Reload it in place before pulling names from it.
if "gapfill_lib_core" in sys.modules:
    importlib.reload(sys.modules["gapfill_lib_core"])
from gapfill_lib_core import (  # noqa: E402
    index_by_country_year, index_selected_pdfs, list_staff_reports, build_candidates, build_candidate_map_rows,
    discover_selected_pdf_dirs,
)

# ------------------------------------------------------------------ CONFIG
# CHECK_DIR = BASE / "output" / "2016-2020" / "gap_year_check"  # folder with the step-1 outputs
# STAMP = "20260920_v2"  # must match the STAMP used by 3a_gapfill_1_build_panel_gap_flags.py

# Root of the ORIGINAL staff-report PDFs, one subfolder per batch -- the candidate universe (same config
# as 3c's STAFF_REPORTS_DIR; keep the two in sync).
STAFF_REPORTS_DIR = BASE / "staff_reports" / "pdf staff reports"

# Same folders as 3c's SELECTED_PDF_DIRS (keep the two lists in sync): one "selected_pdf_pages" source
# per batch, auto-discovered under output/ (see discover_selected_pdf_dirs()'s own docstring -- it
# handles both output/<batch>/selected_pdf_pages/ directly and output/<batch>/round1_<stamp>_run1/...,
# which differ across people's machines). Only used here to flag, per candidate, whether Step 3 can take
# the fast cached path -- not to decide what counts as a candidate (STAFF_REPORTS_DIR does that).
SELECTED_PDF_DIRS: List[Path] = discover_selected_pdf_dirs(BASE / "output")


def main(
    check_dir: Path = CHECK_DIR,
    stamp: str = STAMP,
    staff_reports_dir: Path = STAFF_REPORTS_DIR,
    selected_pdf_dirs: List[Path] = SELECTED_PDF_DIRS,
) -> None:
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

    skip_df = inv[inv["report_status"].isin(["no_table", "excluded_non_country"])].copy()
    skip_df["reason"] = skip_df["report_status"].map({
        "no_table": "Step 1 found no DSA table",
        "excluded_non_country": "multi-country document",
    })
    skip_df[["pdf_file_name", "reason"]].sort_values("pdf_file_name").to_csv(
        check_dir / f"gapfill_skip_reports_{stamp}.csv", index=False, encoding="utf-8-sig"
    )

    staff_reports = list_staff_reports(staff_reports_dir)
    pub_year_idx = index_by_country_year(staff_reports)
    selected_index = index_selected_pdfs([Path(d) for d in selected_pdf_dirs])
    skip = set(skip_df["pdf_file_name"])
    gap_items = targets.to_dict("records")

    candidate_rows = build_candidate_map_rows(gap_items, pub_year_idx, skip)
    for row in candidate_rows:
        report = row.get("candidate_report")
        row["has_cached_selected_pdf"] = bool(report) and Path(report).stem in selected_index
    candidate_map = pd.DataFrame(candidate_rows)
    candidate_map.to_csv(check_dir / f"gapfill_candidate_map_{stamp}.csv", index=False, encoding="utf-8-sig")

    # Step 1's prediction (audit_fill_status, from the merged input CSV's own column_header_audit_json)
    # and the real candidate universe built here (every PDF actually found under STAFF_REPORTS_DIR) are
    # two different signals and can legitimately disagree -- a mismatch here is unusual (it means the
    # predicted report cannot be found as a real PDF at all) and worth a second look.
    has_real_candidate = {
        (r["country"], int(r["gap_year"])): bool(build_candidates(r["country"], int(r["gap_year"]), pub_year_idx, skip))
        for r in gap_items
    }
    targets["has_candidate_report"] = [
        has_real_candidate.get((r["country"], int(r["gap_year"])), False) for r in gap_items
    ]
    targets["audit_vs_real_candidate_mismatch"] = (
        (targets["audit_fill_status"] == "fillable_actual_column_visible") & (~targets["has_candidate_report"])
    )
    targets.to_csv(check_dir / f"gapfill_targets_{stamp}.csv", index=False, encoding="utf-8-sig")

    # build_candidate_map_rows() writes exactly one row (rank=None) for a gap year with no candidate at
    # all, and one row per candidate (rank=1, 2, ...) otherwise, so counting null ranks counts gap years.
    n_no_candidate = int(candidate_map["rank"].isna().sum()) if len(candidate_map) else 0
    n_mismatch = int(targets["audit_vs_real_candidate_mismatch"].sum())
    n_needs_fresh_locate = int((~candidate_map["has_cached_selected_pdf"]).sum()) if len(candidate_map) else 0
    print(f"gap years to fill: {len(targets)}")
    print(f"reports never used as a source: {len(skip_df)}")
    print(f"real staff-report PDFs found under {staff_reports_dir}: {len(staff_reports)}")
    print(f"gap years with no candidate report at all: {n_no_candidate}")
    print(f"candidate reports with no cached selected PDF (Step 3 will locate them fresh): {n_needs_fresh_locate} of {len(candidate_map)}")
    if n_mismatch:
        print(f"  WARNING: {n_mismatch} gap year(s) looked fillable in Step 1's preview but the predicted report "
              f"cannot be found as a real PDF under {staff_reports_dir} at all -- see "
              f"audit_vs_real_candidate_mismatch in gapfill_targets_{stamp}.csv, and check "
              f"audit_expected_source_report there for which report to go look for.")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--check-dir", default=None)
    ap.add_argument("--stamp", default=None)
    a, _ = ap.parse_known_args()  # tolerant of extra args injected by IPython/Spyder
    main(Path(a.check_dir) if a.check_dir else CHECK_DIR, a.stamp or STAMP)
