# Round1 Check Summary

**Round:** round1　**Run date:** 20260924　**Runs compared:** 3　**Generated:** 2026-09-27

**Run CSVs:**
- `dsa_decomposition_sl_round1_20260924_run1.csv`
- `dsa_decomposition_sl_round1_20260924_run2.csv`
- `dsa_decomposition_sl_round1_20260924_run3.csv`

Source: `round1_check_report_summary_20260924.csv`, `round1_check_matched_rows_20260924.csv`, `round1_check_value_diffs_20260924.csv`, `round1_check_fully_match_reports_20260924.json`, `round1_check_disagreement_reports_20260924.json` — all in `C:\Users\xli7\OneDrive - International Monetary Fund (PRD)\Shelley_My Projects\SFA\output\2006-2010\round1_check_20260924`.

---

## 1. Report-level summary

A report is one staff report PDF. See round1_check_disagreement_reports_20260924.json for the exact definitions used to sort a report into these buckets.

| Category | Reports | Share of total |
|---|---|---:|
| Total reports compared | 844 | 100.0% |
| Fully match | 304 | 36.0% |
| Disagreement (needs check) | 136 | 16.1% |
| No table found (all runs agree) | 402 | 47.6% |
| Extraction failed (every run) | 2 | 0.2% |

### 1.1 Detail (all 7 groups)

| Group | Reports | Share of total |
|---|---|---:|
| Fully match | 304 | 36.0% |
| Partial match (table & year agree, some rows differ) | 10 | 1.2% |
| table_found differs across runs | 58 | 6.9% |
| last_actual_year differs across runs | 63 | 7.5% |
| Report missing from at least one run | 5 | 0.6% |
| Extraction failed in every run (no *_dsa.json) | 2 | 0.2% |
| No table found, in every run | 402 | 47.6% |

---

## 2. Data-point-level summary

A data point is one row of the compiled CSV (one line item of one report's DSA decomposition). Reports in "No table found" and "Extraction failed" contribute 0 data points, since they have no comparable rows.

|  | Data points | Share of total |
|---|---|---:|
| Total data points compared | 6769 | 100.0% |
| Matched (identical across all runs) | 4901 | 72.4% |
| Differing | 1868 | 27.6% |

---

## 3. Why the differing data points differ

Breakdown of the 1868 differing data points by cause. "Value differs" is the only category where the two runs actually read the same cell of the same table and got a different number; the rest are the effect of a report-level disagreement (see Section 1) applied to every row of that report.

| Reason | Data points | Share of differing |
|---|---|---:|
| Whole report: last_actual_year differs across runs | 1025 | 54.9% |
| Whole report: table_found differs across runs | 751 | 40.2% |
| Whole report: missing from at least one run's CSV | 61 | 3.3% |
| Value differs (same table, same year, same row) | 27 | 1.4% |
| Row present in some runs but not others | 4 | 0.2% |
