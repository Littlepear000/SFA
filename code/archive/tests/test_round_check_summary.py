"""Offline tests for 1d_round_check_summary.py. Run: python test_round_check_summary.py"""
import importlib.util
import json
import re
import sys
import tempfile
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


chk = load(HERE / "1c_round_check_compare_runs.py", "round_check")
tst = load(HERE / "test_round1_check.py", "round_check_tests")  # reuses make_runs()


def build_check_dir(d: Path, extra_failures: bool = True) -> Path:
    """A realistic 1c run: 3 synthetic runs (+2 all-run extraction failures if requested), then run 1c."""
    dfs = tst.make_runs()
    paths = []
    for i, df in enumerate(dfs, start=1):
        run_dir = d / f"run{i}"
        (run_dir / "compiled_csv").mkdir(parents=True)
        p = run_dir / "compiled_csv" / f"run{i}.csv"
        df.to_csv(p, index=False, encoding="utf-8-sig")
        paths.append(p)
        if extra_failures:
            jo = run_dir / "json_output"
            jo.mkdir()
            (jo / "Z_2016-01-01_ERROR.json").write_text(json.dumps({"error": f"boom in run {i}"}), encoding="utf-8")
    chk.RUN_CSVS = paths
    chk.CHECK_DIR = d / "check"
    chk.RUN_DATE = "20260101"
    chk.ROUND = "round1"
    chk.main()
    return d / "check"


def run_summary(d1, check_dir: Path):
    d1.CHECK_DIR = check_dir
    d1.RUN_DATE = "20260101"
    d1.ROUND = "round1"
    d1.main()
    return check_dir / "round1_check_summary_20260101.md"


def cell(md: str, row_label: str, col: int):
    """Value in the given (1-based) pipe-delimited column of the markdown table row starting with row_label."""
    line = next(l for l in md.splitlines() if l.startswith(f"| {row_label} |"))
    return [c.strip() for c in line.strip("|").split("|")][col - 1]


def test_headline_and_detail_numbers():
    d1 = load(HERE / "1d_round_check_summary.py", "d1")
    with tempfile.TemporaryDirectory() as d:
        check_dir = build_check_dir(Path(d))
        md_path = run_summary(d1, check_dir)
        md = md_path.read_text(encoding="utf-8")

        assert cell(md, "Total reports compared", 2) == "9"
        assert cell(md, "Fully match", 2) == "2" and cell(md, "Fully match", 3) == f"{100 * 2 / 9:.1f}%"
        assert cell(md, "Disagreement (needs check)", 2) == "5" and cell(md, "Disagreement (needs check)", 3) == f"{100 * 5 / 9:.1f}%"
        assert cell(md, "No table found (all runs agree)", 2) == "1"
        assert cell(md, "Extraction failed (every run)", 2) == "1"
        # headline buckets must add up to the total
        assert 2 + 5 + 1 + 1 == 9

        assert cell(md, "Partial match (table & year agree, some rows differ)", 2) == "2"
        assert cell(md, "table_found differs across runs", 2) == "1"
        assert cell(md, "last_actual_year differs across runs", 2) == "1"
        assert cell(md, "Report missing from at least one run", 2) == "1"
        assert cell(md, "Extraction failed in every run (no *_dsa.json)", 2) == "1"
        assert cell(md, "No table found, in every run", 2) == "1"

        assert cell(md, "Total data points compared", 2) == "40"
        assert cell(md, "Matched (identical across all runs)", 2) == "22" and cell(md, "Matched (identical across all runs)", 3) == "55.0%"
        assert cell(md, "Differing", 2) == "18" and cell(md, "Differing", 3) == "45.0%"

        assert cell(md, "Value differs (same table, same year, same row)", 2) == "2"
        assert cell(md, "Row present in some runs but not others", 2) == "1"
        assert cell(md, "Whole report: table_found differs across runs", 2) == "5"
        assert cell(md, "Whole report: last_actual_year differs across runs", 2) == "5"
        assert cell(md, "Whole report: missing from at least one run's CSV", 2) == "5"
        reasons_sum = 2 + 1 + 5 + 5 + 5
        assert reasons_sum == 18

        # header / provenance line
        assert "**Round:** round1" in md and "**Run date:** 20260101" in md and "**Runs compared:** 3" in md
        for name in ("run1.csv", "run2.csv", "run3.csv"):
            assert f"`{name}`" in md

        # re-running overwrites cleanly (no crash, no leftover second copy)
        run_summary(d1, check_dir)
        assert md_path.exists()


def test_no_differing_data_points():
    """All reports fully matching: value_diffs.csv is header-only; the markdown must not show an empty table."""
    d1 = load(HERE / "1d_round_check_summary.py", "d1")
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        df = tst.report("A_2016-01-01", "A", items=tst.ITEMS)
        dfs = [pd.DataFrame(df, columns=tst.COLS) for _ in range(3)]
        paths = []
        for i, dfi in enumerate(dfs, start=1):
            run_dir = d / f"run{i}"
            (run_dir / "compiled_csv").mkdir(parents=True)
            p = run_dir / "compiled_csv" / f"run{i}.csv"
            dfi.to_csv(p, index=False, encoding="utf-8-sig")
            paths.append(p)
        chk.RUN_CSVS = paths
        chk.CHECK_DIR = d / "check"
        chk.RUN_DATE = "20260101"
        chk.ROUND = "round1"
        chk.main()

        md = run_summary(d1, d / "check").read_text(encoding="utf-8")
        assert cell(md, "Differing", 2) == "0"
        assert "*No differing data points.*" in md
        assert "| Reason | Data points |" not in md


def test_guards():
    d1 = load(HERE / "1d_round_check_summary.py", "d1")
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        check_dir = build_check_dir(d)

        # missing 1c output entirely
        d1.CHECK_DIR = d / "no_such_folder"
        d1.RUN_DATE = "20260101"
        d1.ROUND = "round1"
        try:
            d1.main()
            raise AssertionError("expected SystemExit")
        except SystemExit as e:
            assert "not found" in str(e)

        # report_summary.csv row count does not match fully_match_reports.json's n_reports_total
        summ_path = check_dir / "round1_check_report_summary_20260101.csv"
        summ = pd.read_csv(summ_path)
        summ.iloc[:-1].to_csv(summ_path, index=False, encoding="utf-8-sig")  # drop one row
        d1.CHECK_DIR = check_dir
        try:
            d1.main()
            raise AssertionError("expected SystemExit")
        except SystemExit as e:
            assert "Inconsistent" in str(e) and "report_summary" in str(e)
        summ.to_csv(summ_path, index=False, encoding="utf-8-sig")  # restore

        # disagreement_reports.json's category_a count no longer matches the other counts
        dis_path = check_dir / "round1_check_disagreement_reports_20260101.json"
        dis = json.loads(dis_path.read_text(encoding="utf-8"))
        dis["category_a_disagreement"]["count"] = 999
        dis_path.write_text(json.dumps(dis), encoding="utf-8")
        try:
            d1.main()
            raise AssertionError("expected SystemExit")
        except SystemExit as e:
            assert "Inconsistent" in str(e) and "category_a_disagreement" in str(e)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok  ", t.__name__)
    print(f"\nall {len(tests)} tests passed")
