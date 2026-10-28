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

Output (written under OUT_DIR: availability/ and unavailable_detail/)
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

GAPFILL_OUTPUT = HERE.parent / "output" / "gapfill" / "output"
# Every Gap Fill run that contributed rows to INPUT_CSV, oldest first, as {STAMP: its gapfill_resolution CSV}.
# 202601022: gaps BETWEEN a country's own first and last observed years. 202601028: the rest of the
# 2001-2025 panel (3a FULL_RANGE), incremental -- the two runs never target the same (country, year).
GAPFILL_RESOLUTION_CSVS = {
    "202601022": GAPFILL_OUTPUT / "all_202601022" / "gapfill_resolution_202601022.csv",
    "202601028": GAPFILL_OUTPUT / "all_202601028" / "gapfill_resolution_202601028.csv",
}
OUT_DIR = HERE.parent / "output" / "gapfill" / "summary_stats" / "20261028_gapfill_run1_run2"
# The panel the project is building: every country, every year in this range. None = every year seen.
PANEL_YEARS = (2001, 2025)

# Priority order used to pick one "source" when a country has rows from more than one round in the same
# year (see this module's own docstring for why). Gap-fill rows are further split by run, oldest first.
ROUND_PRIORITY = ["round1", "round2", "round3", "gapfill"]

GAP_BUCKETS = {  # Level 2b bucket -> output column
    "not_gap_candidate": "n_unavail_not_gap_candidate",
    "report_exists_field_missing": "n_unavail_report_exists_field_missing",
    "unresolved": "n_unavail_gapfill_unresolved",
    "unresolved_no_candidate_reports": "n_unavail_gapfill_no_candidate_report",
    "pending_api_error": "n_unavail_gapfill_pending_api_error",
    "gapfill_resolved_but_field_missing": "n_unavail_gapfill_resolved_but_field_missing",
}


STATUS_RANK = {"resolved": 0, "resolved_with_warning": 0, "unresolved": 1, "pending_api_error": 2,
               "unresolved_no_candidate_reports": 3}


def _key(c) -> str:
    return core.normalize_country(str(c).strip()).casefold()


def country_universe(input_csv: Path) -> set:
    """Every distinct country (normalize_country() + casefold) appearing anywhere in the merged file,
    regardless of hierarchy_id, year, or whether that row's own value/year happened to parse."""
    countries = pd.read_csv(input_csv, usecols=["country"], dtype=str)["country"]
    return set(countries.dropna().map(_key))


def observed_country_years(input_csv: Path) -> set:
    """(country_key, year) pairs where a real Round 1/2/3 report exists (source_round != "gapfill"),
    using that report's own last_actual_year -- independent of hierarchy_id, i.e. of which field, if
    any, was actually extracted from it."""
    df = pd.read_csv(input_csv, usecols=["country", "last_actual_year", "source_round"], dtype=str)
    df = df[df["source_round"] != "gapfill"].copy()
    df["country_key"] = df["country"].map(_key)

    def _y1(label: str) -> float:
        kind, _y0, y1, _note = core.parse_year_label(label)
        return float(y1) if kind != "invalid" else float("nan")

    df["obs_year"] = df["last_actual_year"].fillna("").str.strip().map(_y1)
    df = df.dropna(subset=["obs_year"])
    return set(zip(df["country_key"], df["obs_year"].astype(int)))


def _as_run_dict(resolution) -> dict:
    if isinstance(resolution, dict):
        return dict(resolution)
    if isinstance(resolution, (list, tuple)):
        return {str(i): p for i, p in enumerate(resolution)}
    return {"": resolution}


def load_resolutions(resolution) -> pd.DataFrame:
    """Every gapfill_resolution row of every run, with country_key, gap_year (int) and gapfill_run. A
    (country, year) listed by more than one run keeps the OLDEST run's row (runs are passed oldest first)."""
    frames = []
    for stamp, path in _as_run_dict(resolution).items():
        if not Path(path).exists():
            print(f"  WARNING: gap-fill resolution not found, skipped: {path}")
            continue
        res = pd.read_csv(path, dtype=str)
        res["gapfill_run"] = stamp
        frames.append(res)
    if not frames:
        return pd.DataFrame(columns=["country_key", "gap_year", "final_status", "gapfill_run"])
    res = pd.concat(frames, ignore_index=True)
    res["country_key"] = res["country"].map(_key)
    res["gap_year"] = res["gap_year"].astype(int)
    # The same (country, year) can be listed twice -- by two runs, or twice in one run when 3a saw two
    # spellings of one country (e.g. "St.Vincent" / "St. Vincent"). Keep the most informative row: a
    # resolved one first, then by status, then the oldest run.
    res["_rank"] = res["final_status"].map(STATUS_RANK).fillna(len(STATUS_RANK))
    res["_run"] = res["gapfill_run"].map({r: i for i, r in enumerate(_as_run_dict(resolution))})
    res = res.sort_values(["_rank", "_run"], kind="stable")
    dup = res.duplicated(["country_key", "gap_year"], keep="first")
    if dup.any():
        print(f"  NOTE: {int(dup.sum())} (country, year) gap-fill target(s) listed more than once; one row kept for each")
    return res[~dup].drop(columns=["_rank", "_run"]).sort_index()


def gap_fill_status_map(resolution) -> dict:
    """(country_key, gap_year) -> final_status, over one gapfill_resolution CSV or several ({STAMP: path},
    oldest first) -- the authoritative list of every (country, year) Gap Fill ever judged to be a gap."""
    res = load_resolutions(resolution)
    return dict(zip(zip(res["country_key"], res["gap_year"]), res["final_status"]))


def gap_fill_run_map(resolution) -> dict:
    """(country_key, gap_year) -> the STAMP of the Gap Fill run that targeted it."""
    res = load_resolutions(resolution)
    return dict(zip(zip(res["country_key"], res["gap_year"]), res["gapfill_run"]))


def _source_tag(source_round, gapfill_run) -> str:
    if source_round == "gapfill" and isinstance(gapfill_run, str) and gapfill_run:
        return f"gapfill:{gapfill_run}"
    return source_round


def pick_source(rounds_present: set) -> str:
    """One source per country-year: round1 > round2 > round3 > gapfill (oldest run first)."""
    for r in ROUND_PRIORITY:
        if r == "gapfill":
            runs = sorted(t for t in rounds_present if isinstance(t, str) and t.startswith("gapfill"))
            if runs:
                return runs[0]
        elif r in rounds_present:
            return r
    return "unknown"  # defensive: should not happen if source_round is always one of ROUND_PRIORITY


def _unavailable_reason(key, year, observed, gap_status) -> str:
    status = gap_status.get((key, year))
    if status is None:
        return "report_exists_field_missing" if (key, year) in observed else "not_gap_candidate"
    if status in core.RESOLVED:
        return "gapfill_resolved_but_field_missing"
    return status


def _year_range(df_field, observed, gap_status, years):
    if years is not None:
        return list(range(years[0], years[1] + 1))
    # A year can have zero available rows for this field yet still be worth a row (e.g. for Level 2b
    # diagnostics), so the panel's year range comes from the union of every source.
    seen = set(df_field["effective_year"])
    if observed:
        seen |= {y for _, y in observed}
    if gap_status:
        seen |= {y for _, y in gap_status}
    return list(range(min(seen), max(seen) + 1)) if seen else []


def _sources_by_year(df_field: pd.DataFrame) -> dict:
    df = df_field.copy()
    run_col = df["gapfill_run"] if "gapfill_run" in df.columns else pd.Series(None, index=df.index)
    df["source_tag"] = [_source_tag(r, g) for r, g in zip(df["source_round"], run_col)]
    return {
        int(y): g.groupby("country_key")["source_tag"].agg(lambda s: pick_source(set(s)))
        for y, g in df.groupby("effective_year")
    }


def breakdown(
    df_field: pd.DataFrame,
    all_countries: set,
    observed: set | None = None,
    gap_status: dict | None = None,
    gap_run: dict | None = None,
    years: tuple | None = None,
) -> pd.DataFrame:
    total_countries = len(all_countries)
    by_year = _sources_by_year(df_field)
    runs = sorted({t.split(":", 1)[1] for s in by_year.values() for t in s if t.startswith("gapfill:")})
    target_runs = sorted(set(gap_run.values())) if gap_run else []

    rows = []
    for year in _year_range(df_field, observed, gap_status, years):
        sources = by_year.get(year, pd.Series(dtype=object))
        counts = sources.value_counts()
        n_gapfill = int(sum(v for k, v in counts.items() if str(k).startswith("gapfill")))
        row = {
            "year": year, "total_countries": total_countries, "n_available": len(sources),
            "n_unavailable": total_countries - len(sources),
            "n_round1": int(counts.get("round1", 0)), "n_round2": int(counts.get("round2", 0)),
            "n_round3_human_review": int(counts.get("round3", 0)), "n_gapfill": n_gapfill,
        }
        for run in runs:  # n_gapfill split by run (these sum to n_gapfill)
            row[f"n_gapfill_run_{run}"] = int(counts.get(f"gapfill:{run}", 0))
        if observed is not None and gap_status is not None:
            bucket, by_run = Counter(), Counter()
            for key in all_countries - set(sources.index):
                bucket[_unavailable_reason(key, year, observed, gap_status)] += 1
                if gap_run and (key, year) in gap_run:
                    by_run[gap_run[(key, year)]] += 1
            row.update({col: bucket[b] for b, col in GAP_BUCKETS.items()})
            for run in target_runs:  # unavailable gap-fill targets, by the run that targeted them
                row[f"n_unavail_gap_target_run_{run}"] = by_run[run]
        rows.append(row)
    return pd.DataFrame(rows).sort_values("year") if rows else pd.DataFrame(rows)


def unavailable_detail(field: str, df_field: pd.DataFrame, all_countries: set, observed: set,
                       resolutions: pd.DataFrame, label_by_key: dict, years: tuple | None = None) -> pd.DataFrame:
    """One row per unavailable (field, country, year), with why -- the list behind the Level 2b counts."""
    gap_status = dict(zip(zip(resolutions["country_key"], resolutions["gap_year"]), resolutions["final_status"]))
    res_idx = resolutions.set_index(["country_key", "gap_year"])
    by_year = _sources_by_year(df_field)
    rows = []
    for year in _year_range(df_field, observed, gap_status, years):
        available = set(by_year.get(year, pd.Series(dtype=object)).index)
        for key in sorted(all_countries - available):
            r = res_idx.loc[(key, year)] if (key, year) in res_idx.index else None
            rows.append({
                "field": field, "year": year, "country": label_by_key.get(key, key),
                "reason": _unavailable_reason(key, year, observed, gap_status),
                "gapfill_run": None if r is None else r["gapfill_run"],
                "gap_id": None if r is None else r.get("gap_id"),
                "n_attempts": None if r is None else r.get("n_attempts"),
                "candidate_reports": None if r is None else r.get("candidate_reports"),
                "last_failure_status": None if r is None else r.get("last_failure_status"),
                "last_failure_detail": None if r is None else r.get("last_failure_detail"),
            })
    return pd.DataFrame(rows)


def main(input_csv: Path = INPUT_CSV, out_dir: Path = OUT_DIR, resolution_csvs=GAPFILL_RESOLUTION_CSVS,
         years: tuple | None = PANEL_YEARS) -> None:
    all_countries = country_universe(input_csv)
    print(f"Total country universe (any hierarchy_id, any year): {len(all_countries)}")

    resolutions = load_resolutions(resolution_csvs)
    observed = gap_status = gap_run = None
    if len(resolutions):
        observed = observed_country_years(input_csv)
        gap_status = dict(zip(zip(resolutions["country_key"], resolutions["gap_year"]), resolutions["final_status"]))
        gap_run = dict(zip(zip(resolutions["country_key"], resolutions["gap_year"]), resolutions["gapfill_run"]))
        print(f"Level 2b enabled: {len(gap_status)} gap-fill target(s) from run(s) {sorted(set(gap_run.values()))}")
    else:
        print("Level 2b skipped: no gapfill_resolution CSV found")

    all_rows = load_rows(input_csv, ALL_HIERARCHIES)
    label_by_key = all_rows.groupby("country_key")["country_label"].first().to_dict()

    avail_dir, detail_dir = out_dir / "availability", out_dir / "unavailable_detail"
    avail_dir.mkdir(parents=True, exist_ok=True)
    for hid, name in FIELDS.items():
        df_field = load_rows(input_csv, {hid})
        if years is not None:
            outside = df_field[~df_field["effective_year"].between(*years)]
            if len(outside):
                print(f"  {name}: {outside['country_key'].nunique()} country(ies) / {len(outside)} row(s) "
                      f"outside {years[0]}-{years[1]} are not in the tables")
        table = breakdown(df_field, all_countries, observed, gap_status, gap_run, years)
        p = avail_dir / f"panel_source_breakdown_{name}.csv"
        table.to_csv(p, index=False, encoding="utf-8-sig")
        print(f"{name}: {len(table)} year(s) -> {p}")
        if observed is not None:
            detail_dir.mkdir(parents=True, exist_ok=True)
            detail = unavailable_detail(name, df_field, all_countries, observed, resolutions, label_by_key, years)
            dp = detail_dir / f"unavailable_country_years_{name}.csv"
            detail.to_csv(dp, index=False, encoding="utf-8-sig")
            print(f"{name}: {len(detail)} unavailable country-year(s) -> {dp}")


if __name__ == "__main__":
    main()
