# Gap-year check, step 1: panel structure and gap flags (2016-2020, SA output)

**Date generated:** 2026-09-18  
**Input:** `dsa_decomposition_labels_2016-2020_sa.csv` (851 reports). The 61 reports in `dsa_decomposition_labels_2016-2020_errors_sa.csv` are **not** used as observations; they are only used to explain gaps (see cause below).  
**Script:** `code/gapfill_1_build_panel_gap_flags.py`

## 1. Rules applied

- Each report gives one observation: (country, `last_actual_year`). No PDF was re-read.
- Country and report date come from the PDF file name, and country spellings are unified (e.g. "Republic of Armenia" = "Armenia", "Kingdom of Swaziland" = "Eswatini", "Former Yugoslav Republic of Macedonia" = "North Macedonia").
- Fiscal-year labels map to the fiscal-year end year (`2015/16` becomes 2016). Multi-year ranges are not a usable year.
- Several reports with the same country and year: the **latest report** is kept; the others are listed in `duplicate_reports_superseded`.
- A gap year is a year strictly between a country's first and last observed year that no kept report supplies. Start and end years are not flagged.
- A report is left out of the panel if `report year - last actual year` is 4 or more, or negative. This is almost certainly a misread or a non-standard document; see section 3.

## 2. Headline numbers

| Item | Count |
|---|---:|
| Reports in main file | 851 |
| Countries in panel | 180 |
| Observed country-years (kept reports) | 640 |
| Countries with at least one gap | 94 |
| Gap years | 120 |
| Gap spans (consecutive missing years) | 104 |
| Gap spans of 1 / 2 / 3 years | 90 / 12 / 2 |
| Gap years if the 32 observations flagged `manual_review` are dropped | 112 (89 countries) |

How the 851 main-file reports were used:

| Status | Reports |
|---|---:|
| Kept observation | 640 |
| Superseded by a later report with the same country-year | 92 |
| No DSA table found | 112 |
| Year implausible vs. report date (left out) | 4 |
| Table found but year unusable | 1 |
| Multi-country document (not a country) | 2 |

## 3. Things to know before using the panel

- **Duplicates disagree often.** 80 country-years have more than one report; in 64 of them the six top-level values differ between reports (revisions or extraction differences). The panel uses the latest report; `duplicate_values_agree` shows which ones to look at.
- **Errors file.** 19 gap spans have a report from the errors file between the two bounding reports. If those reports are verified and added, these gaps may close by themselves, so check them before spending effort on PDF re-extraction.
- **Implausible years left out** (4 reports): `Ecuador_2019-03-21.pdf` (year 2015), `Maldives_2019-09-03_CR2019-281.pdf` (year 2004), `Maldives_2019-09-03_CR2019-282.pdf` (year 2006), `Maldives_2019-09-03_CR2019-283.pdf` (year 2011).
- **Unusable year** (1 report): `Cabo Verde_2016-11-29.pdf` (table found, but `last_actual_year` is empty).
- **Batch edges.** Only 2016-2020 reports are in this file, so a gap that straddles the 2015/2016 or 2020/2021 boundary cannot be seen. The script is batch-independent and can be re-run on a combined file.

## 4. Why the gaps exist

| Primary cause (per gap span) | Spans |
|---|---:|
| Lag: consecutive reports, last actual year jumps | 74 |
| A report in between sits in the errors_sa file (not used) | 19 |
| A report in between has no DSA table | 11 |

## 5. Can the gap year be filled? (from each report's column-header audit)

| Status (per gap year) | Gap years |
|---|---:|
| Fillable: some report shows the year as an actual/historical column | 106 |
| Only inside a merged range column (e.g. "2002-2010") | 5 |
| Only as projection column | 5 |
| Only as preliminary/estimate column | 4 |

For each gap year, `preferred_source_report` is the earliest report (main file first) that shows that exact year as a single actual/historical column; `all_actual_source_reports` lists every such report. Years that appear only as estimate or projection should not be filled without a decision from you.

## 6. All 120 gap years

| Gap | Country | Gap year | Report before gap | Report after gap | Cause | Fill status | Preferred source report |
|---|---|---|---|---|---|---|---|
| G0001 | Angola | 2016 | `Angola_2017-02-06.pdf` | `Angola_2018-06-11.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Angola_2018-06-11.pdf` |
| G0002 | Armenia | 2017 | `Republic of Armenia_2017-07-19.pdf` | `Republic of Armenia_2019-06-05.pdf` | no_table_report_in_between | fillable_actual_column_visible | `Republic of Armenia_2019-06-05.pdf` |
| G0003 | Aruba | 2017 | `Kingdom of the Netherlands—Aruba_2017-06-15.pdf` | `Kingdom of the Netherlands—Aruba_2019-06-05.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Kingdom of the Netherlands—Aruba_2019-06-05.pdf` |
| G0004 | Azerbaijan | 2016 | `Republic of Azerbaijan_2016-09-14.pdf` | `Republic of Azerbaijan_2019-09-18.pdf` | lag_between_consecutive_reports | only_in_merged_range_column | — |
| G0004 | Azerbaijan | 2017 | `Republic of Azerbaijan_2016-09-14.pdf` | `Republic of Azerbaijan_2019-09-18.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Republic of Azerbaijan_2019-09-18.pdf` |
| G0005 | Bangladesh | 2017 | `Bangladesh_2018-06-08.pdf` | `Bangladesh_2019-09-18.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Bangladesh_2019-09-18.pdf` |
| G0006 | Bolivia | 2018 | `Bolivia_2018-12-21.pdf` | `Bolivia_2020-05-29.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Bolivia_2020-05-29.pdf` |
| G0007 | Bosnia and Herzegovina | 2017 | `Bosnia and Herzegovina_2018-02-13.pdf` | `Bosnia and Herzegovina_2020-04-23.pdf` | lag_between_consecutive_reports | only_in_merged_range_column | — |
| G0007 | Bosnia and Herzegovina | 2018 | `Bosnia and Herzegovina_2018-02-13.pdf` | `Bosnia and Herzegovina_2020-04-23.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Bosnia and Herzegovina_2020-04-23.pdf` |
| G0008 | Bulgaria | 2017 | `Bulgaria_2018-02-21.pdf` | `Bulgaria_2019-03-22.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Bulgaria_2019-03-22.pdf` |
| G0009 | Burkina Faso | 2015 | `Burkina Faso_2016-06-16.pdf` | `Burkina Faso_2018-03-15.pdf` | errors_file_report_in_between | fillable_actual_column_visible | `Burkina Faso_2018-03-15.pdf` |
| G0010 | Cabo Verde | 2017 | `Cabo Verde_2018-04-18.pdf` | `Cabo Verde_2019-07-31.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Cabo Verde_2019-07-31.pdf` |
| G0011 | Cameroon | 2016 | `Cameroon_2017-07-05.pdf` | `Cameroon_2018-07-23.pdf` | no_table_report_in_between | fillable_actual_column_visible | `Cameroon_2018-07-23.pdf` |
| G0012 | Central African Republic | 2017 | `Central African Republic_2017-12-27.pdf` | `Central African Republic_2019-07-09.pdf` | errors_file_report_in_between | fillable_actual_column_visible | `Central African Republic_2019-07-09.pdf` |
| G0013 | Chad | 2018 | `Chad_2019-01-24.pdf` | `Chad_2020-04-23.pdf` | errors_file_report_in_between | fillable_actual_column_visible | `Chad_2020-04-23.pdf` |
| G0014 | Chile | 2016 | `Chile_2016-12-09.pdf` | `Chile_2018-11-09.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Chile_2018-11-09.pdf` |
| G0015 | Chile | 2018 | `Chile_2018-11-09.pdf` | `Chile_2020-05-29.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Chile_2020-05-29.pdf` |
| G0016 | Comoros | 2016 | `Union of the Comoros_2016-12-22.pdf` | `Union of the Comoros_2019-08-14.pdf` | errors_file_report_in_between | fillable_actual_column_visible | `Union of the Comoros_2019-08-14.pdf` |
| G0016 | Comoros | 2017 | `Union of the Comoros_2016-12-22.pdf` | `Union of the Comoros_2019-08-14.pdf` | errors_file_report_in_between | fillable_actual_column_visible | `Union of the Comoros_2019-08-14.pdf` |
| G0017 | Costa Rica | 2017 | `Costa Rica_2017-06-27.pdf` | `Costa Rica_2019-04-13.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Costa Rica_2019-04-13.pdf` |
| G0018 | Croatia | 2018 | `Republic of Croatia_2019-02-12.pdf` | `Republic of Croatia_2020-02-19.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Republic of Croatia_2020-02-19.pdf` |
| G0019 | Curaçao and Sint Maarten | 2016 | `Kingdom of the Netherlands—Curaçao and Sint Maarten_2016-08-22.pdf` | `Kingdom of the Netherlands—Curaçao and Sint Maarten_2019-01-25.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Kingdom of the Netherlands—Curaçao and Sint Maarten_2019-01-25.pdf` |
| G0020 | Curaçao and Sint Maarten | 2018 | `Kingdom of the Netherlands—Curaçao and Sint Maarten_2019-01-25.pdf` | `Kingdom of the Netherlands-Curacao and Sint Maarten_2020-04-01.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Kingdom of the Netherlands-Curacao and Sint Maarten_2020-04-01.pdf` |
| G0021 | Cyprus | 2015 | `Cyprus_2016-01-29.pdf` | `Cyprus_2017-06-08.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Cyprus_2017-06-08.pdf` |
| G0022 | Djibouti | 2016 | `Djibouti_2017-04-06.pdf` | `Djibouti_2019-10-23.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Djibouti_2019-10-23.pdf` |
| G0022 | Djibouti | 2017 | `Djibouti_2017-04-06.pdf` | `Djibouti_2019-10-23.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Djibouti_2019-10-23.pdf` |
| G0023 | Dominican Republic | 2015 | `Dominican Republic_2016-11-10.pdf` | `Dominican Republic_2017-08-16.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Dominican Republic_2017-08-16.pdf` |
| G0024 | Dominican Republic | 2018 | `Dominican Republic_2019-08-15.pdf` | `Dominican Republic_2020-05-07.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Dominican Republic_2020-05-07.pdf` |
| G0025 | Ecuador | 2016 | `Ecuador_2016-09-09.pdf` | `Ecuador_2019-03-20.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Ecuador_2019-03-20.pdf` |
| G0026 | El Salvador | 2016 | `El Salvador_2016-07-01.pdf` | `El Salvador_2018-06-07.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `El Salvador_2018-06-07.pdf` |
| G0027 | Equatorial Guinea | 2016 | `Republic of Equatorial Guinea_2016-11-16.pdf` | `Republic of Equatorial Guinea_2019-12-20.pdf` | no_table_report_in_between | only_in_merged_range_column | — |
| G0027 | Equatorial Guinea | 2017 | `Republic of Equatorial Guinea_2016-11-16.pdf` | `Republic of Equatorial Guinea_2019-12-20.pdf` | no_table_report_in_between | fillable_actual_column_visible | `Republic of Equatorial Guinea_2019-12-20.pdf` |
| G0028 | Estonia | 2016 | `Republic of Estonia_2017-01-13.pdf` | `Republic of Estonia_2018-05-24.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Republic of Estonia_2018-05-24.pdf` |
| G0029 | Eswatini | 2017 | `Kingdom of Swaziland_2017-09-11.pdf` | `Kingdom of Eswatini_2020-02-11.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Kingdom of Eswatini_2020-02-11.pdf` |
| G0030 | Ethiopia | 2016 | `The Federal Democratic Republic of Ethiopia_2016-10-04.pdf` | `The Federal Democratic Republic of Ethiopia_2018-01-24.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `The Federal Democratic Republic of Ethiopia_2018-01-24.pdf` |
| G0031 | Fiji | 2015 | `Republic of Fiji_2016-02-22.pdf` | `Republic of Fiji_2018-02-08.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Republic of Fiji_2018-02-08.pdf` |
| G0032 | Gambia | 2017 | `The Gambia_2018-04-04.pdf` | `The Gambia_2019-05-08.pdf` | errors_file_report_in_between | fillable_actual_column_visible | `The Gambia_2019-05-08.pdf` |
| G0033 | Ghana | 2015 | `Ghana_2016-01-20.pdf` | `Ghana_2018-05-02.pdf` | errors_file_report_in_between | fillable_actual_column_visible | `Ghana_2018-05-02.pdf` |
| G0034 | Grenada | 2016 | `Grenada_2016-12-21.pdf` | `Grenada_2018-07-25.pdf` | errors_file_report_in_between | fillable_actual_column_visible | `Grenada_2018-07-25.pdf` |
| G0035 | Guatemala | 2017 | `Guatemala_2018-06-08.pdf` | `Guatemala_2019-06-18.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Guatemala_2019-06-18.pdf` |
| G0036 | Guinea | 2016 | `Guinea_2016-04-04.pdf` | `Guinea_2019-01-28.pdf` | errors_file_report_in_between | fillable_actual_column_visible | `Guinea_2019-01-28.pdf` |
| G0037 | Guinea-Bissau | 2016 | `Guinea-Bissau_2016-12-28.pdf` | `Guinea-Bissau_2018-06-06.pdf` | errors_file_report_in_between | fillable_actual_column_visible | `Guinea-Bissau_2018-06-06.pdf` |
| G0038 | Guyana | 2017 | `Guyana_2017-06-28.pdf` | `Guyana_2019-09-17.pdf` | errors_file_report_in_between | fillable_actual_column_visible | `Guyana_2019-09-17.pdf` |
| G0039 | Haiti | 2016 | `Haiti_2017-02-06.pdf` | `Haiti_2020-04-20_CR2020-121.pdf` | lag_between_consecutive_reports | only_preliminary_or_estimate | `Haiti_2017-02-06.pdf` |
| G0039 | Haiti | 2017 | `Haiti_2017-02-06.pdf` | `Haiti_2020-04-20_CR2020-121.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Haiti_2020-04-20_CR2020-121.pdf` |
| G0039 | Haiti | 2018 | `Haiti_2017-02-06.pdf` | `Haiti_2020-04-20_CR2020-121.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Haiti_2020-04-20_CR2020-121.pdf` |
| G0040 | Hungary | 2016 | `Hungary_2017-05-12.pdf` | `Hungary_2018-08-03.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Hungary_2018-08-03.pdf` |
| G0041 | India | 2016 | `India_2017-02-22.pdf` | `India_2018-08-06.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `India_2018-08-06.pdf` |
| G0042 | Indonesia | 2017 | `Indonesia_2018-02-06.pdf` | `Indonesia_2019-07-31.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Indonesia_2019-07-31.pdf` |
| G0043 | Iraq | 2017 | `Iraq_2017-08-09.pdf` | `Iraq_2019-07-26.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Iraq_2019-07-26.pdf` |
| G0044 | Jamaica | 2016 | `Jamaica_2016-11-15.pdf` | `Jamaica_2018-04-16.pdf` | no_table_report_in_between | fillable_actual_column_visible | `Jamaica_2018-04-16.pdf` |
| G0045 | Jamaica | 2018 | `Jamaica_2019-04-23.pdf` | `Jamaica_2020-05-18.pdf` | no_table_report_in_between | fillable_actual_column_visible | `Jamaica_2020-05-18.pdf` |
| G0046 | Jordan | 2017 | `Jordan_2017-07-24.pdf` | `Jordan_2019-05-15.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Jordan_2019-05-15.pdf` |
| G0047 | Kenya | 2017 | `Kenya_2018-10-23.pdf` | `Republic of Kenya_2020-05-11.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Republic of Kenya_2020-05-11.pdf` |
| G0047 | Kenya | 2018 | `Kenya_2018-10-23.pdf` | `Republic of Kenya_2020-05-11.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Republic of Kenya_2020-05-11.pdf` |
| G0048 | Korea | 2015 | `Republic of Korea_2016-08-26.pdf` | `Republic of Korea_2018-02-13.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Republic of Korea_2018-02-13.pdf` |
| G0049 | Korea | 2017 | `Republic of Korea_2018-02-13.pdf` | `Republic of Korea_2019-05-13.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Republic of Korea_2019-05-13.pdf` |
| G0050 | Kosovo | 2018 | `Republic of Kosovo_2018-12-18.pdf` | `Republic of Kosovo_2020-04-16.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Republic of Kosovo_2020-04-16.pdf` |
| G0051 | Kuwait | 2017 | `Kuwait_2018-01-26.pdf` | `Kuwait_2019-04-02.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Kuwait_2019-04-02.pdf` |
| G0052 | Kyrgyz Republic | 2018 | `Kyrgyz Republic_2019-07-03.pdf` | `Kyrgyz Republic_2020-03-27.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Kyrgyz Republic_2020-03-27.pdf` |
| G0053 | Lebanon | 2016 | `Lebanon_2017-01-24.pdf` | `Lebanon_2019-10-17.pdf` | lag_between_consecutive_reports | only_in_merged_range_column | — |
| G0053 | Lebanon | 2017 | `Lebanon_2017-01-24.pdf` | `Lebanon_2019-10-17.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Lebanon_2019-10-17.pdf` |
| G0054 | Lesotho | 2015 | `Kingdom of Lesotho_2016-02-03.pdf` | `Kingdom of Lesotho_2018-02-28.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Kingdom of Lesotho_2018-02-28.pdf` |
| G0055 | Lesotho | 2018 | `Kingdom of Lesotho_2019-04-30.pdf` | `Kingdom of Lesotho_2020-07-30.pdf` | lag_between_consecutive_reports | only_projection | — |
| G0056 | Liberia | 2015 | `Liberia_2016-12-22.pdf` | `Liberia_2017-11-20.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Liberia_2017-11-20.pdf` |
| G0057 | Liberia | 2017 | `Liberia_2017-11-20.pdf` | `Liberia_2019-06-19.pdf` | errors_file_report_in_between | fillable_actual_column_visible | `Liberia_2019-06-19.pdf` |
| G0058 | Madagascar | 2017 | `Republic of Madagascar_2017-07-18.pdf` | `Republic of Madagascar_2019-08-01.pdf` | errors_file_report_in_between | fillable_actual_column_visible | `Republic of Madagascar_2019-08-01.pdf` |
| G0059 | Malaysia | 2016 | `Malaysia_2017-04-28.pdf` | `Malaysia_2018-03-07.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Malaysia_2018-03-07.pdf` |
| G0060 | Maldives | 2015 | `Maldives_2016-05-31.pdf` | `Maldives_2017-12-01.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Maldives_2017-12-01.pdf` |
| G0061 | Maldives | 2018 | `Maldives_2019-06-10.pdf` | `Maldives_2020-04-23.pdf` | no_table_report_in_between | fillable_actual_column_visible | `Maldives_2020-04-23.pdf` |
| G0062 | Mali | 2016 | `Mali_2016-12-07.pdf` | `Mali_2018-05-31.pdf` | errors_file_report_in_between | fillable_actual_column_visible | `Mali_2018-05-31.pdf` |
| G0063 | Moldova | 2016 | `Republic of Moldova_2016-11-09.pdf` | `Republic of Moldova_2020-03-18.pdf` | errors_file_report_in_between | only_preliminary_or_estimate | `Republic of Moldova_2016-11-09.pdf` |
| G0063 | Moldova | 2017 | `Republic of Moldova_2016-11-09.pdf` | `Republic of Moldova_2020-03-18.pdf` | errors_file_report_in_between | only_projection | — |
| G0064 | Montenegro | 2015 | `Montenegro_2016-03-08.pdf` | `Montenegro_2017-09-14.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Montenegro_2017-09-14.pdf` |
| G0065 | Mozambique | 2015 | `Republic of Mozambique_2016-01-08.pdf` | `Republic of Mozambique_2018-03-07.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Republic of Mozambique_2018-03-07.pdf` |
| G0066 | Myanmar | 2016 | `Myanmar_2017-02-02.pdf` | `Myanmar_2019-04-10.pdf` | errors_file_report_in_between | fillable_actual_column_visible | `Myanmar_2019-04-10.pdf` |
| G0067 | Namibia | 2017 | `Namibia_2018-02-28.pdf` | `Namibia_2019-09-13.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Namibia_2019-09-13.pdf` |
| G0068 | Nauru | 2017 | `Republic of Nauru_2017-04-03.pdf` | `Republic of Nauru_2020-01-29.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Republic of Nauru_2020-01-29.pdf` |
| G0069 | Nepal | 2017 | `Nepal_2017-03-27.pdf` | `Nepal_2019-02-17.pdf` | lag_between_consecutive_reports | only_preliminary_or_estimate | `Nepal_2017-03-27.pdf` |
| G0070 | Netherlands | 2016 | `Kingdom of the Netherlands—Netherlands_2017-04-03.pdf` | `Kingdom of the Netherlands—Netherlands_2018-05-28.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Kingdom of the Netherlands—Netherlands_2018-05-28.pdf` |
| G0071 | New Zealand | 2016 | `New Zealand_2017-05-08.pdf` | `New Zealand_2018-07-03.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `New Zealand_2018-07-03.pdf` |
| G0072 | Nicaragua | 2015 | `Nicaragua_2016-02-04.pdf` | `Nicaragua_2017-06-27.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Nicaragua_2017-06-27.pdf` |
| G0073 | Nicaragua | 2017 | `Nicaragua_2017-06-27.pdf` | `Nicaragua_2020-02-27.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Nicaragua_2020-02-27.pdf` |
| G0074 | Niger | 2016 | `Niger_2017-02-24.pdf` | `Niger_2019-07-22.pdf` | no_table_report_in_between | fillable_actual_column_visible | `Niger_2019-07-22.pdf` |
| G0074 | Niger | 2017 | `Niger_2017-02-24.pdf` | `Niger_2019-07-22.pdf` | no_table_report_in_between | fillable_actual_column_visible | `Niger_2019-07-22.pdf` |
| G0075 | Nigeria | 2017 | `Nigeria_2018-03-07.pdf` | `Nigeria_2019-04-01.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Nigeria_2019-04-01.pdf` |
| G0076 | North Macedonia | 2017 | `Former Yugoslav Republic of Macedonia_2017-11-22.pdf` | `Republic of North Macedonia_2020-04-21.pdf` | errors_file_report_in_between | fillable_actual_column_visible | `Former Yugoslav Republic of Macedonia_2019-01-29.pdf` |
| G0076 | North Macedonia | 2018 | `Former Yugoslav Republic of Macedonia_2017-11-22.pdf` | `Republic of North Macedonia_2020-04-21.pdf` | errors_file_report_in_between | fillable_actual_column_visible | `Republic of North Macedonia_2020-04-21.pdf` |
| G0077 | Palau | 2016 | `Republic of Palau_2016-10-19.pdf` | `Republic of Palau_2019-02-05.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Republic of Palau_2019-02-05.pdf` |
| G0078 | Panama | 2018 | `Panama_2019-01-17.pdf` | `Panama_2020-04-21.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Panama_2020-04-21.pdf` |
| G0079 | Papua New Guinea | 2016 | `Papua New Guinea_2017-01-30.pdf` | `Papua New Guinea_2018-12-03.pdf` | errors_file_report_in_between | fillable_actual_column_visible | `Papua New Guinea_2018-12-03.pdf` |
| G0080 | Paraguay | 2018 | `Paraguay_2019-04-30.pdf` | `Paraguay_2020-04-22.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Paraguay_2020-04-22.pdf` |
| G0081 | Peru | 2017 | `Peru_2018-07-25.pdf` | `Peru_2020-01-13.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Peru_2020-01-13.pdf` |
| G0082 | Portugal | 2015 | `Portugal_2016-09-22_CR2016-300.pdf` | `Portugal_2017-09-15.pdf` | errors_file_report_in_between | fillable_actual_column_visible | `Portugal_2017-09-15.pdf` |
| G0083 | Rwanda | 2017 | `Rwanda_2017-07-13.pdf` | `Rwanda_2019-07-03.pdf` | no_table_report_in_between | fillable_actual_column_visible | `Rwanda_2019-07-03.pdf` |
| G0084 | Samoa | 2017 | `Samoa_2018-06-04.pdf` | `Samoa_2019-05-17.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Samoa_2019-05-17.pdf` |
| G0085 | San Marino | 2017 | `Republic of San Marino_2018-04-11.pdf` | `Republic of San Marino_2019-03-25.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Republic of San Marino_2019-03-25.pdf` |
| G0086 | Seychelles | 2018 | `Seychelles_2019-01-07.pdf` | `Seychelles_2020-05-19.pdf` | no_table_report_in_between | fillable_actual_column_visible | `Seychelles_2020-05-19.pdf` |
| G0087 | Sierra Leone | 2016 | `Sierra Leone_2017-06-22.pdf` | `Sierra Leone_2020-06-10.pdf` | no_table_report_in_between | only_preliminary_or_estimate | `Sierra Leone_2017-06-22.pdf` |
| G0087 | Sierra Leone | 2017 | `Sierra Leone_2017-06-22.pdf` | `Sierra Leone_2020-06-10.pdf` | no_table_report_in_between | only_projection | — |
| G0087 | Sierra Leone | 2018 | `Sierra Leone_2017-06-22.pdf` | `Sierra Leone_2020-06-10.pdf` | no_table_report_in_between | only_projection | — |
| G0088 | Slovak Republic | 2016 | `Slovak Republic_2017-03-23.pdf` | `Slovak Republic_2018-07-26.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Slovak Republic_2018-07-26.pdf` |
| G0089 | Solomon Islands | 2016 | `Solomon Islands_2016-03-23.pdf` | `Solomon Islands_2018-11-08.pdf` | errors_file_report_in_between | fillable_actual_column_visible | `Solomon Islands_2018-11-08.pdf` |
| G0090 | South Sudan | 2019 | `South Sudan_2019-06-04.pdf` | `Republic of South Sudan_2020-11-16.pdf` | lag_between_consecutive_reports | only_projection | — |
| G0091 | Spain | 2018 | `Spain_2018-11-21.pdf` | `Spain_2020-11-13.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Spain_2020-11-13.pdf` |
| G0092 | St. Lucia | 2016 | `St. Lucia_2017-03-31.pdf` | `St. Lucia_2018-06-20.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `St. Lucia_2018-06-20.pdf` |
| G0093 | St. Vincent and the Grenadines | 2015 | `St. Vincent and the Grenadines_2016-07-19.pdf` | `St. Vincent and the Grenadines_2017-12-21.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `St. Vincent and the Grenadines_2017-12-21.pdf` |
| G0094 | St. Vincent and the Grenadines | 2018 | `St. Vincent and the Grenadines_2019-02-25.pdf` | `St. Vincent and the Grenadines_2020-05-29.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `St. Vincent and the Grenadines_2020-05-29.pdf` |
| G0095 | Sudan | 2017 | `Sudan_2017-12-11.pdf` | `Sudan_2020-03-10.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Sudan_2020-03-10.pdf` |
| G0096 | Suriname | 2016 | `Suriname_2016-06-07.pdf` | `Suriname_2018-12-20.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Suriname_2018-12-20.pdf` |
| G0097 | Switzerland | 2016 | `Switzerland_2016-12-15.pdf` | `Switzerland_2018-06-18.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Switzerland_2018-06-18.pdf` |
| G0098 | São Tomé and Príncipe | 2017 | `Democratic Republic of São Tomé and Príncipe_2017-12-18.pdf` | `Democratic Republic of Sao Tome and Principe_2019-10-29.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Democratic Republic of Sao Tome and Principe_2019-10-29.pdf` |
| G0099 | Timor-Leste | 2015 | `Republic of Timor-Leste_2016-06-24.pdf` | `Democratic Republic of Timor-Leste_2017-12-07.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Democratic Republic of Timor-Leste_2017-12-07.pdf` |
| G0100 | Tunisia | 2017 | `Tunisia_2017-07-10.pdf` | `Tunisia_2020-04-14.pdf` | no_table_report_in_between | only_in_merged_range_column | — |
| G0100 | Tunisia | 2018 | `Tunisia_2017-07-10.pdf` | `Tunisia_2020-04-14.pdf` | no_table_report_in_between | fillable_actual_column_visible | `Tunisia_2020-04-14.pdf` |
| G0101 | Turkey | 2017 | `Turkey_2018-04-30.pdf` | `Turkey_2019-12-26.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Turkey_2019-12-26.pdf` |
| G0102 | United Kingdom | 2018 | `United Kingdom_2018-11-14.pdf` | `United Kingdom_2020-12-18.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `United Kingdom_2020-12-18.pdf` |
| G0103 | Vanuatu | 2017 | `Vanuatu_2018-04-26.pdf` | `Vanuatu_2019-06-13.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Vanuatu_2019-06-13.pdf` |
| G0104 | Zambia | 2016 | `Zambia_2017-10-25.pdf` | `Zambia_2019-08-02.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Zambia_2019-08-02.pdf` |
| G0104 | Zambia | 2017 | `Zambia_2017-10-25.pdf` | `Zambia_2019-08-02.pdf` | lag_between_consecutive_reports | fillable_actual_column_visible | `Zambia_2019-08-02.pdf` |

## 7. Files (same folder, suffix `_20260918_v1`)

- `panel_structure_country_year`: one row per country and year from each country's first to last observed year, with `status` = `observed` or `GAP`. Observed rows carry the six top-level values (`change_in_debt`, `identified_flows`, `primary_balance`, `automatic_debt_dynamics`, `other_identified_flows`, `residual`), the source report and quality flags; GAP rows carry the cause and fill status.
- `gap_years`: one row per gap year with bounding reports, reports in between, cause, and candidate source reports.
- `coverage_matrix_country_year`: countries by years; `O` observed, `O?` observed but year flagged for manual review, `GAP` missing.
- `report_inventory`: every report with how it was used.
- `panel_children_long`: sub-rows (levels 1-2) for the kept observations.
- `summary_stats`: the numbers above as JSON.
