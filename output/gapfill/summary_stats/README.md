# Gap Fill summary stats

There is one folder per version of the merged panel. The newest folder is the current one.

| Folder | Built from | Gap Fill runs included |
|---|---|---|
| `20261028_gapfill_run1_run2/` | `final_all_batches_with_gapfill_20261028.csv` | 202601022 + 202601028 |
| `20261026_gapfill_run1/` | `final_all_batches_with_gapfill.csv` (same rows as `_20261026`) | 202601022 only (kept for comparison) |

The two Gap Fill runs targeted different gaps:
- **Run 1 (202601022):** years missing *between* a country's own first and last observed year.
- **Run 2 (202601028):** every other missing year of the full 2001–2025 panel (3a `FULL_RANGE`). It is incremental, so it skips every gap that run 1 already listed.

## What each folder contains

```
<version>/
  availability/        one row per year: available vs unavailable, and the breakdown of each
    panel_source_breakdown_residual.csv                (hierarchy_id 6)
    panel_source_breakdown_other_identified_flows.csv  (hierarchy_id 5)
  coverage/            one row per year: countries with a value, duplicate rows, conflicting duplicates
    panel_coverage_residual.csv
    panel_coverage_other_identified_flows.csv
    panel_coverage_duplicates_detail.csv   every country-year with more than one row, all values listed
  unavailable_detail/  (20261028 only) one row per unavailable country-year, with the reason and the
                       Gap Fill run, gap_id, candidate reports and last failure detail
    unavailable_country_years_residual.csv
    unavailable_country_years_other_identified_flows.csv
```

### `availability/` columns

- `total_countries`: every country in the merged file. The count is the same for every year.
- `n_available` and `n_unavailable` add up to `total_countries`.
- **Available**, split by source: `n_round1` + `n_round2` + `n_round3_human_review` + `n_gapfill` = `n_available`.
  - If more than one round covers a country-year, one round is counted, in this order: round1 > round2 > round3 > gapfill.
  - `n_gapfill_run_<STAMP>` splits `n_gapfill` by Gap Fill run.
- **Unavailable**, split by reason (these six columns add up to `n_unavailable`):
  - `n_unavail_not_gap_candidate`: no report, and no Gap Fill run targeted this country-year.
  - `n_unavail_report_exists_field_missing`: a Round 1/2/3 report exists for this year, but this field was not extracted from it.
  - `n_unavail_gapfill_unresolved`: Gap Fill tried every candidate report, and none gave an actual value.
  - `n_unavail_gapfill_no_candidate_report`: no T+2/T+3/T+4 report exists.
  - `n_unavail_gapfill_pending_api_error`: the run was interrupted. These can be retried.
  - `n_unavail_gapfill_resolved_but_field_missing`: Gap Fill resolved the year, but not this field.
- `n_unavail_gap_target_run_<STAMP>`: the unavailable country-years that Gap Fill targeted, by the run that targeted them.

## Headline numbers (20261028, panel 2001–2025, 190 countries = 4,750 country-years)

| | residual | other_identified_flows |
|---|---|---|
| Available | 3,410 (71.8%) | 3,395 (71.5%) |
| from Round 1 / 2 / 3 | 2,013 / 239 / 169 | 2,005 / 256 / 149 |
| from Gap Fill run 1 / run 2 | 776 / 213 | 775 / 210 |
| Unavailable | 1,340 | 1,355 |
| Gap Fill unresolved (all candidates tried) | 752 | 752 |
| no candidate report | 510 | 510 |
| pending API error (retry) | 49 | 49 |
| other | 29 | 44 |

2025 is mostly unavailable (145 of 190). Its T+2 reports do not exist yet.

## Differences from the 20261026 version

- **Year range.** The tables now cover only the 2001–2025 panel. One residual row outside that range is left out.
- **Country names.** `normalize_country()` in `code/gapfill_lib_core.py` now merges spellings that had been counted as separate countries:
  - `St.Vincent` / `St. Vincent`
  - `Türki̇ye` (with a combining dot) / `Türkiye` / `Turkey`
  - `Cape Verde` / `Cabo Verde`
  - `Democratic Republic of Congo` / `...of the Congo`
  - `Democratic Republic of São Tomé`
  - `Kingdom of the Netherland-…` and `Kingdom Of Netherlands-The Netherlands`

  As a result, the country total is 190 here, down from 194 in the 20261026 version.
- **Spurious run-2 targets.** 3a also split these countries, so run 2 targeted about 150 country-years that were not real gaps: they were already observed under another spelling, or listed twice. In these tables, each country-year is counted once. A duplicated target keeps its most informative status (resolved first). The few resolved duplicates show up as duplicate rows in `coverage/panel_coverage_duplicates_detail.csv`.

## How to rebuild

```
python code/gapfill_append_run.py              # merged CSV: previous version + the new run's values_long
python code/gapfill_panel_coverage_report.py   # coverage/
python code/gapfill_panel_source_breakdown.py  # availability/ and unavailable_detail/
```
