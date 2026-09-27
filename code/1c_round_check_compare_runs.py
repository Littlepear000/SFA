"""
Round check: compare the compiled CSVs of the repeated runs of one round (round1 or round2).
The same script serves both rounds; ROUND ("round1" / "round2") only changes the folder and file names.

Input
    RUN_CSVS   the compiled CSV of every run of the round (run1, run2, ...). They all have the same columns.
               Any number of runs >= 2 works.

What is compared, report by report (a report = one staff report PDF, key = json_file)
    - is the report present in every run's CSV
    - table_found
    - last_actual_year (a fiscal-year label such as 2012/13 counts as its end year, 2013)
    - every decomposition line item, lined up by hierarchy_id: is the row present in every run,
      and is its value the same (compared as numbers: 0.0 = -0.0, 1 = 1.0, empty = empty)
    Not compared: label text (spelling / symbol differences are ignored), confidence, manual_review_required,
    extraction_notes, extraction_method, the column-header audit and the other validation fields.
    Rows are lined up by hierarchy_id, so a line item that one run reads as an extra row shifts the ids of
    the rows after it inside that category; those rows are then reported as differing (never missed).

Every report ends up in exactly one of these groups
    fully_match                    table found in every run, same last actual year, every row identical
    partial_match                  table found in every run, same last actual year, but some rows differ
                                   or are missing in some run
    table_found_differs            some runs found the table and some did not
    last_actual_year_differs       the runs chose different last actual years
    missing_in_run                 the report is absent from the CSV of at least one run
    extraction_failed_in_all_runs  no run produced a *_dsa.json for this report at all (each run's json_output
                                   folder has a *_ERROR.json instead). Found separately from every other group:
                                   a report like this never appears in any run's compiled CSV (1a/1b skip it
                                   silently), so it would otherwise vanish from this comparison without a trace.
    no_table_in_all_runs           every run's *_dsa.json says table_found = false (needs a check as well)

Rows are split in two, so that matched rows + differing rows together cover every row of a report:
    matched rows    fully_match reports: all rows.  partial_match reports: the rows that are identical in every run.
                    (Nothing is kept from the other groups: a different year or table means the runs did not read
                    the same column, so equal numbers there would be coincidence.)
    differing rows  partial_match reports: the rows that differ.  table_found_differs, last_actual_year_differs and
                    missing_in_run reports: all their rows.

Output (all in CHECK_DIR; <ROUND> is round1 or round2; file names end with _<RUN_DATE>)
    <ROUND>_check_fully_match_reports_<RUN_DATE>.json     PDF file names of the fully_match reports
    <ROUND>_check_matched_rows_<RUN_DATE>.csv             the matched rows, taken from run 1, same format as the run CSVs
    <ROUND>_check_disagreement_reports_<RUN_DATE>.json    reports to check again; usable as REPORT_LIST_FILE of 2a
                                                         (category_a_disagreement, category_b_no_table_in_all_runs,
                                                          category_c_extraction_failed_in_all_runs)
    <ROUND>_check_value_diffs_<RUN_DATE>.csv              the differing rows with the value of every run
    <ROUND>_check_report_summary_<RUN_DATE>.csv           one row per report: its group and why. For
                                                         extraction_failed_in_all_runs rows, error_by_run holds
                                                         each run's *_ERROR.json message (found by scanning each
                                                         run's json_output folder; not derived from the CSVs).

When it is run by a controller (0_run_1a_1b.py or 0_run_2a_1b.py), comment out the CONFIG block below
(BASE_DIR ... CHECK_DIR): the controller provides ROUND, RUN_CSVS, CHECK_DIR and RUN_DATE.
To run it on its own, edit the CONFIG block and run the file.
Nothing is written if CHECK_DIR already holds files.
"""
from __future__ import annotations

import json
import re
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

# =============================================================== CONFIG
# BASE_DIR = Path(r"C:\Users\xli7\OneDrive - International Monetary Fund (PRD)\Shelley_My Projects\SFA")
# BATCH = "2011-2015"
# ROUND = "round1"  # "round1" or "round2"
# RUN_DATE = "20260921"
# CSV_PREFIX = "sl"
# BATCH_DIR = BASE_DIR / "output" / BATCH
# RUN_CSVS = sorted(
#     BATCH_DIR.glob(f"{ROUND}_{RUN_DATE}_run*/compiled_csv/dsa_decomposition_{CSV_PREFIX}_{ROUND}_{RUN_DATE}_run*.csv"),
#     key=lambda p: int(re.search(r"_run(\d+)\.csv$", p.name).group(1)),
# )
# CHECK_DIR = BATCH_DIR / f"{ROUND}_check_{RUN_DATE}"
# ==============================================================================

SOURCE_RUN_INDEX = 0  # the matched rows are taken from this run (0 = the first run)
NUMBER_TOLERANCE = 1e-9
REQUIRED_COLUMNS = ["json_file", "pdf_file_name", "table_found", "last_actual_year",
                    "top_category", "hierarchy_id", "label_verbatim", "value"]

CATEGORY_A = "category_a_disagreement"
CATEGORY_B = "category_b_no_table_in_all_runs"
CATEGORY_C = "category_c_extraction_failed_in_all_runs"
GROUP_ORDER = ["fully_match", "partial_match", "table_found_differs", "last_actual_year_differs",
               "missing_in_run", "extraction_failed_in_all_runs", "no_table_in_all_runs"]
SUMMARY_COLUMNS = ["json_file", "pdf_file_name", "country", "group", "needs_check", "runs_present",
                   "table_found_by_run", "last_actual_year_by_run", "rows_compared", "rows_matching",
                   "rows_differing", "error_by_run"]


# ------------------------------------------------------------ normalisation
def norm_bool(v: Any) -> Optional[bool]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip().upper()
    return True if s == "TRUE" else False if s == "FALSE" else None


def norm_year(v: Any) -> Optional[str]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    text = re.sub(r"\s+", " ", str(v)).strip()
    if not text or text.lower() == "nan":
        return None
    m = re.fullmatch(r"(?:FY\s?)?(\d{4})\s*[/-]\s*(\d{2}|\d{4})", text, flags=re.I)
    if m:
        a = int(m.group(1))
        b = int(m.group(2)) if len(m.group(2)) == 4 else int(str(a)[:2] + m.group(2))
        return str(b) if b - a == 1 else text.lower()
    m = re.fullmatch(r"(?:FY\s?)?(\d{4})", text, flags=re.I)
    return m.group(1) if m else text.lower()


def norm_value(v: Any):
    """None for an empty cell, a float for a number, otherwise the cleaned text."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    if not s or s.lower() == "nan":
        return None
    try:
        return float(s.replace(",", "").replace("\u2212", "-").replace("\u2013", "-"))
    except ValueError:
        return re.sub(r"\s+", " ", s).lower()


def same(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) <= NUMBER_TOLERANCE
    return a == b


def hid_key(h: str):
    return [int(p) if p.isdigit() else p for p in str(h).split(".")]


# --------------------------------------------------------------------- data
def read_run(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{path.name} lacks the columns {missing}")
    return df


def index_run(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """json_file -> report-level facts and its line items (hierarchy_id -> row facts)."""
    out: Dict[str, Dict[str, Any]] = {}
    for jf, g in df.groupby("json_file", sort=False):
        first = g.iloc[0]
        rows = {}
        for r in g[g["top_category"].notna()].to_dict("records"):
            rows[str(r["hierarchy_id"])] = {
                "top": r["top_category"], "label": r["label_verbatim"],
                "raw": r["value"], "value": norm_value(r["value"]),
            }
        out[jf] = {
            "pdf": first["pdf_file_name"], "country": first.get("country"),
            "table_found": norm_bool(first["table_found"]), "year": norm_year(first["last_actual_year"]),
            "year_raw": first["last_actual_year"], "rows": rows,
        }
    return out


def compare_rows(jf: str, runs: List[Dict[str, Any]], report_group: Optional[str]):
    """
    Line-by-line comparison of one report.
    Returns (matched hierarchy ids, list of differing-row records, number of rows compared).
    report_group is set for reports whose rows are all reported as differing (different table_found / year,
    or missing in a run); the rows are then listed with that group as their diff_type.
    """
    n = len(runs)
    rows = [(r["rows"] if r is not None else {}) for r in runs]
    hids = sorted({h for rr in rows for h in rr}, key=hid_key)
    matched, diffs = [], []
    for h in hids:
        entries = [rr.get(h) for rr in rows]
        present = [e is not None for e in entries]
        values = [e["value"] if e else None for e in entries]
        if not all(present):
            row_type = "missing_row"
        elif len({e["top"] for e in entries}) > 1:
            row_type = "category"
        elif not all(same(values[0], v) for v in values[1:]):
            row_type = "value"
        else:
            row_type = None
        if row_type is None and report_group is None:
            matched.append(h)
            continue
        first = next(e for e in entries if e)
        rec: Dict[str, Any] = {
            "key": f"{jf}||{h}", "json_file": jf,
            "pdf_file_name": next((r["pdf"] for r in runs if r is not None), None),
            "country": next((r["country"] for r in runs if r is not None), None),
            "top_category": first["top"],
        }
        for i in range(n):
            rec[f"label_run{i + 1}"] = entries[i]["label"] if entries[i] else None
        for i in range(n):
            v = values[i]  # a number, or the printed text if the cell is not a number, or None
            rec[f"value_run{i + 1}"] = str(entries[i]["raw"]).strip() if isinstance(v, str) else v
        pair_flags = []
        for i, j in combinations(range(n), 2):
            ok = (present[i] == present[j]) and same(values[i], values[j])
            rec[f"run{i + 1}_run{j + 1}_match"] = ok
            pair_flags.append(ok)
        rec["all_match"] = all(pair_flags)
        nums = [v for v in values if isinstance(v, float)]
        rec["max_abs_diff"] = (max(nums) - min(nums)) if len(nums) >= 2 else None
        rec["diff_type"] = report_group if report_group else row_type
        diffs.append(rec)
    return matched, diffs, len(hids)


def check_reports(dfs: List[pd.DataFrame]):
    indexes = [index_run(df) for df in dfs]
    all_jfs: List[str] = []
    seen = set()
    for idx in indexes:
        for jf in idx:
            if jf not in seen:
                seen.add(jf)
                all_jfs.append(jf)

    summary, diff_rows, matched_keys = [], [], set()
    for jf in all_jfs:
        runs = [idx.get(jf) for idx in indexes]
        present = [r is not None for r in runs]
        tf = [r["table_found"] if r else None for r in runs]
        yr = [r["year"] if r else None for r in runs]
        info = next(r for r in runs if r)
        n_union, n_match, n_diff = 0, 0, 0
        if not all(present):
            group, report_group = "missing_in_run", "missing_in_run"
        elif len(set(tf)) > 1 or None in tf:
            group, report_group = "table_found_differs", "table_found_differs"
        elif tf[0] is False:
            group, report_group = "no_table_in_all_runs", None
        elif len(set(yr)) > 1:
            group, report_group = "last_actual_year_differs", "last_actual_year_differs"
        else:
            group, report_group = None, None

        if group != "no_table_in_all_runs":
            matched, diffs, n_union = compare_rows(jf, runs, report_group)
            n_match, n_diff = len(matched), len(diffs)
            diff_rows.extend(diffs)
            if group is None:
                group = "fully_match" if not diffs else "partial_match"
                matched_keys.update((jf, h) for h in matched)
        summary.append({
            "json_file": jf, "pdf_file_name": info["pdf"], "country": info["country"], "group": group,
            "needs_check": "No" if group == "fully_match" else "Yes",
            "runs_present": "|".join("yes" if p else "no" for p in present),
            "table_found_by_run": "|".join("" if t is None else str(t) for t in tf),
            "last_actual_year_by_run": "|".join(y or "" for y in yr),
            "rows_compared": n_union, "rows_matching": n_match, "rows_differing": n_diff,
            "error_by_run": "",
        })
    return pd.DataFrame(summary, columns=SUMMARY_COLUMNS), diff_rows, matched_keys


# --------------------------------------------------- reports missing from every run's CSV
def error_folder(csv_path: Path) -> Path:
    """The json_output folder of the run whose compiled CSV is csv_path (run_dir/compiled_csv/x.csv)."""
    return Path(csv_path).parent.parent / "json_output"


def find_extraction_failures(run_csv_paths: List[Path], known_json_files: set) -> pd.DataFrame:
    """
    Reports that never produced a *_dsa.json in ANY run, so check_reports() never sees them (it only reads the
    compiled CSVs, and 1b silently drops a report that has no *_dsa.json). Found here by scanning each run's
    json_output folder for a *_ERROR.json whose report is not in known_json_files (the json_file values that
    check_reports() did find, i.e. that succeeded in at least one run).
    """
    per_run_errors: List[Dict[str, str]] = []
    for csv_path in run_csv_paths:
        folder = error_folder(csv_path)
        if not folder.exists():
            print(f"  NOTE: {folder} not found; cannot check it for extraction failures.")
        errs: Dict[str, str] = {}
        for p in sorted(folder.glob("*_ERROR.json")):
            stem = p.name[: -len("_ERROR.json")]
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                msg = str(data.get("error") or "").strip()
            except (json.JSONDecodeError, OSError) as exc:
                msg = f"(could not read {p.name}: {exc})"
            errs[stem] = msg or "(no error message)"
        per_run_errors.append(errs)

    stems = sorted({s for errs in per_run_errors for s in errs})
    rows = []
    for stem in stems:
        jf = f"{stem}_dsa.json"
        if jf in known_json_files:
            continue  # it succeeded in at least one other run; already covered by check_reports()
        m = re.match(r"^(.+?)_\d{4}-\d{2}-\d{2}", stem)
        country_guess = m.group(1) if m else None
        error_by_run = " | ".join(
            f"run{i + 1}: {errs[stem]}" if stem in errs else f"run{i + 1}: (no _ERROR.json or _dsa.json found)"
            for i, errs in enumerate(per_run_errors)
        )
        rows.append({
            "json_file": jf, "pdf_file_name": f"{stem}.pdf", "country": country_guess,
            "group": "extraction_failed_in_all_runs", "needs_check": "Yes",
            "runs_present": "|".join("no" for _ in per_run_errors),
            "table_found_by_run": "|".join("" for _ in per_run_errors),
            "last_actual_year_by_run": "|".join("" for _ in per_run_errors),
            "rows_compared": 0, "rows_matching": 0, "rows_differing": 0,
            "error_by_run": error_by_run,
        })
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


# ------------------------------------------------------------------- output
def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    if len(RUN_CSVS) < 2:
        raise SystemExit(f"Need at least 2 run CSVs to compare, found {len(RUN_CSVS)}: {[str(p) for p in RUN_CSVS]}")
    missing = [p for p in RUN_CSVS if not Path(p).exists()]
    if missing:
        raise SystemExit("These run CSVs do not exist:\n  " + "\n  ".join(map(str, missing)))
    out_dir = Path(CHECK_DIR)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit(f"Nothing was written: {out_dir} already holds files.")
    out_dir.mkdir(parents=True, exist_ok=True)

    run_names = [Path(p).name for p in RUN_CSVS]
    print(f"Comparing {len(RUN_CSVS)} runs:\n  " + "\n  ".join(run_names))
    dfs = [read_run(Path(p)) for p in RUN_CSVS]
    cols = list(dfs[0].columns)
    for name, d in zip(run_names[1:], dfs[1:]):
        if list(d.columns) != cols:
            raise SystemExit(f"{name} does not have the same columns as {run_names[0]}.")

    summary, diff_rows, matched_keys = check_reports(dfs)
    fails = find_extraction_failures(RUN_CSVS, set(summary["json_file"]))
    if len(fails):
        print(f"  {len(fails)} report(s) never produced a *_dsa.json in any run (see extraction_failed_in_all_runs)")
        summary = pd.concat([summary, fails], ignore_index=True)
    counts = {g: int((summary["group"] == g).sum()) for g in GROUP_ORDER}
    n_runs = len(RUN_CSVS)
    meta_common = {
        "round": ROUND, "run_date": RUN_DATE, "n_runs": n_runs, "run_csvs": run_names,
        "n_reports_total": int(len(summary)), "counts_by_group": counts,
        "compared": "presence in every run, table_found, last_actual_year, and every line item (row present, value equal), lined up by hierarchy_id",
        "not_compared": "label text, confidence, manual_review_required, extraction_notes, extraction_method, audit and validation fields",
    }

    # 1. fully match reports (JSON)
    full = summary[summary["group"] == "fully_match"]
    write_json(out_dir / f"{ROUND}_check_fully_match_reports_{RUN_DATE}.json", {
        "meta": {**meta_common, "n_fully_match": int(len(full))},
        "fully_match_reports": full["pdf_file_name"].tolist(),
    })

    # 2. matched rows (CSV, same format as the run CSVs, taken from the source run)
    src = dfs[SOURCE_RUN_INDEX]
    keep = pd.MultiIndex.from_frame(src[["json_file", "hierarchy_id"]]).isin(matched_keys)
    src[keep].to_csv(out_dir / f"{ROUND}_check_matched_rows_{RUN_DATE}.csv", index=False, encoding="utf-8-sig")

    # 3. reports to check again (JSON, readable by 2a as REPORT_LIST_FILE)
    def entries(sub: pd.DataFrame):
        return [{"json_file": r.json_file, "pdf_file_name": r.pdf_file_name, "country": r.country, "group": r.group,
                 "rows_differing": int(r.rows_differing)} for r in sub.itertuples()]
    a = summary[summary["group"].isin(["partial_match", "table_found_differs", "last_actual_year_differs", "missing_in_run"])]
    b = summary[summary["group"] == "no_table_in_all_runs"]
    c = summary[summary["group"] == "extraction_failed_in_all_runs"]
    write_json(out_dir / f"{ROUND}_check_disagreement_reports_{RUN_DATE}.json", {
        "meta": {**meta_common, "n_to_check": int(len(a) + len(b) + len(c)), "matched_rows_source_run": run_names[SOURCE_RUN_INDEX]},
        CATEGORY_A: {
            "description": "Reports where the runs disagree: some rows differ (partial_match), a different table_found or "
                           "last_actual_year, or the report is missing from a run's CSV.",
            "count": int(len(a)), "reports": entries(a),
        },
        CATEGORY_B: {
            "description": "Reports for which no run found a DSA table.",
            "count": int(len(b)), "reports": entries(b),
        },
        CATEGORY_C: {
            "description": "Reports for which no run produced a successful extraction (*_dsa.json); each run's "
                           "json_output folder has a *_ERROR.json for them instead. See error_by_run in the "
                           "report summary CSV for the failure reason.",
            "count": int(len(c)), "reports": entries(c),
        },
    })

    # 4. differing rows (CSV)
    label_cols = [f"label_run{i + 1}" for i in range(n_runs)]
    value_cols = [f"value_run{i + 1}" for i in range(n_runs)]
    pair_cols = [f"run{i + 1}_run{j + 1}_match" for i, j in combinations(range(n_runs), 2)]
    diff_cols = ["key", "json_file", "pdf_file_name", "country", "top_category"] + label_cols + value_cols + pair_cols \
                + ["all_match", "max_abs_diff", "diff_type"]
    pd.DataFrame(diff_rows, columns=diff_cols).to_csv(
        out_dir / f"{ROUND}_check_value_diffs_{RUN_DATE}.csv", index=False, encoding="utf-8-sig")

    # 5. one row per report
    summary.to_csv(out_dir / f"{ROUND}_check_report_summary_{RUN_DATE}.csv", index=False, encoding="utf-8-sig")

    print(f"\n{len(summary)} reports compared. Output folder: {out_dir}")
    for g in GROUP_ORDER:
        print(f"  {g:<26} {counts[g]}")
    print(f"  matched rows: {int(keep.sum())} | differing rows: {len(diff_rows)}")


if __name__ == "__main__":
    main()
