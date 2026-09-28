"""
Offline regression test for one specific fix in 2a_dsa_pipeline_260924.py: the PDF sent to the API must be
written to SELECTED_PDF_DIR (an independent folder, e.g. set by 0_run_2a_1b.py to <run>/selected_pdf_pages,
a sibling of <run>/json_output — matching round 1's layout), not nested under OUTPUT_DIR.

This does not test the pipeline's extraction quality or its real API calls (those need network access and a
real .env); it only exercises the real page-selection / PDF-building code path (build_step2_input, on a small
real synthetic PDF) with a fake API client, and checks where files land on disk.

Run: python test_2a_dsa_pipeline_selected_pdf_dir.py
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf

HERE = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()


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


class FakeApi:
    """Stands in for ApiClient: no network, no .env, no MSAL. Routes by call order."""

    model = "test-model"

    def __init__(self):
        self.calls = []  # (has_pdf_path,) per call, in order

    def call_json(self, prompt, user_text, pdf_path=None):
        self.calls.append(pdf_path is not None)
        n = len(self.calls)
        if n == 1:  # locator (no pdf_path)
            return {
                "dsa_section_found": True, "framework_hint": "MAC_DSA",
                "candidates": [{"rank": 1, "start_page": 1, "end_page": 1, "reason": "t", "matched_phrases": [], "likely_image_based": False}],
                "primary_table_page": 1, "recommended_start_page": 1, "recommended_end_page": 1,
                "confidence": "high", "notes": "",
            }
        node = lambda v: {"label_verbatim": "x", "value": v, "children": []}
        decomposition = {
            "change_in_debt": {"label_verbatim": "Change in public sector debt", "value": "1.5"},
            "identified_flows": {"label_verbatim": "Identified debt-creating flows", "value": "0.5"},
            "primary_balance": node("-0.3"), "automatic_debt_dynamics": node("0.2"),
            "other_identified_flows": node(None), "residual": node("1.0"),
        }
        if n == 2:  # extraction (with pdf_path)
            return {
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
        # verification (with pdf_path)
        return {
            "column_header_audit": {"columns": [{"position": 1, "year_label": "2019", "status": "actual", "selected": True}], "selected_year": "2019"},
            "latest_observation_year": "2019", "latest_observation_status": "actual",
            "rows": [
                {"label_verbatim": "Change in public sector debt", "value": "1.5"},
                {"label_verbatim": "Identified debt-creating flows", "value": "0.5"},
                {"label_verbatim": "x", "value": "-0.3"},
            ],
            "issues": [], "confidence": "high",
        }


def test_selected_pdf_goes_to_its_own_folder():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        mod = load(HERE / "2a_dsa_pipeline_260924.py", "dsa_pipeline_test")
        mod.OUTPUT_DIR = d / "run" / "json_output"
        mod.SELECTED_PDF_DIR = d / "run" / "selected_pdf_pages"  # a SIBLING of json_output, as 0_run_2a_1b.py sets it
        mod.OUTPUT_DIR.mkdir(parents=True)
        mod.SELECTED_PDF_DIR.mkdir(parents=True)

        prompts = mod.load_prompts(HERE.parent / "dsa_prompt_20260924.txt")
        pdf_path = d / "Testland_2020-01-01.pdf"
        make_pdf(pdf_path)

        api = FakeApi()
        out = mod.process_pdf(pdf_path, api, prompts, mod.OUTPUT_DIR)
        assert api.calls == [False, True, True], api.calls  # locator (text-only), extraction, verification

        result = json.loads(out.read_text(encoding="utf-8"))
        assert result["table_found"] is True
        assert "actual_column_validation" in result["source"]  # exact status isn't the point of this test

        # JSON outputs: directly under OUTPUT_DIR
        assert (mod.OUTPUT_DIR / "Testland_2020-01-01_dsa.json").exists()
        assert (mod.OUTPUT_DIR / "Testland_2020-01-01_step1_locator.json").exists()
        assert (mod.OUTPUT_DIR / "Testland_2020-01-01_timing.json").exists()

        # the PDF actually sent to the (fake) API: in SELECTED_PDF_DIR, not nested under OUTPUT_DIR
        selected_pdfs = list(mod.SELECTED_PDF_DIR.glob("*.pdf"))
        assert len(selected_pdfs) == 1, selected_pdfs
        assert selected_pdfs[0].name.startswith("Testland_2020-01-01_pages_")
        assert not list((mod.OUTPUT_DIR / "selected_pdf_pages").glob("*.pdf")) if (mod.OUTPUT_DIR / "selected_pdf_pages").exists() else True
        assert not (mod.OUTPUT_DIR / "selected_pdf_pages").exists()  # the old nested location must not be created at all

        # timing.json's pdf_sent_to_api points at the file that is actually there (matched by 3c on file name, not full path)
        timing = json.loads((mod.OUTPUT_DIR / "Testland_2020-01-01_timing.json").read_text(encoding="utf-8"))
        assert Path(timing["pdf_sent_to_api"]).name == selected_pdfs[0].name
        assert timing["extraction_method"] == "selected_pdf_direct"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok  ", t.__name__)
    print(f"\nall {len(tests)} tests passed")
