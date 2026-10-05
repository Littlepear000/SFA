"""
Two-step DSA extraction pipeline -- FOR MAC / CLAUDE API testing.

This is a copy of the IMF-machine version, with only the API layer replaced: it calls
Anthropic's Claude API (your own key, in .env as ANTHROPIC_API_KEY) directly over HTTPS,
instead of IMF's internal Azure-AD-authenticated gateway. Everything else -- PDF page
location, page selection, crop/visual fallback rendering, actual-column validation, the
two SUBPROMPTs, process_pdf()'s control flow, main()'s CLI and concurrency -- is unchanged
from the IMF version, so this file is only for testing the pipeline's logic with your own
PDFs and Claude account; it is not meant to reproduce the IMF version's production output.

Step 1: use pdfplumber text to locate the PUBLIC DSA pages.
Local step: copy only those physical PDF pages into a smaller PDF with pypdf.
Step 2: send the smaller PDF inline as Base64 (as a Claude "document" content block) and
extract the table directly from it.
Up to four reports are processed concurrently.

The script retries temporary 429 and 5xx API errors with backoff (no Azure AD token to
refresh here -- the Anthropic API key does not expire).
If selected PDF pages are too large, PyMuPDF and Pillow first create a high-resolution, header-aware table crop; if crop detection fails, the script creates a compressed full-page visual fallback.
Existing fallback PDFs are safely replaced on reruns using atomic temporary-file saves.\nReports for selected currency and monetary unions are skipped.

Required packages:
    pip install pdfplumber pypdf python-dotenv anthropic pymupdf pillow
"""

from __future__ import annotations

import base64
import io
import json
import os
import random
import re
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import anthropic
import pdfplumber
from PIL import Image

try:
    import pymupdf
except ImportError:
    # Compatibility with older PyMuPDF versions.
    import fitz as pymupdf

from dotenv import dotenv_values
from pypdf import PdfReader, PdfWriter

# CONFIG -- edit by hand for a standalone run (not needed when run via a controller with
# runpy init_globals, same convention as the IMF version).
BASE_DIR = Path("/Users/littlepear000/Desktop/IMF projects/SFA")
PDF_DIR = BASE_DIR / "staff_reports_mac_test"  # put your own test PDFs here; not synced from the IMF machine
OUTPUT_DIR = BASE_DIR / "output" / "mac_test" / "json_dsa"
SELECTED_PDF_DIR = OUTPUT_DIR / "selected_pdf_pages"
PROMPT_FILE = BASE_DIR / "two_step_selected_pdf_prompt_table_only_cropfallback_v5_flexible_actual.txt"
ENV_FILE = BASE_DIR / ".env"  # add ANTHROPIC_API_KEY=... to it (the same .env the IMF-machine scripts use)

MODEL = "claude-sonnet-5"  # change here to try a different Claude model
EXTENDED_THINKING_BUDGET_TOKENS = 10_000  # Claude's nearest equivalent to the IMF version's reasoning.effort="high"; 0 disables it

# Claude's PDF document support allows requests up to 32 MB; this stays far below that,
# so unlike the IMF version's 1 MB gateway limit it should rarely trigger the crop/visual fallback.
MAX_UPLOAD_BYTES = 25_000_000

# If the selected PDF cannot be reduced below the safe upload limit,
# render the selected pages with PyMuPDF, compress them with Pillow, and
# rebuild a smaller image-based PDF while preserving the visible layout.
VISION_DPI_OPTIONS = [150, 130, 110, 90, 75]
VISION_JPEG_QUALITY_OPTIONS = [82, 72, 62, 52, 42]

# Preferred fallback for oversized pages: crop the DSA table and render only
# that region at higher resolution, excluding charts and unrelated content.
TABLE_CROP_DPI_OPTIONS = [240, 220, 200, 180, 160, 140]
TABLE_CROP_JPEG_QUALITY_OPTIONS = [92, 88, 84, 80, 76, 72]

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

# Header/status phrases used to extend the crop upward so that the model can
# distinguish actual/historical columns from preliminary, estimate, and
# projection columns. Searches are restricted to text above the first
# decomposition row.
TABLE_CROP_HEADER_PHRASES = [
    "Actual", "Historical", "History", "Outturn", "Final",
    "Prel.", "Prel", "Preliminary", "Provisional",
    "Est.", "Est", "Estimate", "Estimated",
    "Proj.", "Proj", "Projection", "Projections", "Forecast",
    "Medium-term projection", "Medium term projection",
    "Extended projection",
]

# Used only when no reliable status/header phrase is found in the text layer.
# 120 points is about 1.67 inches, large enough for most multi-level headers.
TABLE_CROP_TOP_MARGIN_POINTS = 120
TABLE_CROP_HEADER_MARGIN_POINTS = 14
TABLE_CROP_BOTTOM_MARGIN_POINTS = 28
TABLE_CROP_SIDE_MARGIN_POINTS = 12

# Process at most four reports concurrently. Each report still runs Step 1
# followed by Step 2 sequentially, so there are never more than four active
# API requests at a time.
MAX_WORKERS = 4

# Retry configuration for temporary API failures.
MAX_API_ATTEMPTS = 6
INITIAL_RETRY_DELAY_SECONDS = 3.0
MAX_RETRY_DELAY_SECONDS = 60.0
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

DSA_KEYWORDS = [
    "debt sustainability",
    "sovereign risk and debt sustainability",
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


# Reports for these currency/monetary unions are excluded because the pipeline
# is intended for country-level public DSA tables.
EXCLUDED_UNIONS = [
    "Euro Area",
    "Central African Economic and Monetary Community",
    "Eastern Caribbean Currency Union",
    "West African Economic and Monetary Union",
]


def normalize_name(value: str) -> str:
    """Normalize a filename or country name for robust comparisons."""
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def is_excluded_union(pdf_path: Path) -> bool:
    """Return True when the PDF filename refers to an excluded union."""
    normalized_stem = normalize_name(pdf_path.stem)
    return any(
        normalized_stem.startswith(normalize_name(union_name))
        for union_name in EXCLUDED_UNIONS
    )


def elapsed(start: float) -> float:
    return round(time.perf_counter() - start, 2)


def write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def save_pymupdf_pdf_atomic(document: Any, output_path: Path) -> None:
    """
    Save a PyMuPDF document safely, replacing an older file when rerunning.

    PyMuPDF refuses to save directly over an existing file. To make reruns
    reliable and avoid leaving a partially written PDF, save first to a unique
    temporary file in the same directory and then atomically replace the target.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(
        f".{output_path.stem}.{uuid.uuid4().hex}.tmp{output_path.suffix}"
    )

    try:
        document.save(
            str(temporary_path),
            garbage=4,
            deflate=True,
            clean=True,
        )
        for attempt in range(10):
            try:
                os.replace(temporary_path, output_path)
                break
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(0.5)
    finally:
        # Clean up if saving or replacement failed.
        try:
            if temporary_path.exists():
                temporary_path.unlink()
        except OSError:
            pass


def load_two_subprompts(path: Path) -> Tuple[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    text = path.read_text(encoding="utf-8")
    m1 = re.search(r"(?ms)^\s*SUBPROMPT\s+1\b.*?(?=^\s*SUBPROMPT\s+2\b)", text)
    m2 = re.search(r"(?ms)^\s*SUBPROMPT\s+2\b.*$", text)
    if not m1 or not m2:
        raise RuntimeError("Prompt file must contain SUBPROMPT 1 and SUBPROMPT 2.")
    return m1.group(0).strip(), m2.group(0).strip()


def make_api_session() -> Tuple[Optional[str], anthropic.Anthropic, str]:
    """
    Returns (url, client, model) -- the same 3-tuple shape as the IMF version's
    make_api_session(), so process_pdf() and main() need no other changes. url is always
    None here; it is kept only so call sites that still pass a "url" positional argument
    (e.g. 3c_gapfill_3_run_api.py, if it is ever ported to Mac too) keep working unchanged.
    """
    config = dotenv_values(ENV_FILE)
    api_key = config.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(f"Missing ANTHROPIC_API_KEY in {ENV_FILE} (or in the environment).")
    client = anthropic.Anthropic(api_key=str(api_key))
    return None, client, MODEL


def retry_delay_seconds(exc: Exception, attempt: int) -> float:
    """
    Determine how long to wait before retrying.

    Priority:
      1. Retry-After response header, when the SDK exposes one on the exception.
      2. Exponential backoff with small random jitter.
    """
    response = getattr(exc, "response", None)
    retry_after = response.headers.get("Retry-After") if response is not None else None
    if retry_after:
        try:
            return min(float(retry_after), MAX_RETRY_DELAY_SECONDS)
        except ValueError:
            pass

    base_delay = min(
        INITIAL_RETRY_DELAY_SECONDS * (2 ** max(0, attempt - 1)),
        MAX_RETRY_DELAY_SECONDS,
    )
    return min(base_delay + random.uniform(0.0, 1.5), MAX_RETRY_DELAY_SECONDS)


def call_with_retry(client: anthropic.Anthropic, **kwargs: Any) -> "anthropic.types.Message":
    """
    client.messages.create() with the same retry behavior as the IMF version's
    post_with_token_refresh: retry 429/5xx with backoff, up to MAX_API_ATTEMPTS. There is no
    token to refresh here -- the Anthropic API key does not expire, so unlike the IMF
    version there is no 401 case.
    """
    for attempt in range(1, MAX_API_ATTEMPTS + 1):
        try:
            return client.messages.create(**kwargs)
        except anthropic.APIStatusError as exc:
            if exc.status_code not in RETRYABLE_STATUS_CODES or attempt == MAX_API_ATTEMPTS:
                raise
            delay = retry_delay_seconds(exc, attempt)
            error_type = "rate limit" if exc.status_code == 429 else "temporary API error"
            print(f"  API {error_type} ({exc.status_code}) on attempt {attempt}/{MAX_API_ATTEMPTS}. Retrying in {delay:.1f} seconds...")
            time.sleep(delay)
        except (anthropic.APIConnectionError, anthropic.APITimeoutError) as exc:
            if attempt == MAX_API_ATTEMPTS:
                raise
            delay = retry_delay_seconds(exc, attempt)
            print(f"  API connection error on attempt {attempt}/{MAX_API_ATTEMPTS}. Retrying in {delay:.1f} seconds...")
            time.sleep(delay)
    raise RuntimeError("unreachable")  # defensive; the loop above always returns or raises


def extract_output_text(message: "anthropic.types.Message") -> str:
    for block in message.content:
        if getattr(block, "type", None) == "text":
            return block.text
    raise RuntimeError("No text block in API response (only thinking/tool-use blocks?).")


def parse_json_object(text: str) -> Dict[str, Any]:
    clean = text.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1]
        clean = clean.rsplit("```", 1)[0].strip()
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


def _thinking_kwargs(max_tokens: int) -> Dict[str, Any]:
    """Claude's nearest equivalent to the IMF version's reasoning.effort="high"."""
    if not EXTENDED_THINKING_BUDGET_TOKENS:
        return {"max_tokens": max_tokens}
    return {
        "max_tokens": max(max_tokens, EXTENDED_THINKING_BUDGET_TOKENS + 4000),
        "thinking": {"type": "enabled", "budget_tokens": EXTENDED_THINKING_BUDGET_TOKENS},
    }


def call_text_json(
    url: Optional[str],
    token_manager: anthropic.Anthropic,
    model: str,
    prompt: str,
    user_input: str,
) -> Dict[str, Any]:
    message = call_with_retry(
        token_manager,
        model=model,
        system=prompt,
        messages=[{"role": "user", "content": f"INPUT:\n{user_input}"}],
        **_thinking_kwargs(8_000),
    )
    return parse_json_object(extract_output_text(message))


def call_pdf_json(
    url: Optional[str],
    token_manager: anthropic.Anthropic,
    model: str,
    prompt: str,
    user_text: str,
    pdf_path: Path,
) -> Dict[str, Any]:
    """Send the selected-page PDF directly inside the Messages API request as a Base64-encoded "document" content block."""
    pdf_size = pdf_path.stat().st_size

    if pdf_size > MAX_UPLOAD_BYTES:
        raise RuntimeError(
            f"Selected PDF is {pdf_size:,} bytes, above the configured "
            f"Base64-safe limit of {MAX_UPLOAD_BYTES:,} bytes."
        )

    pdf_base64 = base64.b64encode(pdf_path.read_bytes()).decode("ascii")
    print(f"  Selected PDF size: {pdf_size:,} bytes")

    message = call_with_retry(
        token_manager,
        model=model,
        system=prompt,
        messages=[{
            "role": "user",
            "content": [
                {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_base64}},
                {"type": "text", "text": f"INPUT:\n{user_text}"},
            ],
        }],
        **_thinking_kwargs(8_000),
    )
    return parse_json_object(extract_output_text(message))


def extract_page_text(page: pdfplumber.page.Page) -> str:
    words = page.extract_words(
        x_tolerance=2, y_tolerance=3, keep_blank_chars=False, use_text_flow=False
    )
    if not words:
        return ""
    rows: Dict[float, List[Dict[str, Any]]] = {}
    for word in words:
        rows.setdefault(round(word["top"], 1), []).append(word)
    lines = []
    for y in sorted(rows):
        lines.append("  ".join(w["text"] for w in sorted(rows[y], key=lambda x: x["x0"])))
    return "\n".join(lines)


def extract_full_text(pdf_path: Path) -> Tuple[str, List[str]]:
    pages: List[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            pages.append(f"\n\n--- PAGE {page_no} ---\n{extract_page_text(page)}")
    return "".join(pages), pages





def find_table_crop_rect(page: Any) -> Optional[Any]:
    """
    Find DSA decomposition-table bounds using the PDF text layer.

    Extend the crop upward to retain the complete visible multi-level header,
    especially Actual/Historical/Preliminary/Estimate/Projection labels.
    """
    start_matches = []
    end_matches = []
    header_matches = []

    for phrase in TABLE_CROP_START_PHRASES:
        try:
            start_matches.extend(page.search_for(phrase))
        except Exception:
            pass

    for phrase in TABLE_CROP_END_PHRASES:
        try:
            end_matches.extend(page.search_for(phrase))
        except Exception:
            pass

    if not start_matches or not end_matches:
        return None

    start_rect = min(start_matches, key=lambda rect: rect.y0)
    valid_ends = [rect for rect in end_matches if rect.y1 > start_rect.y0]
    if not valid_ends:
        return None
    end_rect = max(valid_ends, key=lambda rect: rect.y1)

    # Only retain candidate header phrases located above the first decomposition
    # row, so narrative text or notes below the table cannot pull the crop down.
    for phrase in TABLE_CROP_HEADER_PHRASES:
        try:
            matches = page.search_for(phrase)
        except Exception:
            matches = []
        for rect in matches:
            if rect.y1 <= start_rect.y0:
                header_matches.append(rect)

    page_rect = page.rect
    if header_matches:
        header_top = min(rect.y0 for rect in header_matches)
        crop_top = max(
            page_rect.y0,
            header_top - TABLE_CROP_HEADER_MARGIN_POINTS,
        )
    else:
        crop_top = max(
            page_rect.y0,
            start_rect.y0 - TABLE_CROP_TOP_MARGIN_POINTS,
        )

    crop = pymupdf.Rect(
        page_rect.x0 + TABLE_CROP_SIDE_MARGIN_POINTS,
        crop_top,
        page_rect.x1 - TABLE_CROP_SIDE_MARGIN_POINTS,
        min(page_rect.y1, end_rect.y1 + TABLE_CROP_BOTTOM_MARGIN_POINTS),
    )

    if crop.width < page_rect.width * 0.60:
        return None
    if crop.height < 80 or crop.height >= page_rect.height * 0.96:
        return None
    return crop


def render_table_crop_to_compressed_pdf(
    source_pdf: Path,
    output_pdf: Path,
    page_no: int,
    crop_rect: Any,
    dpi: int,
    jpeg_quality: int,
) -> int:
    """Render a high-resolution crop of one DSA table as a compact PDF."""
    source_doc = pymupdf.open(str(source_pdf))
    output_doc = pymupdf.open()

    try:
        source_page = source_doc.load_page(page_no - 1)
        pix = source_page.get_pixmap(
            matrix=pymupdf.Matrix(dpi / 72.0, dpi / 72.0),
            clip=crop_rect,
            colorspace=pymupdf.csRGB,
            alpha=False,
        )

        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        jpeg_buffer = io.BytesIO()
        try:
            image.save(
                jpeg_buffer,
                format="JPEG",
                quality=jpeg_quality,
                optimize=True,
            )
            output_page = output_doc.new_page(
                width=crop_rect.width,
                height=crop_rect.height,
            )
            output_page.insert_image(
                output_page.rect,
                stream=jpeg_buffer.getvalue(),
                keep_proportion=False,
            )
            save_pymupdf_pdf_atomic(output_doc, output_pdf)
        finally:
            image.close()
            jpeg_buffer.close()
    finally:
        output_doc.close()
        source_doc.close()

    return output_pdf.stat().st_size


def create_table_crop_fallback_pdf(
    source_pdf: Path,
    output_pdf: Path,
    primary_page: int,
) -> Tuple[List[int], List[int], int, int, List[float]]:
    """Create an uploadable high-resolution crop of the primary DSA table."""
    source_doc = pymupdf.open(str(source_pdf))
    try:
        if not 1 <= primary_page <= source_doc.page_count:
            raise RuntimeError(f"Invalid primary table page: {primary_page}")
        page = source_doc.load_page(primary_page - 1)
        crop_rect = find_table_crop_rect(page)
    finally:
        source_doc.close()

    if crop_rect is None:
        raise RuntimeError(
            f"Could not identify reliable table crop boundaries on page {primary_page}."
        )

    for dpi in TABLE_CROP_DPI_OPTIONS:
        for quality in TABLE_CROP_JPEG_QUALITY_OPTIONS:
            size = render_table_crop_to_compressed_pdf(
                source_pdf,
                output_pdf,
                primary_page,
                crop_rect,
                dpi,
                quality,
            )
            print(
                f"  Table-crop fallback attempt: page {primary_page}, "
                f"{dpi} DPI, JPEG quality {quality}, {size:,} bytes"
            )
            if size <= MAX_UPLOAD_BYTES:
                crop_box = [
                    round(float(crop_rect.x0), 2),
                    round(float(crop_rect.y0), 2),
                    round(float(crop_rect.x1), 2),
                    round(float(crop_rect.y1), 2),
                ]
                return [primary_page], [], dpi, quality, crop_box

    raise RuntimeError(
        f"High-resolution table crop for page {primary_page} is still "
        f"{output_pdf.stat().st_size:,} bytes after maximum compression."
    )


def render_pages_to_compressed_pdf(
    source_pdf: Path,
    output_pdf: Path,
    page_numbers: List[int],
    dpi: int,
    jpeg_quality: int,
) -> int:
    """
    Render physical PDF pages with PyMuPDF, compress each rendered page as JPEG
    with Pillow, and rebuild an image-based PDF.

    The rebuilt PDF preserves the visible page layout but is usually much
    smaller than a source page containing complex vectors, embedded fonts,
    or oversized images.
    """
    source_doc = pymupdf.open(str(source_pdf))
    output_doc = pymupdf.open()

    try:
        zoom = dpi / 72.0
        matrix = pymupdf.Matrix(zoom, zoom)

        for page_no in sorted(set(page_numbers)):
            if not 1 <= page_no <= source_doc.page_count:
                continue

            source_page = source_doc.load_page(page_no - 1)
            pix = source_page.get_pixmap(
                matrix=matrix,
                colorspace=pymupdf.csRGB,
                alpha=False,
            )

            image = Image.frombytes(
                "RGB",
                (pix.width, pix.height),
                pix.samples,
            )

            jpeg_buffer = io.BytesIO()
            image.save(
                jpeg_buffer,
                format="JPEG",
                quality=jpeg_quality,
                optimize=True,
            )
            jpeg_bytes = jpeg_buffer.getvalue()

            # Keep the original PDF page dimensions in points.
            rect = source_page.rect
            output_page = output_doc.new_page(
                width=rect.width,
                height=rect.height,
            )
            output_page.insert_image(
                output_page.rect,
                stream=jpeg_bytes,
                keep_proportion=False,
            )

            image.close()
            jpeg_buffer.close()

        if output_doc.page_count == 0:
            raise RuntimeError("No valid pages were available for visual fallback.")

        save_pymupdf_pdf_atomic(output_doc, output_pdf)
    finally:
        output_doc.close()
        source_doc.close()

    return output_pdf.stat().st_size


def create_visual_fallback_pdf(
    source_pdf: Path,
    output_pdf: Path,
    start_page: int,
    end_page: int,
    primary_page: int,
) -> Tuple[List[int], List[int], int, int]:
    """
    Create an uploadable visual PDF fallback.

    The function first tries progressively lower DPI and JPEG quality settings
    while retaining all selected pages. If the PDF remains too large, it removes
    outer context pages one at a time while preserving the primary table page.
    """
    pages = list(range(start_page, end_page + 1))
    removed: List[int] = []

    while pages:
        for dpi in VISION_DPI_OPTIONS:
            for quality in VISION_JPEG_QUALITY_OPTIONS:
                size = render_pages_to_compressed_pdf(
                    source_pdf=source_pdf,
                    output_pdf=output_pdf,
                    page_numbers=pages,
                    dpi=dpi,
                    jpeg_quality=quality,
                )

                print(
                    f"  Visual fallback attempt: pages {pages}, "
                    f"{dpi} DPI, JPEG quality {quality}, {size:,} bytes"
                )

                if size <= MAX_UPLOAD_BYTES:
                    return pages.copy(), removed.copy(), dpi, quality

        if len(pages) == 1:
            raise RuntimeError(
                f"Visual fallback for page {pages[0]} is still "
                f"{output_pdf.stat().st_size:,} bytes after maximum compression."
            )

        left = pages[0]
        right = pages[-1]

        # Remove the page farther from the primary table page.
        if (
            abs(right - primary_page) >= abs(primary_page - left)
            and right != primary_page
        ):
            removed.append(pages.pop())
        elif left != primary_page:
            removed.append(pages.pop(0))
        else:
            removed.append(pages.pop())

    raise RuntimeError("Could not create an uploadable visual fallback PDF.")

def prepare_step1_input(full_text: str, filename: str, max_chars: int = 300_000) -> str:
    chunks = re.split(r"(?=\n\n--- PAGE \d+ ---)", full_text)
    selected = set(range(min(10, len(chunks))))
    for i, chunk in enumerate(chunks):
        lower = re.sub(r"\s+", " ", chunk.lower())
        if any(k in lower for k in DSA_KEYWORDS):
            for j in range(max(0, i - 2), min(len(chunks), i + 3)):
                selected.add(j)
    selected.update(range(max(0, len(chunks) - 30), len(chunks)))
    compact = "\n".join(chunks[i] for i in sorted(selected))
    return (f"PDF file: {filename}\n\n" + compact)[:max_chars]


def keyword_candidates(pages: List[str]) -> List[Dict[str, Any]]:
    hits = []
    for page_no, text in enumerate(pages, start=1):
        lower = text.lower()
        matched = [k for k in DSA_KEYWORDS if k in lower]
        if matched:
            score = len(matched) + (5 if "change in public debt" in matched else 0)
            hits.append((score, page_no, matched))
    hits.sort(reverse=True)
    out = []
    for score, page_no, matched in hits[:5]:
        out.append(
            {
                "rank": len(out) + 1,
                "start_page": max(1, page_no - 1),
                "end_page": page_no + 4,
                "reason": f"Keyword fallback score {score} on page {page_no}",
                "matched_phrases": matched,
                "likely_image_based": False,
            }
        )
    return out


def write_subset(source: Path, output: Path, page_numbers: List[int]) -> None:
    reader = PdfReader(str(source))
    writer = PdfWriter()
    for page_no in sorted(set(page_numbers)):
        if 1 <= page_no <= len(reader.pages):
            page = reader.pages[page_no - 1]
            try:
                page.compress_content_streams()
            except Exception:
                pass
            writer.add_page(page)
    if len(writer.pages) == 0:
        raise ValueError("No valid pages selected.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as f:
        writer.write(f)


def create_uploadable_subset(
    source: Path,
    output: Path,
    start_page: int,
    end_page: int,
    primary_page: int,
) -> Tuple[List[int], List[int]]:
    pages = list(range(start_page, end_page + 1))
    removed: List[int] = []
    while pages:
        write_subset(source, output, pages)
        if output.stat().st_size <= MAX_UPLOAD_BYTES:
            return pages, removed
        if len(pages) == 1:
            raise RuntimeError(
                f"Single page {pages[0]} is still {output.stat().st_size:,} bytes."
            )
        left, right = pages[0], pages[-1]
        if abs(right - primary_page) >= abs(primary_page - left) and right != primary_page:
            removed.append(pages.pop())
        elif left != primary_page:
            removed.append(pages.pop(0))
        else:
            removed.append(pages.pop())
    raise RuntimeError("Could not create an uploadable subset PDF.")



ACTUAL_COLUMN_STATUS_PATTERNS = {
    "preliminary": [r"\bprel\b", r"\bprel\.", r"\bpreliminary\b", r"\bprovisional\b"],
    "estimate": [r"\best\b", r"\best\.", r"\bestimate\b", r"\bestimated\b"],
    "projection": [r"\bproj\b", r"\bproj\.", r"\bprojection\b", r"\bprojections\b", r"\bforecast\b", r"\bmedium[- ]term projection\b", r"\bextended projection\b"],
}

ELIGIBLE_ACTUAL_STATUSES = {"actual", "historical"}


def classify_actual_column_status(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    for status, patterns in ACTUAL_COLUMN_STATUS_PATTERNS.items():
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
            return status
    if re.search(r"\bactual\b|\boutturn\b|\bfinal\b", text):
        return "actual"
    if re.search(r"\bhistorical\b|\bhistory\b", text):
        return "historical"
    return "unknown"


def extract_year_token(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    for pattern in (r"\b\d{4}/\d{2,4}\b", r"\b\d{4}-\d{2,4}\b", r"\b\d{4}\b"):
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return None


def get_selected_audit_column(source: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    audit = source.get("column_header_audit")
    if not isinstance(audit, dict):
        return None
    columns = audit.get("columns")
    if not isinstance(columns, list):
        return None
    selected = [item for item in columns if isinstance(item, dict) and item.get("selected") is True]
    return selected[0] if len(selected) == 1 else None


def validate_actual_column(result: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not result.get("table_found"):
        return errors
    source = result.get("source")
    if not isinstance(source, dict):
        return ["source is missing or is not an object"]
    last_year = extract_year_token(source.get("last_actual_year"))
    label_year = extract_year_token(source.get("actual_column_label"))
    status = str(source.get("actual_column_status") or "").strip().lower()
    if not last_year:
        errors.append("last_actual_year is missing or has no recognizable year")
    if not label_year:
        errors.append("actual_column_label is missing or has no recognizable year")
    if last_year and label_year and last_year != label_year:
        errors.append(f"last_actual_year and actual_column_label disagree: {last_year} versus {label_year}")
    if status not in ELIGIBLE_ACTUAL_STATUSES:
        errors.append(f"actual_column_status is not eligible: {status or 'missing'}")
    header_text = " ".join(str(source.get(key) or "") for key in ("actual_column_label", "actual_column_header_verbatim"))
    explicit_status = classify_actual_column_status(header_text)
    if explicit_status in {"preliminary", "estimate", "projection"}:
        errors.append(f"selected header is explicitly {explicit_status}: {header_text!r}")
    audit = source.get("column_header_audit")
    if not isinstance(audit, dict):
        errors.append("column_header_audit is missing")
        return errors
    selected_column = get_selected_audit_column(source)
    if selected_column is None:
        errors.append("column_header_audit must contain exactly one selected column")
        return errors
    audit_status = str(selected_column.get("status") or "").strip().lower()
    audit_year = extract_year_token(selected_column.get("year_label"))
    selected_year = extract_year_token(audit.get("selected_year"))
    if audit_status not in ELIGIBLE_ACTUAL_STATUSES:
        errors.append(f"selected audit column has ineligible status: {audit_status or 'missing'}")
    if last_year and audit_year and last_year != audit_year:
        errors.append(f"selected audit year differs from last_actual_year: {audit_year} versus {last_year}")
    if last_year and selected_year and last_year != selected_year:
        errors.append(f"audit.selected_year differs from last_actual_year: {selected_year} versus {last_year}")
    return errors


def set_actual_column_validation(result: Dict[str, Any], status: str, issues: List[str], first_selected_year: Optional[str] = None, audited_selected_year: Optional[str] = None) -> None:
    source = result.get("source")
    if not isinstance(source, dict):
        return
    source["actual_column_validation"] = {
        "status": status,
        "issues": issues,
        "first_selected_year": first_selected_year,
        "audited_selected_year": audited_selected_year,
    }


def build_independent_header_audit_prompt() -> str:
    return """
INDEPENDENT HEADER AUDIT ONLY

Inspect the complete multi-level header of the qualifying PUBLIC DSA row-and-column table in the attached PDF.
Do not assume any previous selected year is correct or incorrect. Do not extract decomposition rows or values.
Return ONLY this JSON object:
{
  "column_header_audit": {
    "columns": [{"position": 1, "year_label": "", "group_label": null, "status": "actual", "status_basis": "", "selected": false}],
    "selected_year": null,
    "selection_reason": ""
  },
  "latest_observation_year": null,
  "latest_observation_status": null,
  "confidence": "high",
  "issues": []
}
Allowed statuses: actual, historical, preliminary, estimate, projection, unknown.
Select the rightmost explicitly actual/historical year; otherwise the rightmost year clearly in the historical block and separated from preliminary/estimate/projection columns. Do not force a selection when uncertain.
"""


def audit_selected_year(audit_result: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    audit = audit_result.get("column_header_audit")
    if not isinstance(audit, dict):
        return None, None
    columns = audit.get("columns")
    if not isinstance(columns, list):
        return None, None
    selected = [item for item in columns if isinstance(item, dict) and item.get("selected") is True]
    if len(selected) != 1:
        return None, None
    return extract_year_token(selected[0].get("year_label")), str(selected[0].get("status") or "").strip().lower()


def reconcile_with_independent_audit(first_result: Dict[str, Any], audit_result: Dict[str, Any], first_errors: List[str]) -> Dict[str, Any]:
    source = first_result.get("source")
    if not isinstance(source, dict):
        return first_result
    first_year = extract_year_token(source.get("last_actual_year"))
    audited_year, audited_status = audit_selected_year(audit_result)
    audit = audit_result.get("column_header_audit")
    if isinstance(audit, dict):
        source["independent_column_header_audit"] = audit
    source["independent_latest_observation_year"] = audit_result.get("latest_observation_year")
    source["independent_latest_observation_status"] = audit_result.get("latest_observation_status")
    if first_year and audited_year and first_year == audited_year and audited_status in ELIGIBLE_ACTUAL_STATUSES:
        issues = list(first_errors)
        if first_errors:
            issues.append("Independent header audit confirmed the same selected year.")
        set_actual_column_validation(first_result, "accepted_with_warning" if first_errors else "accepted", issues, first_year, audited_year)
        return first_result
    issues = list(first_errors)
    if audited_year and first_year and audited_year != first_year:
        issues.append(f"Independent audit selected {audited_year}, while the first extraction selected {first_year}.")
    elif not audited_year:
        issues.append("Independent audit could not identify one eligible actual or historical year.")
    else:
        issues.append("First extraction did not provide a usable selected year.")
    set_actual_column_validation(first_result, "manual_review", issues, first_year, audited_year)
    source["confidence"] = "low"
    note = "Actual-year selection requires manual review. " + " ".join(issues)
    first_result["extraction_notes"] = f"{str(first_result.get('extraction_notes') or '').strip()} {note}".strip()
    return first_result


def attach_metadata(final: Dict[str, Any], locator: Dict[str, Any], filename: str) -> None:
    metadata = locator.get("report_metadata") or {}
    final.setdefault("report_metadata", metadata)
    final.setdefault("pdf_file_name", filename)
    source = final.get("source")
    if isinstance(source, dict):
        source["country"] = source.get("country") or metadata.get("country")
        source["publication_date"] = source.get("publication_date") or metadata.get("publication_date")
        source["consultation_type"] = source.get("consultation_type") or metadata.get("consultation_type")


def add_table_crop_header_instruction(
    user_text: str,
    extraction_method: str,
) -> str:
    """Add a no-guessing instruction when Step 2 receives a table crop."""
    if extraction_method != "pymupdf_pillow_table_crop_fallback":
        return user_text
    return user_text + (
        "\n\nTABLE-CROP HEADER CHECK:\n"
        "The crop is intended to include the complete multi-level column header. "
        "Before selecting last_actual_year, verify that the visible crop contains "
        "enough evidence to distinguish actual/historical columns from preliminary, "
        "estimate, and projection columns. Do not infer an actual year from year "
        "order or column position alone. If the relevant status headings or group "
        "boundaries remain absent or ambiguous, return null actual-year fields and "
        "mark the selection for manual review rather than guessing."
    )


def process_pdf(
    pdf_path: Path,
    responses_url: Optional[str],
    token_manager: anthropic.Anthropic,
    model: str,
    prompt1: str,
    prompt2: str,
) -> Path:
    started = time.perf_counter()
    stem = pdf_path.stem

    print("  Step 1: locating DSA pages...")
    full_text, pages = extract_full_text(pdf_path)
    try:
        locator = call_text_json(
            responses_url,
            token_manager,
            model,
            prompt1,
            prepare_step1_input(full_text, pdf_path.name),
        )
    except Exception as exc:
        candidates = keyword_candidates(pages)
        locator = {
            "report_metadata": {"pdf_file_name": pdf_path.name},
            "dsa_section_found": bool(candidates),
            "framework_hint": "UNKNOWN",
            "candidates": candidates,
            "primary_table_page": candidates[0]["start_page"] + 1 if candidates else None,
            "recommended_start_page": candidates[0]["start_page"] if candidates else None,
            "recommended_end_page": candidates[0]["end_page"] if candidates else None,
            "confidence": "low",
            "notes": f"Locator failed; keyword fallback used. Error: {exc}",
        }
    write_json(OUTPUT_DIR / f"{stem}_step1_locator.json", locator)

    if not locator.get("dsa_section_found"):
        final = {
            "table_found": False,
            "failure_reason": "dsa_pages_not_in_input",
            "source": None,
            "decomposition": None,
            "unmapped_rows": [],
            "extraction_notes": f"Step 1 found no PUBLIC DSA. {locator.get('notes', '')}",
            "extraction_method": "step1_no_dsa_found",
        }
        attach_metadata(final, locator, pdf_path.name)
        out = OUTPUT_DIR / f"{stem}_dsa.json"
        write_json(out, final)
        return out

    total_pages = len(PdfReader(str(pdf_path)).pages)
    start_page = max(1, int(locator["recommended_start_page"]))
    end_page = min(total_pages, int(locator["recommended_end_page"]))
    primary = locator.get("primary_table_page")
    try:
        primary_page = int(primary)
    except (TypeError, ValueError):
        primary_page = (start_page + end_page) // 2
    if not (start_page <= primary_page <= end_page):
        primary_page = (start_page + end_page) // 2

    selected_pdf = SELECTED_PDF_DIR / f"{stem}_pages_{start_page}_{end_page}.pdf"
    table_crop_pdf = (
        SELECTED_PDF_DIR
        / f"{stem}_page_{primary_page}_table_crop_fallback.pdf"
    )
    visual_pdf = (
        SELECTED_PDF_DIR
        / f"{stem}_pages_{start_page}_{end_page}_vision_fallback.pdf"
    )

    included: List[int] = []
    removed: List[int] = []
    selected_pdf_size: Optional[int] = None
    fallback_reason: Optional[str] = None
    vision_dpi: Optional[int] = None
    vision_jpeg_quality: Optional[int] = None
    table_crop_box: Optional[List[float]] = None
    table_crop_failure_reason: Optional[str] = None
    pdf_sent_to_api: Optional[Path] = None

    try:
        included, removed = create_uploadable_subset(
            pdf_path,
            selected_pdf,
            start_page,
            end_page,
            primary_page,
        )
        selected_pdf_size = selected_pdf.stat().st_size
        pdf_sent_to_api = selected_pdf

        print(
            f"  Selected PDF: {selected_pdf.name}, "
            f"{selected_pdf_size:,} bytes, original pages {included}"
        )
        extraction_method = "selected_pdf_direct"

    except Exception as exc:
        fallback_reason = str(exc)

        print(
            "  Selected PDF is too large for inline upload. "
            "Trying a high-resolution DSA table crop first..."
        )

        try:
            included, _, vision_dpi, vision_jpeg_quality, table_crop_box = (
                create_table_crop_fallback_pdf(
                    source_pdf=pdf_path,
                    output_pdf=table_crop_pdf,
                    primary_page=primary_page,
                )
            )
            removed = sorted(
                set(
                    removed
                    + [
                        page_no
                        for page_no in range(start_page, end_page + 1)
                        if page_no not in included
                    ]
                )
            )
            selected_pdf_size = table_crop_pdf.stat().st_size
            pdf_sent_to_api = table_crop_pdf
            extraction_method = "pymupdf_pillow_table_crop_fallback"

            print(
                f"  Table-crop fallback PDF: {table_crop_pdf.name}, "
                f"{selected_pdf_size:,} bytes, original page {included}, "
                f"{vision_dpi} DPI, JPEG quality {vision_jpeg_quality}, "
                f"crop box {table_crop_box}"
            )

        except Exception as crop_exc:
            table_crop_failure_reason = str(crop_exc)
            print(
                "  Table-crop fallback was not available. "
                "Creating a compressed full-page visual fallback..."
            )
            included, visual_removed, vision_dpi, vision_jpeg_quality = (
                create_visual_fallback_pdf(
                    source_pdf=pdf_path,
                    output_pdf=visual_pdf,
                    start_page=start_page,
                    end_page=end_page,
                    primary_page=primary_page,
                )
            )
            removed = sorted(set(removed + visual_removed))
            selected_pdf_size = visual_pdf.stat().st_size
            pdf_sent_to_api = visual_pdf
            extraction_method = "pymupdf_pillow_visual_fallback"

    print("  Step 2: sending selected pages inline and extracting table...")
    mapping = "\n".join(
        f"Selected PDF page {i} = original physical PDF page {p}"
        for i, p in enumerate(included, start=1)
    )
    user_text = (
        f"Original PDF file: {pdf_path.name}\n"
        f"Selected PDF file: {pdf_sent_to_api.name}\n"
        f"Input rendering method: {extraction_method}\n"
        f"Rendering DPI: {vision_dpi}\n"
        f"JPEG quality: {vision_jpeg_quality}\n"
        f"Table crop box: {table_crop_box}\n\n"
        f"ORIGINAL PHYSICAL PAGE MAPPING:\n{mapping}\n\n"
        f"STEP 1 LOCATOR OUTPUT:\n"
        f"{json.dumps(locator, indent=2, ensure_ascii=False)}"
    )
    user_text = add_table_crop_header_instruction(user_text, extraction_method)

    try:
        final = call_pdf_json(
            responses_url,
            token_manager,
            model,
            prompt2,
            user_text,
            pdf_sent_to_api,
        )
    except Exception as exc:
        # A gateway 413 can occasionally occur even when the local estimate is
        # below the configured threshold. In that case, rebuild the visual PDF
        # and retry once through the normal API retry mechanism.
        error_text = str(exc)
        size_related = any(
            phrase in error_text.lower()
            for phrase in [
                "maximum allowed size",
                "request entity too large",
                "error 413",
                "above the configured base64-safe limit",
                "too close to or above the 1 mb gateway limit",
            ]
        )

        if not size_related or extraction_method == "pymupdf_pillow_visual_fallback":
            raise

        fallback_reason = error_text
        print(
            "  Direct selected PDF was rejected for size. "
            "Trying a high-resolution DSA table crop first..."
        )

        try:
            included, _, vision_dpi, vision_jpeg_quality, table_crop_box = (
                create_table_crop_fallback_pdf(
                    source_pdf=pdf_path,
                    output_pdf=table_crop_pdf,
                    primary_page=primary_page,
                )
            )
            removed = sorted(
                set(
                    removed
                    + [
                        page_no
                        for page_no in range(start_page, end_page + 1)
                        if page_no not in included
                    ]
                )
            )
            selected_pdf_size = table_crop_pdf.stat().st_size
            pdf_sent_to_api = table_crop_pdf
            extraction_method = "pymupdf_pillow_table_crop_fallback"
        except Exception as crop_exc:
            table_crop_failure_reason = str(crop_exc)
            included, visual_removed, vision_dpi, vision_jpeg_quality = (
                create_visual_fallback_pdf(
                    source_pdf=pdf_path,
                    output_pdf=visual_pdf,
                    start_page=start_page,
                    end_page=end_page,
                    primary_page=primary_page,
                )
            )
            removed = sorted(set(removed + visual_removed))
            selected_pdf_size = visual_pdf.stat().st_size
            pdf_sent_to_api = visual_pdf
            extraction_method = "pymupdf_pillow_visual_fallback"

        mapping = "\n".join(
            f"Selected PDF page {i} = original physical PDF page {p}"
            for i, p in enumerate(included, start=1)
        )
        user_text = (
            f"Original PDF file: {pdf_path.name}\n"
            f"Selected PDF file: {pdf_sent_to_api.name}\n"
            f"Input rendering method: {extraction_method}\n"
            f"Rendering DPI: {vision_dpi}\n"
            f"JPEG quality: {vision_jpeg_quality}\n"
            f"Table crop box: {table_crop_box}\n\n"
            f"ORIGINAL PHYSICAL PAGE MAPPING:\n{mapping}\n\n"
            f"STEP 1 LOCATOR OUTPUT:\n"
            f"{json.dumps(locator, indent=2, ensure_ascii=False)}"
        )
        user_text = add_table_crop_header_instruction(user_text, extraction_method)

        final = call_pdf_json(
            responses_url,
            token_manager,
            model,
            prompt2,
            user_text,
            pdf_sent_to_api,
        )


    # Validate the first extraction. If it is inconsistent or uncertain,
    # request a narrow independent header audit that does not assume the first
    # answer is wrong. Disagreement is flagged for manual review rather than
    # forcing a replacement year.
    actual_column_errors = validate_actual_column(final)

    if not actual_column_errors:
        first_source = final.get("source") or {}
        first_year = extract_year_token(first_source.get("last_actual_year"))
        set_actual_column_validation(
            final,
            "accepted",
            [],
            first_selected_year=first_year,
            audited_selected_year=first_year,
        )
    else:
        print("  Actual-column selection is uncertain. Requesting an independent header audit...")
        audit_result = call_pdf_json(
            responses_url,
            token_manager,
            model,
            build_independent_header_audit_prompt(),
            user_text,
            pdf_sent_to_api,
        )
        final = reconcile_with_independent_audit(
            final,
            audit_result,
            actual_column_errors,
        )


    selected_original_pages = included

    attach_metadata(final, locator, pdf_path.name)
    final["extraction_method"] = extraction_method
    final["selected_original_pages"] = selected_original_pages
    if vision_dpi is not None:
        final["vision_fallback_dpi"] = vision_dpi
    if vision_jpeg_quality is not None:
        final["vision_fallback_jpeg_quality"] = vision_jpeg_quality
    if table_crop_box is not None:
        final["table_crop_box_points"] = table_crop_box

    notes: List[str] = []
    existing_notes = final.get("extraction_notes")
    if existing_notes:
        notes.append(str(existing_notes).strip())

    if removed:
        notes.append(
            f"Outer original page(s) {sorted(removed)} were removed "
            "to meet the upload limit."
        )

    if fallback_reason:
        if extraction_method == "pymupdf_pillow_table_crop_fallback":
            notes.append(
                "The selected PDF exceeded the inline upload limit, so Step 2 "
                "used a high-resolution image-based crop of the qualifying DSA "
                "table. Surrounding charts and other material outside the table "
                f"were omitted. Trigger: {fallback_reason}"
            )
        else:
            notes.append(
                "The selected PDF exceeded the inline upload limit, so Step 2 "
                "used a compressed image-based rendering of the selected page(s). "
                "Values were extracted only where the rendered text was clearly "
                f"legible. Trigger: {fallback_reason}"
            )

    if table_crop_failure_reason:
        notes.append(
            "A table-focused crop was attempted before the full-page visual "
            f"fallback but could not be used. Reason: {table_crop_failure_reason}"
        )

    if notes:
        final["extraction_notes"] = " ".join(notes)

    out = OUTPUT_DIR / f"{stem}_dsa.json"
    write_json(out, final)

    write_json(
        OUTPUT_DIR / f"{stem}_timing.json",
        {
            "pdf_file": pdf_path.name,
            "selected_original_pages": selected_original_pages,
            "selected_pdf_size_bytes": selected_pdf_size,
            "removed_for_size": removed,
            "fallback_reason": fallback_reason,
            "extraction_method": extraction_method,
            "vision_fallback_dpi": vision_dpi,
            "vision_fallback_jpeg_quality": vision_jpeg_quality,
            "table_crop_box_points": table_crop_box,
            "table_crop_failure_reason": table_crop_failure_reason,
            "pdf_sent_to_api": str(pdf_sent_to_api) if pdf_sent_to_api else None,
            "total_pdf_seconds": elapsed(started),
        },
    )
    return out


def main() -> None:
    run_start = time.perf_counter()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SELECTED_PDF_DIR.mkdir(parents=True, exist_ok=True)
    prompt1, prompt2 = load_two_subprompts(PROMPT_FILE)
    responses_url, token_manager, model = make_api_session()
    all_pdfs = sorted(PDF_DIR.glob("*.pdf"))
    if not all_pdfs:
        raise RuntimeError(f"No PDFs found in {PDF_DIR}")

    skipped_union_pdfs = [pdf for pdf in all_pdfs if is_excluded_union(pdf)]
    pdfs = [pdf for pdf in all_pdfs if not is_excluded_union(pdf)]

    print(f"Found {len(all_pdfs)} PDF(s) in total.")
    print(f"Skipping {len(skipped_union_pdfs)} currency/monetary union report(s).")
    for skipped_pdf in skipped_union_pdfs:
        print(f"  Skipped union report: {skipped_pdf.name}")

    if not pdfs:
        raise RuntimeError("No country-level PDFs remain after union exclusions.")

    print(f"Processing {len(pdfs)} country-level PDF(s). Model: {model}")
    print(f"Concurrent report workers: {MAX_WORKERS}")

    results = []

    # Outcome counters distinguish valid negative findings from actual
    # API/processing failures.
    tables_extracted = 0
    no_dsa_table_found = 0
    api_or_processing_failures = 0
    uploaded = 0
    vision_fallbacks = 0
    table_crop_fallbacks = 0

    failure_counts = {
        "dsa_pages_not_in_input": 0,
        "pages_unreadable": 0,
        "only_external_dsa_found": 0,
        "other": 0,
    }

    def process_one(index: int, pdf: Path) -> Dict[str, Any]:
        """Process one report and return its run-summary record."""
        print(f"\n[{index}/{len(pdfs)}] Starting {pdf.name}")
        started = time.perf_counter()

        try:
            out = process_pdf(
                pdf,
                responses_url,
                token_manager,
                model,
                prompt1,
                prompt2,
            )

            data = json.loads(out.read_text(encoding="utf-8"))
            print(f"\n[{index}/{len(pdfs)}] Saved: {out.name}")

            return {
                "pdf_file": pdf.name,
                "status": "ok",
                "seconds": elapsed(started),
                "output": str(out),
                "extraction_method": data.get("extraction_method"),
                "table_found": bool(data.get("table_found")),
                "failure_reason": data.get("failure_reason"),
            }

        except Exception as exc:
            seconds = elapsed(started)
            error_file = OUTPUT_DIR / f"{pdf.stem}_ERROR.json"

            write_json(
                error_file,
                {
                    "error": str(exc),
                    "seconds": seconds,
                },
            )

            print(f"\n[{index}/{len(pdfs)}] Error for {pdf.name}: {exc}")

            return {
                "pdf_file": pdf.name,
                "status": "error",
                "seconds": seconds,
                "error": str(exc),
                "error_file": str(error_file),
            }

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_pdf = {
            executor.submit(process_one, index, pdf): pdf
            for index, pdf in enumerate(pdfs, start=1)
        }

        for future in as_completed(future_to_pdf):
            result = future.result()
            results.append(result)

            if result["status"] == "ok":
                # Count how the report was sent to Step 2.
                if result.get("extraction_method") == "selected_pdf_direct":
                    uploaded += 1
                elif result.get("extraction_method") == "pymupdf_pillow_table_crop_fallback":
                    table_crop_fallbacks += 1
                    vision_fallbacks += 1
                elif result.get("extraction_method") == "pymupdf_pillow_visual_fallback":
                    vision_fallbacks += 1

                # A model result with table_found=false is a completed,
                # informative outcome rather than an API/processing failure.
                if result.get("table_found"):
                    tables_extracted += 1
                else:
                    no_dsa_table_found += 1
                    reason = result.get("failure_reason")
                    if reason in failure_counts:
                        failure_counts[reason] += 1
                    else:
                        failure_counts["other"] += 1
            else:
                api_or_processing_failures += 1

    # Reports finish in a different order when processed concurrently.
    # Sort the run summary alphabetically for easier review.
    results.sort(key=lambda item: item["pdf_file"].lower())

    total = elapsed(run_start)
    summary = {
        "reports_found_total": len(all_pdfs),
        "reports_excluded_unions": len(skipped_union_pdfs),
        "excluded_union_files": [pdf.name for pdf in skipped_union_pdfs],
        "reports_processed": len(pdfs),

        # Main outcomes
        "tables_extracted": tables_extracted,
        "no_dsa_table_found": no_dsa_table_found,
        "api_or_processing_failures": api_or_processing_failures,

        # Detailed breakdown of completed runs where table_found=false
        "no_table_breakdown": failure_counts,

        # Input method used for successful Step 2 calls
        "selected_pdfs_uploaded": uploaded,
        "vision_fallback_used": vision_fallbacks,
        "table_crop_fallback_used": table_crop_fallbacks,
        "full_page_visual_fallback_used": vision_fallbacks - table_crop_fallbacks,

        "total_runtime_seconds": total,
        "average_runtime_seconds": round(total / len(pdfs), 2),
        "model": model,
        "safe_upload_limit_bytes": MAX_UPLOAD_BYTES,
        "max_workers": MAX_WORKERS,
        "max_api_attempts": MAX_API_ATTEMPTS,
        "initial_retry_delay_seconds": INITIAL_RETRY_DELAY_SECONDS,
        "max_retry_delay_seconds": MAX_RETRY_DELAY_SECONDS,
        "pdfs": results,
    }
    write_json(OUTPUT_DIR / "RUN_SUMMARY.json", summary)
    print("\n========== RUN SUMMARY ==========")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Fatal error: {exc}")
        sys.exit(1)
