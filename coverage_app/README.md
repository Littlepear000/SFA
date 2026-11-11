# DSA coverage app

A small local web app to generate the country-year coverage database and look at it.

## Start

```
coverage_app\start.bat           # Windows: double-click it in Explorer
coverage_app/start.command       # macOS: double-click it in Finder; in its Terminal window r+Enter restarts, q+Enter quits
python coverage_app/server.py    # any system, from the project folder
```

The browser opens at <http://127.0.0.1:8765>. Stop with Ctrl+C. Options: `--port 8800`, `--no-browser`.
Nothing to install beyond what the project already uses (pandas, openpyxl); the page has no external
scripts, so it works offline. It only listens on 127.0.0.1.

## Tabs

- **Generate**: set the final CSV and the staff-report PDF folder, tick the batch folders, choose a stamp
  and press *Generate coverage database*. This runs `code/check_coverage_database.py` and saves a new
  version. The **version history** below lists every version with the time it was built and the final
  CSV it used (path, size, last-modified time, short SHA-256) and the PDF folders.
- **Database**: browse the chosen version: filter by country and year; pick the columns with *Fields*;
  download the workbook.
- **Dashboard**: one stacked column per year, all 190 panel countries, split by where the value of the
  indicator in the slicer came from (Round 1 / Round 2 / Round 3 / Gap fill) or *Unavailable*. The
  *T+1 … T+4* switch at the top right splits Unavailable again: hatched = no staff report of that
  country published in any of the years T+1 … T+k; the count is shown above each column, and clicking a
  column lists those countries. Needs a version generated with the Sources and Report years sheets
  (older versions show *has a value* only, and check later reports within the panel years only).

## Where the versions live

`OUT_DIR` of `code/check_coverage_database.py` (`output/coverage/`). Each version is two files:

- `coverage_database_<STAMP>.xlsx`: the database (Coverage, By year, Indicators, Notes sheets)
- `coverage_database_<STAMP>.json`: the run record shown in the version history

Runs from the command line (`python code/check_coverage_database.py`) write the same two files, so
they show up in the app too. A stamp that already exists gets `_2`, `_3` … in the app, so a version is
never overwritten.
