# DSA Decomposition Extraction Pipeline — Merge Report

**Deliverables:** `dsa_pipeline.py` (1,208 lines) and `dsa_prompts.txt` (27.5 KB)
**Replaces:** the SL and AL versions described below

---

## 1. Purpose

Two versions of the IMF DSA extraction pipeline were developed in parallel. Both extract the public-debt decomposition table (change in debt, primary balance, automatic debt dynamics, other flows, and residual) for the last actual year from IMF staff reports. Each version added improvements the other lacked.

The goal of this work was to combine the functionality of both versions into a single pipeline and to improve its efficiency, robustness, and maintainability. This report describes:

- what each previous version offered;
- which features the new version combines;
- what was modified or improved;
- what was deliberately changed.

---

## 2. The previous versions

| Label | Code | Prompt |
|---|---|---|
| **SL** | `step_1_revised_on_problematic_reports_sl.py` (2,060 lines) | `sl_revised_prompt_step_one.txt` (34.5 KB) |
| **AL** | `two_step_selected_pdf_inline_base64_cropfallback_summary_v8_robust_visual_effort.py` (2,268 lines) | `two_step_selected_pdf_prompt_table_only_cropfallback_v6_robust_visual.txt` (33.8 KB) |

### 2.1 Shared baseline

Both versions branched from the same pipeline and share most of their design:

- **Two-step process:** Step 1 locates the DSA pages from extracted text; Step 2 extracts the table from those pages, sent inline to the model as a PDF.
- **API infrastructure:** Azure AD authentication, token refresh, and retry with exponential backoff.
- **Size fallbacks:** a table-crop rendering and a compressed full-page rendering when the selected pages exceed the upload limit.
- **Year validation:** checks on the selected year, with an independent header audit when validation fails.
- **Model:** gpt-5.5 at `reasoning effort = high`.
- **Prompts:** more than 90% of the text is identical.

### 2.2 SL: focus on selecting the correct year column

| Feature | Description |
|---|---|
| Merged year-range column rule | A range column such as "2008-2016" is never selected. The model keeps scanning right to the last single-year column under the Actual/Historical heading. The rule is supported by a dedicated worked example. |
| Audit self-contradiction check | A selection is flagged when the model's own `column_header_audit` lists an eligible actual/historical column to the right of the selected one. |
| Embedded-image recompression | Before any rasterization, large embedded images are re-encoded as JPEG while the native text layer is preserved. Table text therefore stays machine-readable. |
| Targeted reruns | Only the reports listed in a JSON file are processed, and results are written to a separate output directory. |
| Upload limit | 700 KB |
| API calls per report | 2 typically; 3 with a header audit |

### 2.3 AL: focus on finding the table and reading values accurately

| Feature | Description |
|---|---|
| High-recall locator principle | Step 1 selects pages with strong DSA signals even when the text layer retains only titles, fragments, or chart labels. |
| Weighted keyword scoring | Pages are scored with phrase weights, a strong-title bonus, and a bonus for co-occurring decomposition terms. |
| Keyword override | If the model reports "not found" but keyword scoring finds strong candidates, those pages are still sent to visual inspection. |
| Mixed table-and-chart pages | A page containing both a table and a chart is not rejected; only the chart is. |
| Row-by-row tracing and full-column reread | Each row is traced from its label to the selected column, and the whole column is reread before output. |
| `pages_unreadable` rule | A mostly-null table is reported as unreadable instead of as a successful extraction. |
| Multi-orientation retry | Null-heavy or unreadable results are retried on the primary page rendered at 0°, 90°, and 270°, for sideways annex tables. |
| Independent numeric verification | An extra call rereads the selected column; any disagreement is flagged for manual review. |
| Upload limit | 550 KB |
| API calls per report | 3 or more (numeric verification always runs) |

### 2.4 Summary

The two versions were largely complementary:

- **SL** addressed *which column* to read. It lacked AL's safeguards for locating the table and reading values.
- **AL** addressed *finding the table* and *reading values correctly*. It lacked SL's range-column rule, self-contradiction check, and text-preserving compression.

---

## 3. Features combined in the new version

| Feature | Origin | Location in the new version |
|---|---|---|
| Merged year-range column rule and worked example | SL | `dsa_prompts.txt` → EXTRACTION → "Merged year-range columns" |
| Audit self-contradiction check | SL | `validate_actual_column()` |
| Embedded-image recompression | SL | `recompress_embedded_images()`; upload stage 2 |
| Targeted reruns | SL | `REPORT_LIST_FILE`, `REPORT_LIST_CATEGORY`, `RERUN_OUTPUT_DIR` |
| Focused Step 1 input (DSA-specific phrases only) | SL | `LOCATOR_CONTEXT_PHRASES`, `build_locator_input()` |
| High-recall locator principle | AL | `dsa_prompts.txt` → LOCATOR |
| Weighted keyword scoring | AL | `DSA_KEYWORD_WEIGHTS`, `keyword_locator()` |
| Keyword override of "not found" | AL | `locate_dsa()` |
| Mixed table-and-chart page rule | AL | `dsa_prompts.txt` → EXTRACTION → "Mixed pages" |
| Row-by-row tracing and full-column reread | AL | `dsa_prompts.txt` → EXTRACTION → "Reading values" |
| `pages_unreadable` rule | AL | `dsa_prompts.txt` → EXTRACTION |
| Multi-orientation retry | AL | `needs_legibility_retry()`, `ROTATED` stage, `<<<ORIENTATION_RETRY>>>` |

---

## 4. Design of the new pipeline

```
Step 1  Extract page text (PyMuPDF)
        → model locates the public-DSA page range         [effort: medium]
        → weighted keyword fallback / override (high recall)

Local   Build the Step 2 input, escalating only as far as needed:
          1. original pages (drop outer context pages if too large)
          2. same, with embedded images recompressed (text layer kept)
          3. high-resolution crop of the table on the primary page
          4. compressed full-page renderings
        A gateway size rejection (413) advances to the next stage.

Step 2  Extract the decomposition table                    [effort: high]
        → if null-heavy or unreadable: retry on 3 orientations

Verify  Local year-selection checks (incl. self-contradiction check)
        → only if a check fails: independent header audit  [effort: high]
        → disagreement ⇒ manual_review (values never changed)
```

**API calls per report**

| Version | Typical | Worst case |
|---|---|---|
| SL | 2 | 3 |
| AL | 3 | 5 |
| **New** | **2** | **4** |

---

## 5. Modifications and improvements

### 5.1 Consolidation

- **Unified upload escalation.** SL contained two near-identical copies (~70 lines each) of the fallback chain: one for oversized files and one for gateway 413 errors. Both paths now iterate over a single ordered stage list (`UPLOAD_STAGES`) through `build_step2_input()`.
- **One rendering routine.** Table-crop, full-page, and rotated rendering were three separate functions with the same resolution/quality search. All three now use `render_jpeg_pdf()`.
- **One page-trimming routine.** The "drop the page farthest from the primary table" loop appeared three times. It is now implemented once, in `fit_page_range()`.
- **Single API client.** Authentication, token refresh, retry, request-size checks, and response parsing are encapsulated in `ApiClient`.
- **Prompts separated from code.** All prompt text now lives in `dsa_prompts.txt`, split by `<<<SECTION>>>` markers:
  - `LOCATOR` (Step 1);
  - `EXTRACTION` (Step 2);
  - `CROP_NOTE` (appended when the input is a table crop);
  - `ORIENTATION_RETRY` (appended for the rotated retry);
  - `VERIFICATION` (independent header audit).
- **Prompt cleanup.**
  - Removed internal review annotations and duplicated chart-exclusion rules.
  - Condensed the range-column section without dropping any rule.
  - Removed `actual_column_validation` from the model's output schema; the pipeline always writes this field itself.

### 5.2 Efficiency

| Change | Effect |
|---|---|
| Header audit only when a year check fails | Typical API calls per report reduced to 2. This is the largest runtime saving because API calls dominate runtime. |
| Per-step reasoning effort (`REASONING_EFFORT`) | Step 1 runs at `medium`; extraction and audit remain at `high`. |
| Focused Step 1 input | A shorter locator input reduces Step 1 latency. |
| PyMuPDF text extraction instead of pdfplumber | About 6× faster on a synthetic test PDF; the gap is larger on real reports. |
| Render once per resolution; search JPEG quality in memory | The PDF is written only once a setting fits. Full-page fallback was about 1.9× faster and rotated rendering about 1.8× faster on a synthetic test. |
| Embedded images recompressed once per page range | Previously this was repeated each time a page was dropped. |
| `SKIP_EXISTING` option | Resumes an interrupted batch without reprocessing completed reports. |

### 5.3 Bug fixes and robustness

- **Header audit now knows the range-column rule.** Previously, the audit triggered by the self-contradiction check could itself select a range column.
- **No redundant recompression after a 413.** Previously, if the image-compressed PDF was rejected, the retry path recompressed the same file. The stage list now always advances to the next stage.
- **Contradictory figure rule resolved.** SL's prompt stated that figures are never valid targets, while also allowing figure-numbered tables. The prompt now consistently judges eligibility by visible row-and-column structure.
- **Locator result without a page range handled.** Previously, a "found" result with no page range caused a crash. The keyword fallback now fills the range, or the report is recorded as not found.
- **Thread safety.** MuPDF is not thread-safe, yet PDF operations previously ran in concurrent worker threads. All PDF work is now serialized with a lock, while API calls remain concurrent.
- **Explicit oversize handling.** Size problems now raise a dedicated `RequestTooLarge` exception instead of relying on error-message string matching.

### 5.4 Reusability

- All configuration sits at the top of the file. Machine-specific paths are placeholders, with the original paths kept as comments.
- Required `.env` entries and dependencies are documented in the module docstring. Dependencies are reduced from 6 to 5 packages (pdfplumber and pypdf removed).
- Functions carry short purpose docstrings; comments are limited to non-obvious decisions.

---

## 6. Deliberate changes

| Item | Change | Rationale / impact |
|---|---|---|
| AL independent numeric verification | Not included | Saves one API call per report. Value misreads are *prevented* by the prompt's reading rules but no longer independently *detected*. It can be reinstated behind a toggle if needed. |
| Upload limit | 650 KB (SL: 700 KB; AL: 550 KB) | Leaves headroom below the 1 MB gateway limit for the longer merged prompt. Lower to 550 KB if 413 errors appear. |
| SL keyword fallback | Replaced by AL weighted scoring | Selects the primary page more accurately. Only used when the model provides no page range. |
| Text extraction library | pdfplumber → PyMuPDF | Faster; Step 1 text may differ slightly for complex layouts. Step 2 reads the PDF directly and is unaffected. |
| `REPORT_LIST_FILE` default | `None` | Full run by default; set it to a JSON list for targeted reruns. |

---

## 7. Output format changes

| File | Change |
|---|---|
| `<stem>_dsa.json` | Structure unchanged. `source.actual_column_validation` is always written by the pipeline. The AL `numeric_verification` field no longer appears. |
| `<stem>_timing.json` | Separate failure-reason fields are consolidated into `stage_failures`. |
| `RUN_SUMMARY.json` | Per-method counters are replaced by `extraction_method_counts`, and a `manual_review` count is added. |
| Extraction method labels | Unchanged: `selected_pdf_direct`, `selected_pdf_image_compressed`, `pymupdf_pillow_table_crop_fallback`, `pymupdf_pillow_visual_fallback`, `pymupdf_pillow_multi_orientation_retry`. |

---

## 8. Validation and limitations

**Performed:**

- Static checks: the code compiles and passes `pyflakes` with no warnings.
- End-to-end runs against a mocked API on synthetic PDFs, covering:
  - the keyword override of a "not found" locator result;
  - all four upload stages and the rotated stage;
  - escalation after an oversize rejection;
  - orientation retry replacing an unreadable first result;
  - conditional header audit, including the `manual_review` and `accepted_with_warning` outcomes;
  - exclusion of currency-union reports and generation of the run summary.
- A live run on a small set of reports completed Step 1 and Step 2 successfully.

**Limitation:** extraction accuracy relative to SL and AL has not yet been measured against a verified reference set.

---

## 9. Recommended next steps

1. **Build a reference set.** Manually verify a sample of reports against the source PDFs, including both difficult and routine cases.
2. **Benchmark.** Run SL, AL, and the new version on that sample and compare year-selection accuracy and value accuracy.
3. **Decide on numeric verification.** If value misreads remain frequent, reinstate AL's numeric verification behind a `NUMERIC_VERIFICATION` toggle.
4. **Improve logging.** Prefix every log line with the report name, since concurrent workers currently interleave their output.