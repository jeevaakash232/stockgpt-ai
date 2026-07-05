/**
 * history.js — Historical data tab.
 *
 * Loads available trading dates, displays daily snapshots,
 * shows per-symbol 30-day history, and downloads historical Excel.
 */

let _currentHistoryDate = "";

// ---------------------------------------------------------------------------
// Init — called when History tab opens
// ---------------------------------------------------------------------------

async function initHistoryTab() {
  await Promise.all([loadHistoryDates(), loadHistoryStats()]);
}


// ---------------------------------------------------------------------------
// Load available dates into the dropdown
// ---------------------------------------------------------------------------

async function loadHistoryDates() {
  const sel = document.getElementById("historyDateSelect");
  if (!sel) return;

  try {
    const dates = await apiFetch("/history/dates");
    sel.innerHTML = '<option value="">Select date…</option>';

    dates.forEach((d, i) => {
      const opt      = document.createElement("option");
      opt.value      = d;
      opt.textContent = _formatDate(d);
      if (i === 0) opt.selected = true;   // default to most recent
      sel.appendChild(opt);
    });

    if (dates.length > 0) {
      _currentHistoryDate = dates[0];
      loadHistorySnapshot(dates[0]);
    } else {
      document.getElementById("historyInfo").textContent =
        "No data yet — data is saved automatically during market hours (9:15 AM – 3:30 PM IST).";
    }
  } catch (err) {
    console.error("loadHistoryDates:", err);
  }
}


// ---------------------------------------------------------------------------
// Load DB stats (trading days, row count, size)
// ---------------------------------------------------------------------------

async function loadHistoryStats() {
  try {
    const s = await apiFetch("/history/stats");
    const el = (id, val) => { const e = document.getElementById(id); if (e) e.textContent = val; };
    el("statsTradingDays", s.trading_days ?? "—");
    el("statsDailyRows",   (s.daily_rows ?? 0).toLocaleString("en-IN"));
    el("statsDbSize",      s.db_size_kb ? s.db_size_kb + " KB" : "—");
  } catch (_) {}
}


// ---------------------------------------------------------------------------
// Load snapshot for a selected date
// ---------------------------------------------------------------------------

async function loadHistorySnapshot(dateStr) {
  if (!dateStr) return;
  _currentHistoryDate = dateStr;

  const tbody = document.getElementById("historySnapshotBody");
  const info  = document.getElementById("historyInfo");
  if (!tbody) return;

  tbody.innerHTML = `<tr><td colspan="10" class="loading-row">
    <span class="spinner-border spinner-border-sm me-2"></span>Loading ${_formatDate(dateStr)}…
  </td></tr>`;

  try {
    const resp = await apiFetch(`/history/snapshot/${dateStr}`);
    const rows = resp.records || [];

    if (!rows.length) {
      tbody.innerHTML = `<tr><td colspan="10" class="text-center text-muted py-3">
        No data found for ${_formatDate(dateStr)}</td></tr>`;
      return;
    }

    if (info) info.textContent = `${_formatDate(dateStr)} · ${rows.length} symbols`;

    tbody.innerHTML = rows.map((s, i) => {
      const pct  = s.price_chg_pct;
      const cls  = _deltaClass(pct);
      const sig  = s.signal || "—";
      return `<tr>
        <td class="text-muted">${i + 1}</td>
        <td>
          <strong class="stock-link" onclick="loadSymbolHistoryFor('${esc(s.symbol)}')"
            style="cursor:pointer">${esc(s.symbol)}</strong>
        </td>
        <td class="text-warning fw-semibold">₹${_fmtN(s.ltp)}</td>
        <td class="text-muted">₹${_fmtN(s.prev_close)}</td>
        <td class="${cls}">${_fmtPctH(pct)}</td>
        <td class="${_pcrCls(s.pcr)}">${s.pcr ?? "—"}</td>
        <td class="${signalClass(sig)}">${esc(sig)}</td>
        <td>${_fmtOI2(s.call_oi)}</td>
        <td>${_fmtOI2(s.put_oi)}</td>
        <td>₹${_fmtN(s.max_pain)}</td>
      </tr>`;
    }).join("");

  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="10" class="text-danger text-center py-3">
      ${esc(err.message)}</td></tr>`;
  }
}


// ---------------------------------------------------------------------------
// Load 30-day history for a single symbol
// ---------------------------------------------------------------------------

async function loadSymbolHistory() {
  const input = document.getElementById("historySymbolInput");
  if (!input || !input.value.trim()) return;
  loadSymbolHistoryFor(input.value.trim().toUpperCase());
}

async function loadSymbolHistoryFor(symbol) {
  const section = document.getElementById("symbolHistorySection");
  const tbody   = document.getElementById("symbolHistoryBody");
  const title   = document.getElementById("symbolHistoryTitle");

  if (!section || !tbody) return;
  section.style.display = "block";
  if (title) title.textContent = `${symbol} — 30 Day History`;

  tbody.innerHTML = `<tr><td colspan="9" class="loading-row">
    <span class="spinner-border spinner-border-sm me-2"></span>Loading…</td></tr>`;

  try {
    const resp  = await apiFetch(`/history/${symbol}?days=30`);
    const rows  = resp.records || [];

    if (!rows.length) {
      tbody.innerHTML = `<tr><td colspan="9" class="text-center text-muted py-3">
        No history for ${esc(symbol)}. Data builds up as you use the app during market hours.
      </td></tr>`;
      return;
    }

    // Newest first
    const sorted = [...rows].reverse();
    tbody.innerHTML = sorted.map(s => {
      const pct = s.price_chg_pct;
      const cls = _deltaClass(pct);
      return `<tr>
        <td class="text-muted small">${_formatDate(s.trade_date)}</td>
        <td class="text-warning fw-semibold">₹${_fmtN(s.ltp)}</td>
        <td class="text-muted">₹${_fmtN(s.prev_close)}</td>
        <td class="${cls}">${_fmtPctH(pct)}</td>
        <td class="${_pcrCls(s.pcr)}">${s.pcr ?? "—"}</td>
        <td class="${signalClass(s.signal || '')}">${esc(s.signal || '—')}</td>
        <td>${_fmtOI2(s.call_oi)}</td>
        <td>${_fmtOI2(s.put_oi)}</td>
        <td>₹${_fmtN(s.max_pain)}</td>
      </tr>`;
    }).join("");

    // Scroll to section
    section.scrollIntoView({ behavior: "smooth", block: "start" });

  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="9" class="text-danger text-center py-3">
      ${esc(err.message)}</td></tr>`;
  }
}


// ---------------------------------------------------------------------------
// Download historical Excel
// ---------------------------------------------------------------------------

async function downloadHistoryExcel() {
  const date = _currentHistoryDate;
  if (!date) {
    showToast("Please select a date first", "warning");
    return;
  }

  const btn = document.getElementById("btnHistoryExcel");
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Downloading…'; }

  try {
    const response = await fetch(`${API_BASE}/history/download/${date}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const blob     = await response.blob();
    const filename = `StockGPT_History_${date}.xlsx`;
    const url      = URL.createObjectURL(blob);
    const a        = document.createElement("a");
    a.href = url; a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 5000);
    showToast(`Downloaded: ${filename}`, "success");
  } catch (err) {
    showToast("Download failed: " + err.message, "danger");
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-file-earmark-excel me-1"></i>Download Excel'; }
  }
}


// ---------------------------------------------------------------------------
// Local helpers
// ---------------------------------------------------------------------------

function _formatDate(d) {
  if (!d) return "—";
  try {
    const dt = new Date(d + "T00:00:00");
    return dt.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
  } catch (_) { return d; }
}

function _fmtN(n) {
  if (n == null || n === 0) return "—";
  return Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function _fmtOI2(n) {
  if (!n) return "—";
  if (n >= 1e7) return (n / 1e7).toFixed(2) + " Cr";
  if (n >= 1e5) return (n / 1e5).toFixed(1) + " L";
  return n.toLocaleString("en-IN");
}

function _fmtPctH(val) {
  if (val == null) return "—";
  const sign = val > 0 ? "+" : "";
  return sign + val.toFixed(1) + "%";
}

function _deltaClass(val) {
  if (val == null) return "text-secondary";
  return val > 0 ? "text-success" : val < 0 ? "text-danger" : "text-secondary";
}

function _pcrCls(pcr) {
  if (pcr == null) return "";
  if (pcr > 1.2)  return "text-success fw-bold";
  if (pcr >= 1.0) return "text-success";
  if (pcr >= 0.8) return "text-warning";
  return "text-danger";
}
