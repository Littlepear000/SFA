"""
5b -- Countries that report other identified flows (h5) = 0 for many consecutive years
    Run by hand | no API, no network | same panel and country classification as 5a_h5_by_income_group.py

What it does
    1. Takes the 5a country-year panel (one value per country and year; Round 1 > 2 > 3 > Gap fill) and the
       5a classification (name -> IFS code -> Dummy file: income group, region and the other dummies).
    2. For every country, finds its runs of consecutive years in which the reported value is 0
       (|value| <= ZERO_TOL). By default a year with no reported value BREAKS the run; set
       ALLOW_MISSING_YEARS = True to let a run continue across missing years (they then do not count
       towards the run's length -- the length is always the number of years actually reported as 0).
    3. Lists every country with at least one run of MIN_RUN_YEARS or more (default 10), sorted by
       SORT_BY (default: income group in GROUP_ORDER, then region, then country name).

Output -- sheets in the same workbook as 5a (only the "5b_" sheets are replaced):
    5b_notes                settings of this run
    5b_zero_<N>y            one row per country with a run >= N years: income group, region, longest run
                            (length, first and last year), how many such runs, years reported / reported as
                            0 / non-zero, and the extra Dummy columns in EXTRA_DUMMIES
    5b_zero_<N>y_runs       one row per run >= N years
    5b_zero_<N>y_by_group   per income group: countries in the panel, countries listed, share
    5b_longest_run_all      every country's longest zero run (to see how the list changes with N)
    Changing MIN_RUN_YEARS writes new sheets with the new N and keeps sheets of earlier N; set
    CLEAR_OLD_N = True to remove them.

Usage
    python 5b_h5_zero_streaks.py
    python 5b_h5_zero_streaks.py --min-run 8
    or edit the settings below and run the file from a console.
"""
from __future__ import annotations

import argparse
import importlib.util
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
if not (HERE / "core.py").exists() and (HERE / "code" / "core.py").exists():
    HERE = HERE / "code"

# 5a holds the panel, the classification and the Excel writer: load it so both analyses always agree
_spec = importlib.util.spec_from_file_location("a5", HERE / "5a_h5_by_income_group.py")
a5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(a5)

# ================================================================= settings
MIN_RUN_YEARS = 10                 # list countries with at least this many consecutive years reported as 0
ZERO_TOL = 0.0                     # |value| <= ZERO_TOL counts as 0 (e.g. 0.05 to treat 0.0x as 0)
ALLOW_MISSING_YEARS = False        # False: a year with no value breaks the run; True: missing years are skipped
YEARS = (2001, 2025)               # years searched (2025 included here: a run can end in the latest year)

HIERARCHY_ID = a5.HIERARCHY_ID     # "5" by default, set in 5a
GROUP_COL = a5.GROUP_COL           # "income"
GROUP_ORDER = ["AE", "EM", "LIC"]  # sort order of the income groups; anything else / unclassified goes last
SORT_BY = [GROUP_COL, "region", "country"]   # sort keys of the list, in order
EXTRA_DUMMIES = ["prgt", "fcs", "oil_exporter", "lac", "ssa", "mena", "em_asia", "eu", "ea", "g20_adv", "g20_em"]

OUT_XLSX = a5.OUT_XLSX             # same workbook as 5a
CLEAR_OLD_N = False                # True: drop 5b sheets written earlier for another MIN_RUN_YEARS
# ===========================================================================


def zero_runs(years: np.ndarray, values: np.ndarray, allow_missing: bool) -> list[tuple[int, int, int]]:
    """[(first year, last year, number of years reported as 0)] for every run of zeros in one country."""
    runs, start, prev, length = [], None, None, 0
    for y, v in zip(years, values):
        is_zero = abs(v) <= ZERO_TOL
        contiguous = prev is not None and (allow_missing or y == prev + 1)
        if is_zero and start is not None and contiguous:
            length += 1
        else:
            if start is not None:
                runs.append((start, prev, length))
                start, length = None, 0
            if is_zero:
                start, length = y, 1
        prev = y
    if start is not None:
        runs.append((start, prev, length))
    return runs


def main(min_run: int = MIN_RUN_YEARS) -> None:
    panel, issues = a5.panel_with_groups(a5.FINAL_CSV, HIERARCHY_ID, YEARS)
    panel = panel.sort_values(["country", "year"])
    info_cols = ["country", "ifscode", "isocode", GROUP_COL, "region"] + [c for c in EXTRA_DUMMIES if c in panel]
    info = panel.drop_duplicates("country").set_index("country")[info_cols[1:]]

    rows_runs, rows_country = [], []
    for country, g in panel.groupby("country"):
        runs = zero_runs(g["year"].to_numpy(), g["value"].to_numpy(), ALLOW_MISSING_YEARS)
        longest = max(runs, key=lambda r: (r[2], r[1]), default=(None, None, 0))
        long_runs = [r for r in runs if r[2] >= min_run]
        for r in long_runs:
            rows_runs.append({"country": country, "run_start": r[0], "run_end": r[1], "run_years_zero": r[2]})
        n_zero = int((g["value"].abs() <= ZERO_TOL).sum())
        rows_country.append({
            "country": country,
            "longest_zero_run": longest[2], "longest_run_start": longest[0], "longest_run_end": longest[1],
            f"n_runs_ge_{min_run}y": len(long_runs),
            "first_year": int(g["year"].min()), "last_year": int(g["year"].max()),
            "years_reported": len(g), "years_zero": n_zero, "years_nonzero": len(g) - n_zero,
            "share_zero": n_zero / len(g),
            "zero_in_latest_year": bool(abs(g["value"].iloc[-1]) <= ZERO_TOL),
            "nonzero_years": ", ".join(str(y) for y, v in zip(g["year"], g["value"]) if abs(v) > ZERO_TOL),
        })
    allc = pd.DataFrame(rows_country).merge(info, left_on="country", right_index=True, how="left")
    front = ["country", "ifscode", "isocode", GROUP_COL, "region"]
    allc = allc[front + [c for c in allc.columns if c not in front]]

    def sort(df: pd.DataFrame) -> pd.DataFrame:
        key = df.copy()
        rank = {g: i for i, g in enumerate(GROUP_ORDER)}
        key["_g"] = key[GROUP_COL].map(rank).fillna(len(rank))
        by = ["_g" if c == GROUP_COL else c for c in SORT_BY]
        return df.loc[key.sort_values(by, na_position="last", kind="stable").index].reset_index(drop=True)

    listed = sort(allc[allc[f"n_runs_ge_{min_run}y"] > 0])
    runs = pd.DataFrame(rows_runs, columns=["country", "run_start", "run_end", "run_years_zero"])
    runs = runs.merge(info[[c for c in ["ifscode", GROUP_COL, "region"] if c in info]],
                      left_on="country", right_index=True, how="left")
    runs = sort(runs)[["country", GROUP_COL, "region", "ifscode", "run_start", "run_end", "run_years_zero"]]

    by_group = allc.assign(listed=allc[f"n_runs_ge_{min_run}y"] > 0).groupby(
        allc[GROUP_COL].fillna("unclassified")).agg(countries_in_panel=("country", "size"),
                                                    countries_listed=("listed", "sum"))
    by_group = by_group.reindex([g for g in GROUP_ORDER if g in by_group.index] +
                                [g for g in by_group.index if g not in GROUP_ORDER])
    by_group.loc["Total"] = by_group.sum()
    by_group["share_listed"] = by_group["countries_listed"] / by_group["countries_in_panel"]
    by_group = by_group.reset_index().rename(columns={GROUP_COL: "group"})

    notes = [
        f"5b -- countries reporting h{HIERARCHY_ID} = 0 for at least {min_run} consecutive years",
        f"Run: {datetime.now():%Y-%m-%d %H:%M}",
        f"Final CSV: {a5.FINAL_CSV}; years searched {YEARS[0]}-{YEARS[1]}; same country-year panel as 5a "
        "(effective year; Round 1 > Round 2 > Round 3 > Gap fill).",
        f"Zero = |value| <= {ZERO_TOL}. Missing years {'are skipped (a run continues across them)' if ALLOW_MISSING_YEARS else 'break a run'}; "
        "run length = number of years actually reported as 0.",
        f"Sorted by {SORT_BY} with {GROUP_COL} in the order {GROUP_ORDER}.",
        f"Classification: {Path(a5.CODES_XLSX).name} -> {Path(a5.DUMMY_XLSX).name}. Not classified: "
        + (", ".join(issues['country']) if len(issues) else "none") + ".",
        f"Result: {len(listed)} of {len(allc)} countries have a zero run of {min_run}+ years.",
    ]
    tag = f"5b_zero_{min_run}y"
    sheets = {
        "5b_notes": notes,
        tag: listed if len(listed) else pd.DataFrame({"country": ["(none)"]}),
        f"{tag}_runs": runs if len(runs) else pd.DataFrame({"country": ["(none)"]}),
        f"{tag}_by_group": by_group,
        "5b_longest_run_all": sort(allc).sort_values("longest_zero_run", ascending=False, kind="stable"),
    }
    a5.write_sheets(OUT_XLSX, sheets, prefix="5b_" if CLEAR_OLD_N else None)
    print(f"{len(listed)} of {len(allc)} countries have h{HIERARCHY_ID} = 0 for {min_run}+ consecutive years")
    print(by_group.to_string(index=False))
    print(f"Wrote sheets {list(sheets)} to {OUT_XLSX}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--min-run", type=int, default=MIN_RUN_YEARS, help="minimum consecutive years reported as 0")
    main(ap.parse_args().min_run)
