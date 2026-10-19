# Round2 Check Summary

**Round:** round2　**Run date:** 20260927　**Runs compared:** 3　**Generated:** 2026-09-28

**Run CSVs:**
- `dsa_decomposition_sl_round2_20260927_run1.csv`
- `dsa_decomposition_sl_round2_20260927_run2.csv`
- `dsa_decomposition_sl_round2_20260927_run3.csv`

Source: `round2_check_report_summary_20260927.csv`, `round2_check_matched_rows_20260927.csv`, `round2_check_value_diffs_20260927.csv`, `round2_check_fully_match_reports_20260927.json`, `round2_check_disagreement_reports_20260927.json` — all in `C:\Users\xli7\OneDrive - International Monetary Fund (PRD)\Shelley_My Projects\SFA\output\2006-2010\round2_check_20260927`.

---

## 1. Report-level summary

A report is one staff report PDF. See round2_check_disagreement_reports_20260927.json for the exact definitions used to sort a report into these buckets.

| Category | Reports | Share of total |
|---|---|---:|
| Total reports compared | 540 | 100.0% |
| Fully match | 78 | 14.4% |
| Disagreement (needs check) | 75 | 13.9% |
| No table found (all runs agree) | 386 | 71.5% |
| Extraction failed (every run) | 1 | 0.2% |

### 1.1 Detail (all 7 groups)

| Group | Reports | Share of total |
|---|---|---:|
| Fully match | 78 | 14.4% |
| Partial match (table & year agree, some rows differ) | 6 | 1.1% |
| table_found differs across runs | 31 | 5.7% |
| last_actual_year differs across runs | 38 | 7.0% |
| Report missing from at least one run | 0 | 0.0% |
| Extraction failed in every run (no *_dsa.json) | 1 | 0.2% |
| No table found, in every run | 386 | 71.5% |

---

## 2. Data-point-level summary

A data point is one row of the compiled CSV (one line item of one report's DSA decomposition). Reports in "No table found" and "Extraction failed" contribute 0 data points, since they have no comparable rows.

|  | Data points | Share of total |
|---|---|---:|
| Total data points compared | 2327 | 100.0% |
| Matched (identical across all runs) | 1279 | 55.0% |
| Differing | 1048 | 45.0% |

---

## 3. Why the differing data points differ

Breakdown of the 1048 differing data points by cause. "Value differs" is the only category where the two runs actually read the same cell of the same table and got a different number; the rest are the effect of a report-level disagreement (see Section 1) applied to every row of that report.

| Reason | Data points | Share of differing |
|---|---|---:|
| Whole report: last_actual_year differs across runs | 618 | 59.0% |
| Whole report: table_found differs across runs | 403 | 38.5% |
| Value differs (same table, same year, same row) | 23 | 2.2% |
| Row present in some runs but not others | 4 | 0.4% |
