"""
【3b_gapfill_2】生成 API 运行的任务清单
    第 2 步 ｜ 手动运行 ｜ 不读 PDF，不调 API，几秒钟跑完

作用
    把第 1 步得到的 gap 清单，整理成第 3 步要用的两个文件。

Input（第 1 步的输出，在 CHECK_DIR 下，文件名带 STAMP）
    gap_years_<STAMP>.csv
    report_inventory_<STAMP>.csv

Output（写到同一个文件夹）
    gapfill_targets_<STAMP>.csv        每个 gap year 一行：gap_id, country, gap_year, gap_span, primary_cause,
                                       audit_fill_status（第 1 步的预判）, audit_expected_source_report（预判的来源报告）
    gapfill_skip_reports_<STAMP>.csv   不能当来源的报告：Step 1 没找到 DSA 表的、多国文件（pdf_file_name, reason）
    -> 这两个文件是第 3 步的输入。

核心步骤
    1. 读 gap_years，每个 gap year 整理成 targets 的一行。
    2. 读 report_inventory，挑出没有 DSA 表的报告和多国文件，列入 skip。
    3. 写出两个 CSV。

用法
    python 3b_gapfill_2_build_targets.py [--check-dir 第1步的输出文件夹] [--stamp 版本号]
    或直接改文件顶部的 CHECK_DIR / STAMP 后运行。STAMP 必须与第 1 步一致。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def _here() -> Path:
    """Folder holding the gapfill scripts. Uses __file__ when the file is run
    normally; in an IPython / PyCharm console (no __file__) it looks for the
    folder that contains gapfill_lib_core.py, starting from the working folder."""
    try:
        return Path(__file__).resolve().parent
    except NameError:
        cwd = Path.cwd()
        for cand in (cwd, cwd / "code", cwd.parent / "code", cwd.parent):
            if (cand / "gapfill_lib_core.py").exists():
                return cand
        return cwd

HERE = _here()
BASE = HERE.parent if HERE.name == "code" else HERE

# ------------------------------------------------------------------ CONFIG
CHECK_DIR = BASE / "output" / "2016-2020" / "gap_year_check"  # folder with the step-1 outputs
STAMP = "20260920_v2"  # must match the STAMP used by 3a_gapfill_1_build_panel_gap_flags.py


def main(check_dir: Path = CHECK_DIR, stamp: str = STAMP) -> None:
    check_dir = Path(check_dir)
    gaps = pd.read_csv(check_dir / f"gap_years_{stamp}.csv")
    inv = pd.read_csv(check_dir / f"report_inventory_{stamp}.csv")

    targets = pd.DataFrame({
        "gap_id": gaps["gap_id"],
        "country": gaps["country"],
        "gap_year": gaps["gap_year"],
        "gap_span": gaps["gap_span"],
        "primary_cause": gaps["primary_cause"],
        "audit_fill_status": gaps["fill_status"],
        "audit_expected_source_report": gaps["preferred_source_report"],
    }).sort_values(["country", "gap_year"])
    targets.to_csv(check_dir / f"gapfill_targets_{stamp}.csv", index=False, encoding="utf-8-sig")

    skip = inv[inv["report_status"].isin(["no_table", "excluded_non_country"])].copy()
    skip["reason"] = skip["report_status"].map({
        "no_table": "Step 1 found no DSA table",
        "excluded_non_country": "multi-country document",
    })
    skip[["pdf_file_name", "reason"]].sort_values("pdf_file_name").to_csv(
        check_dir / f"gapfill_skip_reports_{stamp}.csv", index=False, encoding="utf-8-sig"
    )

    print(f"gap years to fill: {len(targets)}")
    print(f"reports never used as a source: {len(skip)}")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--check-dir", default=None)
    ap.add_argument("--stamp", default=None)
    a, _ = ap.parse_known_args()  # tolerant of extra args injected by IPython/Spyder
    main(Path(a.check_dir) if a.check_dir else CHECK_DIR, a.stamp or STAMP)
