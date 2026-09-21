"""
Gap-year fill controller.

Runs the three gap-fill scripts, in this order, with runpy:
    1. 3a_gapfill_1_build_panel_gap_flags.py
       (read ONE compiled CSV -> find the gap years and build the country x year panel structure)
    2. 3b_gapfill_2_build_targets.py
       (turn the gap list into the task list for the API run)
    3. 3c_gapfill_3_run_api.py
       (call the API to read each gap year from the T+2 / T+3 staff reports, and fill the panel)

All settings shared by the three scripts are declared once, in the CONFIG section below.
Before running, comment out the CONFIG block of each script (the lines that define these names):
    in 3a: INPUT_CSV, OUT_DIR, STAMP
    in 3b: CHECK_DIR, STAMP
    in 3c: BASE_DIR, SELECTED_PDF_DIRS, STEP1_SCRIPT, GAPFILL_PROMPT_FILE, ENV_FILE, STAMP, CHECK_DIR,
           TARGETS_CSV, SKIP_CSV, PANEL_CSV, OUTPUT_DIR, MAX_WORKERS
Otherwise their own values overwrite the ones given here.

The scripts run in this same process, so command-line options are shared. 3c reads --dry-run,
--limit-gaps N, --countries "A,B" and --collect-only; 3a and 3b ignore options they do not know.
If any script stops with an error, the next one is not started.
"""
import runpy
from pathlib import Path

try:
    HERE = Path(__file__).resolve().parent
except NameError:  # run from an IPython / PyCharm console
    HERE = Path.cwd()

# =============================================================== CONFIG
BASE_DIR = Path(r"C:\Users\xli7\OneDrive - International Monetary Fund (PRD)\Shelley_My Projects\SFA")
BATCH = "2016-2020"
STAMP = "20260920_v2"  # version tag added to every file name written by 3a, 3b and 3c

# used by 3a: the ONE compiled CSV to analyse
INPUT_CSV = BASE_DIR / "output" / BATCH / "compiled_csv" / "dsa_decomposition_labels_2016-2020_sa.csv"

# where 3a writes the gap-year files, and where 3b and 3c read them
CHECK_DIR = BASE_DIR / "output" / BATCH / "gap_year_check"
OUT_DIR = CHECK_DIR  # the name 3a uses for the same folder

# used by 3c
# The "selected_pdf_pages" folders of the Step 1 runs to use, one per batch (edit: name the run folder you want to use).
# Step 1's *_timing.json files are looked up in the "json_output" folder next to each of these.
# For a report found in several folders the first one wins, so list round-2 folders BEFORE the round-1 folder of the same batch.
SELECTED_PDF_DIRS = [
    BASE_DIR / "output" / "2011-2015" / "round1_20260921_run1" / "selected_pdf_pages",
    BASE_DIR / "output" / "2016-2020" / "round2_20260921_run1" / "selected_pdf_pages",
    BASE_DIR / "output" / "2016-2020" / "round1_20260921_run1" / "selected_pdf_pages",
    BASE_DIR / "output" / "2021-2026" / "round1_20260921_run1" / "selected_pdf_pages",
]
STEP1_SCRIPT = HERE / "2a_step_1_revised_on_problematic_reports_sl.py"  # its API functions are reused by 3c
GAPFILL_PROMPT_FILE = BASE_DIR / "gapfill_extraction_prompt_v2.txt"
ENV_FILE = BASE_DIR / ".env"
TARGETS_CSV = CHECK_DIR / f"gapfill_targets_{STAMP}.csv"
SKIP_CSV = CHECK_DIR / f"gapfill_skip_reports_{STAMP}.csv"
PANEL_CSV = CHECK_DIR / f"panel_structure_country_year_{STAMP}.csv"  # None = do not build the filled panel
OUTPUT_DIR = BASE_DIR / "output" / "gapfill" / f"{BATCH}_{STAMP}"
MAX_WORKERS = 4
# ==============================================================================

SCRIPTS = [
    "3a_gapfill_1_build_panel_gap_flags.py",
    "3b_gapfill_2_build_targets.py",
    "3c_gapfill_3_run_api.py",
]

CONFIG = {
    "BASE_DIR": BASE_DIR,
    "STAMP": STAMP,
    "INPUT_CSV": INPUT_CSV,
    "CHECK_DIR": CHECK_DIR,
    "OUT_DIR": OUT_DIR,
    "SELECTED_PDF_DIRS": SELECTED_PDF_DIRS,
    "STEP1_SCRIPT": STEP1_SCRIPT,
    "GAPFILL_PROMPT_FILE": GAPFILL_PROMPT_FILE,
    "ENV_FILE": ENV_FILE,
    "TARGETS_CSV": TARGETS_CSV,
    "SKIP_CSV": SKIP_CSV,
    "PANEL_CSV": PANEL_CSV,
    "OUTPUT_DIR": OUTPUT_DIR,
    "MAX_WORKERS": MAX_WORKERS,
}

# ================================================================= RUN
for script in SCRIPTS:
    print(f"\n{'=' * 78}\nRunning {script}\n{'=' * 78}", flush=True)
    runpy.run_path(str(HERE / script), init_globals=CONFIG, run_name="__main__")

print("\nAll scripts finished.")
