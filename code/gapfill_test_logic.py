"""Offline tests for the gap-year fill logic. Run: python gapfill_test_logic.py"""
import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gapfill_lib_core as core  # noqa: E402
import gapfill_3_run_api as run  # noqa: E402


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


# ----------------------------------------- end-to-end with a fake Step 1 module
class FakePdfReader:
    def __init__(self, p): self.pages = [0] * 12


class FakeStep1:
    PdfReader = FakePdfReader

    def __init__(self, answers):
        self.answers, self.api_calls = answers, []

    def create_uploadable_subset(self, src, out, start, end, primary):
        out.write_bytes(b"%PDF fake"); return list(range(start, end + 1)), []

    def add_table_crop_header_instruction(self, text, method): return text

    def call_pdf_json(self, url, tm, model, prompt, user_text, pdf_path):
        self.api_calls.append("audit" if "INDEPENDENT HEADER AUDIT" in prompt else "extract")
        if "INDEPENDENT HEADER AUDIT" in prompt:
            return self.answers["audit"]
        return self.answers["extract"]


def test_processor_end_to_end():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        run.OUTPUT_DIR = d / "out"
        run.LOCATOR_DIRS = [d / "loc"]
        (d / "loc").mkdir()
        (d / "loc" / "A_2018-03-01_step1_locator.json").write_text(json.dumps(
            {"dsa_section_found": True, "recommended_start_page": 5, "recommended_end_page": 8, "primary_table_page": 6}))
        pdf = d / "A_2018-03-01.pdf"; pdf.write_bytes(b"x")
        report = {"pdf_file_name": pdf.name, "path": str(pdf), "country": "A", "date": "2018-03-01", "year": 2018}

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
        proc = run.ReportProcessor(s1, "u", None, "m", "prompt", "")
        out = proc(report, [2014, 2016, 2017])
        assert out[2016]["status"] == "resolved" and out[2016]["decomposition"]
        assert out[2017]["status"] == "rejected_not_actual" and out[2017]["decomposition"] is None
        assert out[2014]["status"] == "year_not_in_table"
        assert s1.api_calls == ["extract", "audit"], s1.api_calls

        # resume: same request again must not call the API
        s1.api_calls.clear()
        out2 = proc(report, [2014, 2016, 2017])
        assert s1.api_calls == [] and out2[2016]["status"] == "resolved"
        # cache-only collect
        co = run.cache_only_process(report, [2016, 2099])
        assert co[2016]["status"] == "resolved" and co[2099]["status"] == "not_run"

        # independent audit rescues a year the model's own audit table omitted
        (d / "out" / "reports" / "A_2018-03-01_gapfill.json").unlink()
        extract["source"]["column_header_audit"] = audit(("2015", "actual"))["column_header_audit"]
        s1.answers["audit"] = audit(("2015", "actual"), ("2016", "historical"))
        out3 = proc(report, [2016])
        assert out3[2016]["status"] == "resolved_with_warning", out3[2016]

        # a report with no DSA table
        (d / "loc" / "B_2019-01-01_step1_locator.json").write_text(json.dumps({"dsa_section_found": False}))
        rb = {"pdf_file_name": "B_2019-01-01.pdf", "path": str(d / "B_2019-01-01.pdf"), "country": "B", "date": "2019-01-01", "year": 2019}
        (d / "B_2019-01-01.pdf").write_bytes(b"x")
        assert proc(rb, [2016])[2016]["status"] == "no_dsa_table"
        # missing PDF
        rc = {"pdf_file_name": "C.pdf", "path": str(d / "nope.pdf"), "country": "C", "date": "2019-01-01", "year": 2019}
        assert proc(rc, [2016])[2016]["status"] == "pdf_not_found"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok  ", t.__name__)
    print(f"\nall {len(tests)} tests passed")
