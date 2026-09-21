# SFA DSA Decomposition — Three-Version Comparison, 2011–2015 (SL vs. Weiqi vs. SA)

**Scope:** IMF Staff Report DSA (Debt Sustainability Analysis) decomposition tables, all countries, 2011–2015.
**Method:** Each of the three team members ran the extraction pipeline independently on the same PDF sample and compiled their own results CSV. This document repeats the three-way comparison done for 2016–2020 (`three_way_comparison_sl_weiqi_sa_2016-2020_20260917.md`) on the 2011–2015 batch, and adds one dimension the earlier comparison did not analyse: **SA saved his results in two files, a main file and an "errors" file**, so every table below shows which of the two each report came from (Section 7 is devoted to this).
**Date generated:** 2026-09-21

| Version | File(s) | Rows | Reports |
|---|---|---:|---:|
| **SL** | `dsa_decomposition_sl_20260914.csv` | 7,430 | 699 |
| **Weiqi** | `dsa_decomposition_labels_2011_2015_Weiqi.csv` | 7,731 | 702 |
| **SA** | `dsa_decomposition_labels_2011-2015_sa.csv` (main) + `dsa_decomposition_labels_2011-2015_errors_sa.csv` (errors) | 7,654 + 812 = 8,466 | 651 + 51 = 702 |

The two SA files contain no report in common and share the same 43-column schema. Both are combined into one 702-report SA dataset; each report keeps a flag for the file it came from (`SA group` = `main` or `errors`). All comparisons use the literal PDF file name as the report key, and dates, booleans and numbers are normalised before matching (fiscal-year labels such as `2012/13` are read as their end year, the same rule as in the gap-year work).

Supporting detail files in this folder (all keyed by `pdf_file_name`, with the `sa_group` column):
- `three_way_sl_weiqi_sa_2011-2015_report_level_20260921_v1.csv` — one row per report (699 rows), all three versions side by side.
- `three_way_sl_weiqi_sa_2011-2015_value_diffs_20260921_v1.csv` — all 625 line-item value mismatches.
- `three_way_sl_weiqi_sa_2011-2015_disagreement_list_20260921_v1.csv` — the 160 reports with any disagreement, tagged by type.
- `three_way_sl_weiqi_sa_2011-2015_two_of_three_match_20260921_v1.csv` — the 138 of those where exactly two versions fully agree, with the outlier.

---

## 1. Overview

Compared with 2016–2020, agreement is clearly lower on this batch, mostly because the three runs disagree far more often on **whether a DSA table exists at all** (Section 3). Two structural facts drive the picture: SA's pipeline recovers many tables that SL and Weiqi report as unreadable, and the reports SA saved in the errors file are harder for every version, not only for SA (Section 7).

| Metric | Value |
|---|---|
| Reports in SL / Weiqi / SA | 699 / 702 / 702 |
| Reports common to all three | 699 (SA main: 649, SA errors: 50) |
| Reports missing only from SL | 3 |
| `table_found` agrees on all three | 623 / 699 (89.1%) |
| Reports where all three found a table | 454 |
| `last_actual_year` agrees on all three (of those 454) | 404 / 454 (89.0%) |
| 3-way exact match on comparable numeric values | 91.0% (6,318 / 6,943) |
| **Reports that fully match across all three versions** | **539 / 699 (77.1%)** |
| **Reports with at least one disagreement (table_found, year, or value)** | **160 / 699 (22.9%)** |

---

## 2. Sample Coverage

Weiqi and SA cover the identical 702 reports. SL is missing 3 of them, so all "common to all three" figures use 699 reports.

| PDF file name | SA group | Weiqi | SA |
|---|---|---|---|
| `Islamic Republic of Afghanistan_2015-12-01.pdf` | main | Table found | Table found |
| `Kingdom of the Netherlands—Curaçao and Sint Maarten_2014-08-27.pdf` | errors | Table found | Table found |
| `United Kingdom_2012-07-19.pdf` | main | Table found | Table found |

SA's 702 reports split into 651 in the main file and 51 in the errors file; 50 of the 51 errors-file reports are among the 699 common reports.

---

## 3. Table Detection & Framework Classification

Across the 699 common reports, all three versions agree on `table_found` for 623 (89.1%). 454 reports were found by all three, 169 were judged to have no table by all three, and **76 reports are split**.

Number of common reports where each version found a table: SL 462, Weiqi 479, **SA 529**.

| Who found the table (SL / Weiqi / SA) | Reports |
|---|---:|
| Only SA found it | 43 |
| SL missed it, Weiqi and SA found it | 24 |
| Weiqi missed it, SL and SA found it | 8 |
| Only Weiqi found it | 1 |

**SA's rotated-page retry explains the largest group.** All 43 reports that only SA found were extracted through SA's `pymupdf_pillow_multi_orientation_retry` method, a fallback that does not exist in the SL and Weiqi runs; SL and Weiqi return `pages_unreadable` (or no DSA found) for these. SA used this method for 62 of its 529 found tables in the common set. These SA-only tables have no second reader, so they are the highest-value candidates for a manual PDF spot check before they are trusted. The other splits are mostly SL failures: SL misses 24 tables that Weiqi and SA both find (mainly `dsa_pages_not_in_input`), and Weiqi misses 8 that SL and SA find (all `pages_unreadable`).

Among the 454 reports found by all three, framework classification (MAC_DSA / LIC_DSF / UNKNOWN) agrees for 449 (98.9%).

**The 76 reports where `table_found` differs:**

| PDF file name | SA group | SL | Weiqi | SA | SA extraction method |
|---|---|---|---|---|---|
| `Bangladesh_2015-11-10.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Belgium_2011-04-06.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Botswana_2012-08-10.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Cambodia_2015-11-16.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Colombia_2011-07-05.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Colombia_2011-08-02.pdf` | main | Table found | No table | Table found | multi_orientation_retry |
| `Colombia_2012-09-20.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Czech Republic_2011-04-07.pdf` | main | Table found | No table | Table found | multi_orientation_retry |
| `Czech Republic_2012-05-18.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Dominica_2012-02-27.pdf` | main | Table found | No table | Table found | multi_orientation_retry |
| `El Salvador_2011-04-19.pdf` | main | Table found | No table | Table found | multi_orientation_retry |
| `El Salvador_2011-10-12.pdf` | main | Table found | No table | Table found | multi_orientation_retry |
| `Finland_2012-08-31.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Georgia_2011-01-28.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Georgia_2011-04-21.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Georgia_2011-06-27.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Georgia_2013-04-03.pdf` | main | No table | Table found | Table found | multi_orientation_retry |
| `Guatemala_2012-06-11.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Hungary_2012-01-25.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Islamic Republic of Afghanistan_2012-08-20.pdf` | errors | No table | No table | Table found | multi_orientation_retry |
| `Jamaica_2011-02-11.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Kingdom of Swaziland_2011-01-24.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Kingdom of the Netherlands_2013-08-09.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Mauritius_2011-05-04.pdf` | main | Table found | No table | Table found | multi_orientation_retry |
| `Mexico_2011-12-22.pdf` | errors | No table | No table | Table found | multi_orientation_retry |
| `Mexico_2012-12-07.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Morocco_2011-12-02.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Pakistan_2012-02-07.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Portugal_2012-04-05.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Portugal_2012-07-17.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Portugal_2012-10-25.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Portugal_2013-01-18.pdf` | main | No table | Table found | Table found | multi_orientation_retry |
| `Republic of Fiji_2011-04-08.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Republic of Moldova_2012-10-22.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Republic of Poland_2011-01-21.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Republic of Poland_2011-07-08.pdf` | main | No table | Table found | Table found | multi_orientation_retry |
| `Republic of Poland_2012-01-25.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Republic of Poland_2012-07-05.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Republic of Poland_2013-01-24.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Republic of Slovenia_2011-05-31.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Romania_2011-01-20.pdf` | errors | No table | Table found | No table | table_crop_fallback |
| `Romania_2011-06-29.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Romania_2012-04-02.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Romania_2012-07-02.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Russian Federation_2011-09-27.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Russian Federation_2012-08-03.pdf` | main | Table found | No table | Table found | multi_orientation_retry |
| `Rwanda_2012-06-20.pdf` | errors | No table | No table | Table found | multi_orientation_retry |
| `Sri Lanka_2012-07-25.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `St. Kitts and Nevis_2011-09-02.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `St. Kitts and Nevis_2012-03-07.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `St. Kitts and Nevis_2012-10-15.pdf` | main | No table | Table found | Table found | multi_orientation_retry |
| `The Bahamas_2011-12-02.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Trinidad and Tobago_2011-03-30.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Trinidad and Tobago_2012-06-01.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Uganda_2015-11-20.pdf` | main | No table | Table found | Table found | multi_orientation_retry |
| `Ukraine_2011-02-17.pdf` | main | No table | No table | Table found | multi_orientation_retry |
| `Ukraine_2012-11-27.pdf` | main | Table found | No table | Table found | multi_orientation_retry |
| `United Kingdom_2014-07-28.pdf` | main | No table | Table found | Table found | direct |
| `United Republic of Tanzania_2011-05-11.pdf` | main | No table | Table found | Table found | direct |
| `United Republic of Tanzania_2012-07-18.pdf` | errors | No table | Table found | Table found | direct |
| `United Republic of Tanzania_2014-05-15.pdf` | errors | No table | Table found | Table found | direct |
| `United States_2012-08-02.pdf` | main | No table | Table found | Table found | direct |
| `United States_2014-07-23.pdf` | main | No table | Table found | Table found | direct |
| `United States_2015-07-07.pdf` | main | No table | Table found | Table found | direct |
| `Uruguay_2011-03-03.pdf` | main | No table | Table found | Table found | direct |
| `Uruguay_2014-01-10.pdf` | main | No table | Table found | Table found | direct |
| `Uruguay_2015-03-26.pdf` | main | No table | Table found | Table found | direct |
| `Vanuatu_2011-05-31.pdf` | main | No table | Table found | Table found | direct |
| `Vanuatu_2015-06-16.pdf` | errors | No table | Table found | Table found | direct |
| `Vietnam_2012-07-06.pdf` | main | No table | Table found | Table found | direct |
| `Vietnam_2014-10-16.pdf` | main | No table | Table found | Table found | direct |
| `Zambia_2012-07-26.pdf` | errors | No table | Table found | Table found | direct |
| `Zambia_2015-06-16.pdf` | errors | No table | Table found | Table found | direct |
| `Zimbabwe_2011-06-14.pdf` | main | No table | Table found | Table found | direct |
| `Zimbabwe_2012-09-28.pdf` | main | No table | Table found | Table found | direct |
| `Zimbabwe_2014-07-11.pdf` | main | No table | Table found | Table found | direct |

---

## 4. "Last Actual Year" Disagreements

Among the 454 reports found by all three, all versions select the same last-actual year in 404 cases (89.0%). The remaining **50 reports** show at least one version disagreeing ("—" = no year selected):

| PDF file name | SA group | SL year | Weiqi year | SA year |
|---|---|---|---|---|
| `Australia_2014-02-12.pdf` | main | 2013 | 2012 | 2012 |
| `Barbados_2012-01-19.pdf` | main | 2010 | 2010 | 2009 |
| `Benin_2011-09-22.pdf` | main | 2010 | 2009 | 2010 |
| `Bhutan_2011-06-02.pdf` | main | 2008 | 2009 | 2009 |
| `Bosnia and Herzegovina_2012-10-05.pdf` | main | — | — | 2011 |
| `Bulgaria_2011-07-15.pdf` | main | — | — | 2010 |
| `Burkina Faso_2012-07-02_CR2012-158.pdf` | main | 2010 | 2009 | 2010 |
| `Cambodia_2014-02-04.pdf` | main | — | — | 2012 |
| `Cameroon_2012-08-13.pdf` | main | 2010 | 2010 | 2011 |
| `Cameroon_2014-07-17.pdf` | main | 2012 | 2012 | 2013 |
| `Colombia_2013-07-10.pdf` | main | — | — | 2011 |
| `Costa Rica_2011-07-05.pdf` | main | 2010 | 2010 | 2009 |
| `Cyprus_2014-04-01.pdf` | main | 2012 | 2013 | 2012 |
| `Democratic Republic of São Tomé and Príncipe_2012-02-08.pdf` | main | 2010 | 2009 | 2010 |
| `Democratic Republic of São Tomé and Príncipe_2014-01-06.pdf` | errors | 2012 | 2011 | 2011 |
| `Democratic Republic of the Congo_2013-04-03.pdf` | main | 2010 | 2010 | 2011 |
| `Dominica_2011-11-14.pdf` | errors | 2009 | 2010 | 2009 |
| `El Salvador_2013-05-22.pdf` | errors | 2012 | 2012 | 2011 |
| `Former Yugoslav Republic of Macedonia_2012-06-08.pdf` | main | — | — | 2011 |
| `Ghana_2015-09-04.pdf` | errors | 2014 | 2013 | 2013 |
| `Guinea-Bissau_2011-12-14.pdf` | main | 2009 | 2009 | 2010 |
| `India_2012-04-18.pdf` | main | 2011 | 2011 | 2012 |
| `Israel_2012-04-02.pdf` | main | — | — | 2011 |
| `Kenya_2013-04-30.pdf` | main | 2011 | 2011 | 2012 |
| `Lao People’s Democratic Republic_2015-02-26.pdf` | errors | 2013 | 2013 | 2012 |
| `Maldives_2011-09-26.pdf` | main | 2008 | 2008 | 2009 |
| `Malta_2012-05-07.pdf` | main | 2011 | 2010 | 2011 |
| `Myanmar_2012-05-07.pdf` | main | 2009 | 2010 | 2010 |
| `Myanmar_2014-10-06.pdf` | main | 2013 | 2013 | 2014 |
| `Namibia_2015-10-01.pdf` | main | 2013 | 2014 | 2013 |
| `Nepal_2014-07-18.pdf` | main | 2013 | 2012 | 2013 |
| `Nicaragua_2011-11-14.pdf` | errors | 2010 | 2010 | 2009 |
| `Nicaragua_2013-12-27.pdf` | main | 2011 | 2012 | 2012 |
| `Niger_2015-03-11.pdf` | main | 2012 | 2013 | 2013 |
| `Papua New Guinea_2012-06-01.pdf` | errors | 2011 | 2010 | 2010 |
| `Republic of Congo_2011-08-17.pdf` | main | 2009 | 2009 | 2010 |
| `Republic of Congo_2014-09-04.pdf` | errors | 2013 | 2012 | 2012 |
| `Republic of Kosovo_2011-08-01.pdf` | main | 2009 | 2009 | 2010 |
| `Republic of Kosovo_2012-05-09.pdf` | errors | 2011 | 2010 | 2010 |
| `Republic of Lithuania_2013-03-28.pdf` | main | 2011 | 2012 | 2011 |
| `Republic of Mozambique_2012-06-15.pdf` | main | 2010 | 2010 | 2011 |
| `Republic of the Marshall Islands_2014-02-03.pdf` | main | 2012 | 2011 | 2012 |
| `Samoa_2013-06-14.pdf` | main | 2012 | 2011 | 2012 |
| `Sierra Leone_2015-11-24.pdf` | main | 2013 | 2014 | 2014 |
| `Solomon Islands_2011-12-19.pdf` | main | 2010 | 2009 | 2010 |
| `St. Vincent and the Grenadines_2014-08-21.pdf` | main | 2010 | 2010 | 2011 |
| `The Federal Democratic Republic of Ethiopia_2012-10-18.pdf` | errors | 2011 | 2011 | 2010 |
| `The Gambia_2012-06-06.pdf` | main | 2011 | 2010 | 2011 |
| `Tuvalu_2012-09-04.pdf` | errors | 2010 | 2011 | 2010 |
| `Uganda_2014-12-12.pdf` | errors | 2013 | 2014 | 2013 |

12 of these 50 are SA errors-file reports, out of only 40 errors-file reports found by all three, which is a much higher share than in the main file (Section 7).

---

## 5. Value-Level Consistency

Matching line items by `json_file` + `hierarchy_id` across the 454 reports found by all three gives 6,943 line items with a numeric value on all three sides:

| | Count | Share |
|---|---:|---:|
| Exact match on all three | 6,318 | 91.0% |
| Differ on at least one side | 625 | 9.0% |

| Pair | Exact-match rate |
|---|---:|
| SL vs. Weiqi | 94.5% |
| SL vs. SA | 94.0% |
| Weiqi vs. SA | 93.4% |

**78 reports** (17.2% of the 454) have at least one differing value: 44 of them also have a last-actual-year disagreement (explained by different column selection); 34 have the same year on all three, so those are genuine read inconsistencies.

### Magnitude

- Mean spread (max − min of the three values, differing rows only): **4.17** percentage points of GDP; median **1.4**; maximum **108.2** (`Guinea-Bissau_2011-12-14.pdf`).
- 57% of differing rows have a spread above 1 point; only 13% are within 0.15 (rounding level).

### By category (differing rows only)

| Category | n | Mean spread |
|---|---:|---:|
| automatic_debt_dynamics | 227 | 2.50 |
| primary_balance | 179 | 2.53 |
| other_identified_flows | 63 | 8.54 |
| change_in_debt | 56 | 6.88 |
| identified_flows | 56 | 7.80 |
| residual | 44 | 5.12 |

As in 2016–2020, the subtotal rows carry large errors, and in this batch `other_identified_flows` is the worst category.

### Top 20 largest value discrepancies

| PDF file name | SA group | Category | Line item | SL | Weiqi | SA | Max spread |
|---|---|---|---|---|---|---|---|
| `Guinea-Bissau_2011-12-14.pdf` | main | other_identified_flows | Debt relief (HIPC and other) | -1.5 | -1.5 | -109.7 | 108.2 |
| `Guinea-Bissau_2011-12-14.pdf` | main | other_identified_flows | Other identified debt-creating flows | -1.5 | -1.5 | -109.7 | 108.2 |
| `Guinea-Bissau_2011-12-14.pdf` | main | change_in_debt | Change in public sector debt | -9.6 | -9.6 | -108.8 | 99.2 |
| `Democratic Republic of the Congo_2013-04-03.pdf` | main | change_in_debt | Change in public sector debt | -103.7 | -103.7 | -7.0 | 96.7 |
| `Guinea-Bissau_2011-12-14.pdf` | main | identified_flows | Identified debt-creating flows | -19.1 | -19.1 | -103.4 | 84.3 |
| `Democratic Republic of the Congo_2013-04-03.pdf` | main | identified_flows | Identified debt-creating flows | -75.4 | -75.4 | -6.6 | 68.8 |
| `Colombia_2014-05-28.pdf` | main | primary_balance | Primary (noninterest) revenue and grants | 27.7 | -27.7 | 27.7 | 55.4 |
| `Republic of Congo_2011-08-17.pdf` | main | identified_flows | Identified debt-creating flows | 0.2 | 0.2 | -48.7 | 48.9 |
| `Tuvalu_2012-09-04.pdf` | errors | identified_flows | Identified debt-creating flows | 59.6 | 10.8 | 59.6 | 48.8 |
| `Tuvalu_2012-09-04.pdf` | errors | residual | Residual, including asset changes 2/ | -63.4 | -22.5 | -63.4 | 40.9 |
| `Democratic Republic of the Congo_2013-04-03.pdf` | main | other_identified_flows | Debt relief (HIPC and other) | -41.8 | -41.8 | -2.3 | 39.5 |
| `Democratic Republic of the Congo_2013-04-03.pdf` | main | other_identified_flows | Other identified debt-creating flows | -41.8 | -41.8 | -2.8 | 39.0 |
| `Democratic Republic of São Tomé and Príncipe_2012-02-08.pdf` | main | other_identified_flows | Other identified debt-creating flows | -0.3 | -33.2 | -0.3 | 32.9 |
| `Tuvalu_2012-09-04.pdf` | errors | primary_balance | Primary deficit | 28.6 | -2.9 | 28.6 | 31.5 |
| `Republic of Congo_2011-08-17.pdf` | main | residual | Residual, including asset changes | -11.4 | -11.4 | 16.7 | 28.1 |
| `Democratic Republic of the Congo_2013-04-03.pdf` | main | residual | Residual, including asset changes | -28.3 | -28.3 | -0.5 | 27.8 |
| `Democratic Republic of São Tomé and Príncipe_2012-02-08.pdf` | main | other_identified_flows | Debt relief (HIPC and other) | 0.0 | -27.0 | 0.0 | 27.0 |
| `Democratic Republic of the Congo_2013-04-03.pdf` | main | automatic_debt_dynamics | Automatic debt dynamics | -32.7 | -32.7 | -7.1 | 25.6 |
| `Democratic Republic of São Tomé and Príncipe_2012-02-08.pdf` | main | residual | Residual, including asset changes 5/ | 3.9 | 27.9 | 3.9 | 24.0 |
| `Democratic Republic of São Tomé and Príncipe_2012-02-08.pdf` | main | identified_flows | Identified debt-creating flows | 8.5 | -15.0 | 8.5 | 23.5 |

---

## 6. Full-Match Summary — Clean Reports vs. Reports Needing Review

A report **fully matches** across the three versions if `table_found` agrees on all three and, when a table was found, `last_actual_year` agrees and every comparable line-item value agrees exactly. `confidence` and `manual_review_required` are excluded (self-reported metadata; see Section 8).

| | Reports | Share of 699 |
|---|---:|---:|
| **Fully match across all three versions** | **539** | **77.1%** |
| — all three agree no table exists | 169 | 24.2% |
| — all three found the table, identical year and values | 370 | 52.9% |
| **At least one disagreement** | **160** | **22.9%** |

Of the 160: 76 are `table_found` splits, 50 involve a last-actual-year disagreement, and 34 are pure value inconsistencies with the same year on all three.

### The 160 reports with at least one disagreement

| PDF file name | Country | SA group | Disagreement type(s) |
|---|---|---|---|
| `Albania_2014-03-19.pdf` | Albania | main | value |
| `Algeria_2014-02-04.pdf` | Algeria | main | value |
| `Angola_2014-09-05.pdf` | Angola | main | value |
| `Australia_2014-02-12.pdf` | Australia | main | last_actual_year, value |
| `Bangladesh_2015-11-10.pdf` | Bangladesh | main | table_found |
| `Barbados_2012-01-19.pdf` | Barbados | main | last_actual_year, value |
| `Belgium_2011-04-06.pdf` | Belgium | main | table_found |
| `Benin_2011-09-22.pdf` | Benin | main | last_actual_year, value |
| `Bhutan_2011-06-02.pdf` | Bhutan | main | last_actual_year, value |
| `Bosnia and Herzegovina_2012-10-05.pdf` | Bosnia and Herzegovina | main | last_actual_year |
| `Botswana_2012-08-10.pdf` | Botswana | main | table_found |
| `Botswana_2014-07-15.pdf` | Botswana | main | value |
| `Bulgaria_2011-07-15.pdf` | Bulgaria | main | last_actual_year |
| `Bulgaria_2015-05-13.pdf` | Bulgaria | main | value |
| `Burkina Faso_2012-07-02_CR2012-158.pdf` | Burkina Faso | main | last_actual_year, value |
| `Cambodia_2014-02-04.pdf` | Cambodia | main | last_actual_year |
| `Cambodia_2015-11-16.pdf` | Cambodia | main | table_found |
| `Cameroon_2012-08-13.pdf` | Cameroon | main | last_actual_year, value |
| `Cameroon_2014-07-17.pdf` | Cameroon | main | last_actual_year, value |
| `Colombia_2011-07-05.pdf` | Colombia | main | table_found |
| `Colombia_2011-08-02.pdf` | Colombia | main | table_found |
| `Colombia_2012-09-20.pdf` | Colombia | main | table_found |
| `Colombia_2013-07-10.pdf` | Colombia | main | last_actual_year |
| `Colombia_2014-05-28.pdf` | Colombia | main | value |
| `Costa Rica_2011-07-05.pdf` | Costa Rica | main | last_actual_year, value |
| `Cyprus_2014-04-01.pdf` | Cyprus | main | last_actual_year, value |
| `Cyprus_2014-10-22.pdf` | Cyprus | main | value |
| `Czech Republic_2011-04-07.pdf` | Czech Republic | main | table_found |
| `Czech Republic_2012-05-18.pdf` | Czech Republic | main | table_found |
| `Democratic Republic of São Tomé and Príncipe_2012-02-08.pdf` | São Tomé and Príncipe | main | last_actual_year, value |
| `Democratic Republic of São Tomé and Príncipe_2014-01-06.pdf` | São Tomé and Príncipe | errors | last_actual_year, value |
| `Democratic Republic of the Congo_2013-04-03.pdf` | Democratic Republic of the Congo | main | last_actual_year, value |
| `Dominica_2011-11-14.pdf` | Dominica | errors | last_actual_year, value |
| `Dominica_2012-02-27.pdf` | Dominica | main | table_found |
| `El Salvador_2011-04-19.pdf` | El Salvador | main | table_found |
| `El Salvador_2011-10-12.pdf` | El Salvador | main | table_found |
| `El Salvador_2013-05-22.pdf` | El Salvador | errors | last_actual_year, value |
| `Finland_2012-08-31.pdf` | Finland | main | table_found |
| `Finland_2014-05-28.pdf` | Finland | main | value |
| `Former Yugoslav Republic of Macedonia_2012-06-08.pdf` | North Macedonia | main | last_actual_year |
| `Former Yugoslav Republic of Macedonia_2015-09-03.pdf` | North Macedonia | main | value |
| `France_2014-07-03.pdf` | France | main | value |
| `Georgia_2011-01-28.pdf` | Georgia | main | table_found |
| `Georgia_2011-04-21.pdf` | Georgia | main | table_found |
| `Georgia_2011-06-27.pdf` | Georgia | main | table_found |
| `Georgia_2013-04-03.pdf` | Georgia | main | table_found |
| `Georgia_2015-01-20.pdf` | Georgia | main | value |
| `Ghana_2015-09-04.pdf` | Ghana | errors | last_actual_year, value |
| `Guatemala_2012-06-11.pdf` | Guatemala | main | table_found |
| `Guinea-Bissau_2011-12-14.pdf` | Guinea-Bissau | main | last_actual_year, value |
| `Hungary_2012-01-25.pdf` | Hungary | main | table_found |
| `Hungary_2015-04-03.pdf` | Hungary | main | value |
| `India_2012-04-18.pdf` | India | main | last_actual_year, value |
| `Indonesia_2015-03-19.pdf` | Indonesia | main | value |
| `Ireland_2015-03-25.pdf` | Ireland | main | value |
| `Islamic Republic of Afghanistan_2012-08-20.pdf` | Afghanistan | errors | table_found |
| `Israel_2012-04-02.pdf` | Israel | main | last_actual_year |
| `Italy_2014-09-18.pdf` | Italy | main | value |
| `Jamaica_2011-02-11.pdf` | Jamaica | main | table_found |
| `Jamaica_2015-09-24.pdf` | Jamaica | main | value |
| `Kenya_2013-04-30.pdf` | Kenya | main | last_actual_year, value |
| `Kingdom of Swaziland_2011-01-24.pdf` | Eswatini | main | table_found |
| `Kingdom of the Netherlands_2013-08-09.pdf` | Netherlands | main | table_found |
| `Lao People’s Democratic Republic_2015-02-26.pdf` | Lao PDR | errors | last_actual_year, value |
| `Malaysia_2014-03-14.pdf` | Malaysia | main | value |
| `Malaysia_2015-03-03.pdf` | Malaysia | main | value |
| `Maldives_2011-09-26.pdf` | Maldives | main | last_actual_year, value |
| `Malta_2012-05-07.pdf` | Malta | main | last_actual_year, value |
| `Mauritius_2011-05-04.pdf` | Mauritius | main | table_found |
| `Mexico_2011-12-22.pdf` | Mexico | errors | table_found |
| `Mexico_2012-12-07.pdf` | Mexico | main | table_found |
| `Mexico_2014-11-12.pdf` | Mexico | main | value |
| `Mexico_2015-11-17.pdf` | Mexico | main | value |
| `Morocco_2011-12-02.pdf` | Morocco | main | table_found |
| `Myanmar_2012-05-07.pdf` | Myanmar | main | last_actual_year, value |
| `Myanmar_2014-10-06.pdf` | Myanmar | main | last_actual_year, value |
| `Namibia_2015-10-01.pdf` | Namibia | main | last_actual_year, value |
| `Nepal_2014-07-18.pdf` | Nepal | main | last_actual_year, value |
| `Nicaragua_2011-11-14.pdf` | Nicaragua | errors | last_actual_year, value |
| `Nicaragua_2013-12-27.pdf` | Nicaragua | main | last_actual_year, value |
| `Niger_2015-03-11.pdf` | Niger | main | last_actual_year, value |
| `Pakistan_2012-02-07.pdf` | Pakistan | main | table_found |
| `Papua New Guinea_2012-06-01.pdf` | Papua New Guinea | errors | last_actual_year, value |
| `Portugal_2012-04-05.pdf` | Portugal | main | table_found |
| `Portugal_2012-07-17.pdf` | Portugal | main | table_found |
| `Portugal_2012-10-25.pdf` | Portugal | main | table_found |
| `Portugal_2013-01-18.pdf` | Portugal | main | table_found |
| `Republic of Armenia_2015-11-19.pdf` | Armenia | main | value |
| `Republic of Belarus_2015-05-29.pdf` | Belarus | main | value |
| `Republic of Congo_2011-08-17.pdf` | Republic of Congo | main | last_actual_year, value |
| `Republic of Congo_2014-09-04.pdf` | Republic of Congo | errors | last_actual_year, value |
| `Republic of Fiji_2011-04-08.pdf` | Fiji | main | table_found |
| `Republic of Kosovo_2011-08-01.pdf` | Kosovo | main | last_actual_year, value |
| `Republic of Kosovo_2012-05-09.pdf` | Kosovo | errors | last_actual_year, value |
| `Republic of Lithuania_2013-03-28.pdf` | Lithuania | main | last_actual_year, value |
| `Republic of Moldova_2012-10-22.pdf` | Moldova | main | table_found |
| `Republic of Mozambique_2012-06-15.pdf` | Mozambique | main | last_actual_year, value |
| `Republic of Poland_2011-01-21.pdf` | Poland | main | table_found |
| `Republic of Poland_2011-07-08.pdf` | Poland | main | table_found |
| `Republic of Poland_2012-01-25.pdf` | Poland | main | table_found |
| `Republic of Poland_2012-07-05.pdf` | Poland | main | table_found |
| `Republic of Poland_2013-01-24.pdf` | Poland | main | table_found |
| `Republic of San Marino_2015-04-08.pdf` | San Marino | main | value |
| `Republic of Slovenia_2011-05-31.pdf` | Slovenia | main | table_found |
| `Republic of Slovenia_2014-01-17.pdf` | Slovenia | main | value |
| `Republic of the Marshall Islands_2014-02-03.pdf` | Marshall Islands | main | last_actual_year, value |
| `Romania_2011-01-20.pdf` | Romania | errors | table_found |
| `Romania_2011-06-29.pdf` | Romania | main | table_found |
| `Romania_2012-04-02.pdf` | Romania | main | table_found |
| `Romania_2012-07-02.pdf` | Romania | main | table_found |
| `Romania_2012-10-23.pdf` | Romania | errors | value |
| `Romania_2015-03-27.pdf` | Romania | main | value |
| `Russian Federation_2011-09-27.pdf` | Russian Federation | main | table_found |
| `Russian Federation_2012-08-03.pdf` | Russian Federation | main | table_found |
| `Russian Federation_2014-07-01.pdf` | Russian Federation | main | value |
| `Russian Federation_2015-08-03.pdf` | Russian Federation | errors | value |
| `Rwanda_2012-06-20.pdf` | Rwanda | errors | table_found |
| `Samoa_2013-06-14.pdf` | Samoa | main | last_actual_year, value |
| `Senegal_2013-06-24.pdf` | Senegal | main | value |
| `Seychelles_2015-07-22.pdf` | Seychelles | main | value |
| `Sierra Leone_2015-11-24.pdf` | Sierra Leone | main | last_actual_year, value |
| `Slovak Republic_2014-09-02.pdf` | Slovak Republic | main | value |
| `Solomon Islands_2011-12-19.pdf` | Solomon Islands | main | last_actual_year, value |
| `Sri Lanka_2012-07-25.pdf` | Sri Lanka | main | table_found |
| `St. Kitts and Nevis_2011-09-02.pdf` | St. Kitts and Nevis | main | table_found |
| `St. Kitts and Nevis_2012-03-07.pdf` | St. Kitts and Nevis | main | table_found |
| `St. Kitts and Nevis_2012-10-15.pdf` | St. Kitts and Nevis | main | table_found |
| `St. Vincent and the Grenadines_2014-08-21.pdf` | St. Vincent and the Grenadines | main | last_actual_year, value |
| `Sweden_2015-12-02.pdf` | Sweden | main | value |
| `The Bahamas_2011-12-02.pdf` | Bahamas | main | table_found |
| `The Bahamas_2014-03-07.pdf` | Bahamas | main | value |
| `The Federal Democratic Republic of Ethiopia_2012-10-18.pdf` | Ethiopia | errors | last_actual_year, value |
| `The Gambia_2012-06-06.pdf` | Gambia | main | last_actual_year, value |
| `Trinidad and Tobago_2011-03-30.pdf` | Trinidad and Tobago | main | table_found |
| `Trinidad and Tobago_2012-06-01.pdf` | Trinidad and Tobago | main | table_found |
| `Turkey_2014-12-05.pdf` | Turkey | main | value |
| `Tuvalu_2012-09-04.pdf` | Tuvalu | errors | last_actual_year, value |
| `Uganda_2014-12-12.pdf` | Uganda | errors | last_actual_year, value |
| `Uganda_2015-11-20.pdf` | Uganda | main | table_found |
| `Ukraine_2011-02-17.pdf` | Ukraine | main | table_found |
| `Ukraine_2012-11-27.pdf` | Ukraine | main | table_found |
| `United Kingdom_2014-07-28.pdf` | United Kingdom | main | table_found |
| `United Republic of Tanzania_2011-05-11.pdf` | Tanzania | main | table_found |
| `United Republic of Tanzania_2012-07-18.pdf` | Tanzania | errors | table_found |
| `United Republic of Tanzania_2014-05-15.pdf` | Tanzania | errors | table_found |
| `United States_2012-08-02.pdf` | United States | main | table_found |
| `United States_2014-07-23.pdf` | United States | main | table_found |
| `United States_2015-07-07.pdf` | United States | main | table_found |
| `Uruguay_2011-03-03.pdf` | Uruguay | main | table_found |
| `Uruguay_2014-01-10.pdf` | Uruguay | main | table_found |
| `Uruguay_2015-03-26.pdf` | Uruguay | main | table_found |
| `Vanuatu_2011-05-31.pdf` | Vanuatu | main | table_found |
| `Vanuatu_2015-06-16.pdf` | Vanuatu | errors | table_found |
| `Vietnam_2012-07-06.pdf` | Vietnam | main | table_found |
| `Vietnam_2014-10-16.pdf` | Vietnam | main | table_found |
| `Zambia_2012-07-26.pdf` | Zambia | errors | table_found |
| `Zambia_2015-06-16.pdf` | Zambia | errors | table_found |
| `Zimbabwe_2011-06-14.pdf` | Zimbabwe | main | table_found |
| `Zimbabwe_2012-09-28.pdf` | Zimbabwe | main | table_found |
| `Zimbabwe_2014-07-11.pdf` | Zimbabwe | main | table_found |

### 6.1 Which of the 160 are a clean "two-vs-one" pattern?

For each disagreeing report we ask whether any **two** versions agree completely with each other (same `table_found`, same year, and every comparable value identical), leaving the third as the lone outlier. Two readers agreeing is a much stronger signal than a three-way scatter.

| | Reports | Share of 160 |
|---|---:|---:|
| **Exactly two versions fully match (clean outlier pattern)** | **138** | **86.2%** |
| — the two agree that there is no table (the third found one) | 44 | 27.5% |
| — the two agree on the same year and all values, the third found no table | 17 | 10.6% |
| — the two agree on the same year and all values, the third read the table differently | 77 | 48.1% |
| No two versions fully agree (three-way scatter) | 22 | 13.8% |

Who is the lone outlier:

| Outlier | All 138 | Two agree there is no table, outlier found one (44) | Two agree on year and values, outlier found no table (17) | Two agree on year and values, outlier read the table differently (77) |
|---|---:|---:|---:|---:|
| SA | 71 | 43 | 0 | 28 |
| SL | 40 | 0 | 17 | 23 |
| Weiqi | 27 | 1 | 0 | 26 |

The first two columns are about table detection: SA is the outlier in the first almost only because it alone recovered the table (Section 3), and SL is the outlier in the second most often because of its missed tables. The last column is the clean reading question, where both other versions found the table and agree on year and values but one version read it differently: SL 23 times, SA 28 times, Weiqi 26 times.

**All 138 reports where two versions fully match and one is the outlier:**

| PDF file name | Country | SA group | Fully-matching pair | Outlier | What the two agree on |
|---|---|---|---|---|---|
| `Albania_2014-03-19.pdf` | Albania | main | Weiqi=SA | SL | same year and values; outlier read the table differently |
| `Algeria_2014-02-04.pdf` | Algeria | main | Weiqi=SA | SL | same year and values; outlier read the table differently |
| `Angola_2014-09-05.pdf` | Angola | main | Weiqi=SA | SL | same year and values; outlier read the table differently |
| `Australia_2014-02-12.pdf` | Australia | main | Weiqi=SA | SL | same year and values; outlier read the table differently |
| `Bangladesh_2015-11-10.pdf` | Bangladesh | main | SL=Weiqi | SA | both found no table |
| `Barbados_2012-01-19.pdf` | Barbados | main | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `Belgium_2011-04-06.pdf` | Belgium | main | SL=Weiqi | SA | both found no table |
| `Benin_2011-09-22.pdf` | Benin | main | SL=SA | Weiqi | same year and values; outlier read the table differently |
| `Bhutan_2011-06-02.pdf` | Bhutan | main | Weiqi=SA | SL | same year and values; outlier read the table differently |
| `Bosnia and Herzegovina_2012-10-05.pdf` | Bosnia and Herzegovina | main | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `Botswana_2012-08-10.pdf` | Botswana | main | SL=Weiqi | SA | both found no table |
| `Botswana_2014-07-15.pdf` | Botswana | main | SL=SA | Weiqi | same year and values; outlier read the table differently |
| `Bulgaria_2011-07-15.pdf` | Bulgaria | main | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `Bulgaria_2015-05-13.pdf` | Bulgaria | main | SL=SA | Weiqi | same year and values; outlier read the table differently |
| `Burkina Faso_2012-07-02_CR2012-158.pdf` | Burkina Faso | main | SL=SA | Weiqi | same year and values; outlier read the table differently |
| `Cambodia_2014-02-04.pdf` | Cambodia | main | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `Cambodia_2015-11-16.pdf` | Cambodia | main | SL=Weiqi | SA | both found no table |
| `Cameroon_2012-08-13.pdf` | Cameroon | main | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `Cameroon_2014-07-17.pdf` | Cameroon | main | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `Colombia_2011-07-05.pdf` | Colombia | main | SL=Weiqi | SA | both found no table |
| `Colombia_2012-09-20.pdf` | Colombia | main | SL=Weiqi | SA | both found no table |
| `Colombia_2013-07-10.pdf` | Colombia | main | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `Colombia_2014-05-28.pdf` | Colombia | main | SL=SA | Weiqi | same year and values; outlier read the table differently |
| `Costa Rica_2011-07-05.pdf` | Costa Rica | main | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `Cyprus_2014-04-01.pdf` | Cyprus | main | SL=SA | Weiqi | same year and values; outlier read the table differently |
| `Cyprus_2014-10-22.pdf` | Cyprus | main | SL=SA | Weiqi | same year and values; outlier read the table differently |
| `Czech Republic_2012-05-18.pdf` | Czech Republic | main | SL=Weiqi | SA | both found no table |
| `Democratic Republic of São Tomé and Príncipe_2012-02-08.pdf` | São Tomé and Príncipe | main | SL=SA | Weiqi | same year and values; outlier read the table differently |
| `Democratic Republic of São Tomé and Príncipe_2014-01-06.pdf` | São Tomé and Príncipe | errors | Weiqi=SA | SL | same year and values; outlier read the table differently |
| `Democratic Republic of the Congo_2013-04-03.pdf` | Democratic Republic of the Congo | main | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `Dominica_2011-11-14.pdf` | Dominica | errors | SL=SA | Weiqi | same year and values; outlier read the table differently |
| `El Salvador_2013-05-22.pdf` | El Salvador | errors | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `Finland_2012-08-31.pdf` | Finland | main | SL=Weiqi | SA | both found no table |
| `Finland_2014-05-28.pdf` | Finland | main | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `Former Yugoslav Republic of Macedonia_2012-06-08.pdf` | North Macedonia | main | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `France_2014-07-03.pdf` | France | main | SL=SA | Weiqi | same year and values; outlier read the table differently |
| `Georgia_2011-01-28.pdf` | Georgia | main | SL=Weiqi | SA | both found no table |
| `Georgia_2011-04-21.pdf` | Georgia | main | SL=Weiqi | SA | both found no table |
| `Georgia_2011-06-27.pdf` | Georgia | main | SL=Weiqi | SA | both found no table |
| `Georgia_2015-01-20.pdf` | Georgia | main | Weiqi=SA | SL | same year and values; outlier read the table differently |
| `Ghana_2015-09-04.pdf` | Ghana | errors | Weiqi=SA | SL | same year and values; outlier read the table differently |
| `Guatemala_2012-06-11.pdf` | Guatemala | main | SL=Weiqi | SA | both found no table |
| `Guinea-Bissau_2011-12-14.pdf` | Guinea-Bissau | main | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `Hungary_2012-01-25.pdf` | Hungary | main | SL=Weiqi | SA | both found no table |
| `Hungary_2015-04-03.pdf` | Hungary | main | SL=SA | Weiqi | same year and values; outlier read the table differently |
| `India_2012-04-18.pdf` | India | main | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `Indonesia_2015-03-19.pdf` | Indonesia | main | SL=SA | Weiqi | same year and values; outlier read the table differently |
| `Ireland_2015-03-25.pdf` | Ireland | main | Weiqi=SA | SL | same year and values; outlier read the table differently |
| `Islamic Republic of Afghanistan_2012-08-20.pdf` | Afghanistan | errors | SL=Weiqi | SA | both found no table |
| `Israel_2012-04-02.pdf` | Israel | main | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `Jamaica_2011-02-11.pdf` | Jamaica | main | SL=Weiqi | SA | both found no table |
| `Jamaica_2015-09-24.pdf` | Jamaica | main | Weiqi=SA | SL | same year and values; outlier read the table differently |
| `Kenya_2013-04-30.pdf` | Kenya | main | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `Kingdom of Swaziland_2011-01-24.pdf` | Eswatini | main | SL=Weiqi | SA | both found no table |
| `Kingdom of the Netherlands_2013-08-09.pdf` | Netherlands | main | SL=Weiqi | SA | both found no table |
| `Lao People’s Democratic Republic_2015-02-26.pdf` | Lao PDR | errors | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `Malaysia_2014-03-14.pdf` | Malaysia | main | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `Maldives_2011-09-26.pdf` | Maldives | main | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `Malta_2012-05-07.pdf` | Malta | main | SL=SA | Weiqi | same year and values; outlier read the table differently |
| `Mexico_2011-12-22.pdf` | Mexico | errors | SL=Weiqi | SA | both found no table |
| `Mexico_2012-12-07.pdf` | Mexico | main | SL=Weiqi | SA | both found no table |
| `Mexico_2014-11-12.pdf` | Mexico | main | Weiqi=SA | SL | same year and values; outlier read the table differently |
| `Mexico_2015-11-17.pdf` | Mexico | main | Weiqi=SA | SL | same year and values; outlier read the table differently |
| `Morocco_2011-12-02.pdf` | Morocco | main | SL=Weiqi | SA | both found no table |
| `Myanmar_2012-05-07.pdf` | Myanmar | main | Weiqi=SA | SL | same year and values; outlier read the table differently |
| `Myanmar_2014-10-06.pdf` | Myanmar | main | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `Namibia_2015-10-01.pdf` | Namibia | main | SL=SA | Weiqi | same year and values; outlier read the table differently |
| `Nepal_2014-07-18.pdf` | Nepal | main | SL=SA | Weiqi | same year and values; outlier read the table differently |
| `Nicaragua_2011-11-14.pdf` | Nicaragua | errors | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `Nicaragua_2013-12-27.pdf` | Nicaragua | main | Weiqi=SA | SL | same year and values; outlier read the table differently |
| `Niger_2015-03-11.pdf` | Niger | main | Weiqi=SA | SL | same year and values; outlier read the table differently |
| `Pakistan_2012-02-07.pdf` | Pakistan | main | SL=Weiqi | SA | both found no table |
| `Papua New Guinea_2012-06-01.pdf` | Papua New Guinea | errors | Weiqi=SA | SL | same year and values; outlier read the table differently |
| `Portugal_2012-04-05.pdf` | Portugal | main | SL=Weiqi | SA | both found no table |
| `Portugal_2012-07-17.pdf` | Portugal | main | SL=Weiqi | SA | both found no table |
| `Portugal_2012-10-25.pdf` | Portugal | main | SL=Weiqi | SA | both found no table |
| `Republic of Armenia_2015-11-19.pdf` | Armenia | main | Weiqi=SA | SL | same year and values; outlier read the table differently |
| `Republic of Belarus_2015-05-29.pdf` | Belarus | main | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `Republic of Congo_2011-08-17.pdf` | Republic of Congo | main | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `Republic of Congo_2014-09-04.pdf` | Republic of Congo | errors | Weiqi=SA | SL | same year and values; outlier read the table differently |
| `Republic of Fiji_2011-04-08.pdf` | Fiji | main | SL=Weiqi | SA | both found no table |
| `Republic of Kosovo_2011-08-01.pdf` | Kosovo | main | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `Republic of Kosovo_2012-05-09.pdf` | Kosovo | errors | Weiqi=SA | SL | same year and values; outlier read the table differently |
| `Republic of Lithuania_2013-03-28.pdf` | Lithuania | main | SL=SA | Weiqi | same year and values; outlier read the table differently |
| `Republic of Moldova_2012-10-22.pdf` | Moldova | main | SL=Weiqi | SA | both found no table |
| `Republic of Mozambique_2012-06-15.pdf` | Mozambique | main | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `Republic of Poland_2011-01-21.pdf` | Poland | main | SL=Weiqi | SA | both found no table |
| `Republic of Poland_2012-01-25.pdf` | Poland | main | SL=Weiqi | SA | both found no table |
| `Republic of Poland_2012-07-05.pdf` | Poland | main | SL=Weiqi | SA | both found no table |
| `Republic of Poland_2013-01-24.pdf` | Poland | main | SL=Weiqi | SA | both found no table |
| `Republic of San Marino_2015-04-08.pdf` | San Marino | main | SL=SA | Weiqi | same year and values; outlier read the table differently |
| `Republic of Slovenia_2011-05-31.pdf` | Slovenia | main | SL=Weiqi | SA | both found no table |
| `Republic of the Marshall Islands_2014-02-03.pdf` | Marshall Islands | main | SL=SA | Weiqi | same year and values; outlier read the table differently |
| `Romania_2011-01-20.pdf` | Romania | errors | SL=SA | Weiqi | both found no table |
| `Romania_2011-06-29.pdf` | Romania | main | SL=Weiqi | SA | both found no table |
| `Romania_2012-04-02.pdf` | Romania | main | SL=Weiqi | SA | both found no table |
| `Romania_2012-07-02.pdf` | Romania | main | SL=Weiqi | SA | both found no table |
| `Russian Federation_2011-09-27.pdf` | Russian Federation | main | SL=Weiqi | SA | both found no table |
| `Russian Federation_2014-07-01.pdf` | Russian Federation | main | SL=SA | Weiqi | same year and values; outlier read the table differently |
| `Russian Federation_2015-08-03.pdf` | Russian Federation | errors | Weiqi=SA | SL | same year and values; outlier read the table differently |
| `Rwanda_2012-06-20.pdf` | Rwanda | errors | SL=Weiqi | SA | both found no table |
| `Samoa_2013-06-14.pdf` | Samoa | main | SL=SA | Weiqi | same year and values; outlier read the table differently |
| `Seychelles_2015-07-22.pdf` | Seychelles | main | Weiqi=SA | SL | same year and values; outlier read the table differently |
| `Sierra Leone_2015-11-24.pdf` | Sierra Leone | main | Weiqi=SA | SL | same year and values; outlier read the table differently |
| `Slovak Republic_2014-09-02.pdf` | Slovak Republic | main | Weiqi=SA | SL | same year and values; outlier read the table differently |
| `Solomon Islands_2011-12-19.pdf` | Solomon Islands | main | SL=SA | Weiqi | same year and values; outlier read the table differently |
| `Sri Lanka_2012-07-25.pdf` | Sri Lanka | main | SL=Weiqi | SA | both found no table |
| `St. Kitts and Nevis_2011-09-02.pdf` | St. Kitts and Nevis | main | SL=Weiqi | SA | both found no table |
| `St. Kitts and Nevis_2012-03-07.pdf` | St. Kitts and Nevis | main | SL=Weiqi | SA | both found no table |
| `St. Vincent and the Grenadines_2014-08-21.pdf` | St. Vincent and the Grenadines | main | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `Sweden_2015-12-02.pdf` | Sweden | main | SL=SA | Weiqi | same year and values; outlier read the table differently |
| `The Bahamas_2011-12-02.pdf` | Bahamas | main | SL=Weiqi | SA | both found no table |
| `The Bahamas_2014-03-07.pdf` | Bahamas | main | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `The Federal Democratic Republic of Ethiopia_2012-10-18.pdf` | Ethiopia | errors | SL=Weiqi | SA | same year and values; outlier read the table differently |
| `The Gambia_2012-06-06.pdf` | Gambia | main | SL=SA | Weiqi | same year and values; outlier read the table differently |
| `Trinidad and Tobago_2011-03-30.pdf` | Trinidad and Tobago | main | SL=Weiqi | SA | both found no table |
| `Trinidad and Tobago_2012-06-01.pdf` | Trinidad and Tobago | main | SL=Weiqi | SA | both found no table |
| `Turkey_2014-12-05.pdf` | Turkey | main | SL=SA | Weiqi | same year and values; outlier read the table differently |
| `Tuvalu_2012-09-04.pdf` | Tuvalu | errors | SL=SA | Weiqi | same year and values; outlier read the table differently |
| `Uganda_2014-12-12.pdf` | Uganda | errors | SL=SA | Weiqi | same year and values; outlier read the table differently |
| `Ukraine_2011-02-17.pdf` | Ukraine | main | SL=Weiqi | SA | both found no table |
| `United Kingdom_2014-07-28.pdf` | United Kingdom | main | Weiqi=SA | SL | same year and values; outlier found no table |
| `United Republic of Tanzania_2011-05-11.pdf` | Tanzania | main | Weiqi=SA | SL | same year and values; outlier found no table |
| `United Republic of Tanzania_2012-07-18.pdf` | Tanzania | errors | Weiqi=SA | SL | same year and values; outlier found no table |
| `United States_2012-08-02.pdf` | United States | main | Weiqi=SA | SL | same year and values; outlier found no table |
| `United States_2014-07-23.pdf` | United States | main | Weiqi=SA | SL | same year and values; outlier found no table |
| `United States_2015-07-07.pdf` | United States | main | Weiqi=SA | SL | same year and values; outlier found no table |
| `Uruguay_2011-03-03.pdf` | Uruguay | main | Weiqi=SA | SL | same year and values; outlier found no table |
| `Uruguay_2014-01-10.pdf` | Uruguay | main | Weiqi=SA | SL | same year and values; outlier found no table |
| `Uruguay_2015-03-26.pdf` | Uruguay | main | Weiqi=SA | SL | same year and values; outlier found no table |
| `Vanuatu_2011-05-31.pdf` | Vanuatu | main | Weiqi=SA | SL | same year and values; outlier found no table |
| `Vietnam_2012-07-06.pdf` | Vietnam | main | Weiqi=SA | SL | same year and values; outlier found no table |
| `Vietnam_2014-10-16.pdf` | Vietnam | main | Weiqi=SA | SL | same year and values; outlier found no table |
| `Zambia_2012-07-26.pdf` | Zambia | errors | Weiqi=SA | SL | same year and values; outlier found no table |
| `Zambia_2015-06-16.pdf` | Zambia | errors | Weiqi=SA | SL | same year and values; outlier found no table |
| `Zimbabwe_2011-06-14.pdf` | Zimbabwe | main | Weiqi=SA | SL | same year and values; outlier found no table |
| `Zimbabwe_2012-09-28.pdf` | Zimbabwe | main | Weiqi=SA | SL | same year and values; outlier found no table |
| `Zimbabwe_2014-07-11.pdf` | Zimbabwe | main | Weiqi=SA | SL | same year and values; outlier found no table |

The 22 reports where no two versions fully agree: `Colombia_2011-08-02.pdf`, `Czech Republic_2011-04-07.pdf`, `Dominica_2012-02-27.pdf`, `El Salvador_2011-04-19.pdf`, `El Salvador_2011-10-12.pdf`, `Former Yugoslav Republic of Macedonia_2015-09-03.pdf`, `Georgia_2013-04-03.pdf`, `Italy_2014-09-18.pdf`, `Malaysia_2015-03-03.pdf`, `Mauritius_2011-05-04.pdf`, `Portugal_2013-01-18.pdf`, `Republic of Poland_2011-07-08.pdf`, `Republic of Slovenia_2014-01-17.pdf`, `Romania_2012-10-23.pdf`, `Romania_2015-03-27.pdf`, `Russian Federation_2012-08-03.pdf`, `Senegal_2013-06-24.pdf`, `St. Kitts and Nevis_2012-10-15.pdf`, `Uganda_2015-11-20.pdf`, `Ukraine_2012-11-27.pdf`, `United Republic of Tanzania_2014-05-15.pdf`, `Vanuatu_2015-06-16.pdf`.

---

## 7. SA Errors File vs. Main File

SA saved 51 reports in a separate errors file. Its role is not documented in the data itself; what the data shows is that 49 of the 51 carry `manual_review_required = Yes` and 2 have no table (`pages_unreadable`), i.e. the file collects reports SA's own checks flagged. His main file is not clean either: 88 of its 651 reports are also flagged. The analysis below therefore looks at the two groups as they are, and asks two questions: are the errors-file reports really different, and does SA's flag help to find the reports where the versions disagree?

### 7.1 Agreement by SA group

| Group | Reports | `table_found` agrees | Found by all three | Same year (of found by all) | 3-way exact value match | Value match SL–Weiqi / SL–SA / Weiqi–SA | Fully match |
|---|---:|---|---:|---|---:|---|---|
| SA main file | 649 | 582 (89.7%) | 414 | 376 (90.8%) | 92.6% | 95.6% / 95.3% / 94.3% | 512 (78.9%) |
| SA errors file | 50 | 41 (82.0%) | 40 | 28 (70.0%) | 75.5% | 83.6% / 81.5% / 85.1% | 27 (54.0%) |
| All common reports | 699 | 623 (89.1%) | 454 | 404 (89.0%) | 91.0% | 94.5% / 94.0% / 93.4% | 539 (77.1%) |

**The errors-file reports are harder for every version.** On these 50 reports SL and Weiqi agree with each other on only 83.6% of values, against 95.6% on the main-file reports, so the low agreement is not specific to SA's reading. Their fully-matching share is 54% against 79% for the main file, and 30% of the errors-file reports found by all three show a year disagreement, against 9%. The group is small (50 reports), so percentages move by a few points with each report.

### 7.2 Headline numbers with and without the errors-file reports

| | All 699 common reports | SA main file only (649) |
|---|---:|---:|
| `table_found` agreement | 89.1% | 89.7% |
| Same last actual year (found by all three) | 89.0% | 90.8% |
| 3-way exact value match | 91.0% | 92.6% |
| Fully matching reports | 77.1% | 78.9% |

Leaving the errors-file reports out lifts every rate, but the picture does not change: the `table_found` splits and the last-actual-year disagreements are present in the main file as well. Reporting both versions is the honest way to present the batch, because the errors-file reports are exactly the ones where a reviewer's time is most needed.

### 7.3 Does SA's `manual_review_required` flag find the disagreements?

Base rate: 160 of 699 common reports (22.9%) have at least one disagreement.

| Flag from | Reports flagged | Flagged reports that are disagreement reports | Disagreement reports caught by the flag (of the disagreement reports in the same group) |
|---|---:|---|---|
| SL | 16 | 15 (94%) | 15 of 160 (9%) |
| Weiqi | 13 | 12 (92%) | 12 of 160 (8%) |
| SA (all) | 136 | 98 (72%) | 98 of 160 (61%) |
| SA, main file | 88 | 76 (86%) | 76 of 137 (55%) |
| SA, errors file | 48 | 22 (46%) | 22 of 23 (96%) |

- SL and Weiqi flag very few reports (16 and 13 in total) and nearly all of them are real disagreements, so their flags are precise but catch only a small part of the problem.
- SA's flag is much broader. In his **main file** it is a useful screen (most flagged reports are real disagreements); in the **errors file** it adds nothing beyond the group itself: 22 of the 48 flagged reports are disagreements, almost exactly the errors-group base rate (23 of 50, 46%), because nearly every report in that file is flagged.
- Taking the flags of all three versions together catches 99 of the 160 disagreement reports; **61 disagreement reports are not flagged by anyone**. The flags are a useful first list, not a substitute for the disagreement list in Section 6.

---

## 8. Other Behavioural Differences

**`manual_review_required`** among the 454 reports found by all three: the three versions agree on 388 (85.5%); the 66 disagreements are almost all SA flagging a report that SL and Weiqi do not (66 reports). As in 2016–2020, SA's flag is stricter than the other two, and SA's pipeline includes an independent numeric re-read of the selected column (visible in his validation issues), which SL and Weiqi do not have.

**`extraction_method`** agrees on 447 of the 454 reports found by all three. SA's method list has one entry the others lack: `pymupdf_pillow_multi_orientation_retry`, used for 59 main-file and 3 errors-file reports.

**Self-reported `confidence`** agrees on 407 of 454 (89.6%); 39 reports differ by one notch and 8 span high to low.

---

## 9. Formatting

Unlike 2016–2020, the three files in this batch already use the same conventions: `True`/`False` for `table_found`, full month-year publication dates (`February 2011`), float strings for `page_pdf` and `level`. The only cosmetic differences left are country-name spellings taken from the report itself, so this comparison keys every report on `pdf_file_name`.

---

## 10. Recommendations

1. **Spot-check the 43 reports only SA found** (list in Section 3, `SA extraction method` = `multi_orientation_retry`). If they hold up, SA's rotated-page fallback should be adopted by the other pipelines; if they do not, SA's table detection is producing false positives.
2. **Check the 24 reports SL missed but Weiqi and SA found** (SL's locator step is the likely cause) and the 8 that Weiqi missed.
3. **Standardise the last-actual-year rule**: 50 reports still differ, and 44 of the 78 reports with value differences trace back to it.
4. **Manually verify the three-way scatter reports** (22, listed in Section 6.1) and the largest value gaps in Section 5, starting with `Guinea-Bissau_2011-12-14.pdf`.
5. **Prioritise the 77 reports where two versions agree and the third read the same table differently** (SL 23, SA 28, Weiqi 26): the two agreeing readers make the odd one out the most likely error. Filter `two_agree_basis` in the two-of-three CSV.
6. **Treat SA's errors-file reports as a review queue, not as SA-specific failures**: all three versions disagree more on them. When reporting results for this batch, give the numbers with and without them (Section 7.2).

---

*Data sources: `dsa_decomposition_sl_20260914.csv` (SL), `dsa_decomposition_labels_2011_2015_Weiqi.csv` (Weiqi), `dsa_decomposition_labels_2011-2015_sa.csv` and `dsa_decomposition_labels_2011-2015_errors_sa.csv` (SA), all in `output/2011-2015/compiled_csv/`. Companion to the 2016–2020 comparison.*
