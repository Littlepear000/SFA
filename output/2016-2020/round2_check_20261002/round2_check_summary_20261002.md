# Round2 Check Summary

**Round:** round2　**Run date:** 20261002　**Runs compared:** 3　**Generated:** 2026-10-02

**Run CSVs:**
- `dsa_decomposition_sl_round2_20261002_run1.csv`
- `dsa_decomposition_sl_round2_20261002_run2.csv`
- `dsa_decomposition_sl_round2_20261002_run3.csv`

Source: `round2_check_report_summary_20261002.csv`, `round2_check_matched_rows_20261002.csv`, `round2_check_value_diffs_20261002.csv`, `round2_check_fully_match_reports_20261002.json`, `round2_check_disagreement_reports_20261002.json` — all in `C:\Users\xli7\OneDrive - International Monetary Fund (PRD)\Shelley_My Projects\SFA\output\2016-2020\round2_check_20261002`.

---

## 1. Report-level summary

A report is one staff report PDF. See round2_check_disagreement_reports_20261002.json for the exact definitions used to sort a report into these buckets.

| Category | Reports | Share of total |
|---|---|---:|
| Total reports compared | 244 | 100.0% |
| Fully match | 54 | 22.1% |
| Disagreement (needs check) | 72 | 29.5% |
| No table found (all runs agree) | 111 | 45.5% |
| Extraction failed (every run) | 7 | 2.9% |

### 1.1 Detail (all 7 groups)

| Group | Reports | Share of total |
|---|---|---:|
| Fully match | 54 | 22.1% |
| Partial match (table & year agree, some rows differ) | 24 | 9.8% |
| table_found differs across runs | 5 | 2.0% |
| last_actual_year differs across runs | 17 | 7.0% |
| Report missing from at least one run | 26 | 10.7% |
| Extraction failed in every run (no *_dsa.json) | 7 | 2.9% |
| No table found, in every run | 111 | 45.5% |

---

## 2. Data-point-level summary

A data point is one row of the compiled CSV (one line item of one report's DSA decomposition). Reports in "No table found" and "Extraction failed" contribute 0 data points, since they have no comparable rows.

|  | Data points | Share of total |
|---|---|---:|
| Total data points compared | 2002 | 100.0% |
| Matched (identical across all runs) | 1117 | 55.8% |
| Differing | 885 | 44.2% |

---

## 3. Why the differing data points differ

Breakdown of the 885 differing data points by cause. "Value differs" is the only category where the two runs actually read the same cell of the same table and got a different number; the rest are the effect of a report-level disagreement (see Section 1) applied to every row of that report.

| Reason | Data points | Share of differing |
|---|---|---:|
| Whole report: missing from at least one run's CSV | 397 | 44.9% |
| Whole report: last_actual_year differs across runs | 283 | 32.0% |
| Value differs (same table, same year, same row) | 120 | 13.6% |
| Whole report: table_found differs across runs | 83 | 9.4% |
| Row present in some runs but not others | 2 | 0.2% |
