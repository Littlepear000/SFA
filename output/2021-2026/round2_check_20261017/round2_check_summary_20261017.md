# Round2 Check Summary

**Round:** round2　**Run date:** 20261017　**Runs compared:** 3　**Generated:** 2026-10-18

**Run CSVs:**
- `dsa_decomposition_sl_round2_20261017_run1.csv`
- `dsa_decomposition_sl_round2_20261017_run2.csv`
- `dsa_decomposition_sl_round2_20261017_run3.csv`

Source: `round2_check_report_summary_20261017.csv`, `round2_check_matched_rows_20261017.csv`, `round2_check_value_diffs_20261017.csv`, `round2_check_fully_match_reports_20261017.json`, `round2_check_disagreement_reports_20261017.json` — all in `C:\Users\xli7\OneDrive - International Monetary Fund (PRD)\Shelley_My Projects\SFA\output\2021-2026\round2_check_20261017`.

---

## 1. Report-level summary

A report is one staff report PDF. See round2_check_disagreement_reports_20261017.json for the exact definitions used to sort a report into these buckets.

| Category | Reports | Share of total |
|---|---|---:|
| Total reports compared | 215 | 100.0% |
| Fully match | 46 | 21.4% |
| Disagreement (needs check) | 52 | 24.2% |
| No table found (all runs agree) | 115 | 53.5% |
| Extraction failed (every run) | 2 | 0.9% |

### 1.1 Detail (all 7 groups)

| Group | Reports | Share of total |
|---|---|---:|
| Fully match | 46 | 21.4% |
| Partial match (table & year agree, some rows differ) | 42 | 19.5% |
| table_found differs across runs | 0 | 0.0% |
| last_actual_year differs across runs | 10 | 4.7% |
| Report missing from at least one run | 0 | 0.0% |
| Extraction failed in every run (no *_dsa.json) | 2 | 0.9% |
| No table found, in every run | 115 | 53.5% |

---

## 2. Data-point-level summary

A data point is one row of the compiled CSV (one line item of one report's DSA decomposition). Reports in "No table found" and "Extraction failed" contribute 0 data points, since they have no comparable rows.

|  | Data points | Share of total |
|---|---|---:|
| Total data points compared | 1584 | 100.0% |
| Matched (identical across all runs) | 1236 | 78.0% |
| Differing | 348 | 22.0% |

---

## 3. Why the differing data points differ

Breakdown of the 348 differing data points by cause. "Value differs" is the only category where the two runs actually read the same cell of the same table and got a different number; the rest are the effect of a report-level disagreement (see Section 1) applied to every row of that report.

| Reason | Data points | Share of differing |
|---|---|---:|
| Value differs (same table, same year, same row) | 171 | 49.1% |
| Whole report: last_actual_year differs across runs | 161 | 46.3% |
| Row present in some runs but not others | 16 | 4.6% |
