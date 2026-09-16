# SFA DSA Extraction — Rerun Verification on the 92 Previously Mismatched Reports

**Scope:** The 92 reports flagged in the original two-version comparison (`output_check/comparison_2016_2020/comparison_summary.md`) as having at least one extracted value that disagreed between Weiqi's and Shelley's runs.
**What changed since the original run:** the prompt was revised to add explicit guidance for merged multi-year range columns and non-year memo columns (Average / Standard Deviation), and the pipeline was updated with an internal self-consistency check that flags a selection when the model's own column audit lists a later eligible column it did not select. Both team members reran only these 92 reports with the updated code/prompt.
**Date generated:** 2026-09-12 (updated after Shelley's Malaysia re-run)

| Version | File | Rows | Reports |
|---|---|---|---|
| **A** (Weiqi rerun) | `dsa_decomposition_labels_new_prompt_weiqi.csv` | 1,479 | 92 |
| **B** (Shelley rerun, updated) | `dsa_decomposition_sl_20260912.csv` | 1,476 | 92 |

Detail file: `rerun_value_diffs.csv` in this folder (all 291 remaining line-item mismatches; regenerated from the updated Shelley file).

> Note: an earlier version of this document compared against `dsa_decomposition_sl_20260910.csv`, in which Shelley's Malaysia — 2016-05-04 run had failed with a transient network error. Shelley re-ran that one report and the update below uses the corrected `..._20260912.csv` file. Malaysia now matches cleanly on both sides (table found, last actual year 2015, no value disagreements), so this only changes the coverage/denominator numbers below, not the substantive findings.

---

## 1. Headline result: clear improvement, but not fully resolved

| Metric | Before (original run, same 92 reports) | After (this rerun) | Change |
|---|---|---|---|
| Reports with a genuine last-actual-year disagreement | 42 / 92 (45.7%) | 14 / 92 (15.2%) | **−67%** |
| Comparable line-item values | 1,474 | 1,473 | — |
| Values that disagree | 742 | 291 | **−60.8%** |
| Value match rate | 49.7% | 80.2% | **+30.5 pts** |
| Reports with ≥1 remaining value disagreement | 92 / 92 (100%, by definition) | 36 / 92 (39.1%) | **−61%** |

The prompt and validation changes cut the disagreement rate roughly in half to two-thirds across every metric. The remaining 36 reports are a much smaller, more targeted list for manual review than the original 92.

---

## 2. Coverage and infrastructure

Both reruns now cover all 92 reports cleanly, with `table_found = True` on both sides for every report (92/92 agreement). The earlier Malaysia — 2016-05-04 network failure on Shelley's side (`RemoteDisconnected`) is resolved after her re-run: both sides now find the table, select the same last-actual-year (2015), and show no value disagreements for that report.

Extraction method agreement: 90/92 (97.8%) reports used the same method on both sides (14 table-crop, 3 visual-fallback, 73 direct-PDF). Neither run needed the new image-compression fallback tier for this particular 92-report set.

Self-reported `confidence` agreement: 86/92 (93.5%) exact match (78 high/high, 8 medium/medium); the rest are one-notch high/medium differences. `manual_review_required` was **not flagged by either run for any of the 92 reports** — including the 36 that still disagree. This confirms a point from the original review: the model's own self-assessment does not reliably catch these disagreements, so the new rightmost-column validation and any future fiscal-table cross-check remain necessary rather than optional safety nets.

A small, unrelated row-count wrinkle remains: three reports (Cambodia — 2019-12-23, São Tomé and Príncipe — 2020-08-04, Belarus — 2019-01-17) each have exactly one line item present in Weiqi's rerun but missing in Shelley's — likely a minor difference in how many child rows got extracted on each side, not a year or major-value issue.

---

## 3. Last-actual-year: 42 → 14 remaining disagreements

The 14 reports below still show a different selected year between the two runs (unchanged by the Malaysia fix — Malaysia no longer appears here). Direction is mixed (9 cases where Shelley's year is later, 5 where Weiqi's is later) — this does not look like one side running a stale prompt version so much as a residual set of harder header layouts the current rules still don't fully resolve.

| Report | Weiqi year | Shelley year |
|---|---|---|
| Argentina — 2019-07-15 | 2017 | 2018 |
| Burkina Faso — 2018-03-15 | 2015 | 2016 |
| Côte d'Ivoire — 2017-12-15 | 2015 | 2016 |
| Grenada — 2016-12-21 | 2014 | 2015 |
| Guatemala — 2018-06-08 | 2016 | 2017 |
| Guinea — 2017-12-19 | 2016 | 2015 |
| Guyana — 2018-07-16 | 2016 | 2017 |
| Mauritania — 2017-10-16 | 2015 | 2016 |
| Lesotho — 2018-02-28 | 2016 | 2015 |
| Liberia — 2017-11-20 | 2016 | 2015 |
| Malaysia — 2019-03-08 | 2018 | 2017 |
| Papua New Guinea — 2017-01-30 | 2015 | 2014 |
| Senegal — 2018-01-12 | 2015 | 2016 |
| Togo — 2017-12-15 | 2015 | 2016 |

(Note: "Malaysia — 2019-03-08" above is a **different** report from the re-run "Malaysia — 2016-05-04" discussed in Section 2 — same country, different report date, unrelated issue.)

Notably, **Argentina 2019-07-15 — the exact report used to design the merged-range-column prompt fix — is still wrong on the Weiqi side** (2017 instead of 2018), while Shelley's side now gets it right. Worth double-checking that both team members are actually running the same, latest version of the prompt/code file before concluding the fix itself is insufficient.

---

## 4. Value-level accuracy: 291 remaining disagreements across 36 reports

| Category | Count | Interpretation |
|---|---|---|
| Value mismatch **and** year mismatch | 14 / 36 | Same driver as Section 3 — fix the year, the values likely follow |
| Value mismatch with **identical** year, method, and confidence | 22 / 36 | Genuine read/extraction inconsistency, unrelated to year selection |

### Magnitude

- Mean absolute difference: **3.11** (GDP percentage points) — actually higher than the original run's 2.49, driven by a few large outliers (see below)
- Median: **1.0**
- Maximum: **61.0**
- 47% of differences exceed 1 point; only 11% are ≤0.15 (rounding-level)
- No systematic bias: mean signed difference (A − B) is −0.26; A>B in 50.5% of cases, A<B in 48.8%

### By category

| Category | n | Mean abs. diff |
|---|---|---|
| identified_flows | 25 | 5.75 |
| residual | 24 | 4.71 |
| change_in_debt | 21 | 4.86 |
| primary_balance | 80 | 3.35 |
| other_identified_flows | 30 | 2.14 |
| automatic_debt_dynamics | 111 | 1.91 |

### Two cases worth priority manual review

Both of these have **identical** selected year, extraction method, and confidence on both sides, so the disagreement is not explained by anything currently tracked in the pipeline metadata:

- **Republic of Moldova — 2019-09-25**: "Revenue and grants" is **−30.5 in Weiqi's run vs. +30.5 in Shelley's** — an exact sign flip on a line item that should essentially never be negative. This is the single largest remaining discrepancy (61.0 points) and looks like a clean misread on one side rather than an ambiguous judgment call.
- **Kiribati — 2019-01-24**: four line items (residual, identified flows, primary deficit, primary expenditure) each differ by 39–40 points, larger than the same report's gap in the *original* run. Same year (2017), same extraction method (`selected_pdf_direct`, i.e. native text, not an image), same confidence (medium) on both sides — worth a manual pull of the source PDF page for this one specifically.

### Top 15 largest remaining differences

| Report | Category | Line item | Weiqi | Shelley | Abs. diff |
|---|---|---|---:|---:|---:|
| Moldova — 2019-09-25 | primary_balance | Revenue and grants | -30.5 | 30.5 | 61.0 |
| Kiribati — 2019-01-24 | residual | Residual | 11.7 | 51.7 | 40.0 |
| Kiribati — 2019-01-24 | identified_flows | Identified debt-creating flows | -12.2 | -52.2 | 40.0 |
| Kiribati — 2019-01-24 | primary_balance | Primary deficit | -11.3 | -50.4 | 39.1 |
| Kiribati — 2019-01-24 | primary_balance | Primary (noninterest) expenditure | 114.5 | 75.5 | 39.0 |
| Argentina — 2019-07-15 | automatic_debt_dynamics | Exchange rate depreciation | 5.6 | 30.5 | 24.9 |
| Argentina — 2019-07-15 | change_in_debt | Change in gross public sector debt | 4.1 | 28.9 | 24.8 |
| Argentina — 2019-07-15 | identified_flows | Identified debt-creating flows | 1.1 | 25.1 | 24.0 |
| Argentina — 2019-07-15 | automatic_debt_dynamics | Automatic debt dynamics | -2.7 | 18.1 | 20.8 |
| Mauritania — 2017-10-16 | change_in_debt | Change in public sector debt | 18.0 | 0.9 | 17.1 |
| Mauritania — 2017-10-16 | identified_flows | Identified debt-creating flows | 12.8 | -0.6 | 13.4 |
| Papua New Guinea — 2017-01-30 | residual | Residual, including asset changes | -19.8 | -7.1 | 12.7 |
| Papua New Guinea — 2017-01-30 | change_in_debt | Change in public sector debt | -7.9 | 4.5 | 12.4 |
| Mauritania — 2017-10-16 | automatic_debt_dynamics | Automatic debt dynamics | 10.7 | 0.3 | 10.4 |
| Lesotho — 2018-02-28 | change_in_debt | Change in public sector debt | -5.8 | 4.4 | 10.2 |

Four of the top 5 rows come from just two reports (Moldova, Kiribati) — both cases where year/method/confidence all agree, reinforcing that these are read-accuracy issues rather than year-selection issues.

*(Argentina and Mauritania's large gaps here are a direct consequence of the Section 3 year mismatch — different years naturally produce different numbers — and should resolve once the year is fixed.)*

### All 36 reports with remaining value disagreements

| Report | # differing values |
|---|---:|
| Grenada — 2016-12-21 | 15 |
| Argentina — 2019-07-15 | 14 |
| Senegal — 2018-01-12 | 14 |
| Papua New Guinea — 2017-01-30 | 14 |
| Côte d'Ivoire — 2017-12-15 | 13 |
| Guinea — 2017-12-19 | 13 |
| Liberia — 2017-11-20 | 12 |
| Burkina Faso — 2018-03-15 | 12 |
| Thailand — 2018-06-04 | 12 |
| Moldova — 2019-09-25 | 12 |
| Guatemala — 2018-06-08 | 12 |
| Guyana — 2018-07-16 | 12 |
| Mauritania — 2017-10-16 | 12 |
| Lesotho — 2018-02-28 | 12 |
| Mali — 2020-05-08 | 12 |
| Togo — 2017-12-15 | 11 |
| Malaysia — 2019-03-08 | 11 |
| Côte d'Ivoire — 2020-04-23 | 11 |
| São Tomé and Príncipe — 2020-08-04 | 11 |
| Chad — 2019-07-31 | 11 |
| Kiribati — 2019-01-24 | 8 |
| Burkina Faso — 2019-12-30 | 6 |
| Ukraine — 2020-06-11 | 5 |
| Cambodia — 2019-12-23 | 5 |
| Belarus — 2019-01-17 | 4 |
| Armenia — 2016-12-13 | 2 |
| Bulgaria — 2018-02-21 | 2 |
| Equatorial Guinea — 2016-11-16 | 2 |
| Equatorial Guinea — 2019-12-20 | 2 |
| Myanmar — 2020-07-02 | 2 |
| Malaysia — 2017-04-28 | 2 |
| Philippines — 2018-09-27 | 1 |
| Nauru — 2020-01-29 | 1 |
| Peru — 2020-05-29 | 1 |
| Sweden — 2019-03-26 | 1 |
| Mexico — 2020-11-20 | 1 |

*(Full row-level detail for every one of these: `rerun_value_diffs.csv` in this folder. Malaysia — 2016-05-04, the report affected by the earlier network failure, does not appear in this list — it now matches cleanly.)*

---

## 5. Recommendations

1. **Verify prompt/code sync before drawing conclusions on the 14 remaining year mismatches.** Argentina — the report that motivated the prompt fix — is still wrong on one side. Confirm both team members are pointing at the same, current version of `sl_revised_prompt_step_one.txt` and `step_1_revised_on_problematic_reports_sl.py` before treating these 14 as "the fix's remaining failure rate."
2. **Manually pull the source PDF for Moldova 2019-09-25 and Kiribati 2019-01-24.** These are the two largest and most concerning remaining gaps, and neither is explained by year, method, or confidence — a genuine read-accuracy problem worth a human eyeball.
3. **Treat the 14 year-mismatch reports as likely also fixing most of their value gaps once the year issue is resolved** — no need to separately debug their value differences first.
4. **Continue not relying on `confidence`/`manual_review_required` as a filter** — 0/92 were self-flagged despite 36 still disagreeing. The rightmost-column validation added to the pipeline is a partial mitigation; extending it (or adding the previously discussed fiscal-table cross-check) remains worthwhile.
5. **Net assessment:** this round of fixes measurably worked — value match rate on this hard subset rose from 49.7% to 80.2%, and the number of reports needing any correction dropped by 61%. This is a good basis for a second, smaller round targeting the 36 (or, after excluding the 14 year-driven ones, more precisely the 22 pure read-accuracy cases) rather than re-opening the full 92.

---

*Data sources: `dsa_decomposition_labels_new_prompt_weiqi.csv` (Weiqi rerun) and `dsa_decomposition_sl_20260912.csv` (Shelley rerun, post Malaysia re-run), both in `output_check/rerun_mismatch_2016_2020/`. "Before" baseline recomputed from the original `output_check/dsa_decomposition_labels_BH_run5_flexible_actual_thinking_weiqi.csv` and `dsa_decomposition_sl_20260901.csv`, restricted to these same 92 reports.*
