"""
【3c_gapfill_3】调内部 API，到后续报告里读取 gap year 的数据并填补
    第 3 步 ｜ 手动运行 ｜ 需要 Step 1 已生成的 selected PDF pages 和内部 API

作用
    对第 2 步清单里的每个 gap year T，按顺序尝试，命中即停：
        T+2 年发布的报告（同一年有多份时，先试最晚的一份，再试更早的）
        -> T+3 年发布的报告（同样先最晚）
    在这些报告的 DSA 分解表里读取 T 年那一列。只接受 actual / historical 列，
    preliminary / estimate / projection 一律不要。T+3 也没取到就标 unresolved，不再往后试。

    本步骤不再读原始 staff report PDF，不再重新定位 DSA 表，也不再压缩 PDF：
    直接使用 Step 1 已经生成的 selected PDF pages（当时发给 API 的那份 PDF）。

Input（路径在下面的 CONFIG 里配置）
    TARGETS_CSV, SKIP_CSV     第 2 步的两个 CSV
    SELECTED_PDF_DIRS         Step 1 生成的 selected_pdf_pages 文件夹（可列多个批次；前面的优先）。
                              候选报告就是这些文件夹里已有 selected PDF 的报告。
                              selected PDF 的文件名 = <国家>_<日期>[_CR编号]<任意后缀>.pdf，按前面的 国家_日期(_CR编号)
                              与报告对应，后缀是什么都可以（如 _pages_5_8、_page_6_table_crop_fallback）
                              每个文件夹旁边的 json_output 文件夹（或上一级文件夹）里应有 Step 1 的 <报告名>_timing.json，
                              用来确定当时实际发给 API 的是哪份 PDF、页码对应关系和渲染方式
    GAPFILL_PROMPT_FILE       gapfill_extraction_prompt_v2.txt
    STEP1_SCRIPT, ENV_FILE    Step 1 脚本（复用它的 API 认证 / 重试 / 调用函数）和 .env
    PANEL_CSV（可选）         第 1 步的 panel_structure，用来生成填好的 panel

Output（OUTPUT_DIR = output/gapfill/<批次>_<STAMP>/）
    reports/<报告名>_gapfill.json       每份被调用的报告一个：模型原始回答和每个目标年份的校验结果（同时是断点续跑的缓存）
    gapfill_resolution_<STAMP>.csv      每个 gap year 的最终结果（resolved / resolved_with_warning / unresolved ...）及来源报告
    gapfill_attempts_<STAMP>.csv        每次尝试的记录：哪份报告、什么状态、失败原因
    gapfill_values_long_<STAMP>.csv     抽到的数值，长表（含子项层级）
    gapfill_values_wide_<STAMP>.csv     抽到的数值，宽表（六个一级变量）
    panel_structure_filled_<STAMP>.csv  把 GAP 行填上数据后的 panel（需要 PANEL_CSV）
    RUN_SUMMARY_<STAMP>.json            结果汇总

核心步骤
    1. 读 targets 和 skip，扫描 SELECTED_PDF_DIRS 里的 selected PDF，得到每个 gap year 的候选报告顺序
       （T+2 -> T+3，跳过 skip 里的报告）。
    2. 分轮处理：每一轮，把"这一轮正好轮到同一份报告"的多个 gap year 合并成一次 API 调用。
    3. 对每份报告：找到它的 selected PDF（优先按 timing.json 记录的、当时实际发送的那份；
       没有 timing.json 时按 直接选页 > 压缩图片 > 表格裁剪 > 整页压缩图 的优先级）-> 用 prompt v2 调 API，
       请求里带上目标年份。找不到 selected PDF 的报告记为 selected_pdf_not_found，直接换下一份报告。
    4. Actual 校验：列状态必须是 actual / historical；表头文字不能含 Prel. / Est. / Proj.；模型自己列出的
       年份列里该年状态必须合规；不能出现"更早的年份是 projection、目标年却是 actual"。
       只有当模型的年份列清单缺这一年、或与它的回答矛盾时，才再发一次独立表头核对。不通过 -> 换下一份报告。
    5. 每份报告的结果缓存在 reports/*.json：中断后重跑不会重复调用 API；API 报错的不缓存，重跑会自动重试。
       selected PDF 加上本步骤的 prompt 后请求体超过网关上限的，记为 pdf_too_large，换下一份报告。
    6. 全部结束后写出上面的汇总文件。

用法（先改好 CONFIG）
    python 3c_gapfill_3_run_api.py --dry-run                     只列出计划调用的报告，并检查 selected PDF 是否都找得到，不调 API（建议先做这个）
    python 3c_gapfill_3_run_api.py --limit-gaps 5                只跑前 5 个 gap year（小规模试跑，检查输出 JSON）
    python 3c_gapfill_3_run_api.py --countries "Angola,Chile"    只跑指定国家
    python 3c_gapfill_3_run_api.py                               全量运行
    python 3c_gapfill_3_run_api.py --collect-only                不调 API，用已保存的 JSON 重新生成汇总文件

同一文件夹里还需要 gapfill_lib_core.py（被本脚本导入，不用单独运行）。
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
try:
    import gapfill_lib_core as core  # noqa: E402
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        f"{exc}. gapfill_lib_core.py must be in the same folder as this script; "
        f"looked in {HERE}. In a console, first run  %cd <path to the code folder>  or set HERE by hand."
    ) from exc

# =============================================================== CONFIG (edit)
BASE_DIR = Path(r"C:\Users\xli7\OneDrive - International Monetary Fund (PRD)\Shelley_My Projects\SFA")

# Step 1's "selected_pdf_pages" folders, one per batch. The first folder that holds a report's
# selected PDF wins, so list re-run folders (e.g. .../2016-2020/rerun_20260910/selected_pdf_pages)
# BEFORE the original ones. The Step 1 "<report>_timing.json" files are expected in the folder
# above each of these (or in a "json_output" folder next to it).
SELECTED_PDF_DIRS: List[Path] = [
    BASE_DIR / "output" / "2011-2015" / "round1_20260921_run1" / "selected_pdf_pages",
    BASE_DIR / "output" / "2016-2020" / "round2_20260921_run1" / "selected_pdf_pages",
    BASE_DIR / "output" / "2016-2020" / "round1_20260921_run1" / "selected_pdf_pages",
    BASE_DIR / "output" / "2021-2026" / "round1_20260921_run1" / "selected_pdf_pages",
]

STEP1_SCRIPT = HERE / "2a_step_1_revised_on_problematic_reports_sl.py"
GAPFILL_PROMPT_FILE = BASE_DIR / "gapfill_extraction_prompt_v2.txt"
ENV_FILE = BASE_DIR / ".env"

STAMP = "20260920_v2"  # must match the STAMP of 3a / 3b
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

# A selected PDF is named "<report stem><any suffix>.pdf". The report stem is "<country>_<YYYY-MM-DD>",
# optionally followed by a Country Report number ("_CR2019-283"). Whatever comes after (_pages_5_8,
# _page_6_table_crop_fallback, or anything else) is only used to guess how the PDF was made.
_STEM_RE = re.compile(r"^(?P<stem>.+?_\d{4}-\d{2}-\d{2}(?:_CR\d{4}-\d+)?)(?P<suffix>_.*)?\.pdf$", re.IGNORECASE)
# Best fidelity first (used only when there is no timing.json to say which file was sent).
_METHOD_ORDER = [
    "selected_pdf_direct", "selected_pdf_image_compressed",
    "pymupdf_pillow_table_crop_fallback", "pymupdf_pillow_visual_fallback",
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


# ------------------------------------------------------- selected PDF lookup
def parse_selected_name(name: str):
    """(report stem, method) for a selected-PDF file name, else None if it has no <country>_<date> part."""
    m = _STEM_RE.match(name)
    if not m:
        return None
    suffix = (m.group("suffix") or "").lower()
    if "crop" in suffix:
        method = "pymupdf_pillow_table_crop_fallback"
    elif "vision" in suffix or "visual" in suffix:
        method = "pymupdf_pillow_visual_fallback"
    elif "compress" in suffix:
        method = "selected_pdf_image_compressed"
    else:
        method = "selected_pdf_direct"
    return m.group("stem"), method


def index_selected_pdfs(dirs: List[Path]) -> Dict[str, List[Dict[str, Any]]]:
    """stem -> selected PDFs found in `dirs` (each with its folder rank and method rank)."""
    idx: Dict[str, List[Dict[str, Any]]] = {}
    for dir_rank, d in enumerate(dirs):
        if not d.exists():
            print(f"  WARNING: selected-PDF folder not found: {d}")
            continue
        ignored = []
        for p in sorted(d.glob("*.pdf")):
            parsed = parse_selected_name(p.name)
            if parsed:
                stem, method = parsed
                idx.setdefault(stem, []).append(
                    {"path": p, "method": method, "dir": d, "dir_rank": dir_rank,
                     "method_rank": _METHOD_ORDER.index(method)}
                )
            else:
                ignored.append(p.name)
        if ignored:
            print(f"  WARNING: {len(ignored)} PDF(s) in {d} have no <country>_<YYYY-MM-DD> in the name and are ignored, e.g. {ignored[:3]}")
    return idx


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
    def __init__(self, s1, url, token_manager, model, prompt, selected_index):
        self.s1, self.url, self.tm, self.model = s1, url, token_manager, model
        self.prompt, self.selected_index = prompt, selected_index

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
            return {**cached, **{y: {"status": "selected_pdf_not_found", "errors": ["no selected PDF found for this report"], "warnings": []} for y in todo}}

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
def reports_from_selected(idx: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """One report record (country, date, year from the file name) per report that has a selected PDF."""
    reports = []
    for stem in sorted(idx):
        rec = core.parse_report_file(Path(stem + ".pdf"))
        if rec:
            reports.append(rec)
    return reports


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
    selected_index = index_selected_pdfs(SELECTED_PDF_DIRS)
    reports = reports_from_selected(selected_index)
    idx = core.index_by_country_year(reports)
    print(f"Reports with a selected PDF: {len(reports)} in {len(SELECTED_PDF_DIRS)} folder(s); reports never used as a source: {len(skip)}")

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
        by_timing = sum(1 for n in first_wave if (resolve_selected_pdf(Path(n).stem, selected_index) or {}).get("source") == "timing")
        print(f"\nDry run: first wave = {len(first_wave)} API report call(s); gap years with no candidate report = {none}")
        print(f"Selected PDF identified from timing.json for {by_timing} of the {len(first_wave)} first-wave reports (the rest fall back to file-name priority, without page mapping)")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    if args.collect_only:
        process_fn = cache_only_process
        workers = 1
    else:
        s1 = load_step1()
        prompt = GAPFILL_PROMPT_FILE.read_text(encoding="utf-8")
        url, tm, model = s1.make_api_session()
        print(f"Model: {model}")
        process_fn = ReportProcessor(s1, url, tm, model, prompt, selected_index)
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
