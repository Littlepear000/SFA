"""
Round 1 controller.

Runs the round-1 scripts, in this order, with runpy. The pair 1a + 1b is repeated N_RUNS times, then 1c
compares the runs:
    1. 1a_two_step_selected_pdf_inline_base64_cropfallback_summary_v7_header_aware_crop_effort.py
       (extract the DSA table of every staff report -> one *_dsa.json per report, plus the selected PDF pages)
    2. 1b_json_to_excel_dsa_v6_flexible_actual.py
       (merge all *_dsa.json files -> one compiled CSV)
    3. 1c_round_check_compare_runs.py   (once, after all runs)
       (compare the compiled CSVs of the runs of RUN_DATE -> matched rows, and the reports to check again)

Every run uses exactly the same prompt and settings; the repeated runs are meant to test how stable the
model output is. Each run writes to its own folder, so nothing is overwritten:

    output/<BATCH>/round1_<RUN_DATE>_run<N>/
        json_output/          all JSON files written by 1a (*_dsa.json, *_step1_locator.json, *_timing.json, *_ERROR.json, RUN_SUMMARY.json)
        selected_pdf_pages/   the selected PDF pages written by 1a
        compiled_csv/         the compiled CSV written by 1b: dsa_decomposition_<CSV_PREFIX>_round1_<RUN_DATE>_run<N>.csv
    output/<BATCH>/round1_check_<RUN_DATE>/
        the result of 1c (fully-match list, matched rows, reports to check again, differing rows, report summary)

All settings shared by the scripts are declared once, in the CONFIG section below.
Before running, comment out the CONFIG block at the top of 1a and of 1b (the lines that define
BASE_DIR, PDF_DIR, OUTPUT_DIR, SELECTED_PDF_DIR, PROMPT_FILE, ENV_FILE in 1a, and
BASE_DIR, JSON_DIR, OUTPUT_FILE in 1b), and the CONFIG block of 1c (the lines from BASE_DIR to CHECK_DIR).
Otherwise their own values overwrite the ones given here.

1c compares every run folder of RUN_DATE that it finds in the batch folder, so runs made in an earlier
session (see FIRST_RUN_NO below) are included too.

Nothing is started if one of the run folders, or the round1_check folder, already exists. If a script stops with an error, the
controller stops: the next script and the remaining runs are not started. To carry on after a failure,
delete the unfinished run folder and set FIRST_RUN_NO to that run number (and N_RUNS to the number left).
"""
import re
import runpy
from pathlib import Path

# =============================================================== CONFIG
BASE_DIR = Path(r"C:\Users\xli7\OneDrive - International Monetary Fund (PRD)\Shelley_My Projects\SFA")
BATCH = "2011-2015"

RUN_DATE = "20260921"  # set by hand; goes into the run folder and CSV names
N_RUNS = 3             # how many times to repeat 1a + 1b
FIRST_RUN_NO = 1       # number of the first run (folders are named run1, run2, ...)
CSV_PREFIX = "sl"      # compiled CSV: dsa_decomposition_<CSV_PREFIX>_round1_<RUN_DATE>_run<N>.csv

# used by 1a
PDF_DIR = BASE_DIR / "staff_reports" / "pdf staff reports" / BATCH
PROMPT_FILE = BASE_DIR / "two_step_selected_pdf_prompt_table_only_cropfallback_v5_flexible_actual.txt"
ENV_FILE = BASE_DIR / ".env"
# ==============================================================================

SCRIPTS = [
    "1a_two_step_selected_pdf_inline_base64_cropfallback_summary_v7_header_aware_crop_effort.py",
    "1b_json_to_excel_dsa_v6_flexible_actual.py",
]
SCRIPT_CHECK = "1c_round_check_compare_runs.py"

# ================================================================= RUN
try:
    HERE = Path(__file__).resolve().parent
except NameError:  # run from an IPython / PyCharm console
    HERE = Path.cwd()

BATCH_DIR = BASE_DIR / "output" / BATCH
run_dirs = {n: BATCH_DIR / f"round1_{RUN_DATE}_run{n}" for n in range(FIRST_RUN_NO, FIRST_RUN_NO + N_RUNS)}

check_dir = BATCH_DIR / f"round1_check_{RUN_DATE}"
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
        "OUTPUT_DIR": json_dir,                                  # 1a: JSON files
        "SELECTED_PDF_DIR": run_dir / "selected_pdf_pages",      # 1a: selected PDF pages
        "JSON_DIR": json_dir,                                    # 1b: reads the JSON files of this run
        "OUTPUT_FILE": run_dir / "compiled_csv" / f"dsa_decomposition_{CSV_PREFIX}_round1_{RUN_DATE}_run{run_no}.csv",
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
    BATCH_DIR.glob(f"round1_{RUN_DATE}_run*/compiled_csv/dsa_decomposition_{CSV_PREFIX}_round1_{RUN_DATE}_run*.csv"),
    key=lambda p: int(re.search(r"_run(\d+)\.csv$", p.name).group(1)),
)
print(f"\n{'=' * 78}\nRunning {SCRIPT_CHECK}\n{'=' * 78}", flush=True)
runpy.run_path(str(HERE / SCRIPT_CHECK), init_globals={"ROUND": "round1", "RUN_CSVS": run_csvs, "CHECK_DIR": check_dir, "RUN_DATE": RUN_DATE}, run_name="__main__")
