"""
Round 2 controller.

Runs the round-2 scripts, in this order, with runpy. The pair 2a + 1b is repeated N_RUNS times, then 1c
compares the runs:
    1. 2a_step_1_revised_on_problematic_reports_sl.py
       (re-run the revised extraction on the reports in REPORT_LIST_FILE -> one *_dsa.json per report,
        plus the selected PDF pages; if REPORT_LIST_FILE is None it re-runs the whole batch)
    2. 1b_json_to_excel_dsa_v6_flexible_actual.py
       (merge the *_dsa.json files written by 2a -> one compiled CSV)
    3. 1c_round_check_compare_runs.py   (once, after all runs; the same script as in round 1)
       (compare the compiled CSVs of the runs of RUN_DATE -> matched rows, and the reports to check again)

The reports to re-run come from the Round 1 check: REPORT_LIST_FILE is its
round1_check_disagreement_reports_<ROUND1_RUN_DATE>.json (run the round-1 controller first).

Every run uses exactly the same prompt and settings; the repeated runs are meant to test how stable the
model output is. Each run writes to its own folder, so nothing is overwritten:

    output/<BATCH>/round2_<RUN_DATE>_run<N>/
        json_output/          all JSON files written by 2a (*_dsa.json, *_step1_locator.json, *_timing.json, *_ERROR.json, RUN_SUMMARY.json)
        selected_pdf_pages/   the selected PDF pages written by 2a
        compiled_csv/         the compiled CSV written by 1b: dsa_decomposition_<CSV_PREFIX>_round2_<RUN_DATE>_run<N>.csv
    output/<BATCH>/round2_check_<RUN_DATE>/
        the result of 1c (fully-match list, matched rows, reports to check again, differing rows, report summary)

All settings shared by the scripts are declared once, in the CONFIG section below.
Before running, comment out the CONFIG block at the top of 2a and of 1b:
    in 2a: the lines that define BASE_DIR, PDF_DIR, OUTPUT_DIR, SELECTED_PDF_DIR, PROMPT_FILE, ENV_FILE,
           REPORT_LIST_FILE, REPORT_LIST_CATEGORY and RERUN_OUTPUT_DIR
    in 1b: the lines that define BASE_DIR, JSON_DIR and OUTPUT_FILE
    in 1c: the CONFIG block (the lines from BASE_DIR to CHECK_DIR)
Otherwise their own values overwrite the ones given here.

1c compares every run folder of RUN_DATE that it finds in the batch folder, so runs made in an earlier
session (see FIRST_RUN_NO below) are included too.

Nothing is started if one of the run folders, or the round2_check folder, already exists. If a script stops with an error, the
controller stops: the next script and the remaining runs are not started. To carry on after a failure,
delete the unfinished run folder and set FIRST_RUN_NO to that run number (and N_RUNS to the number left).
"""
import re
import runpy
from pathlib import Path
from typing import Optional

# =============================================================== CONFIG
BASE_DIR = Path(r"C:\Users\xli7\OneDrive - International Monetary Fund (PRD)\Shelley_My Projects\SFA")
BATCH = "2016-2020"

ROUND1_RUN_DATE = "20260921"  # the Round 1 runs and check whose disagreement list is re-run here
RUN_DATE = "20260921"         # date of THIS round; set by hand; goes into the run folder and CSV names
N_RUNS = 3             # how many times to repeat 2a + 1b
FIRST_RUN_NO = 1       # number of the first run (folders are named run1, run2, ...)
CSV_PREFIX = "sl"      # compiled CSV: dsa_decomposition_<CSV_PREFIX>_round2_<RUN_DATE>_run<N>.csv

# used by 2a
PDF_DIR = BASE_DIR / "staff_reports" / "pdf staff reports" / BATCH
PROMPT_FILE = BASE_DIR / "sl_revised_prompt_step_one.txt"
ENV_FILE = BASE_DIR / ".env"

# Only the reports listed in this JSON file are re-processed: the result of the Round 1 check. None = the whole batch.
REPORT_LIST_FILE: Optional[Path] = (
    BASE_DIR / "output" / BATCH / f"round1_check_{ROUND1_RUN_DATE}" / f"round1_check_disagreement_reports_{ROUND1_RUN_DATE}.json"
)
# The list has two categories. None = both; "category_a_disagreement" = only the reports whose runs disagreed;
# "category_b_no_table_in_all_runs" = only the reports for which no run found a table.
REPORT_LIST_CATEGORY: Optional[str] = None
# ==============================================================================

SCRIPTS = [
    "2a_step_1_revised_on_problematic_reports_sl.py",
    "1b_json_to_excel_dsa_v6_flexible_actual.py",
]
SCRIPT_CHECK = "1c_round_check_compare_runs.py"

# ================================================================= RUN
try:
    HERE = Path(__file__).resolve().parent
except NameError:  # run from an IPython / PyCharm console
    HERE = Path.cwd()

BATCH_DIR = BASE_DIR / "output" / BATCH
run_dirs = {n: BATCH_DIR / f"round2_{RUN_DATE}_run{n}" for n in range(FIRST_RUN_NO, FIRST_RUN_NO + N_RUNS)}

check_dir = BATCH_DIR / f"round2_check_{RUN_DATE}"
existing = [d for d in [*run_dirs.values(), check_dir] if d.exists()]
if existing:
    raise SystemExit("Nothing was started. These folders already exist:\n  " + "\n  ".join(map(str, existing)))

for run_no, run_dir in run_dirs.items():
    json_dir = run_dir / "json_output"
    config = {
        "BASE_DIR": BASE_DIR,
        "PDF_DIR": PDF_DIR,
        "PROMPT_FILE": PROMPT_FILE,
        "ENV_FILE": ENV_FILE,
        "REPORT_LIST_FILE": REPORT_LIST_FILE,
        "REPORT_LIST_CATEGORY": REPORT_LIST_CATEGORY,
        "OUTPUT_DIR": json_dir,                                  # 2a: JSON files (used when REPORT_LIST_FILE is None)
        "RERUN_OUTPUT_DIR": json_dir,                            # 2a: JSON files (used when REPORT_LIST_FILE is set)
        "SELECTED_PDF_DIR": run_dir / "selected_pdf_pages",      # 2a: selected PDF pages
        "JSON_DIR": json_dir,                                    # 1b: reads the JSON files of this run
        "OUTPUT_FILE": run_dir / "compiled_csv" / f"dsa_decomposition_{CSV_PREFIX}_round2_{RUN_DATE}_run{run_no}.csv",
    }
    print(f"\n{'#' * 78}\n# Run {run_no} of {FIRST_RUN_NO + N_RUNS - 1}: {run_dir}\n{'#' * 78}", flush=True)
    for script in SCRIPTS:
        print(f"\n{'=' * 78}\nRunning {script}\n{'=' * 78}", flush=True)
        runpy.run_path(str(HERE / script), init_globals=config, run_name="__main__")
    print(f"\nRun {run_no} finished: {len(list(json_dir.glob('*_dsa.json')))} *_dsa.json, "
          f"{len(list(json_dir.glob('*_ERROR.json')))} *_ERROR.json, CSV: {config['OUTPUT_FILE']}", flush=True)

print("\nAll runs finished:\n  " + "\n  ".join(map(str, run_dirs.values())))

# ---- compare the runs (every run folder of RUN_DATE found in the batch folder)
run_csvs = sorted(
    BATCH_DIR.glob(f"round2_{RUN_DATE}_run*/compiled_csv/dsa_decomposition_{CSV_PREFIX}_round2_{RUN_DATE}_run*.csv"),
    key=lambda p: int(re.search(r"_run(\d+)\.csv$", p.name).group(1)),
)
print(f"\n{'=' * 78}\nRunning {SCRIPT_CHECK}\n{'=' * 78}", flush=True)
runpy.run_path(str(HERE / SCRIPT_CHECK), init_globals={"ROUND": "round2", "RUN_CSVS": run_csvs, "CHECK_DIR": check_dir, "RUN_DATE": RUN_DATE}, run_name="__main__")
