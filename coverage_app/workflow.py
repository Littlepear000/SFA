"""
The Workflow part of the web app: run Round 1 / Round 2 / Gap Fill from the browser, review the results
of each round, do the human review (Round 3), and build the panel database.

Everything here reads and writes the same folders the scripts already use, so a run started from the app
and one started from a 0_run_*.py controller look the same:

    output/<batch>/round1_<VERSION>_run<N>/        one run of Round 1 (json_output, selected_pdf_pages, compiled_csv)
    output/<batch>/round1_check_<VERSION>/         the comparison of the runs (1c, 1d)
    output/<batch>/round2_<VERSION>_run<N>/        Round 2, same layout
    output/<batch>/round2_check_<VERSION>/
    output/<batch>/round3_review_<VERSION>/        human review of the Round 2 check <VERSION>:
        reviews/<report>.json                      one file per reviewed report (what you typed)
        round3_reviewed_rows_<VERSION>.csv          all reviewed rows, in the panel database layout
    output/gapfill/gap_year_check/panel_<STAMP>/   Gap Fill steps 1-2 (4a, 4b)
    output/gapfill/output/panel_<STAMP>/           Gap Fill step 3 (4c); gapfill_rows_final_<STAMP>.csv
    output/panel_database/panel_database_<STAMP>.csv (+ .json)   the panel database, one file per version
    output/workflow/settings.json                  the Workflow settings
    output/workflow/jobs/<id>/                     one folder per job: spec.json, status.json, log.txt
    output/workflow/records/                       what each round version / gap fill run was started with

A version of a round is the 8-digit date given when it is started (e.g. 20261113), as in the controllers.
Jobs run one at a time, in a separate process (coverage_app/runner.py), so a long API run keeps going
while you browse, and it can be stopped from the page.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

APP_DIR = Path(__file__).resolve().parent
BASE = APP_DIR.parent
CODE_DIR = BASE / "code"
PROMPT_DIR = BASE / "prompt"
OUTPUT = BASE / "output"
WF_DIR = OUTPUT / "workflow"
JOBS_DIR = WF_DIR / "jobs"
RECORDS_DIR = WF_DIR / "records"
PANEL_DIR = OUTPUT / "panel_database"
GAP_CHECK_ROOT = OUTPUT / "gapfill" / "gap_year_check"
GAP_OUT_ROOT = OUTPUT / "gapfill" / "output"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))
import final_schema as fs  # noqa: E402

VERSION_RE = re.compile(r"^[A-Za-z0-9_\-]{1,40}$")
ROUNDS = ("round1", "round2")

DEFAULTS = {
    "pdf_dir": "staff_reports/pdf staff reports/2021-2026",
    "batch": "",                      # empty = the name of the PDF folder
    "staff_reports_root": "staff_reports/pdf staff reports",
    "env_file": ".env",
    "csv_prefix": "sl",
    "python": "",                     # empty = the Python running the app
    "round1": {"extract_script": "1a_two_step_selected_pdf_inline_base64_cropfallback_summary_v7_header_aware_crop_effort.py",
               "compile_script": "1b_json_to_excel_dsa_v6_flexible_actual.py",
               "check_script": "1c_round_check_compare_runs.py",
               "summary_script": "1d_round_check_summary.py",
               "prompt": "1a_two_step_selected_pdf_prompt_table_only_cropfallback_v5_flexible_actual.txt",
               "n_runs": 3},
    "round2": {"extract_script": "2a_dsa_pipeline_260924.py",
               "compile_script": "1b_json_to_excel_dsa_v6_flexible_actual.py",
               "check_script": "1c_round_check_compare_runs.py",
               "summary_script": "1d_round_check_summary.py",
               "prompt": "2a_dsa_prompt_20260924.txt",
               "n_runs": 3},
    "gapfill": {"flags_script": "4a_gapfill_1_build_panel_gap_flags.py",
                "targets_script": "4b_gapfill_2_build_targets.py",
                "api_script": "4c_gapfill_3_run_api.py",
                "prompt": "4c_gapfill_extraction_prompt_v2.txt",
                "locator_script": "1a_two_step_selected_pdf_inline_base64_cropfallback_summary_v7_header_aware_crop_effort.py",
                "locator_prompt": "1a_two_step_selected_pdf_prompt_table_only_cropfallback_v5_flexible_actual.txt",
                "year_from": 2001, "year_to": 2025, "max_workers": 4},
}


class UserError(Exception):
    """A problem to show in the page as is (bad input, missing file ...)."""


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def today() -> str:
    return datetime.now().strftime("%Y%m%d")


def read_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path: Path, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    tmp.replace(path)


def proj_path(p) -> Path:
    """A path from the settings: absolute as is, relative = relative to the project folder."""
    p = Path(str(p or "").strip().strip('"'))
    return p if p.is_absolute() else BASE / p


def safe_name(s: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", str(s))


def clean(v):
    """JSON-safe cell: NaN -> None."""
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    return v


def read_csv(path: Path, **kw) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, encoding="utf-8-sig", keep_default_na=False, na_values=[""], **kw)


# ======================================================================= settings
def _merge(base: dict, over: dict) -> dict:
    out = json.loads(json.dumps(base))
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


def load_settings() -> dict:
    return _merge(DEFAULTS, read_json(WF_DIR / "settings.json", {}) or {})


def save_settings(body: dict) -> dict:
    s = _merge(load_settings(), body or {})
    for r in ("round1", "round2"):
        s[r]["n_runs"] = int(s[r]["n_runs"])
        if not 2 <= s[r]["n_runs"] <= 10:
            raise UserError("The number of runs must be between 2 and 10 (the runs are compared with each other).")
    write_json(WF_DIR / "settings.json", s)
    return s


def batch_name(s: dict) -> str:
    return (s.get("batch") or "").strip() or proj_path(s["pdf_dir"]).name


def python_exe(s: dict) -> str:
    return (s.get("python") or "").strip() or sys.executable


def list_code() -> list:
    return sorted(p.name for p in CODE_DIR.glob("*.py") if not p.name.startswith(("_", ".")))


def list_prompts() -> list:
    return sorted(p.name for p in PROMPT_DIR.iterdir() if p.is_file() and p.suffix in (".txt", ".md")) if PROMPT_DIR.is_dir() else []


def settings_info() -> dict:
    s = load_settings()
    pdf_dir, root, env = proj_path(s["pdf_dir"]), proj_path(s["staff_reports_root"]), proj_path(s["env_file"])
    info = {
        "project": str(BASE), "batch": batch_name(s), "python": python_exe(s),
        "pdf_dir": {"path": str(pdf_dir), "exists": pdf_dir.is_dir(),
                    "n_pdfs": len(list(pdf_dir.glob("*.pdf"))) if pdf_dir.is_dir() else 0},
        "staff_reports_root": {"path": str(root), "exists": root.is_dir()},
        "env_file": {"path": str(env), "exists": env.is_file()},
        "output_dir": str(OUTPUT / batch_name(s)),
    }
    return {"settings": s, "info": info, "code_files": list_code(), "prompt_files": list_prompts(), "today": today()}


def read_source(kind: str, name: str) -> dict:
    folder = {"code": CODE_DIR, "prompt": PROMPT_DIR}.get(kind)
    if folder is None or not name or "/" in name or "\\" in name or name.startswith("."):
        raise UserError("unknown file")
    path = folder / name
    if not path.is_file():
        raise UserError(f"{name} not found in {folder}")
    st = path.stat()
    return {"name": name, "path": str(path), "size": st.st_size,
            "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
            "text": path.read_text(encoding="utf-8", errors="replace")}


# ======================================================================= jobs
def _pid_alive(pid: int) -> bool:
    if not pid:
        return False
    if os.name == "nt":
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


class Jobs:
    """One job at a time. A job is a folder under output/workflow/jobs/ (spec.json, job.json, status.json,
    log.txt); its process is coverage_app/runner.py."""

    def __init__(self):
        self.lock = threading.Lock()
        self.proc = None
        self.current = None  # job id

    def _job(self, job_id: str) -> dict | None:
        d = JOBS_DIR / job_id
        meta = read_json(d / "job.json")
        if meta is None:
            return None
        st = read_json(d / "status.json", {}) or {}
        state = st.get("state") or "starting"
        if state in ("running", "starting"):
            alive = (self.proc is not None and self.current == job_id and self.proc.poll() is None) or \
                    (self.current != job_id and _pid_alive(meta.get("pid")))
            if not alive:
                if meta.get("stopped"):
                    state = "stopped"
                else:
                    rc = self.proc.poll() if (self.proc is not None and self.current == job_id) else None
                    state = "error" if rc not in (None, 0) else ("interrupted" if state == "running" else "error")
                    if not st.get("error"):
                        st["error"] = "The job's process ended without finishing (stopped, or the app was closed)."
        return {**meta, **{k: v for k, v in st.items() if k != "state"}, "state": state}

    def running(self) -> dict | None:
        with self.lock:
            if self.current:
                j = self._job(self.current)
                if j and j["state"] in ("running", "starting"):
                    return j
            for d in sorted(JOBS_DIR.glob("*"), reverse=True)[:5] if JOBS_DIR.is_dir() else []:
                j = self._job(d.name)
                if j and j["state"] in ("running", "starting"):
                    return j
        return None

    def start(self, stage: str, title: str, steps: list, params: dict, links: dict, must_not_exist=(), python=None) -> dict:
        if self.running():
            raise UserError("Another job is still running. Wait for it to finish, or stop it first.")
        job_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + stage
        d = JOBS_DIR / job_id
        d.mkdir(parents=True, exist_ok=True)
        spec = {"id": job_id, "title": title, "code_dir": str(CODE_DIR), "steps": steps,
                "must_not_exist": [str(p) for p in must_not_exist]}
        write_json(d / "spec.json", spec)
        meta = {"id": job_id, "stage": stage, "title": title, "params": params, "links": links,
                "created": now(), "n_steps": len(steps), "steps": [s["label"] for s in steps]}
        log = open(d / "log.txt", "w", encoding="utf-8")
        env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
        kw = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        with self.lock:
            self.proc = subprocess.Popen([python or sys.executable, str(APP_DIR / "runner.py"), str(d / "spec.json")],
                                         cwd=str(BASE), stdout=log, stderr=subprocess.STDOUT, env=env, **kw)
            self.current = job_id
        log.close()
        meta["pid"] = self.proc.pid
        write_json(d / "job.json", meta)
        return self.get(job_id)

    def stop(self) -> dict:
        j = self.running()
        if not j:
            raise UserError("No job is running.")
        meta = read_json(JOBS_DIR / j["id"] / "job.json")
        meta["stopped"] = now()
        write_json(JOBS_DIR / j["id"] / "job.json", meta)
        pid = meta.get("pid")
        try:
            if os.name == "nt":
                subprocess.call(["taskkill", "/PID", str(pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
        except OSError:
            pass
        time.sleep(0.5)
        return self.get(j["id"])

    def get(self, job_id: str, log_lines: int = 400) -> dict:
        with self.lock:
            j = self._job(job_id)
        if j is None:
            raise UserError("job not found")
        try:
            text = (JOBS_DIR / job_id / "log.txt").read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        lines = text.splitlines()
        j["log"] = lines[-log_lines:]
        j["log_total_lines"] = len(lines)
        return j

    def history(self, n: int = 30) -> list:
        out = []
        for d in sorted(JOBS_DIR.glob("*"), reverse=True)[:n] if JOBS_DIR.is_dir() else []:
            with self.lock:
                j = self._job(d.name)
            if j:
                out.append(j)
        return out

    def latest(self) -> dict | None:
        h = self.history(1)
        return self.get(h[0]["id"]) if h else None


JOBS = Jobs()


def P(p) -> dict:
    return {"$path": str(p)}


# ======================================================================= round runs
def _round_dirs(batch: str, rnd: str, version: str):
    bdir = OUTPUT / batch
    return bdir, bdir / f"{rnd}_check_{version}"


def count_report_list(path: Path, category: str | None) -> int:
    data = read_json(path, {}) or {}
    cats = [category] if category else [k for k, v in data.items() if isinstance(v, dict) and "reports" in v]
    return sum(len((data.get(c) or {}).get("reports", [])) for c in cats)


def start_round(rnd: str, body: dict) -> dict:
    s = load_settings()
    cfg = s[rnd]
    batch = batch_name(s)
    version = str(body.get("version") or today()).strip()
    if not VERSION_RE.match(version):
        raise UserError("The version may only use letters, digits, - and _ (normally the date, YYYYMMDD).")
    n_runs = int(body.get("n_runs") or cfg["n_runs"])
    first = int(body.get("first_run") or 1)
    if n_runs < 1 or first < 1:
        raise UserError("Number of runs and first run number must be at least 1.")
    pdf_dir, env = proj_path(s["pdf_dir"]), proj_path(s["env_file"])
    if not pdf_dir.is_dir():
        raise UserError(f"The PDF folder in Settings was not found: {pdf_dir}")
    if not env.is_file():
        raise UserError(f"The .env file in Settings was not found: {env}")
    scripts = {k: CODE_DIR / cfg[k] for k in ("extract_script", "compile_script", "check_script", "summary_script")}
    prompt = PROMPT_DIR / cfg["prompt"]
    for p in [*scripts.values(), prompt]:
        if not p.is_file():
            raise UserError(f"Not found: {p}")
    bdir, check_dir = _round_dirs(batch, rnd, version)
    run_dirs = {n: bdir / f"{rnd}_{version}_run{n}" for n in range(first, first + n_runs)}
    existing = [d for d in [*run_dirs.values(), check_dir] if d.exists()]
    if existing:
        raise UserError("This version already exists (" + ", ".join(d.name for d in existing) +
                        "). Pick another version, or a later first run number to add runs.")
    prefix = s.get("csv_prefix") or "sl"
    report_list, category, total = None, None, len(list(pdf_dir.glob("*.pdf")))
    links = {"batch": batch, "round": rnd, "version": version}
    if rnd == "round2":
        r1 = str(body.get("round1_version") or "").strip()
        if not r1:
            raise UserError("Pick the Round 1 version whose disagreements are run again.")
        report_list = bdir / f"round1_check_{r1}" / f"round1_check_disagreement_reports_{r1}.json"
        if not report_list.is_file():
            raise UserError(f"Round 1 version {r1} has no list of reports to check again: {report_list}")
        category = body.get("category") or None
        total = count_report_list(report_list, category)
        if total == 0:
            raise UserError("The Round 1 list has no reports in the chosen category; nothing to run.")
        links["round1_version"] = r1
    steps = []
    for n, run_dir in run_dirs.items():
        json_dir = run_dir / "json_output"
        g = {"BASE_DIR": P(BASE), "PDF_DIR": P(pdf_dir), "PROMPT_FILE": P(prompt), "ENV_FILE": P(env),
             "OUTPUT_DIR": P(json_dir), "SELECTED_PDF_DIR": P(run_dir / "selected_pdf_pages"), "JSON_DIR": P(json_dir),
             "OUTPUT_FILE": P(run_dir / "compiled_csv" / f"dsa_decomposition_{prefix}_{rnd}_{version}_run{n}.csv")}
        if rnd == "round2":
            g.update({"REPORT_LIST_FILE": P(report_list), "REPORT_LIST_CATEGORY": category, "RERUN_OUTPUT_DIR": P(json_dir)})
        steps.append({"label": f"Run {n}: extract ({scripts['extract_script'].name})", "script": str(scripts["extract_script"]),
                      "globals": g, "watch": {"kind": "files", "dir": str(json_dir), "patterns": ["*_dsa.json", "*_ERROR.json"], "total": total},
                      "fail_pattern": r"^Fatal error:"})
        steps.append({"label": f"Run {n}: compile CSV ({scripts['compile_script'].name})", "script": str(scripts["compile_script"]), "globals": g})
    glob = {"$glob": {"dir": str(bdir), "pattern": f"{rnd}_{version}_run*/compiled_csv/dsa_decomposition_{prefix}_{rnd}_{version}_run*.csv", "run_sort": True}}
    steps.append({"label": "Compare the runs (1c)", "script": str(scripts["check_script"]),
                  "globals": {"ROUND": rnd, "RUN_CSVS": glob, "CHECK_DIR": P(check_dir), "RUN_DATE": version}})
    steps.append({"label": "Summary tables (1d)", "script": str(scripts["summary_script"]),
                  "globals": {"ROUND": rnd, "CHECK_DIR": P(check_dir), "RUN_DATE": version}})
    params = {"version": version, "n_runs": n_runs, "first_run": first, "pdf_dir": str(pdf_dir), "n_reports": total,
              "scripts": {k: v.name for k, v in scripts.items()}, "prompt": prompt.name, "csv_prefix": prefix,
              "round1_version": links.get("round1_version"), "category": category}
    title = f"{'Round 1' if rnd == 'round1' else 'Round 2'} · {batch} · version {version} · {n_runs} run(s)"
    job = JOBS.start(rnd, title, steps, params, links, must_not_exist=[*run_dirs.values(), check_dir], python=python_exe(s))
    write_json(RECORDS_DIR / safe_name(batch) / f"{rnd}_{version}.json", {**params, "job": job["id"], "started": now(), "batch": batch})
    return job


# ======================================================================= round versions and results
_cache: dict = {}
_cache_lock = threading.Lock()


def cached(key, paths, build):
    """build() once per key, again only when one of the paths changes (mtime)."""
    stamp = tuple((str(p), p.stat().st_mtime if p.exists() else 0) for p in paths)
    with _cache_lock:
        hit = _cache.get(key)
        if hit and hit[0] == stamp:
            return hit[1]
    val = build()
    with _cache_lock:
        if len(_cache) > 24:
            _cache.clear()
        _cache[key] = (stamp, val)
    return val


def round_versions(batch: str, rnd: str) -> list:
    bdir = OUTPUT / batch
    if not bdir.is_dir():
        return []
    found: dict = {}
    for d in bdir.iterdir():
        if not d.is_dir():
            continue
        m = re.match(rf"^{rnd}_check_(.+)$", d.name)
        if m:
            found.setdefault(m.group(1), {"runs": []})["check"] = d
            continue
        m = re.match(rf"^{rnd}_(.+)_run(\d+)$", d.name)
        if m:
            found.setdefault(m.group(1), {"runs": []})["runs"].append(int(m.group(2)))
    out = []
    for v, f in found.items():
        check = f.get("check")
        meta = (read_json(check / f"{rnd}_check_fully_match_reports_{v}.json", {}) or {}).get("meta", {}) if check else {}
        rec = read_json(RECORDS_DIR / safe_name(batch) / f"{rnd}_{v}.json")
        when = check.stat().st_mtime if check else max((bdir / f"{rnd}_{v}_run{n}").stat().st_mtime for n in f["runs"])
        out.append({"version": v, "has_check": bool(check and any(check.glob("*_report_summary_*.csv"))),
                    "runs": sorted(f["runs"]), "n_runs": meta.get("n_runs") or len(f["runs"]),
                    "n_reports": meta.get("n_reports_total"), "counts_by_group": meta.get("counts_by_group"),
                    "modified": datetime.fromtimestamp(when).isoformat(timespec="seconds"), "record": rec})
    return sorted(out, key=lambda r: r["version"], reverse=True)


class RoundData:
    """One version of one round: the check files (1c) and, when they are on this computer, the runs' CSVs."""

    def __init__(self, batch: str, rnd: str, version: str):
        if rnd not in ROUNDS or not VERSION_RE.match(version or ""):
            raise UserError("bad round or version")
        self.batch, self.rnd, self.version = batch, rnd, version
        self.bdir, self.check = _round_dirs(batch, rnd, version)
        self.f_summary = self.check / f"{rnd}_check_report_summary_{version}.csv"
        self.f_matched = self.check / f"{rnd}_check_matched_rows_{version}.csv"
        self.f_diffs = self.check / f"{rnd}_check_value_diffs_{version}.csv"
        self.f_full = self.check / f"{rnd}_check_fully_match_reports_{version}.json"
        self.f_disagree = self.check / f"{rnd}_check_disagreement_reports_{version}.json"
        if not self.f_summary.is_file():
            raise UserError(f"{rnd} version {version} has no check results yet ({self.f_summary.name} not found).")
        self.run_dirs = sorted((d for d in self.bdir.glob(f"{rnd}_{version}_run*") if d.is_dir()),
                               key=lambda d: int(re.search(r"_run(\d+)$", d.name).group(1)))

    @property
    def files(self):
        return [self.f_summary, self.f_matched, self.f_diffs]

    def summary(self) -> pd.DataFrame:
        return cached(("sum", str(self.f_summary)), [self.f_summary], lambda: read_csv(self.f_summary))

    def matched(self) -> pd.DataFrame:
        return cached(("mat", str(self.f_matched)), [self.f_matched],
                      lambda: read_csv(self.f_matched) if self.f_matched.is_file() else pd.DataFrame(columns=["json_file"]))

    def diffs(self) -> pd.DataFrame:
        return cached(("dif", str(self.f_diffs)), [self.f_diffs],
                      lambda: read_csv(self.f_diffs) if self.f_diffs.is_file() else pd.DataFrame(columns=["json_file"]))

    def meta(self) -> dict:
        return (read_json(self.f_full, {}) or {}).get("meta", {})

    def n_runs(self) -> int:
        return int(self.meta().get("n_runs") or max(1, len(self.run_dirs)))

    def run_csvs(self) -> list:
        out = []
        for d in self.run_dirs:
            hits = sorted((d / "compiled_csv").glob("*.csv"))
            out.append(hits[0] if hits else None)
        return out

    def run_frames(self) -> list | None:
        """The runs' compiled CSVs, if every one of them is on this computer; else None."""
        paths = self.run_csvs()
        if not paths or any(p is None for p in paths) or len(paths) != self.n_runs():
            return None
        return cached(("runs", str(self.check)), paths, lambda: [read_csv(p) for p in paths])

    def fully_matched_ids(self) -> set:
        s = self.summary()
        return set(s.loc[s["group"] == "fully_match", "json_file"])

    def ready_rows(self) -> pd.DataFrame:
        """The rows ready to append: the matched rows of the fully matched reports, in the panel layout."""
        def build():
            m = self.matched()
            keep = m[m["json_file"].isin(self.fully_matched_ids())]
            return fs.to_final(keep, self.rnd)
        return cached(("ready", str(self.check)), self.files, build)


def _top_values(m: pd.DataFrame) -> dict:
    top = m[m["hierarchy_id"].isin([str(i) for i in range(1, 7)])]
    out: dict = {}
    for jf, h, v in zip(top["json_file"], top["hierarchy_id"], top["value"]):
        out.setdefault(jf, {})[h] = clean(v)
    return out


def review_summary(batch: str, rnd: str, version: str) -> dict:
    rd = RoundData(batch, rnd, version)

    def build():
        s, m, d = rd.summary(), rd.matched(), rd.diffs()
        tops = _top_values(m)
        lay = {}
        if len(m):
            first = m.drop_duplicates("json_file")
            lay = dict(zip(first["json_file"], first["last_actual_year"]))
        reports = []
        for r in s.to_dict("records"):
            jf = r["json_file"]
            reports.append({
                "json_file": jf, "pdf": clean(r.get("pdf_file_name")), "country": clean(r.get("country")),
                "group": r["group"], "lay_by_run": clean(r.get("last_actual_year_by_run")),
                "tf_by_run": clean(r.get("table_found_by_run")), "lay": clean(lay.get(jf)),
                "rows_compared": int(r.get("rows_compared") or 0), "rows_matching": int(r.get("rows_matching") or 0),
                "rows_differing": int(r.get("rows_differing") or 0), "error": clean(r.get("error_by_run")),
                "top": tops.get(jf, {}),
            })
        diff_types = d["diff_type"].value_counts().to_dict() if "diff_type" in d.columns else {}
        meta = rd.meta()
        return {"batch": batch, "round": rnd, "version": version, "n_runs": rd.n_runs(),
                "counts_by_group": s["group"].value_counts().to_dict(), "n_reports": int(len(s)),
                "rows_matched": int(len(m)), "rows_differing": int(len(d)), "diff_types": diff_types,
                "rows_ready": int(len(rd.ready_rows())), "run_csvs_available": rd.run_frames() is not None,
                "run_csvs": meta.get("run_csvs") or [], "reports": reports}
    return cached(("rsum", str(rd.check)), rd.files, build)


# ----------------------------------------------------------------- one report, every run side by side
def _pdf_index(root: Path) -> dict:
    def build():
        idx = {}
        if root.is_dir():
            for p in root.rglob("*.pdf"):
                idx.setdefault(p.name, p)
        return idx
    return cached(("pdfidx", str(root)), [root], build)


def find_original_pdf(name: str) -> Path | None:
    s = load_settings()
    for folder in (proj_path(s["pdf_dir"]), proj_path(s["staff_reports_root"]), BASE / "staff_reports"):
        p = folder / name
        if p.is_file():
            return p
    for folder in (proj_path(s["staff_reports_root"]), BASE / "staff_reports"):
        hit = _pdf_index(folder).get(name)
        if hit:
            return hit
    return None


def report_pdfs(rd: RoundData, pdf_name: str, page) -> list:
    stem = Path(pdf_name or "").stem
    out = []
    for d in rd.run_dirs:
        sel = d / "selected_pdf_pages"
        if sel.is_dir():
            for p in sorted(sel.glob(f"{glob_escape(stem)}_*.pdf")):
                out.append({"label": f"Selected pages · {d.name.rsplit('_', 1)[-1]} · {p.name[len(stem) + 1:]}", "path": str(p), "kind": "selected"})
            if out:
                break  # the pages are the same in every run; the first run that has them is enough
    orig = find_original_pdf(pdf_name) if pdf_name else None
    if orig:
        pg = None
        try:
            pg = int(float(page)) if page not in (None, "") else None
        except ValueError:
            pg = None
        out.append({"label": "Original PDF" + (f" · page {pg}" if pg else ""), "path": str(orig), "page": pg, "kind": "original"})
    return out


def glob_escape(s: str) -> str:
    return re.sub(r"([\[\]*?])", r"[\1]", s)


def report_detail(batch: str, rnd: str, version: str, json_file: str) -> dict:
    rd = RoundData(batch, rnd, version)
    s = rd.summary()
    hit = s[s["json_file"] == json_file]
    if hit.empty:
        raise UserError(f"{json_file} is not in {rnd} version {version}")
    srow = hit.iloc[0].to_dict()
    n = rd.n_runs()
    frames = rd.run_frames()
    rows: dict = {}
    meta: dict = {}
    source = "check"
    if frames is not None:
        source = "runs"
        for i, df in enumerate(frames):
            g = df[df["json_file"] == json_file]
            if len(g) and not meta:
                meta = {c: clean(g.iloc[0].get(c)) for c in fs.REPORT_COLUMNS + ["page_printed", "table_found"] if c in g.columns}
            for r in g[g["hierarchy_id"].notna()].to_dict("records"):
                e = rows.setdefault(str(r["hierarchy_id"]), {"labels": [None] * n, "values": [None] * n, "top": r.get("top_category")})
                e["labels"][i], e["values"][i] = clean(r.get("label_verbatim")), clean(r.get("value"))
    else:
        m = rd.matched()
        g = m[m["json_file"] == json_file]
        if len(g):
            meta = {c: clean(g.iloc[0].get(c)) for c in fs.REPORT_COLUMNS + ["page_printed", "table_found"] if c in g.columns}
        for r in g.to_dict("records"):
            rows[str(r["hierarchy_id"])] = {"labels": [clean(r.get("label_verbatim"))] * n, "values": [clean(r.get("value"))] * n,
                                            "top": r.get("top_category")}
        d = rd.diffs()
        for r in d[d["json_file"] == json_file].to_dict("records"):
            hid = str(r["key"]).split("||", 1)[-1]
            rows[hid] = {"labels": [clean(r.get(f"label_run{i + 1}")) for i in range(n)],
                         "values": [clean(r.get(f"value_run{i + 1}")) for i in range(n)], "top": r.get("top_category")}
    out_rows = []
    for hid in sorted(rows, key=fs.hid_sort_key):
        e = rows[hid]
        vals = e["values"]
        nums = []
        for v in vals:
            try:
                nums.append(None if v is None else float(str(v).replace(",", "")))
            except ValueError:
                nums.append(str(v).strip().lower())
        same = all(x == nums[0] for x in nums[1:])
        out_rows.append({"hierarchy_id": hid, "top_category": e.get("top"), "labels": e["labels"], "values": vals,
                         "same": same, "level": hid.count(".")})
    lay_by_run = (clean(srow.get("last_actual_year_by_run")) or "").split("|")
    if not meta:
        meta = {"json_file": json_file, "pdf_file_name": clean(srow.get("pdf_file_name")), "country": clean(srow.get("country"))}
    return {"json_file": json_file, "round": rnd, "version": version, "n_runs": n, "source": source,
            "group": srow.get("group"), "lay_by_run": lay_by_run,
            "tf_by_run": (clean(srow.get("table_found_by_run")) or "").split("|"), "error": clean(srow.get("error_by_run")),
            "meta": meta, "rows": out_rows,
            "pdfs": report_pdfs(rd, meta.get("pdf_file_name") or srow.get("pdf_file_name"), meta.get("page_pdf"))}


# ======================================================================= human review (round 3)
REVIEW_STATUSES = ("reviewed", "no_table", "skipped")


def hr_dir(batch: str, version: str) -> Path:
    return OUTPUT / batch / f"round3_review_{version}"


def hr_rows_csv(batch: str, version: str) -> Path:
    return hr_dir(batch, version) / f"round3_reviewed_rows_{version}.csv"


def _review_path(batch: str, version: str, json_file: str) -> Path:
    return hr_dir(batch, version) / "reviews" / (safe_name(Path(json_file).stem) + ".json")


def hr_reviews(batch: str, version: str) -> dict:
    folder = hr_dir(batch, version) / "reviews"
    out = {}
    for p in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        r = read_json(p)
        if r and r.get("json_file"):
            out[r["json_file"]] = r
    return out


def hr_queue(batch: str, version: str) -> dict:
    rd = RoundData(batch, "round2", version)
    s = rd.summary()
    todo = s[s["group"] != "fully_match"]
    reviews = hr_reviews(batch, version)
    items = []
    for r in todo.to_dict("records"):
        rv = reviews.get(r["json_file"])
        items.append({"json_file": r["json_file"], "pdf": clean(r.get("pdf_file_name")), "country": clean(r.get("country")),
                      "group": r["group"], "rows_differing": int(r.get("rows_differing") or 0),
                      "lay_by_run": clean(r.get("last_actual_year_by_run")),
                      "status": rv.get("status") if rv else "todo", "saved_at": rv.get("saved_at") if rv else None})
    order = {"partial_match": 0, "last_actual_year_differs": 1, "table_found_differs": 2, "missing_in_run": 3,
             "no_table_in_all_runs": 4, "extraction_failed_in_all_runs": 5}
    items.sort(key=lambda x: (str(x["country"] or "").lower(), x["json_file"]))
    counts = {k: sum(1 for i in items if i["status"] == k) for k in ("todo", *REVIEW_STATUSES)}
    rows_csv = hr_rows_csv(batch, version)
    return {"batch": batch, "version": version, "items": items, "counts": counts, "group_order": order,
            "rows_file": str(rows_csv), "rows_ready": int(len(read_csv(rows_csv))) if rows_csv.is_file() else 0}


def standard_template(rd: RoundData) -> list:
    """The usual line items (hierarchy_id, label) of this round's tables, for a report that has no rows from
    any run: every hierarchy_id found in at least 30 % of the reports, with its most common label."""
    def build():
        m = rd.matched()
        if not len(m):
            return []
        n = m["json_file"].nunique()
        g = m.groupby("hierarchy_id")
        share = g["json_file"].nunique() / max(n, 1)
        keep = share[share >= 0.3].index
        labels = m[m["hierarchy_id"].isin(keep)].groupby("hierarchy_id")["label_verbatim"].agg(
            lambda x: x.value_counts().index[0] if len(x.dropna()) else "")
        return [{"hierarchy_id": h, "label": labels.get(h, "")} for h in sorted(keep, key=fs.hid_sort_key)]
    return cached(("tmpl", str(rd.check)), rd.files, build)


def hr_item(batch: str, version: str, json_file: str) -> dict:
    detail = report_detail(batch, "round2", version, json_file)
    rd = RoundData(batch, "round2", version)
    detail["review"] = read_json(_review_path(batch, version, json_file))
    detail["template"] = standard_template(rd)
    detail["top_categories"] = fs.TOP_BY_ID
    return detail


def hr_save(batch: str, version: str, body: dict) -> dict:
    jf = str(body.get("json_file") or "")
    status = body.get("status")
    if status not in REVIEW_STATUSES:
        raise UserError("status must be reviewed, no_table or skipped")
    detail = report_detail(batch, "round2", version, jf)
    rows_in = body.get("rows") or []
    rows, seen, problems = [], set(), []
    if status == "reviewed":
        lay = str(body.get("last_actual_year") or "").strip()
        if not lay:
            problems.append("Enter the last actual year.")
        for r in rows_in:
            hid = str(r.get("hierarchy_id") or "").strip()
            label = str(r.get("label_verbatim") or "").strip()
            value = str(r.get("value") if r.get("value") is not None else "").strip()
            if not hid and not label and not value:
                continue
            if not fs.HID_RE.match(hid):
                problems.append(f"Hierarchy id '{hid}' is not valid (1-6, then .1, .2 ... e.g. 5.2).")
                continue
            if hid in seen:
                problems.append(f"Hierarchy id {hid} appears twice.")
            seen.add(hid)
            if value:
                try:
                    float(value.replace(",", "").replace("−", "-"))
                except ValueError:
                    problems.append(f"{hid}: '{value}' is not a number.")
            rows.append({"hierarchy_id": hid, "label_verbatim": label, "value": value})
        for r in rows:
            parent = ".".join(r["hierarchy_id"].split(".")[:-1])
            if parent and parent not in seen:
                problems.append(f"{r['hierarchy_id']} has no parent row {parent}.")
        if not rows:
            problems.append("No line items entered.")
    if problems:
        raise UserError(" ".join(problems[:6]) + (" …" if len(problems) > 6 else ""))
    rows.sort(key=lambda r: fs.hid_sort_key(r["hierarchy_id"]))
    rec = {"json_file": jf, "pdf_file_name": detail["meta"].get("pdf_file_name"), "country": detail["meta"].get("country"),
           "status": status, "last_actual_year": str(body.get("last_actual_year") or "").strip() or None,
           "actual_column_label": str(body.get("actual_column_label") or "").strip() or None,
           "page_pdf": str(body.get("page_pdf") or "").strip() or None,
           "note": str(body.get("note") or "").strip() or None, "rows": rows if status == "reviewed" else [],
           "meta": detail["meta"], "round2_group": detail["group"], "round2_lay_by_run": detail["lay_by_run"],
           "round2_values": {r["hierarchy_id"]: r["values"] for r in detail["rows"]},
           "saved_at": now(), "batch": batch, "round2_version": version}
    write_json(_review_path(batch, version, jf), rec)
    n = rebuild_round3_rows(batch, version)
    return {"saved": True, "status": status, "rows_ready": n}


def round3_frame(batch: str, version: str) -> pd.DataFrame:
    """Every reviewed report's rows, in the panel database layout."""
    out = []
    for jf, rv in hr_reviews(batch, version).items():
        if rv.get("status") != "reviewed":
            continue
        labels = {r["hierarchy_id"]: r["label_verbatim"] for r in rv["rows"]}
        meta = rv.get("meta") or {}
        for r in rv["rows"]:
            row = {c: meta.get(c) for c in fs.REPORT_COLUMNS}
            row.update(json_file=jf, last_actual_year=rv.get("last_actual_year"),
                       actual_column_label=rv.get("actual_column_label") or rv.get("last_actual_year"))
            if rv.get("page_pdf"):
                row["page_pdf"] = rv["page_pdf"]
            row.update(fs.item_fields(r["hierarchy_id"], labels))
            row.update(hierarchy_id=r["hierarchy_id"], label_verbatim=r["label_verbatim"], value=r["value"] or None)
            out.append(row)
    df = pd.DataFrame(out, columns=[c for c in fs.FINAL_COLUMNS if c not in ("source_round", "gapfill_run")])
    return fs.to_final(df, "round3")


def rebuild_round3_rows(batch: str, version: str) -> int:
    df = round3_frame(batch, version)
    path = hr_rows_csv(batch, version)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return int(len(df))


# ======================================================================= ready to append
def staging(batch: str, r1: str | None, r2: str | None) -> dict:
    parts, frames = [], []
    for rnd, v in (("round1", r1), ("round2", r2)):
        if not v:
            continue
        try:
            df = RoundData(batch, rnd, v).ready_rows()
        except UserError:
            continue
        frames.append(df)
        parts.append({"source": rnd, "label": f"{'Round 1' if rnd == 'round1' else 'Round 2'} fully matched",
                      "version": v, "rows": int(len(df)), "reports": int(df["json_file"].nunique())})
    if r2:
        q = None
        try:
            q = hr_queue(batch, r2)
        except UserError:
            pass
        df = round3_frame(batch, r2) if q else pd.DataFrame(columns=fs.FINAL_COLUMNS)
        frames.append(df)
        parts.append({"source": "round3", "label": "Round 3 human review", "version": r2, "rows": int(len(df)),
                      "reports": int(df["json_file"].nunique()) if len(df) else 0,
                      "reviewed": q["counts"] if q else None, "to_review": len(q["items"]) if q else 0})
    allrows = fs.concat_final(frames)
    problems = fs.check_final(allrows) if len(allrows) else []
    by_source = allrows.groupby("json_file")["source_round"].nunique() if len(allrows) else pd.Series(dtype=int)
    overlap = sorted(by_source[by_source > 1].index)
    if overlap:
        problems.append(f"{len(overlap)} report(s) appear in more than one source, e.g. {overlap[:3]}")
    latest = panel_latest()
    already = 0
    if latest and len(allrows):
        base = panel_frame(latest["stamp"])
        already = int(allrows["json_file"].isin(set(base["json_file"])).groupby(allrows["json_file"]).first().sum())
    return {"batch": batch, "round1_version": r1, "round2_version": r2, "parts": parts, "rows": int(len(allrows)),
            "reports": int(allrows["json_file"].nunique()) if len(allrows) else 0,
            "columns": fs.FINAL_COLUMNS, "problems": problems, "panel_latest": latest,
            "reports_already_in_panel": already}


# ======================================================================= panel database
def panel_versions() -> list:
    out = []
    for p in PANEL_DIR.glob("panel_database_*.csv") if PANEL_DIR.is_dir() else []:
        rec = read_json(p.with_suffix(".json"), {}) or {}
        stamp = p.stem[len("panel_database_"):]
        out.append({"stamp": stamp, "file": str(p), "size_bytes": p.stat().st_size,
                    "created": rec.get("created") or datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"),
                    **{k: rec.get(k) for k in ("rows", "reports", "countries", "country_years", "by_source", "parent", "added", "note")}})
    return sorted(out, key=lambda r: r["created"], reverse=True)


def panel_latest() -> dict | None:
    v = panel_versions()
    return v[0] if v else None


def panel_path(stamp: str) -> Path:
    if not VERSION_RE.match(stamp or ""):
        raise UserError("bad version")
    p = PANEL_DIR / f"panel_database_{stamp}.csv"
    if not p.is_file():
        raise UserError(f"panel database version {stamp} not found")
    return p


def panel_frame(stamp: str) -> pd.DataFrame:
    p = panel_path(stamp)
    return cached(("panel", str(p)), [p], lambda: read_csv(p))


def _panel_stats(df: pd.DataFrame) -> dict:
    lay = df["last_actual_year"].fillna("")
    cy = df.assign(_y=lay)[["country", "_y"]].drop_duplicates()
    return {"rows": int(len(df)), "reports": int(df["json_file"].nunique()), "countries": int(df["country"].nunique()),
            "country_years": int(len(cy)), "by_source": df["source_round"].fillna("").value_counts().to_dict()}


def _new_stamp() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    cand, n = stamp, 2
    while (PANEL_DIR / f"panel_database_{cand}.csv").exists():
        cand, n = f"{stamp}_{n}", n + 1
    return cand


def _write_panel(df: pd.DataFrame, parent: str | None, added: list, note: str | None = None) -> dict:
    PANEL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _new_stamp()
    path = PANEL_DIR / f"panel_database_{stamp}.csv"
    df = df[fs.FINAL_COLUMNS]
    df.to_csv(path, index=False, encoding="utf-8-sig")
    rec = {"stamp": stamp, "created": now(), "parent": parent, "added": added, "note": note,
           "columns": fs.FINAL_COLUMNS, **_panel_stats(df)}
    write_json(path.with_suffix(".json"), rec)
    return rec


def panel_import(body: dict) -> dict:
    src = proj_path(body.get("csv"))
    if not src.is_file():
        raise UserError(f"File not found: {src}")
    df = read_csv(src)
    if "source_round" not in df.columns:
        raise UserError("This CSV has no source_round column, so it is not a merged database.")
    df = df.reset_index(drop=True)
    out = fs.to_final(df, "import")
    out["source_round"] = df["source_round"].values          # keep each row's own source and gap-fill stamp
    out["gapfill_run"] = df["gapfill_run"].values if "gapfill_run" in df.columns else None
    return _write_panel(out, None, [{"source": "import", "file": str(src), "rows": int(len(out))}],
                        note=body.get("note") or f"Imported from {src.name}")


def panel_append_staging(body: dict) -> dict:
    s = load_settings()
    batch = body.get("batch") or batch_name(s)
    r1, r2 = body.get("round1_version") or None, body.get("round2_version") or None
    include = set(body.get("include") or ["round1", "round2", "round3"])
    replace = bool(body.get("replace_existing"))
    frames, added = [], []
    for rnd, v in (("round1", r1), ("round2", r2)):
        if v and rnd in include:
            df = RoundData(batch, rnd, v).ready_rows()
            frames.append(df)
            added.append({"source": rnd, "batch": batch, "version": v, "rows": int(len(df))})
    if r2 and "round3" in include:
        df = round3_frame(batch, r2)
        frames.append(df)
        added.append({"source": "round3", "batch": batch, "version": r2, "rows": int(len(df))})
    new = fs.concat_final(frames)
    if not len(new):
        raise UserError("Nothing to append.")
    problems = [p for p in fs.check_final(new) if "columns" in p or "hierarchy_id" in p]
    if problems:
        raise UserError("Not appended: " + "; ".join(problems))
    latest = panel_latest()
    base = panel_frame(latest["stamp"]) if latest else pd.DataFrame(columns=fs.FINAL_COLUMNS)
    dup = new["json_file"].isin(set(base["json_file"]))
    skipped = int(new.loc[dup, "json_file"].nunique())
    if dup.any():
        if replace:
            base = base[~base["json_file"].isin(set(new["json_file"]))]
        else:
            new = new[~dup]
    out = fs.concat_final([base, new])
    for a in added:
        a["rows_appended"] = int((new["source_round"] == a["source"]).sum())
    rec = _write_panel(out, latest["stamp"] if latest else None, added,
                       note=body.get("note") or f"{batch}: Round 1 {r1 or '-'} / Round 2 {r2 or '-'}")
    rec["reports_already_in_panel"] = skipped
    rec["replaced"] = replace
    return rec


def panel_data(stamp: str, q: dict) -> dict:
    df = panel_frame(stamp)
    f = df
    country = (q.get("country") or "").strip().lower()
    if country:
        f = f[f["country"].fillna("").str.lower().str.contains(re.escape(country))]
    if q.get("year"):
        f = f[f["last_actual_year"] == q["year"]]
    if q.get("source"):
        f = f[f["source_round"] == q["source"]]
    if q.get("top_only") in ("1", "true"):
        f = f[~f["hierarchy_id"].fillna("").str.contains(r"\.")]
    if q.get("hid"):
        f = f[f["hierarchy_id"] == q["hid"]]
    page, size = int(q.get("page") or 0), min(int(q.get("size") or 100), 500)
    rows = f.iloc[page * size:(page + 1) * size]
    years = sorted({y for y in df["last_actual_year"].dropna().unique() if re.fullmatch(r"\d{4}", str(y))})
    by_year = {}
    cy = df[df["last_actual_year"].isin(years)][["country", "last_actual_year", "source_round"]].drop_duplicates(["country", "last_actual_year"])
    for (y, sr), n in cy.groupby(["last_actual_year", "source_round"]).size().items():
        by_year.setdefault(y, {})[sr] = int(n)
    return {"stamp": stamp, "stats": _panel_stats(df), "n_filtered": int(len(f)), "page": page, "size": size,
            "columns": fs.FINAL_COLUMNS, "rows": rows.astype(object).where(rows.notna(), None).values.tolist(),
            "years": years, "sources": fs.SOURCE_ROUNDS, "by_year": by_year,
            "record": read_json(panel_path(stamp).with_suffix(".json"), {})}


# ======================================================================= gap fill
def gap_dirs(stamp: str):
    return GAP_CHECK_ROOT / f"panel_{stamp}", GAP_OUT_ROOT / f"panel_{stamp}"


def gap_runs() -> list:
    out = []
    folder = RECORDS_DIR / "gapfill"
    for p in sorted(folder.glob("*.json"), reverse=True) if folder.is_dir() else []:
        rec = read_json(p, {}) or {}
        check, outd = gap_dirs(rec.get("stamp", ""))
        rec["identified"] = (check / f"gapfill_targets_{rec.get('stamp')}.csv").is_file()
        rec["filled"] = (outd / f"gapfill_resolution_{rec.get('stamp')}.csv").is_file()
        rec["appended_as"] = rec.get("appended_as")
        out.append(rec)
    return out


def _gap_common(s: dict, stamp: str) -> dict:
    gcfg = s["gapfill"]
    check, outd = gap_dirs(stamp)
    import core  # code/core.py
    return {
        "BASE_DIR": P(BASE), "STAMP": stamp, "CHECK_DIR": P(check), "OUT_DIR": P(check),
        "STAFF_REPORTS_DIR": P(proj_path(s["staff_reports_root"])),
        "SELECTED_PDF_DIRS": [P(d) for d in core.discover_selected_pdf_dirs(OUTPUT)],
        "STEP1_SCRIPT": P(CODE_DIR / gcfg["locator_script"]), "STEP1_PROMPT_FILE": P(PROMPT_DIR / gcfg["locator_prompt"]),
        "GAPFILL_PROMPT_FILE": P(PROMPT_DIR / gcfg["prompt"]), "ENV_FILE": P(proj_path(s["env_file"])),
        "TARGETS_CSV": P(check / f"gapfill_targets_{stamp}.csv"), "SKIP_CSV": P(check / f"gapfill_skip_reports_{stamp}.csv"),
        "PANEL_CSV": P(check / f"panel_structure_country_year_{stamp}.csv"), "OUTPUT_DIR": P(outd),
        "MAX_WORKERS": int(gcfg.get("max_workers") or 4),
    }


def start_gap_identify(body: dict) -> dict:
    s = load_settings()
    gcfg = s["gapfill"]
    panel = body.get("panel_version") or (panel_latest() or {}).get("stamp")
    if not panel:
        raise UserError("There is no panel database yet. Append the Round 1-3 data (or import a merged CSV) first.")
    input_csv = panel_path(panel)
    stamp = str(body.get("stamp") or today()).strip()
    if not VERSION_RE.match(stamp):
        raise UserError("The version may only use letters, digits, - and _.")
    check, outd = gap_dirs(stamp)
    if check.exists():
        raise UserError(f"Gap fill version {stamp} already exists. Pick another version.")
    y0, y1 = int(body.get("year_from") or gcfg["year_from"]), int(body.get("year_to") or gcfg["year_to"])
    if not 1990 <= y0 <= y1 <= 2100:
        raise UserError("Check the year range.")
    root = proj_path(s["staff_reports_root"])
    if not root.is_dir():
        raise UserError(f"The staff reports root folder in Settings was not found: {root}")
    panel_countries = body.get("panel_countries_file") or None
    if panel_countries and not proj_path(panel_countries).is_file():
        raise UserError(f"Country list not found: {panel_countries}")
    g = _gap_common(s, stamp)
    g.update({"INPUT_CSV": P(input_csv), "FULL_RANGE": [y0, y1], "EXCLUDE_IDENTIFIED_CSV": None,
              "PANEL_COUNTRIES": P(proj_path(panel_countries)) if panel_countries else None})
    steps = [
        {"label": "Find the missing country-years (4a)", "script": str(CODE_DIR / gcfg["flags_script"]), "globals": g},
        {"label": "Candidate reports for each gap (4b)", "script": str(CODE_DIR / gcfg["targets_script"]), "globals": g},
    ]
    rec = {"stamp": stamp, "panel_version": panel, "input_csv": str(input_csv), "years": [y0, y1],
           "panel_countries_file": panel_countries, "created": now()}
    job = JOBS.start("gap_identify", f"Gap Fill · identify gaps · version {stamp} (panel {panel}, {y0}-{y1})", steps,
                     rec, {"gap": stamp}, must_not_exist=[check], python=python_exe(s))
    rec["identify_job"] = job["id"]
    write_json(RECORDS_DIR / "gapfill" / f"{stamp}.json", rec)
    return job


def start_gap_fill(body: dict) -> dict:
    s = load_settings()
    stamp = str(body.get("stamp") or "")
    rec = read_json(RECORDS_DIR / "gapfill" / f"{safe_name(stamp)}.json")
    if not rec:
        raise UserError("Unknown gap fill version.")
    check, outd = gap_dirs(stamp)
    if not (check / f"gapfill_targets_{stamp}.csv").is_file():
        raise UserError("Identify the gaps first.")
    mode = body.get("mode") or "fill"
    argv = []
    if mode == "dry_run":
        argv.append("--dry-run")
    elif mode == "collect":
        argv.append("--collect-only")
    if body.get("limit"):
        argv += ["--limit-gaps", str(int(body["limit"]))]
    if body.get("countries"):
        argv += ["--countries", str(body["countries"])]
    if mode != "dry_run" and not proj_path(s["env_file"]).is_file() and mode != "collect":
        raise UserError(f"The .env file in Settings was not found: {proj_path(s['env_file'])}")
    g = _gap_common(s, stamp)
    label = {"fill": "Read the gap years from later reports (4c, API)", "dry_run": "Dry run: list the planned calls (4c, no API)",
             "collect": "Rebuild the result files from saved answers (4c, no API)"}[mode]
    steps = [{"label": label, "script": str(CODE_DIR / s["gapfill"]["api_script"]), "globals": g, "argv": argv,
              "watch": {"kind": "log"}}]
    job = JOBS.start("gap_fill", f"Gap Fill · {mode.replace('_', ' ')} · version {stamp}", steps,
                     {"stamp": stamp, "mode": mode, "argv": argv}, {"gap": stamp}, python=python_exe(s))
    rec.setdefault("fill_jobs", []).append(job["id"])
    write_json(RECORDS_DIR / "gapfill" / f"{stamp}.json", rec)
    return job


CELL = {"observed": "o", "GAP": "g"}
RES_CODE = {"resolved": "f", "resolved_with_warning": "w", "unresolved": "u",
            "unresolved_no_candidate_reports": "n", "pending_api_error": "e"}


def gap_status(stamp: str) -> dict:
    rec = read_json(RECORDS_DIR / "gapfill" / f"{safe_name(stamp)}.json")
    if not rec:
        raise UserError("Unknown gap fill version.")
    check, outd = gap_dirs(stamp)
    f_panel = check / f"panel_structure_country_year_{stamp}.csv"
    f_targets = check / f"gapfill_targets_{stamp}.csv"
    f_res = outd / f"gapfill_resolution_{stamp}.csv"
    f_final = outd / f"gapfill_rows_final_{stamp}.csv"
    if not f_panel.is_file():
        return {"stamp": stamp, "record": rec, "ready": False}

    def build():
        panel = read_csv(f_panel, usecols=["country", "year", "status"])
        countries = sorted(panel["country"].unique())
        years = sorted({int(y) for y in panel["year"]})
        ci, yi = {c: i for i, c in enumerate(countries)}, {y: i for i, y in enumerate(years)}
        grid = [["." for _ in years] for _ in countries]
        for c, y, st in zip(panel["country"], panel["year"], panel["status"]):
            grid[ci[c]][yi[int(y)]] = CELL.get(st, ".")
        if f_targets.is_file():
            t = read_csv(f_targets)
            if "has_candidate_report" in t.columns:
                for c, y, h in zip(t["country"], t["gap_year"], t["has_candidate_report"]):
                    if c in ci and int(y) in yi and str(h).upper() == "FALSE" and grid[ci[c]][yi[int(y)]] == "g":
                        grid[ci[c]][yi[int(y)]] = "x"  # gap with no later report to read it from
        detail = {}
        if f_res.is_file():
            r = read_csv(f_res)
            for row in r.to_dict("records"):
                c, y = row["country"], int(row["gap_year"])
                if c in ci and int(y) in yi:
                    code = RES_CODE.get(row.get("final_status"), "g")
                    grid[ci[c]][yi[y]] = code
                    detail[f"{ci[c]}|{yi[y]}"] = {k: clean(row.get(k)) for k in
                                                   ("final_status", "source_report", "source_offset_years", "n_attempts",
                                                    "last_failure_status", "last_failure_detail", "warnings")}
        counts: dict = {}
        for row in grid:
            for ch in row:
                counts[ch] = counts.get(ch, 0) + 1
        return {"countries": countries, "years": years, "grid": ["".join(r) for r in grid], "detail": detail, "counts": counts}

    data = cached(("gap", stamp), [f_panel, f_targets, f_res], build)
    summary = read_json(check / f"summary_stats_{stamp}.json", {}) or {}
    return {"stamp": stamp, "record": rec, "ready": True, **data,
            "n_gap_targets": int(len(read_csv(f_targets))) if f_targets.is_file() else 0,
            "rows_ready": int(len(read_csv(f_final))) if f_final.is_file() else 0,
            "rows_file": str(f_final), "summary": {k: summary.get(k) for k in ("n_reports", "n_countries_in_panel", "n_gap_years", "n_gap_spans", "cause_counts_by_span")}}


def gap_append(body: dict) -> dict:
    stamp = str(body.get("stamp") or "")
    rec = read_json(RECORDS_DIR / "gapfill" / f"{safe_name(stamp)}.json")
    if not rec:
        raise UserError("Unknown gap fill version.")
    check, outd = gap_dirs(stamp)
    f_final = outd / f"gapfill_rows_final_{stamp}.csv"
    if not f_final.is_file():
        raise UserError("No gap fill results yet (run step 3, or 'Rebuild results' if the run was made with older code).")
    new = fs.to_final(read_csv(f_final), "gapfill", gapfill_run=stamp)
    latest = panel_latest()
    if not latest:
        raise UserError("There is no panel database to append to.")
    base = panel_frame(latest["stamp"])
    if (base["gapfill_run"] == stamp).any():
        raise UserError(f"The latest panel database already holds gap fill {stamp}.")
    out = fs.concat_final([base, new])
    added = [{"source": "gapfill", "version": stamp, "rows": int(len(new)), "rows_appended": int(len(new)),
              "gap_years_filled": int(new[["country", "last_actual_year"]].drop_duplicates().shape[0])}]
    res = _write_panel(out, latest["stamp"], added, note=body.get("note") or f"Gap fill {stamp}")
    rec["appended_as"] = res["stamp"]
    write_json(RECORDS_DIR / "gapfill" / f"{stamp}.json", rec)
    return res


# ======================================================================= overview
def overview(r1: str | None = None, r2: str | None = None) -> dict:
    s = load_settings()
    batch = batch_name(s)
    v1, v2 = round_versions(batch, "round1"), round_versions(batch, "round2")
    r1 = r1 or next((v["version"] for v in v1 if v["has_check"]), None)
    r2 = r2 or next((v["version"] for v in v2 if v["has_check"]), None)
    hr = None
    if r2:
        try:
            q = hr_queue(batch, r2)
            hr = {"version": r2, "counts": q["counts"], "total": len(q["items"]), "rows_ready": q["rows_ready"]}
        except UserError:
            hr = None
    stage = None
    try:
        stage = staging(batch, r1, r2)
    except UserError:
        pass
    return {"batch": batch, "round1": v1, "round2": v2, "round1_selected": r1, "round2_selected": r2,
            "human_review": hr, "staging": stage, "panel": panel_versions()[:10], "gap_runs": gap_runs(),
            "job": JOBS.latest(), "importable": [str(p.relative_to(BASE)) for p in sorted((OUTPUT / "final").glob("*.csv"))]
            if (OUTPUT / "final").is_dir() else []}


def allowed_pdf(path: str) -> Path:
    """A PDF the page may show: inside the project folder or one of the PDF folders in Settings."""
    p = Path(path).resolve()
    s = load_settings()
    roots = [BASE.resolve(), proj_path(s["pdf_dir"]).resolve(), proj_path(s["staff_reports_root"]).resolve()]
    if p.suffix.lower() != ".pdf" or not p.is_file() or not any(p == r or r in p.parents for r in roots):
        raise UserError("PDF not available")
    return p
