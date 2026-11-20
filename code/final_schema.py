"""
The one column layout of the panel database, shared by every source of rows.

Every row of the panel database -- whether it comes from Round 1 (fully matched reports), Round 2 (fully
matched reports), Round 3 (human review) or Gap Fill -- has exactly FINAL_COLUMNS, in this order: the 43
columns of a round's compiled CSV (ROUND_COLUMNS, as 1b writes them) + source_round + gapfill_run. So the
rows of every source can be appended to each other directly. Gap Fill and the human review fill as many of
those columns as they know (report facts, table, page, column header audit); the rest stay blank.
A merged file made before 0.6.0 has only 21 of them (LEGACY_COLUMNS); it reads in with the others blank.

    json_file .. actual_column_label   report-level facts (the same on every row of one report-year)
    top_category, hierarchy_id, level, parent_label, label_verbatim, value
                                       one decomposition line item. hierarchy_id is the key that
                                       identifies the indicator (1 = change in debt, 2 = identified
                                       flows, 3 = primary balance, 4 = automatic debt dynamics,
                                       5 = other identified flows, 6 = residual; 5.1 = first child of 5,
                                       and so on) -- it is kept as is from every source.
    source_round                       round1 / round2 / round3 / gapfill
    gapfill_run                        the Gap Fill STAMP that produced a gapfill row, blank otherwise

Two year columns, one per stage:
    last_actual_year   Round 1, Round 2, Round 3 and the Pre Gap Fill file (FINAL_COLUMNS): the report's own
                       last actual (latest historical) year
    year               Gap Fill rows and the panel database after Gap Fill (PANEL_COLUMNS, same columns with
                       year in place of last_actual_year): the year the values are for -- the gap year for a
                       Gap Fill row, the last actual year for a Round 1-3 row (to_panel()).

to_final() turns any of the round CSVs (the 43-column compiled CSV, a check's matched rows, the human
review rows) or Gap Fill's values_long into this layout; it also tidies two number formats that pandas
leaves behind ("0.0" -> "0" for level, "65.0" -> "65" for page_pdf), so the same item reads the same in
every source.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, Optional

import pandas as pd

# The columns of a round's compiled CSV, in the order 1b writes them: every Round 1 / Round 2 run CSV and a
# check's matched rows have exactly these. Every source of the panel database is brought to them.
ROUND_COLUMNS = [
    "json_file", "pdf_file_name", "country", "publication_date", "consultation_type", "report_title",
    "country_report_number", "table_found", "framework", "table_number", "table_title", "page_pdf", "page_printed",
    "last_actual_year", "actual_column_label", "actual_column_status", "actual_column_header_verbatim",
    "latest_observation_year", "latest_observation_status", "actual_year_label_match", "column_header_selected_year",
    "column_header_selection_reason", "independent_audit_selected_year", "independent_audit_selection_reason",
    "independent_latest_observation_year", "independent_latest_observation_status", "actual_column_validation_status",
    "actual_column_validation_issues", "first_selected_year", "audited_selected_year", "manual_review_required",
    "column_header_audit_json", "independent_column_header_audit_json", "confidence", "extraction_method",
    "top_category", "hierarchy_id", "level", "parent_label", "label_verbatim", "value", "failure_reason",
    "extraction_notes",
]
# Round 1-3 rows put together (the Pre Gap Fill file): the round columns + where each row came from.
# last_actual_year = the report's own last actual (latest historical) year.
# update_origin: in a build that starts from a previous database, "previous" = a row taken over unchanged from
# it (its Gap Fill rows are never taken over), "new" = a row from this update (its Round 1-3 results and its
# Gap Fill). Blank in files made before 0.6.0.
FINAL_COLUMNS = ROUND_COLUMNS + ["source_round", "gapfill_run", "update_origin"]
UPDATE_ORIGINS = ["previous", "new"]
PREGAP_COLUMNS = FINAL_COLUMNS
# Gap Fill rows and the panel database after Gap Fill: the same columns, with "year" (the year the values
# are for) in place of last_actual_year, which does not apply to a gap year. For a Round 1-3 row, year =
# its last_actual_year.
PANEL_COLUMNS = ["year" if c == "last_actual_year" else c for c in FINAL_COLUMNS]
# the 21 columns of the merged files made before 0.6.0 (e.g. final_all_batches_with_gapfill_20261028.csv);
# such a file still reads in: the other columns are blank for its rows
LEGACY_COLUMNS = [
    "json_file", "pdf_file_name", "country", "publication_date", "consultation_type", "report_title",
    "country_report_number", "framework", "table_number", "table_title", "page_pdf", "last_actual_year",
    "actual_column_label", "top_category", "hierarchy_id", "level", "parent_label", "label_verbatim", "value",
    "source_round", "gapfill_run",
]
# report-level columns: the same on every row of one report-year
REPORT_COLUMNS = ROUND_COLUMNS[:ROUND_COLUMNS.index("top_category")] + ["failure_reason", "extraction_notes"]
# columns that describe how a run chose its last actual year: they do not apply to a value a person entered
SELECTION_COLUMNS = [
    "actual_column_status", "actual_column_header_verbatim", "latest_observation_year", "latest_observation_status",
    "actual_year_label_match", "column_header_selected_year", "column_header_selection_reason",
    "independent_audit_selected_year", "independent_audit_selection_reason", "independent_latest_observation_year",
    "independent_latest_observation_status", "actual_column_validation_issues", "first_selected_year",
    "audited_selected_year", "independent_column_header_audit_json", "confidence", "failure_reason",
]
ITEM_COLUMNS = ["top_category", "hierarchy_id", "level", "parent_label", "label_verbatim", "value"]
SOURCE_ROUNDS = ["round1", "round2", "round3", "gapfill"]

# first number of the hierarchy id -> top category (same order as 1b's TOP_LEVEL_CATEGORIES)
TOP_CATEGORIES = ["change_in_debt", "identified_flows", "primary_balance",
                  "automatic_debt_dynamics", "other_identified_flows", "residual"]
TOP_BY_ID = {str(i + 1): c for i, c in enumerate(TOP_CATEGORIES)}
HID_RE = re.compile(r"^[1-6](?:\.\d+)*$")


def _int_text(v) -> Optional[str]:
    """'0.0' -> '0', '65.0' -> '65'; anything else unchanged; empty -> None."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    if not s or s.lower() == "nan":
        return None
    m = re.fullmatch(r"(-?\d+)\.0+", s)
    return m.group(1) if m else s


def hid_sort_key(h) -> list:
    return [int(p) if p.isdigit() else 10 ** 6 for p in str(h).split(".")]


def item_fields(hierarchy_id: str, labels: Dict[str, str]) -> dict:
    """top_category, level and parent_label that follow from a hierarchy id (labels: hierarchy_id -> label of
    the same report, used for the parent's label)."""
    hid = str(hierarchy_id).strip()
    parts = hid.split(".")
    parent = ".".join(parts[:-1])
    return {
        "top_category": TOP_BY_ID.get(parts[0]),
        "level": str(len(parts) - 1),
        "parent_label": labels.get(parent) if parent else None,
    }


def to_final(df: pd.DataFrame, source_round: str, gapfill_run: Optional[str] = None) -> pd.DataFrame:
    """Any round / review / gap-fill table -> FINAL_COLUMNS. Columns the input lacks are left blank; a
    values_long table's "year" becomes last_actual_year."""
    out = pd.DataFrame(index=df.index, columns=FINAL_COLUMNS, dtype=object)
    for c in FINAL_COLUMNS:
        if c in df.columns:
            out[c] = df[c]
    if "year" in df.columns:  # gap fill values_long: the gap year is the year the values are for
        lay = out["last_actual_year"]
        out["last_actual_year"] = lay.where(lay.notna() & (lay.astype(str).str.strip() != ""), df["year"])
    out["level"] = out["level"].map(_int_text)
    out["page_pdf"] = out["page_pdf"].map(_int_text)
    out["last_actual_year"] = out["last_actual_year"].map(_int_text)
    out["source_round"] = source_round
    out["gapfill_run"] = gapfill_run if source_round == "gapfill" else None
    out["update_origin"] = out["update_origin"].where(out["update_origin"].notna(), None)  # kept when the input has it
    return out.reset_index(drop=True)


def to_panel(df: pd.DataFrame) -> pd.DataFrame:
    """Rows in FINAL_COLUMNS (last_actual_year), or already in PANEL_COLUMNS (year) -> PANEL_COLUMNS:
    year = the row's year if it has one, else its last_actual_year; last_actual_year is dropped."""
    df = df.reset_index(drop=True)
    lay = df["last_actual_year"] if "last_actual_year" in df.columns else pd.Series(None, index=df.index, dtype=object)
    year = df["year"] if "year" in df.columns else pd.Series(None, index=df.index, dtype=object)
    has_year = year.notna() & (year.astype(str).str.strip() != "")
    out = pd.DataFrame({c: (df[c] if c in df.columns else None) for c in PANEL_COLUMNS if c != "year"}, index=df.index)
    out.insert(PANEL_COLUMNS.index("year"), "year", year.where(has_year, lay).map(_int_text))
    return out[PANEL_COLUMNS]


def concat_final(frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    frames = [f[FINAL_COLUMNS] for f in frames if f is not None and len(f)]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=FINAL_COLUMNS)


def check_final(df: pd.DataFrame) -> list:
    """Problems that would make rows unusable in the panel: wrong columns, a missing or malformed
    hierarchy_id, a top_category that does not match the id, the same line item twice. Works on the Pre Gap
    Fill layout (FINAL_COLUMNS) and on the panel layout (PANEL_COLUMNS)."""
    problems = []
    if list(df.columns) not in (FINAL_COLUMNS, PANEL_COLUMNS):
        problems.append(f"columns differ from FINAL_COLUMNS / PANEL_COLUMNS: {list(df.columns)}")
        return problems
    ycol = "year" if "year" in df.columns else "last_actual_year"
    hid = df["hierarchy_id"].astype(str).str.strip()
    bad = ~hid.str.match(HID_RE)
    if bad.any():
        problems.append(f"{int(bad.sum())} row(s) with a missing or malformed hierarchy_id")
    expect = hid.str.split(".").str[0].map(TOP_BY_ID)
    wrong = (~bad) & (expect != df["top_category"])
    if wrong.any():
        problems.append(f"{int(wrong.sum())} row(s) whose top_category does not match the hierarchy_id")
    dup = df.duplicated(["json_file", ycol, "hierarchy_id"], keep=False)
    if dup.any():
        problems.append(f"{int(dup.sum())} row(s) repeat the same (json_file, {ycol}, hierarchy_id)")
    return problems
