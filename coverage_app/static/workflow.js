/* Workflow, Panel database and the top-level navigation of the DSA app.
   Talks to /api/wf/* (coverage_app/workflow.py). The Coverage section is app.js. */
(function () {
  "use strict";

  // ------------------------------------------------------------------ helpers
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmtN = (n) => (n == null ? "—" : Number(n).toLocaleString("en-US"));
  const fmtTime = (iso) => (iso ? String(iso).replace("T", " ").slice(0, 16) : "");
  const pct = (a, b) => (b ? Math.round((100 * a) / b) + "%" : "—");
  const store = (k, v) => { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } };
  function toast(msg) {
    const t = $("toast"); t.textContent = msg; t.hidden = false;
    clearTimeout(toast._t); toast._t = setTimeout(() => { t.hidden = true; }, 6000);
  }
  function api(path, body, query) {
    let url = "/api/wf/" + path;
    if (query) {
      const q = new URLSearchParams();
      Object.keys(query).forEach((k) => { if (query[k] != null && query[k] !== "") q.set(k, query[k]); });
      const s = q.toString(); if (s) url += "?" + s;
    }
    const opt = body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {};
    return fetch(url, opt).then((r) => r.json().then((j) => { if (!r.ok) throw new Error(j.error || "HTTP " + r.status); return j; }));
  }
  const h = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; };
  const pdfUrl = (p) => "/api/wf/pdf?path=" + encodeURIComponent(p.path) + (p.page ? "#page=" + p.page : "");
  const stemDate = (pdf) => { const m = /_(\d{4}-\d{2}-\d{2})/.exec(pdf || ""); return m ? m[1] : ""; };

  const ROUND_NAME = { round1: "Round One", round2: "Round Two" };
  const GROUPS = {
    fully_match: ["Fully matched", "g-ok"],
    partial_match: ["Some rows differ", "g-warn"],
    last_actual_year_differs: ["Year differs", "g-bad"],
    table_found_differs: ["Table found differs", "g-bad"],
    missing_in_run: ["Missing in a run", "g-bad"],
    no_table_in_all_runs: ["No table in any run", "g-mute"],
    extraction_failed_in_all_runs: ["Extraction failed", "g-mute"],
  };
  const groupBadge = (g) => { const x = GROUPS[g] || [g, "g-mute"]; return `<span class="gbadge ${x[1]}">${esc(x[0])}</span>`; };
  const TOP = [["1", "Change in debt"], ["2", "Identified flows"], ["3", "Primary deficit"], ["4", "Automatic dynamics"], ["5", "Other identified flows"], ["6", "Residual"]];
  const CAT_OF = { 1: "change in debt", 2: "identified flows", 3: "primary balance", 4: "automatic debt dynamics", 5: "other identified flows", 6: "residual" };
  const SRC = { round1: "Round 1", round2: "Round 2", round3: "Round 3", gapfill: "Gap fill" };

  const W = { ov: null, info: null, job: null, jobWasRunning: false, view: null, hr: null, review: null, gap: null, panel: null };

  // ------------------------------------------------------------------ modal (file viewer, job log)
  function openModal(title, sub, bodyHtml, actionsHtml) {
    $("modal-title").textContent = title; $("modal-sub").textContent = sub || "";
    $("modal-body").innerHTML = bodyHtml; $("modal-actions").innerHTML = actionsHtml || "";
    const d = $("modal"); if (!d.open) d.showModal();
  }
  $("modal-close").addEventListener("click", () => $("modal").close());
  $("modal").addEventListener("click", (e) => { if (e.target === $("modal")) $("modal").close(); });
  function viewFile(kind, name) {
    if (!name) return;
    api("file", null, { kind, name }).then((f) => {
      const lines = f.text.split("\n");
      const body = `<pre class="code"><code>${lines.map((l, i) => `<span class="ln">${i + 1}</span>${esc(l)}`).join("\n")}</code></pre>`;
      openModal(f.name, `${kind === "code" ? "Python file" : "Prompt"} · ${f.path} · ${fmtN(f.size)} bytes · modified ${fmtTime(f.modified)}`, body);
    }).catch((e) => toast(e.message));
  }
  function viewLog(id) {
    api("job/" + encodeURIComponent(id), null, { lines: 20000 }).then((r) => {
      const j = r.job;
      openModal("Job log", `${j.title} · ${j.log_total_lines} lines`, `<pre class="log big-log">${esc(j.log.join("\n"))}</pre>`);
      const pre = $("modal-body").querySelector("pre"); pre.scrollTop = pre.scrollHeight;
    }).catch((e) => toast(e.message));
  }

  // ------------------------------------------------------------------ navigation
  function parseHash() {
    const parts = decodeURIComponent(location.hash.replace(/^#/, "")).split("/").filter((x) => x !== "");
    return { main: parts[0] || "workflow", rest: parts.slice(1) };
  }
  function route() {
    const r = parseHash();
    if (["workflow", "panel", "coverage"].indexOf(r.main) < 0) r.main = "workflow";
    ["workflow", "panel", "coverage"].forEach((m) => { $("sec-" + m).hidden = m !== r.main; });
    document.querySelectorAll("[data-main]").forEach((a) => a.setAttribute("aria-current", String(a.dataset.main === r.main ? "page" : "false")));
    if (r.main === "coverage") { window.Coverage.showTab(r.rest[0] || window.Coverage.current()); return; }
    if (r.main === "panel") { renderPanel(r.rest[0]); return; }
    let step = r.rest[0] || store("wf_step") || "round1";
    if (["settings", "round1", "round2", "review", "hr", "gap"].indexOf(step) < 0) step = "round1";
    if (step !== "review") store("wf_step", step);
    document.querySelectorAll(".stepper .step").forEach((a) => {
      const on = a.dataset.step === step || (step === "review" && a.dataset.step === r.rest[1]);
      a.setAttribute("aria-current", on ? "step" : "false");
    });
    W.view = step;
    const v = $("wf-view");
    if (step === "settings") renderSettings(v);
    else if (step === "round1" || step === "round2") renderRound(v, step);
    else if (step === "review") renderReview(v, r.rest[1], r.rest[2]);
    else if (step === "hr") renderHR(v, r.rest[1], r.rest.slice(2).join("/"));
    else if (step === "gap") renderGap(v, r.rest[1]);
  }
  window.addEventListener("hashchange", route);

  // ------------------------------------------------------------------ overview: stepper status + database strip
  function loadOverview() {
    return api("overview").then((ov) => { W.ov = ov; paintOverview(); return ov; }).catch((e) => toast(e.message));
  }
  function latestCheck(list) { return (list || []).find((v) => v.has_check); }
  function paintOverview() {
    const ov = W.ov; if (!ov) return;
    const r1 = latestCheck(ov.round1), r2 = latestCheck(ov.round2);
    const fm = (v) => (v && v.counts_by_group ? fmtN(v.counts_by_group.fully_match) + " fully matched" : "");
    $("st-settings").textContent = "Batch " + ov.batch;
    $("st-round1").textContent = r1 ? "v" + r1.version + " · " + fm(r1) : "not run yet";
    $("st-round2").textContent = r2 ? "v" + r2.version + " · " + fm(r2) : "not run yet";
    const hr = ov.human_review;
    $("st-hr").textContent = hr ? `${fmtN(hr.total - hr.counts.todo)} / ${fmtN(hr.total)} reviewed` : "after Round Two";
    const g = (ov.gap_runs || [])[0];
    $("st-gap").textContent = g ? "v" + g.stamp + (g.appended_as ? " · appended" : g.filled ? " · filled" : g.identified ? " · gaps found" : "") : "after the review";
    // database strip
    const p = (ov.panel || [])[0], st = ov.staging;
    const part = (src) => (st && st.parts ? st.parts.find((x) => x.source === src) : null);
    const piece = (src, label) => { const x = part(src); return x ? `<span class="chip-n"><i class="sw s-${src}"></i>${label} <b>${fmtN(x.rows)}</b> rows <span class="muted">(${fmtN(x.reports)} reports)</span></span>` : `<span class="chip-n muted"><i class="sw s-${src}"></i>${label} —</span>`; };
    $("db-strip").innerHTML = `
      <div class="strip-block">
        <div class="strip-h">Panel database</div>
        ${p ? `<div><b>v${esc(p.stamp)}</b> · ${fmtN(p.rows)} rows · ${fmtN(p.country_years)} country-years · ${fmtN(p.countries)} countries <a href="#panel" class="lnk">Open</a></div>`
            : `<div class="muted">No version yet. <a href="#panel" class="lnk">Start one</a> from an existing merged CSV, or append the rounds below.</div>`}
      </div>
      <div class="strip-block grow">
        <div class="strip-h">Ready to append · batch ${esc(ov.batch)}</div>
        <div class="chips">${piece("round1", "Round 1 fully matched")}${piece("round2", "Round 2 fully matched")}${piece("round3", "Round 3 reviewed")}
          <a class="btn small" href="#workflow/hr/${esc(ov.round2_selected || "")}" data-go-append>Review &amp; append →</a></div>
      </div>`;
    const go = $("db-strip").querySelector("[data-go-append]");
    if (go) go.addEventListener("click", () => setTimeout(() => { const a = $("append-card"); if (a) a.scrollIntoView({ behavior: "smooth" }); }, 300));
  }

  // ------------------------------------------------------------------ jobs
  function pollJob() {
    clearTimeout(pollJob._t);
    return api("job").then((r) => {
      const j = r.job; W.job = j;
      const running = j && (j.state === "running" || j.state === "starting");
      paintJobPill(j);
      document.querySelectorAll("[data-job-slot]").forEach((slot) => paintJobSlot(slot, j));
      if (W.jobWasRunning && !running) onJobFinished(j);
      W.jobWasRunning = running;
      pollJob._t = setTimeout(pollJob, running ? 1500 : 8000);
    }).catch(() => { pollJob._t = setTimeout(pollJob, 5000); });
  }
  function onJobFinished(j) {
    toast(j.state === "done" ? "Finished: " + j.title : "Job " + j.state + ": " + (j.error || j.title));
    loadOverview().then(() => {
      if (W.view === "round1" || W.view === "round2") paintVersions(W.view);
      if (W.view === "gap" && W.gap) loadGap(W.gap.stamp);
    });
  }
  function jobProgress(j) {
    if (!j) return 0;
    if (j.state === "done") return 1;
    const n = j.n_steps || 1, s = Math.max(1, j.step || 1);
    const inner = j.total ? Math.min(1, (j.done || 0) / j.total) : 0;
    return Math.min(0.99, (s - 1 + inner) / n);
  }
  function paintJobPill(j) {
    const pill = $("job-pill");
    if (!j || !(j.state === "running" || j.state === "starting")) { pill.hidden = true; return; }
    pill.hidden = false;
    pill.innerHTML = `<span class="spinner" aria-hidden="true"></span>${esc(j.title.split(" · ").slice(0, 2).join(" · "))} · ${Math.round(100 * jobProgress(j))}%`;
    pill.onclick = () => viewLog(j.id);
  }
  function paintJobSlot(slot, j) {
    const want = slot.dataset.jobSlot; // round1 | round2 | gap
    const mine = j && ((want === "gap" && j.links && j.links.gap) || (j.links && j.links.round === want) ||
                       (want === "gap" && (j.stage || "").startsWith("gap")));
    if (!mine) { slot.innerHTML = ""; return; }
    const running = j.state === "running" || j.state === "starting";
    const steps = (j.steps || []).map((label, i) => {
      const k = i + 1;
      let cls = "pending", mark = String(k);
      if (j.state === "done" || k < (j.step || 0)) { cls = "done"; mark = "✓"; }
      else if (k === j.step) { cls = running ? "now" : j.state === "error" ? "bad" : "stop"; mark = running ? "" : cls === "bad" ? "✕" : "■"; }
      const prog = k === j.step && running && j.total ? ` <span class="muted">${fmtN(j.done)} / ${fmtN(j.total)}</span>` : "";
      return `<li class="${cls}"><span class="dot">${cls === "now" ? '<span class="spinner"></span>' : mark}</span>${esc(label)}${prog}</li>`;
    }).join("");
    const p = jobProgress(j);
    const head = running ? `<b>Running</b> · started ${fmtTime(j.started || j.created)}`
      : j.state === "done" ? `<b class="ok-txt">Finished</b> · ${fmtTime(j.finished)}`
      : `<b class="bad-txt">${esc(j.state === "stopped" ? "Stopped" : j.state === "interrupted" ? "Interrupted" : "Failed")}</b> · ${esc(j.error || "")}`;
    slot.innerHTML = `
      <div class="jobcard ${esc(j.state)}">
        <div class="jobcard-head"><div>${head}<div class="muted small-txt">${esc(j.title)}</div></div>
          <div class="head-actions">${running ? '<button class="btn small danger" data-stop>Stop</button>' : ""}<button class="btn small" data-log>Full log</button></div></div>
        <div class="progress ${running ? "running" : j.state}"><div class="bar"><span style="width:${(100 * p).toFixed(0)}%"></span></div></div>
        <ol class="steps">${steps}</ol>
        <pre class="log tail">${esc((j.log || []).slice(-10).join("\n"))}</pre>
      </div>`;
    const stop = slot.querySelector("[data-stop]");
    if (stop) stop.addEventListener("click", () => {
      if (!confirm("Stop this job? Reports already extracted stay on disk; the run folder is left unfinished.")) return;
      api("job/stop", {}).then(pollJob).catch((e) => toast(e.message));
    });
    slot.querySelector("[data-log]").addEventListener("click", () => viewLog(j.id));
  }

  // ------------------------------------------------------------------ settings
  function loadInfo() { return api("settings").then((i) => { W.info = i; return i; }); }
  function saveSettings(patch, quiet) {
    return api("settings", patch).then((i) => { W.info = i; if (!quiet) toast("Settings saved."); loadOverview(); return i; }).catch((e) => { toast(e.message); throw e; });
  }
  function renderSettings(v) {
    v.innerHTML = `<div class="card"><h2>Settings</h2><p class="muted">Loading…</p></div>`;
    loadInfo().then((I) => {
      const s = I.settings, inf = I.info;
      const st = (o, extra) => `<div class="field-status ${o.exists ? "ok" : "bad"}">${o.exists ? "Found" + (extra || "") : "Not found"} · <code>${esc(o.path)}</code></div>`;
      v.innerHTML = `
        <div class="card">
          <h2>Workflow settings</h2>
          <p class="muted">Shared by every step. Paths may be absolute, or relative to the project folder <code>${esc(inf.project)}</code>.</p>
          <div class="form-grid">
            <label for="s-pdf">Staff reports to read (PDF folder)</label>
            <div class="field"><input id="s-pdf" type="text" value="${esc(s.pdf_dir)}" spellcheck="false">
              ${st(inf.pdf_dir, " · " + fmtN(inf.pdf_dir.n_pdfs) + " PDFs")}
              <div class="field-status muted">The folder with this batch's staff report PDFs. Round One reads every PDF in it; Round Two re-reads the ones Round One could not agree on.</div></div>
            <label for="s-batch">Batch name</label>
            <div class="field"><input id="s-batch" type="text" value="${esc(s.batch)}" placeholder="${esc(inf.batch)}" spellcheck="false">
              <div class="field-status muted">Results go to <code>${esc(inf.output_dir)}</code>. Empty = the PDF folder's name.</div></div>
            <label for="s-root">All staff reports (root folder)</label>
            <div class="field"><input id="s-root" type="text" value="${esc(s.staff_reports_root)}" spellcheck="false">
              ${st(inf.staff_reports_root)}
              <div class="field-status muted">The folder holding every batch's PDF folder. Gap Fill looks for later reports (T+2 … T+4) anywhere in it; the review pages also find PDFs here.</div></div>
            <label for="s-env">API key file (.env)</label>
            <div class="field"><input id="s-env" type="text" value="${esc(s.env_file)}" spellcheck="false">${st(inf.env_file)}</div>
            <label for="s-prefix">CSV name prefix</label>
            <div class="field"><input id="s-prefix" type="text" value="${esc(s.csv_prefix)}" spellcheck="false" style="max-width:10rem">
              <div class="field-status muted">The run CSVs are named dsa_decomposition_&lt;prefix&gt;_round1_&lt;version&gt;_run&lt;N&gt;.csv (your initials).</div></div>
            <label for="s-python">Python</label>
            <div class="field"><input id="s-python" type="text" value="${esc(s.python)}" placeholder="${esc(inf.python)}" spellcheck="false">
              <div class="field-status muted">Runs the scripts. Empty = the Python that runs this app.</div></div>
          </div>
          <div class="actions"><button class="btn primary" id="s-save">Save settings</button></div>
        </div>
        <div class="card">
          <h2>Python files and prompts</h2>
          <p class="muted">Chosen on each step's page (Round One, Round Two, Gap Fill). The scripts' own CONFIG blocks stay commented out; the app passes every path to them, like the 0_run_*.py controllers.</p>
          <div class="table-wrap"><table class="grid"><thead><tr><th>Step</th><th>Python files</th><th>Prompt</th></tr></thead><tbody>
            ${["round1", "round2"].map((r) => `<tr><td>${ROUND_NAME[r]}</td><td>${["extract_script", "compile_script", "check_script", "summary_script"].map((k) => `<code>${esc(s[r][k])}</code>`).join("<br>")}</td><td><code>${esc(s[r].prompt)}</code></td></tr>`).join("")}
            <tr><td>Gap Fill</td><td>${["flags_script", "targets_script", "api_script"].map((k) => `<code>${esc(s.gapfill[k])}</code>`).join("<br>")}</td><td><code>${esc(s.gapfill.prompt)}</code><br><code>${esc(s.gapfill.locator_prompt)}</code> (locator)</td></tr>
          </tbody></table></div>
        </div>`;
      $("s-save").addEventListener("click", () => {
        saveSettings({ pdf_dir: $("s-pdf").value.trim(), batch: $("s-batch").value.trim(), staff_reports_root: $("s-root").value.trim(),
          env_file: $("s-env").value.trim(), csv_prefix: $("s-prefix").value.trim() || "sl", python: $("s-python").value.trim() })
          .then(() => renderSettings(v));
      });
    }).catch((e) => { v.innerHTML = `<div class="card"><p class="bad-txt">${esc(e.message)}</p></div>`; });
  }

  // ------------------------------------------------------------------ script / prompt pickers
  function picker(id, label, kind, files, value, hint) {
    const opts = files.slice(); if (value && opts.indexOf(value) < 0) opts.unshift(value);
    return `<div class="pick-row">
      <div class="pick-lbl"><span class="kind ${kind === "code" ? "k-py" : "k-pr"}">${kind === "code" ? "PY" : "PROMPT"}</span>${esc(label)}${hint ? `<small class="muted">${esc(hint)}</small>` : ""}</div>
      <select id="${id}" data-kind="${kind}">${opts.map((f) => `<option${f === value ? " selected" : ""}>${esc(f)}</option>`).join("")}</select>
      <button class="btn small" type="button" data-view-file="${id}">View</button></div>`;
  }
  function wirePickers(root, section) {
    root.querySelectorAll("[data-view-file]").forEach((b) => b.addEventListener("click", () => {
      const sel = $(b.dataset.viewFile); viewFile(sel.dataset.kind, sel.value);
    }));
    root.querySelectorAll(".pick-row select").forEach((sel) => sel.addEventListener("change", () => {
      const patch = {}; patch[section] = {}; patch[section][sel.id.split("__")[1]] = sel.value;
      saveSettings(patch, true).then(() => toast(`${sel.value} will be used.`));
    }));
  }

  // ------------------------------------------------------------------ rounds
  const groupCounts = (c) => {
    c = c || {};
    const dis = (c.partial_match || 0) + (c.last_actual_year_differs || 0) + (c.table_found_differs || 0) + (c.missing_in_run || 0);
    return { fm: c.fully_match || 0, dis, none: c.no_table_in_all_runs || 0, fail: c.extraction_failed_in_all_runs || 0 };
  };
  function renderRound(v, rnd) {
    v.innerHTML = `<div class="card"><p class="muted">Loading…</p></div>`;
    Promise.all([loadInfo(), W.ov ? Promise.resolve(W.ov) : loadOverview()]).then(([I]) => {
      const s = I.settings[rnd], files = I.code_files, prompts = I.prompt_files;
      const r1s = (W.ov.round1 || []).filter((x) => x.has_check);
      const isR2 = rnd === "round2";
      v.innerHTML = `
        <div class="grid2">
          <div class="card">
            <div class="card-head"><h2>${ROUND_NAME[rnd]} · Python files and prompt</h2></div>
            <p class="muted">${isR2 ? "Re-reads the reports Round One could not agree on (from the chosen Round One version), with the Round Two pipeline." : "Reads the DSA table of every staff report in the PDF folder."} The extraction is repeated <b>${s.n_runs}</b> times with the same prompt, then the runs are compared.</p>
            <div class="pickers">
              ${picker(rnd + "__extract_script", "Extraction", "code", files, s.extract_script, isR2 ? "2a · reads the PDFs, calls the API" : "1a · reads the PDFs, calls the API")}
              ${picker(rnd + "__prompt", "Extraction prompt", "prompt", prompts, s.prompt)}
              ${picker(rnd + "__compile_script", "Compile JSON → CSV", "code", files, s.compile_script, "1b · once per run")}
              ${picker(rnd + "__check_script", "Compare the runs", "code", files, s.check_script, "1c · after all runs")}
              ${picker(rnd + "__summary_script", "Summary tables", "code", files, s.summary_script, "1d · after 1c")}
            </div>
          </div>
          <div class="card">
            <div class="card-head"><h2>Run ${ROUND_NAME[rnd]}</h2></div>
            <div class="form-grid tight">
              <span class="label">Staff reports</span>
              <div class="field"><div><code>${esc(I.info.pdf_dir.path)}</code></div>
                <div class="field-status ${I.info.pdf_dir.exists ? "ok" : "bad"}">${I.info.pdf_dir.exists ? fmtN(I.info.pdf_dir.n_pdfs) + " PDFs · batch " + esc(I.info.batch) : "Folder not found"} · <a href="#workflow/settings" class="lnk">change in Settings</a></div></div>
              ${isR2 ? `<label for="r-r1">Round One version</label>
              <div class="field"><select id="r-r1">${r1s.map((x) => { const g = groupCounts(x.counts_by_group); return `<option value="${esc(x.version)}">${esc(x.version)} · ${fmtN(g.dis)} with disagreement · ${fmtN(g.none)} no table · ${fmtN(g.fail)} failed</option>`; }).join("") || "<option value=''>No Round One results yet</option>"}</select>
                <div class="field-status muted">Its list of reports to check again is what Round Two re-reads.</div></div>
              <label for="r-cat">Reports to re-read</label>
              <div class="field"><select id="r-cat"><option value="">All reports to check again</option><option value="category_a_disagreement">Only the ones where the runs disagree</option><option value="category_b_no_table_in_all_runs">Only the ones with no table in any run</option><option value="category_c_extraction_failed_in_all_runs">Only the ones whose extraction failed</option></select></div>` : ""}
              <label for="r-ver">Version</label>
              <div class="field"><input id="r-ver" type="text" value="${esc(I.today)}" maxlength="40" style="max-width:12rem" spellcheck="false">
                <div class="field-status muted">The date, 8 digits (YYYYMMDD). Goes into the folder and file names: ${esc(rnd)}_&lt;version&gt;_run1 …</div></div>
              <label for="r-n">Number of runs</label>
              <div class="field"><input id="r-n" type="number" min="1" max="10" value="${s.n_runs}" style="max-width:6rem">
                <div class="field-status muted">Same code and prompt every time; each run is saved in its own folder, then all are compared.</div></div>
              <label for="r-first">First run number</label>
              <div class="field"><input id="r-first" type="number" min="1" value="1" style="max-width:6rem">
                <div class="field-status muted">Leave 1. To add runs to a version (after a failed run), give the next number.</div></div>
            </div>
            <div class="actions"><button class="btn primary" id="r-run">▶ Run ${ROUND_NAME[rnd]}</button><span class="muted small-txt">Calls the API; can take hours. You can keep using the app meanwhile.</span></div>
            <div data-job-slot="${rnd}"></div>
          </div>
        </div>
        <div class="card">
          <div class="card-head"><h2>${ROUND_NAME[rnd]} versions · batch ${esc(I.info.batch)}</h2></div>
          <div id="versions-${rnd}"></div>
        </div>`;
      wirePickers(v, rnd);
      $("r-n").addEventListener("change", () => saveSettings({ [rnd]: { n_runs: +$("r-n").value } }, true).catch(() => {}));
      $("r-run").addEventListener("click", () => {
        const body = { version: $("r-ver").value.trim(), n_runs: +$("r-n").value, first_run: +$("r-first").value };
        if (isR2) { body.round1_version = $("r-r1").value; body.category = $("r-cat").value; }
        if (!confirm(`Start ${ROUND_NAME[rnd]}, version ${body.version}, ${body.n_runs} run(s)?`)) return;
        api("run/" + rnd, body).then(() => { toast("Started."); pollJob(); }).catch((e) => toast(e.message));
      });
      paintVersions(rnd);
      pollJob();
    }).catch((e) => { v.innerHTML = `<div class="card"><p class="bad-txt">${esc(e.message)}</p></div>`; });
  }
  function paintVersions(rnd) {
    const box = $("versions-" + rnd); if (!box || !W.ov) return;
    const list = W.ov[rnd] || [];
    if (!list.length) { box.innerHTML = `<p class="muted">No versions yet for this batch.</p>`; return; }
    box.innerHTML = `<div class="table-wrap"><table class="grid"><thead><tr>
      <th>Version</th><th>Runs</th><th class="num">Reports</th><th class="num">Fully matched</th><th class="num">With disagreement</th>
      <th class="num">No table</th><th class="num">Failed</th><th>Prompt</th><th>Last change</th><th></th></tr></thead><tbody>
      ${list.map((x) => {
        const g = groupCounts(x.counts_by_group);
        const rec = x.record || {};
        return `<tr><td><b>${esc(x.version)}</b>${rec.round1_version ? `<span class="sub">re-reads Round One ${esc(rec.round1_version)}</span>` : ""}</td>
          <td>${x.runs.length ? x.runs.map((n) => "run" + n).join(", ") : `<span class="muted">${x.n_runs || ""} (folders not on this computer)</span>`}</td>
          <td class="num">${fmtN(x.n_reports)}</td><td class="num ok-txt">${x.has_check ? fmtN(g.fm) : ""}</td>
          <td class="num warn-txt">${x.has_check ? fmtN(g.dis) : ""}</td><td class="num">${x.has_check ? fmtN(g.none) : ""}</td><td class="num">${x.has_check ? fmtN(g.fail) : ""}</td>
          <td><span class="path" title="${esc(rec.prompt || "")}">${esc(rec.prompt || "")}</span></td><td>${esc(fmtTime(x.modified))}</td>
          <td class="nowrap">${x.has_check ? `<a class="btn small primary" href="#workflow/review/${rnd}/${esc(x.version)}">Review results</a>` : '<span class="muted">not compared yet</span>'}
            ${rnd === "round2" && x.has_check ? `<a class="btn small" href="#workflow/hr/${esc(x.version)}">Human review →</a>` : ""}</td></tr>`;
      }).join("")}</tbody></table></div>`;
  }

  // ------------------------------------------------------------------ review results
  function renderReview(v, rnd, version) {
    v.innerHTML = `<div class="card"><p class="muted">Loading ${esc(ROUND_NAME[rnd] || rnd)} version ${esc(version)}…</p></div>`;
    api(`review/${rnd}/${encodeURIComponent(version)}`).then((d) => {
      W.review = { d, tab: "fm", q: "", group: "", page: 0, open: null };
      const g = groupCounts(d.counts_by_group);
      v.innerHTML = `
        <div class="crumbs"><a href="#workflow/${rnd}" class="lnk">← ${ROUND_NAME[rnd]}</a><span class="muted">/ Review results · version ${esc(version)}</span></div>
        <div class="card">
          <div class="card-head"><h2>${ROUND_NAME[rnd]} · version ${esc(version)} · ${d.n_runs} runs compared</h2>
            ${rnd === "round2" ? `<a class="btn primary" href="#workflow/hr/${esc(version)}">Go to Human Review →</a>` : `<a class="btn" href="#workflow/round2">Round Two re-reads the disagreements →</a>`}</div>
          <div class="tiles">
            <div class="tile"><span class="lbl">Reports</span><span class="val">${fmtN(d.n_reports)}</span></div>
            <div class="tile t-ok"><span class="lbl"><i></i>Fully matched</span><span class="val">${fmtN(g.fm)}</span><span class="sub muted">${pct(g.fm, d.n_reports)} · ${fmtN(d.rows_ready)} rows ready to append</span></div>
            <div class="tile t-warn"><span class="lbl"><i></i>With disagreement</span><span class="val">${fmtN(g.dis)}</span><span class="sub muted">${fmtN(d.rows_differing)} differing rows</span></div>
            <div class="tile t-mute"><span class="lbl"><i></i>No table in any run</span><span class="val">${fmtN(g.none)}</span></div>
            <div class="tile t-mute"><span class="lbl"><i></i>Extraction failed</span><span class="val">${fmtN(g.fail)}</span></div>
          </div>
          <p class="muted small-txt">Compared: the report is in every run, table found, last actual year, and every line item lined up by hierarchy id. Not compared: label wording. ${d.run_csvs_available ? "The runs' CSVs are on this computer, so every run's labels are shown." : "The runs' own CSVs are not on this computer; values come from the check files (matched rows + differing rows)."}</p>
        </div>
        <div class="card">
          <div class="card-head">
            <div class="seg big" role="tablist">
              <button type="button" data-rtab="fm" aria-pressed="true">Fully matched <span class="badge">${fmtN(g.fm)}</span></button>
              <button type="button" data-rtab="dis" aria-pressed="false">With disagreement <span class="badge">${fmtN(d.n_reports - g.fm)}</span></button>
            </div>
            <div class="filters">
              <label>Country or report <input type="search" id="rv-q" placeholder="Search" autocomplete="off"></label>
              <label id="rv-group-wrap" hidden>Group <select id="rv-group"><option value="">All</option>${Object.keys(GROUPS).filter((k) => k !== "fully_match" && d.counts_by_group[k]).map((k) => `<option value="${k}">${GROUPS[k][0]} (${fmtN(d.counts_by_group[k])})</option>`).join("")}</select></label>
            </div>
          </div>
          <div class="table-wrap rv-wrap"><table class="grid rv" id="rv-table"><thead></thead><tbody></tbody></table></div>
          <div class="pager"><span class="muted" id="rv-count"></span><button class="btn" id="rv-prev">Previous</button><span id="rv-page" class="muted"></span><button class="btn" id="rv-next">Next</button></div>
        </div>`;
      v.querySelectorAll("[data-rtab]").forEach((b) => b.addEventListener("click", () => {
        W.review.tab = b.dataset.rtab; W.review.page = 0; W.review.open = null;
        v.querySelectorAll("[data-rtab]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
        $("rv-group-wrap").hidden = W.review.tab !== "dis"; paintReview();
      }));
      $("rv-q").addEventListener("input", () => { W.review.q = $("rv-q").value.trim().toLowerCase(); W.review.page = 0; paintReview(); });
      $("rv-group").addEventListener("change", () => { W.review.group = $("rv-group").value; W.review.page = 0; paintReview(); });
      $("rv-prev").addEventListener("click", () => { W.review.page--; paintReview(); });
      $("rv-next").addEventListener("click", () => { W.review.page++; paintReview(); });
      paintReview();
    }).catch((e) => { v.innerHTML = `<div class="crumbs"><a href="#workflow/${esc(rnd)}" class="lnk">← back</a></div><div class="card"><p class="bad-txt">${esc(e.message)}</p></div>`; });
  }
  function paintReview() {
    const R = W.review, d = R.d, size = 50;
    let list = d.reports.filter((r) => (R.tab === "fm" ? r.group === "fully_match" : r.group !== "fully_match"));
    if (R.group && R.tab === "dis") list = list.filter((r) => r.group === R.group);
    if (R.q) list = list.filter((r) => (r.country || "").toLowerCase().indexOf(R.q) >= 0 || (r.pdf || "").toLowerCase().indexOf(R.q) >= 0);
    const pages = Math.max(1, Math.ceil(list.length / size)); R.page = Math.max(0, Math.min(R.page, pages - 1));
    const slice = list.slice(R.page * size, (R.page + 1) * size);
    const thead = $("rv-table").querySelector("thead"), tbody = $("rv-table").querySelector("tbody");
    if (R.tab === "fm") {
      thead.innerHTML = `<tr><th>Country</th><th>Report date</th><th>Last actual year</th>${TOP.map((t) => `<th class="num" title="hierarchy id ${t[0]}"><span class="hid">${t[0]}</span> ${t[1]}</th>`).join("")}<th class="num">Rows</th></tr>`;
      tbody.innerHTML = slice.map((r) => `<tr class="clickable" data-jf="${esc(r.json_file)}"><td><span class="caret">▸</span>${esc(r.country)}</td><td>${esc(stemDate(r.pdf))}</td><td>${esc(r.lay || "")}</td>
        ${TOP.map((t) => `<td class="num">${esc(r.top[t[0]] == null ? "" : r.top[t[0]])}</td>`).join("")}<td class="num">${fmtN(r.rows_compared)}</td></tr>`).join("");
    } else {
      thead.innerHTML = `<tr><th>Country</th><th>Report date</th><th>Group</th>${Array.from({ length: d.n_runs }, (_, i) => `<th>Run ${i + 1} year</th>`).join("")}<th class="num">Rows differing</th><th class="num">Rows compared</th></tr>`;
      tbody.innerHTML = slice.map((r) => {
        const ys = (r.lay_by_run || "").split("|");
        const same = ys.every((y) => y === ys[0]);
        return `<tr class="clickable" data-jf="${esc(r.json_file)}"><td><span class="caret">▸</span>${esc(r.country)}</td><td>${esc(stemDate(r.pdf))}</td><td>${groupBadge(r.group)}</td>
          ${Array.from({ length: d.n_runs }, (_, i) => `<td class="${same ? "" : "cell-diff"}">${esc(ys[i] || "—")}</td>`).join("")}
          <td class="num">${r.rows_differing ? `<b class="warn-txt">${fmtN(r.rows_differing)}</b>` : "0"}</td><td class="num">${fmtN(r.rows_compared)}</td></tr>`;
      }).join("");
    }
    if (!slice.length) tbody.innerHTML = `<tr><td colspan="12" class="muted">No reports.</td></tr>`;
    tbody.querySelectorAll("tr[data-jf]").forEach((tr) => tr.addEventListener("click", () => toggleReportRow(tr)));
    $("rv-count").textContent = `${fmtN(list.length)} report(s)`;
    $("rv-page").textContent = `Page ${R.page + 1} of ${pages}`;
    $("rv-prev").disabled = R.page === 0; $("rv-next").disabled = R.page >= pages - 1;
  }
  function toggleReportRow(tr) {
    const next = tr.nextElementSibling;
    if (next && next.classList.contains("detail-row")) { next.remove(); tr.classList.remove("open"); return; }
    tr.classList.add("open");
    const cols = tr.children.length;
    const row = h(`<tr class="detail-row"><td colspan="${cols}"><div class="muted">Loading…</div></td></tr>`);
    tr.after(row);
    const d = W.review.d;
    api(`review/${d.round}/${encodeURIComponent(d.version)}/report`, null, { json_file: tr.dataset.jf }).then((x) => {
      row.firstElementChild.innerHTML = reportDetailHtml(x);
      row.querySelectorAll("[data-pdf]").forEach((a) => a.addEventListener("click", (e) => { e.stopPropagation(); }));
    }).catch((e) => { row.firstElementChild.innerHTML = `<span class="bad-txt">${esc(e.message)}</span>`; });
  }
  function reportDetailHtml(x) {
    const n = x.n_runs, m = x.meta || {};
    const lays = x.lay_by_run || [];
    const pdfs = (x.pdfs || []).map((p) => `<a class="btn small" data-pdf target="_blank" href="${pdfUrl(p)}">${esc(p.label)} ↗</a>`).join(" ");
    return `<div class="rd">
      <div class="rd-head"><div><b>${esc(m.country || "")}</b> · ${esc(m.pdf_file_name || x.json_file)}<div class="muted small-txt">${esc(m.table_number || "")} ${esc(m.table_title || "")}${m.page_pdf ? " · PDF page " + esc(m.page_pdf) : ""}</div></div>
        <div class="head-actions">${pdfs || '<span class="muted small-txt">PDF not found on this computer</span>'}</div></div>
      ${x.error ? `<p class="bad-txt small-txt">${esc(x.error)}</p>` : ""}
      <table class="grid rd-table"><thead><tr><th>ID</th><th>Line item (run 1)</th>${Array.from({ length: n }, (_, i) => `<th class="num">Run ${i + 1}${lays[i] ? `<span class="sub">${esc(lays[i])}</span>` : ""}</th>`).join("")}</tr></thead><tbody>
      ${x.rows.length ? x.rows.map((r) => `<tr class="${r.same ? "" : "row-diff"}"><td><span class="hid lvl${r.level}">${esc(r.hierarchy_id)}</span></td>
          <td class="lbl-cell" style="padding-left:${10 + 14 * r.level}px" title="${esc(r.labels.filter((l, i, a) => l && a.indexOf(l) === i).join("  |  "))}">${esc(r.labels.find((l) => l) || "")}</td>
          ${r.values.map((val) => `<td class="num${r.same ? "" : " cell-diff"}">${val == null ? '<span class="muted">—</span>' : esc(val)}</td>`).join("")}</tr>`).join("")
        : `<tr><td colspan="${2 + n}" class="muted">No line items in any run.</td></tr>`}
      </tbody></table></div>`;
  }

  // ------------------------------------------------------------------ human review
  function renderHR(v, version, jf) {
    const versions = (W.ov ? W.ov.round2 : []).filter((x) => x.has_check);
    if (!W.ov) { loadOverview().then(() => renderHR(v, version, jf)); return; }
    version = version || W.ov.round2_selected || (versions[0] && versions[0].version);
    if (!version) {
      v.innerHTML = `<div class="card"><h2>Human Review</h2><p class="muted">Run Round Two first: Human Review works through the reports whose Round Two runs still disagree.</p></div>${appendCardHtml()}`;
      wireAppend(); return;
    }
    if (location.hash.split("/").length < 3) history.replaceState(null, "", `#workflow/hr/${version}`);
    v.innerHTML = `<div class="card"><p class="muted">Loading the review list…</p></div>`;
    api("hr/" + encodeURIComponent(version)).then((q) => {
      W.hr = { version, q, filter: store("hr_filter") || "todo", search: "", cur: null, item: null };
      v.innerHTML = `
        <div class="hr">
          <aside class="card hr-queue">
            <label class="field-inline">Round Two version <select id="hr-ver">${versions.map((x) => `<option${x.version === version ? " selected" : ""}>${esc(x.version)}</option>`).join("")}</select></label>
            <div class="hr-prog" id="hr-prog"></div>
            <div class="hr-filters">
              <select id="hr-filter"><option value="todo">To do</option><option value="all">All</option><option value="reviewed">Reviewed</option><option value="no_table">No DSA table</option><option value="skipped">Skipped</option></select>
              <input type="search" id="hr-search" placeholder="Search country" autocomplete="off">
            </div>
            <ul class="hr-list" id="hr-list"></ul>
          </aside>
          <section class="card hr-main" id="hr-main"><p class="muted">Pick a report on the left.</p></section>
        </div>
        ${appendCardHtml()}`;
      $("hr-filter").value = W.hr.filter;
      $("hr-ver").addEventListener("change", () => { location.hash = "#workflow/hr/" + $("hr-ver").value; });
      $("hr-filter").addEventListener("change", () => { W.hr.filter = $("hr-filter").value; store("hr_filter", W.hr.filter); paintQueue(); });
      $("hr-search").addEventListener("input", () => { W.hr.search = $("hr-search").value.trim().toLowerCase(); paintQueue(); });
      paintQueue();
      wireAppend(null, version);
      const start = jf || (q.items.find((i) => i.status === "todo") || q.items[0] || {}).json_file;
      if (start) openHRItem(start);
    }).catch((e) => { v.innerHTML = `<div class="card"><p class="bad-txt">${esc(e.message)}</p></div>${appendCardHtml()}`; wireAppend(); });
  }
  function queueFiltered() {
    const H = W.hr;
    return H.q.items.filter((i) => (H.filter === "all" || i.status === H.filter || (H.filter === "todo" && i.status === "todo")) &&
      (!H.search || (i.country || "").toLowerCase().indexOf(H.search) >= 0 || (i.pdf || "").toLowerCase().indexOf(H.search) >= 0));
  }
  function paintQueue() {
    const H = W.hr, c = H.q.counts, total = H.q.items.length;
    const done = total - c.todo;
    $("hr-prog").innerHTML = `<div class="bar-multi"><span class="b-rev" style="width:${(100 * c.reviewed) / Math.max(total, 1)}%"></span><span class="b-nt" style="width:${(100 * c.no_table) / Math.max(total, 1)}%"></span><span class="b-sk" style="width:${(100 * c.skipped) / Math.max(total, 1)}%"></span></div>
      <div class="small-txt"><b>${fmtN(done)}</b> of ${fmtN(total)} done · ${fmtN(c.reviewed)} reviewed · ${fmtN(c.no_table)} no table · ${fmtN(c.skipped)} skipped</div>`;
    const list = queueFiltered();
    $("hr-list").innerHTML = list.map((i) => `<li class="${i.json_file === H.cur ? "cur" : ""}" data-jf="${esc(i.json_file)}">
        <span class="st st-${i.status}" title="${esc(i.status)}"></span>
        <span class="q-main"><b>${esc(i.country)}</b> <span class="muted">${esc(stemDate(i.pdf))}</span><br>${groupBadge(i.group)}</span></li>`).join("") ||
      `<li class="muted empty-li">Nothing here.</li>`;
    $("hr-list").querySelectorAll("li[data-jf]").forEach((li) => li.addEventListener("click", () => openHRItem(li.dataset.jf)));
  }
  function openHRItem(jf) {
    const H = W.hr; H.cur = jf; paintQueue();
    const li = $("hr-list").querySelector(`li[data-jf="${CSS.escape(jf)}"]`); if (li) li.scrollIntoView({ block: "nearest" });
    history.replaceState(null, "", `#workflow/hr/${H.version}/${encodeURIComponent(jf)}`);
    $("hr-main").innerHTML = `<p class="muted">Loading ${esc(jf)}…</p>`;
    api(`hr/${encodeURIComponent(H.version)}/item`, null, { json_file: jf }).then((x) => { H.item = x; paintHRItem(); })
      .catch((e) => { $("hr-main").innerHTML = `<p class="bad-txt">${esc(e.message)}</p>`; });
  }
  function hrRowsInitial(x) {
    const rv = x.review;
    const byHid = {}; x.rows.forEach((r) => { byHid[r.hierarchy_id] = r; });
    if (rv && rv.status === "reviewed") {
      const ids = new Set(rv.rows.map((r) => r.hierarchy_id));
      const out = rv.rows.map((r) => ({ hierarchy_id: r.hierarchy_id, label_verbatim: r.label_verbatim, value: r.value, runs: (byHid[r.hierarchy_id] || {}).values || [] }));
      x.rows.forEach((r) => { if (!ids.has(r.hierarchy_id)) out.push({ hierarchy_id: r.hierarchy_id, label_verbatim: r.labels.find((l) => l) || "", value: "", runs: r.values, dropped: true }); });
      return out;
    }
    if (x.rows.length) {
      return x.rows.map((r) => ({ hierarchy_id: r.hierarchy_id, label_verbatim: majority(r.labels) || "", value: r.same ? (r.values[0] == null ? "" : r.values[0]) : "", runs: r.values, diff: !r.same }));
    }
    return (x.template || []).map((t) => ({ hierarchy_id: t.hierarchy_id, label_verbatim: t.label, value: "", runs: [], template: true }));
  }
  function majority(arr) {
    const c = {}; let best = null;
    arr.forEach((a) => { if (a == null) return; c[a] = (c[a] || 0) + 1; if (best == null || c[a] > c[best]) best = a; });
    return best;
  }
  function paintHRItem() {
    const H = W.hr, x = H.item, m = x.meta || {}, n = x.n_runs, rv = x.review || {};
    const items = queueFiltered(); const idx = items.findIndex((i) => i.json_file === H.cur);
    const lays = x.lay_by_run || [];
    const laySame = lays.length && lays.every((y) => y === lays[0]) && lays[0];
    const pdfs = x.pdfs || [];
    H.rows = hrRowsInitial(x);
    $("hr-main").innerHTML = `
      <div class="hr-head">
        <div><h2>${esc(m.country || x.json_file)} <span class="muted hr-date">${esc(stemDate(m.pdf_file_name))}</span></h2>
          <div class="muted small-txt">${esc(m.pdf_file_name || "")}${m.table_title ? " · " + esc(m.table_title) : ""}${m.report_title ? `<br>${esc(m.report_title)}` : ""}</div>
          <div class="hr-tags">${groupBadge(x.group)}${rv.status ? `<span class="gbadge st-badge-${esc(rv.status)}">Saved: ${esc(rv.status.replace("_", " "))} · ${fmtTime(rv.saved_at)}</span>` : ""}</div></div>
        <div class="head-actions"><span class="muted small-txt">${idx >= 0 ? `${idx + 1} of ${items.length}` : ""}</span>
          <button class="btn small" id="hr-prev" ${idx <= 0 ? "disabled" : ""}>← Previous</button><button class="btn small" id="hr-next" ${idx < 0 || idx >= items.length - 1 ? "disabled" : ""}>Next →</button></div>
      </div>
      <div class="hr-split">
        <div class="hr-pdf">
          <div class="pdf-tabs">${pdfs.map((p, i) => `<button type="button" class="pdf-tab" data-i="${i}" aria-pressed="${i === 0}">${esc(p.label)}</button>`).join("")}
            ${pdfs.length ? `<a class="btn small" id="pdf-open" target="_blank" href="${pdfUrl(pdfs[0])}">Open in new tab ↗</a>` : ""}</div>
          ${pdfs.length ? `<iframe class="pdf-frame" id="pdf-frame" title="Staff report pages" src="${pdfUrl(pdfs[0])}"></iframe>`
            : `<div class="pdf-missing"><b>PDF not found on this computer</b><p class="muted">${esc(m.pdf_file_name || "")}<br>The app looks in the selected pages of the Round Two runs, the PDF folder and the staff reports root folder (Settings).</p></div>`}
        </div>
        <div class="hr-form">
          <div class="lay-row">
            <label>Last actual year <input id="hr-lay" type="text" value="${esc(rv.last_actual_year || laySame || "")}" maxlength="12" spellcheck="false"></label>
            <div class="lay-chips">${lays.map((y, i) => `<button type="button" class="chip${laySame ? "" : " chip-diff"}" data-lay="${esc(y)}">Run ${i + 1}: ${esc(y || "—")}</button>`).join("")}</div>
            <label>Column label <input id="hr-col" type="text" value="${esc(rv.actual_column_label || m.actual_column_label || "")}" placeholder="as printed, e.g. 2023 or 2022/23" spellcheck="false"></label>
            <label>PDF page <input id="hr-page" type="text" value="${esc(rv.page_pdf || m.page_pdf || "")}" style="width:5rem" spellcheck="false"></label>
          </div>
          <div class="table-wrap hr-table-wrap"><table class="grid hr-table" id="hr-table">
            <thead><tr><th>ID</th><th>Line item</th>${Array.from({ length: n }, (_, i) => `<th class="num"><button type="button" class="link-btn" data-fill-run="${i}" title="Copy every Run ${i + 1} value into Final">Run ${i + 1} ⇢</button></th>`).join("")}<th class="num">Final value</th><th></th></tr></thead>
            <tbody></tbody></table></div>
          <div class="hr-tools"><button type="button" class="btn small" id="hr-add">+ Add line item</button>
            <span class="muted small-txt">Click a run's value to take it. Rows where the runs differ are highlighted. Keep the hierarchy id: it identifies the indicator (5 = other identified flows, 5.1 its first item …).</span></div>
          <label class="note-lbl">Note <textarea id="hr-note" rows="2" placeholder="Optional: what you checked, why a value was changed">${esc(rv.note || "")}</textarea></label>
          <div class="hr-msg bad-txt" id="hr-msg"></div>
          <div class="actions hr-actions">
            <button class="btn primary" id="hr-save" title="Ctrl+Enter">✓ Save as reviewed</button>
            <button class="btn" id="hr-notable">No DSA table in this report</button>
            <button class="btn" id="hr-skip">Skip for now</button>
            <span class="muted small-txt">Saving moves on to the next report to do.</span>
          </div>
        </div>
      </div>`;
    paintHRRows();
    $("hr-main").querySelectorAll(".pdf-tab").forEach((b) => b.addEventListener("click", () => {
      const p = pdfs[+b.dataset.i];
      $("pdf-frame").src = pdfUrl(p); $("pdf-open").href = pdfUrl(p);
      $("hr-main").querySelectorAll(".pdf-tab").forEach((x2) => x2.setAttribute("aria-pressed", String(x2 === b)));
    }));
    $("hr-main").querySelectorAll("[data-lay]").forEach((b) => b.addEventListener("click", () => { $("hr-lay").value = b.dataset.lay; if (!$("hr-col").value) $("hr-col").value = b.dataset.lay; }));
    $("hr-main").querySelectorAll("[data-fill-run]").forEach((b) => b.addEventListener("click", () => {
      const k = +b.dataset.fillRun; readHRRows();
      H.rows.forEach((r) => { if (r.runs && r.runs[k] != null) { r.value = r.runs[k]; r.dropped = false; } });
      paintHRRows();
    }));
    $("hr-add").addEventListener("click", () => { readHRRows(); H.rows.push({ hierarchy_id: "", label_verbatim: "", value: "", runs: [], added: true }); paintHRRows(); });
    $("hr-prev").addEventListener("click", () => openHRItem(items[idx - 1].json_file));
    $("hr-next").addEventListener("click", () => openHRItem(items[idx + 1].json_file));
    $("hr-save").addEventListener("click", () => saveHR("reviewed"));
    $("hr-notable").addEventListener("click", () => saveHR("no_table"));
    $("hr-skip").addEventListener("click", () => saveHR("skipped"));
  }
  function paintHRRows() {
    const H = W.hr, n = H.item.n_runs;
    const tb = $("hr-table").querySelector("tbody");
    tb.innerHTML = H.rows.map((r, i) => {
      const lvl = (r.hierarchy_id.match(/\./g) || []).length;
      const top = CAT_OF[(r.hierarchy_id || "")[0]] || "";
      return `<tr class="${r.diff ? "row-diff" : ""}${r.dropped ? " row-dropped" : ""}" data-i="${i}">
        <td><input class="in-hid" value="${esc(r.hierarchy_id)}" title="${esc(top)}" spellcheck="false" aria-label="Hierarchy id"></td>
        <td style="padding-left:${6 + 12 * lvl}px"><input class="in-lbl" value="${esc(r.label_verbatim)}" spellcheck="false" aria-label="Line item label"></td>
        ${Array.from({ length: n }, (_, k) => { const val = r.runs ? r.runs[k] : null; return `<td class="num">${val == null ? '<span class="muted">—</span>' : `<button type="button" class="take${r.diff ? " cell-diff" : ""}" data-k="${k}">${esc(val)}</button>`}</td>`; }).join("")}
        <td class="num"><input class="in-val" value="${esc(r.value == null ? "" : r.value)}" inputmode="decimal" spellcheck="false" aria-label="Final value"></td>
        <td><button type="button" class="x-btn" title="${r.dropped ? "Put this line item back" : "Leave this line item out"}">${r.dropped ? "↺" : "×"}</button></td></tr>`;
    }).join("") || `<tr><td colspan="${4 + n}" class="muted">No line items. Add them with “+ Add line item”.</td></tr>`;
    tb.querySelectorAll("tr[data-i]").forEach((tr) => {
      const i = +tr.dataset.i;
      tr.querySelectorAll(".take").forEach((b) => b.addEventListener("click", () => { readHRRows(); H.rows[i].value = H.rows[i].runs[+b.dataset.k]; H.rows[i].dropped = false; paintHRRows(); }));
      tr.querySelector(".x-btn").addEventListener("click", () => {
        readHRRows(); const r = H.rows[i];
        if (r.added && !r.hierarchy_id && !r.value) H.rows.splice(i, 1); else r.dropped = !r.dropped;
        paintHRRows();
      });
    });
  }
  function readHRRows() {
    const H = W.hr;
    $("hr-table").querySelectorAll("tbody tr[data-i]").forEach((tr) => {
      const r = H.rows[+tr.dataset.i];
      r.hierarchy_id = tr.querySelector(".in-hid").value.trim();
      r.label_verbatim = tr.querySelector(".in-lbl").value;
      r.value = tr.querySelector(".in-val").value.trim();
    });
  }
  function saveHR(status) {
    const H = W.hr; readHRRows();
    const body = { json_file: H.cur, status, last_actual_year: $("hr-lay").value.trim(), actual_column_label: $("hr-col").value.trim(),
      page_pdf: $("hr-page").value.trim(), note: $("hr-note").value.trim(),
      rows: H.rows.filter((r) => !r.dropped).map((r) => ({ hierarchy_id: r.hierarchy_id, label_verbatim: r.label_verbatim, value: r.value })) };
    if (status === "reviewed") {
      const blank = body.rows.filter((r) => r.value === "").length;
      if (blank && !confirm(`${blank} line item(s) have no final value and will be saved empty. Save anyway?`)) return;
    }
    $("hr-msg").textContent = "";
    api(`hr/${encodeURIComponent(H.version)}/save`, body).then(() => {
      const it = H.q.items.find((i) => i.json_file === H.cur);
      const before = queueFiltered(); const pos = before.findIndex((i) => i.json_file === H.cur);
      if (it) { if (it.status !== status) { H.q.counts[it.status]--; H.q.counts[status]++; } it.status = status; }
      toast(status === "reviewed" ? "Saved." : "Saved as " + status.replace("_", " ") + ".");
      paintQueue(); loadOverview().then(() => wireAppend(null, H.version));
      const after = queueFiltered();
      const nxt = after.find((i, k) => k >= pos && i.status === "todo" && i.json_file !== H.cur) || after.find((i) => i.status === "todo" && i.json_file !== H.cur);
      if (nxt) openHRItem(nxt.json_file); else { openHRItem(H.cur); toast("Every report in this list is done."); }
    }).catch((e) => { $("hr-msg").textContent = e.message; });
  }
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && W.view === "hr" && $("hr-save")) { e.preventDefault(); saveHR("reviewed"); }
  });

  // ------------------------------------------------------------------ ready to append (on the Human Review page)
  function appendCardHtml() {
    return `<div class="card" id="append-card"><div class="card-head"><h2>Ready to append to the panel database</h2></div><div id="append-body"><p class="muted">Loading…</p></div></div>`;
  }
  function wireAppend(r1, r2) {
    const box = $("append-body"); if (!box || !W.ov) return;
    const v1 = (W.ov.round1 || []).filter((x) => x.has_check), v2 = (W.ov.round2 || []).filter((x) => x.has_check);
    r1 = r1 || ($("ap-r1") && $("ap-r1").value) || W.ov.round1_selected; r2 = r2 || ($("ap-r2") && $("ap-r2").value) || W.ov.round2_selected;
    api("staging", null, { r1, r2 }).then((st) => {
      const latest = st.panel_latest;
      box.innerHTML = `
        <p class="muted">Three sets of rows, all in the same ${st.columns.length} columns, so they append directly: Round One's fully matched reports, Round Two's fully matched reports, and the reports you reviewed in Round Three. Each keeps its line items' hierarchy ids.</p>
        <div class="form-grid tight">
          <label for="ap-r1">Round One version</label><div class="field"><select id="ap-r1"><option value="">(none)</option>${v1.map((x) => `<option${x.version === st.round1_version ? " selected" : ""}>${esc(x.version)}</option>`).join("")}</select></div>
          <label for="ap-r2">Round Two version</label><div class="field"><select id="ap-r2"><option value="">(none)</option>${v2.map((x) => `<option${x.version === st.round2_version ? " selected" : ""}>${esc(x.version)}</option>`).join("")}</select>
            <div class="field-status muted">Round Three = the human review of this Round Two version.</div></div>
        </div>
        <div class="table-wrap"><table class="grid"><thead><tr><th></th><th>Source</th><th>Version</th><th class="num">Reports</th><th class="num">Rows</th><th>Status</th></tr></thead><tbody>
          ${st.parts.map((p) => `<tr><td><input type="checkbox" class="ap-inc" value="${p.source}" ${p.rows ? "checked" : ""} aria-label="Include ${esc(p.label)}"></td><td><i class="sw s-${p.source}"></i> ${esc(p.label)}</td><td>${esc(p.version)}</td>
            <td class="num">${fmtN(p.reports)}</td><td class="num">${fmtN(p.rows)}</td>
            <td>${p.source === "round3" && p.reviewed ? `${fmtN(p.to_review - p.reviewed.todo)} of ${fmtN(p.to_review)} done${p.reviewed.todo ? ` · <span class="warn-txt">${fmtN(p.reviewed.todo)} still to review</span>` : ' · <span class="ok-txt">complete</span>'}` : '<span class="ok-txt">ready</span>'}</td></tr>`).join("")}
          <tr class="tot"><td></td><td><b>Total</b></td><td></td><td class="num"><b>${fmtN(st.reports)}</b></td><td class="num"><b>${fmtN(st.rows)}</b></td><td></td></tr>
        </tbody></table></div>
        ${st.problems.length ? `<p class="bad-txt small-txt">Check: ${st.problems.map(esc).join("; ")}</p>` : `<p class="ok-txt small-txt">✓ Same columns in all three; every hierarchy id is well formed and matches its category.</p>`}
        <details class="small-txt"><summary class="muted">The ${st.columns.length} columns</summary><code>${st.columns.map(esc).join(", ")}</code></details>
        <div class="actions">
          <span>Append to: ${latest ? `<b>panel database v${esc(latest.stamp)}</b> (${fmtN(latest.rows)} rows) → a new version` : "<b>a new panel database</b> (none exists yet)"}</span>
          ${st.reports_already_in_panel ? `<label class="check"><input type="checkbox" id="ap-replace"> Replace the ${fmtN(st.reports_already_in_panel)} report(s) already in the panel (otherwise they are skipped)</label>` : ""}
          <button class="btn primary" id="ap-go" ${st.rows ? "" : "disabled"}>Append →</button>
        </div>`;
      $("ap-r1").addEventListener("change", () => wireAppend($("ap-r1").value || "-", $("ap-r2").value));
      $("ap-r2").addEventListener("change", () => wireAppend($("ap-r1").value, $("ap-r2").value || "-"));
      $("ap-go").addEventListener("click", () => {
        const include = Array.from(box.querySelectorAll(".ap-inc:checked")).map((c) => c.value);
        if (!include.length) { toast("Tick at least one source."); return; }
        if (!confirm("Append these rows as a new version of the panel database?")) return;
        api("panel/append", { round1_version: $("ap-r1").value, round2_version: $("ap-r2").value, include, replace_existing: !!($("ap-replace") && $("ap-replace").checked) })
          .then((r) => { toast(`Panel database v${r.stamp}: ${fmtN(r.rows)} rows.`); loadOverview(); wireAppend(); })
          .catch((e) => toast(e.message));
      });
    }).catch((e) => { box.innerHTML = `<p class="bad-txt">${esc(e.message)}</p>`; });
  }

  // ------------------------------------------------------------------ gap fill
  const CELLS = {
    o: ["Observed (Round 1-3 or earlier gap fill)", "c-o"], g: ["Gap: to fill", "c-g"], x: ["Gap: no later report to read it from", "c-x"],
    f: ["Filled", "c-f"], w: ["Filled, with a warning", "c-w"], u: ["Not filled (no actual value found)", "c-u"],
    n: ["Not filled: no later report", "c-x"], e: ["API error (run again)", "c-e"], ".": ["", "c-none"],
  };
  function renderGap(v, stamp) {
    Promise.all([loadInfo(), api("gap"), W.ov ? Promise.resolve(W.ov) : loadOverview()]).then(([I, gr]) => {
      const s = I.settings.gapfill, runs = gr.runs || [];
      stamp = stamp || (runs[0] && runs[0].stamp);
      const panels = W.ov.panel || [];
      v.innerHTML = `
        <div class="grid2">
          <div class="card">
            <h2>Gap Fill · Python files and prompts</h2>
            <p class="muted">Works on the whole panel: every country, every year from ${s.year_from} to ${s.year_to}. A missing country-year is read from the same country's later reports (T+2, then T+3, then T+4).</p>
            <div class="pickers">
              ${picker("gapfill__flags_script", "Find the gaps", "code", I.code_files, s.flags_script, "4a · no API")}
              ${picker("gapfill__targets_script", "Candidate reports", "code", I.code_files, s.targets_script, "4b · no API")}
              ${picker("gapfill__api_script", "Read the gap years", "code", I.code_files, s.api_script, "4c · calls the API")}
              ${picker("gapfill__prompt", "Gap fill prompt", "prompt", I.prompt_files, s.prompt)}
              ${picker("gapfill__locator_prompt", "Locator prompt", "prompt", I.prompt_files, s.locator_prompt, "finds the DSA pages when no selected pages exist")}
            </div>
          </div>
          <div class="card">
            <h2>1 · Find the gaps</h2>
            <div class="form-grid tight">
              <label for="gp-panel">Panel database</label>
              <div class="field"><select id="gp-panel">${panels.map((p) => `<option value="${esc(p.stamp)}">v${esc(p.stamp)} · ${fmtN(p.rows)} rows · ${fmtN(p.country_years)} country-years</option>`).join("") || "<option value=''>No panel database yet</option>"}</select>
                <div class="field-status muted">The state after Human Review: append the rounds first (Human Review page).</div></div>
              <span class="label">Years</span>
              <div class="field"><div class="inline"><input id="gp-y0" type="number" value="${s.year_from}" style="width:6rem"> – <input id="gp-y1" type="number" value="${s.year_to}" style="width:6rem"></div>
                <div class="field-status muted">Every country of the panel × every year in this range; a year before a country's first report or after its last one counts too.</div></div>
              <label for="gp-countries">Extra countries (optional)</label>
              <div class="field"><input id="gp-countries" type="text" placeholder="CSV with a country column, or a text file, one per line" spellcheck="false">
                <div class="field-status muted">Countries with no report in the panel at all. Empty = the panel's own countries.</div></div>
              <label for="gp-stamp">Version</label>
              <div class="field"><input id="gp-stamp" type="text" value="${esc(I.today)}" maxlength="40" style="max-width:12rem"></div>
            </div>
            <div class="actions"><button class="btn primary" id="gp-identify">Find the gaps</button><span class="muted small-txt">No API call; takes a few seconds.</span></div>
            <div data-job-slot="gap"></div>
          </div>
        </div>
        <div class="card" id="gap-card">
          <div class="card-head"><h2>Gap map</h2>
            <label class="field-inline">Version <select id="gp-run">${runs.map((r) => `<option${r.stamp === stamp ? " selected" : ""} value="${esc(r.stamp)}">${esc(r.stamp)} · panel v${esc(r.panel_version)} · ${esc((r.years || []).join("–"))}</option>`).join("") || "<option value=''>none yet</option>"}</select></label></div>
          <div id="gap-body"><p class="muted">${runs.length ? "Loading…" : "Find the gaps first."}</p></div>
        </div>`;
      wirePickers(v, "gapfill");
      $("gp-identify").addEventListener("click", () => {
        const body = { panel_version: $("gp-panel").value, year_from: +$("gp-y0").value, year_to: +$("gp-y1").value, stamp: $("gp-stamp").value.trim(), panel_countries_file: $("gp-countries").value.trim() };
        api("run/gap_identify", body).then(() => { toast("Finding the gaps…"); W.gap = { stamp: body.stamp }; history.replaceState(null, "", "#workflow/gap/" + body.stamp); pollJob(); })
          .catch((e) => toast(e.message));
      });
      $("gp-run").addEventListener("change", () => { location.hash = "#workflow/gap/" + $("gp-run").value; });
      if (stamp) loadGap(stamp);
      pollJob();
    }).catch((e) => { v.innerHTML = `<div class="card"><p class="bad-txt">${esc(e.message)}</p></div>`; });
  }
  function loadGap(stamp) {
    W.gap = Object.assign(W.gap && W.gap.stamp === stamp ? W.gap : { sort: store("gap_sort") || "gaps", q: "", onlyGaps: true }, { stamp });
    return api("gap/" + encodeURIComponent(stamp)).then((g) => { W.gap.d = g; paintGap(); }).catch((e) => { const b = $("gap-body"); if (b) b.innerHTML = `<p class="bad-txt">${esc(e.message)}</p>`; });
  }
  function paintGap() {
    const G = W.gap, d = G.d, box = $("gap-body"); if (!box) return;
    if (!d.ready) { box.innerHTML = `<p class="muted">The gaps of version ${esc(d.stamp)} are being identified…</p>`; return; }
    const c = d.counts, filled = (c.f || 0) + (c.w || 0);
    const gapsTotal = (c.g || 0) + (c.x || 0) + filled + (c.u || 0) + (c.n || 0) + (c.e || 0);
    const rec = d.record;
    const running = W.job && (W.job.state === "running" || W.job.state === "starting") && W.job.links && W.job.links.gap === d.stamp;
    box.innerHTML = `
      <div class="tiles">
        <div class="tile"><span class="lbl">Countries × years</span><span class="val">${fmtN(d.countries.length)} × ${fmtN(d.years.length)}</span><span class="sub muted">${fmtN(d.countries.length * d.years.length)} country-years</span></div>
        <div class="tile"><span class="lbl"><i class="c-o"></i>Observed</span><span class="val">${fmtN(c.o || 0)}</span><span class="sub muted">${pct(c.o || 0, d.countries.length * d.years.length)}</span></div>
        <div class="tile"><span class="lbl"><i class="c-g"></i>Gaps</span><span class="val">${fmtN(gapsTotal)}</span><span class="sub muted">${fmtN((c.x || 0) + (c.n || 0))} with no later report</span></div>
        <div class="tile"><span class="lbl"><i class="c-f"></i>Filled</span><span class="val">${fmtN(filled)}</span><span class="sub muted">${pct(filled, gapsTotal)} of the gaps · ${fmtN(d.rows_ready)} rows ready</span></div>
        <div class="tile"><span class="lbl"><i class="c-u"></i>Not filled</span><span class="val">${fmtN((c.u || 0) + (c.n || 0))}</span><span class="sub muted">${fmtN(c.e || 0)} API errors to retry</span></div>
      </div>
      <div class="gap-steps">
        <div class="gstep"><b>2 · Read the gap years</b>
          <div class="inline"><label class="small-txt">Only the first <input id="gf-limit" type="number" min="1" placeholder="all" style="width:5rem"> gap years</label>
            <label class="small-txt">Countries <input id="gf-countries" type="text" placeholder="all, or A,B,C" style="width:12rem"></label></div>
          <div class="inline"><button class="btn" id="gf-dry">Dry run (no API)</button><button class="btn primary" id="gf-fill" ${running ? "disabled" : ""}>▶ Fill the gaps (API)</button>
            <button class="btn" id="gf-collect" title="Rebuild the result files from the answers already saved, without calling the API">Rebuild results</button></div>
          <div class="muted small-txt">A stopped run picks up where it left off: gap years already filled are not asked again. The map turns green as the gaps fill.</div></div>
        <div class="gstep"><b>3 · Append to the panel database</b>
          <div class="muted small-txt">${fmtN(d.rows_ready)} rows (${fmtN(filled)} country-years), same columns as Round 1-3, <code>source_round = gapfill</code>, <code>gapfill_run = ${esc(d.stamp)}</code>.</div>
          <div class="inline"><button class="btn primary" id="gf-append" ${d.rows_ready && !rec.appended_as ? "" : "disabled"}>Append →</button>
            ${rec.appended_as ? `<span class="ok-txt small-txt">Appended as panel v${esc(rec.appended_as)}</span>` : ""}</div></div>
      </div>
      <div class="gap-tools">
        <div class="legend">${["o", "g", "x", "f", "w", "u", "e"].map((k) => `<span><i class="${CELLS[k][1]}"></i>${CELLS[k][0]}</span>`).join("")}</div>
        <div class="inline">
          <label class="small-txt">Sort <select id="gm-sort"><option value="gaps">Most gaps first</option><option value="name">A–Z</option></select></label>
          <label class="check small-txt"><input type="checkbox" id="gm-only" ${G.onlyGaps ? "checked" : ""}> Only countries with gaps</label>
          <input type="search" id="gm-q" placeholder="Country" value="${esc(G.q)}" style="width:10rem">
        </div>
      </div>
      <div class="gap-map" id="gap-map"><div class="tip" id="gm-tip"></div></div>`;
    $("gm-sort").value = G.sort;
    $("gm-sort").addEventListener("change", () => { G.sort = $("gm-sort").value; store("gap_sort", G.sort); drawGapMap(); });
    $("gm-only").addEventListener("change", () => { G.onlyGaps = $("gm-only").checked; drawGapMap(); });
    $("gm-q").addEventListener("input", () => { G.q = $("gm-q").value.trim().toLowerCase(); drawGapMap(); });
    const fill = (mode) => {
      const body = { stamp: d.stamp, mode, limit: $("gf-limit").value || null, countries: $("gf-countries").value.trim() || null };
      if (mode === "fill" && !confirm("Start reading the gap years with the API?")) return;
      api("run/gap_fill", body).then(() => { toast("Started."); pollJob(); }).catch((e) => toast(e.message));
    };
    $("gf-dry").addEventListener("click", () => fill("dry_run"));
    $("gf-fill").addEventListener("click", () => fill("fill"));
    $("gf-collect").addEventListener("click", () => fill("collect"));
    $("gf-append").addEventListener("click", () => {
      if (!confirm(`Append ${fmtN(d.rows_ready)} gap fill rows as a new version of the panel database?`)) return;
      api("gap/append", { stamp: d.stamp }).then((r) => { toast(`Panel database v${r.stamp}: ${fmtN(r.rows)} rows.`); loadOverview(); loadGap(d.stamp); }).catch((e) => toast(e.message));
    });
    drawGapMap();
    clearTimeout(paintGap._t);
    if (running) paintGap._t = setTimeout(() => { if (W.view === "gap" && W.gap && W.gap.stamp === d.stamp) loadGap(d.stamp); }, 4000);
  }
  function drawGapMap() {
    const G = W.gap, d = G.d, wrap = $("gap-map"); if (!wrap) return;
    const gapCh = /[gxfwune]/;
    let rows = d.countries.map((c, i) => ({ c, i, row: d.grid[i], n: (d.grid[i].match(/[gxfwune]/g) || []).length }));
    if (G.onlyGaps) rows = rows.filter((r) => r.n > 0);
    if (G.q) rows = rows.filter((r) => r.c.toLowerCase().indexOf(G.q) >= 0);
    rows.sort(G.sort === "name" ? (a, b) => a.c.localeCompare(b.c) : (a, b) => b.n - a.n || a.c.localeCompare(b.c));
    const cw = 24, ch = 15, left = 200, top = 70, ny = d.years.length;
    const W2 = left + ny * cw + 50, H2 = top + rows.length * ch + 6;
    const perYear = d.years.map((_, j) => d.grid.reduce((s, row) => s + (gapCh.test(row[j]) ? 1 : 0), 0));
    const perYearFilled = d.years.map((_, j) => d.grid.reduce((s, row) => s + (/[fw]/.test(row[j]) ? 1 : 0), 0));
    const maxY = Math.max(1, ...perYear);
    let svg = `<svg viewBox="0 0 ${W2} ${H2}" width="${W2}" height="${H2}" role="img" aria-label="Country by year gap map">`;
    svg += `<defs><pattern id="hatch" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="4" height="4" class="c-x-bg"/><line x1="0" y1="0" x2="0" y2="4" class="hatch-line"/></pattern></defs>`;
    d.years.forEach((y, j) => {
      const x = left + j * cw, bh = (34 * perYear[j]) / maxY, fh = (34 * perYearFilled[j]) / maxY;
      svg += `<rect x="${x + 3}" y="${40 - bh}" width="${cw - 6}" height="${bh}" class="c-g"><title>${y}: ${perYear[j]} gaps, ${perYearFilled[j]} filled</title></rect>`;
      svg += `<rect x="${x + 3}" y="${40 - fh}" width="${cw - 6}" height="${fh}" class="c-f"/>`;
      svg += `<text x="${x + cw / 2}" y="${top - 12}" text-anchor="middle" class="yr">${String(y).slice(2)}</text>`;
    });
    svg += `<text x="${left - 8}" y="${top - 12}" text-anchor="end" class="yr">'yy</text><text x="${left - 8}" y="22" text-anchor="end" class="yr">gaps / year</text>`;
    rows.forEach((r, k) => {
      const y = top + k * ch;
      svg += `<text x="${left - 8}" y="${y + ch - 4}" text-anchor="end" class="cn">${esc(r.c.length > 30 ? r.c.slice(0, 29) + "…" : r.c)}</text>`;
      for (let j = 0; j < ny; j++) {
        const code = r.row[j], cls = (CELLS[code] || CELLS["."])[1];
        svg += `<rect x="${left + j * cw + 1}" y="${y + 1}" width="${cw - 2}" height="${ch - 2}" rx="2" class="${cls}" ${code === "x" || code === "n" ? 'fill="url(#hatch)"' : ""} data-i="${r.i}" data-j="${j}"/>`;
      }
      svg += `<text x="${left + ny * cw + 6}" y="${y + ch - 4}" class="cnt">${r.n || ""}</text>`;
    });
    svg += "</svg>";
    wrap.innerHTML = `<div class="tip" id="gm-tip"></div>` + (rows.length ? svg : `<p class="muted">No country matches.</p>`);
    const tip = $("gm-tip");
    wrap.onmousemove = (e) => {
      const t = e.target; if (!t.dataset || t.dataset.i == null) { tip.style.display = "none"; return; }
      const i = +t.dataset.i, j = +t.dataset.j, code = d.grid[i][j], det = d.detail[i + "|" + j];
      tip.innerHTML = `<b>${esc(d.countries[i])} · ${d.years[j]}</b>${esc((CELLS[code] || ["—"])[0])}` +
        (det ? `<div class="tip-h">${esc(det.final_status)}${det.source_report ? " · from " + esc(det.source_report) + " (T+" + esc(det.source_offset_years) + ")" : ""}</div>${det.last_failure_status ? `<div class="tip-h">last try: ${esc(det.last_failure_status)}</div>` : ""}${det.warnings ? `<div class="tip-h">${esc(det.warnings)}</div>` : ""}` : "");
      const rb = wrap.getBoundingClientRect();
      tip.style.display = "block"; tip.style.left = (e.clientX - rb.left + wrap.scrollLeft + 14) + "px"; tip.style.top = (e.clientY - rb.top + wrap.scrollTop + 10) + "px";
    };
    wrap.onmouseleave = () => { tip.style.display = "none"; };
  }

  // ------------------------------------------------------------------ panel database
  function renderPanel(stamp) {
    const v = $("panel-view");
    v.innerHTML = `<div class="card"><p class="muted">Loading…</p></div>`;
    api("panel").then((pv) => {
      const versions = pv.versions || [];
      stamp = stamp || (versions[0] && versions[0].stamp);
      const importCard = `<div class="card"><h2>${versions.length ? "Import a merged CSV as a new version" : "Start the panel database"}</h2>
        <p class="muted">The panel database is the merged result of every round: Round 1 and Round 2 fully matched reports, Round 3 human review, and Gap Fill, in the same ${21} columns. ${versions.length ? "" : "Start from the merged file you already have, or append Round 1-3 from the Human Review page."}</p>
        <div class="inline"><select id="pi-file">${(pv.importable || []).map((f) => `<option>${esc(f)}</option>`).join("")}</select><input id="pi-path" type="text" placeholder="or another path" style="min-width:20rem" spellcheck="false">
        <button class="btn ${versions.length ? "" : "primary"}" id="pi-go">Import</button></div></div>`;
      if (!stamp) { v.innerHTML = importCard; wireImport(); return; }
      v.innerHTML = `
        <div class="card">
          <div class="card-head"><h2>Panel database</h2>
            <div class="head-actions"><label class="field-inline">Version <select id="pd-ver">${versions.map((x) => `<option value="${esc(x.stamp)}"${x.stamp === stamp ? " selected" : ""}>v${esc(x.stamp)} · ${fmtN(x.rows)} rows</option>`).join("")}</select></label>
              <a class="btn" href="/api/wf/panel/${encodeURIComponent(stamp)}/download">Download CSV</a></div></div>
          <div class="tiles" id="pd-tiles"></div>
          <div class="chart" id="pd-chart"></div>
          <div class="legend legend-below">${Object.keys(SRC).map((k) => `<span><i class="sw s-${k}"></i>${SRC[k]}</span>`).join("")}</div>
        </div>
        <div class="card">
          <div class="card-head"><h2>Rows</h2></div>
          <div class="filters">
            <label>Country <input id="pd-country" type="search" placeholder="Search" autocomplete="off"></label>
            <label>Year <select id="pd-year"><option value="">All</option></select></label>
            <label>Source <select id="pd-source"><option value="">All</option>${Object.keys(SRC).map((k) => `<option value="${k}">${SRC[k]}</option>`).join("")}</select></label>
            <label>Hierarchy id <input id="pd-hid" type="text" placeholder="e.g. 5" style="width:6rem"></label>
            <label class="check"><input type="checkbox" id="pd-top"> Top level only</label>
            <span class="muted" id="pd-count"></span>
          </div>
          <div class="table-wrap pd-wrap"><table class="grid pd" id="pd-table"><thead></thead><tbody></tbody></table></div>
          <div class="pager"><button class="btn" id="pd-prev">Previous</button><span class="muted" id="pd-page"></span><button class="btn" id="pd-next">Next</button></div>
        </div>
        <div class="card">
          <h2>Version history</h2>
          <div class="table-wrap"><table class="grid"><thead><tr><th>Version</th><th>Created</th><th>From</th><th>Added</th><th class="num">Rows</th><th class="num">Country-years</th><th>Note</th></tr></thead><tbody>
          ${versions.map((x) => `<tr><td><a class="lnk" href="#panel/${esc(x.stamp)}"><b>v${esc(x.stamp)}</b></a></td><td>${esc(fmtTime(x.created))}</td><td>${x.parent ? "v" + esc(x.parent) : '<span class="muted">—</span>'}</td>
            <td>${(x.added || []).map((a) => `<span class="nowrap"><i class="sw s-${esc(a.source)}"></i>${esc(SRC[a.source] || a.source)}${a.version ? " " + esc(a.version) : ""}: ${fmtN(a.rows_appended != null ? a.rows_appended : a.rows)}</span>`).join("<br>")}</td>
            <td class="num">${fmtN(x.rows)}</td><td class="num">${fmtN(x.country_years)}</td><td class="small-txt">${esc(x.note || "")}</td></tr>`).join("")}
          </tbody></table></div>
        </div>
        ${importCard}`;
      wireImport();
      $("pd-ver").addEventListener("change", () => { location.hash = "#panel/" + $("pd-ver").value; });
      W.panel = { stamp, page: 0 };
      ["pd-country", "pd-year", "pd-source", "pd-hid", "pd-top"].forEach((id) => $(id).addEventListener("input", () => { W.panel.page = 0; loadPanelRows(); }));
      $("pd-prev").addEventListener("click", () => { W.panel.page--; loadPanelRows(); });
      $("pd-next").addEventListener("click", () => { W.panel.page++; loadPanelRows(); });
      loadPanelRows(true);
    }).catch((e) => { v.innerHTML = `<div class="card"><p class="bad-txt">${esc(e.message)}</p></div>`; });
  }
  function wireImport() {
    const go = $("pi-go"); if (!go) return;
    go.addEventListener("click", () => {
      const csv = $("pi-path").value.trim() || $("pi-file").value;
      if (!csv) return;
      api("panel/import", { csv }).then((r) => { toast(`Imported as v${r.stamp} (${fmtN(r.rows)} rows).`); loadOverview(); location.hash = "#panel/" + r.stamp; renderPanel(r.stamp); })
        .catch((e) => toast(e.message));
    });
  }
  function loadPanelRows(first) {
    const P = W.panel;
    const q = { country: $("pd-country").value.trim(), year: $("pd-year").value, source: $("pd-source").value, hid: $("pd-hid").value.trim(), top_only: $("pd-top").checked ? "1" : "", page: P.page, size: 100 };
    api(`panel/${encodeURIComponent(P.stamp)}/data`, null, q).then((d) => {
      if (first) {
        $("pd-year").innerHTML = `<option value="">All</option>` + d.years.map((y) => `<option>${y}</option>`).join("");
        const s = d.stats, bs = s.by_source || {};
        $("pd-tiles").innerHTML = `
          <div class="tile"><span class="lbl">Rows</span><span class="val">${fmtN(s.rows)}</span><span class="sub muted">${d.columns.length} columns</span></div>
          <div class="tile"><span class="lbl">Reports</span><span class="val">${fmtN(s.reports)}</span></div>
          <div class="tile"><span class="lbl">Countries</span><span class="val">${fmtN(s.countries)}</span></div>
          <div class="tile"><span class="lbl">Country-years</span><span class="val">${fmtN(s.country_years)}</span></div>
          ${Object.keys(SRC).map((k) => `<div class="tile"><span class="lbl"><i class="sw s-${k}"></i>${SRC[k]}</span><span class="val">${fmtN(bs[k] || 0)}</span><span class="sub muted">rows</span></div>`).join("")}`;
        drawPanelChart(d);
      }
      const cols = d.columns;
      $("pd-table").querySelector("thead").innerHTML = "<tr>" + cols.map((c) => `<th>${esc(c)}</th>`).join("") + "</tr>";
      $("pd-table").querySelector("tbody").innerHTML = d.rows.map((r) => "<tr>" + r.map((v2, k) => {
        const c = cols[k];
        if (c === "source_round") return `<td><i class="sw s-${esc(v2)}"></i>${esc(SRC[v2] || v2 || "")}</td>`;
        if (c === "hierarchy_id") return `<td><span class="hid">${esc(v2)}</span></td>`;
        return `<td${c === "value" ? ' class="num"' : ""}${["report_title", "consultation_type", "table_title"].indexOf(c) >= 0 ? ` class="clip" title="${esc(v2)}"` : ""}>${esc(v2 == null ? "" : v2)}</td>`;
      }).join("") + "</tr>").join("") || `<tr><td colspan="${cols.length}" class="muted">No rows.</td></tr>`;
      const pages = Math.max(1, Math.ceil(d.n_filtered / d.size));
      $("pd-count").textContent = `${fmtN(d.n_filtered)} of ${fmtN(d.stats.rows)} rows`;
      $("pd-page").textContent = `Page ${d.page + 1} of ${pages}`;
      $("pd-prev").disabled = d.page === 0; $("pd-next").disabled = d.page >= pages - 1;
    }).catch((e) => toast(e.message));
  }
  function drawPanelChart(d) {
    const years = d.years.filter((y) => +y >= 1995);
    const keys = Object.keys(SRC);
    const tot = years.map((y) => keys.reduce((s, k) => s + ((d.by_year[y] || {})[k] || 0), 0));
    const max = Math.max(1, ...tot), w = 900, hgt = 220, left = 40, bottom = 24, bw = (w - left) / Math.max(years.length, 1);
    let svg = `<svg viewBox="0 0 ${w} ${hgt}" role="img" aria-label="Country-years by year and source">`;
    [0, 0.5, 1].forEach((f) => { const y = hgt - bottom - f * (hgt - bottom - 10); svg += `<line x1="${left}" x2="${w}" y1="${y}" y2="${y}" class="grid-line"/><text x="${left - 6}" y="${y + 4}" text-anchor="end">${Math.round(f * max)}</text>`; });
    years.forEach((y, i) => {
      let acc = 0; const x = left + i * bw;
      keys.forEach((k) => {
        const n = (d.by_year[y] || {})[k] || 0; if (!n) return;
        const hh = (n / max) * (hgt - bottom - 10), yy = hgt - bottom - ((acc + n) / max) * (hgt - bottom - 10);
        svg += `<rect x="${x + 2}" y="${yy}" width="${Math.max(1, bw - 4)}" height="${hh}" class="f-${k}"><title>${y} · ${SRC[k]}: ${n} country-years</title></rect>`;
        acc += n;
      });
      if (years.length <= 32 || i % 2 === 0) svg += `<text x="${x + bw / 2}" y="${hgt - 8}" text-anchor="middle">${String(y).slice(2)}</text>`;
    });
    svg += "</svg>";
    $("pd-chart").innerHTML = `<div class="muted small-txt">Country-years with values, by year and source (one source per country-year: the first of Round 1, Round 2, Round 3, Gap fill)</div>` + svg;
  }

  // ------------------------------------------------------------------ start
  loadOverview().then(() => { route(); pollJob(); });
  setInterval(() => { if (!document.hidden && !$("sec-workflow").hidden && W.view !== "hr") loadOverview(); }, 30000);
})();
