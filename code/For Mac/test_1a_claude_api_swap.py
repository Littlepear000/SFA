"""
Offline regression test for the For-Mac copy of 1a: process_pdf() must still work end to end
after replacing the IMF Azure-AD-authenticated API calls with Anthropic's Claude Messages API.

This does not call the real Claude API (no network, no real ANTHROPIC_API_KEY needed); it
stands in a FakeClient whose .messages.create(**kwargs) mimics anthropic.Anthropic's shape
closely enough to exercise call_text_json() / call_pdf_json() / extract_output_text() and the
whole process_pdf() control flow (locator call, extraction call, independent-audit call) on a
small real synthetic PDF built with pymupdf.

Run: python test_1a_claude_api_swap.py
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf

HERE = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
SCRIPT = HERE / "1a_two_step_selected_pdf_inline_base64_cropfallback_summary_v7_header_aware_crop_effort.py"
PROMPT_FILE = HERE.parent.parent / "two_step_selected_pdf_prompt_table_only_cropfallback_v5_flexible_actual.txt"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def make_pdf(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Change in public sector debt   1.5")
    page.insert_text((72, 90), "Identified debt-creating flows   0.5")
    page.insert_text((72, 108), "Primary deficit   -0.3")
    page.insert_text((72, 126), "Automatic debt dynamics   0.2")
    page.insert_text((72, 144), "Residual, including asset changes   1.0")
    doc.save(str(path))
    doc.close()


def text_block(text: str):
    return SimpleNamespace(type="text", text=text)


class FakeMessages:
    def __init__(self, outer):
        self.outer = outer

    def create(self, **kwargs):
        self.outer.calls.append(kwargs)
        content = kwargs["messages"][0]["content"]
        has_document = isinstance(content, list) and any(
            block.get("type") == "document" for block in content
        )
        n = len(self.outer.calls)

        if n == 1:  # Step 1 locator: text-only call
            assert not has_document, "locator call must not attach a PDF document"
            payload = {
                "dsa_section_found": True, "framework_hint": "MAC_DSA",
                "candidates": [{"rank": 1, "start_page": 1, "end_page": 1, "reason": "t", "matched_phrases": [], "likely_image_based": False}],
                "primary_table_page": 1, "recommended_start_page": 1, "recommended_end_page": 1,
                "confidence": "high", "notes": "",
            }
            return SimpleNamespace(content=[text_block(json.dumps(payload))])

        assert has_document, f"call {n} (extraction/audit) must attach the PDF document"
        node = lambda v: {"label_verbatim": "x", "value": v, "children": []}
        decomposition = {
            "change_in_debt": {"label_verbatim": "Change in public sector debt", "value": "1.5"},
            "identified_flows": {"label_verbatim": "Identified debt-creating flows", "value": "0.5"},
            "primary_balance": node("-0.3"), "automatic_debt_dynamics": node("0.2"),
            "other_identified_flows": node(None), "residual": node("1.0"),
        }
        if n == 2:  # Step 2 extraction
            payload = {
                "table_found": True,
                "source": {
                    "country": "Testland", "framework": "MAC_DSA", "table_number": "1", "table_title": "t",
                    "last_actual_year": "2019", "actual_column_label": "2019", "actual_column_status": "actual",
                    "actual_column_header_verbatim": "Actual 2019",
                    "column_header_audit": {"columns": [{"position": 1, "year_label": "2019", "status": "actual", "selected": True}], "selected_year": "2019"},
                    "confidence": "high",
                },
                "decomposition": decomposition, "unmapped_rows": [], "extraction_notes": "",
            }
            return SimpleNamespace(content=[text_block(json.dumps(payload))])

        # n == 3: independent header audit (only reached if validate_actual_column flagged something)
        payload = {
            "column_header_audit": {"columns": [{"position": 1, "year_label": "2019", "status": "actual", "selected": True}], "selected_year": "2019"},
            "latest_observation_year": "2019", "latest_observation_status": "actual",
            "rows": [
                {"label_verbatim": "Change in public sector debt", "value": "1.5"},
                {"label_verbatim": "Identified debt-creating flows", "value": "0.5"},
                {"label_verbatim": "x", "value": "-0.3"},
            ],
            "issues": [], "confidence": "high",
        }
        return SimpleNamespace(content=[text_block(json.dumps(payload))])


class FakeClient:
    """Stands in for anthropic.Anthropic: no network, no real API key."""

    def __init__(self):
        self.calls = []
        self.messages = FakeMessages(self)


def test_process_pdf_with_fake_claude_client():
    assert PROMPT_FILE.exists(), f"prompt file not found: {PROMPT_FILE}"
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        mod = load(SCRIPT, "dsa_pipeline_1a_mac_test")
        mod.OUTPUT_DIR = d / "json_output"
        mod.SELECTED_PDF_DIR = d / "selected_pdf_pages"
        mod.OUTPUT_DIR.mkdir(parents=True)
        mod.SELECTED_PDF_DIR.mkdir(parents=True)

        prompt1, prompt2 = mod.load_two_subprompts(PROMPT_FILE)
        pdf_path = d / "Testland_2020-01-01.pdf"
        make_pdf(pdf_path)

        client = FakeClient()
        out = mod.process_pdf(pdf_path, None, client, mod.MODEL, prompt1, prompt2)
        assert len(client.calls) in (2, 3), client.calls  # locator + extraction, and audit only if needed

        result = json.loads(out.read_text(encoding="utf-8"))
        assert result["table_found"] is True
        assert "actual_column_validation" in result["source"]

        assert (mod.OUTPUT_DIR / "Testland_2020-01-01_dsa.json").exists()
        assert (mod.OUTPUT_DIR / "Testland_2020-01-01_step1_locator.json").exists()

        selected_pdfs = list(mod.SELECTED_PDF_DIR.glob("*.pdf"))
        assert len(selected_pdfs) == 1, selected_pdfs


def test_make_api_session_requires_anthropic_key():
    mod = load(SCRIPT, "dsa_pipeline_1a_mac_test_session")
    mod.ENV_FILE = Path(tempfile.mkdtemp()) / "does_not_exist.env"
    try:
        mod.make_api_session()
        assert False, "expected RuntimeError for missing ANTHROPIC_API_KEY"
    except RuntimeError as exc:
        assert "ANTHROPIC_API_KEY" in str(exc)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok  ", t.__name__)
    print(f"\nall {len(tests)} tests passed")
