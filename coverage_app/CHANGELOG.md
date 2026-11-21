# Changelog

The app's version is the first heading below. Each release is tagged in git as `app-v<version>`.

## 0.7.3 — 2026-11-20

- **Fixed**: On Windows, a job could stop with `PermissionError` ("Access is denied" / "used by another process") when it replaced one of its JSON files (progress, gap fill checkpoint, a report's answers) at the moment another program had it open: OneDrive syncing it, or the app reading the progress. Every such write now tries again for up to about 20 seconds; the progress file (`status.json`) never stops a job. Gap Fill's per-report answers are now written through a temporary file too. A job's progress is written at most once a second (Gap Fill logged dozens of lines a second, each one rewriting the progress file).

## 0.7.2 — 2026-11-20

- **Fixed**: Gap Fill's step 3 crashed on Windows right after "Loading the API and PDF helpers" (access violation in onnxruntime): PyMuPDF with the `pymupdf-layout` add-on loads onnxruntime on import, which crashes once pandas is loaded. Every job now loads PyMuPDF first (`runner.py`), the order Round One / Two already had.

## 0.7.1 — 2026-11-20

- **Fixed**: A job whose process dies without a Python error (a crash inside a C library, out of memory, a closed console) now says so on its card with the exit code and what it means, and the log ends with the Python stack of every thread at the moment of the crash (`faulthandler`), instead of only "The job's process ended without finishing".
- **Changed**: Gap Fill's step 3 logs "Loading the API and PDF helpers …" and "Signing in to the API …" before those steps, so a stop there shows in the log.

## 0.7.0 — 2026-11-20

- **Added**: **Human Review → *Drop this report***, next to *Skip for now*: for a report whose values cannot be used at all. Build panel then leaves out every row of it, also the rows the previous database has for it, and says how many it removed. Saving the report again with another choice undoes it. Dropped reports have their own status filter, a red mark in the list, and a column in Intermediate data.
- **Added**: **Human Review list: filter by kind of disagreement** (e.g. only *Some rows differ*), or *All except "No table in any run"*; it combines with the status filter and the search, and is remembered.

## 0.6.0 — 2026-11-18

- **Changed**: **One column layout for every source.** The panel database files (`panel_pregapfill_*`, `panel_gapfill_*`) now have the 43 columns of a Round One / Round Two run CSV (as `1b` writes them) + `source_round` + `gapfill_run` (+ `update_origin`, below) instead of 21. Round 1 and Round 2 rows keep all their columns; Round 3 (human review) rows keep the report's facts, table, page and column-header audit (`extraction_method = human_review`; the run's own year-choice fields are left blank, the reviewer's year is used); Gap Fill rows fill the report facts, table, page, page printed, column status and header, and the column-header audit (`actual_column_validation_status` = the gap's result, e.g. `resolved`), and take the report's title, date and number from the panel when the gap-fill call did not read them. See `code/final_schema.py`.
- **Changed**: **Year columns by stage.** Round 1, Round 2, Round 3 and the Pre Gap Fill file keep `last_actual_year` (the report's latest historical year). Gap Fill rows use `year` instead, and the panel database after Gap Fill (`panel_gapfill_*`) has only `year`, in the same position: a Round 1-3 row's `year` is its last actual year, a Gap Fill row's `year` is the gap year. A gap-filled panel used as the previous database of a new build is read back with `year` as `last_actual_year`. Coverage and Gap Fill read either column.
- **Added**: Column **`update_origin`** (last column) for updates: `previous` = a row taken over unchanged from the previous database (its Round 1-3 rows; its Gap Fill rows are always removed first), `new` = a row from this update (the new Round 1 / 2 / 3 results and this Gap Fill run). Build panel's *Check* shows both counts; the Panel database page can filter on it. The panel database files now have 46 columns.
- **Changed**: A merged file made before (21 columns, e.g. `final_all_batches_with_gapfill_20261028.csv`) still works as the previous database: the other columns stay blank for its rows.
- **Changed**: With the column-header audit now in the panel, Gap Fill's first step (4a) can say, for each gap, whether a later report shows that year as an actual column.

## 0.5.1 — 2026-11-18

- **Fixed**: After the computer restarts, a job that was running before is always shown as stopped or interrupted (so *Resume* is offered), even if its old process number now belongs to another program.

## 0.5.0 — 2026-11-17

- **Added**: **Resume** for Round One and Round Two. A version that stopped before it finished (*Stop*, the computer went to sleep or was shut down, the app was closed) shows how far each run got and a *▶ Resume* button, in the versions table and on the stopped job. Resume keeps the version, scripts, prompt and runs it was started with: in each run the reports that already have a result are not sent again, reports that only have an error are tried again, runs not started yet run in full; then every run is compiled and the runs compared. An unfinished comparison folder is moved aside as `<round>_check_<version>_incomplete_<time>`.
- **Changed**: `1a` and `2a` write each `*_dsa.json` through a temporary file, so a run stopped mid-write never leaves a cut-off file; both skip the reports already done when `SKIP_EXISTING` is set (the app sets it on Resume; the default stays off, so the `0_run_*.py` controllers work as before).

## 0.4.1 — 2026-11-17

- **Changed**: **Round Two** uses the new prompt `2a_dsa_prompt_20261117.txt` by default. Its script now reads landscape (rotated) pages in their displayed orientation, keeps table rows whose cells sit at slightly different heights on one line, and, when no public DSA table is found in the selected pages, tries the next candidate page range once.
- **Changed**: **Build panel**: the previous database comes from one place at a time (*The output folder*, *Another file* or *None*), and the chosen file's name is shown.

## 0.4.0 — 2026-11-16

- **Added**: **Version management**. The app's version shows at the top left of every page; click it for this changelog. Every record the app writes (coverage run records, `panel_<version>.json`, the Round One / Round Two run records) stores `app_version`, so each output says which version of the app built it.
- **Added**: **Build panel** step: the previous database (its Gap Fill rows removed) + the new Round 1 / Round 2 fully matched reports + the Round 3 reviewed reports of every batch ticked. *Check* shows what goes in; *Write* saves `panel_pregapfill_<version>.csv` to the output folder. A report already in the previous database: keep its rows, or replace them.
- **Changed**: **Gap Fill** starts from a pre-gap-fill file and takes its version. Answers saved by earlier runs are reused, so a report is not asked about the same year twice. *Write* saves `panel_gapfill_<version>.csv`.
- **Changed**: The **output folder** (Settings) holds only the two panel files per version plus `panel_<version>.json` (how it was built). **Panel database** and **Coverage** read from it.
- **Added**: **Intermediate data**: every round's results of every batch, and every panel build and gap fill run, to open or download as CSV.
- **Added**: Every *Browse…* button opens the computer's own folder or file dialog.

## 0.3.0 — 2026-11-13

- **Added**: The whole pipeline in one app (**DSA Database**): **Workflow** with Settings, Round One, Round Two, Human Review and Gap Fill, then **Panel database** and **Coverage**.
- **Added**: Round One and Round Two run the same scripts as the `0_run_*.py` controllers, in a separate process (`runner.py`), with progress, a log and *Stop*. *Review results* shows the fully matched reports and the ones with disagreement, every run side by side.
- **Added**: **Human Review**: one page per report the runs disagree on, with the selected PDF pages, the three runs' values and a *Final value* column.

## 0.2.0 — 2026-11-11

- **Changed**: Dashboard legend sits right under the chart; the plain gray part is called "Unavailable, other reasons".
- **Changed**: Wider layout on large screens (about 1.5x on an ultrawide monitor).
- **Added**: `how_it_works.html` and `browser_and_server_zh.html`: how the Generate button reaches Python, and where each part of the code is.

## 0.1.0 — 2026-11-11

- **Added**: First version of the coverage app: **Generate** (builds the country-year coverage database from the final CSV and the staff report folders, saved as a new version with its run record), **Database** (filter, pick fields, download) and **Dashboard**.
- **Added**: Dashboard: one stacked column per year for all 190 panel countries, split by source (Round 1 / Round 2 / Round 3 / Gap fill) or Unavailable, with a slicer per indicator and a T+1 … T+4 switch marking unavailable countries with no staff report in the following years.
