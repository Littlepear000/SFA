# DSA web app

A local web app for the whole pipeline: run Round 1 and Round 2, review their results, do the human review
(Round 3), build the panel database, fill the gap years, and look at coverage.

## Start

```
coverage_app\start.bat           # Windows: double-click it in Explorer
coverage_app/start.command       # macOS: double-click it in Finder; in its Terminal window r+Enter restarts, q+Enter quits
python coverage_app/server.py    # any system, from the project folder
```

The browser opens at <http://127.0.0.1:8765>. Stop with Ctrl+C. Options: `--port 8800`, `--no-browser`.
Nothing to install beyond what the project already uses (pandas, openpyxl); the page has no external
scripts, so it works offline. It only listens on 127.0.0.1.

## Workflow

One tab per step; the strip under the steps shows the current panel database and what is ready to append.

- **Settings**: the PDF folder of the batch to read (its name is the batch name; results go to
  `output/<batch>/`), the root folder holding every batch's PDFs (Gap Fill and the review pages look there),
  the `.env` file, the CSV name prefix. Saved in `output/workflow/settings.json`.
- **Round One / Round Two**: pick the Python files and the prompt (each has a *View* button), the version
  (the date, YYYYMMDD) and the number of runs (default 3), then *Run*. The app runs the same scripts the
  `0_run_*.py` controllers run, in a separate process (`coverage_app/runner.py`), with the same folders:
  `round1_<version>_run<N>/` and `round1_check_<version>/`. Progress, a log and a *Stop* button show on the
  page. Round Two re-reads the reports to check again from a chosen Round One version.
  *Review results* opens a version: **Fully matched** reports with their six top-level values, and reports
  **With disagreement** with every run side by side (click a row).
- **Human Review**: the reports Round Two's runs still disagree on, one page each: the selected PDF pages
  (or the original PDF at the table's page), the three runs' values, and a *Final value* column. Click a
  run's value (or a run's column header) to take it, edit, add or leave out line items. The hierarchy id of
  every line item is kept. Saved per report in `output/<batch>/round3_review_<version>/reviews/`, and all
  reviewed rows in `round3_reviewed_rows_<version>.csv`.
  **Ready to append** (same page): Round 1 fully matched + Round 2 fully matched + Round 3 reviewed, in the
  same 21 columns (`code/final_schema.py`), appended as a new version of the panel database.
- **Gap Fill**: works on the panel database: every country x every year in the range (2001-2025 by
  default), including years before a country's first report or after its last one. *Find the gaps*
  (4a + 4b, no API), then *Fill the gaps* (4c; a dry run and a limit are available). The gap map turns green
  as gap years are filled. *Append* adds the filled rows (`gapfill_rows_final_<version>.csv`, same 21
  columns) as a new panel database version.

## Panel database

Every version of the merged database, `output/panel_database/panel_database_<STAMP>.csv` (+ `.json`: when,
from which version, what was added). Browse, filter, download. Start it from an existing merged CSV
(*Import*), e.g. `output/final/final_all_batches_with_gapfill_20261028.csv`.

## Coverage

- **Database**: *Generate a coverage version* (top, folded) builds the country-year coverage table from the
  panel database and the staff report folders, and saves a new version; the version history is below it.
  Browse a version: filter by country and year; pick the columns with *Fields*; download the workbook.
- **Dashboard**: one stacked column per year, all 190 panel countries, split by where the value of the
  indicator in the slicer came from (Round 1 / Round 2 / Round 3 / Gap fill) or *Unavailable*. The
  *T+1 … T+4* switch at the top right splits Unavailable again: hatched = no staff report of that
  country published in any of the years T+1 … T+k; the count is shown above each column, and clicking a
  column lists those countries.

## Where the versions live

`OUT_DIR` of `code/check_coverage_database.py` (`output/coverage/`). Each version is two files:

- `coverage_database_<STAMP>.xlsx`: the database (Coverage, By year, Indicators, Notes sheets)
- `coverage_database_<STAMP>.json`: the run record shown in the version history

Runs from the command line (`python code/check_coverage_database.py`) write the same two files, so
they show up in the app too. A stamp that already exists gets `_2`, `_3` … in the app, so a version is
never overwritten.
