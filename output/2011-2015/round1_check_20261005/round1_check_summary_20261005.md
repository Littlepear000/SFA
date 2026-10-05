# Round1 Check Summary

**Round:** round1　**Run date:** 20261005　**Runs compared:** 3　**Generated:** 2026-10-05

**Run CSVs:**
- `dsa_decomposition_labels_2011-2015_sa_merged.csv`
- `dsa_decomposition_labels_2011_2015_Weiqi.csv`
- `dsa_decomposition_sl_20260914.csv`

Source: `round1_check_report_summary_20261005.csv`, `round1_check_matched_rows_20261005.csv`, `round1_check_value_diffs_20261005.csv`, `round1_check_fully_match_reports_20261005.json`, `round1_check_disagreement_reports_20261005.json` — all in `/Users/littlepear000/Desktop/IMF projects/SFA/output/2011-2015/round1_check_20261005`.

---

## 1. Report-level summary

A report is one staff report PDF. See round1_check_disagreement_reports_20261005.json for the exact definitions used to sort a report into these buckets.

| Category | Reports | Share of total |
|---|---|---:|
| Total reports compared | 702 | 100.0% |
| Fully match | 364 | 51.9% |
| Disagreement (needs check) | 169 | 24.1% |
| No table found (all runs agree) | 169 | 24.1% |
| Extraction failed (every run) | 0 | 0.0% |

### 1.1 Detail (all 7 groups)

| Group | Reports | Share of total |
|---|---|---:|
| Fully match | 364 | 51.9% |
| Partial match (table & year agree, some rows differ) | 40 | 5.7% |
| table_found differs across runs | 76 | 10.8% |
| last_actual_year differs across runs | 50 | 7.1% |
| Report missing from at least one run | 3 | 0.4% |
| Extraction failed in every run (no *_dsa.json) | 0 | 0.0% |
| No table found, in every run | 169 | 24.1% |

---

## 2. Data-point-level summary

A data point is one row of the compiled CSV (one line item of one report's DSA decomposition). Reports in "No table found" and "Extraction failed" contribute 0 data points, since they have no comparable rows.

|  | Data points | Share of total |
|---|---|---:|
| Total data points compared | 8307 | 100.0% |
| Matched (identical across all runs) | 6194 | 74.6% |
| Differing | 2113 | 25.4% |

---

## 3. Why the differing data points differ

Breakdown of the 2113 differing data points by cause. "Value differs" is the only category where the two runs actually read the same cell of the same table and got a different number; the rest are the effect of a report-level disagreement (see Section 1) applied to every row of that report.

| Reason | Data points | Share of differing |
|---|---|---:|
| Whole report: table_found differs across runs | 1157 | 54.8% |
| Whole report: last_actual_year differs across runs | 817 | 38.7% |
| Value differs (same table, same year, same row) | 80 | 3.8% |
| Whole report: missing from at least one run's CSV | 47 | 2.2% |
| Row present in some runs but not others | 12 | 0.6% |
