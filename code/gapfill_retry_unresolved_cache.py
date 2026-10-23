"""
[gapfill maintenance] Clear the per-report cache for gap years that ended "unresolved", so the next real
run gives them a fresh chance instead of silently reusing stale, possibly bug-affected results.
    Run by hand | no API call | only edits reports/*.json cache files under OUTPUT_DIR

Why this exists
    3c_gapfill_3_run_api.py caches every candidate attempt's result in
    OUTPUT_DIR/reports/<report>_gapfill.json (per_target[year]), so a report already tried is never
    re-called on a later run -- except for api_error/not_run, which are deliberately left uncached so
    they retry automatically. A gap year whose status is "unresolved" (every candidate was tried and
    none gave an actual/historical value) IS fully cached, though, so a plain rerun reuses that same
    verdict forever, even after a bug in candidate discovery or the selected-PDF cache (e.g. the
    SELECTED_PDF_DIRS auto-discovery fix) is corrected. This script clears exactly those entries -- and
    only those -- so the next run re-tries them with the current, fixed code.

What it does NOT do
    - Touch resolved / resolved_with_warning gap years (their cache is left exactly as-is).
    - Touch unresolved_no_candidate_reports gap years (nothing was ever attempted for them, so there is
      nothing to clear; they are already a no-op here and get recomputed fresh on the next run anyway).
    - Call the API itself. It only edits cache files; 3c_gapfill_3_run_api.py does the real re-extraction
      on its next run.
    - Touch any OTHER gap year's cache entry in a report that is shared across several gap years (a
      report can legitimately be the source for more than one year) -- only the specific
      (report, year) pairs that belong to an unresolved gap year are removed.

Input (from OUTPUT_DIR, for the given STAMP)
    gapfill_resolution_<STAMP>.csv   which gap years ended unresolved / unresolved_no_candidate_reports
    gapfill_attempts_<STAMP>.csv     which reports were actually tried for each of those gap years
    reports/<report>_gapfill.json   the cache files edited in place

Usage
    python gapfill_retry_unresolved_cache.py --output-dir <OUTPUT_DIR> --stamp <STAMP>
    Then just run 3c_gapfill_3_run_api.py (or the controller) again as usual.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

RETRY_STATUSES = {"unresolved", "unresolved_no_candidate_reports"}


def main(output_dir: Path, stamp: str) -> None:
    output_dir = Path(output_dir)
    resolution = pd.read_csv(output_dir / f"gapfill_resolution_{stamp}.csv")
    attempts = pd.read_csv(output_dir / f"gapfill_attempts_{stamp}.csv")

    retry_keys = {
        (r["country"], int(r["gap_year"]))
        for _, r in resolution[resolution["final_status"].isin(RETRY_STATUSES)].iterrows()
    }
    print(f"Gap years marked for retry (unresolved / no candidate reports): {len(retry_keys)}")

    to_clear = attempts[attempts.apply(
        lambda r: (r["country"], int(r["gap_year"])) in retry_keys, axis=1
    )][["report", "gap_year"]].drop_duplicates()

    reports_dir = output_dir / "reports"
    n_cleared, n_files = 0, 0
    for report, group in to_clear.groupby("report"):
        p = reports_dir / f"{Path(report).stem}_gapfill.json"
        if not p.exists():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        per_target = data.get("per_target", {})
        changed = False
        for y in group["gap_year"]:
            key = str(int(y))
            if key in per_target:
                del per_target[key]
                n_cleared += 1
                changed = True
        if changed:
            p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            n_files += 1

    print(f"Cache entries cleared: {n_cleared}, across {n_files} report file(s) under {reports_dir}")
    print("Resolved / resolved_with_warning gap years were not touched. Run 3c again to retry the rest.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--stamp", required=True)
    args = ap.parse_args()
    main(Path(args.output_dir), args.stamp)
