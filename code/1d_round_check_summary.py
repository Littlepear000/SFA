"""
Round check summary: turn the output of 1c_round_check_compare_runs.py into one Markdown file of tables,
for direct citation (e.g. in a paper). Read-only: no comparison is redone here. Every number in this file is
read straight from 1c's own output files, so it always agrees with them; if 1c is rerun, rerun this too.

Input (read from CHECK_DIR, the folder 1c wrote into; <ROUND> is round1 or round2)
    <ROUND>_check_fully_match_reports_<RUN_DATE>.json    for the run metadata and the 7-way group counts
    <ROUND>_check_disagreement_reports_<RUN_DATE>.json   for the disagreement / no-table / extraction-failed counts
    <ROUND>_check_report_summary_<RUN_DATE>.csv           for a cross-check of the report total
    <ROUND>_check_matched_rows_<RUN_DATE>.csv             row count = matched data points
    <ROUND>_check_value_diffs_<RUN_DATE>.csv              row count = differing data points, and diff_type breakdown

Output (written to CHECK_DIR)
    <ROUND>_check_summary_<RUN_DATE>.md, with these tables:
        1. report-level headline: total / fully match / disagreement / no table (all runs agree) / extraction failed
        2. report-level detail: the 7 groups 1c uses internally
        3. data-point-level headline: total / matched / differing (a data point = one row of the compiled CSV)
        4. why the differing data points differ (diff_type: value / missing_row / table_found_differs /
           last_actual_year_differs / missing_in_run)
    "Data point" and "report" are two different units throughout; see the note under table 3.

When run by a controller, comment out the CONFIG block below (BASE_DIR ... CHECK_DIR): the controller provides
ROUND, RUN_DATE and CHECK_DIR. To run it on its own, edit the CONFIG block and run the file; run 1c first.
Re-running this script overwrites its own .md file (cheap to regenerate; nothing else is touched).
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict

import pandas as pd

# =============================================================== CONFIG
# BASE_DIR = Path(r"C:\Users\xli7\OneDrive - International Monetary Fund (PRD)\Shelley_My Projects\SFA")
# BATCH = "2011-2015"
# ROUND = "round1"  # "round1" or "round2"
# RUN_DATE = "20260921"
# CHECK_DIR = BASE_DIR / "output" / BATCH / f"{ROUND}_check_{RUN_DATE}"
# ==============================================================================

GROUP_LABELS = {
    "fully_match": "Fully match",
    "partial_match": "Partial match (table & year agree, some rows differ)",
    "table_found_differs": "table_found differs across runs",
    "last_actual_year_differs": "last_actual_year differs across runs",
    "missing_in_run": "Report missing from at least one run",
    "extraction_failed_in_all_runs": "Extraction failed in every run (no *_dsa.json)",
    "no_table_in_all_runs": "No table found, in every run",
}
DIFF_TYPE_LABELS = {
    "value": "Value differs (same table, same year, same row)",
    "missing_row": "Row present in some runs but not others",
    "table_found_differs": "Whole report: table_found differs across runs",
    "last_actual_year_differs": "Whole report: last_actual_year differs across runs",
    "missing_in_run": "Whole report: missing from at least one run's CSV",
}


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Required 1c output not found: {path}\nRun 1c_round_check_compare_runs.py for this ROUND/RUN_DATE first.")
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"Required 1c output not found: {path}\nRun 1c_round_check_compare_runs.py for this ROUND/RUN_DATE first.")
    return pd.read_csv(path, dtype=str, encoding="utf-8-sig")


def pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.1f}%" if whole else "n/a"


def table(headers, rows) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * (len(headers) - 1) + "---:|"]
    for r in rows:
        lines.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(lines)


def main() -> None:
    check_dir = Path(CHECK_DIR)
    p = lambda name: check_dir / f"{ROUND}_check_{name}_{RUN_DATE}"

    fully_match = read_json(p("fully_match_reports").with_suffix(".json"))
    disagreement = read_json(p("disagreement_reports").with_suffix(".json"))
    summary = read_csv(p("report_summary").with_suffix(".csv"))
    matched_rows = read_csv(p("matched_rows").with_suffix(".csv"))
    value_diffs = read_csv(p("value_diffs").with_suffix(".csv"))

    meta = fully_match["meta"]
    n_reports = meta["n_reports_total"]
    if len(summary) != n_reports:
        raise SystemExit(
            f"Inconsistent 1c output: {p('report_summary')} has {len(summary)} rows but "
            f"{p('fully_match_reports')} reports n_reports_total = {n_reports}. Rerun 1c before this script."
        )
    counts = meta["counts_by_group"]  # already in the fixed group order 1c used, preserved through JSON

    n_fully_match = counts.get("fully_match", 0)
    n_no_table = counts.get("no_table_in_all_runs", 0)
    n_extraction_failed = counts.get("extraction_failed_in_all_runs", 0)
    n_disagreement = disagreement[  # category_a_disagreement's own count, for a second, independent cross-check
        [k for k in disagreement if k.startswith("category_a_")][0]
    ]["count"]
    computed_disagreement = n_reports - n_fully_match - n_no_table - n_extraction_failed
    if n_disagreement != computed_disagreement:
        raise SystemExit(
            f"Inconsistent 1c output: category_a_disagreement count ({n_disagreement}) does not equal "
            f"n_reports_total - fully_match - no_table_in_all_runs - extraction_failed_in_all_runs "
            f"({computed_disagreement}). Rerun 1c before this script."
        )

    n_matched_points = len(matched_rows)
    n_diff_points = len(value_diffs)
    n_points = n_matched_points + n_diff_points
    diff_type_counts = value_diffs["diff_type"].value_counts() if n_diff_points else pd.Series(dtype=int)

    headline_rows = [
        ("Total reports compared", n_reports, "100.0%"),
        ("Fully match", n_fully_match, pct(n_fully_match, n_reports)),
        ("Disagreement (needs check)", n_disagreement, pct(n_disagreement, n_reports)),
        ("No table found (all runs agree)", n_no_table, pct(n_no_table, n_reports)),
        ("Extraction failed (every run)", n_extraction_failed, pct(n_extraction_failed, n_reports)),
    ]
    detail_rows = [(GROUP_LABELS.get(g, g), n, pct(n, n_reports)) for g, n in counts.items()]
    point_rows = [
        ("Total data points compared", n_points, "100.0%"),
        ("Matched (identical across all runs)", n_matched_points, pct(n_matched_points, n_points)),
        ("Differing", n_diff_points, pct(n_diff_points, n_points)),
    ]
    reason_rows = [
        (DIFF_TYPE_LABELS.get(t, t), int(c), pct(int(c), n_diff_points))
        for t, c in diff_type_counts.items()
    ]

    md = f"""# {ROUND.capitalize()} Check Summary

**Round:** {ROUND}　**Run date:** {RUN_DATE}　**Runs compared:** {meta['n_runs']}　**Generated:** {date.today().isoformat()}

**Run CSVs:**
{chr(10).join(f"- `{c}`" for c in meta['run_csvs'])}

Source: `{p('report_summary').with_suffix('.csv').name}`, `{p('matched_rows').with_suffix('.csv').name}`, `{p('value_diffs').with_suffix('.csv').name}`, `{p('fully_match_reports').with_suffix('.json').name}`, `{p('disagreement_reports').with_suffix('.json').name}` — all in `{check_dir}`.

---

## 1. Report-level summary

A report is one staff report PDF. See {p('disagreement_reports').with_suffix('.json').name} for the exact definitions used to sort a report into these buckets.

{table(["Category", "Reports", "Share of total"], headline_rows)}

### 1.1 Detail (all 7 groups)

{table(["Group", "Reports", "Share of total"], detail_rows)}

---

## 2. Data-point-level summary

A data point is one row of the compiled CSV (one line item of one report's DSA decomposition). Reports in "No table found" and "Extraction failed" contribute 0 data points, since they have no comparable rows.

{table(["", "Data points", "Share of total"], point_rows)}

---

## 3. Why the differing data points differ

Breakdown of the {n_diff_points} differing data points by cause. "Value differs" is the only category where the two runs actually read the same cell of the same table and got a different number; the rest are the effect of a report-level disagreement (see Section 1) applied to every row of that report.

{table(["Reason", "Data points", "Share of differing"], reason_rows) if n_diff_points else "*No differing data points.*"}
"""
    out_path = p("summary").with_suffix(".md")
    out_path.write_text(md, encoding="utf-8")
    print(f"Written: {out_path}")
    print(f"Reports: {n_reports} total, {n_fully_match} fully match, {n_disagreement} disagreement, "
          f"{n_no_table} no table, {n_extraction_failed} extraction failed")
    print(f"Data points: {n_points} total, {n_matched_points} matched, {n_diff_points} differing")


if __name__ == "__main__":
    main()
