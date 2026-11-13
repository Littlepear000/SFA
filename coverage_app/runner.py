"""
Runs one workflow job (a list of pipeline scripts) in its own process, for the web app.

    python coverage_app/runner.py <job folder>/spec.json

The web app writes spec.json and starts this file with subprocess; everything printed goes to the job's
log file (the app shows it). Each step runs one script with runpy, exactly like the 0_run_*.py controllers
do: the step's settings are passed as init_globals, so the CONFIG block at the top of each script must stay
commented out (it already is). sys.argv is set per step, for the options 4c reads (--dry-run ...).

status.json (next to spec.json) is rewritten while the job runs:
    {"state": running|done|error, "step": i, "n_steps": n, "label": ..., "done": k, "total": m, ...}
done / total is the progress inside the current step: for an extraction step, the number of reports
finished so far (counted from the files the script writes); for 4c, from its "[done/total]" log lines.

Values in a step's "globals" may be written as {"$path": "..."} (a pathlib.Path), a list of those, or
{"$glob": {"dir": ..., "pattern": ..., "run_sort": true}} (the sorted list of matching files, resolved when
the step starts -- used for the run CSVs that 1c compares, which only exist once the runs are done).
"""
from __future__ import annotations

import json
import re
import runpy
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Status:
    def __init__(self, path: Path, n_steps: int):
        self.path, self.lock = path, threading.Lock()
        self.data = {"state": "running", "step": 0, "n_steps": n_steps, "label": "", "done": None,
                     "total": None, "started": now(), "finished": None, "error": None, "step_started": None}
        self.write()

    def update(self, **kw):
        with self.lock:
            self.data.update(kw)
            self.write()

    def write(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)


def decode(v):
    if isinstance(v, dict) and "$path" in v:
        return Path(v["$path"])
    if isinstance(v, dict) and "$glob" in v:
        g = v["$glob"]
        files = list(Path(g["dir"]).glob(g["pattern"]))
        if g.get("run_sort"):
            def run_no(p):
                m = re.search(r"_run(\d+)\.csv$", p.name)
                return int(m.group(1)) if m else 0
            files.sort(key=run_no)
        else:
            files.sort()
        return files
    if isinstance(v, list):
        return [decode(x) for x in v]
    return v


class Tee:
    """stdout wrapper: passes everything on, and reads "[done/total]" progress lines and failure lines."""

    def __init__(self, stream, status: Status):
        self.stream, self.status, self.buf = stream, status, ""
        self.parse_progress, self.fail_pattern, self.failed_line = False, None, None

    def write(self, s):
        self.stream.write(s)
        self.buf += s
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            if self.parse_progress:
                m = re.search(r"\[(\d+)/(\d+)\]", line)
                if m:
                    self.status.update(done=int(m.group(1)), total=int(m.group(2)))
            if self.fail_pattern and self.failed_line is None and re.search(self.fail_pattern, line):
                self.failed_line = line.strip()
        return len(s)

    def flush(self):
        self.stream.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)


def watch_files(status: Status, folder: Path, patterns: list, total: int, stop: threading.Event):
    while not stop.wait(2.0):
        if folder.is_dir():
            n = sum(len(list(folder.glob(p))) for p in patterns)
            status.update(done=min(n, total), total=total)


def main(spec_path: Path) -> int:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    status = Status(spec_path.with_name("status.json"), len(spec["steps"]))
    code_dir = spec.get("code_dir")
    if code_dir and code_dir not in sys.path:
        sys.path.insert(0, code_dir)
    tee = Tee(sys.stdout, status)
    sys.stdout = tee
    print(f"Job {spec.get('id')}: {spec.get('title')}  (started {now()})", flush=True)
    for path in spec.get("must_not_exist", []):
        if Path(path).exists():
            msg = f"Nothing was started: {path} already exists."
            print(msg, flush=True)
            status.update(state="error", error=msg, finished=now())
            return 1
    for i, step in enumerate(spec["steps"], start=1):
        label = step.get("label") or Path(step["script"]).name
        print(f"\n{'=' * 78}\n[step {i}/{len(spec['steps'])}] {label}\n  {step['script']}\n{'=' * 78}", flush=True)
        status.update(step=i, label=label, done=None, total=None, step_started=now())
        stop = threading.Event()
        watch = step.get("watch") or {}
        if watch.get("kind") == "files":
            threading.Thread(target=watch_files, daemon=True,
                             args=(status, Path(watch["dir"]), watch["patterns"], int(watch["total"]), stop)).start()
        tee.parse_progress = watch.get("kind") == "log"
        tee.fail_pattern, tee.failed_line = step.get("fail_pattern"), None
        init = {k: decode(v) for k, v in (step.get("globals") or {}).items()}
        sys.argv = [step["script"], *step.get("argv", [])]
        started = time.perf_counter()
        try:
            runpy.run_path(step["script"], init_globals=init, run_name="__main__")
            if tee.failed_line:
                raise RuntimeError(tee.failed_line)
        except SystemExit as e:  # the scripts use SystemExit("message") to stop with a reason
            if e.code not in (None, 0):
                msg = str(e.code)
                print(f"\nStopped: {msg}", flush=True)
                status.update(state="error", error=f"{label}: {msg}", finished=now())
                stop.set()
                return 1
        except BaseException as e:
            traceback.print_exc()
            sys.stdout.flush()
            status.update(state="error", error=f"{label}: {type(e).__name__}: {e}", finished=now())
            stop.set()
            return 1
        finally:
            stop.set()
        print(f"\n[step {i} finished in {time.perf_counter() - started:.0f} s]", flush=True)
    status.update(state="done", finished=now(), done=None, total=None)
    print(f"\nAll steps finished ({now()}).", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
