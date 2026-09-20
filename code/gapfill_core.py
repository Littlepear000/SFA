"""
Pure logic for the gap-year fill run (no API, no PDF, no network).

Kept separate from gapfill_run_api.py so it can be unit-tested on any machine:
  * candidate report ordering (T+2 first, then T+3; latest report of a year first)
  * the resolve/cascade loop across rounds
  * validation that an extracted column is an ACTUAL / HISTORICAL year
  * flattening results and writing the output tables
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

from build_panel_gap_flags import normalize_country, parse_year_label

# ------------------------------------------------------------------ settings
OFFSETS = (2, 3)  # report year = gap year + 2, then + 3. Stop after that.
ELIGIBLE = {"actual", "historical"}
NOT_ACTUAL = {"preliminary", "estimate", "projection"}
ROLES = [
    "debt_level", "change_in_debt", "identified_flows", "primary_balance",
    "automatic_debt_dynamics", "other_identified_flows", "residual",
]
PANEL_ROLES = ROLES[1:]  # same six categories as the Step 1 flattening
RESOLVED = {"resolved", "resolved_with_warning"}
STOP_STATUSES = {"api_error", "not_run"}  # do not fall through to the next report
IDENTITY_TOLERANCE = 0.25

REASON_TO_STATUS = {
    "year_not_in_table": "year_not_in_table",
    "year_only_in_merged_range": "merged_range_only",
    "column_is_preliminary": "rejected_not_actual",
    "column_is_estimate": "rejected_not_actual",
    "column_is_projection": "rejected_not_actual",
    "status_unclear": "rejected_not_actual",
    "values_unreadable": "values_unreadable",
}

_STATUS_PATTERNS = {
    "preliminary": [r"\bprel\b", r"\bprel\.", r"\bpreliminary\b", r"\bprovisional\b"],
    "estimate": [r"\best\b", r"\best\.", r"\bestimate\b", r"\bestimated\b"],
    "projection": [
        r"\bproj\b", r"\bproj\.", r"\bprojection\b", r"\bprojections\b", r"\bforecast\b",
        r"\bmedium[- ]term projection\b", r"\bextended projection\b",
    ],
}


# ------------------------------------------------------------ report indexing
_FILE_RE = re.compile(r"^(?P<prefix>.*?)_(?P<date>\d{4}-\d{2}-\d{2})")


def parse_report_file(path: Path) -> Optional[Dict[str, Any]]:
    m = _FILE_RE.match(path.name)
    if not m:
        return None
    date = m.group("date")
    return {
        "pdf_file_name": path.name,
        "path": str(path),
        "country": normalize_country(m.group("prefix")),
        "date": date,
        "year": int(date[:4]),
    }


def index_by_country_year(reports: List[Dict[str, Any]]) -> Dict[Tuple[str, int], List[Dict[str, Any]]]:
    idx: Dict[Tuple[str, int], List[Dict[str, Any]]] = {}
    seen = set()
    for r in reports:
        if r["pdf_file_name"] in seen:
            continue
        seen.add(r["pdf_file_name"])
        idx.setdefault((r["country"], r["year"]), []).append(r)
    return idx


def build_candidates(
    country: str,
    gap_year: int,
    idx: Dict[Tuple[str, int], List[Dict[str, Any]]],
    skip: set,
    offsets: Tuple[int, ...] = OFFSETS,
) -> List[Dict[str, Any]]:
    """Ordered source reports for one gap year: T+2 (latest first), then T+3."""
    out: List[Dict[str, Any]] = []
    for off in offsets:
        reps = sorted(
            idx.get((country, gap_year + off), []),
            key=lambda r: (r["date"], r["pdf_file_name"]),
            reverse=True,
        )
        for r in reps:
            if r["pdf_file_name"] in skip:
                continue
            out.append({**r, "offset": off})
    return out


# ---------------------------------------------------------------- validation
def classify_header_text(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    for status, patterns in _STATUS_PATTERNS.items():
        if any(re.search(p, text, flags=re.I) for p in patterns):
            return status
    if re.search(r"\bactual\b|\boutturn\b|\bfinal\b", text):
        return "actual"
    if re.search(r"\bhistorical\b|\bhistory\b", text):
        return "historical"
    return "unknown"


def to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    s = str(x).strip().replace(",", "").replace("−", "-").replace("–", "-")
    try:
        return float(s)
    except ValueError:
        return None


def role_value(decomp: Optional[Dict[str, Any]], role: str) -> Optional[float]:
    node = (decomp or {}).get(role)
    return to_float(node.get("value")) if isinstance(node, dict) else None


def _audit_single_year_columns(source: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    audit = (source or {}).get("column_header_audit") or {}
    cols = audit.get("columns") if isinstance(audit, dict) else None
    out = []
    for c in cols or []:
        if not isinstance(c, dict):
            continue
        kind, y0, _y1, _ = parse_year_label(c.get("year_label"))
        out.append({
            "kind": kind, "year": y0,
            "label": c.get("year_label"),
            "status": str(c.get("status") or "unknown").strip().lower(),
        })
    return out


def identity_warnings(decomp: Optional[Dict[str, Any]]) -> List[str]:
    w = []
    chg, idf, res = (role_value(decomp, r) for r in ("change_in_debt", "identified_flows", "residual"))
    if None not in (chg, idf, res) and abs(chg - (idf + res)) > IDENTITY_TOLERANCE:
        w.append(f"identity change_in_debt = identified_flows + residual fails: {chg} vs {round(idf + res, 3)}")
    pb, ad, oth = (role_value(decomp, r) for r in ("primary_balance", "automatic_debt_dynamics", "other_identified_flows"))
    if None not in (idf, pb, ad, oth) and abs(idf - (pb + ad + oth)) > 1.5 * IDENTITY_TOLERANCE:
        w.append(f"identity identified_flows = primary + automatic + other fails: {idf} vs {round(pb + ad + oth, 3)}")
    return w


def validate_target(
    target: Dict[str, Any], source: Optional[Dict[str, Any]]
) -> Tuple[str, List[Tuple[str, str]], List[str]]:
    """
    Check one model answer for one target year.

    Returns (status, errors, warnings); errors is a list of (code, message).
    status is 'resolved' when there are no errors. 'needs_independent_audit' is
    returned only when the sole problem is that the model's own column audit is
    missing or disagrees; every other problem is a hard rejection, because the
    panel must never receive a preliminary, estimate or projection value.
    """
    year = target.get("target_year")
    if target.get("extractable") is not True:
        reason = target.get("not_extractable_reason")
        return REASON_TO_STATUS.get(reason, "not_extracted"), [], []

    errors: List[Tuple[str, str]] = []
    warnings: List[str] = []

    status = str(target.get("column_status") or "").strip().lower()
    if status not in ELIGIBLE:
        errors.append(("status", f"column_status is '{status or 'missing'}', not actual/historical"))

    kind, y0, _y1, _ = parse_year_label(target.get("matched_year_label"))
    if kind != "single" or y0 != year:
        errors.append(("label", f"matched_year_label '{target.get('matched_year_label')}' is not target year {year}"))

    header_text = " ".join(
        str(target.get(k) or "") for k in ("column_header_verbatim", "matched_year_label")
    )
    explicit = classify_header_text(header_text)
    if explicit in NOT_ACTUAL:
        errors.append(("header_text", f"header text is explicitly {explicit}: {header_text.strip()!r}"))

    cols = _audit_single_year_columns(source)
    matching = [c for c in cols if c["kind"] == "single" and c["year"] == year]
    if len(matching) != 1:
        errors.append(("audit_missing", f"column audit lists {len(matching)} single-year columns for {year}"))
    else:
        audit_status = matching[0]["status"]
        if audit_status not in ELIGIBLE:
            errors.append(("audit_status", f"column audit says {year} is '{audit_status}'"))
        elif status in ELIGIBLE and audit_status != status:
            warnings.append(f"column_status '{status}' differs from audit status '{audit_status}' (both eligible)")
    later_not_actual = [
        c for c in cols if c["kind"] == "single" and c["year"] is not None and c["year"] < year and c["status"] in NOT_ACTUAL
    ]
    if later_not_actual:
        errors.append((
            "monotonic",
            f"year {year} is called actual but an earlier column ({later_not_actual[0]['label']}) is {later_not_actual[0]['status']}",
        ))

    decomp = target.get("decomposition")
    if not isinstance(decomp, dict) or all(role_value(decomp, r) is None for r in PANEL_ROLES):
        errors.append(("no_values", "no numeric value found in any of the six decomposition roles"))
    else:
        warnings.extend(identity_warnings(decomp))

    if not errors:
        return "resolved", [], warnings
    if all(code in {"audit_missing", "audit_status"} for code, _ in errors) and status in ELIGIBLE:
        return "needs_independent_audit", errors, warnings
    return "rejected_not_actual", errors, warnings


def audit_confirms(audit_result: Dict[str, Any], year: int) -> Tuple[bool, str]:
    """Independent header audit: is `year` a single, actual/historical column?"""
    cols = _audit_single_year_columns({"column_header_audit": (audit_result or {}).get("column_header_audit")})
    matching = [c for c in cols if c["kind"] == "single" and c["year"] == year]
    if len(matching) != 1:
        return False, f"independent audit lists {len(matching)} single-year columns for {year}"
    status = matching[0]["status"]
    if status not in ELIGIBLE:
        return False, f"independent audit says {year} is '{status}'"
    if any(c["kind"] == "single" and c["year"] is not None and c["year"] < year and c["status"] in NOT_ACTUAL for c in cols):
        return False, "independent audit shows an earlier year that is estimate/projection"
    return True, f"independent audit confirms {year} as {status}"


# ------------------------------------------------------------------- cascade
def run_cascade(
    gap_items: List[Dict[str, Any]],
    candidates_fn: Callable[[str, int], List[Dict[str, Any]]],
    process_fn: Callable[[Dict[str, Any], List[int]], Dict[int, Dict[str, Any]]],
    max_workers: int = 4,
    log: Callable[[str], None] = print,
) -> List[Dict[str, Any]]:
    """
    Try each gap year's candidate reports in order until one gives an
    actual/historical value. One call per report per wave, covering every gap
    year of that country that is pointed at that report in this wave.
    """
    state = []
    for g in gap_items:
        cands = candidates_fn(g["country"], int(g["gap_year"]))
        state.append({
            **g, "gap_year": int(g["gap_year"]), "cands": cands, "next": 0,
            "attempts": [], "final_status": None, "resolved": None, "stopped": None,
        })

    wave_no = 0
    while True:
        wave: Dict[str, Tuple[Dict[str, Any], List[Dict[str, Any]]]] = {}
        for st in state:
            if st["final_status"] is not None:
                continue
            if st["next"] >= len(st["cands"]):
                st["final_status"] = "unresolved" if st["cands"] else "unresolved_no_candidate_reports"
                continue
            rep = st["cands"][st["next"]]
            wave.setdefault(rep["pdf_file_name"], (rep, []))[1].append(st)
        if not wave:
            break
        wave_no += 1
        log(f"Wave {wave_no}: {len(wave)} report(s) for {sum(len(v[1]) for v in wave.values())} gap year(s)")

        jobs = {name: (rep, sorted({s["gap_year"] for s in sts})) for name, (rep, sts) in wave.items()}

        def _run(item):
            name, (rep, years) = item
            try:
                return name, process_fn(rep, years)
            except Exception as exc:  # never lose the whole wave to one report
                return name, {y: {"status": "api_error", "errors": [str(exc)], "warnings": []} for y in years}

        if max_workers > 1 and len(jobs) > 1:
            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                results = dict(ex.map(_run, jobs.items()))
        else:
            results = dict(_run(i) for i in jobs.items())

        for name, (rep, sts) in wave.items():
            res = results[name]
            for st in sts:
                out = res.get(st["gap_year"]) or {"status": "not_run", "errors": [], "warnings": []}
                st["attempts"].append({
                    "attempt_no": len(st["attempts"]) + 1,
                    "report": name,
                    "offset": rep["offset"],
                    "status": out["status"],
                    "errors": "; ".join(out.get("errors", [])),
                    "warnings": "; ".join(out.get("warnings", [])),
                })
                if out["status"] in RESOLVED:
                    st["final_status"] = out["status"]
                    st["resolved"] = {"report": name, "offset": rep["offset"], "outcome": out}
                elif out["status"] in STOP_STATUSES:
                    st["final_status"] = "pending_" + out["status"]
                    st["stopped"] = out["status"]
                else:
                    st["next"] += 1
    return state


# ---------------------------------------------------------------- flattening
def flatten_node(node, rows, top_category, level, parent_label, hierarchy_id):
    if not isinstance(node, dict):
        return
    rows.append({
        "top_category": top_category, "hierarchy_id": hierarchy_id, "level": level,
        "parent_label": parent_label,
        "label_verbatim": node.get("label_verbatim"), "value": node.get("value"),
    })
    children = node.get("children")
    if isinstance(children, list):
        for i, child in enumerate(children, start=1):
            flatten_node(child, rows, top_category, level + 1, node.get("label_verbatim"), f"{hierarchy_id}.{i}")


def flatten_decomposition(decomp: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for n, cat in enumerate(PANEL_ROLES, start=1):
        node = (decomp or {}).get(cat)
        if node is not None:
            flatten_node(node, rows, cat, 0, None, str(n))
    return rows


# ------------------------------------------------------------------- outputs
def write_outputs(
    state: List[Dict[str, Any]],
    targets_meta: Optional[pd.DataFrame],
    out_dir: Path,
    stamp: str,
    panel_csv: Optional[Path] = None,
) -> Dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: Dict[str, Path] = {}
    meta = {}
    if targets_meta is not None and len(targets_meta):
        meta = {(r["country"], int(r["gap_year"])): r for _, r in targets_meta.iterrows()}

    attempts, resolution, long_rows, wide_rows = [], [], [], []
    for st in state:
        for a in st["attempts"]:
            attempts.append({"gap_id": st.get("gap_id"), "country": st["country"], "gap_year": st["gap_year"], **a})
        m = meta.get((st["country"], st["gap_year"]))
        last = st["attempts"][-1] if st["attempts"] else {}
        res = st["resolved"]
        expected = None if m is None else m.get("audit_expected_source_report")
        resolution.append({
            "gap_id": st.get("gap_id"), "country": st["country"], "gap_year": st["gap_year"],
            "final_status": st["final_status"],
            "source_report": res["report"] if res else None,
            "source_offset_years": res["offset"] if res else None,
            "n_attempts": len(st["attempts"]),
            "candidate_reports": "; ".join(c["pdf_file_name"] for c in st["cands"]),
            "last_failure_status": None if res else last.get("status"),
            "last_failure_detail": None if res else last.get("errors"),
            "warnings": res["outcome"].get("warnings") and "; ".join(res["outcome"]["warnings"]) if res else None,
            "audit_fill_status": None if m is None else m.get("audit_fill_status"),
            "audit_expected_source_report": expected,
            "source_matches_audit_expectation": (None if not (res and isinstance(expected, str)) else res["report"] == expected),
        })
        if res:
            out = res["outcome"]
            decomp = out.get("decomposition")
            meta_src = out.get("meta", {})
            for r in flatten_decomposition(decomp):
                long_rows.append({"country": st["country"], "year": st["gap_year"], "source_report": res["report"], **r})
            wide_rows.append({
                "country": st["country"], "year": st["gap_year"], "gap_id": st.get("gap_id"),
                "source_report": res["report"], "source_offset_years": res["offset"],
                "resolution_status": st["final_status"],
                "column_status": out.get("column_status"),
                "column_header_verbatim": out.get("column_header_verbatim"),
                "framework": meta_src.get("framework"), "units_verbatim": meta_src.get("units_verbatim"),
                "table_number": meta_src.get("table_number"), "page_pdf": meta_src.get("page_pdf"),
                "confidence": meta_src.get("confidence"),
                "warnings": "; ".join(out.get("warnings", [])),
                **{c: role_value(decomp, c) for c in PANEL_ROLES},
            })

    def save(name, rows):
        p = out_dir / f"{name}_{stamp}.csv"
        pd.DataFrame(rows).to_csv(p, index=False, encoding="utf-8-sig")
        paths[name] = p

    save("gapfill_attempts", attempts)
    save("gapfill_resolution", resolution)
    save("gapfill_values_long", long_rows)
    save("gapfill_values_wide", wide_rows)

    if panel_csv is not None and Path(panel_csv).exists() and wide_rows:
        panel = pd.read_csv(panel_csv)
        wide = pd.DataFrame(wide_rows).set_index(["country", "year"])
        for idx, row in panel.iterrows():
            key = (row["country"], row["year"])
            if row["status"] == "GAP" and key in wide.index:
                w = wide.loc[key]
                panel.loc[idx, "status"] = "FILLED"
                panel.loc[idx, "source_report"] = w["source_report"]
                for c in PANEL_ROLES:
                    panel.loc[idx, c] = w[c]
        p = out_dir / f"panel_structure_filled_{stamp}.csv"
        panel.to_csv(p, index=False, encoding="utf-8-sig")
        paths["panel_structure_filled"] = p
    return paths
