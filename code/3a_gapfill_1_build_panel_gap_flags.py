"""
[3a_gapfill_1] Find gap years and build the panel skeleton.
    Step 1 | run by hand | does not read PDFs, does not call the API

Purpose
    From a compiled CSV (Step 1's extraction output, long format: one row = one
    decomposition line item from one report), take one observation per report
    (country + the value for its last_actual_year), assemble a "country x year"
    panel skeleton, and flag the years "missing in the middle" of each country's
    span of observed years, i.e. gap years.

Input (usually one CSV; can be more than one -- see below)
    INPUT_CSV at the top of the file, or --input on the command line (repeat --input to pass more than
    one). Once a batch's Round 1 + Round 2 + human review are all done and merged into one unified
    panel, that is what this should point at (same columns as a single round's compiled CSV, below);
    until then it can still point at one round's own compiled CSV, e.g.
    output/2016-2020/compiled_csv/dsa_decomposition_labels_2016-2020_sa.csv.

    Gaps at a batch's edge need the ADJACENT batch's data too: find_gap_years() only flags a year that
    is "missing in the middle" of a country's observed years, so e.g. a gap at 2020 is invisible from
    the 2016-2020 batch alone -- there is nothing in it to call "the middle" without the next real
    observation (e.g. 2022, from the 2021-2026 batch). Pass that next batch's compiled CSV too
    (INPUT_CSV as a list, or a second --input) whenever a gap could be sitting at the edge of the
    batch being checked; the two (or more) CSVs are concatenated before anything else runs, using the
    exact same (json_file, last_actual_year) dedup as a single CSV, so passing more than one is always
    safe even when a report happens to appear in both.

    Columns required: json_file, pdf_file_name, country, last_actual_year, level, top_category, value,
    hierarchy_id, parent_label, label_verbatim. That is enough to find gap years on its own -- a slimmer
    "final answer only" merged CSV (e.g. one that dropped every per-attempt audit column once Round
    1/2/3 + Human Review + Gap Fill were all folded together) works fine with just these.
    Columns used IF PRESENT, for extra diagnostics only, each degrading gracefully (not erroring) when
    absent from the input: table_found (missing -> every row assumed to have found its table; a row only
    exists in a slimmer merged file because its table WAS found), manual_review_required and
    actual_column_validation_status (missing -> year_uncertain stays False), confidence, framework,
    source_round (missing -> MAX_PLAUSIBLE_LAG's check applies to every row; see "A Gap Fill row is BY
    DESIGN..." in main()'s own code), column_header_audit_json (missing -> fill_status in gap_years.csv
    reads "preview_unavailable_no_audit_column" instead of a real preview -- Step 2/3 are unaffected,
    since they never read this column either; it only exists to flag a gap worth a second look before
    spending any API calls on it).

    Unique row key is (json_file, last_actual_year, hierarchy_id), not (json_file, hierarchy_id): once
    gap-fill's own output is folded back into this input, one real report can legitimately appear under
    two different last_actual_year values -- its own normal extraction, and a gap-fill row-group at an
    earlier year it was also used to source -- so json_file alone no longer identifies one observation.
    A gap-fill row's own year lives in a separate "year" column (last_actual_year is blank for it) --
    effective_year_label() coalesces the two wherever a row needs to be identified or grouped by year, so
    a previously gap-filled year reads as observed here, not as still missing.

    FULL_RANGE / EXCLUDE_IDENTIFIED_CSV (see main()'s own docstring) switch the whole file from "gaps
    sandwiched inside each country's own observed span" to "every missing year in a fixed panel-wide
    range (e.g. 2001 onward), for every country with at least one observation" -- the panel-data framing,
    where ANY missing cell counts, not only ones between two of that country's own reports. Pair it with
    pointing INPUT_CSV at the CURRENT merged panel (including any Gap Fill output already folded in) and
    EXCLUDE_IDENTIFIED_CSV at the prior, narrower run's own gap list, to get exactly the new gaps that
    narrower definition could never have found (years before a country's first report, or after its most
    recent one) without re-identifying (and so re-attempting) anything already run once.

Output (written by default to <batch folder>/gap_year_check/, filenames suffixed _<STAMP>)
    panel_structure_country_year   country x year skeleton. status = observed (has data) or GAP (missing)
    gap_years                      one row per gap year: the bounding reports, cause, whether an actual
                                   column for that year can be found in another report, preferred source
                                   report                                          -> input to Step 2
    report_inventory               how each report was used (valid observation / superseded by a later
                                   report / no table / year unusable ...)          -> input to Step 2
    coverage_matrix_country_year   country x year matrix: O = has data, O? = has data but year needs manual
                                   review, GAP = missing
    panel_children_long            child-item detail (level 1-2) for the valid observations
    summary_stats_<STAMP>.json     summary numbers

Core steps
    1. Read the CSV, keep one report-level row per report; country name and report date come from
       pdf_file_name (country names are normalized to one spelling).
    2. Parse last_actual_year: a fiscal-year label like 2015/16 takes the fiscal year's end year (2016);
       a multi-year range (e.g. 2009-2014) is invalid.
    3. Classify each report's usage:
         valid observation / superseded by a later report for the same country-year (the latest of
         several reports for the same year is kept) / no DSA table found / has a table but the year
         could not be parsed / year implausible (report year - that year >= 4, or negative, treated as
         a misread and kept out of the panel) / multi-country document.
    4. gap year = a year with no report at all, between a country's first and last observed years
       (the first and last years themselves don't count).
    5. Tag each gap with a cause: adjacent reports jump straight over the year / there is a report in
       between but it has no table / there is a report in between but its year is unusable.
    6. Use each report's own column_header_audit_json (every year column in the table and its
       actual/estimate/projection status) to predict: in which report is that year a standalone
       actual/historical column (fillable), versus only an estimate / projection / merged-range column.
       This checks only the same T+2-then-T+3-then-T+4, latest-publication-date-first candidates Step 2/3 would
       actually try (gapfill_lib_core.build_candidates()) -- it is a preview of their result, not a
       separate, looser guess that could point at a different report.
    7. Write out the files above.

Usage
    python 3a_gapfill_1_build_panel_gap_flags.py --input <some CSV> [--out-dir <output folder>]
    or just edit INPUT_CSV at the top of the file and run (also works from an IPython / PyCharm console).
    STAMP is the version tag; it must match the STAMP used in Steps 2 and 3.
"""
from __future__ import annotations

import importlib
import json
import re
import sys
from pathlib import Path

import pandas as pd



def _here() -> Path:
    """Folder holding the gapfill scripts. Uses __file__ when the file is run
    normally; in an IPython / PyCharm console (no __file__) it looks for the
    folder that contains gapfill_lib_core.py, starting from the working folder."""
    try:
        return Path(__file__).resolve().parent
    except NameError:
        cwd = Path.cwd()
        for cand in (cwd, cwd / "code", cwd.parent / "code", cwd.parent):
            if (cand / "gapfill_lib_core.py").exists():
                return cand
        return cwd

HERE = _here()
BASE = HERE.parent if HERE.name == "code" else HERE

# ------------------------------------------------------------------ CONFIG
# INPUT_CSV = BASE / "output" / "2016-2020" / "compiled_csv" / "dsa_decomposition_labels_2016-2020_sa.csv"
# OUT_DIR = None  # None -> "gap_year_check" folder next to the CSV's batch folder
# STAMP = "20260920_v2"

# Panel-wide gap definition (see main()'s own docstring) -- leave both None for the original, narrower
# "missing in the middle of this country's own observed years" definition.
FULL_RANGE = None  # e.g. (2001, 2025): every missing year in this range counts as a gap, for every
                    # country with at least one observation anywhere
EXCLUDE_IDENTIFIED_CSV = None  # e.g. the prior (narrower) run's gap_years_<STAMP>.csv or
                                # gapfill_resolution_<STAMP>.csv -- drops any (country, gap_year) it
                                # already lists, so this run only writes the INCREMENTAL new gaps


def default_out_dir(input_csv: Path) -> Path:
    parent = Path(input_csv).resolve().parent
    base = parent.parent if parent.name == "compiled_csv" else parent
    return base / "gap_year_check"


TOP_CATEGORIES = [
    "change_in_debt", "identified_flows", "primary_balance",
    "automatic_debt_dynamics", "other_identified_flows", "residual",
]
ELIGIBLE = {"actual", "historical"}
# Report year minus last actual year is 1-2 in practice (0 for some fiscal-year
# reports). A gap of 4+ years (or a future year) is almost certainly a misread or a
# non-standard document, so it is kept out of the panel instead of creating false gaps.
MAX_PLAUSIBLE_LAG = 4
PRELIM_EST = {"preliminary", "estimate"}

# ------------------------------------------------ country names and year labels
# normalize_country(), parse_year_label() and build_candidates() live in gapfill_lib_core.py (same
# folder). build_candidates() is reused here (not a separate implementation) so Step 1's preview of
# "which report can fill this year" is an honest forecast of what Step 2/3 actually try (T+2 first,
# then T+3, latest publication date first) rather than a second, looser guess that can disagree with it.
sys.path.insert(0, str(HERE))
# A long-lived IPython/Spyder console keeps gapfill_lib_core cached in sys.modules across repeated runs
# of this script via 0_run_gapfill.py -- without this, a code change (e.g. a git pull) would not take
# effect until the console itself is restarted. Reload it in place before pulling names from it.
if "gapfill_lib_core" in sys.modules:
    importlib.reload(sys.modules["gapfill_lib_core"])
from gapfill_lib_core import normalize_country, parse_year_label, build_candidates  # noqa: E402

def to_float(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    s = str(x).strip().replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


# ------------------------------------------------------------------ loading
def effective_year_label(df: pd.DataFrame) -> pd.Series:
    """last_actual_year if present, else "year" -- the merged panel (Round 1/2/3 + Gap Fill) keeps both
    columns but never unified them: "year" is populated only for source_round == "gapfill" rows, blank
    for Round 1/2/3 rows, which carry their year in "last_actual_year" instead (and a CSV from before any
    Gap Fill output was folded in may not have a "year" column at all -- .get() with a blank default
    covers that). Used everywhere a row needs to be identified or grouped by "which year it represents",
    so a previously gap-filled year counts as observed instead of looking like it is still missing."""
    lay = df["last_actual_year"].fillna("").astype(str).str.strip()
    year = df.get("year", pd.Series("", index=df.index)).fillna("").astype(str).str.strip()
    return lay.where(lay != "", year)


def build_report_table(df: pd.DataFrame) -> pd.DataFrame:
    # Unique key is (json_file, effective_year_label), not json_file alone: once gap-fill output is
    # folded back into this input, the same real report can legitimately carry two row-groups -- its own
    # normal extraction at its own last_actual_year, and a gap-fill row-group at an earlier year it also
    # supplied as a T+2/T+3/T+4 source -- so json_file alone no longer identifies one observation.
    df = df.copy()
    df["effective_year_label"] = effective_year_label(df)
    r = df.sort_values(["json_file", "effective_year_label"]).drop_duplicates(["json_file", "effective_year_label"], keep="first").copy()
    m = r["pdf_file_name"].str.extract(r"^(?P<prefix>.*?)_(?P<date>\d{4}-\d{2}-\d{2})")
    r["country_raw"] = m["prefix"]
    r["report_date"] = pd.to_datetime(m["date"])
    r["country"] = r["country_raw"].apply(normalize_country)
    parsed = r["effective_year_label"].apply(parse_year_label)
    r["year_kind"] = parsed.apply(lambda t: t[0])
    r["obs_year"] = parsed.apply(lambda t: t[1])
    r["year_parse_note"] = parsed.apply(lambda t: t[3])
    # table_found / manual_review_required / actual_column_validation_status are per-attempt audit columns
    # from the long-form extraction output; a slimmer "final answer only" merged CSV (e.g. one with just
    # json_file, country, last_actual_year, hierarchy_id, value, source_round, ...) may not carry them at
    # all -- every row that made it into that kind of file already represents a successfully extracted,
    # accepted value, so table_found defaults to TRUE and year_uncertain to False when they are absent.
    r["table_found_bool"] = r.get("table_found", pd.Series("TRUE", index=r.index)).fillna("TRUE").str.upper().eq("TRUE")
    r["year_uncertain"] = (
        r.get("manual_review_required", pd.Series("", index=r.index)).eq("Yes")
        | r.get("actual_column_validation_status", pd.Series("", index=r.index)).eq("manual_review")
    )
    r["year_after_report_year"] = r.apply(
        lambda x: bool(pd.notna(x["obs_year"]) and pd.notna(x["report_date"]) and x["obs_year"] > x["report_date"].year),
        axis=1,
    )
    return r.reset_index(drop=True)


def top_level_values(df: pd.DataFrame) -> pd.DataFrame:
    top = df[df["level"].astype(str).isin(["0", "0.0"]) & df["top_category"].isin(TOP_CATEGORIES)].copy()
    top["value_num"] = top["value"].apply(to_float)
    top["effective_year_label"] = effective_year_label(top)
    # Keyed like build_report_table(): (json_file, effective_year_label), so a report that supplies two
    # different years (its own, plus one it filled via gap-fill) doesn't have its two years' top-level
    # values collapsed into a single json_file row.
    wide = top.pivot_table(index=["json_file", "effective_year_label"], columns="top_category", values="value_num", aggfunc="first")
    return wide.reindex(columns=TOP_CATEGORIES)


# ------------------------------------------------------------ gap detection
def find_gap_years(obs_years_by_country: dict, full_range: tuple[int, int] | None = None) -> dict:
    """
    full_range=None (default): a gap year is one "missing in the middle" of a country's own observed
    years only -- a year before its first observation or after its last is never a gap, and a country
    with fewer than 2 observed years is skipped entirely (there is no "middle" to speak of).

    full_range=(start, end): every missing year in [start, end] is a gap, for every country with at
    least one observation anywhere (no anchor at all -> nothing to build a T+2/T+3/T+4 candidate off of,
    so still skipped) -- this is the panel-wide definition: any missing cell in the full country x year
    grid, not just ones a country's own two bounding reports happen to sandwich.
    """
    out = {}
    for country, years in obs_years_by_country.items():
        ys = sorted(set(years))
        if full_range is not None:
            if not ys:
                continue
            span = range(full_range[0], full_range[1] + 1)
        else:
            if len(ys) < 2:
                continue
            span = range(ys[0], ys[-1] + 1)
        missing = [y for y in span if y not in set(ys)]
        if missing:
            out[country] = missing
    return out


def audit_columns(audit_json):
    if not isinstance(audit_json, str) or not audit_json.strip():
        return []
    try:
        cols = json.loads(audit_json).get("columns", [])
    except json.JSONDecodeError:
        return []
    out = []
    for c in cols:
        kind, y0, y1, _ = parse_year_label(c.get("year_label"))
        out.append({
            "kind": kind, "y0": y0, "y1": y1,
            "label": c.get("year_label"),
            "status": str(c.get("status") or "unknown").lower(),
            "group": c.get("group_label"),
        })
    return out


def main(
    input_csv: Path | list = INPUT_CSV,
    out_dir: Path | None = OUT_DIR,
    full_range: tuple[int, int] | None = None,
    exclude_identified_csv: Path | None = None,
):
    """
    input_csv is usually one compiled CSV (or the unified panel), but can also be a list of CSVs -- e.g.
    this batch's compiled CSV plus the next batch's -- which are concatenated before anything else runs.
    This is the fix for gaps at a batch's edge: find_gap_years() only flags a year "missing in the
    middle" of a country's observed years, so a gap at e.g. 2020 is invisible unless some LATER
    observation (e.g. 2022, from the next batch) is also loaded, giving 3a something to call "the
    middle." A single later batch's CSV is normally enough -- only years inside the gap need the next
    real observation, not the whole of every later batch.

    full_range=(start, end): switch to the panel-wide gap definition -- every missing year in that range
    for every country with at least one observation, not just years sandwiched between that country's
    own first and last report (see find_gap_years()'s own docstring). The panel/coverage-matrix outputs
    also use this range (instead of each country's own [first, last] observed span) for consistency.
    Typical use: input_csv points at the CURRENT merged panel (Round 1/2/3 + Human Review + any earlier
    Gap Fill output already folded in -- a previously gap-filled year then counts as observed and is not
    re-flagged), so this finds gaps the narrower, original definition could never have found: years
    before a country's first report or after its most recent one.

    exclude_identified_csv: a prior run's gap_years_<STAMP>.csv or gapfill_resolution_<STAMP>.csv (either
    works -- both have one row per (country, gap_year) that run ever identified, resolved or not). Only
    affects the written gap_years_<STAMP>.csv (what Step 2/3 are fed) -- a country-year already
    identified there is dropped so it is not attempted a second time; the panel/coverage-matrix outputs
    still show it as GAP, since it honestly still is one, just not re-submitted here. Use this together
    with full_range to get only the INCREMENTAL gaps a broader run adds on top of a narrower run already
    done -- never re-run (or lose track of) whatever that earlier run already attempted.
    """
    input_csvs = [Path(p) for p in input_csv] if isinstance(input_csv, (list, tuple)) else [Path(input_csv)]
    missing = [p for p in input_csvs if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Input CSV(s) not found: {missing}  (edit INPUT_CSV or pass --input)")
    out_dir = Path(out_dir) if out_dir else default_out_dir(input_csvs[0])
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Input : {'; '.join(str(p) for p in input_csvs)}\nOutput: {out_dir}")

    all_df = pd.concat([pd.read_csv(p, dtype=str) for p in input_csvs], ignore_index=True)

    reports = build_report_table(all_df)
    wide = top_level_values(all_df)
    reports = reports.merge(wide, left_on=["json_file", "effective_year_label"], right_index=True, how="left")
    # column_header_audit_json may not exist at all in a slimmer "final answer only" merged CSV -- without
    # it there is no per-year-column evidence to preview a fill_status from (see the loop below), so this
    # stays empty rather than silently claiming "not visible in any report" for every gap year.
    has_audit_data = "column_header_audit_json" in all_df.columns
    reports["audit_cols"] = (
        reports["column_header_audit_json"].apply(audit_columns) if has_audit_data
        else [[] for _ in range(len(reports))]
    )

    # (country, report publication year) -> reports, for the T+2/T+3/T+4 candidate lookup below. Built from
    # the already-parsed report_date (not re-parsed from the filename), one entry per real report.
    pub_year_idx: dict = {}
    for _, rep in reports.iterrows():
        pub_year_idx.setdefault((rep["country"], rep["report_date"].year), []).append(
            {"pdf_file_name": rep["pdf_file_name"], "date": rep["report_date"].strftime("%Y-%m-%d")}
        )

    # ------------------------------------------------ report usage status
    def status(row):
        if row["country"] == "Multi-Country Report":
            return "excluded_non_country"
        if not row["table_found_bool"]:
            return "no_table"
        if row["year_kind"] != "single":
            return "table_but_year_unusable"
        lag = row["report_date"].year - row["obs_year"]
        # A Gap Fill row is BY DESIGN sourced from a report published 2-4 years after the year it fills
        # (T+2/T+3/T+4) -- the plausible-lag window below is calibrated for a normal report's own
        # last_actual_year (1-2 years before its own publication) and would wrongly reject every
        # legitimate T+4 gap-fill row (lag == MAX_PLAUSIBLE_LAG exactly), so it only applies here to
        # non-gapfill rows. A gap-fill row published BEFORE the year it supposedly filled is still
        # nonsensical and stays flagged.
        is_gapfill = str(row.get("source_round") or "").strip().lower() == "gapfill"
        if lag < 0 or (not is_gapfill and lag >= MAX_PLAUSIBLE_LAG):
            return "year_implausible_vs_report_date"
        return "observation"

    reports["report_status"] = reports.apply(status, axis=1)
    # Reports Step 2/3 would also skip as a candidate source (no table, or a multi-country document) --
    # excluded here too so the T+2/T+3/T+4 preview below matches what Step 2/3 will actually try.
    skip_reports = set(reports.loc[reports["report_status"].isin(["no_table", "excluded_non_country"]), "pdf_file_name"])
    obs = reports[reports["report_status"] == "observation"].copy()
    obs["obs_year"] = obs["obs_year"].astype(int)

    # -------------------------------------------- dedupe: latest report wins
    obs = obs.sort_values(["country", "obs_year", "report_date", "pdf_file_name"])
    keep_idx = obs.groupby(["country", "obs_year"]).tail(1).index
    reports["superseded_duplicate"] = False
    dup_info = {}
    for (country, year), grp in obs.groupby(["country", "obs_year"]):
        if len(grp) > 1:
            kept = grp.iloc[-1]
            others = grp.iloc[:-1]
            agree = all(
                all(
                    (pd.isna(kept[c]) and pd.isna(o[c])) or (pd.notna(kept[c]) and pd.notna(o[c]) and abs(kept[c] - o[c]) < 1e-6)
                    for c in TOP_CATEGORIES
                )
                for _, o in others.iterrows()
            )
            dup_info[(country, year)] = {
                "n_reports": len(grp),
                "others": "; ".join(others["pdf_file_name"]),
                "agree": "Yes" if agree else "No",
            }
            reports.loc[others.index, "superseded_duplicate"] = True
    reports.loc[reports["superseded_duplicate"], "report_status"] = "observation_superseded_by_later_report"
    kept_obs = obs.loc[keep_idx].copy()

    # ------------------------------------------------------- gap detection
    def gaps_for(observations: pd.DataFrame):
        d = {c: g["obs_year"].tolist() for c, g in observations.groupby("country")}
        return find_gap_years(d, full_range=full_range)

    gaps_primary = gaps_for(kept_obs)
    gaps_certain_only = gaps_for(kept_obs[~kept_obs["year_uncertain"]])

    # per-country lookups
    reports_by_country = {c: g.sort_values("report_date") for c, g in reports.groupby("country")}

    def observed_years(country):
        return sorted(kept_obs.loc[kept_obs["country"] == country, "obs_year"])

    gap_rows = []
    span_counter = 0
    for country in sorted(gaps_primary):
        ys = observed_years(country)
        missing = gaps_primary[country]
        # group consecutive missing years into spans
        spans, cur = [], [missing[0]]
        for y in missing[1:]:
            if y == cur[-1] + 1:
                cur.append(y)
            else:
                spans.append(cur)
                cur = [y]
        spans.append(cur)
        creps = reports_by_country[country]
        for span in spans:
            span_counter += 1
            span_id = f"G{span_counter:04d}"
            # A span can be one-sided when full_range reaches before the country's first observation or
            # after its last (the panel-wide gap definition) -- there is no "prev"/"next" bounding report
            # on that side, so the "between two reports" causes below only apply when both sides exist.
            prev_candidates = [y for y in ys if y < span[0]]
            next_candidates = [y for y in ys if y > span[-1]]
            prev_y = max(prev_candidates) if prev_candidates else None
            next_y = min(next_candidates) if next_candidates else None
            prev_rows = obs[(obs["country"] == country) & (obs["obs_year"] == prev_y)] if prev_y is not None else obs.iloc[0:0]
            next_rows = obs[(obs["country"] == country) & (obs["obs_year"] == next_y)] if next_y is not None else obs.iloc[0:0]
            prev_rep = prev_rows.iloc[-1] if len(prev_rows) else None    # latest report giving prev year
            next_rep = next_rows.iloc[0] if len(next_rows) else None     # earliest report giving next year
            if prev_rep is not None and next_rep is not None:
                between = creps[(creps["report_date"] > prev_rep["report_date"]) & (creps["report_date"] < next_rep["report_date"])]
            elif prev_rep is not None:
                between = creps[creps["report_date"] > prev_rep["report_date"]]
            elif next_rep is not None:
                between = creps[creps["report_date"] < next_rep["report_date"]]
            else:
                between = creps.iloc[0:0]
            causes = []
            if prev_rep is None:
                causes.append("before_first_observed_year")
            if next_rep is None:
                causes.append("after_last_observed_year")
            if prev_rep is not None and next_rep is not None:
                if ((~between["table_found_bool"]) & (between["report_status"] != "excluded_non_country")).any():
                    causes.append("no_table_report_in_between")
                if (between["report_status"] == "table_but_year_unusable").any():
                    causes.append("unusable_year_report_in_between")
                if between.empty:
                    causes.append("lag_between_consecutive_reports")
            if not causes:
                causes.append("other_reports_in_between")
            months = (next_rep["report_date"] - prev_rep["report_date"]).days / 30.44 if (prev_rep is not None and next_rep is not None) else None

            for y in span:
                # Same T+2-then-T+3-then-T+4, latest-publication-date-first order Step 2/3 actually try (see
                # gapfill_lib_core.build_candidates()) -- this is a preview, not a second guess, so the
                # candidates considered here are restricted to exactly the reports Step 2/3 would reach.
                ordered_cands = build_candidates(country, y, pub_year_idx, skip_reports)
                cands = []
                for oc in ordered_cands:
                    match = creps[creps["pdf_file_name"] == oc["pdf_file_name"]]
                    if match.empty or not match.iloc[0]["table_found_bool"]:
                        continue
                    rep = match.iloc[0]
                    for c in rep["audit_cols"]:
                        if c["kind"] == "single" and c["y0"] == y:
                            cands.append((rep, c, "single"))
                        elif c["kind"] == "range" and c["y0"] <= y <= c["y1"]:
                            cands.append((rep, c, "merged_range"))
                singles = [t for t in cands if t[2] == "single"]
                actual = [t for t in singles if t[1]["status"] in ELIGIBLE]
                prelim = [t for t in singles if t[1]["status"] in PRELIM_EST]
                proj = [t for t in singles if t[1]["status"] == "projection"]
                merged_rng = [t for t in cands if t[2] == "merged_range"]
                if not has_audit_data:
                    # No column_header_audit_json anywhere in the input -- there is no evidence to preview
                    # a fill_status from, so say so honestly instead of defaulting to the same outcome
                    # "not_visible_in_any_report" would silently produce for every gap year.
                    fill_status = "preview_unavailable_no_audit_column"
                elif actual:
                    fill_status = "fillable_actual_column_visible"
                elif prelim:
                    fill_status = "only_preliminary_or_estimate"
                elif merged_rng:
                    fill_status = "only_in_merged_range_column"
                elif proj:
                    fill_status = "only_projection"
                elif singles:
                    fill_status = "status_unknown"
                else:
                    fill_status = "not_visible_in_any_report"
                # cands is already in T+2-then-T+3-then-T+4, latest-first order (it was built by walking
                # ordered_cands), so the first eligible one is exactly what Step 2/3 would pick.
                pool = actual or prelim or []
                pref = pool[0] if pool else None
                gap_rows.append({
                    "gap_id": span_id,
                    "country": country,
                    "gap_year": y,
                    "gap_span": f"{span[0]}-{span[-1]}" if len(span) > 1 else str(span[0]),
                    "gap_span_length": len(span),
                    "prev_observed_year": prev_y,
                    "prev_report": prev_rep["pdf_file_name"] if prev_rep is not None else None,
                    "next_observed_year": next_y,
                    "next_report": next_rep["pdf_file_name"] if next_rep is not None else None,
                    "months_between_bounding_reports": round(months, 1) if months is not None else None,
                    "n_reports_in_between": len(between),
                    "reports_in_between": "; ".join(between["pdf_file_name"]),
                    "primary_cause": causes[0],
                    "all_causes": "; ".join(causes),
                    "boundary_year_uncertain": bool(
                        (prev_rep is not None and prev_rep["year_uncertain"])
                        or (next_rep is not None and next_rep["year_uncertain"])
                    ),
                    "fill_status": fill_status,
                    "preferred_source_report": pref[0]["pdf_file_name"] if pref else None,
                    "preferred_source_col_label": pref[1]["label"] if pref else None,
                    "preferred_source_col_status": pref[1]["status"] if pref else None,
                    "n_reports_actual_column_visible": len({t[0]["pdf_file_name"] for t in actual}),
                    "all_actual_source_reports": "; ".join(sorted({t[0]["pdf_file_name"] for t in actual})),
                })
    gaps = pd.DataFrame(gap_rows)

    # -------------------------------------------------------------- panel
    panel_rows = []
    gap_lookup = {(r["country"], r["gap_year"]): r for _, r in gaps.iterrows()} if len(gaps) else {}
    all_countries = sorted(kept_obs["country"].unique())
    for country in all_countries:
        ys = observed_years(country)
        year_span = range(full_range[0], full_range[1] + 1) if full_range is not None else range(ys[0], ys[-1] + 1)
        for y in year_span:
            if (country, y) in gap_lookup:
                g = gap_lookup[(country, y)]
                panel_rows.append({
                    "country": country, "year": y, "status": "GAP",
                    "source_report": None, "source_report_date": None,
                    "n_reports_for_year": 0, "duplicate_reports_superseded": None,
                    "duplicate_values_agree": None,
                    "year_uncertain": None, "year_parse_note": None,
                    "gap_id": g["gap_id"], "gap_span": g["gap_span"],
                    "gap_primary_cause": g["primary_cause"], "gap_fill_status": g["fill_status"],
                    "gap_preferred_source_report": g["preferred_source_report"],
                    **{c: None for c in TOP_CATEGORIES},
                })
            else:
                row = kept_obs[(kept_obs["country"] == country) & (kept_obs["obs_year"] == y)].iloc[0]
                di = dup_info.get((country, y), {})
                panel_rows.append({
                    "country": country, "year": y, "status": "observed",
                    "source_report": row["pdf_file_name"], "source_report_date": row["report_date"].date().isoformat(),
                    "n_reports_for_year": di.get("n_reports", 1),
                    "duplicate_reports_superseded": di.get("others"),
                    "duplicate_values_agree": di.get("agree"),
                    "year_uncertain": bool(row["year_uncertain"]),
                    "year_parse_note": row["year_parse_note"] or None,
                    "gap_id": None, "gap_span": None, "gap_primary_cause": None,
                    "gap_fill_status": None, "gap_preferred_source_report": None,
                    **{c: row[c] for c in TOP_CATEGORIES},
                })
    panel = pd.DataFrame(panel_rows)

    # ------------------------------------------------ children long table
    # (json_file, effective_year_label) identifies one kept observation; json_file alone is not unique
    # once a real report can carry rows for more than one year (its own, plus any gap year it was used
    # to fill), so both the membership filter and the join key below use the pair, not json_file alone.
    all_df["effective_year_label"] = effective_year_label(all_df)
    keep_pairs = set(zip(kept_obs["json_file"], kept_obs["effective_year_label"]))
    all_df_keys = pd.Series(list(zip(all_df["json_file"], all_df["effective_year_label"])), index=all_df.index)
    children_src = all_df[
        all_df_keys.isin(keep_pairs)
        & (all_df["level"].astype(str).isin(["1", "1.0", "2", "2.0", "3", "3.0"]))
    ][["json_file", "effective_year_label", "pdf_file_name", "top_category", "hierarchy_id", "level", "parent_label", "label_verbatim", "value"]].copy()
    key = kept_obs.set_index(["json_file", "effective_year_label"])[["country", "obs_year"]]
    children = children_src.join(key, on=["json_file", "effective_year_label"])
    children = children.rename(columns={"obs_year": "year"})[
        ["country", "year", "pdf_file_name", "top_category", "hierarchy_id", "level", "parent_label", "label_verbatim", "value"]
    ].sort_values(["country", "year", "hierarchy_id"])

    # ------------------------------------------------------ coverage matrix
    y_min, y_max = int(panel["year"].min()), int(panel["year"].max())
    years = list(range(y_min, y_max + 1))
    matrix = pd.DataFrame("", index=all_countries, columns=years)
    for _, r in panel.iterrows():
        if r["status"] == "GAP":
            matrix.loc[r["country"], r["year"]] = "GAP"
        else:
            matrix.loc[r["country"], r["year"]] = "O?" if r["year_uncertain"] else "O"
    matrix.index.name = "country"

    # ----------------------------------------------------- report inventory
    # Some of these are audit columns a slimmer "final answer only" merged CSV may not carry at all (see
    # build_report_table()); kept only when actually present rather than raising on a missing column.
    inv_cols = [c for c in [
        "pdf_file_name", "country", "report_date", "report_status",
        "table_found", "last_actual_year", "obs_year", "year_parse_note",
        "year_uncertain", "year_after_report_year", "manual_review_required",
        "actual_column_validation_status", "confidence", "framework",
    ] if c in reports.columns]
    inv = reports[inv_cols].copy()
    inv["report_date"] = inv["report_date"].dt.date.astype(str)
    inv = inv.sort_values(["country", "report_date"])

    # ---------------------------------------- exclude already-identified gaps
    # Only affects what gets WRITTEN to gap_years (and so fed to Step 2/3) -- panel/coverage-matrix above
    # already reflect the full, honest state and are untouched.
    gaps_to_write = gaps
    n_excluded = 0
    if exclude_identified_csv is not None and len(gaps):
        exclude_path = Path(exclude_identified_csv)
        if exclude_path.exists():
            prior = pd.read_csv(exclude_path, dtype=str)
            prior_keys = set(zip(
                prior["country"].map(lambda c: normalize_country(str(c).strip()).casefold()),
                prior["gap_year"].astype(int),
            ))
            is_new = gaps.apply(
                lambda r: (normalize_country(str(r["country"])).casefold(), int(r["gap_year"])) not in prior_keys,
                axis=1,
            )
            gaps_to_write = gaps[is_new].copy()
            n_excluded = int((~is_new).sum())
            print(f"Excluding {n_excluded} gap year(s) already identified in {exclude_path}; "
                  f"{len(gaps_to_write)} new gap year(s) remain.")
        else:
            print(f"exclude_identified_csv not found, nothing excluded: {exclude_path}")

    # ------------------------------------------------------------- write
    p = lambda name: out_dir / f"{name}_{STAMP}.csv"
    panel.to_csv(p("panel_structure_country_year"), index=False, encoding="utf-8-sig")
    gaps_to_write.to_csv(p("gap_years"), index=False, encoding="utf-8-sig")
    matrix.to_csv(p("coverage_matrix_country_year"), encoding="utf-8-sig")
    inv.to_csv(p("report_inventory"), index=False, encoding="utf-8-sig")
    children.to_csv(p("panel_children_long"), index=False, encoding="utf-8-sig")

    # ------------------------------------------------------------- summary
    gaps = gaps_to_write  # stats below describe what was actually written (fed to Step 2/3)
    stats = {
        "n_reports": int(len(reports)),
        "status_counts": reports["report_status"].value_counts().to_dict(),
        "n_countries_in_panel": len(all_countries),
        "n_observed_country_years": int((panel["status"] == "observed").sum()),
        "n_gap_years_excluded_already_identified": n_excluded,
        "n_countries_with_gap": int(gaps["country"].nunique()) if len(gaps) else 0,
        "n_gap_years": int(len(gaps)),
        "n_gap_spans": int(gaps["gap_id"].nunique()) if len(gaps) else 0,
        "gap_years_certain_only": int(sum(len(v) for v in gaps_certain_only.values())),
        "countries_with_gap_certain_only": int(len(gaps_certain_only)),
        "span_length_dist": gaps.drop_duplicates("gap_id")["gap_span_length"].value_counts().sort_index().to_dict() if len(gaps) else {},
        "cause_counts_by_span": gaps.drop_duplicates("gap_id")["primary_cause"].value_counts().to_dict() if len(gaps) else {},
        "fill_status_by_gap_year": gaps["fill_status"].value_counts().to_dict() if len(gaps) else {},
        "n_dup_country_years": len(dup_info),
        "n_dup_values_disagree": sum(1 for v in dup_info.values() if v["agree"] == "No"),
        "n_year_after_report_year": int(reports["year_after_report_year"].sum()),
        "n_uncertain_obs": int(kept_obs["year_uncertain"].sum()),
    }
    (out_dir / f"summary_stats_{STAMP}.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(stats, indent=2, ensure_ascii=False, default=str))
    return stats


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--input", action="append", default=None,
                    help="compiled CSV to analyse (default: INPUT_CSV above); repeat to pass more than "
                         "one, e.g. --input this_batch.csv --input next_batch.csv, so gaps at this "
                         "batch's edge (which need the next batch's first observation to even be "
                         "visible as 'the middle') are detected")
    ap.add_argument("--out-dir", default=None, help="output folder (default: gap_year_check next to the CSV's batch folder)")
    a, _ = ap.parse_known_args()  # tolerant: extra args injected by IPython/Spyder are ignored
    main(
        [Path(p) for p in a.input] if a.input else INPUT_CSV,
        Path(a.out_dir) if a.out_dir else OUT_DIR,
        full_range=FULL_RANGE,
        exclude_identified_csv=EXCLUDE_IDENTIFIED_CSV,
    )
