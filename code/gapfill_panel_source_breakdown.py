"""
[ad hoc report] For each year, break the full country universe down into available / unavailable for
residual (hierarchy_id "6") and other_identified_flows (hierarchy_id "5"), and -- within available --
which stage of the pipeline supplied it: Round 1, Round 2, Round 3 (Human Review), or Gap Fill.
    Run by hand | no API, no network | reads the one merged CSV a colleague built, writes two summary CSVs

Builds on gapfill_panel_coverage_report.py (reuses its year-coalescing and country-normalization logic,
see that script's own docstring for why both are needed) and adds two more levels:

Level 1 -- available vs. unavailable, out of a FIXED total country count
    The total is every distinct country (after normalize_country() + casefold) appearing ANYWHERE in the
    merged file, regardless of hierarchy_id or year -- the full country universe this project has ever
    touched, not just the ones with a value for this one field in this one year. It is the same number
    for every year and every field.

Level 2a -- within available, which round supplied it
    A country can have more than one report's row for the same year (see the other script's docstring --
    this is real, not a bug: different reports can each carry an actual/historical value for the same
    year). When that happens here, one round is picked as "the" source by priority: round1, else round2,
    else round3 (Human Review), else gapfill -- Round 1 is the default/first-pass path, Round 2 and
    Round 3 only come into play for a report Round 1 could not resolve, and Gap Fill is last because it
    is only ever invoked for a year no round's own report produced at all (confirmed on this dataset:
    a gapfill row shares its exact country+year with a round1/2/3 row in only 6 of 781 (field, country,
    year) combinations that have more than one round present at all). This priority is a simplification
    for a single clean bucket per country-year, not a claim that Round 1 is more "correct" -- see the
    duplicates-detail output from the other script if you want every individual value instead of one
    picked winner.

Level 2b -- within UNAVAILABLE, gap-fill-attempted vs not, and why a gap-fill attempt still failed
    Needs gapfill_resolution_<STAMP>.csv (3c's own output -- one row per (country, gap_year) Gap Fill
    ever targeted, with its final_status). gap_years_<STAMP>.csv is NOT needed separately:
    gapfill_resolution already has one row per gap year Gap Fill was ever given to try (nothing in the
    pipeline drops a target before it reaches that file, confirmed against the 202601022 run: 1238 rows
    there, 1238 "Gap years selected" printed by 3c's own dry run), so it already IS the authoritative list
    of "what Step 1 judged to be a gap".

    Every unavailable (field, country, year) falls into exactly one of:
      - not a gap-fill target at all, and no report exists for that country-year in any round -- almost
        always because the year falls outside that country's own observed bracket (find_gap_years() in
        3a only ever flags a year strictly BETWEEN a country's first and last observed years; a country
        with fewer than 2 total observed years is skipped entirely) -- Gap Fill was never going to look
        at it, full stop.
      - not a gap-fill target, but a report DOES exist for that country-year (from Round 1/2/3) -- the
        country-year itself is not a panel gap; this one field's value just was not extracted from that
        report. An extraction-completeness issue within Round 1/2/3, unrelated to Gap Fill.
      - a gap-fill target: final_status is one of resolved/resolved_with_warning (yet this field is still
        unavailable -- rare; worth a direct look if the count is more than a handful),
        unresolved (every candidate tried, none gave a value), unresolved_no_candidate_reports (no T+2/
        T+3/T+4 report existed at all), or pending_api_error (interrupted; retry the run).
    On this dataset (202601022 run): of ~1840 unavailable (field, country, year) combinations, roughly
    98-99% of the "not a gap-fill target, no report" bucket is the observed-bracket case above, not a
    processing gap -- i.e. most unavailability is simply outside this project's panel scope for that
    country, not a failure of any step.

Output (written next to the input CSV by default)
    panel_source_breakdown_residual.csv              one row per year: total_countries, n_available,
                                                      n_unavailable, n_round1, n_round2, n_round3,
                                                      n_gapfill (the four n_round*/n_gapfill columns sum
                                                      to n_available), plus -- when GAPFILL_RESOLUTION_CSV
                                                      exists -- n_unavail_not_gap_candidate,
                                                      n_unavail_report_exists_field_missing,
                                                      n_unavail_gapfill_unresolved,
                                                      n_unavail_gapfill_no_candidate_report,
                                                      n_unavail_gapfill_pending_api_error,
                                                      n_unavail_gapfill_resolved_but_field_missing (these
                                                      six sum to n_unavailable)
    panel_source_breakdown_other_identified_flows.csv   the same, for hierarchy_id "5"

Usage
    python gapfill_panel_source_breakdown.py
    or edit INPUT_CSV / OUT_DIR / GAPFILL_RESOLUTION_CSV at the top of the file and run (also works from
    a console). GAPFILL_RESOLUTION_CSV must be the run that produced the gapfill-sourced rows in
    INPUT_CSV (same STAMP) -- Level 2b is silently skipped (columns omitted) if it is not found.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(HERE))
import gapfill_lib_core as core  # noqa: E402
from gapfill_panel_coverage_report import ALL_HIERARCHIES, FIELDS, INPUT_CSV, load_rows  # noqa: E402

OUT_DIR = INPUT_CSV.parent
GAPFILL_RESOLUTION_CSV = INPUT_CSV.parent / "output" / "all_202601022" / "gapfill_resolution_202601022.csv"

# Priority order used to pick one "source" when a country has rows from more than one round in the same
# year (see this module's own docstring for why).
ROUND_PRIORITY = ["round1", "round2", "round3", "gapfill"]


def country_universe(input_csv: Path) -> set:
    """Every distinct country (normalize_country() + casefold) appearing anywhere in the merged file,
    regardless of hierarchy_id, year, or whether that row's own value/year happened to parse."""
    countries = pd.read_csv(input_csv, usecols=["country"], dtype=str)["country"]
    norm = countries.dropna().map(lambda c: core.normalize_country(str(c).strip()).casefold())
    return set(norm)


def observed_country_years(input_csv: Path) -> set:
    """(country_key, year) pairs where a real Round 1/2/3 report exists (source_round != "gapfill"),
    using that report's own last_actual_year -- independent of hierarchy_id, i.e. of which field, if
    any, was actually extracted from it."""
    df = pd.read_csv(input_csv, usecols=["country", "last_actual_year", "source_round"], dtype=str)
    df = df[df["source_round"] != "gapfill"].copy()
    df["country_key"] = df["country"].map(lambda c: core.normalize_country(str(c).strip()).casefold())

    def _y1(label: str) -> float:
        kind, _y0, y1, _note = core.parse_year_label(label)
        return float(y1) if kind != "invalid" else float("nan")

    df["obs_year"] = df["last_actual_year"].fillna("").str.strip().map(_y1)
    df = df.dropna(subset=["obs_year"])
    return set(zip(df["country_key"], df["obs_year"].astype(int)))


def gap_fill_status_map(resolution_csv: Path) -> dict:
    """(country_key, gap_year) -> final_status, from Gap Fill's own gapfill_resolution_<STAMP>.csv --
    the authoritative list of every (country, year) Step 1 of Gap Fill ever judged to be a gap."""
    res = pd.read_csv(resolution_csv, dtype=str)
    res["country_key"] = res["country"].map(lambda c: core.normalize_country(str(c).strip()).casefold())
    res["gap_year"] = res["gap_year"].astype(int)
    return dict(zip(zip(res["country_key"], res["gap_year"]), res["final_status"]))


def pick_source(rounds_present: set) -> str:
    for r in ROUND_PRIORITY:
        if r in rounds_present:
            return r
    return "unknown"  # defensive: should not happen if source_round is always one of ROUND_PRIORITY


def breakdown(
    df_field: pd.DataFrame,
    all_countries: set,
    observed: set | None = None,
    gap_status: dict | None = None,
) -> pd.DataFrame:
    total_countries = len(all_countries)
    # A year can have zero available rows for this field yet still be worth a row (e.g. for Level 2b
    # diagnostics), so the panel's year range comes from the union of every source, not just df_field's
    # own groupby() keys, which would silently skip a field-empty year entirely.
    years_seen = set(df_field["effective_year"])
    if observed:
        years_seen |= {y for _, y in observed}
    if gap_status:
        years_seen |= {y for _, y in gap_status}
    by_year = {int(y): g for y, g in df_field.groupby("effective_year")}

    rows = []
    for year in range(min(years_seen), max(years_seen) + 1) if years_seen else []:
        at_year = by_year.get(year)
        sources = (
            at_year.groupby("country_key")["source_round"].agg(lambda s: pick_source(set(s)))
            if at_year is not None else pd.Series(dtype=object)
        )
        counts = sources.value_counts()
        n_available = len(sources)
        row = {
            "year": year, "total_countries": total_countries, "n_available": n_available,
            "n_unavailable": total_countries - n_available,
            "n_round1": int(counts.get("round1", 0)), "n_round2": int(counts.get("round2", 0)),
            "n_round3_human_review": int(counts.get("round3", 0)), "n_gapfill": int(counts.get("gapfill", 0)),
        }
        if observed is not None and gap_status is not None:
            bucket = Counter()
            for key in all_countries - set(sources.index):
                status = gap_status.get((key, year))
                if status is None:
                    bucket["report_exists_field_missing" if (key, year) in observed else "not_gap_candidate"] += 1
                elif status in core.RESOLVED:
                    bucket["gapfill_resolved_but_field_missing"] += 1
                else:
                    bucket[status] += 1
            row.update({
                "n_unavail_not_gap_candidate": bucket["not_gap_candidate"],
                "n_unavail_report_exists_field_missing": bucket["report_exists_field_missing"],
                "n_unavail_gapfill_unresolved": bucket["unresolved"],
                "n_unavail_gapfill_no_candidate_report": bucket["unresolved_no_candidate_reports"],
                "n_unavail_gapfill_pending_api_error": bucket["pending_api_error"],
                "n_unavail_gapfill_resolved_but_field_missing": bucket["gapfill_resolved_but_field_missing"],
            })
        rows.append(row)
    return pd.DataFrame(rows).sort_values("year")


def main(input_csv: Path = INPUT_CSV, out_dir: Path = OUT_DIR, resolution_csv: Path = GAPFILL_RESOLUTION_CSV) -> None:
    all_countries = country_universe(input_csv)
    print(f"Total country universe (any hierarchy_id, any year): {len(all_countries)}")

    observed = gap_status = None
    if resolution_csv.exists():
        observed = observed_country_years(input_csv)
        gap_status = gap_fill_status_map(resolution_csv)
        print(f"Level 2b enabled: {len(gap_status)} gap-fill target(s) read from {resolution_csv}")
    else:
        print(f"Level 2b skipped: {resolution_csv} not found (copy the matching gapfill_resolution_<STAMP>.csv here)")

    out_dir.mkdir(parents=True, exist_ok=True)
    for hid, name in FIELDS.items():
        df_field = load_rows(input_csv, {hid})
        table = breakdown(df_field, all_countries, observed, gap_status)
        p = out_dir / f"panel_source_breakdown_{name}.csv"
        table.to_csv(p, index=False, encoding="utf-8-sig")
        print(f"{name}: {len(table)} year(s) -> {p}")


if __name__ == "__main__":
    main()
