"""
Gap-year fill run: read the DSA column of a missing year from a LATER staff
report through the internal AI API.

For every gap year T the script tries, in this order, and stops at the first
report that shows T as an ACTUAL / HISTORICAL column:
    reports published in year T+2 (latest report first), then
    reports published in year T+3 (latest report first).
If T+3 also fails the gap year is left "unresolved" (no T+4).

Runs on the IMF machine (needs the staff-report PDFs, the internal API and the
Step 1 script). Reuses the Step 1 machinery: authentication, retries, PDF
size ladder (direct -> image-compressed -> table crop -> full-page image) and,
where the file still exists, the saved Step 1 locator JSON, so the page-finding
API call is skipped.

Before running: edit the CONFIG block below, then

    python gapfill_run_api.py --dry-run                 # list what would be called, no API
    python gapfill_run_api.py --limit-gaps 5            # small pilot
    python gapfill_run_api.py                           # full run (resumable)
    python gapfill_run_api.py --collect-only            # rebuild outputs from saved JSONs, no API

Inputs (made offline by gapfill_build_targets.py): the targets CSV and the skip CSV.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gapfill_core as core  # noqa: E402

# =============================================================== CONFIG (edit)
BASE_DIR = Path(r"C:\Users\xli7\OneDrive - International Monetary Fund (PRD)\Shelley_My Projects\SFA")

# Every folder that holds staff-report PDFs. Add or remove batches freely; PDFs are
# found by file name, so a report may live in any of them.
PDF_FOLDERS: List[Path] = [
    BASE_DIR / "staff_reports" / "pdf staff reports" / "2011-2015",
    BASE_DIR / "staff_reports" / "pdf staff reports" / "2016-2020",
    BASE_DIR / "staff_reports" / "pdf staff reports" / "2021-2026",
]

# Folders holding the saved Step 1 "<report>_step1_locator.json" files. If a report has
# none, the locator is run again (needs STEP1_PROMPT_FILE).
LOCATOR_DIRS: List[Path] = [
    BASE_DIR / "output" / "json_dsa" / "2011-2015",
    BASE_DIR / "output" / "json_dsa" / "2016-2020",
    BASE_DIR / "output" / "json_dsa" / "2021-2026",
]

STEP1_SCRIPT = Path(__file__).resolve().parent / "step_1_revised_on_problematic_reports_sl.py"
STEP1_PROMPT_FILE = BASE_DIR / "sl_revised_prompt_step_one.txt"      # only used to re-run a locator
GAPFILL_PROMPT_FILE = BASE_DIR / "gapfill_extraction_prompt_v1.txt"
ENV_FILE = BASE_DIR / ".env"

STAMP = "20260918_v1"
CHECK_DIR = BASE_DIR / "output" / "2016-2020" / "gap_year_check"
TARGETS_CSV = CHECK_DIR / f"gapfill_targets_{STAMP}.csv"
SKIP_CSV = CHECK_DIR / f"gapfill_skip_reports_{STAMP}.csv"
PANEL_CSV: Optional[Path] = CHECK_DIR / f"panel_structure_country_year_{STAMP}.csv"  # None = do not build the filled panel
OUTPUT_DIR = BASE_DIR / "output" / "gapfill" / f"2016-2020_{STAMP}"

MAX_WORKERS = 4
# ==============================================================================

SIZE_PHRASES = [
    "maximum allowed size", "request entity too large", "error 413",
    "above the configured base64-safe limit", "too close to or above the 1 mb gateway limit",
]


def build_gapfill_audit_prompt() -> str:
    return (
        "INDEPENDENT HEADER AUDIT ONLY\n\n"
        "Inspect the complete multi-level column header of the qualifying PUBLIC DSA decomposition table in the "
        "attached PDF. Do not extract any rows or values. Do not assume any earlier answer is right or wrong.\n"
        "List EVERY visible year column from left to right. Status vocabulary: actual, historical, preliminary, "
        "estimate, projection, unknown. A merged span such as 2002-2010 is one column with its own label. A "
        "two-part label such as 2015/16 stands for its end year. Use the group headings, separators, spacing and "
        "table notes; if the status cannot be established use unknown.\n"
        "Return ONLY this JSON object:\n"
        '{"column_header_audit": {"columns": [{"position": 1, "year_label": "", "group_label": null, '
        '"status": "actual", "status_basis": ""}]}, "issues": []}\n'
    )


def load_step1():
    spec = importlib.util.spec_from_file_location("step1_module", str(STEP1_SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["step1_module"] = mod
    spec.loader.exec_module(mod)
    mod.ENV_FILE = ENV_FILE
    return mod


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


# ---------------------------------------------------------------- cache utils
def report_json_path(stem: str) -> Path:
    return OUTPUT_DIR / "reports" / f"{stem}_gapfill.json"


def read_cache(stem: str) -> Dict[str, Any]:
    p = report_json_path(stem)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def cached_outcomes(stem: str, years: List[int]) -> Dict[int, Dict[str, Any]]:
    per = read_cache(stem).get("per_target", {})
    out = {}
    for y in years:
        o = per.get(str(y))
        if o and o.get("status") not in core.STOP_STATUSES:
            out[y] = o
    return out


def cache_only_process(report: Dict[str, Any], years: List[int]) -> Dict[int, Dict[str, Any]]:
    stem = Path(report["pdf_file_name"]).stem
    got = cached_outcomes(stem, years)
    return {y: got.get(y, {"status": "not_run", "errors": [], "warnings": []}) for y in years}


# ------------------------------------------------------------------ processor
class ReportProcessor:
    def __init__(self, s1, url, token_manager, model, prompt, prompt1):
        self.s1, self.url, self.tm, self.model = s1, url, token_manager, model
        self.prompt, self.prompt1 = prompt, prompt1
        self.work_dir = OUTPUT_DIR / "selected_pdf_pages"
        self.work_dir.mkdir(parents=True, exist_ok=True)

    # -- locator ------------------------------------------------------------
    def get_locator(self, stem: str, pdf_path: Path):
        for d in LOCATOR_DIRS + [OUTPUT_DIR / "locators"]:
            p = d / f"{stem}_step1_locator.json"
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8")), f"saved:{p}"
        s1 = self.s1
        full_text, pages = s1.extract_full_text(pdf_path)
        try:
            locator = s1.call_text_json(
                self.url, self.tm, self.model, self.prompt1, s1.prepare_step1_input(full_text, pdf_path.name)
            )
        except Exception as exc:
            cands = s1.keyword_candidates(pages)
            locator = {
                "report_metadata": {"pdf_file_name": pdf_path.name},
                "dsa_section_found": bool(cands), "framework_hint": "UNKNOWN", "candidates": cands,
                "primary_table_page": cands[0]["start_page"] + 1 if cands else None,
                "recommended_start_page": cands[0]["start_page"] if cands else None,
                "recommended_end_page": cands[0]["end_page"] if cands else None,
                "confidence": "low", "notes": f"Locator failed; keyword fallback used. Error: {exc}",
            }
        write_json(OUTPUT_DIR / "locators" / f"{stem}_step1_locator.json", locator)
        return locator, "rerun"

    # -- PDF preparation ladder --------------------------------------------
    def prepare(self, level: str, pdf_path: Path, stem: str, start: int, end: int, primary: int):
        s1 = self.s1
        if level == "direct":
            out = self.work_dir / f"{stem}_pages_{start}_{end}.pdf"
            pages, _removed = s1.create_uploadable_subset(pdf_path, out, start, end, primary)
            return {"path": out, "method": "selected_pdf_direct", "pages": pages, "dpi": None, "quality": None, "box": None}
        if level == "image_compressed":
            if not hasattr(s1, "create_image_compressed_fallback_pdf"):
                raise RuntimeError("image-compression fallback not available in this Step 1 script")
            out = self.work_dir / f"{stem}_pages_{start}_{end}_image_compressed.pdf"
            pages, _removed = s1.create_image_compressed_fallback_pdf(
                source_pdf=pdf_path, output_pdf=out, start_page=start, end_page=end, primary_page=primary
            )
            return {"path": out, "method": "selected_pdf_image_compressed", "pages": pages, "dpi": None, "quality": None, "box": None}
        if level == "table_crop":
            out = self.work_dir / f"{stem}_page_{primary}_table_crop_fallback.pdf"
            pages, _r, dpi, quality, box = s1.create_table_crop_fallback_pdf(
                source_pdf=pdf_path, output_pdf=out, primary_page=primary
            )
            return {"path": out, "method": "pymupdf_pillow_table_crop_fallback", "pages": pages, "dpi": dpi, "quality": quality, "box": box}
        out = self.work_dir / f"{stem}_pages_{start}_{end}_vision_fallback.pdf"
        pages, _removed, dpi, quality = s1.create_visual_fallback_pdf(
            source_pdf=pdf_path, output_pdf=out, start_page=start, end_page=end, primary_page=primary
        )
        return {"path": out, "method": "pymupdf_pillow_visual_fallback", "pages": pages, "dpi": dpi, "quality": quality, "box": None}

    def user_text(self, prep, pdf_path, locator, country, report_date, years) -> str:
        mapping = "\n".join(
            f"Selected PDF page {i} = original physical PDF page {p}" for i, p in enumerate(prep["pages"], start=1)
        )
        text = (
            f"Original PDF file: {pdf_path.name}\n"
            f"Selected PDF file: {prep['path'].name}\n"
            f"Input rendering method: {prep['method']}\n"
            f"Rendering DPI: {prep['dpi']}\n"
            f"JPEG quality: {prep['quality']}\n"
            f"Table crop box: {prep['box']}\n\n"
            f"ORIGINAL PHYSICAL PAGE MAPPING:\n{mapping}\n\n"
            f"STEP 1 LOCATOR OUTPUT:\n{json.dumps(locator, indent=2, ensure_ascii=False)}\n\n"
            "GAP-FILL REQUEST:\n"
            f"Country: {country}\n"
            f"Staff report file: {pdf_path.name} (report date {report_date})\n"
            f"TARGET YEARS (extract each one, from ACTUAL or HISTORICAL columns only): {json.dumps(years)}\n"
        )
        return self.s1.add_table_crop_header_instruction(text, prep["method"])

    # -- one report -----------------------------------------------------------
    def __call__(self, report: Dict[str, Any], years: List[int]) -> Dict[int, Dict[str, Any]]:
        started = time.perf_counter()
        pdf_path = Path(report["path"])
        stem = pdf_path.stem
        cached = cached_outcomes(stem, years)
        todo = [y for y in years if y not in cached]
        if not todo:
            return cached
        if not pdf_path.exists():
            return {**cached, **{y: {"status": "pdf_not_found", "errors": [str(pdf_path)], "warnings": []} for y in todo}}

        prev = read_cache(stem)
        record: Dict[str, Any] = {
            "pdf_file_name": pdf_path.name, "country": report["country"], "report_date": report["date"],
            "per_target": prev.get("per_target", {}), "calls": prev.get("calls", []),
        }
        outcomes: Dict[int, Dict[str, Any]] = dict(cached)
        try:
            locator, loc_src = self.get_locator(stem, pdf_path)
            record["locator_source"] = loc_src
            if not locator.get("dsa_section_found"):
                for y in todo:
                    outcomes[y] = {"status": "no_dsa_table", "errors": ["Step 1 locator found no public DSA"], "warnings": []}
            else:
                outcomes.update(self._extract(pdf_path, stem, report, locator, todo, record))
        except Exception as exc:
            for y in todo:
                outcomes[y] = {"status": "api_error", "errors": [f"{type(exc).__name__}: {exc}"], "warnings": []}

        for y, o in outcomes.items():
            record["per_target"][str(y)] = o
        record["timing_seconds"] = round(time.perf_counter() - started, 2)
        write_json(report_json_path(stem), record)
        return outcomes

    def _extract(self, pdf_path, stem, report, locator, years, record) -> Dict[int, Dict[str, Any]]:
        s1 = self.s1
        total_pages = len(s1.PdfReader(str(pdf_path)).pages)
        start = max(1, int(locator["recommended_start_page"]))
        end = min(total_pages, int(locator["recommended_end_page"]))
        try:
            primary = int(locator.get("primary_table_page"))
        except (TypeError, ValueError):
            primary = (start + end) // 2
        if not (start <= primary <= end):
            primary = (start + end) // 2

        notes: List[str] = []
        model_out = prep = user_text = None
        for level in ("direct", "image_compressed", "table_crop", "visual"):
            try:
                prep = self.prepare(level, pdf_path, stem, start, end, primary)
            except Exception as exc:
                notes.append(f"{level}: not usable ({exc})")
                continue
            user_text = self.user_text(prep, pdf_path, locator, report["country"], report["date"], years)
            try:
                model_out = s1.call_pdf_json(self.url, self.tm, self.model, self.prompt, user_text, prep["path"])
                break
            except Exception as exc:
                if any(p in str(exc).lower() for p in SIZE_PHRASES):
                    notes.append(f"{level}: rejected for size ({exc})")
                    continue
                raise
        if model_out is None:
            raise RuntimeError("no PDF preparation level produced an uploadable file: " + " | ".join(notes))

        record["calls"].append({
            "target_years": years, "extraction_method": prep["method"], "selected_original_pages": prep["pages"],
            "table_crop_box_points": prep["box"], "ladder_notes": notes, "model_output": model_out,
        })

        if not model_out.get("table_found"):
            reason = model_out.get("failure_reason")
            return {y: {"status": "no_dsa_table", "errors": [f"model: table_found=false ({reason})"], "warnings": []} for y in years}

        source = model_out.get("source") or {}
        by_year: Dict[int, Dict[str, Any]] = {}
        for t in model_out.get("targets") or []:
            try:
                by_year[int(t.get("target_year"))] = t
            except (TypeError, ValueError):
                continue

        outcomes: Dict[int, Dict[str, Any]] = {}
        for y in years:
            t = by_year.get(y)
            if t is None:
                outcomes[y] = {"status": "not_extracted", "errors": ["model returned no entry for this year"], "warnings": []}
                continue
            t["target_year"] = y
            status, errors, warnings = core.validate_target(t, source)
            err_msgs = [m for _c, m in errors]
            if status == "needs_independent_audit":
                audit = s1.call_pdf_json(self.url, self.tm, self.model, build_gapfill_audit_prompt(), user_text, prep["path"])
                record.setdefault("independent_audits", {})[str(y)] = audit
                ok, msg = core.audit_confirms(audit, y)
                if ok:
                    status = "resolved_with_warning"
                    warnings = warnings + err_msgs + [msg]
                    err_msgs = []
                else:
                    status = "rejected_not_actual"
                    err_msgs = err_msgs + [msg]
            outcomes[y] = {
                "status": status, "errors": err_msgs, "warnings": warnings,
                "column_status": t.get("column_status"),
                "column_header_verbatim": t.get("column_header_verbatim"),
                "not_extractable_reason": t.get("not_extractable_reason"),
                "decomposition": t.get("decomposition") if status in core.RESOLVED else None,
                "unmapped_rows": t.get("unmapped_rows") if status in core.RESOLVED else None,
                "notes": t.get("notes"),
                "meta": {
                    "framework": source.get("framework"), "units_verbatim": source.get("units_verbatim"),
                    "table_number": source.get("table_number"), "page_pdf": source.get("page_pdf"),
                    "confidence": source.get("confidence"), "extraction_method": prep["method"],
                },
            }
        return outcomes


# ------------------------------------------------------------------------ main
def scan_reports() -> List[Dict[str, Any]]:
    reports = []
    for folder in PDF_FOLDERS:
        if not folder.exists():
            print(f"  WARNING: PDF folder not found: {folder}")
            continue
        for p in sorted(folder.glob("*.pdf")):
            rec = core.parse_report_file(p)
            if rec:
                reports.append(rec)
    return reports


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="scan PDFs and list planned calls; no API")
    ap.add_argument("--collect-only", action="store_true", help="rebuild outputs from saved JSONs; no API")
    ap.add_argument("--limit-gaps", type=int, default=None, help="only the first N gap years (pilot)")
    ap.add_argument("--countries", type=str, default=None, help="comma-separated country names to run")
    args = ap.parse_args()

    targets = pd.read_csv(TARGETS_CSV)
    run = targets[targets["run_flag"].astype(str).str.lower() == "true"].copy()
    if args.countries:
        wanted = {c.strip() for c in args.countries.split(",")}
        run = run[run["country"].isin(wanted)]
    run = run.sort_values(["country", "gap_year"])
    if args.limit_gaps:
        run = run.head(args.limit_gaps)
    skip = set(pd.read_csv(SKIP_CSV)["pdf_file_name"]) if SKIP_CSV.exists() else set()

    print(f"Gap years selected: {len(run)} (held out in targets file: {int((targets['run_flag'].astype(str).str.lower() != 'true').sum())})")
    reports = scan_reports()
    idx = core.index_by_country_year(reports)
    print(f"PDFs found: {len(reports)} in {len(PDF_FOLDERS)} folder(s); reports never used as a source: {len(skip)}")

    def candidates_fn(country: str, year: int):
        return core.build_candidates(country, year, idx, skip)

    gap_items = run[["gap_id", "country", "gap_year"]].to_dict("records")

    if args.dry_run:
        first_wave, none = set(), 0
        for g in gap_items:
            c = candidates_fn(g["country"], int(g["gap_year"]))
            if not c:
                none += 1
            else:
                first_wave.add(c[0]["pdf_file_name"])
            print(f"  {g['gap_id']} {g['country']} {g['gap_year']}: " + (", ".join(f"[T+{x['offset']}] {x['pdf_file_name']}" for x in c[:4]) or "NO CANDIDATE REPORT"))
        print(f"\nDry run: first wave = {len(first_wave)} API report call(s); gap years with no candidate report = {none}")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    if args.collect_only:
        process_fn = cache_only_process
        workers = 1
    else:
        s1 = load_step1()
        prompt = GAPFILL_PROMPT_FILE.read_text(encoding="utf-8")
        prompt1 = s1.load_two_subprompts(STEP1_PROMPT_FILE)[0] if STEP1_PROMPT_FILE.exists() else ""
        url, tm, model = s1.make_api_session()
        print(f"Model: {model}")
        process_fn = ReportProcessor(s1, url, tm, model, prompt, prompt1)
        workers = MAX_WORKERS

    state = core.run_cascade(gap_items, candidates_fn, process_fn, max_workers=workers)
    paths = core.write_outputs(state, targets, OUTPUT_DIR, STAMP, PANEL_CSV)

    counts: Dict[str, int] = {}
    for st in state:
        counts[st["final_status"]] = counts.get(st["final_status"], 0) + 1
    summary = {"gap_years": len(state), "final_status_counts": counts,
               "runtime_seconds": round(time.perf_counter() - started, 1),
               "outputs": {k: str(v) for k, v in paths.items()}}
    write_json(OUTPUT_DIR / f"RUN_SUMMARY_{STAMP}.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
