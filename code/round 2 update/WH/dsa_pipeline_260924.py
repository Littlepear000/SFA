"""
IMF DSA debt-decomposition extraction pipeline.

For each IMF staff report PDF:
  Step 1  Extract page text (PyMuPDF) and ask the model for the public-DSA page range.
          A weighted keyword search is used when the call fails and overrides a
          "not found" answer when strong DSA signals exist (high recall).
  Local   Build an uploadable PDF of those pages, escalating only as far as needed:
            1. original pages, dropping outer context pages if too large;
            2. same, with oversized embedded images recompressed (text layer intact);
            3. high-resolution crop of the table on the primary page;
            4. compressed full-page renderings.
          A 413/oversize rejection from the gateway moves to the next stage.
  Step 2  Send the PDF inline (Base64) and extract the decomposition table as JSON.
          A null-heavy or unreadable result is retried once on the primary page
          rendered in three orientations (sideways LIC-DSF annex tables).
  Verify  One independent call re-audits the column header and rereads the selected
          column. Year disagreements, self-contradictory header audits, and value
          mismatches are flagged as manual_review; printed values are never changed.

Outputs per report in OUTPUT_DIR: <stem>_step1_locator.json, <stem>_dsa.json,
<stem>_timing.json (or <stem>_ERROR.json), the PDFs sent to the API in
selected_pdf_pages/, and RUN_SUMMARY.json for the whole run.

Requirements:  pip install pymupdf pillow msal requests python-dotenv
.env entries:  API_KEY, CLIENT_ID, BASE_URL, TENANT_ID, optional MODEL
"""

from __future__ import annotations

import atexit
import base64
import io
import json
import os
import random
import re
import sys
import threading
import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple

import msal
import requests
from dotenv import dotenv_values
from PIL import Image

try:
    import pymupdf
except ImportError:  # PyMuPDF < 1.24
    import fitz as pymupdf


# =============================================================================
# Configuration
# =============================================================================

BASE_DIR = Path(r"Q:\DATA\FP\Staff Working Files\Whan\SFA")
PDF_DIR = BASE_DIR / "staff_reports" / "test_updated_prompt"
OUTPUT_DIR = BASE_DIR / "output" / "json_dsa" / "test_updated_prompt_2016-2020_5"
SELECTED_PDF_DIR = OUTPUT_DIR / "selected_pdf_pages"
PROMPT_FILE = BASE_DIR / "dsa_prompt_20260924.txt"
ENV_FILE = BASE_DIR / ".env"

# Optional targeted run: a JSON file listing reports to (re)process, e.g. a
# mismatch export. Accepts a flat list of stems / "<stem>.pdf" / "<stem>_dsa.json",
# or nested objects with "json_file" or "report" keys (inside "reports" lists).
# REPORT_LIST_CATEGORY restricts processing to one top-level key of that file.
# Targeted runs write to RERUN_OUTPUT_DIR (default: "<OUTPUT_DIR>_rerun").
REPORT_LIST_FILE: Optional[Path] = None
REPORT_LIST_CATEGORY: Optional[str] = None
RERUN_OUTPUT_DIR: Optional[Path] = None

# Skip reports whose <stem>_dsa.json already exists (resume an interrupted run).
SKIP_EXISTING = False

DEFAULT_MODEL = "gpt-5.5"
REASONING_EFFORT = "high"
MAX_WORKERS = 4  # concurrent reports; each report makes its API calls sequentially

# The gateway rejects requests above 1,048,576 bytes and Base64 adds ~33%.
MAX_UPLOAD_BYTES = 650_000     # selected PDF size before encoding
MAX_REQUEST_BYTES = 1_000_000  # complete encoded request
LOCATOR_MAX_CHARS = 300_000

MAX_API_ATTEMPTS = 6
INITIAL_RETRY_DELAY_SECONDS = 3.0
MAX_RETRY_DELAY_SECONDS = 60.0
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# Stage 2: embedded images at least this large are re-encoded as JPEG.
EMBEDDED_IMAGE_JPEG_QUALITY = 60
EMBEDDED_IMAGE_MIN_BYTES = 15_000

# Rendering grids, searched in order (highest fidelity first).
TABLE_CROP_DPI = [240, 220, 200, 180, 160, 140]
TABLE_CROP_JPEG_QUALITY = [92, 88, 84, 80, 76, 72]
FULL_PAGE_DPI = [150, 130, 110, 90, 75]
FULL_PAGE_JPEG_QUALITY = [82, 72, 62, 52, 42]
ROTATION_DPI = [260, 230, 200, 180, 160, 140]
ROTATION_JPEG_QUALITY = [88, 82, 76, 70, 64, 58, 52]
ROTATIONS = (0, 90, 270)

# Table-crop boundaries are found from the text layer of the primary page.
TABLE_CROP_START_PHRASES = [
    "Contribution to Changes in Public Debt",
    "Contribution to Change in Public Debt",
    "Contributions to Changes in Public Debt",
    "Change in gross public sector debt",
    "Change in public sector debt",
    "Change in gross public debt",
    "Change in public debt",
]
TABLE_CROP_END_PHRASES = [
    "Residual, including asset changes",
    "Residual including asset changes",
    "Contribution of residual",
    "Residual",
]
# Status labels above the first decomposition row extend the crop upward so the
# actual / preliminary / projection headings stay visible.
TABLE_CROP_HEADER_PHRASES = [
    "Actual", "Historical", "History", "Outturn", "Final",
    "Prel", "Preliminary", "Provisional",
    "Est", "Estimate", "Estimated",
    "Proj", "Projection", "Projections", "Forecast",
    "Medium-term projection", "Medium term projection", "Extended projection",
]
TABLE_CROP_TOP_MARGIN = 120  # points, used when no header phrase is found
TABLE_CROP_HEADER_MARGIN = 14
TABLE_CROP_BOTTOM_MARGIN = 28
TABLE_CROP_SIDE_MARGIN = 12

# Pages containing these phrases (plus two pages either side, the first 10 and
# last 30 pages) are sent to the Step 1 model.
LOCATOR_CONTEXT_PHRASES = [
    "debt sustainability",
    "public dsa",
    "baseline scenario",
    "contribution to change in public debt",
    "contributions to changes in public debt",
    "change in public debt",
    "identified debt-creating flows",
    "automatic debt dynamics",
    "public sector debt sustainability framework",
    "drivers of debt dynamics",
]

# Weighted phrases for the deterministic Step 1 fallback.
DSA_KEYWORD_WEIGHTS = {
    "public sector debt sustainability framework": 18,
    "public dsa - baseline scenario": 18,
    "sovereign risk and debt sustainability framework": 18,
    "contribution to change in public debt": 16,
    "contribution to changes in public debt": 16,
    "contributions to changes in public debt": 16,
    "contribution of identified flows": 12,
    "identified debt-creating flows": 12,
    "other identified debt-creating flows": 10,
    "automatic debt dynamics": 10,
    "drivers of debt dynamics": 9,
    "change in gross public sector debt": 9,
    "change in public sector debt": 9,
    "change in gross public debt": 9,
    "change in public debt": 8,
    "baseline scenario": 5,
    "public debt": 3,
    "residual": 2,
}
STRONG_TITLE_PHRASES = {
    "public sector debt sustainability framework",
    "public dsa - baseline scenario",
    "sovereign risk and debt sustainability framework",
    "contribution to change in public debt",
    "contribution to changes in public debt",
    "contributions to changes in public debt",
}
DECOMPOSITION_PHRASES = {
    "identified debt-creating flows",
    "contribution of identified flows",
    "automatic debt dynamics",
    "other identified debt-creating flows",
    "residual",
}
KEYWORD_MIN_SCORE = 18

# Country-level pipeline: currency/monetary union reports are skipped.
EXCLUDED_UNIONS = [
    "Euro Area",
    "Central African Economic and Monetary Community",
    "Eastern Caribbean Currency Union",
    "West African Economic and Monetary Union",
]

PROMPT_SECTIONS = ("LOCATOR", "EXTRACTION", "CROP_NOTE", "ORIENTATION_RETRY", "VERIFICATION")

# Stage names double as the "extraction_method" recorded in the output.
DIRECT = "selected_pdf_direct"
IMAGE_COMPRESSED = "selected_pdf_image_compressed"
TABLE_CROP = "pymupdf_pillow_table_crop_fallback"
FULL_PAGE = "pymupdf_pillow_visual_fallback"
ROTATED = "pymupdf_pillow_multi_orientation_retry"
UPLOAD_STAGES = (DIRECT, IMAGE_COMPRESSED, TABLE_CROP, FULL_PAGE)

ELIGIBLE_STATUSES = {"actual", "historical"}
NON_ACTUAL_STATUS_PATTERNS = {
    "preliminary": r"\b(prel\.?|preliminary|provisional)\b",
    "estimate": r"\b(est\.?|estimate|estimated)\b",
    "projection": r"\b(proj\.?|projections?|forecast|medium[- ]term projection|extended projection)\b",
}
MIN_VALUES_FOR_NUMERIC_CHECK = 3

# MuPDF is not thread-safe. All PDF work is serialized; API calls, which dominate
# run time, happen outside this lock.
PDF_LOCK = threading.RLock()


# =============================================================================
# General helpers
# =============================================================================

def elapsed(start: float) -> float:
    return round(time.perf_counter() - start, 2)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def normalize_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def is_excluded_union(pdf_path: Path) -> bool:
    stem = normalize_text(pdf_path.stem)
    return any(stem.startswith(normalize_text(name)) for name in EXCLUDED_UNIONS)


def append_note(result: Dict[str, Any], note: str) -> None:
    result["extraction_notes"] = f"{str(result.get('extraction_notes') or '').strip()} {note}".strip()


def load_prompts(path: Path) -> Dict[str, str]:
    """Split the prompt file on <<<NAME>>> marker lines."""
    parts = re.split(r"^<<<([A-Z_]+)>>>[ \t]*$", path.read_text(encoding="utf-8"), flags=re.M)
    sections = {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}
    missing = [name for name in PROMPT_SECTIONS if not sections.get(name)]
    if missing:
        raise RuntimeError(f"Prompt file {path} is missing section(s): {', '.join(missing)}")
    return sections


def load_target_report_stems(path: Path, category: Optional[str] = None) -> List[str]:
    """Return report stems listed in a JSON file, in order and without duplicates."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if category:
        if not (isinstance(data, dict) and category in data):
            raise RuntimeError(f"Category '{category}' is not a top-level key in {path}.")
        data = data[category]

    stems: List[str] = []

    def to_stem(value: str) -> str:
        for suffix in ("_dsa.json", ".pdf"):
            if value.endswith(suffix):
                return value[: -len(suffix)]
        return value

    def visit(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                stems.append(to_stem(item)) if isinstance(item, str) else visit(item)
        elif isinstance(node, dict):
            for key in ("json_file", "report"):
                if isinstance(node.get(key), str):
                    stems.append(to_stem(node[key]))
                    return
            # Follow only "reports" lists and nested objects so descriptive
            # sibling fields are never mistaken for report names.
            for key, value in node.items():
                if (key == "reports" and isinstance(value, list)) or isinstance(value, dict):
                    visit(value)

    visit(data)
    return list(dict.fromkeys(stems))


# =============================================================================
# API client
# =============================================================================

class RequestTooLarge(RuntimeError):
    """The PDF or request exceeds the gateway limit; try a smaller rendering."""


class ApiClient:
    """Responses API client with Azure AD auth, token refresh, and retry/backoff."""

    def __init__(self, env_file: Path) -> None:
        config = dotenv_values(env_file)
        missing = [k for k in ("API_KEY", "CLIENT_ID", "BASE_URL", "TENANT_ID") if not config.get(k)]
        if missing:
            raise RuntimeError(f"Missing .env entries: {', '.join(missing)}")

        local_appdata = os.getenv("LOCALAPPDATA")
        if not local_appdata:
            raise RuntimeError("LOCALAPPDATA environment variable is not set.")
        cache_file = Path(local_appdata) / ".IdentityService" / "my_custom_cache.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache = msal.SerializableTokenCache()
        if cache_file.exists():
            cache.deserialize(cache_file.read_text(encoding="utf-8"))

        def save_cache() -> None:
            if cache.has_state_changed:
                cache_file.write_text(cache.serialize(), encoding="utf-8")

        atexit.register(save_cache)

        self._app = msal.PublicClientApplication(
            str(config["CLIENT_ID"]),
            authority=f"https://login.microsoftonline.com/{config['TENANT_ID']}",
            token_cache=cache,
        )
        self._api_key = str(config["API_KEY"])
        self._token: Optional[str] = None
        self._lock = threading.Lock()
        self.model = str(config.get("MODEL") or DEFAULT_MODEL)
        self.url = self._responses_url(str(config["BASE_URL"]))
        self._get_token()  # authenticate once up front

    @staticmethod
    def _responses_url(base_url: str) -> str:
        base = base_url.rstrip("/")
        if base.endswith("/v1/responses"):
            return base
        return (base if base.endswith("/v1") else base + "/v1") + "/responses"

    def _get_token(self, force_refresh: bool = False) -> str:
        with self._lock:
            if self._token and not force_refresh:
                return self._token
            scopes = [".default"]
            accounts = self._app.get_accounts()
            result = (
                self._app.acquire_token_silent(scopes, account=accounts[0], force_refresh=force_refresh)
                if accounts else None
            )
            if not result or "access_token" not in result:
                result = self._app.acquire_token_interactive(scopes=scopes)
            if "access_token" not in result:
                raise RuntimeError(f"Authentication failed: {result}")
            self._token = str(result["access_token"])
            return self._token

    def _headers(self, force_refresh: bool) -> Dict[str, str]:
        return {
            "api-key": self._api_key,
            "Authorization": f"Bearer {self._get_token(force_refresh)}",
            "Cache-Control": "no-cache",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _retry_delay(response: requests.Response, attempt: int) -> float:
        """Retry-After header, then a delay stated in the body, then exponential backoff."""
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), MAX_RETRY_DELAY_SECONDS)
            except ValueError:
                pass
        match = re.search(r"try again in\s+(\d+(?:\.\d+)?)\s*seconds?", response.text, re.I)
        if match:
            return min(float(match.group(1)), MAX_RETRY_DELAY_SECONDS)
        backoff = INITIAL_RETRY_DELAY_SECONDS * 2 ** (attempt - 1)
        return min(backoff + random.uniform(0, 1.5), MAX_RETRY_DELAY_SECONDS)

    @staticmethod
    def _error_text(response: requests.Response) -> str:
        body = response.text[:1000]
        request_id = next(
            (response.headers[h] for h in ("x-request-id", "request-id", "apim-request-id") if h in response.headers),
            None,
        )
        return f"{body} Request ID: {request_id}" if request_id and request_id not in body else body

    def _post(self, payload: str, timeout: int) -> requests.Response:
        """401: refresh token. 429/5xx: back off and retry. Other codes: return."""
        refresh = False
        response: Optional[requests.Response] = None
        for attempt in range(1, MAX_API_ATTEMPTS + 1):
            response = requests.post(self.url, headers=self._headers(refresh), data=payload, timeout=timeout)
            refresh = False
            if response.status_code == 200 or attempt == MAX_API_ATTEMPTS:
                return response
            if response.status_code == 401:
                print("  Token rejected (401); refreshing and retrying...")
                refresh = True
            elif response.status_code in RETRYABLE_STATUS_CODES:
                delay = self._retry_delay(response, attempt)
                print(f"  API {response.status_code} on attempt {attempt}/{MAX_API_ATTEMPTS}; retrying in {delay:.1f}s")
                time.sleep(delay)
            else:
                return response
        return response  # type: ignore[return-value]

    @staticmethod
    def _parse_output(data: Dict[str, Any]) -> Dict[str, Any]:
        text = data.get("output_text")
        if not text:
            text = next(
                (c.get("text", "") for item in data.get("output", []) if item.get("type") == "message"
                 for c in item.get("content", []) if c.get("type") == "output_text"),
                None,
            )
        if text is None:
            raise RuntimeError("No output_text in API response.")
        clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(text).strip())
        try:
            obj = json.loads(clean)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", clean, flags=re.S)
            if not match:
                raise
            obj = json.loads(match.group(0))
        if not isinstance(obj, dict):
            raise ValueError("Model output is not a JSON object.")
        return obj

    def call_json(self, prompt: str, user_text: str, pdf_path: Optional[Path] = None) -> Dict[str, Any]:
        """Send a prompt (and optionally a PDF inline as Base64) and parse the JSON reply."""
        text = f"{prompt}\n\nINPUT:\n{user_text}"
        if pdf_path is None:
            model_input: Any = text
        else:
            pdf_bytes = pdf_path.read_bytes()
            if len(pdf_bytes) > MAX_UPLOAD_BYTES:
                raise RequestTooLarge(f"{pdf_path.name} is {len(pdf_bytes):,} bytes (limit {MAX_UPLOAD_BYTES:,}).")
            model_input = [{
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "filename": pdf_path.name,
                        "file_data": "data:application/pdf;base64," + base64.b64encode(pdf_bytes).decode("ascii"),
                    },
                    {"type": "input_text", "text": text},
                ],
            }]

        payload = json.dumps({"model": self.model, "reasoning": {"effort": REASONING_EFFORT}, "input": model_input})
        if len(payload.encode("utf-8")) >= MAX_REQUEST_BYTES:
            raise RequestTooLarge(f"Encoded request is {len(payload):,} bytes, at or above the gateway limit.")

        response = self._post(payload, timeout=600 if pdf_path is None else 900)
        if response.status_code == 413 or re.search(
            r"maximum allowed size|request entity too large", response.text, re.I
        ):
            raise RequestTooLarge(f"Gateway rejected the request size: {self._error_text(response)}")
        if response.status_code != 200:
            raise RuntimeError(f"API error {response.status_code}: {self._error_text(response)}")
        return self._parse_output(response.json())


# =============================================================================
# Step 1: locate the public DSA pages
# =============================================================================

def extract_page_texts(pdf_path: Path) -> List[str]:
    """Return one text block per page, words grouped into visual lines left to right."""
    texts: List[str] = []
    with PDF_LOCK, pymupdf.open(str(pdf_path)) as doc:
        for page in doc:
            lines: Dict[float, List[Tuple[float, str]]] = {}
            for x0, y0, _x1, _y1, word, *_ in page.get_text("words"):
                lines.setdefault(round(y0, 1), []).append((x0, word))
            texts.append("\n".join("  ".join(w for _, w in sorted(lines[y])) for y in sorted(lines)))
    return texts


def build_locator_input(pages: List[str], filename: str) -> str:
    """Keep the opening pages, the last 30 pages, and DSA-related pages with neighbors."""
    n = len(pages)
    keep = set(range(min(10, n))) | set(range(max(0, n - 30), n))
    for i, text in enumerate(pages):
        lower = re.sub(r"\s+", " ", text.lower())
        if any(phrase in lower for phrase in LOCATOR_CONTEXT_PHRASES):
            keep.update(range(max(0, i - 2), min(n, i + 3)))
    body = "".join(f"\n\n--- PAGE {i + 1} ---\n{pages[i]}" for i in sorted(keep))
    return f"PDF file: {filename}\n{body}"[:LOCATOR_MAX_CHARS]


def keyword_locator(pages: List[str], filename: str, note: str) -> Dict[str, Any]:
    """Deterministic locator: score pages with weighted public-DSA phrases."""
    hits = []
    for page_no, text in enumerate(pages, start=1):
        lower = re.sub(r"\s+", " ", text.lower())
        matched = [p for p in DSA_KEYWORD_WEIGHTS if p in lower]
        if not matched:
            continue
        score = sum(DSA_KEYWORD_WEIGHTS[p] for p in matched)
        score += 12 if STRONG_TITLE_PHRASES.intersection(matched) else 0
        score += 10 if len(DECOMPOSITION_PHRASES.intersection(matched)) >= 2 else 0
        if score >= KEYWORD_MIN_SCORE:  # ignore pages that only mention DSA in prose
            image_based = len(re.findall(r"(?<!\d)-?\d+(?:\.\d+)?", text)) < 12
            hits.append((score, page_no, matched, image_based))
    hits.sort(key=lambda h: (-h[0], h[1]))

    candidates = [
        {
            "rank": rank,
            "start_page": max(1, page_no - 2),
            "end_page": min(len(pages), page_no + 2),
            "reason": f"Weighted keyword score {score} on physical page {page_no}.",
            "matched_phrases": matched,
            "likely_image_based": image_based,
        }
        for rank, (score, page_no, matched, image_based) in enumerate(hits[:5], start=1)
    ]
    best = candidates[0] if candidates else {}
    return {
        "report_metadata": {"pdf_file_name": filename},
        "dsa_section_found": bool(candidates),
        "framework_hint": "UNKNOWN",
        "candidates": candidates,
        "primary_table_page": hits[0][1] if hits else None,
        "recommended_start_page": best.get("start_page"),
        "recommended_end_page": best.get("end_page"),
        "confidence": "medium" if candidates else "low",
        "notes": note,
    }


def locate_dsa(api: ApiClient, prompt: str, pages: List[str], filename: str) -> Dict[str, Any]:
    try:
        locator = api.call_json(prompt, build_locator_input(pages, filename))
    except Exception as exc:
        return keyword_locator(pages, filename, f"Locator call failed; keyword fallback used. Error: {exc}")

    has_range = locator.get("recommended_start_page") is not None and locator.get("recommended_end_page") is not None
    if locator.get("dsa_section_found") and has_range:
        return locator

    # High recall: a "not found" (or range-less) answer is overridden when the
    # text layer shows strong DSA signals, e.g. a table lost in text extraction.
    fallback = keyword_locator(
        pages, filename,
        "Model locator returned no usable page range; keyword fallback selected pages for visual inspection. "
        f"Model notes: {locator.get('notes') or ''}",
    )
    if not fallback["dsa_section_found"]:
        return locator
    if isinstance(locator.get("report_metadata"), dict):
        fallback["report_metadata"] = locator["report_metadata"]
    fallback["framework_hint"] = locator.get("framework_hint") or "UNKNOWN"
    return fallback


def resolve_page_range(locator: Dict[str, Any], total_pages: int) -> Tuple[int, int, int]:
    start = max(1, int(locator["recommended_start_page"]))
    end = min(total_pages, max(start, int(locator["recommended_end_page"])))
    try:
        primary = int(locator.get("primary_table_page"))
    except (TypeError, ValueError):
        primary = 0
    if not start <= primary <= end:
        primary = (start + end) // 2
    return start, end, primary


# =============================================================================
# Building the PDF sent to Step 2
# =============================================================================

@dataclass
class Step2Input:
    path: Path
    pages: List[int]  # original physical page of each attached page, in order
    method: str
    removed: List[int] = field(default_factory=list)
    dpi: Optional[int] = None
    jpeg_quality: Optional[int] = None
    crop_box: Optional[List[float]] = None


def save_pdf_atomic(doc: Any, path: Path) -> int:
    """Save via a temporary file so reruns can replace older outputs safely."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.stem}.{uuid.uuid4().hex}.tmp.pdf")
    try:
        doc.save(str(tmp), garbage=4, deflate=True, clean=True)
        for attempt in range(10):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:  # file briefly locked (e.g. by a viewer or sync client)
                if attempt == 9:
                    raise
                time.sleep(0.5)
    finally:
        tmp.unlink(missing_ok=True)
    return path.stat().st_size


def drop_farthest_page(pages: List[int], primary: int) -> int:
    """Remove and return the outer page farthest from the primary page (never the primary)."""
    left, right = pages[0], pages[-1]
    if right != primary and (right - primary >= primary - left or left == primary):
        return pages.pop()
    return pages.pop(0)


def fit_page_range(
    pages: List[int], primary: int, build: Callable[[List[int]], Any]
) -> Tuple[List[int], List[int], Any]:
    """Call build(pages) -> (size, info), dropping outer pages until the size fits."""
    pages, removed = list(pages), []
    while True:
        size, info = build(pages)
        if size <= MAX_UPLOAD_BYTES:
            return pages, removed, info
        if len(pages) == 1:
            raise RuntimeError(f"Page {pages[0]} alone is {size:,} bytes after this stage.")
        removed.append(drop_farthest_page(pages, primary))


def recompress_embedded_images(doc: Any) -> None:
    """Re-encode large RGB/grayscale images as JPEG; text and vectors are untouched.

    CMYK, palette, and undecodable images are skipped, and an image is replaced
    only if the new stream is smaller.
    """
    seen = set()
    for page in doc:
        for info in page.get_images(full=True):
            xref = info[0]
            if xref in seen:
                continue
            seen.add(xref)
            try:
                image = doc.extract_image(xref)
                original = image.get("image") or b""
                if len(original) < EMBEDDED_IMAGE_MIN_BYTES or image.get("colorspace") not in (1, 3):
                    continue
                with Image.open(io.BytesIO(original)) as pil:
                    if pil.mode not in ("RGB", "L"):
                        continue
                    buffer = io.BytesIO()
                    pil.save(buffer, format="JPEG", quality=EMBEDDED_IMAGE_JPEG_QUALITY, optimize=True)
                if buffer.tell() >= len(original):
                    continue
                doc.update_stream(xref, buffer.getvalue())
                doc.xref_set_key(xref, "Filter", "/DCTDecode")
                doc.xref_set_key(xref, "DecodeParms", "null")
            except Exception:
                continue


def write_page_subset(source: Any, pages: List[int], out: Path, compress_images: bool) -> int:
    subset = pymupdf.open()
    try:
        for page_no in pages:
            subset.insert_pdf(source, from_page=page_no - 1, to_page=page_no - 1)
        if compress_images:
            recompress_embedded_images(subset)
        return save_pdf_atomic(subset, out)
    finally:
        subset.close()


def find_table_crop_rect(page: Any) -> Optional[Any]:
    """Locate the decomposition block from the text layer, extended up to its header."""
    starts = [r for p in TABLE_CROP_START_PHRASES for r in page.search_for(p)]
    ends = [r for p in TABLE_CROP_END_PHRASES for r in page.search_for(p)]
    if not starts or not ends:
        return None
    start = min(starts, key=lambda r: r.y0)
    ends = [r for r in ends if r.y1 > start.y0]
    if not ends:
        return None
    end = max(ends, key=lambda r: r.y1)

    headers = [r for p in TABLE_CROP_HEADER_PHRASES for r in page.search_for(p) if r.y1 <= start.y0]
    top = min(r.y0 for r in headers) - TABLE_CROP_HEADER_MARGIN if headers else start.y0 - TABLE_CROP_TOP_MARGIN

    bounds = page.rect
    crop = pymupdf.Rect(
        bounds.x0 + TABLE_CROP_SIDE_MARGIN,
        max(bounds.y0, top),
        bounds.x1 - TABLE_CROP_SIDE_MARGIN,
        min(bounds.y1, end.y1 + TABLE_CROP_BOTTOM_MARGIN),
    )
    if crop.width < bounds.width * 0.60 or crop.height < 80 or crop.height >= bounds.height * 0.96:
        return None
    return crop


def render_jpeg_pdf(
    source: Any,
    views: Sequence[Tuple[int, Any, int]],
    out: Path,
    dpi_options: Sequence[int],
    quality_options: Sequence[int],
) -> Tuple[int, int, int]:
    """Rasterize views (page_no, clip or None, rotation) into an image-only PDF.

    Each view is rendered once per DPI; JPEG qualities are tried in memory and the
    PDF is written only for a combination whose estimated size fits.
    Returns (size, dpi, quality).
    """
    size = 0
    for dpi in dpi_options:
        matrix = pymupdf.Matrix(dpi / 72.0, dpi / 72.0)
        rendered: Dict[Tuple[int, Any], Image.Image] = {}
        frames: List[Tuple[Image.Image, float, float]] = []
        for page_no, clip, rotation in views:
            key = (page_no, tuple(clip) if clip is not None else None)
            if key not in rendered:
                page = source.load_page(page_no - 1)
                pix = page.get_pixmap(matrix=matrix, clip=clip, colorspace=pymupdf.csRGB, alpha=False)
                rendered[key] = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            rect = clip if clip is not None else source.load_page(page_no - 1).rect
            width, height = (rect.height, rect.width) if rotation in (90, 270) else (rect.width, rect.height)
            image = rendered[key] if rotation == 0 else rendered[key].rotate(rotation, expand=True)
            frames.append((image, width, height))

        for quality in quality_options:
            jpegs = []
            for image, _, _ in frames:
                buffer = io.BytesIO()
                image.save(buffer, format="JPEG", quality=quality, optimize=True)
                jpegs.append(buffer.getvalue())
            if sum(map(len, jpegs)) + 4_096 * len(jpegs) > MAX_UPLOAD_BYTES:
                continue
            output = pymupdf.open()
            try:
                for jpeg, (_, width, height) in zip(jpegs, frames):
                    output.new_page(width=width, height=height).insert_image(
                        pymupdf.Rect(0, 0, width, height), stream=jpeg, keep_proportion=False
                    )
                size = save_pdf_atomic(output, out)
            finally:
                output.close()
            if size <= MAX_UPLOAD_BYTES:
                return size, dpi, quality
    return max(size, MAX_UPLOAD_BYTES + 1), dpi_options[-1], quality_options[-1]


def build_step2_input(pdf_path: Path, stage: str, start: int, end: int, primary: int, out_dir: Path) -> Step2Input:
    stem = pdf_path.stem
    page_range = list(range(start, end + 1))
    with PDF_LOCK, pymupdf.open(str(pdf_path)) as source:
        if stage in (DIRECT, IMAGE_COMPRESSED):
            suffix = "" if stage == DIRECT else "_image_compressed"
            out = out_dir / f"{stem}_pages_{start}_{end}{suffix}.pdf"
            pages, removed, _ = fit_page_range(
                page_range, primary,
                lambda p: (write_page_subset(source, p, out, stage == IMAGE_COMPRESSED), None),
            )
            return Step2Input(out, pages, stage, removed)

        if stage == TABLE_CROP:
            crop = find_table_crop_rect(source.load_page(primary - 1))
            if crop is None:
                raise RuntimeError(f"No reliable table boundaries found on page {primary}.")
            out = out_dir / f"{stem}_page_{primary}_table_crop_fallback.pdf"
            size, dpi, quality = render_jpeg_pdf(source, [(primary, crop, 0)], out, TABLE_CROP_DPI, TABLE_CROP_JPEG_QUALITY)
            if size > MAX_UPLOAD_BYTES:
                raise RuntimeError(f"Table crop of page {primary} does not fit at the lowest setting.")
            removed = [p for p in page_range if p != primary]
            box = [round(float(v), 2) for v in (crop.x0, crop.y0, crop.x1, crop.y1)]
            return Step2Input(out, [primary], stage, removed, dpi, quality, box)

        if stage == FULL_PAGE:
            out = out_dir / f"{stem}_pages_{start}_{end}_vision_fallback.pdf"
            pages, removed, (dpi, quality) = fit_page_range(
                page_range, primary,
                lambda p: (lambda r: (r[0], r[1:]))(
                    render_jpeg_pdf(source, [(n, None, 0) for n in p], out, FULL_PAGE_DPI, FULL_PAGE_JPEG_QUALITY)
                ),
            )
            return Step2Input(out, pages, stage, removed, dpi, quality)

        if stage == ROTATED:
            out = out_dir / f"{stem}_page_{primary}_multi_orientation_retry.pdf"
            views = [(primary, None, angle) for angle in ROTATIONS]
            size, dpi, quality = render_jpeg_pdf(source, views, out, ROTATION_DPI, ROTATION_JPEG_QUALITY)
            if size > MAX_UPLOAD_BYTES:
                raise RuntimeError(f"Rotated renderings of page {primary} do not fit at the lowest setting.")
            return Step2Input(out, [primary] * len(ROTATIONS), stage, [], dpi, quality)

    raise ValueError(f"Unknown stage: {stage}")


# =============================================================================
# Step 2: extraction
# =============================================================================

def build_step2_user_text(pdf_name: str, inp: Step2Input, locator: Dict[str, Any], crop_note: str) -> str:
    suffix = " (alternative orientation of the same source page)" if inp.method == ROTATED else ""
    mapping = "\n".join(
        f"Selected PDF page {i} = original physical PDF page {p}{suffix}" for i, p in enumerate(inp.pages, 1)
    )
    text = (
        f"Original PDF file: {pdf_name}\n"
        f"Selected PDF file: {inp.path.name}\n"
        f"Input rendering method: {inp.method}\n"
        f"Rendering DPI: {inp.dpi}\nJPEG quality: {inp.jpeg_quality}\nTable crop box: {inp.crop_box}\n\n"
        f"ORIGINAL PHYSICAL PAGE MAPPING:\n{mapping}\n\n"
        f"STEP 1 LOCATOR OUTPUT:\n{json.dumps(locator, indent=2, ensure_ascii=False)}"
    )
    return f"{text}\n\n{crop_note}" if inp.method == TABLE_CROP else text


def iter_nodes(result: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    """Yield every decomposition node, depth first."""
    stack = list((result.get("decomposition") or {}).values())[::-1]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            yield node
            stack.extend(reversed([c for c in node.get("children") or [] if isinstance(c, dict)]))


def count_values(result: Dict[str, Any]) -> Tuple[int, int]:
    """Return (labeled nodes with a value, labeled nodes)."""
    labeled = [n for n in iter_nodes(result) if n.get("label_verbatim") not in (None, "")]
    return sum(n.get("value") not in (None, "") for n in labeled), len(labeled)


def needs_legibility_retry(result: Dict[str, Any]) -> bool:
    if not result.get("table_found"):
        return result.get("failure_reason") in {"pages_unreadable", "dsa_pages_not_in_input"}
    values, labeled = count_values(result)
    return labeled == 0 or values < 3 or values / labeled < 0.45


# =============================================================================
# Verification of the selected year and column
# =============================================================================

def year_token(value: Any) -> Optional[str]:
    match = re.search(r"\b\d{4}(?:[/-]\d{2,4})?\b", str(value or ""))
    return match.group(0) if match else None


def status_of(value: Any) -> str:
    return str(value or "").strip().lower()


def selected_audit_column(audit: Any) -> Optional[Dict[str, Any]]:
    columns = audit.get("columns") if isinstance(audit, dict) else None
    selected = [c for c in columns or [] if isinstance(c, dict) and c.get("selected") is True]
    return selected[0] if len(selected) == 1 else None


def validate_actual_column(source: Dict[str, Any]) -> List[str]:
    """Consistency checks on the first extraction's year selection."""
    errors: List[str] = []
    year = year_token(source.get("last_actual_year"))
    label_year = year_token(source.get("actual_column_label"))
    if not year:
        errors.append("last_actual_year is missing or has no recognizable year")
    if not label_year:
        errors.append("actual_column_label is missing or has no recognizable year")
    if year and label_year and year != label_year:
        errors.append(f"last_actual_year {year} differs from actual_column_label {label_year}")
    if status_of(source.get("actual_column_status")) not in ELIGIBLE_STATUSES:
        errors.append(f"actual_column_status is not eligible: {source.get('actual_column_status') or 'missing'}")
    header = f"{source.get('actual_column_label') or ''} {source.get('actual_column_header_verbatim') or ''}".lower()
    for status, pattern in NON_ACTUAL_STATUS_PATTERNS.items():
        if re.search(pattern, header):
            errors.append(f"selected header is explicitly {status}: {header.strip()!r}")
            break

    audit = source.get("column_header_audit")
    selected = selected_audit_column(audit)
    if selected is None:
        errors.append("column_header_audit must contain exactly one selected column")
        return errors
    if status_of(selected.get("status")) not in ELIGIBLE_STATUSES:
        errors.append(f"selected audit column has ineligible status: {selected.get('status') or 'missing'}")
    for other in (year_token(selected.get("year_label")), year_token(audit.get("selected_year"))):
        if year and other and other != year:
            errors.append(f"column_header_audit selects {other}, last_actual_year is {year}")

    # The model's own audit contradicts its choice if an eligible column lies
    # further right (e.g. 2017 chosen while 2018 is also tagged actual).
    def position(column: Dict[str, Any]) -> Optional[float]:
        try:
            return float(column.get("position"))
        except (TypeError, ValueError):
            return None

    selected_pos = position(selected)
    if selected_pos is not None:
        later = [
            str(c.get("year_label")) for c in audit.get("columns") or []
            if isinstance(c, dict) and (position(c) or 0) > selected_pos
            and status_of(c.get("status")) in ELIGIBLE_STATUSES
        ]
        if later:
            errors.append(f"column_header_audit lists later eligible column(s) not selected: {', '.join(later)}")
    return errors


def apply_verification(result: Dict[str, Any], errors: List[str], check: Optional[Dict[str, Any]]) -> None:
    """Record year validation and the independent numeric comparison on result['source']."""
    source = result["source"]
    first_year = year_token(source.get("last_actual_year"))
    values, _ = count_values(result)

    audit = (check or {}).get("column_header_audit")
    audited = selected_audit_column(audit)
    audited_year = year_token(audited.get("year_label")) if audited else None
    audited_status = status_of(audited.get("status")) if audited else ""
    if check is not None:
        source["independent_column_header_audit"] = audit
        source["independent_latest_observation_year"] = check.get("latest_observation_year")
        source["independent_latest_observation_status"] = check.get("latest_observation_status")

    # Year selection.
    issues = list(errors)
    year_confirmed = bool(first_year and audited_year == first_year and audited_status in ELIGIBLE_STATUSES)
    if check is None:
        status = "manual_review" if errors else "accepted"
        if errors:
            issues.append("Independent verification could not be completed.")
    elif year_confirmed:
        status = "accepted_with_warning" if errors else "accepted"
        if errors:
            issues.append("Independent header audit confirmed the same selected year.")
    else:
        status = "manual_review"
        if first_year and audited_year:
            issues.append(f"Independent audit selected {audited_year}; first extraction selected {first_year}.")
        elif not audited_year:
            issues.append("Independent audit could not identify one eligible actual or historical year.")
        else:
            issues.append("First extraction did not provide a usable selected year.")
        source["confidence"] = "low"
        append_note(result, "Actual-year selection requires manual review. " + " ".join(issues))
    source["actual_column_validation"] = {
        "status": status,
        "issues": issues,
        "first_selected_year": first_year,
        "audited_selected_year": audited_year if check is not None else None,
    }

    # Selected-column values.
    if values < MIN_VALUES_FOR_NUMERIC_CHECK:
        source["numeric_verification"] = {
            "status": "manual_review",
            "issues": ["Fewer than three readable decomposition values were available for comparison."],
        }
        return
    if check is None:
        source["numeric_verification"] = {"status": "not_completed", "issues": ["Verification call failed."]}
        append_note(result, "Independent numeric verification could not be completed.")
        return

    first_values = {normalize_text(n.get("label_verbatim")): n.get("value") for n in iter_nodes(result) if n.get("label_verbatim")}
    compared, disagreements = 0, []
    for row in check.get("rows") or []:
        key = normalize_text(row.get("label_verbatim")) if isinstance(row, dict) else ""
        if key in first_values:
            compared += 1
            if first_values[key] != row.get("value"):
                disagreements.append(f"{row['label_verbatim']}: first={first_values[key]!r}, verification={row.get('value')!r}")

    passed = year_confirmed and not disagreements and compared >= MIN_VALUES_FOR_NUMERIC_CHECK
    source["numeric_verification"] = {
        "status": "passed" if passed else "manual_review",
        "first_selected_year": first_year,
        "verified_selected_year": audited_year,
        "verified_selected_year_status": audited_status or None,
        "rows_compared": compared,
        "disagreements": disagreements,
        "issues": check.get("issues") or [],
        "confidence": check.get("confidence"),
    }
    if not passed:
        validation = source["actual_column_validation"]
        validation["status"] = "manual_review"
        if disagreements:
            validation["issues"].append("Independent numeric reread disagreed with one or more selected-column values.")
        if compared < MIN_VALUES_FOR_NUMERIC_CHECK:
            validation["issues"].append("Independent numeric reread could compare fewer than three rows.")
        append_note(result, "Independent numeric verification requires manual review.")


def verify_result(api: ApiClient, prompt: str, result: Dict[str, Any], user_text: str, pdf_path: Path) -> None:
    """Run at most one independent call covering both the header and the column values."""
    source = result.get("source")
    if not result.get("table_found") or not isinstance(source, dict):
        return
    errors = validate_actual_column(source)
    values, _ = count_values(result)
    check: Optional[Dict[str, Any]] = None
    if errors or values >= MIN_VALUES_FOR_NUMERIC_CHECK:
        print("  Independent verification of header and selected column...")
        try:
            check = api.call_json(prompt, user_text, pdf_path)
        except Exception as exc:
            print(f"  Verification failed: {exc}")
    elif not errors:
        # Nothing to compare and nothing to audit: accept the consistent selection.
        pass
    apply_verification(result, errors, check)


# =============================================================================
# Per-report orchestration
# =============================================================================

def attach_metadata(result: Dict[str, Any], locator: Dict[str, Any], filename: str) -> None:
    metadata = locator.get("report_metadata") or {}
    result.setdefault("report_metadata", metadata)
    result.setdefault("pdf_file_name", filename)
    source = result.get("source")
    if isinstance(source, dict):
        for key in ("country", "publication_date", "consultation_type"):
            source[key] = source.get(key) or metadata.get(key)


def process_pdf(pdf_path: Path, api: ApiClient, prompts: Dict[str, str], out_dir: Path) -> Path:
    started = time.perf_counter()
    stem = pdf_path.stem
    pdf_dir = out_dir / "selected_pdf_pages"
    out_path = out_dir / f"{stem}_dsa.json"

    print(f"  Step 1: locating DSA pages in {pdf_path.name}")
    pages = extract_page_texts(pdf_path)
    locator = locate_dsa(api, prompts["LOCATOR"], pages, pdf_path.name)
    write_json(out_dir / f"{stem}_step1_locator.json", locator)

    if not locator.get("dsa_section_found"):
        result = {
            "table_found": False,
            "failure_reason": "dsa_pages_not_in_input",
            "source": None,
            "decomposition": None,
            "unmapped_rows": [],
            "extraction_notes": f"Step 1 found no public DSA. {locator.get('notes') or ''}".strip(),
            "extraction_method": "step1_no_dsa_found",
        }
        attach_metadata(result, locator, pdf_path.name)
        write_json(out_path, result)
        return out_path

    start, end, primary = resolve_page_range(locator, len(pages))

    # Step 2: escalate through the upload stages until one is built and accepted.
    stage_failures: Dict[str, str] = {}
    result: Optional[Dict[str, Any]] = None
    inp: Optional[Step2Input] = None
    user_text = ""
    for stage in UPLOAD_STAGES:
        try:
            inp = build_step2_input(pdf_path, stage, start, end, primary, pdf_dir)
        except Exception as exc:
            stage_failures[stage] = str(exc)
            continue
        user_text = build_step2_user_text(pdf_path.name, inp, locator, prompts["CROP_NOTE"])
        print(f"  Step 2 ({stage}): {inp.path.name}, pages {inp.pages}, {inp.path.stat().st_size:,} bytes")
        try:
            result = api.call_json(prompts["EXTRACTION"], user_text, inp.path)
            break
        except RequestTooLarge as exc:
            stage_failures[stage] = str(exc)
    if result is None or inp is None:
        raise RuntimeError(f"No upload stage succeeded: {stage_failures}")

    # Retry a null-heavy or unreadable result on the primary page in three orientations.
    if needs_legibility_retry(result):
        print("  Result is null-heavy or unreadable; retrying with rotated renderings...")
        try:
            retry_inp = build_step2_input(pdf_path, ROTATED, start, end, primary, pdf_dir)
            retry_text = build_step2_user_text(pdf_path.name, retry_inp, locator, prompts["CROP_NOTE"])
            retry = api.call_json(
                f"{prompts['EXTRACTION']}\n\n{prompts['ORIENTATION_RETRY']}", retry_text, retry_inp.path
            )
            if retry.get("table_found") and (not result.get("table_found") or count_values(retry)[0] > count_values(result)[0]):
                result, user_text = retry, retry_text
                retry_inp.removed = [p for p in range(start, end + 1) if p != primary]
                inp = retry_inp
                append_note(result, f"Extracted from a multi-orientation rendering of page {primary} after a null-heavy first read.")
        except Exception as exc:
            stage_failures[ROTATED] = str(exc)

    verify_result(api, prompts["VERIFICATION"], result, user_text, inp.path)

    attach_metadata(result, locator, pdf_path.name)
    result["extraction_method"] = inp.method
    result["selected_original_pages"] = sorted(set(inp.pages))
    if inp.dpi is not None:
        result["vision_fallback_dpi"] = inp.dpi
        result["vision_fallback_jpeg_quality"] = inp.jpeg_quality
    if inp.crop_box is not None:
        result["table_crop_box_points"] = inp.crop_box
    if inp.removed:
        append_note(result, f"Original page(s) {sorted(inp.removed)} were not sent to Step 2 to meet the upload limit.")
    if inp.method in (TABLE_CROP, FULL_PAGE):
        append_note(
            result,
            "The selected pages exceeded the upload limit, so Step 2 used an image-based "
            + ("crop of the DSA table." if inp.method == TABLE_CROP else "rendering of the selected pages."),
        )
    for stage, reason in stage_failures.items():
        append_note(result, f"Stage {stage} was not used: {reason}")
    write_json(out_path, result)

    write_json(
        out_dir / f"{stem}_timing.json",
        {
            "pdf_file": pdf_path.name,
            "extraction_method": inp.method,
            "selected_original_pages": result["selected_original_pages"],
            "selected_pdf_size_bytes": inp.path.stat().st_size,
            "removed_for_size": sorted(inp.removed),
            "vision_fallback_dpi": inp.dpi,
            "vision_fallback_jpeg_quality": inp.jpeg_quality,
            "table_crop_box_points": inp.crop_box,
            "stage_failures": stage_failures,
            "pdf_sent_to_api": str(inp.path),
            "total_pdf_seconds": elapsed(started),
        },
    )
    return out_path


# =============================================================================
# Batch runner
# =============================================================================

def select_reports() -> Tuple[List[Path], List[Path], Path]:
    """Return (reports to process, excluded union reports, output directory)."""
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    if not pdfs:
        raise RuntimeError(f"No PDFs found in {PDF_DIR}")
    out_dir = OUTPUT_DIR

    if REPORT_LIST_FILE:
        targets = set(load_target_report_stems(REPORT_LIST_FILE, REPORT_LIST_CATEGORY))
        pdfs = [p for p in pdfs if p.stem in targets]
        missing = sorted(targets - {p.stem for p in pdfs})
        print(f"Report list {REPORT_LIST_FILE.name} ({REPORT_LIST_CATEGORY or 'all categories'}): "
              f"{len(targets)} listed, {len(pdfs)} found in {PDF_DIR}")
        for stem in missing:
            print(f"  Missing: {stem}.pdf")
        if not pdfs:
            raise RuntimeError("None of the listed reports were found in PDF_DIR.")
        out_dir = RERUN_OUTPUT_DIR or OUTPUT_DIR.with_name(OUTPUT_DIR.name + "_rerun")

    unions = [p for p in pdfs if is_excluded_union(p)]
    pdfs = [p for p in pdfs if not is_excluded_union(p)]
    if SKIP_EXISTING:
        done = [p for p in pdfs if (out_dir / f"{p.stem}_dsa.json").exists()]
        pdfs = [p for p in pdfs if p not in done]
        print(f"Skipping {len(done)} report(s) with existing output.")
    return pdfs, unions, out_dir


def main() -> None:
    run_start = time.perf_counter()
    pdfs, unions, out_dir = select_reports()
    out_dir.mkdir(parents=True, exist_ok=True)
    prompts = load_prompts(PROMPT_FILE)
    api = ApiClient(ENV_FILE)

    print(f"Excluded {len(unions)} currency/monetary union report(s).")
    print(f"Processing {len(pdfs)} report(s) with {api.model}, {MAX_WORKERS} worker(s). Output: {out_dir}")

    def run_one(index: int, pdf: Path) -> Dict[str, Any]:
        print(f"\n[{index}/{len(pdfs)}] {pdf.name}")
        started = time.perf_counter()
        try:
            data = json.loads(process_pdf(pdf, api, prompts, out_dir).read_text(encoding="utf-8"))
            return {
                "pdf_file": pdf.name,
                "status": "ok",
                "seconds": elapsed(started),
                "extraction_method": data.get("extraction_method"),
                "table_found": bool(data.get("table_found")),
                "failure_reason": data.get("failure_reason"),
                "validation_status": ((data.get("source") or {}).get("actual_column_validation") or {}).get("status"),
            }
        except Exception as exc:
            write_json(out_dir / f"{pdf.stem}_ERROR.json", {"error": str(exc), "seconds": elapsed(started)})
            print(f"[{index}/{len(pdfs)}] Error for {pdf.name}: {exc}")
            return {"pdf_file": pdf.name, "status": "error", "seconds": elapsed(started), "error": str(exc)}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(run_one, i, pdf) for i, pdf in enumerate(pdfs, start=1)]
        results = sorted((f.result() for f in as_completed(futures)), key=lambda r: r["pdf_file"].lower())

    ok = [r for r in results if r["status"] == "ok"]
    methods = Counter(r["extraction_method"] for r in ok)
    total = elapsed(run_start)
    summary = {
        "reports_found_total": len(pdfs) + len(unions),
        "reports_excluded_unions": len(unions),
        "excluded_union_files": [p.name for p in unions],
        "reports_processed": len(pdfs),
        "tables_extracted": sum(r["table_found"] for r in ok),
        "no_dsa_table_found": sum(not r["table_found"] for r in ok),
        "api_or_processing_failures": len(results) - len(ok),
        "no_table_breakdown": dict(Counter(r["failure_reason"] or "other" for r in ok if not r["table_found"])),
        "manual_review": sum(r.get("validation_status") == "manual_review" for r in ok),
        "extraction_method_counts": dict(methods),
        "total_runtime_seconds": total,
        "average_runtime_seconds": round(total / max(len(pdfs), 1), 2),
        "model": api.model,
        "reasoning_effort": REASONING_EFFORT,
        "safe_upload_limit_bytes": MAX_UPLOAD_BYTES,
        "max_workers": MAX_WORKERS,
        "pdfs": results,
    }
    write_json(out_dir / "RUN_SUMMARY.json", summary)
    print("\n========== RUN SUMMARY ==========")
    print(json.dumps({k: v for k, v in summary.items() if k != "pdfs"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Fatal error: {exc}")
        sys.exit(1)