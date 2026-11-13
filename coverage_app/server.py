"""
DSA coverage web app: generate the country-year coverage database and browse it in the browser.
    python coverage_app/server.py            then open http://127.0.0.1:8765 (opens by itself)
    python coverage_app/server.py --port 8800 --no-browser

Only the Python standard library plus what the project already uses (pandas, openpyxl). The page is
served from coverage_app/static/ and talks to the small JSON API below. It listens on 127.0.0.1 only,
so nobody else on the network can reach it.

Generating runs code/check_coverage_database.py's main() in a background thread. Every run writes, in
that script's OUT_DIR, coverage_database_<STAMP>.xlsx and coverage_database_<STAMP>.json (the run record:
when, which final CSV with its size / modified time / SHA-256, which PDF folders). The version history in
the app is the list of those files, so runs made from the command line show up too.

API
    GET  /api/defaults                  default paths and batches from check_coverage_database.py
    POST /api/inspect                   {final_csv, pdf_root} -> does each exist; batch folders found
    POST /api/generate                  {final_csv, pdf_root, batches, stamp} -> starts a run
    GET  /api/job                       state of the current / last run, with its log
    GET  /api/runs                      the version history, newest first
    GET  /api/runs/<stamp>/data         one version's Coverage table, compact, for the Database and
                                        Dashboard tabs
    GET  /api/runs/<stamp>/download     that version's workbook

Workflow and Panel database (see workflow.py; every path starts with /api/wf/)
    GET  settings | file?kind=code|prompt&name= | overview?r1=&r2= | job | jobs | job/<id>
    GET  versions/<round> | review/<round>/<version> | review/<round>/<version>/report?json_file=
    GET  hr/<version> | hr/<version>/item?json_file= | staging?r1=&r2=
    GET  panel | panel/<stamp>/data?country=&year=&source=&top_only=&page= | panel/<stamp>/download
    GET  gap | gap/<stamp> | pdf?path=
    POST settings | run/round1 | run/round2 | run/gap_identify | run/gap_fill | job/stop
    POST hr/<version>/save | panel/import | panel/append | gap/append
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import sys
import threading
import traceback
import webbrowser
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

APP_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd() / "coverage_app"
STATIC_DIR = APP_DIR / "static"
CODE_DIR = APP_DIR.parent / "code"
sys.path.insert(0, str(CODE_DIR))
import check_coverage_database as ccd  # noqa: E402
import workflow as wf  # noqa: E402  (coverage_app/workflow.py: the Workflow and Panel database tabs)

import pandas as pd  # noqa: E402

BATCH_RE = re.compile(r"^\d{4}-\d{4}$")
STAMP_RE = re.compile(r"^[A-Za-z0-9_\-]{1,40}$")
WORKBOOK_RE = re.compile(r"^coverage_database(?:_(?P<stamp>.+))?\.xlsx$")


# ================================================================= versions
def out_dir() -> Path:
    return Path(ccd.OUT_DIR)


def stamp_of(path: Path) -> str:
    m = WORKBOOK_RE.match(path.name)
    return (m.group("stamp") or "") if m else ""


def list_runs() -> list:
    """Every coverage_database*.xlsx in OUT_DIR with its run record (if it has one), newest first."""
    runs = []
    folder = out_dir()
    if not folder.is_dir():
        return runs
    for xlsx in folder.glob("coverage_database*.xlsx"):
        if xlsx.name.startswith("~$") or not WORKBOOK_RE.match(xlsx.name):
            continue
        record_path = xlsx.with_suffix(".json")
        record = {}
        if record_path.exists():
            try:
                record = json.loads(record_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                record = {}
        modified = datetime.fromtimestamp(xlsx.stat().st_mtime).isoformat(timespec="seconds")
        runs.append({**record, "stamp": stamp_of(xlsx), "workbook": xlsx.name,
                     "created": record.get("created") or modified, "has_record": bool(record)})
    return sorted(runs, key=lambda r: r["created"], reverse=True)


def workbook_for(stamp: str) -> Path | None:
    name = f"coverage_database_{stamp}.xlsx" if stamp else "coverage_database.xlsx"
    path = out_dir() / name
    return path if path.exists() else None


def unique_stamp(stamp: str) -> str:
    """The stamp asked for, or stamp_2, stamp_3 ... if a workbook with it already exists -- a run never
    overwrites an earlier version."""
    candidate, n = stamp, 2
    while (out_dir() / f"coverage_database_{candidate}.xlsx").exists():
        candidate, n = f"{stamp}_{n}", n + 1
    return candidate


_cache: dict = {}
_cache_lock = threading.Lock()


def coverage_payload(path: Path) -> dict:
    """The workbook's Coverage and Indicators sheets in a compact form: one string of 1/0 per column.
    Workbooks with a Sources sheet also give sources (one character per row: 1 / 2 / 3 = Round 1-3,
    g = Gap fill, 0 = no value); with a Report years sheet, report_years (per country, every publication
    year with a staff report, all years)."""
    key = (str(path), path.stat().st_mtime)
    with _cache_lock:
        if key in _cache:
            return _cache[key]
    sheets = pd.read_excel(path, sheet_name=None, dtype=str)
    cov, ind = sheets["Coverage"], sheets["Indicators"]
    countries = sorted(cov["country"].unique())
    idx = {c: i for i, c in enumerate(countries)}
    flag_cols = [c for c in cov.columns if c not in ("country", "year")]
    info = {r["column"]: r for r in ind.fillna("").to_dict("records")}
    payload = {
        "countries": countries,
        "row_country": [idx[c] for c in cov["country"]],
        "row_year": [int(y) for y in cov["year"]],
        "columns": [{
            "name": c,
            "hierarchy_id": info.get(c, {}).get("hierarchy_id", ""),
            "level": info.get(c, {}).get("level", ""),
            "top_category": info.get(c, {}).get("top_category", ""),
            "labels": info.get(c, {}).get("most_common_labels", ""),
        } for c in flag_cols],
        "flags": {c: "".join("1" if v == "Yes" else "0" for v in cov[c]) for c in flag_cols},
    }
    src = sheets.get("Sources")
    if src is not None and len(src) == len(cov):
        code = {"Round 1": "1", "Round 2": "2", "Round 3": "3", "Gap fill": "g"}
        payload["sources"] = {c: "".join(code.get(v, "0") for v in src[c].fillna(""))
                              for c in flag_cols if c in src.columns}
    ry = sheets.get("Report years")
    if ry is not None:
        years = [[] for _ in countries]
        for c, y in zip(ry["country"], ry["year"]):
            if c in idx:
                years[idx[c]].append(int(y))
        payload["report_years"] = [sorted(set(v)) for v in years]
        payload["report_year_range"] = [int(ry["year"].astype(int).min()), int(ry["year"].astype(int).max())] if len(ry) else None
    with _cache_lock:
        _cache.clear()  # keep only the latest workbook in memory
        _cache[key] = payload
    return payload


# ================================================================= generate (one run at a time)
class _LogWriter(io.TextIOBase):
    def __init__(self, job: dict):
        self.job, self.buf = job, ""

    def write(self, s):
        self.buf += s
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            with JOB_LOCK:
                self.job["log"].append(line)
        return len(s)


JOB_LOCK = threading.Lock()
JOB: dict = {"state": "idle", "log": [], "stamp": None, "error": None, "started": None, "finished": None,
             "progress": 0.0, "stage": ""}


def _progress(fraction: float, label: str):
    with JOB_LOCK:
        JOB.update(progress=round(float(fraction), 3), stage=label)


def _run_job(final_csv: Path, pdf_root: Path, batches: list, stamp: str):
    writer = _LogWriter(JOB)
    try:
        with contextlib.redirect_stdout(writer):
            print(f"Final CSV: {final_csv}")
            print(f"PDF folder: {pdf_root}  (batches: {', '.join(batches)})")
            print(f"Stamp: {stamp}\n")
            ccd.main(final_csv=final_csv, pdf_root=pdf_root, out_dir=out_dir(), stamp=stamp, batches=batches,
                     progress=_progress)
        with JOB_LOCK:
            JOB.update(state="done", finished=datetime.now().isoformat(timespec="seconds"))
    except Exception as e:  # report any failure in the page instead of losing it in the console
        with JOB_LOCK:
            JOB["log"].extend(traceback.format_exc().rstrip().splitlines())
            JOB.update(state="error", error=f"{type(e).__name__}: {e}",
                       finished=datetime.now().isoformat(timespec="seconds"))


def start_job(body: dict) -> tuple[int, dict]:
    final_csv = Path(str(body.get("final_csv", "")).strip().strip('"'))
    pdf_root = Path(str(body.get("pdf_root", "")).strip().strip('"'))
    batches = [b for b in body.get("batches", []) if isinstance(b, str) and b.strip()]
    stamp = str(body.get("stamp") or "").strip() or datetime.now().strftime("%Y%m%d_%H%M")
    problems = []
    if not final_csv.is_file():
        problems.append(f"Final CSV not found: {final_csv}")
    if not pdf_root.is_dir():
        problems.append(f"PDF folder not found: {pdf_root}")
    if not batches:
        problems.append("Pick at least one batch folder.")
    missing = [b for b in batches if not (pdf_root / b).is_dir()]
    if pdf_root.is_dir() and missing:
        problems.append(f"Batch folder(s) not found under the PDF folder: {', '.join(missing)}")
    if not STAMP_RE.match(stamp):
        problems.append("Stamp may only use letters, digits, - and _ (up to 40 characters).")
    if problems:
        return HTTPStatus.BAD_REQUEST, {"error": " ".join(problems)}
    with JOB_LOCK:
        if JOB["state"] == "running":
            return HTTPStatus.CONFLICT, {"error": "A run is already in progress."}
        stamp = unique_stamp(stamp)
        JOB.update(state="running", log=[], stamp=stamp, error=None, progress=0.0, stage="Starting",
                   started=datetime.now().isoformat(timespec="seconds"), finished=None)
    threading.Thread(target=_run_job, args=(final_csv, pdf_root, batches, stamp), daemon=True).start()
    return HTTPStatus.ACCEPTED, {"stamp": stamp}


def inspect(body: dict) -> dict:
    out = {}
    csv = Path(str(body.get("final_csv", "")).strip().strip('"'))
    if csv.is_file():
        st = csv.stat()
        out["final_csv"] = {"exists": True, "size_bytes": st.st_size,
                            "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")}
    else:
        out["final_csv"] = {"exists": False}
    root = Path(str(body.get("pdf_root", "")).strip().strip('"'))
    if root.is_dir():
        batches = []
        for d in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith((".", "__"))):
            n = sum(1 for f in d.rglob("*.pdf") if f.is_file())
            batches.append({"name": d.name, "n_pdfs": n, "looks_like_batch": bool(BATCH_RE.match(d.name))})
        direct = sum(1 for f in root.glob("*.pdf") if f.is_file())  # PDFs not in any batch folder (not read)
        out["pdf_root"] = {"exists": True, "folders": batches, "n_direct_pdfs": direct}
    else:
        out["pdf_root"] = {"exists": False, "folders": []}
    return out


# ================================================================= HTTP
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, fmt, *args):  # keep the console quiet except for errors
        if args and str(args[1]).startswith(("4", "5")):
            super().log_message(fmt, *args)

    def _json(self, status, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return {}

    def _file(self, path: Path, ctype: str, download: bool = False):
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        disp = "attachment" if download else "inline"
        self.send_header("Content-Disposition", f'{disp}; filename="{path.name}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _wf(self, method: str, route: str, q: dict, body: dict):
        """The Workflow / Panel database API. A wf.UserError is answered with 400 and its message."""
        try:
            parts = route.strip("/").split("/")
            s = wf.load_settings()
            batch = wf.batch_name(s)
            if method == "GET":
                if route == "settings":
                    return self._json(HTTPStatus.OK, wf.settings_info())
                if route == "file":
                    return self._json(HTTPStatus.OK, wf.read_source(q.get("kind"), q.get("name")))
                if route == "overview":
                    return self._json(HTTPStatus.OK, wf.overview(q.get("r1"), q.get("r2")))
                if route == "job":
                    return self._json(HTTPStatus.OK, {"job": wf.JOBS.latest()})
                if route == "jobs":
                    return self._json(HTTPStatus.OK, {"jobs": wf.JOBS.history()})
                if parts[0] == "job" and len(parts) == 2:
                    return self._json(HTTPStatus.OK, {"job": wf.JOBS.get(parts[1], int(q.get("lines") or 2000))})
                if parts[0] == "versions" and len(parts) == 2:
                    return self._json(HTTPStatus.OK, {"versions": wf.round_versions(batch, parts[1])})
                if parts[0] == "review" and len(parts) == 3:
                    return self._json(HTTPStatus.OK, wf.review_summary(batch, parts[1], parts[2]))
                if parts[0] == "review" and len(parts) == 4 and parts[3] == "report":
                    return self._json(HTTPStatus.OK, wf.report_detail(batch, parts[1], parts[2], q.get("json_file", "")))
                if parts[0] == "hr" and len(parts) == 2:
                    return self._json(HTTPStatus.OK, wf.hr_queue(batch, parts[1]))
                if parts[0] == "hr" and len(parts) == 3 and parts[2] == "item":
                    return self._json(HTTPStatus.OK, wf.hr_item(batch, parts[1], q.get("json_file", "")))
                if route == "staging":
                    return self._json(HTTPStatus.OK, wf.staging(batch, q.get("r1") or None, q.get("r2") or None))
                if route == "panel":
                    return self._json(HTTPStatus.OK, {"versions": wf.panel_versions(), "importable": wf.overview()["importable"]})
                if parts[0] == "panel" and len(parts) == 3 and parts[2] == "data":
                    return self._json(HTTPStatus.OK, wf.panel_data(parts[1], q))
                if parts[0] == "panel" and len(parts) == 3 and parts[2] == "download":
                    return self._file(wf.panel_path(parts[1]), "text/csv; charset=utf-8", download=True)
                if route == "gap":
                    return self._json(HTTPStatus.OK, {"runs": wf.gap_runs()})
                if parts[0] == "gap" and len(parts) == 2:
                    return self._json(HTTPStatus.OK, wf.gap_status(parts[1]))
                if route == "pdf":
                    return self._file(wf.allowed_pdf(q.get("path", "")), "application/pdf")
            else:
                if route == "settings":
                    wf.save_settings(body)
                    return self._json(HTTPStatus.OK, wf.settings_info())
                if route in ("run/round1", "run/round2"):
                    return self._json(HTTPStatus.ACCEPTED, {"job": wf.start_round(parts[1], body)})
                if route == "run/gap_identify":
                    return self._json(HTTPStatus.ACCEPTED, {"job": wf.start_gap_identify(body)})
                if route == "run/gap_fill":
                    return self._json(HTTPStatus.ACCEPTED, {"job": wf.start_gap_fill(body)})
                if route == "job/stop":
                    return self._json(HTTPStatus.OK, {"job": wf.JOBS.stop()})
                if parts[0] == "hr" and len(parts) == 3 and parts[2] == "save":
                    return self._json(HTTPStatus.OK, wf.hr_save(batch, parts[1], body))
                if route == "panel/import":
                    return self._json(HTTPStatus.OK, wf.panel_import(body))
                if route == "panel/append":
                    return self._json(HTTPStatus.OK, wf.panel_append_staging(body))
                if route == "gap/append":
                    return self._json(HTTPStatus.OK, wf.gap_append(body))
            return self._json(HTTPStatus.NOT_FOUND, {"error": f"unknown endpoint {method} /api/wf/{route}"})
        except wf.UserError as e:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": str(e)})
        except (BrokenPipeError, ConnectionResetError):
            return None
        except Exception as e:
            traceback.print_exc()
            return self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"{type(e).__name__}: {e}"})

    def do_GET(self):
        url = urlparse(self.path)
        path = unquote(url.path)
        if path.startswith("/api/wf/"):
            return self._wf("GET", path[len("/api/wf/"):], {k: v[-1] for k, v in parse_qs(url.query).items()}, {})
        if not path.startswith("/api/"):
            return super().do_GET()
        if path == "/api/defaults":
            latest = wf.panel_latest()  # the newest panel database version is the default input
            return self._json(HTTPStatus.OK, {
                "final_csv": latest["file"] if latest else str(Path(ccd.FINAL_CSV).resolve()), "pdf_root": str(Path(ccd.PDF_ROOT).resolve()),
                "batches": list(ccd.BATCHES), "out_dir": str(out_dir().resolve()), "years": list(ccd.YEARS),
                "default_stamp": datetime.now().strftime("%Y%m%d_%H%M")})
        if path == "/api/job":
            with JOB_LOCK:
                return self._json(HTTPStatus.OK, dict(JOB, log=list(JOB["log"])))
        if path == "/api/runs":
            return self._json(HTTPStatus.OK, {"runs": list_runs()})
        m = re.match(r"^/api/runs/([^/]*)/(data|download)$", path)
        if m:
            stamp, what = m.group(1), m.group(2)
            if stamp and not STAMP_RE.match(stamp):
                return self._json(HTTPStatus.BAD_REQUEST, {"error": "bad stamp"})
            wb = workbook_for(stamp)
            if wb is None:
                return self._json(HTTPStatus.NOT_FOUND, {"error": f"no workbook for stamp {stamp!r}"})
            if what == "download":
                data = wb.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                self.send_header("Content-Disposition", f'attachment; filename="{wb.name}"')
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return None
            try:
                return self._json(HTTPStatus.OK, coverage_payload(wb))
            except Exception as e:
                return self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"could not read {wb.name}: {e}"})
        return self._json(HTTPStatus.NOT_FOUND, {"error": "unknown endpoint"})

    def do_POST(self):
        path = unquote(urlparse(self.path).path)
        if path.startswith("/api/wf/"):
            return self._wf("POST", path[len("/api/wf/"):], {}, self._body())
        if path == "/api/inspect":
            return self._json(HTTPStatus.OK, inspect(self._body()))
        if path == "/api/generate":
            status, payload = start_job(self._body())
            return self._json(status, payload)
        return self._json(HTTPStatus.NOT_FOUND, {"error": "unknown endpoint"})


def main(port: int = 8765, open_browser: bool = True):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"DSA coverage app running at {url}  (Ctrl+C to stop)")
    print(f"Workbooks and run records: {out_dir().resolve()}")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="DSA coverage web app")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true", help="do not open the browser")
    a, _ = ap.parse_known_args()
    main(a.port, not a.no_browser)
