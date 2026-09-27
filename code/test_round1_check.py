"""Offline tests for 1c_round_check_compare_runs.py. Run: python test_round1_check.py"""
import ast
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, List, Optional

import pandas as pd

HERE = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


chk = load(HERE / "1c_round_check_compare_runs.py", "round1_check")

COLS = ["json_file", "pdf_file_name", "country", "table_found", "last_actual_year", "confidence", "extraction_notes",
        "failure_reason", "top_category", "hierarchy_id", "level", "parent_label", "label_verbatim", "value"]


def report(stem, country, found=True, year="2016", items=(), confidence="high", failure=None, notes=""):
    """items: (hierarchy_id, top_category, label, value)."""
    base = {"json_file": f"{stem}_dsa.json", "pdf_file_name": f"{stem}.pdf", "country": country,
            "table_found": str(found), "last_actual_year": year if found else None, "confidence": confidence if found else None,
            "extraction_notes": notes, "failure_reason": failure}
    if not found:
        return [{**base, "top_category": None, "hierarchy_id": None, "level": None, "parent_label": None,
                 "label_verbatim": None, "value": None}]
    return [{**base, "top_category": top, "hierarchy_id": hid, "level": str(hid.count(".")), "parent_label": None,
             "label_verbatim": lab, "value": val} for hid, top, lab, val in items]


ITEMS = [("1", "change_in_debt", "Change in debt", "1.5"), ("2", "identified_flows", "Identified flows", "0.5"),
         ("3", "primary_balance", "Primary deficit", "-0.3"), ("3.1", "primary_balance", "Revenue", "20.1"),
         ("6", "residual", "Residual", "1.0")]


def make_runs():
    r1, r2, r3 = [], [], []
    # A: identical in substance; run 2 has other label spelling, number formats and confidence; run 3 has "-0.0" for a zero
    a_items = ITEMS + [("4", "automatic_debt_dynamics", "Automatic debt dynamics", "0.0")]
    r1 += report("A_2016-01-01", "A", items=a_items)
    r2 += report("A_2016-01-01", "A", items=[(h, t, l + " ." if h == "3" else l, {"1.5": "1.50", "0.5": "0.5"}.get(v, v)) for h, t, l, v in a_items], confidence="medium", notes="x")
    r3 += report("A_2016-01-01", "A", items=[(h, t, l, "-0.0" if v == "0.0" else v) for h, t, l, v in a_items])
    # B: one value differs in run 3
    r1 += report("B_2016-01-01", "B", items=ITEMS)
    r2 += report("B_2016-01-01", "B", items=ITEMS)
    r3 += report("B_2016-01-01", "B", items=[(h, t, l, "9.9" if h == "3.1" else v) for h, t, l, v in ITEMS])
    # C: run 2 reads an extra child row, so the ids after it shift
    c1 = [("4", "automatic_debt_dynamics", "ADD", "1.0"), ("4.1", "automatic_debt_dynamics", "Rate", "0.2"), ("4.2", "automatic_debt_dynamics", "Growth", "0.3")]
    c2 = [("4", "automatic_debt_dynamics", "ADD", "1.0"), ("4.1", "automatic_debt_dynamics", "Rate", "0.2"), ("4.2", "automatic_debt_dynamics", "Extra", "0.1"), ("4.3", "automatic_debt_dynamics", "Growth", "0.3")]
    r1 += report("C_2016-01-01", "C", items=ITEMS + c1); r2 += report("C_2016-01-01", "C", items=ITEMS + c2); r3 += report("C_2016-01-01", "C", items=ITEMS + c1)
    # D: run 3 picked another year (values equal by coincidence must NOT be kept)
    r1 += report("D_2016-01-01", "D", items=ITEMS); r2 += report("D_2016-01-01", "D", items=ITEMS); r3 += report("D_2016-01-01", "D", year="2015", items=ITEMS)
    # E: run 2 found no table
    r1 += report("E_2016-01-01", "E", items=ITEMS); r2 += report("E_2016-01-01", "E", found=False, failure="pages_unreadable"); r3 += report("E_2016-01-01", "E", items=ITEMS)
    # F: absent from run 3
    r1 += report("F_2016-01-01", "F", items=ITEMS); r2 += report("F_2016-01-01", "F", items=ITEMS)
    # G: no table in any run (different failure reasons)
    r1 += report("G_2016-01-01", "G", found=False, failure="dsa_pages_not_in_input"); r2 += report("G_2016-01-01", "G", found=False, failure="pages_unreadable"); r3 += report("G_2016-01-01", "G", found=False, failure="dsa_pages_not_in_input")
    # H: fiscal-year spellings of the same year
    r1 += report("H_2016-01-01", "H", year="2012/13", items=ITEMS); r2 += report("H_2016-01-01", "H", year="2013", items=ITEMS); r3 += report("H_2016-01-01", "H", year="FY2013", items=ITEMS)
    return [pd.DataFrame(r, columns=COLS) for r in (r1, r2, r3)]


def run_check(dfs, d, round_name="round1"):
    paths = []
    for i, df in enumerate(dfs, start=1):
        p = d / f"run{i}.csv"; df.to_csv(p, index=False, encoding="utf-8-sig"); paths.append(p)
    chk.RUN_CSVS = paths
    chk.CHECK_DIR = d / "check"
    chk.RUN_DATE = "20260101"
    chk.ROUND = round_name
    chk.main()
    return d / "check"


def test_groups_and_outputs():
    with tempfile.TemporaryDirectory() as d:
        out = run_check(make_runs(), Path(d))
        summ = pd.read_csv(out / "round1_check_report_summary_20260101.csv").set_index("pdf_file_name")
        grp = summ["group"].to_dict()
        assert grp == {"A_2016-01-01.pdf": "fully_match", "B_2016-01-01.pdf": "partial_match", "C_2016-01-01.pdf": "partial_match",
                       "D_2016-01-01.pdf": "last_actual_year_differs", "E_2016-01-01.pdf": "table_found_differs",
                       "F_2016-01-01.pdf": "missing_in_run", "G_2016-01-01.pdf": "no_table_in_all_runs",
                       "H_2016-01-01.pdf": "fully_match"}, grp
        assert (summ["needs_check"] == "No").sum() == 2

        # 1. fully match JSON
        fm = json.loads((out / "round1_check_fully_match_reports_20260101.json").read_text(encoding="utf-8"))
        assert fm["fully_match_reports"] == ["A_2016-01-01.pdf", "H_2016-01-01.pdf"] and fm["meta"]["n_fully_match"] == 2

        # 2. matched rows: all rows of A and H, the agreeing rows of B and C, nothing of D, E, F, G; same columns as the runs
        mr = pd.read_csv(out / "round1_check_matched_rows_20260101.csv", dtype=str)
        assert list(mr.columns) == COLS
        by = mr.groupby("json_file")["hierarchy_id"].apply(sorted).to_dict()
        assert set(by) == {"A_2016-01-01_dsa.json", "B_2016-01-01_dsa.json", "C_2016-01-01_dsa.json", "H_2016-01-01_dsa.json"}, by
        assert by["B_2016-01-01_dsa.json"] == ["1", "2", "3", "6"]                       # 3.1 differs
        assert by["C_2016-01-01_dsa.json"] == ["1", "2", "3", "3.1", "4", "4.1", "6"]      # 4.2 / 4.3 differ
        assert len(by["A_2016-01-01_dsa.json"]) == 6
        a_run1 = mr[mr.json_file == "A_2016-01-01_dsa.json"].set_index("hierarchy_id")
        assert a_run1.loc["1", "value"] == "1.5" and a_run1.loc["3", "label_verbatim"] == "Primary deficit"   # run 1's rows

        # 4. differing rows
        vd = pd.read_csv(out / "round1_check_value_diffs_20260101.csv")
        assert list(vd.columns) == ["key", "json_file", "pdf_file_name", "country", "top_category",
                                    "label_run1", "label_run2", "label_run3", "value_run1", "value_run2", "value_run3",
                                    "run1_run2_match", "run1_run3_match", "run2_run3_match", "all_match", "max_abs_diff", "diff_type"]
        b = vd[vd.pdf_file_name == "B_2016-01-01.pdf"]
        assert len(b) == 1 and b.iloc[0].diff_type == "value" and abs(b.iloc[0].max_abs_diff - 10.2) < 1e-9
        assert bool(b.iloc[0].run1_run2_match) and not bool(b.iloc[0].run1_run3_match)
        c = vd[vd.pdf_file_name == "C_2016-01-01.pdf"]
        assert set(c.key.str.split("||", regex=False).str[1]) == {"4.2", "4.3"}
        assert set(c.diff_type) == {"value", "missing_row"}
        d_rows = vd[vd.pdf_file_name == "D_2016-01-01.pdf"]
        assert len(d_rows) == 5 and set(d_rows.diff_type) == {"last_actual_year_differs"}
        assert d_rows.all_match.all()                                    # equal numbers, but listed because the year differs
        assert set(vd[vd.pdf_file_name == "E_2016-01-01.pdf"].diff_type) == {"table_found_differs"}
        f = vd[vd.pdf_file_name == "F_2016-01-01.pdf"]
        assert set(f.diff_type) == {"missing_in_run"} and f.value_run3.isna().all()
        assert not set(vd.pdf_file_name) & {"A_2016-01-01.pdf", "G_2016-01-01.pdf", "H_2016-01-01.pdf"}

        # every row of a partly matching report is in exactly one of the two files
        runs_now = make_runs()
        for stem in ("B_2016-01-01", "C_2016-01-01"):
            jf = f"{stem}_dsa.json"
            union = set().union(*[set(r[r.json_file == jf].hierarchy_id.dropna()) for r in runs_now])
            m = set(mr[mr.json_file == jf].hierarchy_id)
            x = set(vd[vd.pdf_file_name == f"{stem}.pdf"].key.str.split("||", regex=False).str[1])
            assert not m & x and m | x == union, (stem, m, x, union)

        # 3. disagreement JSON, read with the real loader of 2a
        dj = json.loads((out / "round1_check_disagreement_reports_20260101.json").read_text(encoding="utf-8"))
        assert dj["category_a_disagreement"]["count"] == 5 and dj["category_b_no_table_in_all_runs"]["count"] == 1
        loader = extract_loader()
        stems_all = loader(out / "round1_check_disagreement_reports_20260101.json", None)
        assert sorted(stems_all) == sorted(["B_2016-01-01", "C_2016-01-01", "D_2016-01-01", "E_2016-01-01", "F_2016-01-01", "G_2016-01-01"]), stems_all
        assert sorted(loader(out / "round1_check_disagreement_reports_20260101.json", "category_b_no_table_in_all_runs")) == ["G_2016-01-01"]
        assert "G_2016-01-01" not in loader(out / "round1_check_disagreement_reports_20260101.json", "category_a_disagreement")


def extract_loader():
    """The real load_target_report_stems of 2a, pulled out of the file without importing the whole script."""
    src = (HERE / "2a_step_1_revised_on_problematic_reports_sl.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "load_target_report_stems")
    ns = {"json": json, "Path": Path, "Optional": Optional, "List": List, "Any": Any}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "2a_loader", "exec"), ns)
    return ns["load_target_report_stems"]


def test_two_runs_and_guards():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        runs = make_runs()[:2]
        out = run_check(runs, d)
        summ = pd.read_csv(out / "round1_check_report_summary_20260101.csv").set_index("pdf_file_name")["group"]
        assert summ["B_2016-01-01.pdf"] == "fully_match"           # the differing value was only in run 3
        vd = pd.read_csv(out / "round1_check_value_diffs_20260101.csv")
        assert "run1_run3_match" not in vd.columns and "run1_run2_match" in vd.columns
        # a second call must not write into a folder that already has files
        try:
            chk.main(); raise AssertionError("expected SystemExit")
        except SystemExit as e:
            assert "already holds files" in str(e)
        # one run only
        chk.RUN_CSVS = chk.RUN_CSVS[:1]; chk.CHECK_DIR = d / "other"
        try:
            chk.main(); raise AssertionError("expected SystemExit")
        except SystemExit as e:
            assert "at least 2" in str(e)


def test_round2_names():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        out = run_check(make_runs(), d, round_name="round2")
        names = sorted(p.name for p in out.glob("*"))
        assert names == ["round2_check_disagreement_reports_20260101.json", "round2_check_fully_match_reports_20260101.json",
                         "round2_check_matched_rows_20260101.csv", "round2_check_report_summary_20260101.csv",
                         "round2_check_value_diffs_20260101.csv"], names
        meta = json.loads((out / "round2_check_fully_match_reports_20260101.json").read_text(encoding="utf-8"))["meta"]
        assert meta["round"] == "round2"


def test_extraction_failures():
    """A report that never produced a *_dsa.json in any run must still show up (not silently vanish)."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        dfs = make_runs()
        paths = []
        for i, df in enumerate(dfs, start=1):
            run_dir = d / f"run{i}"
            (run_dir / "compiled_csv").mkdir(parents=True)
            p = run_dir / "compiled_csv" / f"run{i}.csv"
            df.to_csv(p, index=False, encoding="utf-8-sig")
            paths.append(p)
            json_out = run_dir / "json_output"
            json_out.mkdir()
            # Z fails in every run
            (json_out / "Z_2016-01-01_ERROR.json").write_text(json.dumps({"error": f"boom in run {i}"}), encoding="utf-8")
        # W fails in run 1 and run 2, and was not even attempted in run 3 (no file of any kind for it there)
        (d / "run1" / "json_output" / "W_2016-01-01_ERROR.json").write_text(json.dumps({"error": "w fail 1"}), encoding="utf-8")
        (d / "run2" / "json_output" / "W_2016-01-01_ERROR.json").write_text(json.dumps({"error": "w fail 2"}), encoding="utf-8")

        chk.RUN_CSVS = paths
        chk.CHECK_DIR = d / "check"
        chk.RUN_DATE = "20260101"
        chk.ROUND = "round1"
        chk.main()
        out = d / "check"

        summ = pd.read_csv(out / "round1_check_report_summary_20260101.csv").set_index("pdf_file_name")
        assert summ.loc["Z_2016-01-01.pdf", "group"] == "extraction_failed_in_all_runs"
        assert summ.loc["Z_2016-01-01.pdf", "needs_check"] == "Yes"
        z_err = summ.loc["Z_2016-01-01.pdf", "error_by_run"]
        assert "run1: boom in run 1" in z_err and "run2: boom in run 2" in z_err and "run3: boom in run 3" in z_err
        assert summ.loc["Z_2016-01-01.pdf", "country"] == "Z"          # filename-derived
        assert summ.loc["Z_2016-01-01.pdf", "runs_present"] == "no|no|no"
        w_err = summ.loc["W_2016-01-01.pdf", "error_by_run"]
        assert "run1: w fail 1" in w_err and "run2: w fail 2" in w_err
        assert "run3: (no _ERROR.json or _dsa.json found)" in w_err
        # every other report (A-H, from make_runs) must be unaffected
        assert summ.loc["A_2016-01-01.pdf", "group"] == "fully_match"
        assert summ.loc["A_2016-01-01.pdf", "error_by_run"] == "" or pd.isna(summ.loc["A_2016-01-01.pdf", "error_by_run"])

        # not counted as fully matching, no rows anywhere
        fm = json.loads((out / "round1_check_fully_match_reports_20260101.json").read_text(encoding="utf-8"))
        assert "Z_2016-01-01.pdf" not in fm["fully_match_reports"] and "W_2016-01-01.pdf" not in fm["fully_match_reports"]
        assert fm["meta"]["n_reports_total"] == 10                     # A-H (8) + Z + W, now correctly counted
        mr = pd.read_csv(out / "round1_check_matched_rows_20260101.csv")
        assert not {"Z_2016-01-01_dsa.json", "W_2016-01-01_dsa.json"} & set(mr.json_file)
        vd = pd.read_csv(out / "round1_check_value_diffs_20260101.csv")
        assert not {"Z_2016-01-01.pdf", "W_2016-01-01.pdf"} & set(vd.pdf_file_name)

        # usable by 2a: category C, separate from category A
        dj = json.loads((out / "round1_check_disagreement_reports_20260101.json").read_text(encoding="utf-8"))
        assert dj["category_c_extraction_failed_in_all_runs"]["count"] == 2
        c_pdfs = {r["pdf_file_name"] for r in dj["category_c_extraction_failed_in_all_runs"]["reports"]}
        assert c_pdfs == {"Z_2016-01-01.pdf", "W_2016-01-01.pdf"}
        assert not c_pdfs & {r["pdf_file_name"] for r in dj["category_a_disagreement"]["reports"]}
        loader = extract_loader()
        stems_c = loader(out / "round1_check_disagreement_reports_20260101.json", "category_c_extraction_failed_in_all_runs")
        assert sorted(stems_c) == ["W_2016-01-01", "Z_2016-01-01"]


def test_normalisers():
    assert chk.same(chk.norm_value("0.0"), chk.norm_value("-0.0")) and chk.same(chk.norm_value("1"), chk.norm_value("1.0"))
    assert chk.same(chk.norm_value("1,169.28"), chk.norm_value("1169.28")) and chk.same(chk.norm_value(None), chk.norm_value(""))
    assert not chk.same(chk.norm_value("1.5"), chk.norm_value(None)) and not chk.same(chk.norm_value("1.5"), chk.norm_value("1.6"))
    assert chk.same(chk.norm_value("n.a."), chk.norm_value(" N.A. "))
    assert chk.norm_year("2012/13") == chk.norm_year("FY2013") == chk.norm_year("2013") == "2013"
    assert chk.norm_year("2009-2014") != chk.norm_year("2014") and chk.norm_year(None) is None
    assert chk.norm_bool("TRUE") is True and chk.norm_bool("False") is False and chk.norm_bool(None) is None


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok  ", t.__name__)
    print(f"\nall {len(tests)} tests passed")
