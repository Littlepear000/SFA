**Fill gap years prompt**

**Research Project: Detecting and Filling Year Gaps in SFA Panel Data from IMF Staff Reports**

**Background**
I am working on a research project on Stock Flow Adjustment (SFA). I have been extracting time-series data from IMF staff reports across many countries and many years, then consolidating them into a panel dataset (the "Output file").

**Why Gaps Occur**
Gaps arise because of the staggered publication schedule of staff reports. For example:
- Country A's 2023 staff report reports actual data only up to 2021.
- Country A's 2024 staff report reports actual data up to 2023.

As a result, Country A's 2022 data is missing from the panel — a gap in the middle of an otherwise continuous series.

**Task 1: Detect Gap Years**
1. Read the existing Output (panel) file 'Data/2021-2026 staff reports/DSA tables'.
2. For **each country individually**, identify its own start year and end year based on the data actually present. **Do not** require all countries to share the same start or end year — panel lengths may differ across countries.
3. Within each country's own range, detect any **interior missing years** (gaps). A year is a gap only if it falls strictly between that country's earliest and latest available years. Leading or trailing missing years (before the first observation or after the last) are **not** considered gaps and should be left as-is.
4. Produce a list of all (country, gap_year) pairs.

**Task 2: Fill the Gaps**
- 'Data/2021-2026 staff reports/staff_reports_pdfs' is where all staff reports are stored.
- For each detected (country, gap_year = T):
  1. Locate that country's **T+1** and **T+2** staff reports within the provided directory.
  2. Extract the Year T actual data from those reports. The T+2 report typically contains the finalized actual figure for Year T; the T+1 report may contain a preliminary or estimated figure.
  3. Prefer the T+2 report's actual value when both are available. If only T+1 has it, use that and mark it as preliminary.
  4. If neither report contains the value, leave it as missing and flag it as unfilled.

**Task 3: Flagging**
- Add a column (e.g., `filled_flag` / `data_source`) to the output indicating, for every observation:
  - Whether it was originally present, backfilled from T+2, backfilled from T+1 (preliminary), or still unfilled.
  - The source staff report year for any backfilled value.
- Provide a separate summary listing every backfilled and every unfilled (country, year) pair.

**Deliverable**
- Output the gap-filled panel to a **new CSV file**, named descriptively (e.g., `sfa_panel_filled_YYYYMMDD.csv`).
- Preserve the original panel structure and all original values; only add the filled values and the flagging column.
- Include the summary of flagged observations alongside or within the output.

---

Ready to paste. Want me to adjust anything before you send it off?