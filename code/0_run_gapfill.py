"""
Gap-year fill controller.

Runs the three gap-fill scripts, in this order, with runpy:
    1. 3a_gapfill_1_build_panel_gap_flags.py
       (read ONE compiled CSV -> find the gap years and build the country x year panel structure)
    2. 3b_gapfill_2_build_targets.py
       (turn the gap list into the task list for the API run)
    3. 3c_gapfill_3_run_api.py
       (call the API to read each gap year from the T+2 / T+3 / T+4 staff reports, and fill the panel)

All settings shared by the three scripts are declared once, in the CONFIG section below.
Before running, comment out the CONFIG block of each script (the lines that define these names):
    in 3a: INPUT_CSV, OUT_DIR, STAMP
    in 3b: CHECK_DIR, STAMP, STAFF_REPORTS_DIR, SELECTED_PDF_DIRS
    in 3c: BASE_DIR, STAFF_REPORTS_DIR, SELECTED_PDF_DIRS, STEP1_SCRIPT, STEP1_PROMPT_FILE,
           GAPFILL_PROMPT_FILE, ENV_FILE, STAMP, CHECK_DIR, TARGETS_CSV, SKIP_CSV, PANEL_CSV,
           OUTPUT_DIR, MAX_WORKERS
Otherwise their own values overwrite the ones given here.
3b now also builds and persists the Step 2 candidate map (gapfill_candidate_map_<STAMP>.csv), so it
needs the same STAFF_REPORTS_DIR and SELECTED_PDF_DIRS as 3c: the candidate universe is every real PDF
under STAFF_REPORTS_DIR (batch-agnostic); SELECTED_PDF_DIRS only says which of them already have a
cached selected PDF from Step 1 -- a candidate without one is located fresh by 3c, not skipped.

The scripts run in this same process, so command-line options are shared. 3c reads --dry-run,
--limit-gaps N, --countries "A,B" and --collect-only; 3a and 3b ignore options they do not know.
If any script stops with an error, the next one is not started.
"""
import runpy
from pathlib import Path

# =============================================================== CONFIG
BASE_DIR = Path(r"C:\Users\xli7\OneDrive - International Monetary Fund (PRD)\Shelley_My Projects\SFA")
try:
    HERE = Path(__file__).resolve().parent
except NameError:  # run from an IPython / PyCharm console: look for the code folder
    HERE = next((c for c in (Path.cwd(), Path.cwd() / "code", BASE_DIR / "code") if (c / "3a_gapfill_1_build_panel_gap_flags.py").exists()),
                BASE_DIR / "code")

BATCH = "2016-2020"
STAMP = "202601020_test2"  # version tag added to every file name written by 3a, 3b and 3c

# used by 3a: the ONE compiled CSV to analyse
INPUT_CSV = BASE_DIR / "output" / BATCH / "round1_check_20261002" / "round1_check_matched_rows_20261002.csv"

# where 3a writes the gap-year files, and where 3b and 3c read them
CHECK_DIR = BASE_DIR / "output" / BATCH / "gap_year_check"
OUT_DIR = CHECK_DIR  # the name 3a uses for the same folder

# used by 3b and 3c
# Root of the ORIGINAL staff-report PDFs, one subfolder per batch -- the candidate universe. Every real
# PDF found under here counts as a T+2/T+3/T+4 candidate, whether or not Step 1 ever located a table in it
# in any run, and regardless of which batch it is in (a candidate from an adjacent batch is found the
# same way as one from the batch being checked). Not added to git; local-only on this Mac.
STAFF_REPORTS_DIR = BASE_DIR / "staff_reports" / "pdf staff reports"

# used by 3c
# The "selected_pdf_pages" folders of the Step 1 runs to use, one per batch (edit: name the run folder you want to use).
# Step 1's *_timing.json files are looked up in the "json_output" folder next to each of these.
# For a report found in several folders the first one wins, so list round-2 folders BEFORE the round-1 folder of the same batch.
# Only used as a fast-path cache check (does this candidate already have a selected PDF from Step 1) --
# STAFF_REPORTS_DIR above decides what counts as a candidate, not this.
SELECTED_PDF_DIRS = [
    BASE_DIR / "output" / "2011-2015" / "round1_20260921_run1" / "selected_pdf_pages",
    BASE_DIR / "output" / "2016-2020" / "round2_20260921_run1" / "selected_pdf_pages",
    BASE_DIR / "output" / "2016-2020" / "round1_20260921_run1" / "selected_pdf_pages",
    BASE_DIR / "output" / "2021-2026" / "round1_20260921_run1" / "selected_pdf_pages",
]
STEP1_SCRIPT = HERE / "1a_two_step_selected_pdf_inline_base64_cropfallback_summary_v7_header_aware_crop_effort.py"
# 1a on purpose, not 2a: gap-fill only needs call_pdf_json / make_api_session / add_table_crop_header_instruction,
# identical in both; 2a's extra accuracy is specifically about *choosing* last_actual_year, which gap-fill
# never does (the target year is already given). See 3c_gapfill_3_run_api.py's own CONFIG for the same note.
STEP1_PROMPT_FILE = BASE_DIR / "two_step_selected_pdf_prompt_table_only_cropfallback_v5_flexible_actual.txt"
# only SUBPROMPT 1 (the locator) is used from this file -- when a candidate has no cached selected PDF,
# 3c reuses 1a's own locate-the-DSA-pages step fresh against the original PDF instead of skipping it.
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
    "STAFF_REPORTS_DIR": STAFF_REPORTS_DIR,
    "SELECTED_PDF_DIRS": SELECTED_PDF_DIRS,
    "STEP1_SCRIPT": STEP1_SCRIPT,
    "STEP1_PROMPT_FILE": STEP1_PROMPT_FILE,
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
