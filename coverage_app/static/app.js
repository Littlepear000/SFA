(function () {
  "use strict";

  // ------------------------------------------------------------------ helpers
  var $ = function (id) { return document.getElementById(id); };
  var NS = "http://www.w3.org/2000/svg";
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmtN(n) { return Number(n).toLocaleString("en-US"); }
  function pct(a, b) { return b ? (100 * a / b).toFixed(1) + "%" : "—"; }
  function fmtBytes(n) { return n == null ? "" : n > 1e6 ? (n / 1e6).toFixed(1) + " MB" : Math.round(n / 1e3) + " KB"; }
  function fmtTime(iso) { return iso ? iso.replace("T", " ").slice(0, 16) : ""; }
  function baseName(p) { return String(p || "").split(/[\\/]/).pop(); }
  function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } }
  function toast(msg) {
    var t = $("toast"); t.textContent = msg; t.hidden = false;
    clearTimeout(toast._t); toast._t = setTimeout(function () { t.hidden = true; }, 5000);
  }
  function api(path, body) {
    var opt = body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {};
    return fetch(path, opt).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
        return j;
      });
    });
  }

  var S = { defaults: null, runs: [], active: null, data: null, page: 0, pageSize: 60, polling: null };

  // ------------------------------------------------------------------ tabs
  // Coverage has two modules, Database (with "Generate a new version" at the top) and Dashboard; the
  // top-level navigation (Workflow / Panel database / Coverage) lives in workflow.js, which calls this.
  function showTab(name) {
    if (name === "generate") name = "database";
    if (["database", "dashboard"].indexOf(name) < 0) name = "database";
    document.querySelectorAll(".cov-tab").forEach(function (b) { b.setAttribute("aria-selected", String(b.dataset.tab === name)); });
    ["database", "dashboard"].forEach(function (t) { $("tab-" + t).hidden = t !== name; });
    store("cov_tab", name);
    if (name === "dashboard") drawChart();
  }
  window.Coverage = { showTab: showTab, current: function () { return store("cov_tab") || "database"; } };

  // ------------------------------------------------------------------ generate
  function inspectPaths() {
    var body = { final_csv: $("in-csv").value, pdf_root: $("in-pdf").value };
    store("cov_csv", body.final_csv); store("cov_pdf", body.pdf_root);
    return api("/api/inspect", body).then(function (r) {
      var c = r.final_csv, sc = $("st-csv");
      sc.className = "field-status " + (c.exists ? "ok" : "bad");
      sc.textContent = c.exists ? "Found · " + fmtBytes(c.size_bytes) + " · modified " + fmtTime(c.modified) : "File not found";
      var p = r.pdf_root, sp = $("st-pdf");
      sp.className = "field-status " + (p.exists ? "ok" : "bad");
      sp.textContent = p.exists ? "Found · " + p.folders.length + " sub-folder(s)" : "Folder not found";
      renderBatches(p.folders || [], p.exists, body.pdf_root, p.n_direct_pdfs);
    }).catch(function (e) { toast(e.message); });
  }

  // Batch folders: every sub-folder of the PDF folder is listed and ticked by default ("Select all").
  // Re-checking the same folder keeps the ticks you changed; a different folder starts with all ticked.
  function renderBatches(folders, exists, root, nDirect) {
    var box = $("batch-list");
    var keep = S.batchRoot === root ? selectedBatches() : null;
    S.batchRoot = root;
    if (!exists) { box.innerHTML = '<span class="muted">Enter the PDF folder above; its batch sub-folders are listed here.</span>'; return; }
    if (!folders.length) {
      box.innerHTML = '<span class="field-status bad">No sub-folders found in this folder. Each batch of PDFs should sit in its own sub-folder ' +
        '(e.g. 2011-2015), and the path above should be the folder that holds them.' +
        (nDirect ? " This folder has " + fmtN(nDirect) + " PDFs directly in it; those are not read." : "") + "</span>";
      return;
    }
    box.innerHTML =
      '<div class="batch-tools"><button type="button" class="btn small" id="b-all">Select all</button>' +
      '<button type="button" class="btn small" id="b-none">Clear</button><span class="muted" id="b-count"></span></div>' +
      '<div class="batch-chips">' + folders.map(function (f) {
        var on = keep ? keep.indexOf(f.name) >= 0 : true;
        return '<label class="batch' + (on ? "" : " off") + '"><input type="checkbox" value="' + esc(f.name) + '" data-n="' + f.n_pdfs + '"' +
          (on ? " checked" : "") + "> " + esc(f.name) + ' <span class="n">' + fmtN(f.n_pdfs) + " PDFs</span></label>";
      }).join("") + "</div>" +
      (nDirect ? '<div class="field-status">' + fmtN(nDirect) + " PDFs sit directly in the folder (not in a batch sub-folder); they are not read.</div>" : "");
    var boxes = box.querySelectorAll("input[type=checkbox]");
    function sync() {
      var n = 0, pdfs = 0;
      boxes.forEach(function (i) { i.parentNode.classList.toggle("off", !i.checked); if (i.checked) { n++; pdfs += +i.dataset.n; } });
      $("b-count").textContent = n + " of " + boxes.length + " selected · " + fmtN(pdfs) + " PDFs";
    }
    boxes.forEach(function (i) { i.addEventListener("change", sync); });
    $("b-all").addEventListener("click", function () { boxes.forEach(function (i) { i.checked = true; }); sync(); });
    $("b-none").addEventListener("click", function () { boxes.forEach(function (i) { i.checked = false; }); sync(); });
    sync();
  }

  function selectedBatches() {
    return Array.prototype.map.call($("batch-list").querySelectorAll("input[type=checkbox]:checked"), function (i) { return i.value; });
  }

  function setJobState(job) {
    var box = $("job-progress"), bar = $("job-bar"), text = $("job-text"), det = $("job-details");
    $("btn-generate").disabled = job.state === "running";
    if (job.state === "idle") { box.hidden = true; det.hidden = true; return; }
    box.hidden = false;
    var p = job.state === "done" ? 1 : Math.max(0.02, job.progress || 0);
    box.className = "progress " + job.state;
    bar.style.width = (100 * p).toFixed(0) + "%";
    $("job-bar-wrap").setAttribute("aria-valuenow", (100 * p).toFixed(0));
    if (job.state === "running") {
      text.innerHTML = '<span class="spinner" aria-hidden="true"></span>' + esc(job.stage || "Working") + "… " + (100 * p).toFixed(0) + "%";
    } else if (job.state === "done") {
      text.innerHTML = '<span class="check" aria-hidden="true">✓</span><b>Completed</b> · version ' + esc(job.stamp);
    } else {
      text.innerHTML = '<span class="cross" aria-hidden="true">✕</span><b>Failed</b> · ' + esc(job.error || "");
    }
    // the run's printed output stays available, folded away, mainly for when something fails
    det.hidden = !(job.log && job.log.length) || job.state === "running";
    if (job.state === "error") det.open = true;
    $("job-log").textContent = (job.log || []).join("\n");
  }

  function pollJob() {
    api("/api/job").then(function (job) {
      setJobState(job);
      if (job.state === "running") { S.polling = setTimeout(pollJob, 1000); return; }
      S.polling = null;
      if (job.state === "done") { S.stampEdited = false; setDefaultStamp(); loadRuns(job.stamp); }
    }).catch(function () { S.polling = setTimeout(pollJob, 2000); });
  }

  // version stamp: filled with the current date and time (YYYYMMDD_HHMM) and kept up to date,
  // until you type your own
  function nowStamp() {
    var t = new Date(), pad = function (n) { return (n < 10 ? "0" : "") + n; };
    return t.getFullYear() + pad(t.getMonth() + 1) + pad(t.getDate()) + "_" + pad(t.getHours()) + pad(t.getMinutes());
  }
  function setDefaultStamp() { if (!S.stampEdited) $("in-stamp").value = nowStamp(); }
  $("in-stamp").addEventListener("input", function () { S.stampEdited = this.value.trim() !== ""; });
  setInterval(setDefaultStamp, 20000);

  // check the paths as soon as they are typed or pasted (short pause), and again when the field is left
  var typing;
  function inspectSoon() { clearTimeout(typing); typing = setTimeout(inspectPaths, 450); }
  ["in-csv", "in-pdf"].forEach(function (id) {
    $(id).addEventListener("input", inspectSoon);
    $(id).addEventListener("change", inspectPaths);
  });
  $("btn-generate").addEventListener("click", function () {
    // re-check first, so the batch list always belongs to the folder in the box
    clearTimeout(typing);
    inspectPaths().then(function () {
      var batches = selectedBatches();
      if (!batches.length) { toast("No batch folder selected. Tick at least one (or Select all)."); return; }
      var body = { final_csv: $("in-csv").value, pdf_root: $("in-pdf").value, batches: batches, stamp: $("in-stamp").value };
      return api("/api/generate", body).then(function (r) {
        toast("Started version " + r.stamp + " (" + batches.length + " batch folder" + (batches.length > 1 ? "s" : "") + ").");
        clearTimeout(S.polling); pollJob();
      });
    }).catch(function (e) { toast(e.message); });
  });

  // ------------------------------------------------------------------ versions
  function runLabel(r) { return (r.stamp || "(no stamp)") + " · " + fmtTime(r.created); }

  function loadRuns(select) {
    return api("/api/runs").then(function (j) {
      S.runs = j.runs;
      var sel = $("version-select");
      sel.innerHTML = S.runs.map(function (r) {
        return '<option value="' + esc(r.stamp) + '">' + esc(runLabel(r)) + "</option>";
      }).join("") || "<option value=''>No versions yet</option>";
      var keep = select != null ? select : (S.active != null ? S.active : store("cov_version"));
      var exists = S.runs.some(function (r) { return r.stamp === keep; });
      var pick = exists ? keep : (S.runs[0] ? S.runs[0].stamp : null);
      renderRuns();
      if (!S.runs.length) $("gen-card").open = true;  // nothing to show yet: start with Generate open
      if (pick != null) { sel.value = pick; setActive(pick); }
      else { S.active = null; S.data = null; renderDatabase(); drawChart(); }
    }).catch(function (e) { toast(e.message); });
  }

  function renderRuns() {
    var tb = $("runs-table").querySelector("tbody");
    $("runs-empty").hidden = S.runs.length > 0;
    tb.innerHTML = S.runs.map(function (r) {
      var csv = r.final_csv || {};
      var csvCell = r.has_record
        ? '<span class="path" title="' + esc(csv.path) + '">' + esc(baseName(csv.path)) + "</span>" +
          '<span class="sub">' + esc(fmtBytes(csv.size_bytes)) + " · modified " + esc(fmtTime(csv.modified)) + " · sha " + esc(csv.sha256_16) + "</span>"
        : '<span class="tag">no run record</span>';
      var pdfCell = r.has_record
        ? '<span class="path" title="' + esc(r.pdf_root) + '">' + esc(baseName(r.pdf_root)) + "</span>" +
          '<span class="sub">' + esc((r.batches || []).join(", ")) + "</span>"
        : "";
      return '<tr class="' + (r.stamp === S.active ? "active" : "") + '">' +
        "<td><b>" + esc(r.stamp || "(no stamp)") + "</b></td>" +
        "<td>" + esc(fmtTime(r.created)) + "</td>" +
        "<td>" + csvCell + "</td><td>" + pdfCell + "</td>" +
        '<td class="num">' + (r.has_record ? fmtN(r.country_years_with_staff_report) : "") + "</td>" +
        '<td class="num">' + (r.seconds != null ? r.seconds + " s" : "") + "</td>" +
        '<td><button class="btn small" data-view="' + esc(r.stamp) + '">View</button> ' +
        '<a class="btn small" href="/api/runs/' + encodeURIComponent(r.stamp) + '/download">Download</a></td></tr>';
    }).join("");
    tb.querySelectorAll("[data-view]").forEach(function (b) {
      b.addEventListener("click", function () { $("version-select").value = b.dataset.view; setActive(b.dataset.view); location.hash = "#coverage/dashboard"; });
    });
  }

  function setActive(stamp) {
    S.active = stamp; store("cov_version", stamp);
    renderRuns();
    $("btn-download").href = "/api/runs/" + encodeURIComponent(stamp) + "/download";
    $("db-count").textContent = "Loading…";
    return api("/api/runs/" + encodeURIComponent(stamp) + "/data").then(function (d) {
      if (S.active !== stamp) return;
      S.data = d; S.page = 0;
      setupFilters(); renderDatabase(); setupSlicer(); drawChart();
    }).catch(function (e) { toast(e.message); $("db-count").textContent = ""; });
  }
  $("version-select").addEventListener("change", function () { setActive(this.value); });

  // ------------------------------------------------------------------ database
  function indicatorCols() {
    return S.data ? S.data.columns.filter(function (c) { return /^h\d/.test(c.name); }) : [];
  }

  function setupFilters() {
    var years = Array.from(new Set(S.data.row_year)).sort();
    var keep = $("f-year").value;
    $("f-year").innerHTML = '<option value="">All</option>' + years.map(function (y) { return "<option>" + y + "</option>"; }).join("");
    if (years.indexOf(+keep) >= 0) $("f-year").value = keep;
    setupFields();
  }

  // Fields: which columns the table shows. Default: has_staff_report and the top-level
  // indicators (h1-h6); the choice is remembered in this browser.
  // has_dsa_table is left out of the app for now (its definition is under review); the workbook still has it
  var HIDDEN = ["has_dsa_table"];
  function shownColumns() { return S.data.columns.filter(function (c) { return HIDDEN.indexOf(c.name) < 0; }); }
  function isTop(c) { return !/^h\d/.test(c.name) || c.hierarchy_id.indexOf(".") < 0; }
  function topFields() { return shownColumns().filter(isTop).map(function (c) { return c.name; }); }
  function setupFields() {
    var saved = null;
    try { saved = JSON.parse(store("cov_fields") || "null"); } catch (e) { saved = null; }
    var names = shownColumns().map(function (c) { return c.name; });
    S.fields = Array.isArray(saved) ? saved.filter(function (n) { return names.indexOf(n) >= 0; }) : topFields();
    var groups = {}, order = [];
    shownColumns().forEach(function (c) {
      var g = /^h\d/.test(c.name) ? (c.top_category || "other").replace(/_/g, " ") : "reports";
      if (!groups[g]) { groups[g] = []; order.push(g); }
      groups[g].push(c);
    });
    $("fields-list").innerHTML = order.map(function (g) {
      return '<div class="fld-group"><div class="fld-head">' + esc(g) + "</div>" + groups[g].map(function (c) {
        return '<label class="fld' + (isTop(c) ? " top" : "") + '" title="' + esc(c.labels || "") + '"><input type="checkbox" value="' + esc(c.name) + '"' +
          (S.fields.indexOf(c.name) >= 0 ? " checked" : "") + "> " + esc(c.name) + "</label>";
      }).join("") + "</div>";
    }).join("");
    $("fields-list").querySelectorAll("input").forEach(function (i) {
      i.addEventListener("change", function () { readFields(); });
    });
    updateFieldsBadge();
  }
  function readFields() {
    S.fields = Array.prototype.map.call($("fields-list").querySelectorAll("input:checked"), function (i) { return i.value; });
    store("cov_fields", JSON.stringify(S.fields));
    updateFieldsBadge(); renderDatabase();
  }
  function setFields(names) {
    $("fields-list").querySelectorAll("input").forEach(function (i) { i.checked = names.indexOf(i.value) >= 0; });
    readFields();
  }
  function updateFieldsBadge() { $("fields-count").textContent = S.fields.length + " / " + shownColumns().length; }
  // colour family of a column: staff report / DSA table / indicator value
  function kindOf(name) { return name === "has_staff_report" ? "k-rep" : name === "has_dsa_table" ? "k-dsa" : "k-val"; }
  function visibleCols() {
    return shownColumns().filter(function (c) { return S.fields.indexOf(c.name) >= 0; });
  }
  $("fld-top").addEventListener("click", function () { setFields(topFields()); });
  $("fld-all").addEventListener("click", function () { setFields(shownColumns().map(function (c) { return c.name; })); });
  $("fld-none").addEventListener("click", function () { setFields([]); });
  function toggleFields(open) {
    $("fields-pop").hidden = !open;
    $("btn-fields").setAttribute("aria-expanded", String(open));
  }
  $("btn-fields").addEventListener("click", function (e) { e.stopPropagation(); if (S.data) toggleFields($("fields-pop").hidden); });
  $("fields-pop").addEventListener("click", function (e) { e.stopPropagation(); });
  document.addEventListener("click", function () { toggleFields(false); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") toggleFields(false); });

  function filteredRows() {
    var d = S.data, q = $("f-country").value.trim().toLowerCase(), y = $("f-year").value;
    var onlyReported = $("f-reported").checked, reported = {};
    if (onlyReported) {   // countries with a staff report in any year of the scanned PDF folders
      for (var k = 0; k < d.row_year.length; k++) if (d.flags.has_staff_report[k] === "1") reported[d.row_country[k]] = true;
    }
    var out = [];
    for (var i = 0; i < d.row_year.length; i++) {
      if (onlyReported && !reported[d.row_country[i]]) continue;
      if (y && String(d.row_year[i]) !== y) continue;
      if (q && d.countries[d.row_country[i]].toLowerCase().indexOf(q) < 0) continue;
      out.push(i);
    }
    return out;
  }

  function renderDatabase() {
    var thead = $("db-table").querySelector("thead"), tbody = $("db-table").querySelector("tbody");
    if (!S.data) { thead.innerHTML = ""; tbody.innerHTML = ""; $("db-count").textContent = "No version selected."; $("pg-info").textContent = ""; return; }
    var cols = visibleCols(), rows = filteredRows(), d = S.data;
    var pages = Math.max(1, Math.ceil(rows.length / S.pageSize));
    S.page = Math.min(S.page, pages - 1);
    var slice = rows.slice(S.page * S.pageSize, (S.page + 1) * S.pageSize);
    // column names break after "_" so long names wrap onto a few short lines
    thead.innerHTML = '<tr><th class="c-country">Country</th><th class="c-year">Year</th>' + cols.map(function (c) {
      return '<th class="flag ' + kindOf(c.name) + '" title="' + esc(c.labels || c.name) + '">' + esc(c.name).replace(/_/g, "_<wbr>") + "</th>";
    }).join("") + "</tr>";
    tbody.innerHTML = slice.map(function (i) {
      return '<tr><td class="c-country">' + esc(d.countries[d.row_country[i]]) + '</td><td class="c-year">' + d.row_year[i] + "</td>" + cols.map(function (c) {
        return d.flags[c.name][i] === "1" ? '<td class="flag" title="Yes"><span class="yes ' + kindOf(c.name) + '" aria-label="Yes"></span></td>'
          : '<td class="flag" title="No"><span class="no" aria-label="No"></span></td>';
      }).join("") + "</tr>";
    }).join("");
    var first = $("db-table").querySelector("thead th");
    if (first) $("db-table").style.setProperty("--c1w", first.getBoundingClientRect().width + "px");
    $("db-count").textContent = fmtN(rows.length) + " of " + fmtN(d.row_year.length) + " country-years · " + cols.length + " columns";
    $("pg-info").textContent = "Page " + (S.page + 1) + " of " + pages;
    $("pg-prev").disabled = S.page === 0; $("pg-next").disabled = S.page >= pages - 1;
  }
  ["f-country", "f-year", "f-reported"].forEach(function (id) {
    $(id).addEventListener("input", function () { S.page = 0; renderDatabase(); });
  });
  $("pg-prev").addEventListener("click", function () { S.page--; renderDatabase(); });
  $("pg-next").addEventListener("click", function () { S.page++; renderDatabase(); });

  // ------------------------------------------------------------------ dashboard
  // One stacked column per year: all panel countries, split by where the value for the indicator in the
  // slicer came from (Round 1 / 2 / 3 / Gap fill) or Unavailable. With a follow-up window T+1 ... T+k
  // picked (top right), Unavailable is split again: countries with NO staff report published in any of
  // the years T+1 ... T+k (hatched, on top, counted above the column) vs. the rest.
  var SOURCES = [
    { key: "r1", code: "1", label: "Round 1", color: "var(--s-round1)" },
    { key: "r2", code: "2", label: "Round 2", color: "var(--s-round2)" },
    { key: "r3", code: "3", label: "Round 3 (human review)", color: "var(--s-round3)" },
    { key: "gf", code: "g", label: "Gap fill", color: "var(--s-gapfill)" }
  ];
  var VALUE_ONLY = [{ key: "val", code: "v", label: "Has a value", color: "var(--c-value)" }];
  var HATCH = "url(#hatch-nolater)";
  var HATCH_SWATCH = "repeating-linear-gradient(135deg, var(--s-hatch) 0 2px, var(--s-unavail) 2px 5px)";

  function setupSlicer() {
    var sel = $("ind-select"), cols = indicatorCols(), groups = {}, order = [];
    cols.forEach(function (c) {
      var g = c.top_category || "other";
      if (!groups[g]) { groups[g] = []; order.push(g); }
      groups[g].push(c);
    });
    sel.innerHTML = order.map(function (g) {
      return '<optgroup label="' + esc(g.replace(/_/g, " ")) + '">' + groups[g].map(function (c) {
        var n = (S.data.flags[c.name].match(/1/g) || []).length;
        return '<option value="' + esc(c.name) + '">' + esc(c.name) + " (" + fmtN(n) + ")</option>";
      }).join("") + "</optgroup>";
    }).join("");
    var keep = store("cov_indicator");
    var names = cols.map(function (c) { return c.name; });
    sel.value = names.indexOf(keep) >= 0 ? keep : (names.indexOf("h6_residual") >= 0 ? "h6_residual" : names[0]);
  }
  $("ind-select").addEventListener("change", function () { store("cov_indicator", this.value); S.pick = null; drawChart(); });

  // follow-up window: 0 = off, k = T+1 ... T+k
  S.span = Math.min(4, Math.max(0, parseInt(store("cov_span"), 10) || 0));
  function setSpan(k) {
    S.span = k; store("cov_span", String(k));
    document.querySelectorAll("#span-seg button").forEach(function (b) { b.setAttribute("aria-pressed", String(+b.dataset.k === k)); });
    drawChart();
  }
  document.querySelectorAll("#span-seg button").forEach(function (b) {
    b.addEventListener("click", function () { setSpan(+b.dataset.k); });
  });
  setSpan(S.span);
  function spanText(y, k) { return k === 1 ? String(y + 1) : (y + 1) + "–" + (y + k); }

  // per country: the set of publication years with a staff report. The workbook's Report years sheet
  // has every year; older workbooks only have has_staff_report for the panel years.
  function reportLookup() {
    var d = S.data;
    if (d._reports) return d._reports;
    var sets = d.countries.map(function () { return {}; }), last;
    if (d.report_years) {
      d.report_years.forEach(function (ys, c) { ys.forEach(function (y) { sets[c][y] = 1; }); });
      last = d.report_year_range ? d.report_year_range[1] : null;
    } else {
      var f = d.flags.has_staff_report;
      for (var i = 0; i < d.row_year.length; i++) if (f[i] === "1") sets[d.row_country[i]][d.row_year[i]] = 1;
      last = Math.max.apply(null, d.row_year);
    }
    d._reports = { sets: sets, last: last };
    return d._reports;
  }

  function yearBreakdown(ind, k) {
    var d = S.data, by = {}, rep = reportLookup();
    var src = d.sources && d.sources[ind], flag = d.flags[ind];
    var series = src ? SOURCES : VALUE_ONLY;
    for (var i = 0; i < d.row_year.length; i++) {
      var y = d.row_year[i], c = d.row_country[i];
      var b = by[y];
      if (!b) {
        b = by[y] = { year: y, total: 0, unavail: 0, later: 0, nolater: 0, list: [], partial: k > 0 && rep.last != null && y + k > rep.last };
        series.forEach(function (s) { b[s.key] = 0; });
      }
      b.total++;
      var code = src ? src[i] : (flag[i] === "1" ? "v" : "0");
      if (code !== "0") {
        for (var s = 0; s < series.length; s++) if (series[s].code === code) { b[series[s].key]++; break; }
        continue;
      }
      b.unavail++;
      if (!k) continue;
      var none = true;
      for (var j = 1; j <= k; j++) if (rep.sets[c][y + j]) { none = false; break; }
      if (none) { b.nolater++; b.list.push(d.countries[c]); } else b.later++;
    }
    return { series: series, rows: Object.keys(by).sort().map(function (y) { return by[y]; }) };
  }

  function el(name, attrs, parent) {
    var e = document.createElementNS(NS, name);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }

  // a bar segment; only the top segment gets rounded top corners (the data end), the base stays square.
  // A thin surface-coloured line separates stacked segments.
  function segment(g, x, y0, y1, w, fill, roundTop) {
    var h = y0 - y1; if (h <= 0) return;
    var r = roundTop ? Math.min(3, w / 2, h) : 0;
    el("path", { d: "M" + x + "," + y0 + "V" + (y1 + r) + (r ? "Q" + x + "," + y1 + " " + (x + r) + "," + y1 : "") +
      "H" + (x + w - r) + (r ? "Q" + (x + w) + "," + y1 + " " + (x + w) + "," + (y1 + r) : "") + "V" + y0 + "Z",
      fill: fill, stroke: "var(--panel)", "stroke-width": 1 }, g);
  }

  function drawChart() {
    var wrap = $("ch-wrap"), tip = $("ch-tip");
    var old = wrap.querySelector("svg"); if (old) old.remove();
    tip.style.display = "none";
    if (!S.data || $("tab-dashboard").hidden) return;
    var ind = $("ind-select").value; if (!ind) return;
    var k = S.span, br = yearBreakdown(ind, k), rows = br.rows, series = br.series;
    var col = S.data.columns.filter(function (c) { return c.name === ind; })[0] || {};
    var nCountries = S.data.countries.length, rep = reportLookup();
    var parts = series.slice();
    if (k) {
      parts.push({ key: "later", label: "Unavailable, other reasons", color: "var(--s-unavail)" });
      parts.push({ key: "nolater", label: "Unavailable, no staff report in T+1" + (k > 1 ? "…T+" + k : ""), color: HATCH, swatch: HATCH_SWATCH });
    } else {
      parts.push({ key: "unavail", label: "Unavailable", color: "var(--s-unavail)" });
    }

    $("ch-note").textContent = "Each column is all " + nCountries + " panel countries for that year, split by where the value for " + ind +
      (col.labels ? " (" + col.labels.split(" | ")[0] + ")" : "") + " came from." +
      (S.data.sources ? "" : " This version has no source detail (generated before it was added); generate a new version to see Round 1/2/3 and Gap fill.") +
      (k ? " Hatched: unavailable, and the country has no staff report published in any of the next " + (k === 1 ? "year" : k + " years") + " (T+1" + (k > 1 ? "…T+" + k : "") + "); the number above each column counts them. Click a column to list them." : "");
    $("ch-legend").innerHTML = parts.map(function (p) {
      return '<span><i style="background:' + (p.swatch || p.color) + '"></i>' + esc(p.label) + "</span>";
    }).join("");

    // three headline numbers: all country-years, those with data for the indicator, and the share
    var total = 0, avail = 0;
    rows.forEach(function (r) { total += r.total; avail += r.total - r.unavail; });
    var nYears = rows.length;
    $("tiles").innerHTML =
      '<div class="tile"><span class="lbl">Country-years</span><span class="val">' + fmtN(total) +
        '</span><span class="sub muted">' + nCountries + " countries × " + nYears + " years (" +
        (rows.length ? rows[0].year + "–" + rows[nYears - 1].year : "") + ")</span></div>" +
      '<div class="tile"><span class="lbl">With data available</span><span class="val">' + fmtN(avail) +
        '</span><span class="sub muted">country-years with a value for ' + esc(ind) + "</span></div>" +
      '<div class="tile"><span class="lbl">Coverage</span><span class="val">' + pct(avail, total) +
        '</span><span class="sub muted">' + fmtN(avail) + " of " + fmtN(total) + " country-years</span></div>";

    var yMax = nCountries;
    var W = Math.max(320, wrap.clientWidth), H = Math.round(Math.min(520, Math.max(280, W * 0.36)));
    var m = { top: k ? 22 : 12, right: 8, bottom: 28, left: 38 }, iw = W - m.left - m.right, ih = H - m.top - m.bottom;
    var svg = el("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": "Stacked columns per year: countries by source of the " + ind + " value" });
    wrap.insertBefore(svg, tip);
    var pat = el("pattern", { id: "hatch-nolater", width: 5, height: 5, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, el("defs", {}, svg));
    el("rect", { width: 5, height: 5, fill: "var(--s-unavail)" }, pat);
    el("rect", { width: 2, height: 5, fill: "var(--s-hatch)" }, pat);
    var g = el("g", { transform: "translate(" + m.left + "," + m.top + ")" }, svg);
    var y = function (v) { return ih - v / yMax * ih; };
    var step = yMax > 150 ? 50 : yMax > 60 ? 20 : 10;
    for (var t = 0; t <= yMax; t += step) {
      el("line", { x1: 0, x2: iw, y1: y(t), y2: y(t), "class": "grid-line" }, g);
      el("text", { x: -8, y: y(t), "text-anchor": "end", "dominant-baseline": "middle" }, g).textContent = t;
    }
    if (yMax % step) {
      el("line", { x1: 0, x2: iw, y1: y(yMax), y2: y(yMax), "class": "grid-line max" }, g);
      el("text", { x: -8, y: y(yMax), "text-anchor": "end", "dominant-baseline": "middle" }, g).textContent = yMax;
    }

    var n = rows.length, slot = iw / n;
    var bw = Math.max(4, Math.min(30, slot * 0.66));
    var every = slot < 26 ? (slot < 14 ? 5 : 2) : 1;
    rows.forEach(function (r, i) {
      var x = i * slot + (slot - bw) / 2, acc = 0;
      var last = -1; parts.forEach(function (p, j) { if (r[p.key]) last = j; });
      parts.forEach(function (p, j) {
        var v = r[p.key]; if (!v) return;
        segment(g, x, y(acc), y(acc + v), bw, p.color, j === last);
        acc += v;
      });
      if (k && slot >= 16) {
        var lab = el("text", { x: x + bw / 2, y: y(acc) - 6, "text-anchor": "middle", "class": "bar-lab" + (r.partial ? " partial" : "") }, g);
        lab.textContent = r.nolater + (r.partial ? "*" : "");
      }
      if (S.pick === r.year) el("rect", { x: x - 2.5, y: y(acc) - 1.5, width: bw + 5, height: ih - y(acc) + 1.5, rx: 4, "class": "picked" }, g);
      if (i % every === 0 || i === n - 1) {
        el("text", { x: i * slot + slot / 2, y: ih + 18, "text-anchor": "middle" }, g).textContent =
          every > 1 || slot >= 34 ? r.year : "’" + String(r.year).slice(2);
      }
      var hit = el("rect", { x: i * slot, y: -m.top, width: slot, height: ih + m.top, "class": "hit" + (k ? " clickable" : "") }, g);
      hit.addEventListener("mousemove", function (ev) { showTip(ev, r); });
      hit.addEventListener("mouseleave", function () { tip.style.display = "none"; });
      hit.addEventListener("click", function () { if (k) { S.pick = S.pick === r.year ? null : r.year; drawChart(); } });
    });
    el("line", { x1: 0, x2: iw, y1: ih, y2: ih, "class": "axis-line" }, g);

    function showTip(ev, r) {
      var line = function (p, v, cls) {
        return '<div class="r' + (cls || "") + '"><span><i style="background:' + (p.swatch || p.color) + '"></i>' + esc(p.label) +
          "</span><span>" + v + " (" + pct(v, r.total) + ")</span></div>";
      };
      var html = "<b>" + r.year + " · " + r.total + " countries</b>";
      parts.slice().reverse().forEach(function (p) {
        var label = p.key === "later" ? p
          : p.key === "nolater" ? { label: "Unavailable, no staff report in " + spanText(r.year, k), swatch: p.swatch } : p;
        html += line(label, r[p.key]);
      });
      if (k) html += '<div class="r tot"><span>Unavailable, total</span><span>' + r.unavail + " (" + pct(r.unavail, r.total) + ")</span></div>";
      if (r.partial) html += '<div class="tip-h">* Staff reports go up to ' + rep.last + ", so " +
        (rep.last > r.year ? "only " + spanText(r.year, rep.last - r.year) + " is checked." : "no later year can be checked.") + "</div>";
      tip.innerHTML = html;
      tip.style.display = "block";
      var b = wrap.getBoundingClientRect(), px = ev.clientX - b.left + 14, py = ev.clientY - b.top + 10;
      if (px + tip.offsetWidth > b.width) px = ev.clientX - b.left - tip.offsetWidth - 14;
      tip.style.left = Math.max(0, px) + "px"; tip.style.top = py + "px";
    }

    // the countries behind the hatched part of the clicked column
    var picked = k && S.pick != null ? rows.filter(function (r) { return r.year === S.pick; })[0] : null;
    var box = $("ch-pick");
    if (picked) {
      box.hidden = false;
      box.innerHTML = '<div class="pick-head"><b>' + picked.year + ": " + picked.nolater + " of " + picked.unavail +
        " unavailable countries have no staff report in " + spanText(picked.year, k) + (picked.partial ? "*" : "") +
        '</b><button type="button" class="btn small" id="pick-close">Close</button></div>' +
        (picked.partial ? '<p class="muted">* Staff reports go up to ' + rep.last + "; later years are not checked.</p>" : "") +
        '<div class="pick-list">' + (picked.list.length ? picked.list.map(function (c) { return "<span>" + esc(c) + "</span>"; }).join("") : '<span class="muted">None</span>') + "</div>";
      $("pick-close").addEventListener("click", function () { S.pick = null; drawChart(); });
    } else {
      box.hidden = true; box.innerHTML = "";
    }
    $("span-last").textContent = rep.last != null ? "Staff reports up to " + rep.last + (S.data.report_years ? "" : " (this version: panel years only)") : "";

    $("ch-table").querySelector("thead").innerHTML = "<tr><th>Year</th>" + series.map(function (s) {
      return '<th class="num">' + esc(s.label) + "</th>";
    }).join("") + '<th class="num">Unavailable</th>' + (k ? '<th class="num">of which no staff report in T+1' + (k > 1 ? "…T+" + k : "") + "</th>" : "") + "</tr>";
    $("ch-table").querySelector("tbody").innerHTML = rows.map(function (r) {
      return "<tr><td>" + r.year + "</td>" + series.map(function (s) { return '<td class="num">' + r[s.key] + "</td>"; }).join("") +
        '<td class="num">' + r.unavail + "</td>" + (k ? '<td class="num">' + r.nolater + (r.partial ? "*" : "") + "</td>" : "") + "</tr>";
    }).join("");
  }
  var rt; window.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(drawChart, 120); });

  // ------------------------------------------------------------------ start
  api("/api/defaults").then(function (d) {
    S.defaults = d;
    $("in-csv").value = store("cov_csv") || d.final_csv;
    $("in-pdf").value = store("cov_pdf") || d.pdf_root;
    $("in-stamp").placeholder = "YYYYMMDD_HHMM";
    setDefaultStamp();
    $("out-dir").textContent = d.out_dir;
    inspectPaths();
    return loadRuns();
  }).then(function () {
    return api("/api/job").then(function (job) { setJobState(job); if (job.state === "running") pollJob(); });
  }).catch(function (e) { toast("Could not reach the app server: " + e.message); });
})();
