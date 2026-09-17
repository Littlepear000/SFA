# SFA DSA Decomposition — Three-Version Comparison (SL vs. Weiqi vs. SA)

**Scope:** IMF Staff Report DSA (Debt Sustainability Analysis) decomposition tables, all countries, 2016–2020.
**Method:** Each team member ran their own *original/pre-revision* extraction pipeline independently, on the same PDF sample, and compiled their own results CSV. This document extends the earlier SL-vs-Weiqi comparison (`comparison_summary.md`) by adding a third team member, SA, who ran his own version of the original codebase with some independent modifications (see Section 7 for the behavioral differences this introduced).
**Note on scope:** This comparison uses SL's **original** run (`dsa_decomposition_sl_20260901.csv`), not SL's later "Last Actual Year" prompt/code revision. The revised-pipeline rerun on the 92 previously-mismatched reports is a separate, already-documented exercise (`_rerun_20260910/compiled_csv/rerun_comparison_summary.md`) and is out of scope here.
**Date generated:** 2026-09-17

| Version | File(s) | Rows | Reports covered |
|---|---|---:|---:|
| **SL** | `dsa_decomposition_sl_20260901.csv` | 12,394 | 907 |
| **Weiqi** | `dsa_decomposition_labels_BH_run5_flexible_actual_thinking_weiqi.csv` | 12,470 | 912 |
| **SA** | `dsa_decomposition_labels_2016-2020_sa.csv` (851 reports) + `dsa_decomposition_labels_2016-2020_errors_sa.csv` (61 reports) | 11,475 + 1,009 = 12,484 | 912 |

SA's results are split across two files with no overlapping reports (`_sa.csv` covers the main 851-report batch, `_errors_sa.csv` covers 61 reports that were processed/tracked separately on his side). Both are combined into a single 912-report "SA" dataset for this comparison. All three files share the identical 43-column schema (columns in a slightly different order in `_errors_sa.csv`, but comparison here is by column name, not position).

Full supporting detail behind this document is saved alongside it in this same folder:
- `three_way_sl_weiqi_sa_report_level_20260917.csv` — one row per report (907 rows), all three versions' key fields side by side, with agreement flags.
- `three_way_sl_weiqi_sa_value_diffs_20260917.csv` — all 877 line-item value mismatches among reports where all three versions found a table.
- `three_way_sl_weiqi_sa_disagreement_list_20260917.csv` — the 118 reports with any disagreement (table_found, last_actual_year, and/or value), tagged by type (Section 6).
- `three_way_sl_weiqi_sa_two_of_three_match_20260917.csv` — the 96 of those 118 reports where exactly two versions fully agree with each other, with the fully-matching pair and the outlier version (Section 6.1).

---

## 1. Overview

Coverage and table-level judgments agree closely across all three versions. As with the original two-way comparison, the main disagreements concentrate in (a) which year each run selected as the "last actual" column, and (b) read-accuracy noise on a modest subset of reports. Adding SA as a third, independently-modified run mostly confirms the same picture, but also surfaces one new systematic difference: SA's `manual_review_required` flag fires far more often than SL's or Weiqi's (Section 7).

| Metric | Value |
|---|---|
| Reports in SL / Weiqi / SA | 907 / 912 / 912 |
| Reports common to all three | 907 |
| Reports missing only from SL | 5 |
| Reports where all three found a DSA table | 788 |
| Reports with a 3-way "last actual year" disagreement | 59 / 788 (7.5%) |
| 3-way exact match rate on comparable numeric values | 92.8% |
| **Reports that fully match across all three versions** | **789 / 907 (87.0%)** |
| **Reports with at least one disagreement (table_found, year, or value)** | **118 / 907 (13.0%)** |

---

## 2. Sample Coverage

SL is missing the same 5 reports that were already identified in the original two-way comparison — all Hong Kong SAR, People's Republic of China reports. Weiqi's and SA's report sets are **identical** (912/912 keys match exactly), so this remains purely an SL-side coverage gap, not a new discrepancy introduced by SA.

**Reports present only in Weiqi and SA (missing from SL):**

| Country | Report date |
|---|---|
| Hong Kong SAR, People's Republic of China | 2016-01-19 |
| Hong Kong SAR, People's Republic of China | 2017-01-12 |
| Hong Kong SAR, People's Republic of China | 2018-01-22 |
| Hong Kong SAR, People's Republic of China | 2019-01-24 |
| Hong Kong SAR, People's Republic of China | 2019-12-30 |

---

## 3. Table Detection & Framework Classification

Across the 907 reports common to all three, 3-way agreement on `table_found` is **99.4% (902/907)**.

**The 5 disagreeing reports:**

| Report | SL | Weiqi | SA |
|---|---|---|---|
| Bolivia — 2020-05-29 | No table | Table found | Table found |
| Côte d'Ivoire — 2018-06-25 | Table found | Table found | No table |
| Italy — 2017-07-27 | Table found | No table | Table found |
| Mali — 2016-12-07 | No table | Table found | Table found |
| Tanzania — 2016-02-01 | No table | No table | Table found |

Of the original comparison's 3 `table_found` disagreements (Bolivia, Italy, Mali), SA sides with Weiqi on all three (i.e., SA also finds a table). Côte d'Ivoire 2018-06-25 and Tanzania 2016-02-01 are new disagreements not flagged in the original SL-vs-Weiqi document — worth a manual PDF check (see Recommendations).

Restricting to the **788 reports where all three found a table**, framework classification (MAC_DSA / LIC_DSF / UNKNOWN) agrees 99.5% of the time (784/788).

---

## 4. "Last Actual Year" Disagreements — Still the Main Systematic Driver

Among the 788 jointly-found reports, all three versions select the **same** last-actual year in 729 cases (92.5%). The remaining **59 reports (7.5%)** show at least one version disagreeing with the other two:

| Report | SL year | Weiqi year | SA year |
|---|---|---|---|
| Argentina — 2019-07-15 | 2018 | 2017 | 2018 |
| Bangladesh — 2016-02-01 | — | — | 2014 |
| Belize — 2016-03-28 | 2013 | 2013 | 2014 |
| Benin — 2017-04-26 | 2014 | 2014 | 2015 |
| Benin — 2016-01-07 | — | — | 2014 |
| Burkina Faso — 2016-12-22 | 2014 | 2015 | 2014 |
| Burkina Faso — 2018-03-15 | 2016 | 2015 | 2016 |
| Cabo Verde — 2016-11-29 | 2015 | — | — |
| Chad — 2016-08-17 | 2014 | 2015 | 2015 |
| Cyprus — 2016-01-29 | 2015 | 2015 | 2014 |
| Côte d'Ivoire — 2017-12-15 | 2016 | 2015 | 2016 |
| São Tomé and Príncipe — 2017-12-18 | 2015 | 2015 | 2016 |
| Djibouti — 2017-04-06 | 2014 | 2014 | 2015 |
| Dominica — 2017-12-20 | 2014 | 2014 | 2015 |
| Dominica — 2016-07-20 | 2014 | 2013 | 2014 |
| Ecuador — 2019-03-20 | 2018 | 2017 | 2017 |
| Greece — 2017-07-20 | 2016 | — | 2016 |
| Grenada — 2016-12-21 | 2015 | 2014 | 2015 |
| Guatemala — 2018-06-08 | 2016 | 2017 | 2016 |
| Guinea — 2017-12-19 | 2016 | 2015 | 2015 |
| Guinea-Bissau — 2016-12-28 | 2014 | 2014 | 2015 |
| Guinea-Bissau — 2017-12-18 | 2015 | 2016 | 2015 |
| Guyana — 2016-07-07 | 2015 | 2014 | 2015 |
| Guyana — 2018-07-16 | 2017 | 2016 | 2016 |
| Honduras — 2018-07-03 | 2016 | 2016 | 2017 |
| Mauritania — 2017-12-13 | 2015 | 2015 | 2016 |
| Mauritania — 2016-05-11 | 2015 | 2014 | 2014 |
| Mauritania — 2017-10-16 | 2016 | 2015 | 2015 |
| Lesotho — 2018-02-28 | 2016 | 2015 | 2016 |
| Kyrgyz Republic — 2018-02-22 | 2015 | 2015 | 2016 |
| Lao PDR — 2017-02-15 | 2014 | 2015 | 2014 |
| Lao PDR — 2018-03-23 | 2015 | 2016 | 2016 |
| Liberia — 2016-01-08 | 2014 | 2013 | 2014 |
| Liberia — 2018-06-15 | 2017 | 2016 | 2016 |
| Liberia — 2017-11-20 | 2016 | 2015 | 2016 |
| Malaysia — 2017-04-28 | 2016 | 2015 | 2015 |
| Malaysia — 2019-03-08 | 2017 | 2018 | 2018 |
| Maldives — 2017-12-01 | 2015 | 2016 | 2016 |
| Myanmar — 2017-02-02 | 2014 | 2014 | 2015 |
| New Zealand — 2017-05-08 | 2009-2014 | 2015 | 2015 |
| Papua New Guinea — 2017-12-29 | 2016 | 2015 | 2015 |
| Papua New Guinea — 2017-01-30 | 2014 | 2015 | 2015 |
| Croatia — 2019-02-12 | 2018 | 2018 | 2017 |
| Madagascar — 2018-07-25 | 2017 | 2016 | 2016 |
| Moldova — 2016-11-09 | 2014 | 2014 | 2015 |
| Nauru — 2020-01-29 | 2018 | 2019 | 2018 |
| San Marino — 2020-04-02 | 2019 | 2018 | 2018 |
| Timor-Leste — 2016-06-24 | 2014 | 2013 | 2014 |
| Rwanda — 2017-07-13 | 2016 | 2015 | 2016 |
| Senegal — 2017-01-04 | 2015 | 2014 | 2015 |
| Senegal — 2018-01-12 | 2015 | 2016 | 2016 |
| Singapore — 2018-07-27 | 2017 | 2016 | 2017 |
| Solomon Islands — 2016-03-23 | 2014 | 2014 | 2015 |
| Solomon Islands — 2018-03-05 | 2015 | 2016 | 2015 |
| Ethiopia — 2016-10-04 | 2015 | 2014 | 2015 |
| The Gambia — 2017-07-03 | 2016 | 2015 | 2015 |
| Togo — 2017-12-15 | 2016 | 2015 | 2016 |
| United Kingdom — 2016-02-24 | 2014 | 2015 | 2014 |
| Vanuatu — 2016-10-31 | 2014 | 2014 | 2015 |

*(Full machine-readable version: `three_way_sl_weiqi_sa_report_level_20260917.csv`.)*

**Pattern:** Of these 59 rows, SA's selected year matches SL's (but not Weiqi's) in 23 cases, matches Weiqi's (but not SL's) in 18 cases, and matches neither in the remaining 18 (a genuine 3-way split, or SA/one side has no selection at all — e.g. Cabo Verde 2016-11-29). SA leans slightly toward agreeing with SL more than with Weiqi, but not so strongly that it can be read as "SA is just a copy of one side" — most of these remain genuinely three-sided disagreements over a hard header-layout judgment call.

---

## 5. Value-Level Consistency

Matching rows by `json_file` + `hierarchy_id` across all three versions, restricted to the 788 reports where all three found a table, yields 12,227 comparable line-item keys (10 blank on all sides, excluded). Of these, 12,133 have a non-null numeric value on **all three** sides:

| | Count | Share |
|---|---:|---:|
| Exact match on all three | 11,256 | 92.8% |
| Differ on at least one side | 877 | 7.2% |

**Pairwise exact-match rates** (useful for isolating which pair drives the disagreement):

| Pair | Match rate |
|---|---:|
| SL vs. Weiqi | 94.4% |
| SL vs. SA | 95.5% |
| Weiqi vs. SA | 95.1% |

SA agrees with each of the other two runs slightly more often than they agree with each other, but the differences are small (~1 point) — no pair is a clear outlier.

**109 reports** (13.8% of the 788 jointly-found reports) contain at least one differing value among the three:

| Category | Count | Interpretation |
|---|---:|---|
| Value mismatch **and** last-actual-year mismatch | 55 / 109 | Explained by different year-column selection (Section 4) |
| Value mismatch with **identical** year selection on all three | 54 / 109 | Genuine read/extraction inconsistency, unrelated to year selection |

### Magnitude

- Mean spread (max − min across the three values, differing rows only): **2.81** (GDP percentage points)
- Median spread: **1.2**
- Maximum spread: **48.0** (Kiribati — 2019-01-24, see below)
- 54.0% of differing rows have a spread exceeding 1 point (economically meaningful); only 9.5% are ≤0.15 (rounding-level noise)

### By category (differing rows only)

| Category | n | Mean spread |
|---|---:|---:|
| automatic_debt_dynamics | 329 | 1.91 |
| primary_balance | 243 | 2.75 |
| other_identified_flows | 86 | 1.74 |
| identified_flows | 76 | 5.16 |
| residual | 74 | 4.29 |
| change_in_debt | 69 | 4.42 |

As in the original two-way comparison, aggregate/subtotal line items (identified flows, residual, change in debt) carry the largest average error, since they inherit the error of upstream detail rows.

### Top 20 largest value discrepancies

| Report | Category | Line item | SL | Weiqi | SA | Max spread |
|---|---|---|---:|---:|---:|---:|
| Kiribati — 2019-01-24 | primary_balance | Primary deficit | -0.3 | -18.3 | -48.3 | 48.0 |
| Kiribati — 2019-01-24 | primary_balance | Primary (noninterest) expenditure | 125.4 | 110.5 | 78.5 | 46.9 |
| Kiribati — 2019-01-24 | identified_flows | Identified debt-creating flows | -2.2 | -22.2 | -48.3 | 46.1 |
| Kiribati — 2019-01-24 | residual | Residual | 1.7 | 21.7 | 47.7 | 46.0 |
| Nauru — 2020-01-29 | residual | Residual, including asset changes | 68.9 | 34.0 | 68.9 | 34.9 |
| Nauru — 2020-01-29 | identified_flows | Identified debt-creating flows | -72.6 | -42.4 | -72.6 | 30.2 |
| Nauru — 2020-01-29 | primary_balance | Primary (noninterest) expenditure | 96.6 | 125.6 | 96.6 | 29.0 |
| Argentina — 2019-07-15 | automatic_debt_dynamics | Exchange rate depreciation | 30.5 | 5.6 | 30.5 | 24.9 |
| Argentina — 2019-07-15 | change_in_debt | Change in gross public sector debt | 28.9 | 4.1 | 28.9 | 24.8 |
| Argentina — 2019-07-15 | identified_flows | Identified debt-creating flows | 25.1 | 1.1 | 25.1 | 24.0 |
| Argentina — 2019-07-15 | automatic_debt_dynamics | Automatic debt dynamics | 18.1 | -2.7 | 18.1 | 20.8 |
| Republic of Congo — 2020-01-27 | automatic_debt_dynamics | Automatic debt dynamics | -18.5 | 1.1 | -18.5 | 19.6 |
| Republic of Congo — 2020-01-27 | residual | Residual | -3.1 | -22.7 | -3.1 | 19.6 |
| Republic of Congo — 2020-01-27 | identified_flows | Identified debt-creating flows | -27.3 | -7.8 | -27.3 | 19.5 |
| Republic of Congo — 2020-01-27 | automatic_debt_dynamics | Contribution from real exchange rate depreciation | -10.5 | 9.0 | -10.5 | 19.5 |
| Kyrgyz Republic — 2018-02-22 | change_in_debt | Change in public sector debt | 12.6 | 12.6 | -6.8 | 19.4 |
| Kyrgyz Republic — 2018-02-22 | automatic_debt_dynamics | Automatic debt dynamics | 11.0 | 11.0 | -8.0 | 19.0 |
| Djibouti — 2017-04-06 | primary_balance | Primary (noninterest) expenditure | 39.8 | 39.8 | 58.1 | 18.3 |
| Kyrgyz Republic — 2018-02-22 | automatic_debt_dynamics | Contribution from real exchange rate depreciation | 12.7 | 12.7 | -5.6 | 18.3 |
| Mauritania — 2017-12-13 | change_in_debt | Change in public sector debt | 18.1 | 18.1 | 0.3 | 17.8 |

*(Full set of 877 rows: `three_way_sl_weiqi_sa_value_diffs_20260917.csv`.)*

Three cases stand out because SL and Weiqi agree exactly and SA is the outlier (Kyrgyz Republic, Djibouti, Mauritania 2017-12-13 above) — these are worth a targeted PDF check on SA's side specifically, since a 2-vs-1 split is a stronger signal than the more common 3-way scatter (e.g. Kiribati, Nauru, Argentina, Congo).

---

## 6. Full-Match Summary — Clean Reports vs. Reports Needing Review

Rolling up Sections 3–5 into a single per-report verdict: a report **fully matches** across all three versions if (a) `table_found` agrees on all three, and (b), when a table was found, `last_actual_year` agrees on all three **and** every comparable line-item value agrees exactly on all three. This deliberately excludes `confidence` and `manual_review_required` (self-reported metadata, covered separately in Section 7) since those don't reflect a difference in the actual extracted data.

| | Reports | Share of 907 |
|---|---:|---:|
| **Fully match across all three versions** | **789** | **87.0%** |
| — all three agree no table exists | 114 | 12.6% |
| — all three found the table, with identical year and values | 675 | 74.4% |
| **At least one disagreement** (table_found, year, and/or value) | **118** | **13.0%** |

### The 118 reports with at least one disagreement

| Country | Report date | Disagreement type(s) |
|---|---|---|
| Argentina | July 2019 | last_actual_year, value |
| Bangladesh | January 2016 | last_actual_year |
| Belize | March 2016 | last_actual_year, value |
| Benin | January 2016 | last_actual_year |
| Benin | April 2017 | last_actual_year, value |
| Bolivia | May 2020 | table_found |
| Bulgaria | February 2018 | value |
| Burkina Faso | December 2016 | last_actual_year, value |
| Burkina Faso | March 2018 | last_actual_year, value |
| Burkina Faso | December 2019 | value |
| Cabo Verde | November 2016 | last_actual_year |
| Cambodia | December 2019 | value |
| Central African Republic | April 2020 | value |
| Chad | August 2016 | last_actual_year, value |
| Chad | July 2019 | value |
| Chad | August 2020 | value |
| Côte D'Ivoire | December 2017 | last_actual_year, value |
| Côte D'Ivoire | June 2018 | table_found |
| Cyprus | January 2016 | last_actual_year, value |
| São Tomé and Príncipe | December 2017 | last_actual_year, value |
| São Tomé and Príncipe | August 2020 | value |
| Timor-Leste | May 2019 | value |
| Djibouti | April 2017 | last_actual_year, value |
| Dominica | July 2016 | last_actual_year, value |
| Dominica | December 2017 | last_actual_year, value |
| Ecuador | March 2019 | last_actual_year, value |
| Ecuador | May 2020 | value |
| Ghana | April 2020 | value |
| Greece | July 2017 | last_actual_year |
| Grenada | December 2016 | last_actual_year, value |
| Guatemala | August 2016 | value |
| Guatemala | June 2018 | last_actual_year, value |
| Guinea-Bissau | December 2016 | last_actual_year, value |
| Guinea-Bissau | December 2017 | last_actual_year, value |
| Guinea | December 2017 | last_actual_year, value |
| Guyana | July 2016 | last_actual_year, value |
| Guyana | July 2018 | last_actual_year, value |
| Honduras | June 2018 | last_actual_year, value |
| Indonesia | March 2016 | value |
| Indonesia | February 2018 | value |
| Afghanistan | November 2020 | value |
| Mauritania | May 2016 | last_actual_year, value |
| Mauritania | October 2017 | last_actual_year, value |
| Mauritania | December 2017 | last_actual_year, value |
| Israel | March 2017 | value |
| Italy | July 2017 | table_found |
| Lesotho | February 2018 | last_actual_year, value |
| Kiribati | January 24, 2019 | value |
| Kyrgyz Republic | February 2018 | last_actual_year, value |
| Lao PDR | February 2017 | last_actual_year, value |
| Lao PDR | March 2018 | last_actual_year, value |
| Liberia | January 2016 | last_actual_year, value |
| Liberia | November 2017 | last_actual_year, value |
| Liberia | June 2018 | last_actual_year, value |
| Liberia | June 2019 | value |
| Luxembourg | May 2017 | value |
| Malaysia | May 2016 | value |
| Malaysia | April 2017 | last_actual_year, value |
| Malaysia | March 2019 | last_actual_year, value |
| Maldives | December 2017 | last_actual_year, value |
| Maldives | September 2019 | value |
| Maldives | April 2020 | value |
| Mali | December 2016 | table_found |
| Mali | May 2020 | value |
| Mexico | November 2018 | value |
| Mexico | November 2020 | value |
| Myanmar | February 2017 | last_actual_year, value |
| Myanmar | July 2020 | value |
| Nepal | April 2020 | value |
| New Zealand | May 2017 | last_actual_year, value |
| Norway | September 2018 | value |
| Papua New Guinea | January 2017 | last_actual_year, value |
| Papua New Guinea | December 2017 | last_actual_year, value |
| Peru | May 2020 | value |
| Philippines | September 2016 | value |
| Philippines | November 2017 | value |
| Philippines | September 2018 | value |
| Armenia | July 2016 | value |
| Armenia | December 2016 | value |
| Armenia | July 2017 | value |
| Belarus | January 2019 | value |
| Republic of Congo | January 2020 | value |
| Croatia | February 2019 | last_actual_year, value |
| Equatorial Guinea | November 2016 | value |
| Equatorial Guinea | December 2019 | value |
| Kosovo | March 2017 | value |
| Lithuania | June 2017 | value |
| Madagascar | July 2018 | last_actual_year, value |
| Madagascar | August 2020 | value |
| Moldova | November 2016 | last_actual_year, value |
| Moldova | September 2019 | value |
| Nauru | January 2020 | last_actual_year, value |
| Poland | January 2017 | value |
| San Marino | April 2017 | value |
| San Marino | April 2020 | last_actual_year, value |
| Slovenia | February 2019 | value |
| Timor-Leste | June 2016 | last_actual_year, value |
| Rwanda | January 2016 | value |
| Rwanda | July 2017 | last_actual_year, value |
| Saudi Arabia | October 2017 | value |
| Senegal | January 2016 | value |
| Senegal | January 2017 | last_actual_year, value |
| Senegal | January 2018 | last_actual_year, value |
| Singapore | July 2018 | last_actual_year, value |
| Solomon Islands | March 2016 | last_actual_year, value |
| Solomon Islands | March 2018 | last_actual_year, value |
| Sri Lanka | May 2019 | value |
| St. Vincent and the Grenadines | May 2020 | value |
| Sweden | March 2019 | value |
| Thailand | June 2018 | value |
| Ethiopia | October 2016 | last_actual_year, value |
| The Gambia | June 2017 | last_actual_year, value |
| Togo | December 2017 | last_actual_year, value |
| Ukraine | June 2020 | value |
| United Kingdom | February 2016 | last_actual_year, value |
| Tanzania | February 2016 | table_found |
| Vanuatu | October 2016 | last_actual_year, value |
| Zambia | August 2019 | value |

*(Machine-readable version, with the raw country-name spelling from each source file preserved: `three_way_sl_weiqi_sa_disagreement_list_20260917.csv`.)*

Of the 118: 59 (50%) involve a `last_actual_year` disagreement (with or without a resulting value mismatch), 54 (46%) are pure value-read inconsistencies with an identical selected year on all three, and 5 (4%) are `table_found` disagreements. The year-selection issue remains the single largest identifiable driver (see Recommendations).

### 6.1 Which of the 118 are a clean "two-vs-one" pattern?

For each of the 118 disagreeing reports, a pairwise "fully match" check asks: do any **two** of the three versions agree completely with each other (same `table_found`, same `last_actual_year` where a table exists, and every comparable value identical), leaving the third version as the lone outlier? This matters because a 2-vs-1 split is a much stronger error signal for manual review than a report where all three versions differ from each other — a two-reader agreement is far less likely to be coincidence.

| | Reports | Share of 118 |
|---|---:|---:|
| **Exactly two versions fully match each other (clean outlier pattern)** | **96** | **81.4%** |
| No two versions fully agree with each other (genuine 3-way scatter) | 22 | 18.6% |

Of the 96 clean two-vs-one cases, **Weiqi is the lone outlier most often**:

| Outlier version | Count | Share of 96 |
|---|---:|---:|
| Weiqi | 43 | 44.8% |
| SL | 31 | 32.3% |
| SA | 22 | 22.9% |

This does not necessarily mean Weiqi's run is "worse" — it only shows that, when two of the three agree and one doesn't, that one is most often Weiqi. Combined with SL and SA's more similar export formatting (Section 8), one plausible explanation is that SL's and SA's compiler scripts (and possibly closer prompt/code lineage) simply produce more similar edge-case judgment calls to each other than either does to Weiqi's — this is worth confirming directly with Weiqi rather than assuming from the data alone.

**All 96 reports where two versions fully match and one is the outlier:**

| Country | Report date | Fully-matching pair | Outlier | Note |
|---|---|---|---|---|
| Argentina | July 2019 | SL=SA | Weiqi | |
| Armenia | December 2016 | Weiqi=SA | SL | |
| Armenia | July 2016 | Weiqi=SA | SL | |
| Armenia | July 2017 | Weiqi=SA | SL | |
| Belize | March 2016 | SL=Weiqi | SA | |
| Benin | April 2017 | SL=Weiqi | SA | |
| Bolivia | May 2020 | Weiqi=SA | SL | SL found no table; Weiqi & SA agree on year 2019 and all 15 values |
| Bulgaria | February 2018 | Weiqi=SA | SL | |
| Burkina Faso | December 2016 | SL=SA | Weiqi | |
| Burkina Faso | December 2019 | Weiqi=SA | SL | |
| Burkina Faso | March 2018 | SL=SA | Weiqi | |
| Chad | August 2016 | Weiqi=SA | SL | |
| Croatia | February 2019 | SL=Weiqi | SA | |
| Cyprus | January 2016 | SL=Weiqi | SA | |
| Côte d'Ivoire | December 2017 | SL=SA | Weiqi | |
| Côte d'Ivoire | June 2018 | SL=Weiqi | SA | SA found no table; SL & Weiqi agree on year 2016 and all 17 values |
| Djibouti | April 2017 | SL=Weiqi | SA | |
| Dominica | December 2017 | SL=Weiqi | SA | |
| Dominica | July 2016 | SL=SA | Weiqi | |
| Ecuador | March 2019 | Weiqi=SA | SL | |
| Ecuador | May 2020 | SL=SA | Weiqi | |
| Equatorial Guinea | December 2019 | SL=SA | Weiqi | |
| Equatorial Guinea | November 2016 | SL=SA | Weiqi | |
| Ethiopia | October 2016 | SL=SA | Weiqi | |
| Ghana | April 2020 | Weiqi=SA | SL | |
| Grenada | December 2016 | SL=SA | Weiqi | |
| Guatemala | August 2016 | Weiqi=SA | SL | |
| Guatemala | June 2018 | SL=SA | Weiqi | |
| Guinea | December 2017 | Weiqi=SA | SL | |
| Guinea-Bissau | December 2016 | SL=Weiqi | SA | |
| Guinea-Bissau | December 2017 | SL=SA | Weiqi | |
| Guyana | July 2018 | Weiqi=SA | SL | |
| Honduras | June 2018 | SL=Weiqi | SA | |
| Indonesia | February 2018 | SL=SA | Weiqi | |
| Indonesia | March 2016 | SL=SA | Weiqi | |
| Israel | March 2017 | SL=SA | Weiqi | |
| Italy | July 2017 | SL=SA | Weiqi | Weiqi found no table; SL & SA agree on year 2016 and all 15 values |
| Kosovo | March 2017 | SL=SA | Weiqi | |
| Kyrgyz Republic | February 2018 | SL=Weiqi | SA | |
| Lao PDR | February 2017 | SL=SA | Weiqi | |
| Lao PDR | March 2018 | Weiqi=SA | SL | |
| Lesotho | February 2018 | SL=SA | Weiqi | |
| Liberia | January 2016 | SL=SA | Weiqi | |
| Liberia | June 2018 | Weiqi=SA | SL | |
| Liberia | November 2017 | SL=SA | Weiqi | |
| Lithuania | June 2017 | SL=Weiqi | SA | |
| Luxembourg | May 2017 | SL=SA | Weiqi | |
| Madagascar | August 2020 | SL=Weiqi | SA | |
| Madagascar | July 2018 | Weiqi=SA | SL | |
| Malaysia | March 2019 | Weiqi=SA | SL | |
| Malaysia | May 2016 | SL=SA | Weiqi | |
| Maldives | December 2017 | Weiqi=SA | SL | |
| Maldives | September 2019 | SL=SA | Weiqi | |
| Mauritania | December 2017 | SL=Weiqi | SA | |
| Mauritania | May 2016 | Weiqi=SA | SL | |
| Mauritania | October 2017 | Weiqi=SA | SL | |
| Mexico | November 2018 | SL=Weiqi | SA | |
| Mexico | November 2020 | SL=SA | Weiqi | |
| Moldova | November 2016 | SL=Weiqi | SA | |
| Myanmar | February 2017 | SL=Weiqi | SA | |
| Myanmar | July 2020 | SL=SA | Weiqi | |
| Nauru | January 2020 | SL=SA | Weiqi | |
| Nepal | April 2020 | Weiqi=SA | SL | |
| New Zealand | May 2017 | Weiqi=SA | SL | |
| Norway | September 2018 | SL=Weiqi | SA | |
| Papua New Guinea | December 2017 | Weiqi=SA | SL | |
| Papua New Guinea | January 2017 | Weiqi=SA | SL | |
| Peru | May 2020 | SL=SA | Weiqi | |
| Philippines | November 2017 | SL=Weiqi | SA | |
| Philippines | September 2016 | SL=SA | Weiqi | |
| Philippines | September 2018 | Weiqi=SA | SL | |
| Poland | January 2017 | Weiqi=SA | SL | |
| Rwanda | January 2016 | SL=SA | Weiqi | |
| Rwanda | July 2017 | SL=SA | Weiqi | |
| San Marino | April 2017 | SL=SA | Weiqi | |
| San Marino | April 2020 | Weiqi=SA | SL | |
| Saudi Arabia | October 2017 | Weiqi=SA | SL | |
| Senegal | January 2016 | Weiqi=SA | SL | |
| Senegal | January 2017 | SL=SA | Weiqi | |
| Senegal | January 2018 | Weiqi=SA | SL | |
| Singapore | July 2018 | SL=SA | Weiqi | |
| Slovenia | February 2019 | SL=SA | Weiqi | |
| Solomon Islands | March 2016 | SL=Weiqi | SA | |
| Solomon Islands | March 2018 | SL=SA | Weiqi | |
| Sri Lanka | May 2019 | SL=SA | Weiqi | |
| St. Vincent and the Grenadines | May 2020 | Weiqi=SA | SL | |
| Sweden | March 2019 | SL=SA | Weiqi | |
| São Tomé and Príncipe | December 2017 | SL=Weiqi | SA | |
| Tanzania | February 2016 | SL=Weiqi | SA | SL & Weiqi both concluded no DSA table exists; SA found one (no values to compare) |
| Thailand | June 2018 | SL=SA | Weiqi | |
| The Gambia | June 2017 | Weiqi=SA | SL | |
| Timor-Leste | June 2016 | SL=SA | Weiqi | |
| Togo | December 2017 | SL=SA | Weiqi | |
| United Kingdom | February 2016 | SL=SA | Weiqi | |
| Vanuatu | October 2016 | SL=Weiqi | SA | |
| Zambia | August 2019 | SL=SA | Weiqi | |

*(Machine-readable version: `three_way_sl_weiqi_sa_two_of_three_match_20260917.csv`. The 22 reports with no two-way agreement — a genuine 3-way scatter, or a missing year selection on more than one side — are: Afghanistan Nov 2020, Bangladesh Jan 2016, Belarus Jan 2019, Benin Jan 2016, Cabo Verde Nov 2016, Cambodia Dec 2019, Central African Republic Apr 2020, Chad Jul 2019, Chad Aug 2020, Congo Jan 2020, Greece Jul 2017, Guyana Jul 2016, Kiribati Jan 2019, Liberia Jun 2019, Malaysia Apr 2017, Maldives Apr 2020, Mali May 2020, Mali Dec 2016 — a table_found split where Weiqi found a table with no values and no year, so it cannot pairwise-match SA's year either — Moldova Sep 2019, São Tomé and Príncipe Aug 2020, Timor-Leste May 2019, and Ukraine Jun 2020.)*

---

## 7. Behavioral Differences Introduced by SA's Modified Pipeline

Because SA ran his own modified version of the original codebase (not SL's later "last actual year" revision), a few systematic — not random — differences show up that are worth flagging separately from ordinary read noise:

**`manual_review_required` disagrees on 93/788 reports (88.2% agreement)** — substantially noisier than `table_found` or `framework`. The disagreement is almost entirely one-directional:

| SL | Weiqi | SA | Count |
|---|---|---|---:|
| No | No | **Yes** | 90 |
| No | Yes | No | 2 |
| No | Yes | Yes | 1 |

SA's pipeline flags manual review far more readily than SL's or Weiqi's original code. This looks like a deliberate validation change on SA's side (stricter last-actual-year self-consistency check) rather than noise — but it also means `manual_review_required` cannot currently be used as a cross-version filter. Of the 109 reports with an actual value disagreement, only 40 were flagged by *any* version's `manual_review_required` — confirming (as in the original 92-report rerun study) that this flag is not a reliable predictor of which reports actually have extraction problems.

**`extraction_method` disagrees on 6/788 reports.** Five of these are ordinary fallback-tier differences (e.g. one side used `selected_pdf_direct`, another used a compressed image fallback for the same report). The sixth is more interesting: SA's method values include `pymupdf_pillow_multi_orientation_retry`, a method name that does not appear anywhere in SL's or Weiqi's output. This confirms SA's code adds new fallback logic (handling rotated/landscape pages) that is not present in the original codebase used by SL and Weiqi — a genuine capability difference, not a bug, but it means extraction-method comparisons across SA and the other two are not apples-to-apples for the handful of reports where it triggers (Bangladesh 2016-02-01, Côte d'Ivoire 2020-04-23).

**Self-reported `confidence` agrees 89.1% (702/788) exactly**; 83 reports are a one-notch high/medium (or medium/low) difference, and 3 reports (Bangladesh 2016-02-01, Greece 2017-07-20, Singapore 2018-07-27) show a full high-vs-low spread across the three versions.

---

## 8. Formatting Differences (cosmetic, but will break naive diffs)

These do not change meaning but will produce false positives in a row-by-row script comparison unless normalized first — this comparison normalized all of them before matching.

| Field | SL | Weiqi | SA |
|---|---|---|---|
| `table_found` | `True` / `False` (title case) | `TRUE` / `FALSE` (uppercase) | `True` / `False` (title case, matches SL) |
| `publication_date` | Full, e.g. `February 2016` | Abbreviated, e.g. `Feb-16` | Full, e.g. `February 2016` (matches SL) |
| `page_pdf`, `level` | Float string, e.g. `61.0`, `0.0` | Integer string, e.g. `61`, `0` | Float string, e.g. `61.0`, `0.0` (matches SL) |
| Country name spelling | `Côte D'Ivoire` (apostrophe capitalized by title-casing) | `Côte d'Ivoire` | `Côte D'Ivoire` (matches SL) |
| Hong Kong SAR name | 1 spelling (n/a — missing from SL) | Straight hyphen/quote variant | Same variant as Weiqi |

SA's export formatting is closer to SL's than to Weiqi's on every cosmetic dimension checked, which is expected since SL's `json_to_excel_dsa_v6_flexible_actual.py`-style compiler (with `.title()` country-name cleanup and full publication-date strings) appears to be the common ancestor SA's compiler script was built from.

---

## 9. Recommendations

1. **Manually verify the 5 `table_found` disagreements** against the source PDF, prioritizing the 2 new ones not seen in the original two-way comparison: Côte d'Ivoire — 2018-06-25 (SL & Weiqi say table found, SA says not found) and Tanzania — 2016-02-01 (SL & Weiqi say not found, SA says found).
2. **Prioritize the 3 reports where SA is the lone outlier against an SL/Weiqi agreement** (Kyrgyz Republic — 2018-02-22, Djibouti — 2017-04-06, Mauritania — 2017-12-13) — a 2-vs-1 split with two independent readers agreeing is a stronger error signal than the typical 3-way scatter.
3. **Manually pull the source PDF for Kiribati — 2019-01-24 and Nauru — 2020-01-29**, the two largest and most concerning value gaps (spreads of 46–48 and 29–35 points respectively), where all three versions disagree with each other even though extraction "succeeded" on all sides.
4. **Do not use `manual_review_required` as a cross-version reliability filter** until the flagging logic is reconciled — SA's stricter flag inflates disagreement counts on this field without reliably catching the reports that actually have value errors (only 40/109 value-mismatch reports were flagged by anyone).
5. **Continue treating the 59 last-actual-year disagreements as the top single fix** — as in the original comparison, standardizing the "Actual" column rule remains the largest, most explainable, most fixable source of downstream value disagreement (55 of the 109 value-mismatch reports trace directly to it).
6. **Overall, the three runs still agree closely**: 788/907 reports agree on table detection across all three, and 92.8% of comparable values match exactly across all three. Focus manual review on the ~120 reports flagged in this document (59 year mismatches + 54 same-year value mismatches, with some overlap) rather than re-checking the full sample.

---

*Data sources: `dsa_decomposition_sl_20260901.csv` (SL), `dsa_decomposition_labels_BH_run5_flexible_actual_thinking_weiqi.csv` (Weiqi), and `dsa_decomposition_labels_2016-2020_sa.csv` + `dsa_decomposition_labels_2016-2020_errors_sa.csv` (SA), all in `output/2016-2020/compiled_csv/`. Detail files generated for this comparison: `three_way_sl_weiqi_sa_report_level_20260917.csv`, `three_way_sl_weiqi_sa_value_diffs_20260917.csv`. Builds on the earlier `comparison_summary.md` (SL vs. Weiqi only).*
