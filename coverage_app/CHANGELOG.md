# Changelog

The app's version is the first heading below. Each release is tagged in git as `app-v<version>`.

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
