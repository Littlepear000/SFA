# Round1 Check Summary

**Round:** round1　**Run date:** 20261016　**Runs compared:** 3　**Generated:** 2026-10-17

**Run CSVs:**
- `dsa_decomposition_sl_round1_20261016_run1.csv`
- `dsa_decomposition_sl_round1_20261016_run2.csv`
- `dsa_decomposition_sl_round1_20261016_run3.csv`

Source: `round1_check_report_summary_20261016.csv`, `round1_check_matched_rows_20261016.csv`, `round1_check_value_diffs_20261016.csv`, `round1_check_fully_match_reports_20261016.json`, `round1_check_disagreement_reports_20261016.json` — all in `C:\Users\xli7\OneDrive - International Monetary Fund (PRD)\Shelley_My Projects\SFA\output\2021-2026\round1_check_20261016`.

---

## 1. Report-level summary

A report is one staff report PDF. See round1_check_disagreement_reports_20261016.json for the exact definitions used to sort a report into these buckets.

| Category | Reports | Share of total |
|---|---|---:|
| Total reports compared | 1060 | 100.0% |
| Fully match | 845 | 79.7% |
| Disagreement (needs check) | 96 | 9.1% |
| No table found (all runs agree) | 117 | 11.0% |
| Extraction failed (every run) | 2 | 0.2% |

### 1.1 Detail (all 7 groups)

| Group | Reports | Share of total |
|---|---|---:|
| Fully match | 845 | 79.7% |
| Partial match (table & year agree, some rows differ) | 61 | 5.8% |
| table_found differs across runs | 2 | 0.2% |
| last_actual_year differs across runs | 27 | 2.5% |
| Report missing from at least one run | 6 | 0.6% |
| Extraction failed in every run (no *_dsa.json) | 2 | 0.2% |
| No table found, in every run | 117 | 11.0% |

---

## 2. Data-point-level summary

A data point is one row of the compiled CSV (one line item of one report's DSA decomposition). Reports in "No table found" and "Extraction failed" contribute 0 data points, since they have no comparable rows.

|  | Data points | Share of total |
|---|---|---:|
| Total data points compared | 14947 | 100.0% |
| Matched (identical across all runs) | 14085 | 94.2% |
| Differing | 862 | 5.8% |

---

## 3. Why the differing data points differ

Breakdown of the 862 differing data points by cause. "Value differs" is the only category where the two runs actually read the same cell of the same table and got a different number; the rest are the effect of a report-level disagreement (see Section 1) applied to every row of that report.

| Reason | Data points | Share of differing |
|---|---|---:|
| Whole report: last_actual_year differs across runs | 428 | 49.7% |
| Value differs (same table, same year, same row) | 281 | 32.6% |
| Whole report: missing from at least one run's CSV | 96 | 11.1% |
| Whole report: table_found differs across runs | 33 | 3.8% |
| Row present in some runs but not others | 24 | 2.8% |
