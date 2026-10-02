# Round1 Check Summary

**Round:** round1　**Run date:** 20261002　**Runs compared:** 3　**Generated:** 2026-10-02

**Run CSVs:**
- `dsa_decomposition_labels_2016-2020_sa_merged.csv`
- `dsa_decomposition_labels_BH_run5_flexible_actual_thinking_weiqi.csv`
- `dsa_decomposition_sl_20260901.csv`

Source: `round1_check_report_summary_20261002.csv`, `round1_check_matched_rows_20261002.csv`, `round1_check_value_diffs_20261002.csv`, `round1_check_fully_match_reports_20261002.json`, `round1_check_disagreement_reports_20261002.json` — all in `/Users/littlepear000/Desktop/IMF projects/SFA/output/2016-2020/round1_check_20261002`.

---

## 1. Report-level summary

A report is one staff report PDF. See round1_check_disagreement_reports_20261002.json for the exact definitions used to sort a report into these buckets.

| Category | Reports | Share of total |
|---|---|---:|
| Total reports compared | 912 | 100.0% |
| Fully match | 668 | 73.2% |
| Disagreement (needs check) | 130 | 14.3% |
| No table found (all runs agree) | 114 | 12.5% |
| Extraction failed (every run) | 0 | 0.0% |

### 1.1 Detail (all 7 groups)

| Group | Reports | Share of total |
|---|---|---:|
| Fully match | 668 | 73.2% |
| Partial match (table & year agree, some rows differ) | 61 | 6.7% |
| table_found differs across runs | 5 | 0.5% |
| last_actual_year differs across runs | 59 | 6.5% |
| Report missing from at least one run | 5 | 0.5% |
| Extraction failed in every run (no *_dsa.json) | 0 | 0.0% |
| No table found, in every run | 114 | 12.5% |

---

## 2. Data-point-level summary

A data point is one row of the compiled CSV (one line item of one report's DSA decomposition). Reports in "No table found" and "Extraction failed" contribute 0 data points, since they have no comparable rows.

|  | Data points | Share of total |
|---|---|---:|
| Total data points compared | 12395 | 100.0% |
| Matched (identical across all runs) | 11036 | 89.0% |
| Differing | 1359 | 11.0% |

---

## 3. Why the differing data points differ

Breakdown of the 1359 differing data points by cause. "Value differs" is the only category where the two runs actually read the same cell of the same table and got a different number; the rest are the effect of a report-level disagreement (see Section 1) applied to every row of that report.

| Reason | Data points | Share of differing |
|---|---|---:|
| Whole report: last_actual_year differs across runs | 965 | 71.0% |
| Value differs (same table, same year, same row) | 237 | 17.4% |
| Whole report: table_found differs across runs | 81 | 6.0% |
| Whole report: missing from at least one run's CSV | 60 | 4.4% |
| Row present in some runs but not others | 16 | 1.2% |
