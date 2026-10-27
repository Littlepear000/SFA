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
    NOT YET IMPLEMENTED HERE -- it needs two files this merged CSV does not carry on its own:
    gap_years_<STAMP>.csv (which (country, year) pairs Step 1 of Gap Fill identified as a gap at all --
    a year outside a country's observed bracket is never identified as a gap in the first place, so it
    is not the same as "Gap Fill tried and failed") and gapfill_resolution_<STAMP>.csv (the final_status
    / failure reason for every gap year Gap Fill did attempt). Copy the latest run's versions of both
    (same STAMP as the merged CSV's own Gap Fill rows) onto this machine and point GAP_YEARS_CSV /
    GAPFILL_RESOLUTION_CSV at them to add this level.

Output (written next to the input CSV by default)
    panel_source_breakdown_residual.csv              one row per year: total_countries, n_available,
                                                      n_unavailable, n_round1, n_round2, n_round3,
                                                      n_gapfill (the four n_round*/n_gapfill columns sum
                                                      to n_available)
    panel_source_breakdown_other_identified_flows.csv   the same, for hierarchy_id "5"

Usage
    python gapfill_panel_source_breakdown.py
    or edit INPUT_CSV / OUT_DIR at the top of the file and run (also works from a console).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(HERE))
import gapfill_lib_core as core  # noqa: E402
from gapfill_panel_coverage_report import ALL_HIERARCHIES, FIELDS, INPUT_CSV, load_rows  # noqa: E402

OUT_DIR = INPUT_CSV.parent

# Priority order used to pick one "source" when a country has rows from more than one round in the same
# year (see this module's own docstring for why).
ROUND_PRIORITY = ["round1", "round2", "round3", "gapfill"]


def country_universe(input_csv: Path) -> set:
    """Every distinct country (normalize_country() + casefold) appearing anywhere in the merged file,
    regardless of hierarchy_id, year, or whether that row's own value/year happened to parse."""
    countries = pd.read_csv(input_csv, usecols=["country"], dtype=str)["country"]
    norm = countries.dropna().map(lambda c: core.normalize_country(str(c).strip()).casefold())
    return set(norm)


def pick_source(rounds_present: set) -> str:
    for r in ROUND_PRIORITY:
        if r in rounds_present:
            return r
    return "unknown"  # defensive: should not happen if source_round is always one of ROUND_PRIORITY


def breakdown(df_field: pd.DataFrame, total_countries: int) -> pd.DataFrame:
    rows = []
    for year, at_year in df_field.groupby("effective_year"):
        sources = at_year.groupby("country_key")["source_round"].agg(lambda s: pick_source(set(s)))
        counts = sources.value_counts()
        n_available = len(sources)
        rows.append({
            "year": int(year),
            "total_countries": total_countries,
            "n_available": n_available,
            "n_unavailable": total_countries - n_available,
            "n_round1": int(counts.get("round1", 0)),
            "n_round2": int(counts.get("round2", 0)),
            "n_round3_human_review": int(counts.get("round3", 0)),
            "n_gapfill": int(counts.get("gapfill", 0)),
        })
    return pd.DataFrame(rows).sort_values("year")


def main(input_csv: Path = INPUT_CSV, out_dir: Path = OUT_DIR) -> None:
    total_countries = len(country_universe(input_csv))
    print(f"Total country universe (any hierarchy_id, any year): {total_countries}")

    out_dir.mkdir(parents=True, exist_ok=True)
    for hid, name in FIELDS.items():
        df_field = load_rows(input_csv, {hid})
        table = breakdown(df_field, total_countries)
        p = out_dir / f"panel_source_breakdown_{name}.csv"
        table.to_csv(p, index=False, encoding="utf-8-sig")
        print(f"{name}: {len(table)} year(s) -> {p}")


if __name__ == "__main__":
    main()
