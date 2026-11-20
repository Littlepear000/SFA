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
    <output folder>/panel_pregapfill_<VERSION>.csv   the panel database before Gap Fill (Settings: output folder)
    <output folder>/panel_gapfill_<VERSION>.csv      the same + the gap years filled; same VERSION (date_time)
    <output folder>/panel_<VERSION>.json             how that version was built
    output/workflow/records/builds/, records/gapfill/   the app's own record of each build and gap fill run
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
GAP_CHECK_ROOT = OUTPUT / "gapfill" / "gap_year_check"
GAP_OUT_ROOT = OUTPUT / "gapfill" / "output"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))
import final_schema as fs  # noqa: E402
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
from version import app_version  # noqa: E402  (coverage_app/version.py)

VERSION_RE = re.compile(r"^[A-Za-z0-9_\-]{1,40}$")
ROUNDS = ("round1", "round2")

DEFAULTS = {
    "pdf_dir": "staff_reports/pdf staff reports/2021-2026",
    "batch": "",                      # empty = the name of the PDF folder
    "staff_reports_root": "staff_reports/pdf staff reports",
    "env_file": ".env",
    "csv_prefix": "sl",
    "output_folder": "output/final",  # where the panel database files are written and read
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
               "prompt": "2a_dsa_prompt_20261117.txt",
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


def toint(v) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


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
        "output_folder": {"path": str(output_folder(s)), "exists": output_folder(s).is_dir()},
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


_BOOT: list = []


def _boot_time() -> float | None:
    """When this computer last started (seconds since 1970), or None if it cannot be read."""
    if _BOOT:
        return _BOOT[0]
    t = None
    try:
        if os.name == "nt":
            import ctypes
            ctypes.windll.kernel32.GetTickCount64.restype = ctypes.c_ulonglong
            t = time.time() - ctypes.windll.kernel32.GetTickCount64() / 1000.0
        elif sys.platform == "darwin":
            out = subprocess.run(["sysctl", "-n", "kern.boottime"], capture_output=True, text=True, timeout=5).stdout
            m = re.search(r"sec\s*=\s*(\d+)", out)
            t = float(m.group(1)) if m else None
        else:
            for line in Path("/proc/stat").read_text().splitlines():
                if line.startswith("btime"):
                    t = float(line.split()[1])
    except Exception:
        t = None
    _BOOT.append(t)
    return t


def _started_before_boot(meta: dict) -> bool:
    """A job started before the computer last restarted cannot still be running, even if its old process
    number now belongs to some other program."""
    boot = _boot_time()
    try:
        created = datetime.fromisoformat(meta.get("created")).timestamp()
    except (TypeError, ValueError):
        return False
    return boot is not None and created < boot


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
                    (self.current != job_id and _pid_alive(meta.get("pid")) and not _started_before_boot(meta))
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


def _round_steps(rnd, version, bdir, check_dir, run_dirs, pdf_dir, env, prompt, scripts, prefix,
                 report_list, category, total, resume: bool = False) -> list:
    """The steps of one round version: extract + compile for every run, then compare (1c) and summarise (1d).
    resume=True: the extraction skips the reports already done in that run (SKIP_EXISTING)."""
    steps = []
    for n, run_dir in run_dirs.items():
        json_dir = run_dir / "json_output"
        g = {"BASE_DIR": P(BASE), "PDF_DIR": P(pdf_dir), "PROMPT_FILE": P(prompt), "ENV_FILE": P(env),
             "OUTPUT_DIR": P(json_dir), "SELECTED_PDF_DIR": P(run_dir / "selected_pdf_pages"), "JSON_DIR": P(json_dir),
             "OUTPUT_FILE": P(run_dir / "compiled_csv" / f"dsa_decomposition_{prefix}_{rnd}_{version}_run{n}.csv")}
        if rnd == "round2":
            g.update({"REPORT_LIST_FILE": P(report_list), "REPORT_LIST_CATEGORY": category, "RERUN_OUTPUT_DIR": P(json_dir)})
        if resume:
            g["SKIP_EXISTING"] = True
        steps.append({"label": f"Run {n}: extract ({scripts['extract_script'].name})" + (" · resume" if resume else ""),
                      "script": str(scripts["extract_script"]), "globals": g,
                      "watch": {"kind": "files", "dir": str(json_dir), "patterns": ["*_dsa.json"], "total": total},
                      "fail_pattern": r"^Fatal error:"})
        steps.append({"label": f"Run {n}: compile CSV ({scripts['compile_script'].name})", "script": str(scripts["compile_script"]), "globals": g})
    glob = {"$glob": {"dir": str(bdir), "pattern": f"{rnd}_{version}_run*/compiled_csv/dsa_decomposition_{prefix}_{rnd}_{version}_run*.csv", "run_sort": True}}
    steps.append({"label": "Compare the runs (1c)", "script": str(scripts["check_script"]),
                  "globals": {"ROUND": rnd, "RUN_CSVS": glob, "CHECK_DIR": P(check_dir), "RUN_DATE": version}})
    steps.append({"label": "Summary tables (1d)", "script": str(scripts["summary_script"]),
                  "globals": {"ROUND": rnd, "CHECK_DIR": P(check_dir), "RUN_DATE": version}})
    return steps


def run_progress(batch: str, rnd: str, version: str, runs: list) -> list:
    """Per run folder of a version: how many reports have a finished *_dsa.json, and how many only an error."""
    out = []
    for n in runs:
        jd = OUTPUT / batch / f"{rnd}_{version}_run{n}" / "json_output"
        done = {p.name[:-len("_dsa.json")] for p in jd.glob("*_dsa.json")} if jd.is_dir() else set()
        err = {p.name[:-len("_ERROR.json")] for p in jd.glob("*_ERROR.json")} if jd.is_dir() else set()
        csv = any((jd.parent / "compiled_csv").glob("*.csv")) if jd.parent.is_dir() else False
        out.append({"run": n, "done": len(done), "errors": len(err - done), "compiled": csv})
    return out


def resume_round(rnd: str, body: dict) -> dict:
    """Carry on with a round version that stopped before it finished (stopped, computer asleep, app closed):
    the same version, scripts, prompt and runs as when it was started. In each run, the reports that already
    have a finished *_dsa.json are skipped and the rest are extracted (a report that only has *_ERROR.json is
    tried again); runs not started yet run in full; then every run is compiled again and the runs compared."""
    s = load_settings()
    batch = batch_name(s)
    version = str(body.get("version") or "").strip()
    if not VERSION_RE.match(version):
        raise UserError("bad version")
    rec = read_json(RECORDS_DIR / safe_name(batch) / f"{rnd}_{version}.json")
    if not rec:
        raise UserError(f"{rnd} version {version} was not started from this app (no run record), so it cannot be resumed here.")
    bdir, check_dir = _round_dirs(batch, rnd, version)
    if (check_dir / f"{rnd}_check_report_summary_{version}.csv").is_file():
        raise UserError(f"{rnd} version {version} already finished; nothing to resume.")
    run = JOBS.running()
    if run:
        raise UserError("A job is still running. Wait for it to finish, or stop it first.")
    pdf_dir, env = Path(rec["pdf_dir"]), proj_path(s["env_file"])
    if not pdf_dir.is_dir():
        raise UserError(f"The PDF folder this version was started with is not found: {pdf_dir}")
    if not env.is_file():
        raise UserError(f"The .env file in Settings was not found: {env}")
    scripts = {k: CODE_DIR / v for k, v in rec["scripts"].items()}
    prompt = PROMPT_DIR / rec["prompt"]
    for p in [*scripts.values(), prompt]:
        if not p.is_file():
            raise UserError(f"Not found: {p} (this version was started with it)")
    first, n_runs = int(rec.get("first_run") or 1), int(rec["n_runs"])
    run_dirs = {n: bdir / f"{rnd}_{version}_run{n}" for n in range(first, first + n_runs)}
    report_list, category = None, rec.get("category")
    total = int(rec.get("n_reports") or 0)
    if rnd == "round2":
        r1 = rec.get("round1_version")
        report_list = bdir / f"round1_check_{r1}" / f"round1_check_disagreement_reports_{r1}.json"
        if not report_list.is_file():
            raise UserError(f"The Round 1 list this version re-reads is gone: {report_list}")
    # 1c writes nothing into a folder that already holds files: an unfinished comparison is moved aside
    if check_dir.exists() and any(check_dir.iterdir()):
        check_dir.rename(check_dir.with_name(f"{check_dir.name}_incomplete_{datetime.now():%Y%m%d_%H%M%S}"))
    steps = _round_steps(rnd, version, bdir, check_dir, run_dirs, pdf_dir, env, prompt, scripts, rec.get("csv_prefix") or "sl",
                         report_list, category, total, resume=True)
    before = run_progress(batch, rnd, version, list(run_dirs))
    params = {**{k: rec.get(k) for k in ("version", "n_runs", "first_run", "pdf_dir", "n_reports", "scripts", "prompt", "csv_prefix",
                                         "round1_version", "category")}, "resume": True, "progress_before": before}
    links = {"batch": batch, "round": rnd, "version": version}
    if rec.get("round1_version"):
        links["round1_version"] = rec["round1_version"]
    title = f"{'Round 1' if rnd == 'round1' else 'Round 2'} · {batch} · version {version} · resume"
    job = JOBS.start(rnd, title, steps, params, links, python=python_exe(s))
    rec.setdefault("resumed", []).append({"job": job["id"], "at": now(), "progress_before": before, "app_version": app_version()})
    write_json(RECORDS_DIR / safe_name(batch) / f"{rnd}_{version}.json", rec)
    return job


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
    steps = _round_steps(rnd, version, bdir, check_dir, run_dirs, pdf_dir, env, prompt, scripts, prefix,
                         report_list, category, total)
    params = {"version": version, "n_runs": n_runs, "first_run": first, "pdf_dir": str(pdf_dir), "n_reports": total,
              "scripts": {k: v.name for k, v in scripts.items()}, "prompt": prompt.name, "csv_prefix": prefix,
              "round1_version": links.get("round1_version"), "category": category}
    title = f"{'Round 1' if rnd == 'round1' else 'Round 2'} · {batch} · version {version} · {n_runs} run(s)"
    job = JOBS.start(rnd, title, steps, params, links, must_not_exist=[*run_dirs.values(), check_dir], python=python_exe(s))
    write_json(RECORDS_DIR / safe_name(batch) / f"{rnd}_{version}.json", {**params, "job": job["id"], "started": now(), "batch": batch, "app_version": app_version()})
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
        if not d.is_dir() or "_incomplete_" in d.name:  # an unfinished comparison moved aside by a resume
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
        has_check = bool(check and any(check.glob("*_report_summary_*.csv")))
        runs_all = sorted(set(f["runs"]) | (set(range(int(rec.get("first_run") or 1), int(rec.get("first_run") or 1) + int(rec["n_runs"]))) if rec and rec.get("n_runs") else set()))
        out.append({"resumable": bool(rec) and not has_check, "progress": None if has_check else run_progress(batch, rnd, v, runs_all),
                    "version": v, "has_check": has_check,
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
                "rows_compared": toint(r.get("rows_compared")), "rows_matching": toint(r.get("rows_matching")),
                "rows_differing": toint(r.get("rows_differing")), "error": clean(r.get("error_by_run")),
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


def report_meta_fallback(rd: RoundData, json_file: str) -> dict:
    """Report-level facts (title, date, table, page ...) for a report whose rows are not in this round's
    matched rows (e.g. the runs chose different years): from a run's own *_dsa.json if it is on this
    computer, else from the matched rows of another round of the same batch."""
    for d in rd.run_dirs:
        data = read_json(d / "json_output" / json_file)
        if data:
            md, src = data.get("report_metadata") or {}, data.get("source") or {}
            return {k: clean(v) for k, v in {
                "pdf_file_name": data.get("pdf_file_name") or md.get("pdf_file_name"),
                "country": md.get("country") or src.get("country"),
                "publication_date": md.get("publication_date") or src.get("publication_date"),
                "consultation_type": md.get("consultation_type") or src.get("consultation_type"),
                "report_title": md.get("report_title"), "country_report_number": md.get("country_report_number"),
                "framework": src.get("framework"), "table_number": src.get("table_number"),
                "table_title": src.get("table_title"), "page_pdf": src.get("page_pdf"),
                "page_printed": src.get("page_printed")}.items() if v not in (None, "")}
    for rnd in ROUNDS:
        for v in round_versions(rd.batch, rnd):
            if (rnd, v["version"]) == (rd.rnd, rd.version) or not v["has_check"]:
                continue
            try:
                m = RoundData(rd.batch, rnd, v["version"]).matched()
            except UserError:
                continue
            g = m[m["json_file"] == json_file]
            if len(g):
                return {c: clean(g.iloc[0].get(c)) for c in fs.REPORT_COLUMNS + ["page_printed"]
                        if c in g.columns and c not in ("last_actual_year", "actual_column_label")}
    return {}


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
    if not meta or not meta.get("report_title"):
        meta = {**report_meta_fallback(rd, json_file), **{k: v for k, v in meta.items() if v is not None}}
    meta.setdefault("json_file", json_file)
    meta.setdefault("pdf_file_name", clean(srow.get("pdf_file_name")))
    meta.setdefault("country", clean(srow.get("country")))
    return {"json_file": json_file, "round": rnd, "version": version, "n_runs": n, "source": source,
            "group": srow.get("group"), "lay_by_run": lay_by_run,
            "tf_by_run": (clean(srow.get("table_found_by_run")) or "").split("|"), "error": clean(srow.get("error_by_run")),
            "meta": meta, "rows": out_rows,
            "pdfs": report_pdfs(rd, meta.get("pdf_file_name") or srow.get("pdf_file_name"), meta.get("page_pdf"))}


# ======================================================================= human review (round 3)
# dropped: the report's values cannot be used at all; Build panel leaves every row of it out of the panel,
# including rows the previous database has for it
REVIEW_STATUSES = ("reviewed", "no_table", "skipped", "dropped")


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
                      "group": r["group"], "rows_differing": toint(r.get("rows_differing")),
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
        raise UserError("status must be reviewed, no_table, skipped or dropped")
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
            # the year and values are the reviewer's: the run's own year choice no longer describes them
            row.update({c: None for c in fs.SELECTION_COLUMNS})
            row.update(json_file=jf, last_actual_year=rv.get("last_actual_year"),
                       actual_column_label=rv.get("actual_column_label") or rv.get("last_actual_year"),
                       table_found="True", extraction_method="human_review", actual_column_validation_status="human_review",
                       manual_review_required="No", extraction_notes=rv.get("note"))
            if rv.get("page_pdf"):
                row["page_pdf"] = rv["page_pdf"]
            row.update(fs.item_fields(r["hierarchy_id"], labels))
            row.update(hierarchy_id=r["hierarchy_id"], label_verbatim=r["label_verbatim"], value=r["value"] or None)
            out.append(row)
    df = pd.DataFrame(out, columns=fs.ROUND_COLUMNS)
    return fs.to_final(df, "round3")


def rebuild_round3_rows(batch: str, version: str) -> int:
    df = round3_frame(batch, version)
    path = hr_rows_csv(batch, version)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return int(len(df))




# ======================================================================= the output folder
# The panel database is written to the output folder (Settings) as two files per version:
#     panel_pregapfill_<VERSION>.csv   Round 1-3 of every batch (+ the previous database without its gap fill)
#     panel_gapfill_<VERSION>.csv      the same rows + the gap years read by Gap Fill
#     panel_<VERSION>.json             how that version was built (the manifest)
# <VERSION> is the date and time the pre-gap-fill file was written (YYYYMMDD_HHMM); its gap-filled file
# carries the same version. The Panel database and Coverage pages read these files from the folder.
OUT_FILE_RE = re.compile(r"^panel_(?P<kind>pregapfill|gapfill)_(?P<version>[A-Za-z0-9_\-]+)\.csv$")


def output_folder(s: dict | None = None) -> Path:
    return proj_path((s or load_settings()).get("output_folder") or DEFAULTS["output_folder"])


def stamp_now() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M")


def output_files() -> list:
    """Every CSV in the output folder, newest first: the pre-gap-fill and gap-filled versions written by the
    app, and any other merged CSV kept there (e.g. final_all_batches_with_gapfill_20261028.csv)."""
    folder = output_folder()
    out = []
    for p in folder.glob("*.csv") if folder.is_dir() else []:
        if p.name.startswith(("~$", ".")):
            continue
        m = OUT_FILE_RE.match(p.name)
        st = p.stat()
        man = read_json(folder / f"panel_{m.group('version')}.json", {}) if m else {}
        out.append({"name": p.name, "path": str(p), "kind": m.group("kind") if m else "other",
                    "version": m.group("version") if m else None, "size_bytes": st.st_size,
                    "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                    "manifest": man or None})
    # newest first: versioned files by version, then the others by time
    return sorted(out, key=lambda f: (f["version"] or "", f["modified"]), reverse=True)


def latest_output(kind: str | None = None) -> dict | None:
    files = output_files()
    if kind:
        files = [f for f in files if f["kind"] == kind]
    else:  # the newest version: gap-filled if it exists, else pre-gap-fill, else any other CSV
        rank = {"gapfill": 0, "pregapfill": 1, "other": 2}
        versioned = [f for f in files if f["version"]]
        if versioned:
            top = max(f["version"] for f in versioned)
            return min((f for f in versioned if f["version"] == top), key=lambda f: rank[f["kind"]])
    return files[0] if files else None


def output_path(name: str) -> Path:
    """A file of the output folder, by name (the pages only ever send a name, not a path)."""
    if not name or "/" in name or "\\" in name or not name.lower().endswith(".csv"):
        raise UserError("bad file name")
    p = output_folder() / name
    if not p.is_file():
        raise UserError(f"{name} is not in the output folder {output_folder()}")
    return p


def any_csv(path_or_name: str) -> Path:
    """A CSV named by a full path (picked with Browse) or by its name in the output folder."""
    s = str(path_or_name or "").strip().strip('"')
    if not s:
        raise UserError("No file given.")
    p = Path(s)
    if not p.is_absolute() and ("/" in s or "\\" in s):
        p = proj_path(s)
    elif not p.is_absolute():
        p = output_folder() / s
    if not p.is_file():
        raise UserError(f"File not found: {p}")
    return p


def panel_frame_at(path: Path) -> pd.DataFrame:
    return cached(("panelf", str(path)), [path], lambda: read_csv(path))


def as_final(df: pd.DataFrame) -> pd.DataFrame:
    """Any merged CSV with a source_round column -> FINAL_COLUMNS, keeping each row's source and stamp."""
    if "source_round" not in df.columns:
        raise UserError("This CSV has no source_round column, so it is not a merged database.")
    df = df.reset_index(drop=True)
    out = fs.to_final(df, "x")
    out["source_round"] = df["source_round"].values
    out["gapfill_run"] = df["gapfill_run"].values if "gapfill_run" in df.columns else None
    out["update_origin"] = df["update_origin"].values if "update_origin" in df.columns else None
    return out


def norm_countries(df: pd.DataFrame) -> pd.Series:
    """One spelling per country, read like Gap Fill (4a) reads it: from the PDF file name
    (<Country>_<YYYY-MM-DD>...), through code/core.py's normalize_country; the country column only when the
    file name has no date. So the counts here match the gap map."""
    import core
    raw = df["pdf_file_name"].fillna("").str.extract(r"^(.*?)_\d{4}-\d{2}-\d{2}")[0]
    raw = raw.where(raw.notna() & (raw != ""), df["country"])
    uniq = {n: core.normalize_country(str(n).strip()) for n in raw.dropna().unique()}
    return raw.map(uniq)


def year_col(df: pd.DataFrame) -> str:
    """The year column of a panel file: "year" after Gap Fill, "last_actual_year" before it."""
    return "year" if "year" in df.columns else "last_actual_year"


def panel_stats(df: pd.DataFrame) -> dict:
    lay = df[year_col(df)].fillna("")
    cn = norm_countries(df)
    cy = pd.DataFrame({"c": cn, "y": lay}).drop_duplicates()
    by_origin = ({str(k): int(v) for k, v in df["update_origin"].fillna("").value_counts().items()}
                 if "update_origin" in df.columns else {})
    return {"by_origin": by_origin, "rows": int(len(df)), "reports": int(df["json_file"].nunique()), "countries": int(cn.nunique()),
            "country_years": int(len(cy)), "by_source": {str(k): int(v) for k, v in df["source_round"].fillna("").value_counts().items()}}


def output_info() -> dict:
    folder = output_folder()
    files = output_files()
    return {"folder": str(folder), "exists": folder.is_dir(), "files": files,
            "latest": latest_output(), "latest_pregapfill": latest_output("pregapfill"),
            "latest_gapfill": latest_output("gapfill")}


def panel_data(name: str, q: dict) -> dict:
    """One file of the output folder, for the Panel database page: stats, a chart of country-years by year
    and source, and one page of rows (filtered)."""
    path = output_path(name)
    df = panel_frame_at(path)
    if "source_round" not in df.columns:
        raise UserError(f"{name} has no source_round column; it is not a panel database file.")
    order = fs.PANEL_COLUMNS if "year" in df.columns else fs.FINAL_COLUMNS
    cols = [c for c in order if c in df.columns] + [c for c in df.columns if c not in order]
    f = df
    country = (q.get("country") or "").strip().lower()
    if country:
        f = f[f["country"].fillna("").str.lower().str.contains(re.escape(country))]
    if q.get("year"):
        f = f[f[year_col(df)] == q["year"]]
    if q.get("source"):
        f = f[f["source_round"] == q["source"]]
    if q.get("origin") and "update_origin" in df.columns:
        f = f[f["update_origin"].fillna("") == ("" if q["origin"] == "none" else q["origin"])]
    if q.get("top_only") in ("1", "true"):
        f = f[~f["hierarchy_id"].fillna("").str.contains(r"\.")]
    if q.get("hid"):
        f = f[f["hierarchy_id"] == q["hid"]]
    page, size = int(q.get("page") or 0), min(int(q.get("size") or 100), 500)
    rows = f[cols].iloc[page * size:(page + 1) * size]

    def summary():
        yc = year_col(df)
        years = sorted({y for y in df[yc].dropna().unique() if re.fullmatch(r"\d{4}", str(y))})
        sub = df[df[yc].isin(years)]
        cy = pd.DataFrame({"country": norm_countries(sub), "last_actual_year": sub[yc],
                           "source_round": sub["source_round"]}).drop_duplicates(["country", "last_actual_year"])
        by_year: dict = {}
        for (y, sr), n in cy.groupby(["last_actual_year", "source_round"]).size().items():
            by_year.setdefault(y, {})[sr] = int(n)
        return {"stats": panel_stats(df), "years": years, "by_year": by_year}
    sm = cached(("panelsum", str(path)), [path], summary)
    m = OUT_FILE_RE.match(path.name)
    return {"name": path.name, "path": str(path), "columns": cols, "n_filtered": int(len(f)), "page": page, "size": size,
            "rows": rows.astype(object).where(rows.notna(), None).values.tolist(), "sources": fs.SOURCE_ROUNDS,
            "manifest": read_json(path.parent / f"panel_{m.group('version')}.json", {}) if m else {}, **sm}


# ======================================================================= build the pre-gap-fill panel
def batches_with_rounds() -> list:
    """Every batch folder under output/ with Round 1 or Round 2 results, with its versions and review state."""
    out = []
    for d in sorted(p for p in OUTPUT.iterdir() if p.is_dir()) if OUTPUT.is_dir() else []:
        if not any(d.glob("round1_check_*")) and not any(d.glob("round2_check_*")):
            continue
        v1 = [v for v in round_versions(d.name, "round1") if v["has_check"]]
        v2 = [v for v in round_versions(d.name, "round2") if v["has_check"]]
        reviews = {}
        for v in v2:
            try:
                q = hr_queue(d.name, v["version"])
                reviews[v["version"]] = {"total": len(q["items"]), "counts": q["counts"], "rows": q["rows_ready"]}
            except UserError:
                pass
        out.append({"batch": d.name, "round1": v1, "round2": v2, "reviews": reviews})
    return out


def _components(body: dict) -> list:
    comps = []
    for c in body.get("components") or []:
        if not c.get("include", True):
            continue
        batch = str(c.get("batch") or "")
        if not batch or not (OUTPUT / batch).is_dir():
            raise UserError(f"Unknown batch: {batch}")
        comps.append({"batch": batch, "round1": c.get("round1") or None, "round2": c.get("round2") or None,
                      "round3": bool(c.get("round3", True)) and bool(c.get("round2"))})
    return comps


def build_frame(body: dict):
    """The pre-gap-fill panel: the previous database (optionally without its gap fill rows) + the new Round
    1/2/3 rows of the chosen batches. Returns (rows, report of what went in)."""
    report = {"base": None, "parts": [], "problems": []}
    base = pd.DataFrame(columns=fs.FINAL_COLUMNS)
    if body.get("base"):
        bpath = any_csv(body["base"])
        base = as_final(panel_frame_at(bpath))
        n_all = len(base)
        by_src = {str(k): int(v) for k, v in base["source_round"].fillna("").value_counts().items()}
        removed = 0
        if body.get("remove_gapfill", True):
            gap = base["source_round"] == "gapfill"
            removed = int(gap.sum())
            base = base[~gap]
        base = base.copy()
        base["update_origin"] = "previous"  # taken over unchanged from the previous database
        report["base"] = {"file": str(bpath), "name": bpath.name, "rows": n_all, "by_source": by_src,
                          "legacy": "column_header_audit_json" not in panel_frame_at(bpath).columns,
                          "gapfill_removed": removed, "rows_kept": int(len(base)), "reports_kept": int(base["json_file"].nunique())}
    new_frames = []
    for c in _components(body):
        for rnd in ("round1", "round2"):
            if c[rnd]:
                df = RoundData(c["batch"], rnd, c[rnd]).ready_rows()
                new_frames.append(df)
                report["parts"].append({"batch": c["batch"], "source": rnd, "version": c[rnd], "rows": int(len(df)),
                                        "reports": int(df["json_file"].nunique())})
        if c["round3"]:
            df = round3_frame(c["batch"], c["round2"])
            q = hr_queue(c["batch"], c["round2"])
            new_frames.append(df)
            report["parts"].append({"batch": c["batch"], "source": "round3", "version": c["round2"], "rows": int(len(df)),
                                    "reports": int(df["json_file"].nunique()) if len(df) else 0,
                                    "to_review": len(q["items"]), "todo": q["counts"]["todo"]})
    new = fs.concat_final(new_frames)
    report["problems"] = [p for p in fs.check_final(new)] if len(new) else []
    # a report that is both in the previous database and among the new rows: keep one of the two
    dup_ids = sorted(set(new["json_file"]) & set(base["json_file"])) if len(new) and len(base) else []
    replace = body.get("duplicates") == "replace"
    if dup_ids:
        if replace:
            base = base[~base["json_file"].isin(dup_ids)]
        else:
            new = new[~new["json_file"].isin(dup_ids)]
    # reports dropped in Human Review: none of their rows goes into the panel, wherever they come from
    dropped = set()
    for c in _components(body):
        if c["round2"]:
            dropped |= {jf for jf, rv in hr_reviews(c["batch"], c["round2"]).items() if rv.get("status") == "dropped"}
    if dropped:
        rm_base, rm_new = int(base["json_file"].isin(dropped).sum()), int(new["json_file"].isin(dropped).sum())
        base, new = base[~base["json_file"].isin(dropped)], new[~new["json_file"].isin(dropped)]
        report["dropped"] = {"reports": len(dropped), "rows_removed_previous": rm_base, "rows_removed_new": rm_new,
                             "examples": sorted(dropped)[:5]}
    by_src_new = new.groupby("json_file")["source_round"].nunique() if len(new) else pd.Series(dtype=int)
    multi = sorted(by_src_new[by_src_new > 1].index)
    if multi:
        report["problems"].append(f"{len(multi)} report(s) come from more than one new source, e.g. {multi[:3]}")
    new = new.copy()
    new["update_origin"] = "new"  # this update's Round 1 / 2 / 3 results
    out = fs.concat_final([base, new])
    report["by_origin"] = {str(k): int(v) for k, v in out["update_origin"].fillna("").value_counts().items()}
    report.update({"duplicates": len(dup_ids), "duplicates_mode": "replace" if replace else "keep_previous",
                   "duplicate_examples": dup_ids[:5], "new_rows": int(len(new)),
                   "new_reports": int(new["json_file"].nunique()) if len(new) else 0,
                   "total": panel_stats(out) if len(out) else {"rows": 0}, "columns_ok": list(out.columns) == fs.FINAL_COLUMNS,
                   "n_columns": len(fs.FINAL_COLUMNS),
                   "base_legacy": bool(report["base"]) and report["base"].get("legacy", False)})
    return out, report


def build_preview(body: dict) -> dict:
    _, report = build_frame(body)
    return report


def build_write(body: dict) -> dict:
    folder = output_folder()
    if not folder.is_dir():
        raise UserError(f"The output folder in Settings does not exist: {folder}")
    df, report = build_frame(body)
    if not len(df):
        raise UserError("Nothing to write: no previous database and no new rows.")
    bad = [p for p in report["problems"] if "hierarchy_id" in p or "columns" in p]
    if bad:
        raise UserError("Not written: " + "; ".join(bad))
    version = str(body.get("version") or stamp_now()).strip()
    if not VERSION_RE.match(version):
        raise UserError("The version may only use letters, digits, - and _.")
    path = folder / f"panel_pregapfill_{version}.csv"
    if path.exists():
        raise UserError(f"{path.name} already exists in the output folder. Pick another version.")
    df.to_csv(path, index=False, encoding="utf-8-sig")
    manifest = {"version": version, "created": now(), "app_version": app_version(), "output_folder": str(folder),
                "pregapfill": {"file": path.name, "written": now(), **report,
                               "components": _components(body), "remove_gapfill": bool(body.get("remove_gapfill", True))},
                "gapfill": None}
    write_json(folder / f"panel_{version}.json", manifest)
    write_json(RECORDS_DIR / "builds" / f"{version}.json", manifest)  # the app's own record of the build
    return {"version": version, "file": str(path), **report}


def builds() -> list:
    folder = RECORDS_DIR / "builds"
    out = []
    for p in sorted(folder.glob("*.json"), reverse=True) if folder.is_dir() else []:
        m = read_json(p, {}) or {}
        out.append(m)
    return out


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
    """Gap Fill steps 1-2 (4a, 4b) on a pre-gap-fill file of the output folder. The gap fill version is the
    file's version, so its gap-filled file gets the same version."""
    s = load_settings()
    gcfg = s["gapfill"]
    name = str(body.get("input") or "")
    input_csv = output_path(name)
    m = OUT_FILE_RE.match(name)
    stamp = m.group("version") if m and m.group("kind") == "pregapfill" else str(body.get("stamp") or stamp_now())
    if m and m.group("kind") == "gapfill":
        raise UserError("Pick a pre-gap-fill file: a gap-filled file already holds gap fill rows.")
    if not VERSION_RE.match(stamp):
        raise UserError("bad version")
    check, outd = gap_dirs(stamp)
    if check.exists():
        raise UserError(f"The gaps of version {stamp} were already identified; continue with it below.")
    y0, y1 = int(body.get("year_from") or gcfg["year_from"]), int(body.get("year_to") or gcfg["year_to"])
    if not 1990 <= y0 <= y1 <= 2100:
        raise UserError("Check the year range.")
    root = proj_path(s["staff_reports_root"])
    if not root.is_dir():
        raise UserError(f"The staff reports root folder in Settings was not found: {root}")
    if "source_round" in read_csv(input_csv, nrows=5).columns and (read_csv(input_csv, usecols=["source_round"])["source_round"] == "gapfill").any():
        note = "The input still holds gap fill rows; those country-years count as observed."
    else:
        note = None
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
    rec = {"stamp": stamp, "input": name, "input_csv": str(input_csv), "output_folder": str(output_folder()),
           "years": [y0, y1], "panel_countries_file": panel_countries, "created": now(), "note": note}
    job = JOBS.start("gap_identify", f"Gap Fill · find the gaps · version {stamp} ({y0}-{y1})", steps,
                     rec, {"gap": stamp}, must_not_exist=[check], python=python_exe(s))
    rec["identify_job"] = job["id"]
    write_json(RECORDS_DIR / "gapfill" / f"{stamp}.json", rec)
    return job


def seed_answers(stamp: str) -> int:
    """Copy the answers saved by earlier gap fill runs (output/gapfill/output/*/reports/*_gapfill.json) into
    this run's cache, so a (report, year) already asked is not asked again. Answers for the same report from
    several runs are merged; the newest run wins for the same year."""
    _, outd = gap_dirs(stamp)
    dest = outd / "reports"
    dest.mkdir(parents=True, exist_ok=True)
    runs = sorted((d for d in GAP_OUT_ROOT.glob("*") if d.is_dir() and d != outd and (d / "reports").is_dir()),
                  key=lambda d: d.stat().st_mtime)
    merged: dict = {}
    for d in runs:  # oldest first, so newer answers overwrite older ones
        for f in (d / "reports").glob("*_gapfill.json"):
            rec = read_json(f)
            if not isinstance(rec, dict):
                continue
            cur = merged.get(f.name)
            if cur is None:
                merged[f.name] = json.loads(json.dumps(rec))
            else:
                per = dict(cur.get("per_target") or {})
                per.update(rec.get("per_target") or {})
                merged[f.name] = {**cur, **rec, "per_target": per}
    n = 0
    for name, rec in merged.items():
        target = dest / name
        if target.exists():
            mine = read_json(target, {}) or {}
            per = dict(rec.get("per_target") or {})
            per.update(mine.get("per_target") or {})  # this run's own answers win
            rec = {**rec, **mine, "per_target": per}
        write_json(target, rec)
        n += 1
    return n


def start_gap_fill(body: dict) -> dict:
    s = load_settings()
    stamp = str(body.get("stamp") or "")
    rec = read_json(RECORDS_DIR / "gapfill" / f"{safe_name(stamp)}.json")
    if not rec:
        raise UserError("Unknown gap fill version.")
    check, outd = gap_dirs(stamp)
    if not (check / f"gapfill_targets_{stamp}.csv").is_file():
        raise UserError("Find the gaps first.")
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
    if mode == "fill" and not proj_path(s["env_file"]).is_file():
        raise UserError(f"The .env file in Settings was not found: {proj_path(s['env_file'])}")
    seeded = None
    if mode in ("fill", "collect") and body.get("reuse_answers", True) and not rec.get("seeded"):
        seeded = seed_answers(stamp)
        rec["seeded"] = {"reports": seeded, "at": now()}
    g = _gap_common(s, stamp)
    label = {"fill": "Read the gap years from later reports (4c, API)", "dry_run": "Dry run: list the planned calls (4c, no API)",
             "collect": "Rebuild the result files from saved answers (4c, no API)"}[mode]
    steps = [{"label": label, "script": str(CODE_DIR / s["gapfill"]["api_script"]), "globals": g, "argv": argv,
              "watch": {"kind": "log"}}]
    job = JOBS.start("gap_fill", f"Gap Fill · {mode.replace('_', ' ')} · version {stamp}", steps,
                     {"stamp": stamp, "mode": mode, "argv": argv, "seeded_reports": seeded}, {"gap": stamp}, python=python_exe(s))
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
    written = output_folder() / f"panel_gapfill_{stamp}.csv"
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
            "rows_file": str(f_final), "written": written.name if written.is_file() else None,
            "output_folder": str(output_folder()),
            "summary": {k: summary.get(k) for k in ("n_reports", "n_countries_in_panel", "n_gap_years", "n_gap_spans", "cause_counts_by_span")}}


REPORT_FACTS = ["publication_date", "consultation_type", "report_title", "country_report_number"]


def fill_report_facts(rows: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    """Gap Fill reads a later report's table, which seldom shows the report's own title, date or number; the
    same report is usually already in the panel (from its own Round 1-3 extraction), so its facts are taken
    from there where the gap fill rows have none."""
    if not len(rows) or not len(panel):
        return rows
    known = panel.dropna(subset=["report_title"]).drop_duplicates("json_file").set_index("json_file")
    rows = rows.copy()
    for c in REPORT_FACTS:
        if c in known.columns:
            fill = rows["json_file"].map(known[c])
            rows[c] = rows[c].where(rows[c].notna() & (rows[c].astype(str).str.strip() != ""), fill)
    return rows


def gap_write(body: dict) -> dict:
    """panel_gapfill_<VERSION>.csv = the pre-gap-fill file the gaps were found in + the gap years filled."""
    stamp = str(body.get("stamp") or "")
    rec = read_json(RECORDS_DIR / "gapfill" / f"{safe_name(stamp)}.json")
    if not rec:
        raise UserError("Unknown gap fill version.")
    _, outd = gap_dirs(stamp)
    f_final = outd / f"gapfill_rows_final_{stamp}.csv"
    if not f_final.is_file():
        raise UserError("No gap fill results yet (fill the gaps, or 'Rebuild results' for a run made with older code).")
    # gap fill rows and the panel after Gap Fill have "year", not last_actual_year (final_schema.PANEL_COLUMNS)
    new = fs.to_panel(read_csv(f_final))
    new["source_round"], new["gapfill_run"], new["update_origin"] = "gapfill", stamp, "new"
    if not len(new):
        raise UserError("No gap year has been filled in this version yet, so there is nothing to write.")
    src = Path(rec["input_csv"])
    if not src.is_file():
        raise UserError(f"The pre-gap-fill file is gone: {src}")
    base = fs.to_panel(as_final(read_csv(src)))  # Round 1-3 rows: year = their last actual year
    new = fill_report_facts(new, base)
    folder = output_folder()
    path = folder / f"panel_gapfill_{stamp}.csv"
    if path.exists() and not body.get("overwrite"):
        raise UserError(f"{path.name} already exists. Tick 'overwrite' to write it again (e.g. after more gaps were filled).")
    out = pd.concat([base, new], ignore_index=True)[fs.PANEL_COLUMNS]
    out.to_csv(path, index=False, encoding="utf-8-sig")
    info = {"file": path.name, "written": now(), "from": src.name, "gap_rows": int(len(new)), "columns": "year (no last_actual_year)",
            "by_origin": {str(k): int(v) for k, v in out["update_origin"].fillna("").value_counts().items()},
            "gap_years_filled": int(new[["country", "year"]].drop_duplicates().shape[0]), "total": panel_stats(out)}
    man_path = folder / f"panel_{stamp}.json"
    man = read_json(man_path, {}) or {"version": stamp, "created": now(), "output_folder": str(folder), "pregapfill": None}
    man["gapfill"] = {**info, "app_version": app_version()}
    write_json(man_path, man)
    if (RECORDS_DIR / "builds" / f"{stamp}.json").is_file():
        write_json(RECORDS_DIR / "builds" / f"{stamp}.json", man)
    rec["written"] = info
    write_json(RECORDS_DIR / "gapfill" / f"{stamp}.json", rec)
    return info


# ======================================================================= intermediate data (archive) and exports
def archive() -> dict:
    """Everything the rounds produced, every batch: for the Intermediate data tab."""
    rows1, rows2, hr = [], [], []
    for b in batches_with_rounds():
        for v in b["round1"]:
            rows1.append({"batch": b["batch"], **v})
        for v in b["round2"]:
            rows2.append({"batch": b["batch"], **v})
            r = b["reviews"].get(v["version"])
            if r:
                path = hr_rows_csv(b["batch"], v["version"])
                hr.append({"batch": b["batch"], "version": v["version"], **r,
                           "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds") if path.is_file() else None})
    return {"round1": rows1, "round2": rows2, "human_review": hr, "builds": builds(), "gap_runs": gap_runs(),
            "output": output_info()}


EXPORTS = {
    "ready": "rows ready to append (fully matched reports, panel columns)",
    "matched": "matched rows (as written by 1c)",
    "diffs": "differing rows, every run's value",
    "summary": "one row per report: group, years by run, rows compared",
    "round3": "human review rows (panel columns)",
    "pregapfill": "pre-gap-fill panel",
    "gaprows": "gap fill rows (panel columns)",
    "gapresolution": "gap fill result per gap year",
}


def export_file(q: dict):
    """(file name, CSV bytes) for a download from the Intermediate data tab."""
    kind, batch, version = q.get("kind"), q.get("batch") or "", q.get("version") or ""
    if kind in ("ready", "matched", "diffs", "summary"):
        rd = RoundData(batch, q.get("round") or "round1", version)
        if kind == "ready":
            df, name = rd.ready_rows(), f"{rd.rnd}_fully_matched_rows_{batch}_{version}.csv"
        else:
            path = {"matched": rd.f_matched, "diffs": rd.f_diffs, "summary": rd.f_summary}[kind]
            return f"{batch}_{path.name}", path.read_bytes()
    elif kind == "round3":
        df, name = round3_frame(batch, version), f"round3_reviewed_rows_{batch}_{version}.csv"
    elif kind == "pregapfill":
        p = output_folder() / f"panel_pregapfill_{version}.csv"
        if not p.is_file():
            raise UserError(f"{p.name} is not in the output folder")
        return p.name, p.read_bytes()
    elif kind in ("gaprows", "gapresolution"):
        _, outd = gap_dirs(version)
        p = outd / (f"gapfill_rows_final_{version}.csv" if kind == "gaprows" else f"gapfill_resolution_{version}.csv")
        if not p.is_file():
            raise UserError(f"{p.name} not found")
        return p.name, p.read_bytes()
    else:
        raise UserError("unknown export")
    return name, df.to_csv(index=False).encode("utf-8-sig")


# ======================================================================= choosing files and folders
def browse_native(kind: str, start: str | None, title: str | None) -> dict:
    """Open the computer's own file / folder dialog (Finder on a Mac, Explorer on Windows) and return the
    path picked. Runs in a separate process, so the dialog has its own main thread."""
    start_dir = Path(start) if start else BASE
    if start_dir.is_file():
        start_dir = start_dir.parent
    if not start_dir.is_dir():
        start_dir = BASE
    prompt = (title or ("Choose a folder" if kind == "dir" else "Choose a file")).replace('"', "'")
    try:
        if sys.platform == "darwin":
            what = "choose folder" if kind == "dir" else "choose file"
            script = (f'tell application (path to frontmost application as text)\n'
                      f'  set p to {what} with prompt "{prompt}" default location (POSIX file "{start_dir}")\n'
                      f'end tell\nPOSIX path of p')
            r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=600)
            if r.returncode != 0:
                if "-128" in r.stderr:  # user cancelled
                    return {"cancelled": True}
                raise RuntimeError(r.stderr.strip())
            path = r.stdout.strip()
        else:
            code = ("import sys, tkinter as tk\nfrom tkinter import filedialog\nr = tk.Tk(); r.withdraw(); r.attributes('-topmost', True)\n"
                    f"p = filedialog.{'askdirectory' if kind == 'dir' else 'askopenfilename'}(initialdir=sys.argv[1], title=sys.argv[2])\n"
                    "print(p or '')")
            r = subprocess.run([sys.executable, "-c", code, str(start_dir), prompt], capture_output=True, text=True, timeout=600)
            if r.returncode != 0:
                raise RuntimeError(r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "dialog failed")
            path = r.stdout.strip()
            if not path:
                return {"cancelled": True}
    except Exception as e:  # no dialog on this computer: the page falls back to its own folder browser
        return {"unavailable": True, "error": str(e)}
    path = path.rstrip("/") if len(path) > 1 and kind == "dir" else path
    return {"path": str(Path(path))}


def list_dir(path: str | None) -> dict:
    """A folder's sub-folders and files, for the page's own folder browser (when no dialog is available)."""
    p = Path(path) if path else BASE
    if not p.is_dir():
        p = p.parent if p.parent.is_dir() else BASE
    dirs, files = [], []
    try:
        for c in sorted(p.iterdir(), key=lambda x: x.name.lower()):
            if c.name.startswith("."):
                continue
            (dirs if c.is_dir() else files).append(c.name)
    except OSError as e:
        raise UserError(f"Cannot open {p}: {e}")
    roots = [str(Path.home()), str(BASE)]
    return {"path": str(p), "parent": str(p.parent) if p.parent != p else None, "dirs": dirs, "files": files[:500], "roots": roots}


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
    ready = []
    for rnd, v in (("round1", r1), ("round2", r2)):
        if v:
            try:
                df = RoundData(batch, rnd, v).ready_rows()
                ready.append({"source": rnd, "version": v, "rows": int(len(df)), "reports": int(df["json_file"].nunique())})
            except UserError:
                pass
    if hr:
        ready.append({"source": "round3", "version": r2, "rows": hr["rows_ready"], "reviewed": hr["total"] - hr["counts"]["todo"], "total": hr["total"]})
    return {"batch": batch, "round1": v1, "round2": v2, "round1_selected": r1, "round2_selected": r2,
            "human_review": hr, "ready": ready, "output": output_info(), "gap_runs": gap_runs(), "builds": builds()[:5],
            "job": JOBS.latest()}


def allowed_pdf(path: str) -> Path:
    """A PDF the page may show: inside the project folder or one of the PDF folders in Settings."""
    p = Path(path).resolve()
    s = load_settings()
    roots = [BASE.resolve(), proj_path(s["pdf_dir"]).resolve(), proj_path(s["staff_reports_root"]).resolve()]
    if p.suffix.lower() != ".pdf" or not p.is_file() or not any(p == r or r in p.parents for r in roots):
        raise UserError("PDF not available")
    return p
