"""Offline tests for the gap-year fill logic. Run: python gapfill_test_logic.py"""
import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent if "__file__" in globals() else
                       next((c for c in (Path.cwd(), Path.cwd() / "code") if (c / "gapfill_lib_core.py").exists()), Path.cwd())))
import gapfill_lib_core as core  # noqa: E402
import importlib.util  # noqa: E402


def _load(path, name, defaults=None):
    """Load a script as a module. `defaults` pre-seeds module-level names before the module body runs
    (mirrors runpy's init_globals) -- needed for 3a/3b, whose own CONFIG block is commented out on a
    real run (the controller injects it instead), which would otherwise make `def main(x=INPUT_CSV)`
    raise NameError at import time when loaded standalone, as this test file does."""
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    if defaults:
        for k, v in defaults.items():
            setattr(mod, k, v)
    spec.loader.exec_module(mod)
    return mod


_HERE = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
run = _load(_HERE / "3c_gapfill_3_run_api.py", "gapfill_run_api")
three_a = _load(_HERE / "3a_gapfill_1_build_panel_gap_flags.py", "gapfill_3a_test",
                 defaults={"INPUT_CSV": Path("/dev/null"), "OUT_DIR": None, "STAMP": "test"})
three_b = _load(_HERE / "3b_gapfill_2_build_targets.py", "gapfill_3b_test",
                 defaults={"CHECK_DIR": Path("/dev/null"), "STAMP": "test"})


def rep(name, country, date):
    return {"pdf_file_name": name, "path": f"/x/{name}", "country": country, "date": date, "year": int(date[:4])}


# ------------------------------------------------------------ helpers for targets
def decomp(chg="1.0", idf="0.5", res="0.5", pb="0.2", ad="0.2", oth="0.1"):
    node = lambda v: {"label_verbatim": "x", "value": v}
    kids = lambda v: {"label_verbatim": "x", "value": v, "children": [{"label_verbatim": "kid", "value": "0.1", "children": []}]}
    return {"debt_level": kids("50.0"), "change_in_debt": node(chg), "identified_flows": node(idf),
            "primary_balance": kids(pb), "automatic_debt_dynamics": kids(ad),
            "other_identified_flows": kids(oth), "residual": kids(res)}


def audit(*cols):
    return {"column_header_audit": {"columns": [
        {"position": i + 1, "year_label": y, "group_label": None, "status": s, "status_basis": ""}
        for i, (y, s) in enumerate(cols)]}}


def target(year=2016, label="2016", status="actual", header="Actual 2016", **kw):
    t = {"target_year": year, "column_found": True, "matched_year_label": label, "column_status": status,
         "column_header_verbatim": header, "extractable": True, "not_extractable_reason": None,
         "decomposition": decomp(), "unmapped_rows": [], "notes": ""}
    t.update(kw)
    return t


GOOD_SRC = audit(("2015", "actual"), ("2016", "actual"), ("2017", "actual"), ("2018", "projection"))


def test_candidates():
    reps = [
        rep("A_2018-03-01.pdf", "A", "2018-03-01"), rep("A_2018-11-05.pdf", "A", "2018-11-05"),
        rep("A_2019-06-01.pdf", "A", "2019-06-01"), rep("A_2020-06-01.pdf", "A", "2020-06-01"),
        rep("B_2018-01-01.pdf", "B", "2018-01-01"),
    ]
    idx = core.index_by_country_year(reps)
    c = core.build_candidates("A", 2016, idx, set())
    assert [x["pdf_file_name"] for x in c] == ["A_2018-11-05.pdf", "A_2018-03-01.pdf", "A_2019-06-01.pdf"], c
    assert [x["offset"] for x in c] == [2, 2, 3]
    c = core.build_candidates("A", 2016, idx, {"A_2018-11-05.pdf"})
    assert [x["pdf_file_name"] for x in c][0] == "A_2018-03-01.pdf"
    assert core.build_candidates("A", 2017, idx, set())[0]["pdf_file_name"] == "A_2019-06-01.pdf"
    assert core.build_candidates("A", 2015, idx, set()) [-1]["offset"] == 3  # 2018 reports at T+3, none at T+2
    assert core.build_candidates("A", 2010, idx, set()) == []  # no T+4 fallback


def test_country_from_filename():
    r = core.parse_report_file(Path("Republic of Armenia_2019-06-05.pdf"))
    assert r["country"] == "Armenia" and r["year"] == 2019
    assert core.parse_report_file(Path("Maldives_2019-09-03_CR2019-283.pdf"))["date"] == "2019-09-03"


def test_validate():
    st, e, w = core.validate_target(target(), GOOD_SRC)
    assert st == "resolved" and not e, (st, e)

    st, e, _ = core.validate_target(target(status="projection", header="Proj. 2016"), audit(("2016", "projection")))
    assert st == "rejected_not_actual"

    # header text says Prel. although the model says actual -> hard reject
    st, e, _ = core.validate_target(target(header="Prel. 2016"), GOOD_SRC)
    assert st == "rejected_not_actual" and any(c == "header_text" for c, _ in e), e

    # model's own audit missing the year -> independent audit needed
    st, e, _ = core.validate_target(target(), audit(("2015", "actual"), ("2017", "actual")))
    assert st == "needs_independent_audit", (st, e)

    # audit disagrees with model (audit says estimate)
    st, e, _ = core.validate_target(target(), audit(("2016", "estimate")))
    assert st == "needs_independent_audit"

    # status order violated: an earlier year is a projection
    st, e, _ = core.validate_target(target(), audit(("2015", "projection"), ("2016", "actual")))
    assert st == "rejected_not_actual" and any(c == "monotonic" for c, _ in e)

    # wrong year label
    st, e, _ = core.validate_target(target(label="2017"), GOOD_SRC)
    assert st == "rejected_not_actual"

    # fiscal-year label 2015/16 counts as 2016
    st, e, _ = core.validate_target(target(label="2015/16", header="Actual 2015/16"), audit(("2015/16", "actual")))
    assert st == "resolved", (st, e)

    # no values
    t = target(); t["decomposition"] = decomp(chg=None, idf=None, res=None, pb=None, ad=None, oth=None)
    st, e, _ = core.validate_target(t, GOOD_SRC)
    assert st == "rejected_not_actual" and any(c == "no_values" for c, _ in e)

    # not extractable reasons
    for reason, expect in [("year_not_in_table", "year_not_in_table"), ("year_only_in_merged_range", "merged_range_only"),
                           ("column_is_projection", "rejected_not_actual"), ("column_is_estimate", "rejected_not_actual"),
                           ("values_unreadable", "values_unreadable")]:
        st, _, _ = core.validate_target({"target_year": 2016, "extractable": False, "not_extractable_reason": reason}, GOOD_SRC)
        assert st == expect, (reason, st)

    # identity warning does not block
    t = target(); t["decomposition"] = decomp(chg="5.0")
    st, e, w = core.validate_target(t, GOOD_SRC)
    assert st == "resolved" and any("identity" in x for x in w)


def test_audit_confirms():
    assert core.audit_confirms(audit(("2015", "actual"), ("2016", "historical")), 2016)[0]
    assert not core.audit_confirms(audit(("2016", "estimate")), 2016)[0]
    assert not core.audit_confirms(audit(("2002-2010", "actual")), 2006)[0]
    assert not core.audit_confirms(audit(("2015", "projection"), ("2016", "actual")), 2016)[0]


def test_flatten():
    rows = core.flatten_decomposition(decomp())
    ids = {(r["top_category"], r["hierarchy_id"]) for r in rows}
    assert ("change_in_debt", "1") in ids and ("primary_balance", "3.1") in ids and ("residual", "6.1") in ids
    assert not any(r["top_category"] == "debt_level" for r in rows)


def test_cascade():
    reps = [
        rep("A_2018-03-01.pdf", "A", "2018-03-01"), rep("A_2018-11-05.pdf", "A", "2018-11-05"),
        rep("A_2019-06-01.pdf", "A", "2019-06-01"),
        rep("B_2019-01-01.pdf", "B", "2019-01-01"), rep("B_2020-01-01.pdf", "B", "2020-01-01"),
        rep("C_2019-01-01.pdf", "C", "2019-01-01"), rep("C_2020-01-01.pdf", "C", "2020-01-01"),
        rep("D_2019-01-01.pdf", "D", "2019-01-01"),
        rep("E_2018-01-01.pdf", "E", "2018-01-01"),
    ]
    idx = core.index_by_country_year(reps)
    calls = []

    def ok(extra=None):
        return {"status": "resolved", "errors": [], "warnings": [], "decomposition": decomp(), "meta": {}, **(extra or {})}

    def bad(status):
        return {"status": status, "errors": [status], "warnings": []}

    plan = {
        # A 2016: latest T+2 report rejected, earlier T+2 report resolves
        ("A_2018-11-05.pdf", 2016): bad("rejected_not_actual"), ("A_2018-03-01.pdf", 2016): ok(),
        # B 2016: T+2 (2018) none; T+3 (2019) resolves.  B 2017: T+2 2019 fails, T+3 2020 resolves
        ("B_2019-01-01.pdf", 2016): ok(), ("B_2019-01-01.pdf", 2017): bad("year_not_in_table"), ("B_2020-01-01.pdf", 2017): ok(),
        # C 2016: T+3 fails -> unresolved (no T+4)
        ("C_2019-01-01.pdf", 2016): bad("rejected_not_actual"),
        # D 2016: API error stops the cascade
        ("D_2019-01-01.pdf", 2016): bad("api_error"),
    }

    def process(report, years):
        calls.append((report["pdf_file_name"], tuple(years)))
        return {y: plan[(report["pdf_file_name"], y)] for y in years}

    items = [
        {"gap_id": "G1", "country": "A", "gap_year": 2016},
        {"gap_id": "G2", "country": "B", "gap_year": 2016}, {"gap_id": "G3", "country": "B", "gap_year": 2017},
        {"gap_id": "G4", "country": "C", "gap_year": 2016},
        {"gap_id": "G5", "country": "D", "gap_year": 2016},
        {"gap_id": "G6", "country": "E", "gap_year": 2010},
    ]
    state = core.run_cascade(items, lambda c, y: core.build_candidates(c, y, idx, set()), process, max_workers=1, log=lambda s: None)
    fin = {s["gap_id"]: s["final_status"] for s in state}
    assert fin == {"G1": "resolved", "G2": "resolved", "G3": "resolved", "G4": "unresolved",
                   "G5": "pending_api_error", "G6": "unresolved_no_candidate_reports"}, fin
    src = {s["gap_id"]: s["resolved"]["report"] for s in state if s["resolved"]}
    assert src == {"G1": "A_2018-03-01.pdf", "G2": "B_2019-01-01.pdf", "G3": "B_2020-01-01.pdf"}, src
    # B_2019 serves G2 (as its first choice) and G3 (as its first choice): one call, both years
    assert ("B_2019-01-01.pdf", (2016, 2017)) in calls, calls
    assert [s for s in state if s["gap_id"] == "G4"][0]["attempts"][-1]["offset"] == 3

    with tempfile.TemporaryDirectory() as d:
        meta = pd.DataFrame([{"country": "A", "gap_year": 2016, "audit_fill_status": "x", "audit_expected_source_report": "A_2018-03-01.pdf"}])
        panel = pd.DataFrame([{"country": "A", "year": 2016, "status": "GAP", "source_report": None, **{c: None for c in core.PANEL_ROLES}},
                              {"country": "A", "year": 2017, "status": "observed", "source_report": "z.pdf", **{c: 1.0 for c in core.PANEL_ROLES}}])
        pp = Path(d) / "panel.csv"; panel.to_csv(pp, index=False)
        paths = core.write_outputs(state, meta, Path(d), "t", pp)
        res = pd.read_csv(paths["gapfill_resolution"])
        assert res.loc[res.gap_id == "G1", "source_matches_audit_expectation"].iloc[0] == True  # noqa: E712
        filled = pd.read_csv(paths["panel_structure_filled"])
        assert filled.loc[filled.year == 2016, "status"].iloc[0] == "FILLED"
        assert filled.loc[filled.year == 2016, "change_in_debt"].iloc[0] == 1.0
        assert filled.loc[filled.year == 2017, "status"].iloc[0] == "observed"


# ----------------------------------------- selected PDF lookup and the processor
def touch(path, size=10):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def test_selected_name_parsing():
    assert run.core.parse_selected_name("Angola_2017-02-06_pages_45_49.pdf") == ("Angola_2017-02-06", "selected_pdf_direct")
    assert run.core.parse_selected_name("Angola_2017-02-06_pages_45_49_image_compressed.pdf")[1] == "selected_pdf_image_compressed"
    assert run.core.parse_selected_name("Angola_2017-02-06_page_47_table_crop_fallback.pdf")[1] == "pymupdf_pillow_table_crop_fallback"
    assert run.core.parse_selected_name("Angola_2017-02-06_pages_45_49_vision_fallback.pdf")[1] == "pymupdf_pillow_visual_fallback"
    assert run.core.parse_selected_name("Angola_2017-02-06_timing.json") is None
    # any other suffix still maps to the right report
    assert run.core.parse_selected_name("Angola_2017-02-06_pages_45_49_v2_final.pdf") == ("Angola_2017-02-06", "selected_pdf_direct")
    assert run.core.parse_selected_name("Angola_2017-02-06.pdf") == ("Angola_2017-02-06", "selected_pdf_direct")
    assert run.core.parse_selected_name("Angola_2017-02-06_selected.PDF") == ("Angola_2017-02-06", "selected_pdf_direct")
    assert run.core.parse_selected_name("Angola_2017-02-06_p47_cropped.pdf")[1] == "pymupdf_pillow_table_crop_fallback"
    # names with a Country Report number keep it in the stem; names with several words / an apostrophe work too
    assert run.core.parse_selected_name("Maldives_2019-09-03_CR2019-283_pages_5_8.pdf") == ("Maldives_2019-09-03_CR2019-283", "selected_pdf_direct")
    assert run.core.parse_selected_name("Maldives_2019-09-03_pages_5_8.pdf")[0] == "Maldives_2019-09-03"
    assert run.core.parse_selected_name("Democratic Republic of São Tomé and Príncipe_2017-12-18_pages_3_6.pdf")[0] == "Democratic Republic of São Tomé and Príncipe_2017-12-18"
    assert run.core.parse_selected_name("Kingdom of the Netherlands—Aruba_2019-06-05_page_8_table_crop_fallback.pdf")[0] == "Kingdom of the Netherlands—Aruba_2019-06-05"
    assert run.core.parse_selected_name("notes.pdf") is None


def test_selected_pdf_resolution():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        rerun, orig = d / "rerun" / "selected_pdf_pages", d / "orig" / "selected_pdf_pages"
        # A: timing.json in the original batch says the crop was sent, although a direct PDF also exists
        touch(orig / "A_2018-03-01_pages_5_8.pdf"); touch(orig / "A_2018-03-01_page_6_table_crop_fallback.pdf")
        (d / "orig" / "A_2018-03-01_timing.json").write_text(json.dumps({
            "pdf_sent_to_api": "C:\\Users\\x\\out\\selected_pdf_pages\\A_2018-03-01_page_6_table_crop_fallback.pdf",
            "extraction_method": "pymupdf_pillow_table_crop_fallback", "selected_original_pages": [6],
            "vision_fallback_dpi": 240, "vision_fallback_jpeg_quality": 92, "table_crop_box_points": [1, 2, 3, 4]}))
        # B: no timing.json -> best fidelity by file name
        touch(orig / "B_2019-01-01_page_6_table_crop_fallback.pdf"); touch(orig / "B_2019-01-01_pages_5_8_image_compressed.pdf")
        # C: exists in both folders; the re-run folder is listed first and wins
        touch(rerun / "C_2019-01-01_pages_9_12.pdf"); touch(orig / "C_2019-01-01_pages_5_8.pdf")
        # D: timing.json in the "json_output" folder next to selected_pdf_pages (current layout)
        cur = d / "cur" / "selected_pdf_pages"
        touch(cur / "D_2019-01-01_pages_5_8.pdf"); touch(cur / "D_2019-01-01_page_6_table_crop_fallback.pdf")
        (d / "cur" / "json_output").mkdir(parents=True)
        (d / "cur" / "json_output" / "D_2019-01-01_timing.json").write_text(json.dumps({
            "pdf_sent_to_api": str(cur / "D_2019-01-01_page_6_table_crop_fallback.pdf"), "extraction_method": "pymupdf_pillow_table_crop_fallback",
            "selected_original_pages": [6]}))
        idx = run.core.index_selected_pdfs([rerun, orig, cur])
        dd = run.resolve_selected_pdf("D_2019-01-01", idx)
        assert dd["source"] == "timing" and dd["path"].name.endswith("table_crop_fallback.pdf") and dd["pages"] == [6], dd
        a = run.resolve_selected_pdf("A_2018-03-01", idx)
        assert a["source"] == "timing" and a["path"].name.endswith("table_crop_fallback.pdf") and a["pages"] == [6] and a["box"] == [1, 2, 3, 4]
        b = run.resolve_selected_pdf("B_2019-01-01", idx)
        assert b["source"] == "filename" and b["method"] == "selected_pdf_image_compressed" and b["pages"] is None
        c = run.resolve_selected_pdf("C_2019-01-01", idx)
        assert c["path"].parent == rerun, c
        assert run.resolve_selected_pdf("nope_2019-01-01", idx) is None
        reports = run.core.reports_from_selected(idx)
        assert {r["pdf_file_name"] for r in reports} == {"A_2018-03-01.pdf", "B_2019-01-01.pdf", "C_2019-01-01.pdf", "D_2019-01-01.pdf"}
        assert {r["country"] for r in reports} == {"A", "B", "C", "D"}


class FakeStep1:
    def __init__(self, answers, fail_with=None, locator_answer=None):
        self.answers, self.api_calls, self.fail_with, self.last_text = answers, [], fail_with, ""
        self.locator_answer = locator_answer
        self.PdfReader = lambda p: type("FakePdfReader", (), {"pages": [None] * 20})()

    def add_table_crop_header_instruction(self, text, method): return text

    def call_pdf_json(self, url, tm, model, prompt, user_text, pdf_path):
        if self.fail_with:
            raise RuntimeError(self.fail_with)
        self.api_calls.append("audit" if "INDEPENDENT HEADER AUDIT" in prompt else "extract")
        self.last_text = user_text
        return self.answers["audit"] if "INDEPENDENT HEADER AUDIT" in prompt else self.answers["extract"]

    # ---- Step 1 locate machinery, used only by the fresh-locate fallback (no cached selected PDF)
    def extract_full_text(self, pdf_path):
        return "full text of " + pdf_path.name, ["page one", "page two"]

    def prepare_step1_input(self, full_text, name):
        return full_text

    def keyword_candidates(self, pages):
        return []

    def call_text_json(self, url, tm, model, prompt, user_input):
        self.api_calls.append("locate")
        return self.locator_answer

    def create_uploadable_subset(self, pdf_path, out_path, start_page, end_page, primary_page):
        touch(out_path)
        return list(range(start_page, end_page + 1)), []


def test_processor_end_to_end():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        run.OUTPUT_DIR = d / "out"
        sel_dir = d / "step1" / "selected_pdf_pages"
        touch(sel_dir / "A_2018-03-01_pages_5_8.pdf")
        (d / "step1" / "A_2018-03-01_timing.json").write_text(json.dumps({
            "pdf_sent_to_api": str(sel_dir / "A_2018-03-01_pages_5_8.pdf"), "extraction_method": "selected_pdf_direct",
            "selected_original_pages": [5, 6, 7, 8]}))
        idx = run.core.index_selected_pdfs([sel_dir])
        report = {"pdf_file_name": "A_2018-03-01.pdf", "country": "A", "date": "2018-03-01", "year": 2018}

        extract = {
            "table_found": True,
            "source": {"framework": "MAC_DSA", "column_header_audit": audit(("2015", "actual"), ("2016", "actual"), ("2017", "estimate"), ("2018", "projection"))["column_header_audit"]},
            "targets": [
                target(2016),                                                     # good
                target(2017, "2017", "actual", "Actual 2017"),                    # model says actual, its audit says estimate
                {"target_year": 2014, "extractable": False, "not_extractable_reason": "year_not_in_table"},
            ],
        }
        s1 = FakeStep1({"extract": extract, "audit": audit(("2017", "estimate"))})
        proc = run.ReportProcessor(s1, "u", None, "m", "prompt", idx)
        out = proc(report, [2014, 2016, 2017])
        assert out[2016]["status"] == "resolved" and out[2016]["decomposition"]
        assert out[2017]["status"] == "rejected_not_actual" and out[2017]["decomposition"] is None
        assert out[2014]["status"] == "year_not_in_table"
        assert s1.api_calls == ["extract", "audit"], s1.api_calls
        assert "Selected PDF page 1 = original physical PDF page 5" in s1.last_text  # mapping from timing.json is passed on

        # resume: same request again must not call the API
        s1.api_calls.clear()
        out2 = proc(report, [2014, 2016, 2017])
        assert s1.api_calls == [] and out2[2016]["status"] == "resolved"
        co = run.cache_only_process(report, [2016, 2099])
        assert co[2016]["status"] == "resolved" and co[2099]["status"] == "not_run"

        # independent audit rescues a year the model's own audit table omitted
        (d / "out" / "reports" / "A_2018-03-01_gapfill.json").unlink()
        extract["source"]["column_header_audit"] = audit(("2015", "actual"))["column_header_audit"]
        s1.answers["audit"] = audit(("2015", "actual"), ("2016", "historical"))
        assert proc(report, [2016])[2016]["status"] == "resolved_with_warning"

        # no selected PDF for this report -> non-stopping status, no API call
        s1.api_calls.clear()
        rb = {"pdf_file_name": "B_2019-01-01.pdf", "country": "B", "date": "2019-01-01", "year": 2019}
        assert proc(rb, [2016])[2016]["status"] == "selected_pdf_not_found" and s1.api_calls == []

        # request too large for the gateway -> pdf_too_large (cascade moves on), other errors -> api_error (cascade stops)
        touch(sel_dir / "C_2019-01-01_pages_5_8.pdf"); idx.update(run.core.index_selected_pdfs([sel_dir]))
        rc = {"pdf_file_name": "C_2019-01-01.pdf", "country": "C", "date": "2019-01-01", "year": 2019}
        big = run.ReportProcessor(FakeStep1({}, fail_with="The complete encoded request is 1,200,000 bytes, which is too close to or above the 1 MB gateway limit"), "u", None, "m", "p", idx)
        assert big(rc, [2016])[2016]["status"] == "pdf_too_large"
        (d / "out" / "reports" / "C_2019-01-01_gapfill.json").unlink()
        bad = run.ReportProcessor(FakeStep1({}, fail_with="API error 500"), "u", None, "m", "p", idx)
        assert bad(rc, [2016])[2016]["status"] == "api_error"
        assert "pdf_too_large" not in core.STOP_STATUSES and "api_error" in core.STOP_STATUSES


def test_processor_fresh_locate_fallback():
    """
    The new behaviour this session added: when resolve_selected_pdf() finds no cache for a candidate
    report, ReportProcessor locates it fresh from the original PDF (report["path"]) using 1a's own
    locate machinery, instead of giving up with selected_pdf_not_found. A second gap year for the same
    report must reuse the cached fresh selection rather than locating it twice.
    """
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        run.OUTPUT_DIR = d / "out"
        original_pdf = d / "originals" / "E_2019-05-01.pdf"
        touch(original_pdf)
        report = {"pdf_file_name": "E_2019-05-01.pdf", "country": "E", "date": "2019-05-01", "year": 2019,
                  "path": str(original_pdf)}

        extract = {
            "table_found": True,
            "source": {"framework": "MAC_DSA", "column_header_audit": audit(("2016", "actual"))["column_header_audit"]},
            "targets": [target(2016)],
        }
        locator_answer = {"dsa_section_found": True, "recommended_start_page": 3, "recommended_end_page": 5,
                           "primary_table_page": 4, "notes": ""}
        s1 = FakeStep1({"extract": extract, "audit": audit(("2016", "actual"))}, locator_answer=locator_answer)
        idx = {}  # empty: no cached selected PDF anywhere for this report
        fresh_dir = d / "out" / "fresh_selected_pdf"
        proc = run.ReportProcessor(s1, "u", None, "m", "prompt", idx, prompt1="locator prompt", fresh_dir=fresh_dir)

        out = proc(report, [2016])
        assert out[2016]["status"] == "resolved" and out[2016]["decomposition"]
        assert s1.api_calls == ["locate", "extract"], s1.api_calls
        selected_files = list(fresh_dir.glob("E_2019-05-01_pages_*.pdf"))
        assert len(selected_files) == 1, selected_files

        # a second gap year for the same report must reuse the fresh selection, not locate again
        s1.api_calls.clear()
        (d / "out" / "reports" / "E_2019-05-01_gapfill.json").unlink()
        extract["targets"] = [target(2017, "2017", "actual", "Actual 2017")]
        extract["source"]["column_header_audit"] = audit(("2017", "actual"))["column_header_audit"]
        out2 = proc(report, [2017])
        assert out2[2017]["status"] == "resolved"
        assert s1.api_calls == ["extract"], s1.api_calls  # no second "locate"

        # Step 1 finds no DSA section at all -> no_dsa_table_in_source, not selected_pdf_not_found
        no_table_pdf = d / "originals" / "F_2019-05-01.pdf"
        touch(no_table_pdf)
        s1_none = FakeStep1({"extract": {}, "audit": {}}, locator_answer={"dsa_section_found": False, "notes": "no DSA"})
        proc_none = run.ReportProcessor(s1_none, "u", None, "m", "prompt", {}, prompt1="locator prompt", fresh_dir=fresh_dir)
        report_f = {"pdf_file_name": "F_2019-05-01.pdf", "country": "F", "date": "2019-05-01", "year": 2019,
                    "path": str(no_table_pdf)}
        out3 = proc_none(report_f, [2016])
        assert out3[2016]["status"] == "no_dsa_table_in_source"

        # report that genuinely does not exist on disk at all (not even an original PDF) -> selected_pdf_not_found
        report_missing = {"pdf_file_name": "G_2019-05-01.pdf", "country": "G", "date": "2019-05-01", "year": 2019,
                           "path": str(d / "originals" / "G_2019-05-01.pdf")}
        out4 = proc_none(report_missing, [2016])
        assert out4[2016]["status"] == "selected_pdf_not_found"


def test_candidate_map_rows():
    idx = {
        ("Angola", 2017): [
            {"pdf_file_name": "Angola_2017-03-01.pdf", "date": "2017-03-01"},
            {"pdf_file_name": "Angola_2017-09-01.pdf", "date": "2017-09-01"},  # later in the same year -> ranks first
        ],
        ("Angola", 2018): [{"pdf_file_name": "Angola_2018-06-01.pdf", "date": "2018-06-01"}],
    }
    gap_items = [
        {"gap_id": "G0001", "country": "Angola", "gap_year": 2015},  # T+2=2017 (2 candidates), T+3=2018
        {"gap_id": "G0002", "country": "Angola", "gap_year": 2030},  # no candidate at all
    ]
    rows = core.build_candidate_map_rows(gap_items, idx, skip=set())
    assert rows[0]["candidate_report"] == "Angola_2017-09-01.pdf" and rows[0]["rank"] == 1
    assert rows[1]["candidate_report"] == "Angola_2017-03-01.pdf" and rows[1]["rank"] == 2
    assert rows[2]["candidate_report"] == "Angola_2018-06-01.pdf" and rows[2]["offset_years"] == 3
    assert rows[3]["rank"] is None and rows[3]["candidate_report"] is None


def test_3b_candidate_map_end_to_end():
    """Candidate exists both as a real PDF under STAFF_REPORTS_DIR and as an already-cached selected PDF."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        check_dir = d / "gap_year_check"; check_dir.mkdir()
        stamp = "test1"
        gaps = pd.DataFrame([{"gap_id": "G0001", "country": "Angola", "gap_year": 2015, "gap_span": "2015",
                               "primary_cause": "lag_between_consecutive_reports",
                               "fill_status": "fillable_actual_column_visible",
                               "preferred_source_report": "Angola_2017-09-01.pdf"}])
        gaps.to_csv(check_dir / f"gap_years_{stamp}.csv", index=False)
        inv = pd.DataFrame([
            {"pdf_file_name": "Angola_2010-01-01.pdf", "report_status": "no_table"},
            {"pdf_file_name": "Angola_2017-09-01.pdf", "report_status": "observation"},
        ])
        inv.to_csv(check_dir / f"report_inventory_{stamp}.csv", index=False)
        staff_dir = d / "staff_reports" / "2016-2020"; staff_dir.mkdir(parents=True)
        (staff_dir / "Angola_2017-09-01.pdf").write_bytes(b"%PDF-1.4 fake original")
        sel_dir = d / "selected_pdf_pages"; sel_dir.mkdir()
        (sel_dir / "Angola_2017-09-01_pages_5_8.pdf").write_bytes(b"%PDF-1.4 fake selected")

        three_b.main(check_dir=check_dir, stamp=stamp, staff_reports_dir=d / "staff_reports", selected_pdf_dirs=[sel_dir])

        cmap = pd.read_csv(check_dir / f"gapfill_candidate_map_{stamp}.csv")
        assert len(cmap) == 1 and cmap.iloc[0]["candidate_report"] == "Angola_2017-09-01.pdf"
        assert bool(cmap.iloc[0]["has_cached_selected_pdf"]) is True
        assert (check_dir / f"gapfill_targets_{stamp}.csv").exists()
        assert (check_dir / f"gapfill_skip_reports_{stamp}.csv").exists()

        targets = pd.read_csv(check_dir / f"gapfill_targets_{stamp}.csv")
        assert bool(targets.iloc[0]["has_candidate_report"]) is True
        assert bool(targets.iloc[0]["audit_vs_real_candidate_mismatch"]) is False


def test_3b_candidate_exists_but_no_cache():
    """
    The common case once candidates come from STAFF_REPORTS_DIR rather than SELECTED_PDF_DIRS: the real
    PDF exists, but Step 1 never produced a selected PDF for it in any run that is configured. This is
    NOT flagged as a mismatch -- Step 3 handles it by locating the table fresh -- but gapfill_candidate_map
    must show has_cached_selected_pdf=False so the cost (one extra locator call) is visible up front.
    """
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        check_dir = d / "gap_year_check"; check_dir.mkdir()
        stamp = "test1"
        gaps = pd.DataFrame([{"gap_id": "G0001", "country": "Armenia", "gap_year": 2017, "gap_span": "2017",
                               "primary_cause": "lag_between_consecutive_reports",
                               "fill_status": "fillable_actual_column_visible",
                               "preferred_source_report": "Armenia_2019-06-05.pdf"}])
        gaps.to_csv(check_dir / f"gap_years_{stamp}.csv", index=False)
        inv = pd.DataFrame([{"pdf_file_name": "Armenia_2019-06-05.pdf", "report_status": "observation"}])
        inv.to_csv(check_dir / f"report_inventory_{stamp}.csv", index=False)
        staff_dir = d / "staff_reports" / "2016-2020"; staff_dir.mkdir(parents=True)
        (staff_dir / "Armenia_2019-06-05.pdf").write_bytes(b"%PDF-1.4 fake original")
        sel_dir = d / "selected_pdf_pages"; sel_dir.mkdir()  # empty: no cached selection anywhere

        three_b.main(check_dir=check_dir, stamp=stamp, staff_reports_dir=d / "staff_reports", selected_pdf_dirs=[sel_dir])

        targets = pd.read_csv(check_dir / f"gapfill_targets_{stamp}.csv")
        assert bool(targets.iloc[0]["has_candidate_report"]) is True
        assert bool(targets.iloc[0]["audit_vs_real_candidate_mismatch"]) is False
        cmap = pd.read_csv(check_dir / f"gapfill_candidate_map_{stamp}.csv")
        assert bool(cmap.iloc[0]["has_cached_selected_pdf"]) is False


def test_3b_audit_vs_real_candidate_mismatch():
    """
    The predicted report cannot be found as a real PDF under STAFF_REPORTS_DIR at all (e.g. a parsing
    mismatch, or it genuinely is not among the batches scanned) -- the one case still worth flagging,
    since no fresh locate is possible without a real PDF to locate it from.
    """
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        check_dir = d / "gap_year_check"; check_dir.mkdir()
        stamp = "test1"
        gaps = pd.DataFrame([{"gap_id": "G0001", "country": "Armenia", "gap_year": 2017, "gap_span": "2017",
                               "primary_cause": "lag_between_consecutive_reports",
                               "fill_status": "fillable_actual_column_visible",
                               "preferred_source_report": "Armenia_2019-06-05.pdf"}])
        gaps.to_csv(check_dir / f"gap_years_{stamp}.csv", index=False)
        inv = pd.DataFrame([{"pdf_file_name": "Armenia_2019-06-05.pdf", "report_status": "observation"}])
        inv.to_csv(check_dir / f"report_inventory_{stamp}.csv", index=False)
        staff_dir = d / "staff_reports" / "2016-2020"; staff_dir.mkdir(parents=True)  # empty: no real PDF at all
        sel_dir = d / "selected_pdf_pages"; sel_dir.mkdir()

        three_b.main(check_dir=check_dir, stamp=stamp, staff_reports_dir=d / "staff_reports", selected_pdf_dirs=[sel_dir])

        targets = pd.read_csv(check_dir / f"gapfill_targets_{stamp}.csv")
        assert bool(targets.iloc[0]["has_candidate_report"]) is False
        assert bool(targets.iloc[0]["audit_vs_real_candidate_mismatch"]) is True


def test_3a_same_real_report_two_years():
    """
    The case the (json_file, last_actual_year) dedup fix exists for: one real report can legitimately
    carry two row-groups once gap-fill output is folded back in -- its own normal extraction at its own
    last_actual_year, and a gap-fill row-group at an earlier year it was also used to source. Before the
    fix, grouping by json_file alone silently collapsed the two years into one.
    """
    cols = ["json_file", "pdf_file_name", "table_found", "last_actual_year", "level", "top_category", "value",
            "hierarchy_id", "parent_label", "label_verbatim", "column_header_audit_json",
            "manual_review_required", "actual_column_validation_status", "confidence", "framework"]
    roles = ["change_in_debt", "identified_flows", "primary_balance", "automatic_debt_dynamics",
             "other_identified_flows", "residual"]

    def mkrow(json_file, pdf, year, top_cat, value):
        r = dict.fromkeys(cols, "")
        r.update(json_file=json_file, pdf_file_name=pdf, table_found="TRUE", last_actual_year=year,
                 level="0", top_category=top_cat, value=value, hierarchy_id="1",
                 manual_review_required="No", actual_column_validation_status="accepted",
                 confidence="high", framework="MAC_DSA")
        return r

    rows = []
    for i, role in enumerate(roles, start=1):
        rows.append(mkrow("France_2021-05-01_dsa.json", "France_2021-05-01.pdf", "2021", role, str(10 + i)))
    for i, role in enumerate(roles, start=1):  # same real report, also used to source a gap-fill year
        rows.append(mkrow("France_2021-05-01_dsa.json", "France_2021-05-01.pdf", "2019", role, str(20 + i)))
    for i, role in enumerate(roles, start=1):
        rows.append(mkrow("France_2017-05-01_dsa.json", "France_2017-05-01.pdf", "2017", role, str(30 + i)))
    df = pd.DataFrame(rows)

    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        csv_path = d / "input.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        out_dir = d / "out"
        three_a.main(csv_path, out_dir)

        panel = pd.read_csv(out_dir / f"panel_structure_country_year_{three_a.STAMP}.csv")
        inv = pd.read_csv(out_dir / f"report_inventory_{three_a.STAMP}.csv")
        fr = panel[panel["country"] == "France"].sort_values("year")

        assert set(fr["year"]) >= {2017, 2019, 2021}
        assert (fr[fr["year"] == 2021]["status"] == "observed").all()
        assert (fr[fr["year"] == 2019]["status"] == "observed").all(), "2019 must be 'observed', not GAP"
        assert fr[fr["year"] == 2021]["change_in_debt"].iloc[0] == 11.0
        assert fr[fr["year"] == 2019]["change_in_debt"].iloc[0] == 21.0, "2019 and 2021 values must not collapse together"
        assert (inv["pdf_file_name"] == "France_2021-05-01.pdf").sum() == 2, "the shared report appears once per year it supplies"


def test_3a_cross_batch_edge_gap():
    """
    A gap sitting at a batch's edge is invisible from that batch alone: find_gap_years() only flags a
    year "missing in the middle" of a country's observed years, and a single batch's last observed year
    has nothing after it to call "the middle." Passing the next batch's CSV too (as a list) must make
    the edge gap visible, without having to hand-merge the files first.
    """
    cols = ["json_file", "pdf_file_name", "table_found", "last_actual_year", "level", "top_category", "value",
            "hierarchy_id", "parent_label", "label_verbatim", "column_header_audit_json",
            "manual_review_required", "actual_column_validation_status", "confidence", "framework"]
    roles = ["change_in_debt", "identified_flows", "primary_balance", "automatic_debt_dynamics",
             "other_identified_flows", "residual"]

    def mkrow(json_file, pdf, year, top_cat, value):
        r = dict.fromkeys(cols, "")
        r.update(json_file=json_file, pdf_file_name=pdf, table_found="TRUE", last_actual_year=year,
                 level="0", top_category=top_cat, value=value, hierarchy_id="1",
                 manual_review_required="No", actual_column_validation_status="accepted",
                 confidence="high", framework="MAC_DSA")
        return r

    batch_a_rows = [mkrow("Spain_2019-05-01_dsa.json", "Spain_2019-05-01.pdf", "2018", role, "1.0") for role in roles]
    batch_b_rows = [mkrow("Spain_2023-05-01_dsa.json", "Spain_2023-05-01.pdf", "2022", role, "2.0") for role in roles]

    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        csv_a = d / "batch_a.csv"; pd.DataFrame(batch_a_rows).to_csv(csv_a, index=False, encoding="utf-8-sig")
        csv_b = d / "batch_b.csv"; pd.DataFrame(batch_b_rows).to_csv(csv_b, index=False, encoding="utf-8-sig")

        out_single = d / "out_single"
        three_a.main(csv_a, out_single)
        panel_single = pd.read_csv(out_single / f"panel_structure_country_year_{three_a.STAMP}.csv")
        sp_single = panel_single[panel_single["country"] == "Spain"]
        assert list(sp_single["year"]) == [2018] and list(sp_single["status"]) == ["observed"], \
            "with only one observed year there is no 'middle' at all -- Spain has just that one row, no GAP rows"

        out_both = d / "out_both"
        three_a.main([csv_a, csv_b], out_both)
        panel_both = pd.read_csv(out_both / f"panel_structure_country_year_{three_a.STAMP}.csv")
        sp = panel_both[panel_both["country"] == "Spain"].sort_values("year")
        assert list(sp["year"]) == [2018, 2019, 2020, 2021, 2022]
        assert list(sp["status"]) == ["observed", "GAP", "GAP", "GAP", "observed"], \
            "2019-2021 must now show as GAP once the next batch's 2022 observation makes them visible"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok  ", t.__name__)
    print(f"\nall {len(tests)} tests passed")
