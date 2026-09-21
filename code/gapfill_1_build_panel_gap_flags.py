"""
Step 1 of the "fill missing year gap" exercise.

Reads one batch of extraction output (the compiled CSV produced by
json_to_excel_dsa_*.py), builds a country x year panel of the SFA decomposition
values (one observation per report = its last actual year), and flags interior
gap years, i.e. years between a country's first and last observed year that no
report supplies.

Nothing here re-reads PDFs. Which report could supply a gap year is inferred
from the per-report column_header_audit_json (every visible year column with
its actual/estimate/projection status).

Input is ONE compiled CSV. Usage:
    python gapfill_1_build_panel_gap_flags.py --input path/to/compiled.csv [--out-dir DIR]
or edit INPUT_CSV below and just run the file (also works from IPython / Spyder).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd



def _here() -> Path:
    """Folder of this script; falls back to the working folder when __file__ is
    not defined (code pasted or run as a cell in IPython / Spyder)."""
    try:
        return Path(__file__).resolve().parent
    except NameError:
        return Path.cwd()


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

# ---------------------------------------------------------------- countries
_ALIASES = {
    "cote d'ivoire": "Côte d'Ivoire",
    "côte d'ivoire": "Côte d'Ivoire",
    "democratic republic of sao tome and principe": "São Tomé and Príncipe",
    "democratic republic of são tomé and príncipe": "São Tomé and Príncipe",
    "democratic republic of timor-leste": "Timor-Leste",
    "republic of timor-leste": "Timor-Leste",
    "democratic republic of the congo": "Democratic Republic of the Congo",
    "republic of congo": "Republic of Congo",
    "islamic republic of afghanistan": "Afghanistan",
    "islamic republic of iran": "Iran",
    "islamic republic of mauritania": "Mauritania",
    "kingdom of eswatini": "Eswatini",
    "kingdom of swaziland": "Eswatini",
    "kingdom of lesotho": "Lesotho",
    "lao people's democratic republic": "Lao PDR",
    "people's republic of china": "China",
    "former yugoslav republic of macedonia": "North Macedonia",
    "republic of north macedonia": "North Macedonia",
    "republic of the marshall islands": "Marshall Islands",
    "union of comoros": "Comoros",
    "union of the comoros": "Comoros",
    "united republic of tanzania": "Tanzania",
    "republic of tanzania": "Tanzania",
    "federated states of micronesia": "Micronesia",
    "arab republic of egypt": "Egypt",
    "federal democratic republic of ethiopia": "Ethiopia",
    "brunei darussalam": "Brunei",
    "republic of korea": "Korea",
}
_REPUBLIC_OF = re.compile(r"^republic of (.+)$", re.I)


def normalize_country(raw: str) -> str:
    """Canonical country label from the PDF-filename prefix."""
    s = str(raw).strip().replace("’", "'")
    s = re.sub(r"[–—]+", "-", s)
    s = re.sub(r"\s*-\s*", "-", s)
    s = re.sub(r"^the\s+", "", s, flags=re.I)
    low = s.lower()
    m = re.match(r"^people's republic of china-(.+)$", low)
    if m:
        return "Hong Kong SAR, China" if "hong kong" in m.group(1) else "Macao SAR, China"
    m = re.match(r"^kingdom of the netherlands-(.+)$", low)
    if m:
        t = m.group(1)
        if t == "netherlands":
            return "Netherlands"
        if t == "aruba":
            return "Aruba"
        return "Curaçao and Sint Maarten"
    if low == "kingdom of the netherlands":
        return "Netherlands"
    if low in _ALIASES:
        return _ALIASES[low]
    m = _REPUBLIC_OF.match(s)
    if m:
        return m.group(1).strip()
    return s


# -------------------------------------------------------------------- years
def parse_year_label(value):
    """Return (kind, y0, y1, note); kind in single | range | invalid.

    Fiscal-year labels (2012/13, 2012-13, FY2012) map to the fiscal-year END year
    for the two-part forms; FY2012 is taken as 2012. Multi-year spans
    (2002-2010) are ranges and are never a single observation year.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "invalid", None, None, "missing"
    text = re.sub(r"\s+", " ", str(value)).strip()
    if not text or text.lower() == "nan":
        return "invalid", None, None, "missing"
    m = re.fullmatch(r"(?:FY\s?)?(\d{4})\s*[/-]\s*(\d{2}|\d{4})", text, flags=re.I)
    if m:
        a = int(m.group(1))
        b_txt = m.group(2)
        b = int(b_txt) if len(b_txt) == 4 else int(str(a)[:2] + b_txt)
        if b - a == 1:
            return "single", b, b, f"fiscal_year_end_of_{text}"
        if b > a:
            return "range", a, b, f"multi_year_range_{text}"
        return "invalid", None, None, f"unparsed_{text}"
    m = re.fullmatch(r"(?:FY\s?)?(\d{4})", text, flags=re.I)
    if m:
        return "single", int(m.group(1)), int(m.group(1)), "fy_label" if text.upper().startswith("FY") else ""
    years = re.findall(r"\b(\d{4})\b", text)
    if len(set(years)) == 1:
        y = int(years[0])
        return "single", y, y, f"extracted_from_text_{text}"
    return "invalid", None, None, f"unparsed_{text}"


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
