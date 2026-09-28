"""
[3a_gapfill_1] Find gap years and build the panel skeleton.
    Step 1 | run by hand | does not read PDFs, does not call the API

Purpose
    From a compiled CSV (Step 1's extraction output, long format: one row = one
    decomposition line item from one report), take one observation per report
    (country + the value for its last_actual_year), assemble a "country x year"
    panel skeleton, and flag the years "missing in the middle" of each country's
    span of observed years, i.e. gap years.

Input (needs only one CSV)
    INPUT_CSV at the top of the file, or --input on the command line. E.g.
    output/2016-2020/compiled_csv/dsa_decomposition_labels_2016-2020_sa.csv
    Columns used: json_file, pdf_file_name, table_found, last_actual_year, level, top_category, value,
    hierarchy_id, parent_label, label_verbatim, column_header_audit_json,
    manual_review_required, actual_column_validation_status, confidence, framework

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
    7. Write out the files above.

Usage
    python 3a_gapfill_1_build_panel_gap_flags.py --input <some CSV> [--out-dir <output folder>]
    or just edit INPUT_CSV at the top of the file and run (also works from an IPython / PyCharm console).
    STAMP is the version tag; it must match the STAMP used in Steps 2 and 3.
"""
from __future__ import annotations

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
INPUT_CSV = BASE / "output" / "2016-2020" / "compiled_csv" / "dsa_decomposition_labels_2016-2020_sa.csv"
OUT_DIR = None  # None -> "gap_year_check" folder next to the CSV's batch folder
STAMP = "20260920_v2"


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
# normalize_country() and parse_year_label() live in gapfill_lib_core.py (same folder).
sys.path.insert(0, str(HERE))
from gapfill_lib_core import normalize_country, parse_year_label  # noqa: E402

def to_float(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    s = str(x).strip().replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


# ------------------------------------------------------------------ loading
def build_report_table(df: pd.DataFrame) -> pd.DataFrame:
    r = df.sort_values("json_file").drop_duplicates("json_file", keep="first").copy()
    m = r["pdf_file_name"].str.extract(r"^(?P<prefix>.*?)_(?P<date>\d{4}-\d{2}-\d{2})")
    r["country_raw"] = m["prefix"]
    r["report_date"] = pd.to_datetime(m["date"])
    r["country"] = r["country_raw"].apply(normalize_country)
    parsed = r["last_actual_year"].apply(parse_year_label)
    r["year_kind"] = parsed.apply(lambda t: t[0])
    r["obs_year"] = parsed.apply(lambda t: t[1])
    r["year_parse_note"] = parsed.apply(lambda t: t[3])
    r["table_found_bool"] = r["table_found"].str.upper().eq("TRUE")
    r["year_uncertain"] = (
        r["manual_review_required"].eq("Yes")
        | r["actual_column_validation_status"].eq("manual_review")
    )
    r["year_after_report_year"] = r.apply(
        lambda x: bool(pd.notna(x["obs_year"]) and pd.notna(x["report_date"]) and x["obs_year"] > x["report_date"].year),
        axis=1,
    )
    return r.reset_index(drop=True)


def top_level_values(df: pd.DataFrame) -> pd.DataFrame:
    top = df[df["level"].astype(str).isin(["0", "0.0"]) & df["top_category"].isin(TOP_CATEGORIES)].copy()
    top["value_num"] = top["value"].apply(to_float)
    wide = top.pivot_table(index="json_file", columns="top_category", values="value_num", aggfunc="first")
    return wide.reindex(columns=TOP_CATEGORIES)


# ------------------------------------------------------------ gap detection
def find_gap_years(obs_years_by_country: dict) -> dict:
    out = {}
    for country, years in obs_years_by_country.items():
        ys = sorted(set(years))
        if len(ys) < 2:
            continue
        missing = [y for y in range(ys[0], ys[-1] + 1) if y not in set(ys)]
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


def main(input_csv: Path = INPUT_CSV, out_dir: Path | None = OUT_DIR):
    input_csv = Path(input_csv)
    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}  (edit INPUT_CSV or pass --input)")
    out_dir = Path(out_dir) if out_dir else default_out_dir(input_csv)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Input : {input_csv}\nOutput: {out_dir}")

    all_df = pd.read_csv(input_csv, dtype=str)

    reports = build_report_table(all_df)
    wide = top_level_values(all_df)
    reports = reports.merge(wide, left_on="json_file", right_index=True, how="left")
    reports["audit_cols"] = reports["column_header_audit_json"].apply(audit_columns)

    # ------------------------------------------------ report usage status
    def status(row):
        if row["country"] == "Multi-Country Report":
            return "excluded_non_country"
        if not row["table_found_bool"]:
            return "no_table"
        if row["year_kind"] != "single":
            return "table_but_year_unusable"
        lag = row["report_date"].year - row["obs_year"]
        if lag >= MAX_PLAUSIBLE_LAG or lag < 0:
            return "year_implausible_vs_report_date"
        return "observation"

    reports["report_status"] = reports.apply(status, axis=1)
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
        return find_gap_years(d)

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
            prev_y = max(y for y in ys if y < span[0])
            next_y = min(y for y in ys if y > span[-1])
            prev_rows = obs[(obs["country"] == country) & (obs["obs_year"] == prev_y)]
            next_rows = obs[(obs["country"] == country) & (obs["obs_year"] == next_y)]
            prev_rep = prev_rows.iloc[-1]          # latest report giving prev year
            next_rep = next_rows.iloc[0]           # earliest report giving next year
            between = creps[(creps["report_date"] > prev_rep["report_date"]) & (creps["report_date"] < next_rep["report_date"])]
            causes = []
            if ((~between["table_found_bool"]) & (between["report_status"] != "excluded_non_country")).any():
                causes.append("no_table_report_in_between")
            if (between["report_status"] == "table_but_year_unusable").any():
                causes.append("unusable_year_report_in_between")
            if between.empty:
                causes.append("lag_between_consecutive_reports")
            if not causes:
                causes.append("other_reports_in_between")
            months = (next_rep["report_date"] - prev_rep["report_date"]).days / 30.44

            for y in span:
                cands = []
                for _, rep in creps.iterrows():
                    if not rep["table_found_bool"]:
                        continue
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
                if actual:
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
                pool = actual or prelim or []
                pool_sorted = sorted(pool, key=lambda t: t[0]["report_date"])
                pref = pool_sorted[0] if pool_sorted else None
                gap_rows.append({
                    "gap_id": span_id,
                    "country": country,
                    "gap_year": y,
                    "gap_span": f"{span[0]}-{span[-1]}" if len(span) > 1 else str(span[0]),
                    "gap_span_length": len(span),
                    "prev_observed_year": prev_y,
                    "prev_report": prev_rep["pdf_file_name"],
                    "next_observed_year": next_y,
                    "next_report": next_rep["pdf_file_name"],
                    "months_between_bounding_reports": round(months, 1),
                    "n_reports_in_between": len(between),
                    "reports_in_between": "; ".join(between["pdf_file_name"]),
                    "primary_cause": causes[0],
                    "all_causes": "; ".join(causes),
                    "boundary_year_uncertain": bool(prev_rep["year_uncertain"] or next_rep["year_uncertain"]),
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
        for y in range(ys[0], ys[-1] + 1):
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
    children_src = all_df[
        all_df["json_file"].isin(kept_obs["json_file"])
        & (all_df["level"].astype(str).isin(["1", "1.0", "2", "2.0", "3", "3.0"]))
    ][["json_file", "pdf_file_name", "top_category", "hierarchy_id", "level", "parent_label", "label_verbatim", "value"]].copy()
    key = kept_obs.set_index("json_file")[["country", "obs_year"]]
    children = children_src.join(key, on="json_file")
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
    inv = reports[[
        "pdf_file_name", "country", "report_date", "report_status",
        "table_found", "last_actual_year", "obs_year", "year_parse_note",
        "year_uncertain", "year_after_report_year", "manual_review_required",
        "actual_column_validation_status", "confidence", "framework",
    ]].copy()
    inv["report_date"] = inv["report_date"].dt.date.astype(str)
    inv = inv.sort_values(["country", "report_date"])

    # ------------------------------------------------------------- write
    p = lambda name: out_dir / f"{name}_{STAMP}.csv"
    panel.to_csv(p("panel_structure_country_year"), index=False, encoding="utf-8-sig")
    gaps.to_csv(p("gap_years"), index=False, encoding="utf-8-sig")
    matrix.to_csv(p("coverage_matrix_country_year"), encoding="utf-8-sig")
    inv.to_csv(p("report_inventory"), index=False, encoding="utf-8-sig")
    children.to_csv(p("panel_children_long"), index=False, encoding="utf-8-sig")

    # ------------------------------------------------------------- summary
    stats = {
        "n_reports": int(len(reports)),
        "status_counts": reports["report_status"].value_counts().to_dict(),
        "n_countries_in_panel": len(all_countries),
        "n_observed_country_years": int((panel["status"] == "observed").sum()),
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
    ap.add_argument("--input", default=None, help="compiled CSV to analyse (default: INPUT_CSV above)")
    ap.add_argument("--out-dir", default=None, help="output folder (default: gap_year_check next to the CSV's batch folder)")
    a, _ = ap.parse_known_args()  # tolerant: extra args injected by IPython/Spyder are ignored
    main(Path(a.input) if a.input else INPUT_CSV, Path(a.out_dir) if a.out_dir else OUT_DIR)
