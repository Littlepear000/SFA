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
- `three_way_sl_weiqi_sa_report_level_20260917_v2.csv` — one row per report (907 rows), all three versions' key fields side by side, with agreement flags.
- `three_way_sl_weiqi_sa_value_diffs_20260917_v2.csv` — all 877 line-item value mismatches among reports where all three versions found a table.
- `three_way_sl_weiqi_sa_disagreement_list_20260917_v2.csv` — the 118 reports with any disagreement (table_found, last_actual_year, and/or value), tagged by type (Section 6).
- `three_way_sl_weiqi_sa_two_of_three_match_20260917_v2.csv` — the 96 of those 118 reports where exactly two versions fully agree with each other, with the fully-matching pair and the outlier version (Section 6.1).

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

| PDF file name | Country |
|---|---|
| `People's Republic of China-Hong Kong Special Administrative Region_2017-01-12.pdf` | Hong Kong SAR, China |
| `People's Republic of China-Hong Kong Special Administrative Region_2018-01-22.pdf` | Hong Kong SAR, China |
| `People's Republic of China-Hong Kong Special Administrative Region_2019-01-24.pdf` | Hong Kong SAR, China |
| `People's Republic of China-Hong Kong Special Administrative Region_2019-12-30.pdf` | Hong Kong SAR, China |
| `People’s Republic of China—Hong Kong Special Administrative Region_2016-01-19.pdf` | Hong Kong SAR, China |

---

## 3. Table Detection & Framework Classification

Across the 907 reports common to all three, 3-way agreement on `table_found` is **99.4% (902/907)**.

**The 5 disagreeing reports:**

| PDF file name | SL | Weiqi | SA |
|---|---|---|---|
| `Bolivia_2020-05-29.pdf` | No table | Table found | Table found |
| `Cote d'Ivoire_2018-06-25.pdf` | Table found | Table found | No table |
| `Italy_2017-07-27.pdf` | Table found | No table | Table found |
| `Mali_2016-12-07.pdf` | No table | Table found | Table found |
| `United Republic of Tanzania_2016-02-01.pdf` | No table | No table | Table found |

Of the original comparison's 3 `table_found` disagreements (Bolivia, Italy, Mali), SA sides with Weiqi on all three (i.e., SA also finds a table). Côte d'Ivoire 2018-06-25 and Tanzania 2016-02-01 are new disagreements not flagged in the original SL-vs-Weiqi document — worth a manual PDF check (see Recommendations).

Restricting to the **788 reports where all three found a table**, framework classification (MAC_DSA / LIC_DSF / UNKNOWN) agrees 99.5% of the time (784/788).

---

## 4. "Last Actual Year" Disagreements — Still the Main Systematic Driver

Among the 788 jointly-found reports, all three versions select the **same** last-actual year in 729 cases (92.5%). The remaining **59 reports (7.5%)** show at least one version disagreeing with the other two:

| PDF file name | SL year | Weiqi year | SA year |
|---|---|---|---|
| `Argentina_2019-07-15.pdf` | 2018 | 2017 | 2018 |
| `Bangladesh_2016-02-01.pdf` | — | — | 2014 |
| `Belize_2016-03-28.pdf` | 2013 | 2013 | 2014 |
| `Benin_2016-01-07.pdf` | — | — | 2014 |
| `Benin_2017-04-26.pdf` | 2014 | 2014 | 2015 |
| `Burkina Faso_2016-12-22.pdf` | 2014 | 2015 | 2014 |
| `Burkina Faso_2018-03-15.pdf` | 2016 | 2015 | 2016 |
| `Cabo Verde_2016-11-29.pdf` | 2015 | — | — |
| `Chad_2016-08-17.pdf` | 2014 | 2015 | 2015 |
| `Cote d'Ivoire_2017-12-15.pdf` | 2016 | 2015 | 2016 |
| `Cyprus_2016-01-29.pdf` | 2015 | 2015 | 2014 |
| `Democratic Republic of São Tomé and Príncipe_2017-12-18.pdf` | 2015 | 2015 | 2016 |
| `Djibouti_2017-04-06.pdf` | 2014 | 2014 | 2015 |
| `Dominica_2016-07-20.pdf` | 2014 | 2013 | 2014 |
| `Dominica_2017-12-20.pdf` | 2014 | 2014 | 2015 |
| `Ecuador_2019-03-20.pdf` | 2018 | 2017 | 2017 |
| `Greece_2017-07-20.pdf` | 2016 | — | 2016 |
| `Grenada_2016-12-21.pdf` | 2015 | 2014 | 2015 |
| `Guatemala_2018-06-08.pdf` | 2016 | 2017 | 2016 |
| `Guinea-Bissau_2016-12-28.pdf` | 2014 | 2014 | 2015 |
| `Guinea-Bissau_2017-12-18.pdf` | 2015 | 2016 | 2015 |
| `Guinea_2017-12-19.pdf` | 2016 | 2015 | 2015 |
| `Guyana_2016-07-07.pdf` | 2015 | 2014 | 2015 |
| `Guyana_2018-07-16.pdf` | 2017 | 2016 | 2016 |
| `Honduras_2018-07-03.pdf` | 2016 | 2016 | 2017 |
| `Islamic Republic of Mauritania_2016-05-11.pdf` | 2015 | 2014 | 2014 |
| `Islamic Republic of Mauritania_2017-10-16.pdf` | 2016 | 2015 | 2015 |
| `Islamic Republic of Mauritania_2017-12-13.pdf` | 2015 | 2015 | 2016 |
| `Kingdom of Lesotho_2018-02-28.pdf` | 2016 | 2015 | 2016 |
| `Kyrgyz Republic_2018-02-22.pdf` | 2015 | 2015 | 2016 |
| `Lao People's Democratic Republic_2017-02-15.pdf` | 2014 | 2015 | 2014 |
| `Lao People’s Democratic Republic_2018-03-23.pdf` | 2015 | 2016 | 2016 |
| `Liberia_2016-01-08.pdf` | 2014 | 2013 | 2014 |
| `Liberia_2017-11-20.pdf` | 2016 | 2015 | 2016 |
| `Liberia_2018-06-15.pdf` | 2017 | 2016 | 2016 |
| `Malaysia_2017-04-28.pdf` | 2016 | 2015 | 2015 |
| `Malaysia_2019-03-08.pdf` | 2017 | 2018 | 2018 |
| `Maldives_2017-12-01.pdf` | 2015 | 2016 | 2016 |
| `Myanmar_2017-02-02.pdf` | 2014 | 2014 | 2015 |
| `New Zealand_2017-05-08.pdf` | 2009-2014 | 2015 | 2015 |
| `Papua New Guinea_2017-01-30.pdf` | 2014 | 2015 | 2015 |
| `Papua New Guinea_2017-12-29.pdf` | 2016 | 2015 | 2015 |
| `Republic of Croatia_2019-02-12.pdf` | 2018 | 2018 | 2017 |
| `Republic of Madagascar_2018-07-25.pdf` | 2017 | 2016 | 2016 |
| `Republic of Moldova_2016-11-09.pdf` | 2014 | 2014 | 2015 |
| `Republic of Nauru_2020-01-29.pdf` | 2018 | 2019 | 2018 |
| `Republic of San Marino_2020-04-02.pdf` | 2019 | 2018 | 2018 |
| `Republic of Timor-Leste_2016-06-24.pdf` | 2014 | 2013 | 2014 |
| `Rwanda_2017-07-13.pdf` | 2016 | 2015 | 2016 |
| `Senegal_2017-01-04.pdf` | 2015 | 2014 | 2015 |
| `Senegal_2018-01-12.pdf` | 2015 | 2016 | 2016 |
| `Singapore_2018-07-27.pdf` | 2017 | 2016 | 2017 |
| `Solomon Islands_2016-03-23.pdf` | 2014 | 2014 | 2015 |
| `Solomon Islands_2018-03-05.pdf` | 2015 | 2016 | 2015 |
| `The Federal Democratic Republic of Ethiopia_2016-10-04.pdf` | 2015 | 2014 | 2015 |
| `The Gambia_2017-07-03.pdf` | 2016 | 2015 | 2015 |
| `Togo_2017-12-15.pdf` | 2016 | 2015 | 2016 |
| `United Kingdom_2016-02-24.pdf` | 2014 | 2015 | 2014 |
| `Vanuatu_2016-10-31.pdf` | 2014 | 2014 | 2015 |

*(Full machine-readable version: `three_way_sl_weiqi_sa_report_level_20260917_v2.csv`.)*

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

| PDF file name | Category | Line item | SL | Weiqi | SA | Max spread |
|---|---|---|---:|---:|---:|---:|
| `Kiribati_2019-01-24.pdf` | primary_balance | Primary deficit | -0.3 | -18.3 | -48.3 | 48.0 |
| `Kiribati_2019-01-24.pdf` | primary_balance | Primary (noninterest) expenditure | 125.4 | 110.5 | 78.5 | 46.9 |
| `Kiribati_2019-01-24.pdf` | identified_flows | Identified debt-creating flows | -2.2 | -22.2 | -48.3 | 46.1 |
| `Kiribati_2019-01-24.pdf` | residual | Residual | 1.7 | 21.7 | 47.7 | 46.0 |
| `Republic of Nauru_2020-01-29.pdf` | residual | Residual, including asset changes 8/ | 68.9 | 34.0 | 68.9 | 34.9 |
| `Republic of Nauru_2020-01-29.pdf` | identified_flows | Identified debt-creating flows | -72.6 | -42.4 | -72.6 | 30.2 |
| `Republic of Nauru_2020-01-29.pdf` | primary_balance | Primary (noninterest) expenditure | 96.6 | 125.6 | 96.6 | 29.0 |
| `Argentina_2019-07-15.pdf` | automatic_debt_dynamics | Exchange rate depreciation 7/ | 30.5 | 5.6 | 30.5 | 24.9 |
| `Argentina_2019-07-15.pdf` | change_in_debt | Change in gross public sector debt | 28.9 | 4.1 | 28.9 | 24.8 |
| `Argentina_2019-07-15.pdf` | identified_flows | Identified debt-creating flows | 25.1 | 1.1 | 25.1 | 24.0 |
| `Argentina_2019-07-15.pdf` | automatic_debt_dynamics | Automatic debt dynamics 5/ | 18.1 | -2.7 | 18.1 | 20.8 |
| `Republic of Congo_2020-01-27.pdf` | automatic_debt_dynamics | Automatic debt dynamics | -18.5 | 1.1 | -18.5 | 19.6 |
| `Republic of Congo_2020-01-27.pdf` | residual | Residual | -3.1 | -22.7 | -3.1 | 19.6 |
| `Republic of Congo_2020-01-27.pdf` | identified_flows | Identified debt-creating flows | -27.3 | -7.8 | -27.3 | 19.5 |
| `Republic of Congo_2020-01-27.pdf` | automatic_debt_dynamics | Contribution from real exchange rate depreciation | -10.5 | 9.0 | -10.5 | 19.5 |
| `Kyrgyz Republic_2018-02-22.pdf` | change_in_debt | Change in public sector debt | 12.6 | 12.6 | -6.8 | 19.4 |
| `Kyrgyz Republic_2018-02-22.pdf` | automatic_debt_dynamics | Automatic debt dynamics | 11.0 | 11.0 | -8.0 | 19.0 |
| `Djibouti_2017-04-06.pdf` | primary_balance | Primary (noninterest) expenditure | 39.8 | 39.8 | 58.1 | 18.3 |
| `Kyrgyz Republic_2018-02-22.pdf` | automatic_debt_dynamics | Contribution from real exchange rate depreciation | 12.7 | 12.7 | -5.6 | 18.3 |
| `Islamic Republic of Mauritania_2017-12-13.pdf` | change_in_debt | Change in public sector debt | 18.1 | 18.1 | 0.3 | 17.8 |

*(Full set of 877 rows: `three_way_sl_weiqi_sa_value_diffs_20260917_v2.csv`.)*

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

| PDF file name | Country | Disagreement type(s) |
|---|---|---|
| `Argentina_2019-07-15.pdf` | Argentina | last_actual_year, value |
| `Bangladesh_2016-02-01.pdf` | Bangladesh | last_actual_year |
| `Belize_2016-03-28.pdf` | Belize | last_actual_year, value |
| `Benin_2016-01-07.pdf` | Benin | last_actual_year |
| `Benin_2017-04-26.pdf` | Benin | last_actual_year, value |
| `Bolivia_2020-05-29.pdf` | Bolivia | table_found |
| `Bulgaria_2018-02-21.pdf` | Bulgaria | value |
| `Burkina Faso_2016-12-22.pdf` | Burkina Faso | last_actual_year, value |
| `Burkina Faso_2018-03-15.pdf` | Burkina Faso | last_actual_year, value |
| `Burkina Faso_2019-12-30.pdf` | Burkina Faso | value |
| `Cabo Verde_2016-11-29.pdf` | Cabo Verde | last_actual_year |
| `Cambodia_2019-12-23.pdf` | Cambodia | value |
| `Central African Republic_2020-04-28.pdf` | Central African Republic | value |
| `Chad_2016-08-17.pdf` | Chad | last_actual_year, value |
| `Chad_2019-07-31.pdf` | Chad | value |
| `Chad_2020-08-05.pdf` | Chad | value |
| `Cote d'Ivoire_2017-12-15.pdf` | Côte d'Ivoire | last_actual_year, value |
| `Cote d'Ivoire_2018-06-25.pdf` | Côte d'Ivoire | table_found |
| `Cyprus_2016-01-29.pdf` | Cyprus | last_actual_year, value |
| `Democratic Republic of São Tomé and Príncipe_2017-12-18.pdf` | São Tomé and Príncipe | last_actual_year, value |
| `Democratic Republic of São Tomé and Príncipe_2020-08-04.pdf` | São Tomé and Príncipe | value |
| `Democratic Republic of Timor-Leste_2019-05-07.pdf` | Timor-Leste | value |
| `Djibouti_2017-04-06.pdf` | Djibouti | last_actual_year, value |
| `Dominica_2016-07-20.pdf` | Dominica | last_actual_year, value |
| `Dominica_2017-12-20.pdf` | Dominica | last_actual_year, value |
| `Ecuador_2019-03-20.pdf` | Ecuador | last_actual_year, value |
| `Ecuador_2020-05-28.pdf` | Ecuador | value |
| `Ghana_2020-04-16.pdf` | Ghana | value |
| `Greece_2017-07-20.pdf` | Greece | last_actual_year |
| `Grenada_2016-12-21.pdf` | Grenada | last_actual_year, value |
| `Guatemala_2016-09-01.pdf` | Guatemala | value |
| `Guatemala_2018-06-08.pdf` | Guatemala | last_actual_year, value |
| `Guinea-Bissau_2016-12-28.pdf` | Guinea-Bissau | last_actual_year, value |
| `Guinea-Bissau_2017-12-18.pdf` | Guinea-Bissau | last_actual_year, value |
| `Guinea_2017-12-19.pdf` | Guinea | last_actual_year, value |
| `Guyana_2016-07-07.pdf` | Guyana | last_actual_year, value |
| `Guyana_2018-07-16.pdf` | Guyana | last_actual_year, value |
| `Honduras_2018-07-03.pdf` | Honduras | last_actual_year, value |
| `Indonesia_2016-03-15.pdf` | Indonesia | value |
| `Indonesia_2018-02-06.pdf` | Indonesia | value |
| `Islamic Republic of Afghanistan_2020-11-13.pdf` | Afghanistan | value |
| `Islamic Republic of Mauritania_2016-05-11.pdf` | Mauritania | last_actual_year, value |
| `Islamic Republic of Mauritania_2017-10-16.pdf` | Mauritania | last_actual_year, value |
| `Islamic Republic of Mauritania_2017-12-13.pdf` | Mauritania | last_actual_year, value |
| `Israel_2017-03-28.pdf` | Israel | value |
| `Italy_2017-07-27.pdf` | Italy | table_found |
| `Kingdom of Lesotho_2018-02-28.pdf` | Lesotho | last_actual_year, value |
| `Kiribati_2019-01-24.pdf` | Kiribati | value |
| `Kyrgyz Republic_2018-02-22.pdf` | Kyrgyz Republic | last_actual_year, value |
| `Lao People's Democratic Republic_2017-02-15.pdf` | Lao PDR | last_actual_year, value |
| `Lao People’s Democratic Republic_2018-03-23.pdf` | Lao PDR | last_actual_year, value |
| `Liberia_2016-01-08.pdf` | Liberia | last_actual_year, value |
| `Liberia_2017-11-20.pdf` | Liberia | last_actual_year, value |
| `Liberia_2018-06-15.pdf` | Liberia | last_actual_year, value |
| `Liberia_2019-06-19.pdf` | Liberia | value |
| `Luxembourg_2017-05-10.pdf` | Luxembourg | value |
| `Malaysia_2016-05-04.pdf` | Malaysia | value |
| `Malaysia_2017-04-28.pdf` | Malaysia | last_actual_year, value |
| `Malaysia_2019-03-08.pdf` | Malaysia | last_actual_year, value |
| `Maldives_2017-12-01.pdf` | Maldives | last_actual_year, value |
| `Maldives_2019-09-03_CR2019-281.pdf` | Maldives | value |
| `Maldives_2020-04-23.pdf` | Maldives | value |
| `Mali_2016-12-07.pdf` | Mali | table_found |
| `Mali_2020-05-08.pdf` | Mali | value |
| `Mexico_2018-11-27.pdf` | Mexico | value |
| `Mexico_2020-11-20.pdf` | Mexico | value |
| `Myanmar_2017-02-02.pdf` | Myanmar | last_actual_year, value |
| `Myanmar_2020-07-02.pdf` | Myanmar | value |
| `Nepal_2020-04-06.pdf` | Nepal | value |
| `New Zealand_2017-05-08.pdf` | New Zealand | last_actual_year, value |
| `Norway_2018-09-17.pdf` | Norway | value |
| `Papua New Guinea_2017-01-30.pdf` | Papua New Guinea | last_actual_year, value |
| `Papua New Guinea_2017-12-29.pdf` | Papua New Guinea | last_actual_year, value |
| `Peru_2020-05-29.pdf` | Peru | value |
| `Philippines_2016-09-26.pdf` | Philippines | value |
| `Philippines_2017-11-10.pdf` | Philippines | value |
| `Philippines_2018-09-27.pdf` | Philippines | value |
| `Republic of Armenia_2016-07-21.pdf` | Armenia | value |
| `Republic of Armenia_2016-12-13.pdf` | Armenia | value |
| `Republic of Armenia_2017-07-19.pdf` | Armenia | value |
| `Republic of Belarus_2019-01-17.pdf` | Belarus | value |
| `Republic of Congo_2020-01-27.pdf` | Republic of Congo | value |
| `Republic of Croatia_2019-02-12.pdf` | Croatia | last_actual_year, value |
| `Republic of Equatorial Guinea_2016-11-16.pdf` | Equatorial Guinea | value |
| `Republic of Equatorial Guinea_2019-12-20.pdf` | Equatorial Guinea | value |
| `Republic of Kosovo_2017-03-17.pdf` | Kosovo | value |
| `Republic of Lithuania_2017-06-30.pdf` | Lithuania | value |
| `Republic of Madagascar_2018-07-25.pdf` | Madagascar | last_actual_year, value |
| `Republic of Madagascar_2020-08-27.pdf` | Madagascar | value |
| `Republic of Moldova_2016-11-09.pdf` | Moldova | last_actual_year, value |
| `Republic of Moldova_2019-09-25.pdf` | Moldova | value |
| `Republic of Nauru_2020-01-29.pdf` | Nauru | last_actual_year, value |
| `Republic of Poland_2017-01-18.pdf` | Poland | value |
| `Republic of San Marino_2017-04-06.pdf` | San Marino | value |
| `Republic of San Marino_2020-04-02.pdf` | San Marino | last_actual_year, value |
| `Republic of Slovenia_2019-02-18.pdf` | Slovenia | value |
| `Republic of Timor-Leste_2016-06-24.pdf` | Timor-Leste | last_actual_year, value |
| `Rwanda_2016-01-28.pdf` | Rwanda | value |
| `Rwanda_2017-07-13.pdf` | Rwanda | last_actual_year, value |
| `Saudi Arabia_2017-10-05.pdf` | Saudi Arabia | value |
| `Senegal_2016-01-06.pdf` | Senegal | value |
| `Senegal_2017-01-04.pdf` | Senegal | last_actual_year, value |
| `Senegal_2018-01-12.pdf` | Senegal | last_actual_year, value |
| `Singapore_2018-07-27.pdf` | Singapore | last_actual_year, value |
| `Solomon Islands_2016-03-23.pdf` | Solomon Islands | last_actual_year, value |
| `Solomon Islands_2018-03-05.pdf` | Solomon Islands | last_actual_year, value |
| `Sri Lanka_2019-05-16.pdf` | Sri Lanka | value |
| `St. Vincent and the Grenadines_2020-05-29.pdf` | St. Vincent and the Grenadines | value |
| `Sweden_2019-03-26.pdf` | Sweden | value |
| `Thailand_2018-06-04.pdf` | Thailand | value |
| `The Federal Democratic Republic of Ethiopia_2016-10-04.pdf` | Ethiopia | last_actual_year, value |
| `The Gambia_2017-07-03.pdf` | Gambia | last_actual_year, value |
| `Togo_2017-12-15.pdf` | Togo | last_actual_year, value |
| `Ukraine_2020-06-11.pdf` | Ukraine | value |
| `United Kingdom_2016-02-24.pdf` | United Kingdom | last_actual_year, value |
| `United Republic of Tanzania_2016-02-01.pdf` | Tanzania | table_found |
| `Vanuatu_2016-10-31.pdf` | Vanuatu | last_actual_year, value |
| `Zambia_2019-08-02.pdf` | Zambia | value |

*(Machine-readable version: `three_way_sl_weiqi_sa_disagreement_list_20260917_v2.csv`. Reports are identified by the literal source PDF filename (`pdf_file_name`, verbatim, preferring SL's spelling, then SA's, then Weiqi's) rather than the model-extracted `publication_date` field, which can be an imprecise or inconsistently-worded paraphrase — use the PDF filename to locate the source file directly for manual review.)*

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

| PDF file name | Country | Fully-matching pair | Outlier | Note |
|---|---|---|---|---|
| `Argentina_2019-07-15.pdf` | Argentina | SL=SA | Weiqi |  |
| `Belize_2016-03-28.pdf` | Belize | SL=Weiqi | SA |  |
| `Benin_2017-04-26.pdf` | Benin | SL=Weiqi | SA |  |
| `Bolivia_2020-05-29.pdf` | Bolivia | Weiqi=SA | SL | SL found no table; Weiqi & SA agree on year 2019 and all 15 values |
| `Bulgaria_2018-02-21.pdf` | Bulgaria | Weiqi=SA | SL |  |
| `Burkina Faso_2016-12-22.pdf` | Burkina Faso | SL=SA | Weiqi |  |
| `Burkina Faso_2018-03-15.pdf` | Burkina Faso | SL=SA | Weiqi |  |
| `Burkina Faso_2019-12-30.pdf` | Burkina Faso | Weiqi=SA | SL |  |
| `Chad_2016-08-17.pdf` | Chad | Weiqi=SA | SL |  |
| `Cote d'Ivoire_2017-12-15.pdf` | Côte d'Ivoire | SL=SA | Weiqi |  |
| `Cote d'Ivoire_2018-06-25.pdf` | Côte d'Ivoire | SL=Weiqi | SA | SA found no table; SL & Weiqi agree on year 2016 and all 17 values |
| `Cyprus_2016-01-29.pdf` | Cyprus | SL=Weiqi | SA |  |
| `Democratic Republic of São Tomé and Príncipe_2017-12-18.pdf` | São Tomé and Príncipe | SL=Weiqi | SA |  |
| `Djibouti_2017-04-06.pdf` | Djibouti | SL=Weiqi | SA |  |
| `Dominica_2016-07-20.pdf` | Dominica | SL=SA | Weiqi |  |
| `Dominica_2017-12-20.pdf` | Dominica | SL=Weiqi | SA |  |
| `Ecuador_2019-03-20.pdf` | Ecuador | Weiqi=SA | SL |  |
| `Ecuador_2020-05-28.pdf` | Ecuador | SL=SA | Weiqi |  |
| `Ghana_2020-04-16.pdf` | Ghana | Weiqi=SA | SL |  |
| `Grenada_2016-12-21.pdf` | Grenada | SL=SA | Weiqi |  |
| `Guatemala_2016-09-01.pdf` | Guatemala | Weiqi=SA | SL |  |
| `Guatemala_2018-06-08.pdf` | Guatemala | SL=SA | Weiqi |  |
| `Guinea-Bissau_2016-12-28.pdf` | Guinea-Bissau | SL=Weiqi | SA |  |
| `Guinea-Bissau_2017-12-18.pdf` | Guinea-Bissau | SL=SA | Weiqi |  |
| `Guinea_2017-12-19.pdf` | Guinea | Weiqi=SA | SL |  |
| `Guyana_2018-07-16.pdf` | Guyana | Weiqi=SA | SL |  |
| `Honduras_2018-07-03.pdf` | Honduras | SL=Weiqi | SA |  |
| `Indonesia_2016-03-15.pdf` | Indonesia | SL=SA | Weiqi |  |
| `Indonesia_2018-02-06.pdf` | Indonesia | SL=SA | Weiqi |  |
| `Islamic Republic of Mauritania_2016-05-11.pdf` | Mauritania | Weiqi=SA | SL |  |
| `Islamic Republic of Mauritania_2017-10-16.pdf` | Mauritania | Weiqi=SA | SL |  |
| `Islamic Republic of Mauritania_2017-12-13.pdf` | Mauritania | SL=Weiqi | SA |  |
| `Israel_2017-03-28.pdf` | Israel | SL=SA | Weiqi |  |
| `Italy_2017-07-27.pdf` | Italy | SL=SA | Weiqi | Weiqi found no table; SL & SA agree on year 2016 and all 15 values |
| `Kingdom of Lesotho_2018-02-28.pdf` | Lesotho | SL=SA | Weiqi |  |
| `Kyrgyz Republic_2018-02-22.pdf` | Kyrgyz Republic | SL=Weiqi | SA |  |
| `Lao People's Democratic Republic_2017-02-15.pdf` | Lao PDR | SL=SA | Weiqi |  |
| `Lao People’s Democratic Republic_2018-03-23.pdf` | Lao PDR | Weiqi=SA | SL |  |
| `Liberia_2016-01-08.pdf` | Liberia | SL=SA | Weiqi |  |
| `Liberia_2017-11-20.pdf` | Liberia | SL=SA | Weiqi |  |
| `Liberia_2018-06-15.pdf` | Liberia | Weiqi=SA | SL |  |
| `Luxembourg_2017-05-10.pdf` | Luxembourg | SL=SA | Weiqi |  |
| `Malaysia_2016-05-04.pdf` | Malaysia | SL=SA | Weiqi |  |
| `Malaysia_2019-03-08.pdf` | Malaysia | Weiqi=SA | SL |  |
| `Maldives_2017-12-01.pdf` | Maldives | Weiqi=SA | SL |  |
| `Maldives_2019-09-03_CR2019-281.pdf` | Maldives | SL=SA | Weiqi |  |
| `Mexico_2018-11-27.pdf` | Mexico | SL=Weiqi | SA |  |
| `Mexico_2020-11-20.pdf` | Mexico | SL=SA | Weiqi |  |
| `Myanmar_2017-02-02.pdf` | Myanmar | SL=Weiqi | SA |  |
| `Myanmar_2020-07-02.pdf` | Myanmar | SL=SA | Weiqi |  |
| `Nepal_2020-04-06.pdf` | Nepal | Weiqi=SA | SL |  |
| `New Zealand_2017-05-08.pdf` | New Zealand | Weiqi=SA | SL |  |
| `Norway_2018-09-17.pdf` | Norway | SL=Weiqi | SA |  |
| `Papua New Guinea_2017-01-30.pdf` | Papua New Guinea | Weiqi=SA | SL |  |
| `Papua New Guinea_2017-12-29.pdf` | Papua New Guinea | Weiqi=SA | SL |  |
| `Peru_2020-05-29.pdf` | Peru | SL=SA | Weiqi |  |
| `Philippines_2016-09-26.pdf` | Philippines | SL=SA | Weiqi |  |
| `Philippines_2017-11-10.pdf` | Philippines | SL=Weiqi | SA |  |
| `Philippines_2018-09-27.pdf` | Philippines | Weiqi=SA | SL |  |
| `Republic of Armenia_2016-07-21.pdf` | Armenia | Weiqi=SA | SL |  |
| `Republic of Armenia_2016-12-13.pdf` | Armenia | Weiqi=SA | SL |  |
| `Republic of Armenia_2017-07-19.pdf` | Armenia | Weiqi=SA | SL |  |
| `Republic of Croatia_2019-02-12.pdf` | Croatia | SL=Weiqi | SA |  |
| `Republic of Equatorial Guinea_2016-11-16.pdf` | Equatorial Guinea | SL=SA | Weiqi |  |
| `Republic of Equatorial Guinea_2019-12-20.pdf` | Equatorial Guinea | SL=SA | Weiqi |  |
| `Republic of Kosovo_2017-03-17.pdf` | Kosovo | SL=SA | Weiqi |  |
| `Republic of Lithuania_2017-06-30.pdf` | Lithuania | SL=Weiqi | SA |  |
| `Republic of Madagascar_2018-07-25.pdf` | Madagascar | Weiqi=SA | SL |  |
| `Republic of Madagascar_2020-08-27.pdf` | Madagascar | SL=Weiqi | SA |  |
| `Republic of Moldova_2016-11-09.pdf` | Moldova | SL=Weiqi | SA |  |
| `Republic of Nauru_2020-01-29.pdf` | Nauru | SL=SA | Weiqi |  |
| `Republic of Poland_2017-01-18.pdf` | Poland | Weiqi=SA | SL |  |
| `Republic of San Marino_2017-04-06.pdf` | San Marino | SL=SA | Weiqi |  |
| `Republic of San Marino_2020-04-02.pdf` | San Marino | Weiqi=SA | SL |  |
| `Republic of Slovenia_2019-02-18.pdf` | Slovenia | SL=SA | Weiqi |  |
| `Republic of Timor-Leste_2016-06-24.pdf` | Timor-Leste | SL=SA | Weiqi |  |
| `Rwanda_2016-01-28.pdf` | Rwanda | SL=SA | Weiqi |  |
| `Rwanda_2017-07-13.pdf` | Rwanda | SL=SA | Weiqi |  |
| `Saudi Arabia_2017-10-05.pdf` | Saudi Arabia | Weiqi=SA | SL |  |
| `Senegal_2016-01-06.pdf` | Senegal | Weiqi=SA | SL |  |
| `Senegal_2017-01-04.pdf` | Senegal | SL=SA | Weiqi |  |
| `Senegal_2018-01-12.pdf` | Senegal | Weiqi=SA | SL |  |
| `Singapore_2018-07-27.pdf` | Singapore | SL=SA | Weiqi |  |
| `Solomon Islands_2016-03-23.pdf` | Solomon Islands | SL=Weiqi | SA |  |
| `Solomon Islands_2018-03-05.pdf` | Solomon Islands | SL=SA | Weiqi |  |
| `Sri Lanka_2019-05-16.pdf` | Sri Lanka | SL=SA | Weiqi |  |
| `St. Vincent and the Grenadines_2020-05-29.pdf` | St. Vincent and the Grenadines | Weiqi=SA | SL |  |
| `Sweden_2019-03-26.pdf` | Sweden | SL=SA | Weiqi |  |
| `Thailand_2018-06-04.pdf` | Thailand | SL=SA | Weiqi |  |
| `The Federal Democratic Republic of Ethiopia_2016-10-04.pdf` | Ethiopia | SL=SA | Weiqi |  |
| `The Gambia_2017-07-03.pdf` | Gambia | Weiqi=SA | SL |  |
| `Togo_2017-12-15.pdf` | Togo | SL=SA | Weiqi |  |
| `United Kingdom_2016-02-24.pdf` | United Kingdom | SL=SA | Weiqi |  |
| `United Republic of Tanzania_2016-02-01.pdf` | Tanzania | SL=Weiqi | SA | SL & Weiqi both concluded no DSA table exists; SA found one (no values to compare) |
| `Vanuatu_2016-10-31.pdf` | Vanuatu | SL=Weiqi | SA |  |
| `Zambia_2019-08-02.pdf` | Zambia | SL=SA | Weiqi |  |

*(Machine-readable version: `three_way_sl_weiqi_sa_two_of_three_match_20260917_v2.csv`. Reports are identified by the literal source PDF filename, same convention as Section 6. The 22 reports with no two-way agreement — a genuine 3-way scatter, or a missing year selection on more than one side — are: `Bangladesh_2016-02-01.pdf`, `Benin_2016-01-07.pdf`, `Cabo Verde_2016-11-29.pdf`, `Cambodia_2019-12-23.pdf`, `Central African Republic_2020-04-28.pdf`, `Chad_2019-07-31.pdf`, `Chad_2020-08-05.pdf`, `Democratic Republic of São Tomé and Príncipe_2020-08-04.pdf`, `Democratic Republic of Timor-Leste_2019-05-07.pdf`, `Greece_2017-07-20.pdf`, `Guyana_2016-07-07.pdf`, `Islamic Republic of Afghanistan_2020-11-13.pdf`, `Kiribati_2019-01-24.pdf`, `Liberia_2019-06-19.pdf`, `Malaysia_2017-04-28.pdf`, `Maldives_2020-04-23.pdf`, `Mali_2016-12-07.pdf` (a `table_found` split where Weiqi found a table with no values and no year, so it cannot pairwise-match SA's year either), `Mali_2020-05-08.pdf`, `Republic of Belarus_2019-01-17.pdf`, `Republic of Congo_2020-01-27.pdf`, `Republic of Moldova_2019-09-25.pdf`, and `Ukraine_2020-06-11.pdf`.)*

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

*Data sources: `dsa_decomposition_sl_20260901.csv` (SL), `dsa_decomposition_labels_BH_run5_flexible_actual_thinking_weiqi.csv` (Weiqi), and `dsa_decomposition_labels_2016-2020_sa.csv` + `dsa_decomposition_labels_2016-2020_errors_sa.csv` (SA), all in `output/2016-2020/compiled_csv/`. Detail files generated for this comparison: `three_way_sl_weiqi_sa_report_level_20260917_v2.csv`, `three_way_sl_weiqi_sa_value_diffs_20260917_v2.csv`, `three_way_sl_weiqi_sa_disagreement_list_20260917_v2.csv`, `three_way_sl_weiqi_sa_two_of_three_match_20260917_v2.csv`. All detail CSVs identify reports by the literal source PDF filename (`pdf_file_name`). Builds on the earlier `comparison_summary.md` (SL vs. Weiqi only).*
