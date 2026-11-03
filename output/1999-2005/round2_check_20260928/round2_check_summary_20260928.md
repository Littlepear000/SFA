# Round2 Check Summary

**Round:** round2　**Run date:** 20260928　**Runs compared:** 3　**Generated:** 2026-10-06

**Run CSVs:**
- `dsa_decomposition_1999_2005_51_reports_with_inconsistencies_01.csv`
- `dsa_decomposition_1999_2005_51_reports_with_inconsistencies_02.csv`
- `dsa_decomposition_1999_2005_51_reports_with_inconsistencies_03.csv`

Source: `round2_check_report_summary_20260928.csv`, `round2_check_matched_rows_20260928.csv`, `round2_check_value_diffs_20260928.csv`, `round2_check_fully_match_reports_20260928.json`, `round2_check_disagreement_reports_20260928.json` — all in `/Users/vickipedia/Desktop/IMF_work/FADFP/research_projects/SFA/dsa_results/round2_check_1999_2005_20260928`.

---

## 1. Report-level summary

A report is one staff report PDF. See round2_check_disagreement_reports_20260928.json for the exact definitions used to sort a report into these buckets.

| Category | Reports | Share of total |
|---|---|---:|
| Total reports compared | 51 | 100.0% |
| Fully match | 30 | 58.8% |
| Disagreement (needs check) | 20 | 39.2% |
| No table found (all runs agree) | 1 | 2.0% |
| Extraction failed (every run) | 0 | 0.0% |

### 1.1 Detail (all 7 groups)

| Group | Reports | Share of total |
|---|---|---:|
| Fully match | 30 | 58.8% |
| Partial match (table & year agree, some rows differ) | 4 | 7.8% |
| table_found differs across runs | 1 | 2.0% |
| last_actual_year differs across runs | 15 | 29.4% |
| Report missing from at least one run | 0 | 0.0% |
| Extraction failed in every run (no *_dsa.json) | 0 | 0.0% |
| No table found, in every run | 1 | 2.0% |

---

## 2. Data-point-level summary

A data point is one row of the compiled CSV (one line item of one report's DSA decomposition). Reports in "No table found" and "Extraction failed" contribute 0 data points, since they have no comparable rows.

|  | Data points | Share of total |
|---|---|---:|
| Total data points compared | 716 | 100.0% |
| Matched (identical across all runs) | 475 | 66.3% |
| Differing | 241 | 33.7% |

---

## 3. Why the differing data points differ

Breakdown of the 241 differing data points by cause. "Value differs" is the only category where the two runs actually read the same cell of the same table and got a different number; the rest are the effect of a report-level disagreement (see Section 1) applied to every row of that report.

| Reason | Data points | Share of differing |
|---|---|---:|
| Whole report: last_actual_year differs across runs | 219 | 90.9% |
| Whole report: table_found differs across runs | 15 | 6.2% |
| Value differs (same table, same year, same row) | 7 | 2.9% |
