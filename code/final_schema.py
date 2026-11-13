"""
The one column layout of the panel database, shared by every source of rows.

Every row of the panel database -- whether it comes from Round 1 (fully matched reports), Round 2 (fully
matched reports), Round 3 (human review) or Gap Fill -- has exactly FINAL_COLUMNS, in this order. This is
the layout of output/final/final_all_batches_with_gapfill_20261028.csv, so earlier merged files and new
ones can be appended to each other directly.

    json_file .. actual_column_label   report-level facts (the same on every row of one report-year)
    top_category, hierarchy_id, level, parent_label, label_verbatim, value
                                       one decomposition line item. hierarchy_id is the key that
                                       identifies the indicator (1 = change in debt, 2 = identified
                                       flows, 3 = primary balance, 4 = automatic debt dynamics,
                                       5 = other identified flows, 6 = residual; 5.1 = first child of 5,
                                       and so on) -- it is kept as is from every source.
    source_round                       round1 / round2 / round3 / gapfill
    gapfill_run                        the Gap Fill STAMP that produced a gapfill row, blank otherwise

last_actual_year is the year the values are for: the report's own last actual year for Round 1-3 rows,
the gap year for Gap Fill rows.

to_final() turns any of the round CSVs (the 43-column compiled CSV, a check's matched rows, the human
review rows) or Gap Fill's values_long into this layout; it also tidies two number formats that pandas
leaves behind ("0.0" -> "0" for level, "65.0" -> "65" for page_pdf), so the same item reads the same in
every source.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, Optional

import pandas as pd

FINAL_COLUMNS = [
    "json_file", "pdf_file_name", "country", "publication_date", "consultation_type", "report_title",
    "country_report_number", "framework", "table_number", "table_title", "page_pdf", "last_actual_year",
    "actual_column_label", "top_category", "hierarchy_id", "level", "parent_label", "label_verbatim", "value",
    "source_round", "gapfill_run",
]
REPORT_COLUMNS = FINAL_COLUMNS[:FINAL_COLUMNS.index("top_category")]
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
    return out.reset_index(drop=True)


def concat_final(frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    frames = [f[FINAL_COLUMNS] for f in frames if f is not None and len(f)]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=FINAL_COLUMNS)


def check_final(df: pd.DataFrame) -> list:
    """Problems that would make rows unusable in the panel: wrong columns, a missing or malformed
    hierarchy_id, a top_category that does not match the id, the same line item twice."""
    problems = []
    if list(df.columns) != FINAL_COLUMNS:
        problems.append(f"columns differ from FINAL_COLUMNS: {list(df.columns)}")
        return problems
    hid = df["hierarchy_id"].astype(str).str.strip()
    bad = ~hid.str.match(HID_RE)
    if bad.any():
        problems.append(f"{int(bad.sum())} row(s) with a missing or malformed hierarchy_id")
    expect = hid.str.split(".").str[0].map(TOP_BY_ID)
    wrong = (~bad) & (expect != df["top_category"])
    if wrong.any():
        problems.append(f"{int(wrong.sum())} row(s) whose top_category does not match the hierarchy_id")
    dup = df.duplicated(["json_file", "last_actual_year", "hierarchy_id"], keep=False)
    if dup.any():
        problems.append(f"{int(dup.sum())} row(s) repeat the same (json_file, last_actual_year, hierarchy_id)")
    return problems
