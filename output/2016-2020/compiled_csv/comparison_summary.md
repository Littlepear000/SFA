# SFA DSA Decomposition — Two-Version Comparison

**Scope:** IMF Staff Report DSA (Debt Sustainability Analysis) decomposition tables, all countries, 2016–2020.
**Method:** Same extraction codebase, same sample, run independently on two machines by two team members.
**Date generated:** 2026-09-03

| Version | File | Rows | Reports covered |
|---|---|---|---|
| **A** ("weiqi" run) | `dsa_decomposition_labels_BH_run5_flexible_actual_thinking_weiqi.csv` | 12,470 | 912 |
| **B** ("sl" run) | `dsa_decomposition_sl_20260901.csv` | 12,394 | 907 |

Both files share the identical 43-column schema. Detailed diff files referenced throughout this document live alongside it in `comparison_2016_2020/`:
- `01_report_level_comparison.csv` — one row per report, A vs. B on table_found / framework / last_actual_year / confidence / manual_review_required
- `02_value_level_differences.csv` — all 742 line-item value mismatches
- `03_reports_missing_in_sl_version.csv` — the 5 reports only present in A

---

## 1. Overview

Coverage and table-level judgments agree closely between the two runs. The main disagreements are concentrated in (a) which year each pipeline selected as the "latest actual" column, and (b) read-accuracy noise on a modest subset of reports.

| Metric | Value |
|---|---|
| Reports in A / B | 912 / 907 |
| Reports common to both | 907 |
| Reports only in A | 5 |
| Reports where both versions found a DSA table | 789 |
| Reports with a different "last actual year" selection | 44 / 907 (4.9%) |
| Exact match rate on comparable numeric values | 93.9% |

---

## 2. Sample Coverage

Version B is missing 5 reports that exist in Version A. This was verified against the `country` field — it is a genuine coverage gap in B, not a naming/encoding mismatch.

**Reports present only in Version A:**

| Country | Report date |
|---|---|
| Hong Kong SAR, People's Republic of China | 2016-01-19 |
| Hong Kong SAR, People's Republic of China | 2017-01-12 |
| Hong Kong SAR, People's Republic of China | 2018-01-22 |
| Hong Kong SAR, People's Republic of China | 2019-01-24 |
| Hong Kong SAR, People's Republic of China | 2019-12-30 |

---

## 3. Table Detection & Framework Classification

Across the 907 common reports, agreement on whether a public-sector DSA table was found (`table_found`) is 99.7% (904/907).

| | B = table found | B = no table |
|---|---|---|
| **A = table found** | 789 (agree) | 1 (disagree) |
| **A = no table** | 2 (disagree) | 115 (agree) |

**The 3 disagreeing reports:**

| Report | A | B | Note |
|---|---|---|---|
| Bolivia — 2020-05-29 | Table found (15 line items) | No table | |
| Italy — 2017-07-27 | No table | Table found (15 line items) | |
| Mali — 2016-12-07 | Table found (17 line items)-no values| No table | |

Framework classification (MAC_DSA vs. LIC_DSF) agrees on essentially all of the 789 jointly-found reports, with only a handful of edge cases falling into NA/UNKNOWN on one side (<0.5%).

Self-reported extraction confidence (`confidence`) agrees less tightly — **80.3%** exact match; the remaining ~19% is almost entirely a one-notch difference between "high" and "medium" (57 reports, 6.3%), with no cases jumping from "high" straight to "low".

`manual_review_required` agrees on 99.6% of reports (903/907). Four reports were flagged by A but not B: Cabo Verde 2016-11-29, Greece 2017-07-20, Mali 2016-12-07, Singapore 2018-07-27.

---

## 4. "Last Actual Year" Disagreements — the Main Systematic Driver

For 44 of the 907 common reports (4.9%), the two runs selected a different year as the rightmost "Actual" column in the same table. Since downstream values are pulled from whichever column is selected, this single field explains a large share of the numeric differences in Section 5.

| Report | A selected year | B selected year |
|---|---|---|
| Argentina — 2019-07-15 | 2017 | 2018 yes|
| Bolivia — 2020-05-29 | 2019 | — (no table in B) |
| Burkina Faso — 2016-12-22 | 2015 | 2014 |
| Burkina Faso — 2018-03-15 | 2015 | 2016 yes|
| Cabo Verde — 2016-11-29 | — | 2015 |
| Chad — 2016-08-17 | 2015 yes | 2014 |
| Côte d'Ivoire — 2017-12-15 | 2015 | 2016 |
| Dominica — 2016-07-20 | 2013 | 2014 |
| Ecuador — 2019-03-20 | 2017 | 2018 |
| Greece — 2017-07-20 | — (no table in A) | 2016 |
| Grenada — 2016-12-21 | 2014 | 2015 |
| Guatemala — 2018-06-08 | 2017 | 2016 |
| Guinea — 2017-12-19 | 2015 | 2016 |
| Guinea-Bissau — 2017-12-18 | 2016 | 2015 |
| Guyana — 2016-07-07 | 2014 | 2015 |
| Guyana — 2018-07-16 | 2016 | 2017 |
| Mauritania — 2016-05-11 | 2014 | 2015 |
| Mauritania — 2017-10-16 | 2015 | 2016 |
| Italy — 2017-07-27 | — (no table in A) | 2016 |
| Lesotho — 2018-02-28 | 2015 | 2016 |
| Lao PDR — 2017-02-15 | 2015 | 2014 |
| Lao PDR — 2018-03-23 | 2016 | 2015 |
| Liberia — 2016-01-08 | 2013 | 2014 |
| Liberia — 2017-11-20 | 2015 | 2016 |
| Liberia — 2018-06-15 | 2016 | 2017 |
| Malaysia — 2017-04-28 | 2015 | 2016 |
| Malaysia — 2019-03-08 | 2018 | 2017 |
| Maldives — 2017-12-01 | 2016 | 2015 |
| New Zealand — 2017-05-08 | 2015 | 2009-2014 |
| Papua New Guinea — 2017-01-30 | 2015 | 2014 |
| Papua New Guinea — 2017-12-29 | 2015 | 2016 |
| Madagascar — 2018-07-25 | 2016 | 2017 |
| Nauru — 2020-01-29 | 2019 | 2018 |
| San Marino — 2020-04-02 | 2018 | 2019 |
| Timor-Leste — 2016-06-24 | 2013 | 2014 |
| Rwanda — 2017-07-13 | 2015 | 2016 |
| Senegal — 2017-01-04 | 2014 | 2015 |
| Senegal — 2018-01-12 | 2016 | 2015 |
| Singapore — 2018-07-27 | 2016 | 2017 |
| Solomon Islands — 2018-03-05 | 2016 | 2015 |
| Ethiopia — 2016-10-04 | 2014 | 2015 |
| The Gambia — 2017-07-03 | 2015 | 2016 |
| Togo — 2017-12-15 | 2015 | 2016 |
| United Kingdom — 2016-02-24 | 2015 | 2014 |

*(Full machine-readable list: `01_report_level_comparison.csv`, column `last_actual_year_diff`.)*

---

## 5. Value-Level Consistency

Matching rows by `json_file` + `hierarchy_id` yields 12,373 common line-item keys. Of these, 160 are blank on both sides, leaving 12,213 comparable numeric values:

| | Count | Share |
|---|---|---|
| Exact match | 11,471 | 93.9% |
| Differ | 742 | 6.1% |

**92 reports** (11.7% of the 789 jointly-found reports) contain at least one differing value. Cross-referencing against Section 4:

| Category | Count | Interpretation |
|---|---|---|
| Value mismatch **and** last-actual-year mismatch | 42 / 92 | Explained by different year-column selection |
| Value mismatch with **identical** year selection | 50 / 92 | Genuine read/extraction inconsistency between runs |

### Magnitude

- Mean absolute difference: **2.49** (GDP percentage points)
- Median absolute difference: **1.1**
- Maximum: **34.9**
- ~47% of differences exceed 1 point (economically meaningful); only ~10% are ≤0.15 (rounding-level noise)
- No systematic direction: mean signed difference (A − B) is only +0.17; A>B in 47.6% of cases, A<B in 44.5% — differences look like noise plus selection-criteria mismatch, not a consistent bias in either version.

### By category (differing rows only)

| Category | n | Mean abs. diff |
|---|---|---|
| identified_flows | 64 | 4.28 |
| residual | 63 | 4.05 |
| change_in_debt | 56 | 3.91 |
| primary_balance | 196 | 2.18 |
| other_identified_flows | 83 | 1.91 |
| automatic_debt_dynamics | 280 | 1.80 |

Aggregate/subtotal line items (identified flows, residual, change in debt) carry the largest average error, since they accumulate the error of upstream detail rows.

### Top 20 largest value discrepancies

| Report | Category | Line item | A | B | Abs. diff |
|---|---|---|---:|---:|---:|
| Nauru — 2020-01-29 | residual | Residual, including asset changes | 34.0 | 68.9 | 34.9 |
| Nauru — 2020-01-29 | identified_flows | Identified debt-creating flows | -42.4 | -72.6 | 30.2 |
| Nauru — 2020-01-29 | primary_balance | Primary (noninterest) expenditure | 125.6 | 96.6 | 29.0 |
| Argentina — 2019-07-15 | automatic_debt_dynamics | Exchange rate depreciation | 5.6 | 30.5 | 24.9 |
| Argentina — 2019-07-15 | change_in_debt | Change in gross public sector debt | 4.1 | 28.9 | 24.8 |
| Argentina — 2019-07-15 | identified_flows | Identified debt-creating flows | 1.1 | 25.1 | 24.0 |
| Argentina — 2019-07-15 | automatic_debt_dynamics | Automatic debt dynamics | -2.7 | 18.1 | 20.8 |
| Kiribati — 2019-01-24 | residual | Residual | 21.7 | 1.7 | 20.0 |
| Kiribati — 2019-01-24 | identified_flows | Identified debt-creating flows | -22.2 | -2.2 | 20.0 |
| Congo, Rep. — 2020-01-27 | residual | Residual | -22.7 | -3.1 | 19.6 |
| Congo, Rep. — 2020-01-27 | automatic_debt_dynamics | Automatic debt dynamics | 1.1 | -18.5 | 19.6 |
| Congo, Rep. — 2020-01-27 | automatic_debt_dynamics | Contribution from real exchange rate depreciation | 9.0 | -10.5 | 19.5 |
| Congo, Rep. — 2020-01-27 | identified_flows | Identified debt-creating flows | -7.8 | -27.3 | 19.5 |
| Kiribati — 2019-01-24 | primary_balance | Primary deficit | -18.3 | -0.3 | 18.0 |
| Mauritania — 2017-10-16 | change_in_debt | Change in public sector debt | 18.0 | 0.9 | 17.1 |
| Nauru — 2020-01-29 | primary_balance | Primary deficit | -15.0 | -31.9 | 16.9 |
| Kiribati — 2019-01-24 | primary_balance | Primary (noninterest) expenditure | 110.5 | 125.4 | 14.9 |
| The Gambia — 2017-07-03 | change_in_debt | Change in public sector debt | 0.4 | 14.9 | 14.5 |
| The Gambia — 2017-07-03 | identified_flows | Identified debt-creating flows | -8.7 | 5.5 | 14.2 |
| Timor-Leste — 2016-06-24 | primary_balance | Primary (noninterest) expenditure | 24.0 | 37.4 | 13.4 |

*(Full set of 742 rows: `02_value_level_differences.csv`.)*

---

## 6. Read-Stability Case Studies

Two reports illustrate that mismatches are not purely a year-selection artifact — the same selected year can still yield different numbers, pointing to instability in the vision/OCR extraction step itself.

**Côte d'Ivoire — 2020-04-23** (selected year: A = 2019, B = 2019 — identical)
- Version A: all 17 line items are blank (confidence = low)
- Version B: fully populated (confidence = medium), e.g. Revenue and grants = 15.2, Primary (noninterest) expenditure = 17.0, Automatic debt dynamics = -0.8

**Chad — 2019-07-31** (selected year: A = 2018, B = 2018 — identical)
- "of which: contribution from real GDP growth": A = -0.6, B = -1.1
- "Contribution from real exchange rate depreciation": A = -1.4, B = **+3.3** (sign reversed)
- "of which: grants": A = 1.3, B = 3.2

Separately, 57 line items have a value in B but are blank in A, concentrated in 6 reports (Cabo Verde 2016-11-29, Côte d'Ivoire 2020-04-23, Greece 2017-07-20 account for most; Timor-Leste, Guatemala, and the UK each have 1–6). The reverse (blank in B, present in A) occurs in only 2 rows, spread across 2 reports — no systematic direction.

---

## 7. Formatting Differences (cosmetic, but will break naive diffs)

These do not change meaning but will produce false positives in a row-by-row script comparison unless normalized first.

| Field | A | B |
|---|---|---|
| `table_found` | `TRUE` / `FALSE` (uppercase) | `True` / `False` (title case) |
| `publication_date` | Abbreviated, e.g. `Feb-16` | Full, e.g. `February 2016` |
| `page_pdf`, `level` | Integer string, e.g. `61`, `0` | Float string, e.g. `61.0`, `0.0` |
| Country name spelling | Hong Kong SAR name has 3 internal variants (mixed dashes/quote characters) | — |

---

## 8. Recommendations

1. **Reconcile the 44 "last actual year" mismatches first.** Standardize the rule for what counts as an "Actual" column (e.g., whether a year footnoted "Est." should count as actual). This is the largest, most explainable, and most fixable source of disagreement (Section 4).
2. **Manually spot-check the 50 reports where the year selection matches but values still differ**, especially Côte d'Ivoire 2020-04-23 (fully blank in A) and Chad 2019-07-31 (sign-reversed values). Determine whether this is extraction randomness and whether a re-run or a confidence-threshold change is warranted (Sections 5–6).
3. **Re-run the 5 Hong Kong SAR reports missing from Version B** so both versions cover an identical sample (Section 2).
4. **Manually verify the 3 reports where `table_found` disagrees** (Bolivia 2020-05-29, Italy 2017-07-27, Mali 2016-12-07) against the source PDF (Section 3).
5. **Normalize export formatting** (boolean casing, date format, numeric string precision) to prevent false positives in future automated diffs (Section 7).
6. **Overall, the two runs agree closely**: 789/907 reports agree on table detection, and 93.9% of comparable values match exactly. Rather than re-checking the full sample, treat the agreeing portion as reliable and focus manual review on the ~100 reports flagged above.

---

*Data sources: `dsa_decomposition_labels_BH_run5_flexible_actual_thinking_weiqi.csv` (Version A) and `dsa_decomposition_sl_20260901.csv` (Version B), both in `output_check/`. Supporting detail files in `output_check/comparison_2016_2020/`.*
