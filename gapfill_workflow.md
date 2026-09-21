# Gap year 填补流程

更新日期：2026-09-20　｜　当前批次：2016-2020（SA主文件）。errors文件不在本流程内，流程只处理你传入的那一个CSV。

**目的**：同一国家相邻两份staff report的`last_actual_year`不连续时，panel里会缺中间的年份（gap year）。本流程先找出gap year，再通过内部API到后续报告（T+2、T+3年）里读取该年的actual数据补进panel。

## 1. 流程总览

```
① 3a_gapfill_1_build_panel_gap_flags.py   找出哪些国家哪些年是gap
      ↓  gap_years, report_inventory, panel_structure ...
② 3b_gapfill_2_build_targets.py           生成任务清单（要填哪些、哪些报告不能当来源）
      ↓  gapfill_targets, gapfill_skip_reports
③ 3c_gapfill_3_run_api.py                 调API读T+2 / T+3报告，校验是actual，填补
      ↓  output/gapfill/...
后续：核对结果、并入最终panel
```

## 2. 文件一览

| 步骤 | 文件（`code/`） | Input | Output |
|---|---|---|---|
| ① | `3a_gapfill_1_build_panel_gap_flags.py` | **一个**compiled CSV（如`output/2016-2020/compiled_csv/dsa_decomposition_labels_2016-2020_sa.csv`），路径在文件顶部`INPUT_CSV`或用`--input`指定 | `output/2016-2020/gap_year_check/`：`panel_structure_country_year`、`gap_years`、`report_inventory`、`coverage_matrix_country_year`、`panel_children_long`、`summary_stats.json`（后缀`_20260920_v2`） |
| ② | `3b_gapfill_2_build_targets.py` | ①的`gap_years`、`report_inventory` | 同一文件夹：`gapfill_targets`（每个gap year一行）、`gapfill_skip_reports`（不能当来源的报告） |
| ③ | `3c_gapfill_3_run_api.py` | ②的两个CSV；Step 1已生成的`selected_pdf_pages`文件夹（及其上一级的`*_timing.json`）；`gapfill_extraction_prompt_v2.txt`；`.env`；（可选）①的`panel_structure` | `output/gapfill/2016-2020_20260920_v2/`：`reports/<报告名>_gapfill.json`、`gapfill_resolution`、`gapfill_attempts`、`gapfill_values_long`、`gapfill_values_wide`、`panel_structure_filled`、`RUN_SUMMARY_*.json` |
| 库 | `gapfill_lib_core.py` | — | 被③调用：候选报告排序、级联流程、actual校验、结果输出。**不直接运行** |
| 测试 | `gapfill_test_logic.py` | 无 | 打印测试结果，可选。`python gapfill_test_logic.py` |

其他依赖：③会导入Step 1脚本`2a_step_1_revised_on_problematic_reports_sl.py`，复用它的API认证、重试和调用函数（不会运行Step 1本身）。国家名标准化和年份解析函数放在库文件里，①和库都要放在同一文件夹。

## 3. 各步骤做什么

**① 找gap**
- 每份报告 = 一个观测值（国家, `last_actual_year`）。国家和日期取自PDF文件名，国家名统一拼写。
- 财年写法（`2015/16`）映射到财年结束年（2016）；多年区间不算有效年份。
- 同国家同年多份报告，保留最新一份。
- gap = 国家首末观测年之间没有任何报告提供的年份；首尾年份不算。
- `报告年份 − last actual year ≥ 4`或为负的观测值不入panel（判为误读，避免造出假gap）。
- 每个gap标注成因，并用各报告的column-header audit预判"哪份报告里该年是actual列"（不读PDF）。

**② 生成任务清单**
- 每个gap year一行。
- Step 1没找到DSA表的报告、多国文件，列入skip清单（不当来源）。

**③ 调API填补**
- 每个gap year（T）按顺序尝试：**T+2年的报告（同年最晚的先试）→ T+3年的报告**，命中第一个"T为actual/historical列"的报告即停；T+3也失败则标`unresolved`，不再试T+4。
- **不再读原始PDF、不再定位DSA表、不再压缩**：直接使用Step 1已生成的selected PDF pages。候选报告就是`SELECTED_PDF_DIRS`各文件夹里已有selected PDF的报告，可跨批次（如T+3落在2021年后）。
- selected PDF的文件名只要以`<国家>_<日期>`（有Country Report编号的再加`_CR编号`）开头即可，后面是什么后缀都行，按这个前缀与报告对应。
- 每份报告的selected PDF：优先取`*_timing.json`记录的、当时实际发给API的那份（同时得到页码对应关系）；没有timing.json时按 直接选页 > 压缩图片 > 表格裁剪 > 整页压缩图 的优先级取。
- 同一份报告被多个gap year同时指向时，合并成一次调用。
- 已处理的报告缓存为JSON，中断后重跑不会重复调用。

## 4. Actual校验（只准要actual/historical，三层）

1. **Prompt**：开头和Task 2.4/2.5都写明：preliminary、estimate、projection列一律不提取，返回null和原因码。表头判定沿用Step 1的证据层级（改成针对目标年份的列）。
2. **代码校验**：列状态必须是actual/historical；表头原文不能含Prel./Est./Proj.；模型自己列出的年份列里该年状态必须合规；不能出现"更早年份是projection、目标年却是actual"。任一不过即拒绝，转下一份报告。
3. **二次核对**：仅当模型自己的年份列清单缺该年或与其回答矛盾时，再发一次独立表头核对；确认是actual才接受，标`resolved_with_warning`。

## 5. 结果状态

| 状态 | 含义 |
|---|---|
| `resolved` | 取到actual/historical数据 |
| `resolved_with_warning` | 取到，但经二次核对才确认，或有提示（如恒等式不成立） |
| `unresolved` | T+2、T+3都没取到（列是estimate/projection、年份不在表里、只在合并区间列等） |
| `unresolved_no_candidate_reports` | 该国T+2、T+3年没有可用报告 |
| `pending_api_error` | API出错，重跑脚本会自动重试 |

单次尝试的状态（`gapfill_attempts`）：`rejected_not_actual`、`year_not_in_table`、`merged_range_only`、`values_unreadable`、`no_dsa_table`、`selected_pdf_not_found`（找不到该报告的selected PDF，换下一份）、`pdf_too_large`（请求体超过网关上限，换下一份）等。

## 6. 运行

1. 用Git拉取最新代码。
   （推荐用总控`0_run_gapfill.py`一次运行①②③：它在CONFIG里集中设置路径和版本号，用runpy依次运行三个脚本。使用前先把①②③各自的CONFIG块注释掉，注释哪些行见总控文件开头的说明。运行时可以带`--dry-run`、`--limit-gaps 5`等选项，由③读取。）
2. 修改`3c_gapfill_3_run_api.py`顶部CONFIG：`BASE_DIR`、`SELECTED_PDF_DIRS`（Step 1各批次的`selected_pdf_pages`文件夹，重跑过的文件夹排在前面）、`STEP1_SCRIPT`等。
3. 依次运行①、②，再运行③：
   ```
   python 3c_gapfill_3_run_api.py --dry-run          # 只列出计划调用，并检查selected PDF找得到，不调API
   python 3c_gapfill_3_run_api.py --limit-gaps 5     # 试跑5个gap year，检查输出JSON
   python 3c_gapfill_3_run_api.py                    # 全量运行（可中断重跑）
   python 3c_gapfill_3_run_api.py --collect-only     # 用已保存JSON重新生成汇总表，不调API
   ```

在IPython/PyCharm console里运行也可以；如提示找不到文件，先`%cd`到`code`文件夹，或直接修改脚本顶部的路径配置。

## 7. 当前结果与待办（2016-2020）

- 851份报告 → 640个观测值、180个国家；94个国家有gap，共**120个gap year**（104段）。
- 成因：相邻报告年份直接跳年87段；中间报告无DSA表17段。
- 任务清单：**120个gap year全部运行**；不能当来源的报告114份。
- audit预判：105个gap year能在其他报告里找到actual列，15个只有estimate/projection/合并区间列。
- 按当前清单测算：第一轮约103次API调用，4个gap year无候选报告（含South Sudan 2019，需2021年后的报告的selected PDF）。

待办与注意：
- ③已在IMF电脑上用旧版（含定位和压缩步骤）完整跑通；**简化后直接读selected PDF的新版还没跑过**，请先`--dry-run`，再`--limit-gaps 5`并核对输出JSON。
- 同国家同年有多份报告的80个country-year里，64个数值不一致（已按规则取最新），后续可能需单独核查。
- 批次边缘的gap（跨2015/16、2020/21）在单批次里看不到，合并多批次后重跑①即可。

## 8. 用于其他批次

- ①：`python 3a_gapfill_1_build_panel_gap_flags.py --input 某个CSV [--out-dir 输出文件夹]`，输出文件夹默认是该CSV所在批次文件夹下的`gap_year_check`。
- ②：`python 3b_gapfill_2_build_targets.py --check-dir 上一步的输出文件夹 --stamp 版本号`。
- ①②③文件里各有一个`STAMP`（当前`20260920_v2`），必须一致；换批次或版本时同步修改，③里还要改`SELECTED_PDF_DIRS`等路径。
