"""
[3c_gapfill_3] Call the internal API to read and fill each gap year's data from later reports.
    Step 3 | run by hand | needs the original staff-report PDFs (STAFF_REPORTS_DIR) and the internal API

Purpose
    For each gap year T in Step 2's list, try candidate reports in order, stopping at the first hit:
        the report published in year T+2 (if there is more than one that year, try the latest first,
        then earlier ones)
        -> the report published in year T+3 (again, latest first)
        -> the report published in year T+4 (again, latest first)
    Read the column for year T in these reports' DSA decomposition tables. Only actual / historical
    columns are accepted; preliminary / estimate / projection are never accepted. If T+4 also fails to
    yield the year, the gap is marked unresolved and no further years (T+5, ...) are tried.

    The candidate universe is every real PDF under STAFF_REPORTS_DIR -- batch-agnostic (a T+2/T+3/T+4
    candidate from an adjacent batch's subfolder is found exactly the same way as one from the batch
    being checked) and independent of whether Step 1 ever successfully located a table in it in any
    repeated run. For each candidate actually tried: if Step 1 already produced a selected PDF for it
    (found in SELECTED_PDF_DIRS), that cached selection is reused (the fast path, no extra API call);
    otherwise this step locates the DSA table fresh from the original PDF itself (one extra locator API
    call, using 1a's own locate + size-fallback machinery, reused via STEP1_SCRIPT) and builds its own
    selected-pages subset, cached under OUTPUT_DIR/fresh_selected_pdf/ so a later gap year or a resumed
    run for the same report does not locate it twice.

Input (paths set in the CONFIG below)
    TARGETS_CSV, SKIP_CSV     the two CSVs from Step 2
    STAFF_REPORTS_DIR         root of the ORIGINAL staff-report PDFs, one subfolder per batch (e.g.
                              staff_reports/pdf staff reports/2016-2020/...). The candidate universe.
    SELECTED_PDF_DIRS         one selected_pdf_pages folder per batch, built by
                              discover_selected_pdf_dirs() from the output/ folder itself rather than a
                              hand-maintained list -- it handles both output/<batch>/selected_pdf_pages/
                              directly and output/<batch>/round1_<stamp>_run1/selected_pdf_pages/, since
                              different people's machines have produced either layout; see that
                              function's own docstring for the exact preference order. Only the
                              fast-path cache, not the candidate universe. A selected PDF's file name is
                              <country>_<date>[_CR number]<any suffix>.pdf; it is matched to a report by
                              the leading country_date(_CR number) part, and the suffix can be anything
                              (e.g. _pages_5_8, _page_6_table_crop_fallback). The json_output folder next
                              to each of these folders (or the folder above it) should hold Step 1's
                              <report>_timing.json, used to determine which PDF was actually sent to the
                              API at the time, the page mapping, and the rendering method.
    STEP1_PROMPT_FILE         the Step 1 prompt file (its SUBPROMPT 1, the locator, only -- used for a
                              fresh locate when no cached selected PDF exists)
    GAPFILL_PROMPT_FILE       gapfill_extraction_prompt_v2.txt (the extraction prompt, used in both the
                              cached and the fresh-locate path)
    STEP1_SCRIPT, ENV_FILE    the Step 1 script (reused for its API auth / retry / call functions, and
                              for its locate + size-fallback PDF functions) and .env
    PANEL_CSV (optional)      Step 1's panel_structure, used to build the filled-in panel

Output (OUTPUT_DIR = output/gapfill/<batch>_<STAMP>/)
    reports/<report>_gapfill.json       one per report that was called: the model's raw answer and the
                                        validation result for each target year (also the resume cache)
    gapfill_checkpoint_<STAMP>.json     the full cascade state (which candidate each gap year is on,
                                        every attempt so far, final_status) -- written after every wave,
                                        not just at the end. A killed console, a lost network connection,
                                        or a laptop sleeping mid-run all just pause this file's progress;
                                        nothing is lost except whatever call was in flight at that moment,
                                        and that one call becomes api_error on the specific gap year(s) it
                                        covered (see run_cascade's STOP_STATUSES) -- it is retried, not the
                                        whole run. Re-running with the same OUTPUT_DIR + STAMP reads this
                                        checkpoint and only re-tries gap years not already RESOLVED there.
    fresh_selected_pdf/                 selected-pages PDFs this step located itself (no cache existed);
                                        reused on a later run instead of re-locating
    gapfill_resolution_<STAMP>.csv      the final result for each gap year (resolved / resolved_with_warning /
                                        unresolved ...) and its source report -- rewritten after every wave,
                                        so it reflects real progress while a long run is still going, not
                                        only once everything finishes
    gapfill_attempts_<STAMP>.csv        a record of each attempt: which report, what status, failure reason
    gapfill_values_long_<STAMP>.csv     the extracted values, long format (including child-item level)
    gapfill_values_wide_<STAMP>.csv     the extracted values, wide format (the six top-level variables)
    panel_structure_filled_<STAMP>.csv  the panel with its GAP rows filled in (needs PANEL_CSV)
    RUN_SUMMARY_<STAMP>.json            a summary of the results

Core steps
    1. Read targets and skip, scan STAFF_REPORTS_DIR for the candidate universe, and build the
       candidate-report order for each gap year (T+2 -> T+3 -> T+4, skipping reports listed in skip).
    2. Process in waves: in each wave, the gap years that currently land on the same report are merged
       into a single API call.
    3. For each report: find a cached selected PDF in SELECTED_PDF_DIRS (preferring the one recorded in
       timing.json as actually sent at the time; when there is no timing.json, by priority direct page
       selection > compressed image > table crop > full-page compressed image); if none exists, locate
       the DSA table fresh from the original PDF (1a's own locator prompt, falling back to keyword
       matching on a locator API error, then the same table-crop / visual-fallback cascade 1a uses if the
       selected pages are too large) -- either way, call the API with the gap-fill prompt, with the
       target years in the request. A report whose original PDF cannot be found on disk at all is
       recorded as selected_pdf_not_found; one whose table genuinely cannot be located (cached or fresh)
       is recorded as no_dsa_table_in_source; either way the next report is tried.
    4. Actual validation: the column status must be actual / historical; the header text must not contain
       Prel. / Est. / Proj.; the status for that year in the model's own list of year columns must be
       compliant; it must not be the case that an earlier year is projection while the target year is
       actual. A second, independent header check is only sent when the model's own list of year columns
       is missing this year, or contradicts its own answer. Failing validation -> the next report is tried.
    5. Each report's result is cached in reports/*.json: resuming after an interruption does not re-call
       the API; a report whose call errored is not cached, so a rerun retries it automatically. A selected
       PDF that, together with this step's prompt, exceeds the gateway's request-body limit is recorded as
       pdf_too_large and the next report is tried.
    6. On top of that per-report cache, gap years already RESOLVED in a previous run (read from
       gapfill_checkpoint_<STAMP>.json, if it exists for this OUTPUT_DIR + STAMP) are skipped before the
       cascade even starts -- a rerun only walks the gap years that are not yet done.
    7. The summary files are (re)written after every wave, not only once everything finishes.

Usage (set up CONFIG first)
    python 3c_gapfill_3_run_api.py --dry-run                     list the planned calls and check that every
                                                                  selected PDF can be found; no API call
                                                                  (do this first)
    python 3c_gapfill_3_run_api.py --limit-gaps 5                run only the first 5 gap years (a small
                                                                  pilot run, to check the output JSON)
    python 3c_gapfill_3_run_api.py --countries "Angola,Chile"    run only the given countries
    python 3c_gapfill_3_run_api.py                               full run
    python 3c_gapfill_3_run_api.py --collect-only                no API call; rebuild the summary files
                                                                  from the already-saved JSON

gapfill_lib_core.py must be in the same folder (imported by this script; not meant to be run on its own).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import time
from pathlib import Path, PureWindowsPath
from typing import Any, Dict, List, Optional

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
sys.path.insert(0, str(HERE))
# A long-lived IPython/Spyder console keeps gapfill_lib_core cached in sys.modules across repeated runs
# of this script via 0_run_gapfill.py -- without this, a code change (e.g. a git pull) would not take
# effect until the console itself is restarted. Reload it in place before importing it.
if "gapfill_lib_core" in sys.modules:
    importlib.reload(sys.modules["gapfill_lib_core"])
try:
    import gapfill_lib_core as core  # noqa: E402
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        f"{exc}. gapfill_lib_core.py must be in the same folder as this script; "
        f"looked in {HERE}. In a console, first run  %cd <path to the code folder>  or set HERE by hand."
    ) from exc

# =============================================================== CONFIG (edit)
# BASE_DIR = Path(r"C:\Users\xli7\OneDrive - International Monetary Fund (PRD)\Shelley_My Projects\SFA")
#
# # Root of the ORIGINAL staff-report PDFs, one subfolder per batch -- the candidate universe (same
# # config as 3b's STAFF_REPORTS_DIR; keep the two in sync). A T+2/T+3/T+4 candidate is any real PDF found
# # anywhere under here, whether or not Step 1 ever located a table in it in any run, and regardless of
# # which batch subfolder it is actually in.
# STAFF_REPORTS_DIR = BASE_DIR / "staff_reports" / "pdf staff reports"
#
# # One "selected_pdf_pages" source per batch, auto-discovered under output/ (same config as 3b's
# # SELECTED_PDF_DIRS -- keep the two in sync). Handles both output/<batch>/selected_pdf_pages/ directly
# # and output/<batch>/round1_<stamp>_run1/selected_pdf_pages/, which differ across people's machines;
# # see discover_selected_pdf_dirs()'s own docstring for the exact preference order. Only used for the
# # FAST path: a candidate report with no selected PDF here is not skipped -- it is located fresh from
# # STAFF_REPORTS_DIR instead (one extra locator API call).
# SELECTED_PDF_DIRS: List[Path] = core.discover_selected_pdf_dirs(BASE_DIR / "output")
#
# STEP1_SCRIPT = HERE / "1a_two_step_selected_pdf_inline_base64_cropfallback_summary_v7_header_aware_crop_effort.py"
# # 1a (not 2a/round2's pipeline) on purpose: gap-fill only needs call_pdf_json / make_api_session /
# # add_table_crop_header_instruction / extract_full_text / create_uploadable_subset and the rest of the
# # locate+select machinery, identical (or not needed for choosing last_actual_year) in both; 2a's extra
# # accuracy is specifically about *choosing* last_actual_year, which gap-fill never does (the target
# # year is already given).
# STEP1_PROMPT_FILE = BASE_DIR / "two_step_selected_pdf_prompt_table_only_cropfallback_v5_flexible_actual.txt"
# # Only SUBPROMPT 1 (the locator) is used from this file, for a fresh locate when no cached selected PDF
# # exists; SUBPROMPT 2 (1a's own extraction prompt) is never used -- GAPFILL_PROMPT_FILE below is used
# # for extraction instead, on whichever selected PDF (cached or freshly located) is sent.
# GAPFILL_PROMPT_FILE = BASE_DIR / "gapfill_extraction_prompt_v2.txt"
# ENV_FILE = BASE_DIR / ".env"
#
# STAMP = "20260920_v2"  # must match the STAMP of 3a / 3b
# CHECK_DIR = BASE_DIR / "output" / "2016-2020" / "gap_year_check"
# TARGETS_CSV = CHECK_DIR / f"gapfill_targets_{STAMP}.csv"
# SKIP_CSV = CHECK_DIR / f"gapfill_skip_reports_{STAMP}.csv"
# PANEL_CSV: Optional[Path] = CHECK_DIR / f"panel_structure_country_year_{STAMP}.csv"  # None = do not build the filled panel
# OUTPUT_DIR = BASE_DIR / "output" / "gapfill" / f"2016-2020_{STAMP}"
#
# MAX_WORKERS = 4
# ==============================================================================

SIZE_PHRASES = [
    "maximum allowed size", "request entity too large", "error 413",
    "above the configured base64-safe limit", "too close to or above the 1 mb gateway limit",
]

# The selected-PDF indexing helpers (parse_selected_name, index_selected_pdfs, reports_from_selected)
# and the T+2/T+3/T+4 candidate-map builder now live in gapfill_lib_core.py, shared with 3b (which persists
# the candidate map before any API call) -- see core.index_selected_pdfs / core.reports_from_selected.


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


# parse_selected_name / index_selected_pdfs now live in gapfill_lib_core.py (core.*), shared with 3b.


def read_timing(selected_dir: Path, stem: str) -> Optional[Dict[str, Any]]:
    """Step 1's <report>_timing.json: in "json_output" next to the selected folder (current layout),
    or directly in the folder above it (older layout)."""
    for p in (selected_dir.parent / "json_output" / f"{stem}_timing.json", selected_dir.parent / f"{stem}_timing.json"):
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return None
    return None


def resolve_selected_pdf(stem: str, idx: Dict[str, List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    """
    The selected PDF to send for one report.
    1. The file Step 1's timing.json says was sent to the API (also gives the page mapping,
       rendering method and crop box). Folders are tried in SELECTED_PDF_DIRS order.
    2. Otherwise the best-fidelity selected PDF by file name (no page mapping available).
    """
    found = idx.get(stem, [])
    if not found:
        return None
    for dir_rank in sorted({f["dir_rank"] for f in found}):
        same_dir = [f for f in found if f["dir_rank"] == dir_rank]
        timing = read_timing(same_dir[0]["dir"], stem)
        sent = PureWindowsPath(str(timing.get("pdf_sent_to_api") or "")).name if timing else ""
        for f in same_dir:
            if sent and f["path"].name == sent:
                return {
                    "path": f["path"], "source": "timing", "method": timing.get("extraction_method") or f["method"],
                    "pages": timing.get("selected_original_pages"), "dpi": timing.get("vision_fallback_dpi"),
                    "quality": timing.get("vision_fallback_jpeg_quality"), "box": timing.get("table_crop_box_points"),
                }
    best = min(found, key=lambda f: (f["dir_rank"], f["method_rank"], f["path"].name))
    return {"path": best["path"], "source": "filename", "method": best["method"],
            "pages": None, "dpi": None, "quality": None, "box": None}


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
    def __init__(self, s1, url, token_manager, model, prompt, selected_index, prompt1=None, fresh_dir: Optional[Path] = None):
        self.s1, self.url, self.tm, self.model = s1, url, token_manager, model
        self.prompt, self.selected_index = prompt, selected_index
        self.prompt1, self.fresh_dir = prompt1, fresh_dir

    def _locate_and_select_fresh(self, pdf_path: Path, stem: str) -> Optional[Dict[str, Any]]:
        """
        No cached selected PDF exists for this report (Step 1 never located its DSA table in any run
        whose output is listed in SELECTED_PDF_DIRS -- including never having tried this report at all).
        Locate it fresh from the ORIGINAL PDF and build a selected-pages subset: the same locate +
        size-fallback cascade 1a's own process_pdf() runs, reusing its functions directly (self.s1), just
        without 1a's own extraction step or its own JSON outputs. Cached to self.fresh_dir so a later
        gap year or a resumed run for the same report does not locate it twice.

        Returns a sel dict shaped like resolve_selected_pdf()'s (path, source, method, pages, dpi,
        quality, box), or None if Step 1 still finds no DSA section in this report.
        """
        s1, fresh_dir = self.s1, self.fresh_dir
        fresh_dir.mkdir(parents=True, exist_ok=True)

        cached = (
            sorted(fresh_dir.glob(f"{stem}_pages_*.pdf"))
            + sorted(fresh_dir.glob(f"{stem}_page_*_table_crop_fallback.pdf"))
            + sorted(fresh_dir.glob(f"{stem}_pages_*_vision_fallback.pdf"))
        )
        if cached:
            p = cached[0]
            method = ("pymupdf_pillow_table_crop_fallback" if "table_crop_fallback" in p.name
                      else "pymupdf_pillow_visual_fallback" if "vision_fallback" in p.name
                      else "selected_pdf_direct")
            return {"path": p, "source": "fresh_locate_cached", "method": method,
                    "pages": None, "dpi": None, "quality": None, "box": None}

        no_dsa_marker = fresh_dir / f"{stem}_no_dsa.json"
        if no_dsa_marker.exists():
            return None

        print(f"  No cached selected PDF for {stem}; locating fresh from the original PDF...")
        full_text, pages = s1.extract_full_text(pdf_path)
        try:
            locator = s1.call_text_json(self.url, self.tm, self.model, self.prompt1, s1.prepare_step1_input(full_text, pdf_path.name))
        except Exception as exc:
            candidates = s1.keyword_candidates(pages)
            locator = {
                "dsa_section_found": bool(candidates),
                "primary_table_page": candidates[0]["start_page"] + 1 if candidates else None,
                "recommended_start_page": candidates[0]["start_page"] if candidates else None,
                "recommended_end_page": candidates[0]["end_page"] if candidates else None,
                "notes": f"Locator failed; keyword fallback used. Error: {exc}",
            }

        if not locator.get("dsa_section_found"):
            write_json(no_dsa_marker, {"notes": locator.get("notes")})
            return None

        total_pages = len(s1.PdfReader(str(pdf_path)).pages)
        start_page = max(1, int(locator["recommended_start_page"]))
        end_page = min(total_pages, int(locator["recommended_end_page"]))
        try:
            primary_page = int(locator.get("primary_table_page"))
        except (TypeError, ValueError):
            primary_page = (start_page + end_page) // 2
        if not (start_page <= primary_page <= end_page):
            primary_page = (start_page + end_page) // 2

        selected_pdf = fresh_dir / f"{stem}_pages_{start_page}_{end_page}.pdf"
        table_crop_pdf = fresh_dir / f"{stem}_page_{primary_page}_table_crop_fallback.pdf"
        visual_pdf = fresh_dir / f"{stem}_pages_{start_page}_{end_page}_vision_fallback.pdf"

        try:
            included, _ = s1.create_uploadable_subset(pdf_path, selected_pdf, start_page, end_page, primary_page)
            return {"path": selected_pdf, "source": "fresh_locate", "method": "selected_pdf_direct",
                    "pages": included, "dpi": None, "quality": None, "box": None}
        except Exception:
            pass

        try:
            included, _, dpi, quality, box = s1.create_table_crop_fallback_pdf(
                source_pdf=pdf_path, output_pdf=table_crop_pdf, primary_page=primary_page)
            return {"path": table_crop_pdf, "source": "fresh_locate", "method": "pymupdf_pillow_table_crop_fallback",
                    "pages": included, "dpi": dpi, "quality": quality, "box": box}
        except Exception:
            pass

        included, _, dpi, quality = s1.create_visual_fallback_pdf(
            source_pdf=pdf_path, output_pdf=visual_pdf, start_page=start_page, end_page=end_page, primary_page=primary_page)
        return {"path": visual_pdf, "source": "fresh_locate", "method": "pymupdf_pillow_visual_fallback",
                "pages": included, "dpi": dpi, "quality": quality, "box": None}

    def user_text(self, sel: Dict[str, Any], stem: str, country: str, report_date: str, years: List[int]) -> str:
        if sel["pages"]:
            mapping = "\n".join(
                f"Selected PDF page {i} = original physical PDF page {p}" for i, p in enumerate(sel["pages"], start=1)
            )
        else:
            mapping = "not available (leave page_pdf null)"
        text = (
            f"Original PDF file: {stem}.pdf\n"
            f"Selected PDF file: {sel['path'].name}\n"
            f"Input rendering method: {sel['method']}\n"
            f"Rendering DPI: {sel['dpi']}\n"
            f"JPEG quality: {sel['quality']}\n"
            f"Table crop box: {sel['box']}\n\n"
            f"ORIGINAL PHYSICAL PAGE MAPPING:\n{mapping}\n\n"
            "GAP-FILL REQUEST:\n"
            f"Country: {country}\n"
            f"Staff report file: {stem}.pdf (report date {report_date})\n"
            f"TARGET YEARS (extract each one, from ACTUAL or HISTORICAL columns only): {json.dumps(years)}\n"
        )
        return self.s1.add_table_crop_header_instruction(text, sel["method"])

    def __call__(self, report: Dict[str, Any], years: List[int]) -> Dict[int, Dict[str, Any]]:
        started = time.perf_counter()
        stem = Path(report["pdf_file_name"]).stem
        cached = cached_outcomes(stem, years)
        todo = [y for y in years if y not in cached]
        if not todo:
            return cached

        sel = resolve_selected_pdf(stem, self.selected_index)
        if sel is None:
            pdf_path = Path(report.get("path") or "") if report.get("path") else None
            if not pdf_path or not pdf_path.exists():
                return {**cached, **{y: {"status": "selected_pdf_not_found",
                        "errors": [f"no cached selected PDF, and the original PDF was not found at {pdf_path}"],
                        "warnings": []} for y in todo}}
            try:
                sel = self._locate_and_select_fresh(pdf_path, stem)
            except Exception as exc:
                return {**cached, **{y: {"status": "api_error", "errors": [f"fresh locate failed: {exc}"], "warnings": []} for y in todo}}
            if sel is None:
                return {**cached, **{y: {"status": "no_dsa_table_in_source",
                        "errors": ["Step 1 located no DSA section in the original PDF (no cache; fresh locate also found nothing)"],
                        "warnings": []} for y in todo}}

        prev = read_cache(stem)
        record: Dict[str, Any] = {
            "pdf_file_name": report["pdf_file_name"], "country": report["country"], "report_date": report["date"],
            "selected_pdf": str(sel["path"]), "selected_pdf_source": sel["source"],
            "extraction_method": sel["method"], "selected_original_pages": sel["pages"],
            "per_target": prev.get("per_target", {}), "calls": prev.get("calls", []),
        }
        outcomes: Dict[int, Dict[str, Any]] = dict(cached)
        try:
            outcomes.update(self._extract(sel, stem, report, todo, record))
        except Exception as exc:
            size_related = any(p in str(exc).lower() for p in SIZE_PHRASES)
            status = "pdf_too_large" if size_related else "api_error"
            for y in todo:
                outcomes[y] = {"status": status, "errors": [f"{type(exc).__name__}: {exc}"], "warnings": []}

        for y, o in outcomes.items():
            record["per_target"][str(y)] = o
        record["timing_seconds"] = round(time.perf_counter() - started, 2)
        write_json(report_json_path(stem), record)
        return outcomes

    def _extract(self, sel, stem, report, years, record) -> Dict[int, Dict[str, Any]]:
        s1 = self.s1
        user_text = self.user_text(sel, stem, report["country"], report["date"], years)
        model_out = s1.call_pdf_json(self.url, self.tm, self.model, self.prompt, user_text, sel["path"])
        record["calls"].append({"target_years": years, "model_output": model_out})

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
                audit = s1.call_pdf_json(self.url, self.tm, self.model, build_gapfill_audit_prompt(), user_text, sel["path"])
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
                    "confidence": source.get("confidence"), "extraction_method": sel["method"],
                },
            }
        return outcomes


# ------------------------------------------------------------------------ main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="list planned calls and check selected PDFs; no API")
    ap.add_argument("--collect-only", action="store_true", help="rebuild outputs from saved JSONs; no API")
    ap.add_argument("--limit-gaps", type=int, default=None, help="only the first N gap years (pilot)")
    ap.add_argument("--countries", type=str, default=None, help="comma-separated country names to run")
    args, _ = ap.parse_known_args()  # tolerant of extra args injected by IPython/Spyder

    targets = pd.read_csv(TARGETS_CSV)
    run = targets.copy()
    if args.countries:
        wanted = {c.strip() for c in args.countries.split(",")}
        run = run[run["country"].isin(wanted)]
    run = run.sort_values(["country", "gap_year"])
    if args.limit_gaps:
        run = run.head(args.limit_gaps)
    skip = set(pd.read_csv(SKIP_CSV)["pdf_file_name"]) if SKIP_CSV.exists() else set()

    print(f"Gap years selected: {len(run)} of {len(targets)}")
    # Candidate universe: every real PDF under STAFF_REPORTS_DIR (batch-agnostic, independent of whether
    # Step 1 ever located a table in it in any run). SELECTED_PDF_DIRS is only consulted later, per
    # candidate actually tried, to decide the fast cached path vs. a fresh locate.
    staff_reports = core.list_staff_reports(STAFF_REPORTS_DIR)
    idx = core.index_by_country_year(staff_reports)
    selected_index = core.index_selected_pdfs(SELECTED_PDF_DIRS)
    print(f"Real staff-report PDFs found under {STAFF_REPORTS_DIR}: {len(staff_reports)}; "
          f"reports never used as a source: {len(skip)}")

    def candidates_fn(country: str, year: int):
        return core.build_candidates(country, year, idx, skip)

    gap_items = run[["gap_id", "country", "gap_year"]].to_dict("records")

    if args.dry_run:
        first_wave, none, needs_fresh = set(), 0, 0
        for g in gap_items:
            c = candidates_fn(g["country"], int(g["gap_year"]))
            if not c:
                none += 1
            else:
                first_wave.add(c[0]["pdf_file_name"])
            print(f"  {g['gap_id']} {g['country']} {g['gap_year']}: " + (", ".join(f"[T+{x['offset']}] {x['pdf_file_name']}" for x in c[:4]) or "NO CANDIDATE REPORT"))
        by_timing = sum(1 for n in first_wave if (resolve_selected_pdf(Path(n).stem, selected_index) or {}).get("source") == "timing")
        needs_fresh = sum(1 for n in first_wave if resolve_selected_pdf(Path(n).stem, selected_index) is None)
        print(f"\nDry run: first wave = {len(first_wave)} API report call(s); gap years with no candidate report = {none}")
        print(f"Selected PDF identified from timing.json for {by_timing} of the {len(first_wave)} first-wave reports "
              f"(the rest fall back to file-name priority, without page mapping)")
        print(f"{needs_fresh} of the {len(first_wave)} first-wave reports have no cached selected PDF at all and "
              f"will be located fresh from the original PDF (one extra locator API call each)")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    if args.collect_only:
        process_fn = cache_only_process
        workers = 1
    else:
        s1 = load_step1()
        prompt1, _ = s1.load_two_subprompts(STEP1_PROMPT_FILE)
        prompt = GAPFILL_PROMPT_FILE.read_text(encoding="utf-8")
        url, tm, model = s1.make_api_session()
        print(f"Model: {model}")
        process_fn = ReportProcessor(s1, url, tm, model, prompt, selected_index,
                                      prompt1=prompt1, fresh_dir=OUTPUT_DIR / "fresh_selected_pdf")
        workers = MAX_WORKERS

    # Resume support: same OUTPUT_DIR + STAMP as an earlier, interrupted run (killed console, lost
    # network, laptop slept mid-call, ...) picks up its checkpoint -- only gap years not already
    # RESOLVED there are retried. A different STAMP (or no checkpoint yet) starts clean, as before.
    checkpoint_path = OUTPUT_DIR / f"gapfill_checkpoint_{STAMP}.json"
    prev_state = core.load_checkpoint(checkpoint_path)
    done_state = [s for s in prev_state if s.get("final_status") in core.RESOLVED]
    done_keys = {(s["country"], int(s["gap_year"])) for s in done_state}
    todo_items = [g for g in gap_items if (g["country"], int(g["gap_year"])) not in done_keys]
    if done_keys:
        print(f"Resuming from checkpoint {checkpoint_path.name}: {len(done_keys)} gap year(s) already "
              f"resolved, skipping. {len(todo_items)} of {len(gap_items)} remaining.")

    def on_progress(partial_state: List[Dict[str, Any]]) -> None:
        merged = done_state + partial_state
        core.save_checkpoint(merged, checkpoint_path)
        core.write_outputs(merged, targets, OUTPUT_DIR, STAMP, PANEL_CSV)

    new_state = core.run_cascade(todo_items, candidates_fn, process_fn, max_workers=workers, on_progress=on_progress)
    state = done_state + new_state
    core.save_checkpoint(state, checkpoint_path)
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
