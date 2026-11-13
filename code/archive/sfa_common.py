"""
Shared helpers used across the SFA pipeline (no API, no network).

    normalize_country()   one canonical country name for every spelling seen in PDF file names / the data
    parse_year_label()    a year column label (2019, 2012/13, FY2012, ...) -> (kind, y0, y1, note)
    load_rows()           read the merged final CSV: one effective year per row, numeric value,
                          normalized country (used by check_coverage_database.py)

Moved here from gapfill_lib_core.py (now core.py) and gapfill_panel_coverage_report.py (archived) so
that scripts outside Gap Fill do not depend on Gap Fill's code. core.py re-exports the first two, so
core.normalize_country / core.parse_year_label still work.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

# ------------------------------------------------ country names and year labels
_ALIASES = {
    "cote d'ivoire": "Côte d'Ivoire",
    "côte d'ivoire": "Côte d'Ivoire",
    "democratic republic of sao tome and principe": "São Tomé and Príncipe",
    "democratic republic of são tomé and príncipe": "São Tomé and Príncipe",
    "democratic republic of são tomé": "São Tomé and Príncipe",  # truncated in some PDF file names
    "democratic republic of sao tome": "São Tomé and Príncipe",
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
    # same country under an older / alternative official name
    "cape verde": "Cabo Verde",
    "turkey": "Türkiye",
    "democratic republic of congo": "Democratic Republic of the Congo",
    "principality of andorra": "Andorra",
    "principality of liechtenstein": "Liechtenstein",
}
_REPUBLIC_OF = re.compile(r"^republic of (.+)$", re.I)


def normalize_country(raw: str) -> str:
    """Canonical country label from the PDF-filename prefix."""
    s = str(raw).strip().replace("’", "'")
    # "Türki̇ye" spelled with a combining dot above the i (U+0307, what lower-casing "İ" produces) vs plain
    # "Türkiye"; "St.Vincent" vs "St. Vincent" -- otherwise each spelling becomes a separate country.
    s = s.replace("\u0130", "I").replace("\u0307", "")
    s = re.sub(r"\bSt\.(?=\S)", "St. ", s)
    s = re.sub(r"[–—]+", "-", s)
    s = re.sub(r"\s*-\s*", "-", s)
    s = re.sub(r"^the\s+", "", s, flags=re.I)
    low = s.lower()
    m = re.match(r"^people's republic of china-(.+)$", low)
    if m:
        return "Hong Kong SAR, China" if "hong kong" in m.group(1) else "Macao SAR, China"
    m = re.match(r"^kingdom of (?:the )?netherlands?-(.+)$", low)  # "Netherland-" / "Kingdom Of Netherlands-" variants
    if m:
        t = re.sub(r"^the\s+", "", m.group(1))  # the part after the dash can itself start with "the "
        if t == "netherlands":
            return "Netherlands"
        if t == "aruba":
            return "Aruba"
        return "Curaçao and Sint Maarten"
    if re.match(r"^kingdom of (?:the )?netherlands?$", low):
        return "Netherlands"
    if low in _ALIASES:
        return _ALIASES[low]
    m = _REPUBLIC_OF.match(s)
    if m:
        rest = m.group(1).strip()
        return _ALIASES.get(rest.lower(), rest)  # e.g. "Republic of Turkey" -> "Türkiye"
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


# ------------------------------------------------------------------ merged final CSV
FIELDS = {"6": "residual", "5": "other_identified_flows"}
# values within this far apart are treated as the same observation re-reported, not a genuine conflict
# (e.g. a typo-level rounding difference), well inside the identity-check tolerance used elsewhere
VALUE_TOLERANCE = 0.05


def _parsed_year(label: str) -> float:
    """y1 (the single year, or a fiscal-year label's end year) from parse_year_label() above, or
    NaN if unparseable. A pandas-missing cell reads back as the float NaN here, not the string "nan" --
    `pd.Series.fillna("")` upstream is what prevents the classic `nan or default` truthiness trap (NaN is
    truthy in Python, so a bare `or` never falls through to the fallback column)."""
    kind, _y0, y1, _note = parse_year_label(label)
    return float(y1) if kind != "invalid" else float("nan")


ALL_HIERARCHIES = object()  # sentinel for load_rows(): no hierarchy_id filter at all


def load_rows(input_csv: Path, hierarchy_ids=FIELDS) -> pd.DataFrame:
    """hierarchy_ids: an iterable of hierarchy_id values to keep (default: FIELDS, i.e. residual +
    other_identified_flows only), or ALL_HIERARCHIES to keep every row regardless of hierarchy_id (used
    e.g. by check_coverage_database.py)."""
    # "year" (gap-fill rows' own year) and "gapfill_run" only exist in some versions of the merged file;
    # the slim 20261026+ files keep a gap-fill row's year in last_actual_year instead.
    wanted = ["country", "hierarchy_id", "value", "year", "last_actual_year", "source_round", "gapfill_run"]
    present = set(pd.read_csv(input_csv, nrows=0).columns)
    df = pd.read_csv(input_csv, usecols=[c for c in wanted if c in present], dtype=str)
    for c in ("year", "gapfill_run"):
        if c not in df.columns:
            df[c] = None
    if hierarchy_ids is not ALL_HIERARCHIES:
        df = df[df["hierarchy_id"].isin(hierarchy_ids)].copy()
    else:
        df = df.copy()

    year_s = df["year"].fillna("").str.strip()
    lay_s = df["last_actual_year"].fillna("").str.strip()
    effective_label = year_s.where(year_s != "", lay_s)  # year if present, else last_actual_year
    df["effective_year"] = effective_label.map(_parsed_year)

    df["value_num"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["effective_year", "value_num"])
    df["effective_year"] = df["effective_year"].astype(int)

    df["country_norm"] = df["country"].map(lambda c: normalize_country(str(c).strip()))
    df["country_key"] = df["country_norm"].str.casefold()
    # canonical display label per casefold group: the most common normalized spelling seen for it
    label_by_key = (
        df.groupby("country_key")["country_norm"]
        .agg(lambda s: s.value_counts().idxmax())
    )
    df["country_label"] = df["country_key"].map(label_by_key)
    return df
