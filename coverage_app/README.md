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
  every line item is kept. Saved per report in `output/<batch>/round3_review_<version>/reviews/`.
- **Build panel**: previous database (any merged CSV, e.g. the last gap-filled file; its Gap Fill rows are
  removed, because a new staff report may now give those years directly) + the new Round 1 / Round 2 fully
  matched reports + the Round 3 reviewed reports, of every batch ticked. *Check* shows what goes in;
  *Write* saves `panel_pregapfill_<version>.csv` (version = YYYYMMDD_HHMM) to the **output folder**.
  A report in both the previous database and the new results: keep the previous rows, or replace them.
- **Gap Fill**: starts from a pre-gap-fill file of the output folder and takes its version. Every country
  x every year in the range (2001-2025 by default). *Find the gaps* (4a + 4b, no API), then *Fill the gaps*
  (4c); answers saved by earlier gap fill runs are reused, so a report is not asked about the same year
  twice. *Write* saves `panel_gapfill_<version>.csv` (same version) to the output folder.

Year columns: Round 1-3 and `panel_pregapfill_*` have `last_actual_year` (each report's latest historical
year); Gap Fill rows and `panel_gapfill_*` have `year` instead (for a Round 1-3 row, its last actual year;
for a Gap Fill row, the gap year), with no `last_actual_year`.

The output folder (Settings) only receives these two files per version, plus `panel_<version>.json`
(how the version was built). The **Panel database** and **Coverage** pages read from that same folder.

## Intermediate data

Every round's results of every batch, as kept in `output/<batch>/` (Round 1, Round 2, Round 3 review),
plus every panel build and gap fill run: open them, or download them as CSV. They are not written to the
output folder.

## Panel database

Shows one file of the output folder (the newest by default): totals, country-years by year and source, and
the rows (filter by country, year, source, hierarchy id). The folder can be changed here (it is the same
setting as in Settings). Every *Browse…* button opens the computer's own folder / file dialog.

## Coverage

- **Database**: *Generate a coverage version* (top, folded) builds the country-year coverage table from the
  newest file of the output folder (or another file you pick) and the staff report folders, and saves a new version; the version history is below it.
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

## Versions

The app's version is the first `## X.Y.Z — YYYY-MM-DD` heading of `CHANGELOG.md` (read by `version.py`).
It shows next to *DSA Database* at the top left (click it for the changelog), is printed when the server
starts, and is stored as `app_version` in every record the app writes: the coverage run records
(`coverage_database_<STAMP>.json`), `panel_<version>.json`, and the Round One / Round Two run records.

When you change the app:

1. Add a line under the top version of `CHANGELOG.md` (**Added** / **Changed** / **Fixed**: what changed, in words a user would use).
2. For a release, start a new heading at the top: the last number up for fixes and small changes
   (0.4.0 → 0.4.1), the middle number up for new features (0.4.0 → 0.5.0).
3. Commit, then tag that commit and push the tag:
   ```
   git tag app-v0.5.0 && git push origin master app-v0.5.0
   ```
   `git tag -l "app-v*"` lists every release; `git checkout app-v0.4.0` goes back to one.
