"""The web app's version.

One source: the first "## X.Y.Z — YYYY-MM-DD" heading of coverage_app/CHANGELOG.md. The page shows it
(top left, click for the changelog), and every record the app writes (coverage run records, panel
manifests, round run records) stores it as "app_version", so each output says which app built it.
"""
from __future__ import annotations

import re
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent / "CHANGELOG.md"
HEADING_RE = re.compile(r"^##\s+(?P<version>\d+\.\d+\.\d+)\s*(?:[—–-]\s*(?P<date>\d{4}-\d{2}-\d{2}))?", re.M)


def info() -> dict:
    """{version, date, changelog}: the newest version and date, and the changelog's text."""
    try:
        text = CHANGELOG.read_text(encoding="utf-8")
    except OSError:
        return {"version": "0.0.0", "date": None, "changelog": ""}
    m = HEADING_RE.search(text)
    return {"version": m.group("version") if m else "0.0.0", "date": m.group("date") if m else None, "changelog": text}


def app_version() -> str:
    return info()["version"]
