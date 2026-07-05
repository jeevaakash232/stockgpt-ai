/**
 * app.js — Tab navigation, sidebar toggle, refresh timestamp.
 */

document.addEventListener("DOMContentLoaded", () => {
  showTab("dashboard", document.querySelector(".sidebar-link.active"));
  startKeepAlive();
  console.log("StockGPT AI v2.0 ready.");
});

// ---------------------------------------------------------------------------
// Keep-alive — ping backend every 10 min to prevent Render free tier sleep
// ---------------------------------------------------------------------------
function startKeepAlive() {
  // Only runs when deployed (not localhost)
  if (window.location.hostname === "localhost" ||
      window.location.hostname === "127.0.0.1") return;

  setInterval(() => {
    fetch(`${API_BASE}/`)
      .then(() => console.log("Keep-alive ping OK"))
      .catch(() => {});
  }, 10 * 60 * 1000);  // every 10 minutes
}


// ---------------------------------------------------------------------------
// Tab switching
// ---------------------------------------------------------------------------
function showTab(tabName, linkEl) {
  // Hide all panels
  document.querySelectorAll(".tab-panel").forEach(p => p.style.display = "none");

  // Show selected
  const panel = document.getElementById("tab-" + tabName);
  if (panel) panel.style.display = "block";

  // Update sidebar active state
  document.querySelectorAll(".sidebar-link").forEach(l => l.classList.remove("active"));
  if (linkEl) linkEl.classList.add("active");

  // Close mobile sidebar after nav
  if (window.innerWidth < 992) closeSidebar();

  // Lazy-load data for tabs that need it
  if (tabName === "pcr")     loadPCRFullTable();
  if (tabName === "watchlist") loadWatchlistTab();
  if (tabName === "history") initHistoryTab();}


// ---------------------------------------------------------------------------
// Inner tabs (Gainers / Losers / Most Active)
// ---------------------------------------------------------------------------
function switchInnerTab(name, btn) {
  // Hide all inner panels
  document.querySelectorAll(".inner-panel").forEach(p => p.style.display = "none");
  // Show selected
  const panel = document.getElementById("inner-" + name);
  if (panel) panel.style.display = "block";

  // Update button states
  document.querySelectorAll(".inner-tab").forEach(b => b.classList.remove("active"));
  if (btn) btn.classList.add("active");
}


// ---------------------------------------------------------------------------
// PCR Table — full 11-column option chain table
// ---------------------------------------------------------------------------
let _pcrLoaded  = false;
let _pcrData    = [];      // full dataset for client-side sort/filter
let _pcrSortCol = -1;
let _pcrSortAsc = true;

async function loadPCRFullTable() {
  const tbody = document.getElementById("pcrFullBody");
  if (!tbody) return;

  try {
    const data = await apiFetch("/market");
    _pcrData   = data;
    _pcrLoaded = true;
    _renderPCRTable(data, tbody);
    _initPCRTooltips();
  } catch (err) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="12" class="text-danger text-center py-3">
      <i class="bi bi-exclamation-triangle me-1"></i>${esc(err.message)}</td></tr>`;
  }
}

function _renderPCRTable(data, tbody) {
  if (!tbody) tbody = document.getElementById("pcrFullBody");
  if (!tbody) return;
  tbody.innerHTML = "";

  data.forEach(s => {
    const row = document.createElement("tr");
    row.setAttribute("data-symbol", s.symbol);

    row.innerHTML = `
      <td>
        <strong class="stock-link" onclick="openStockDetail('${esc(s.symbol)}')"
          style="cursor:pointer" title="Open ${esc(s.symbol)} detail">
          ${esc(s.symbol)}
        </strong>
      </td>
      <td class="text-end ${_deltaColour(s.price_chg_pct)}" title="Price % change since yesterday close">
        ${_fmtPct(s.price_chg_pct, 1)}
      </td>
      <td class="text-end" title="Total Call Open Interest">
        ${fmtOI(s.call_oi)}
      </td>
      <td class="text-end" title="Total Put Open Interest">
        ${fmtOI(s.put_oi)}
      </td>
      <td class="text-end" title="Max Pain strike price">
        ${s.max_pain ? '₹' + Number(s.max_pain).toLocaleString("en-IN") : '—'}
      </td>
      <td class="text-end fw-semibold ${_pcrColour(s.pcr)}" title="Current day PCR = Put OI / Call OI">
        ${s.pcr != null ? s.pcr : '—'}
      </td>
      <td class="text-end fw-semibold ${_pcrColour(s.prev_day_pcr)}" title="Previous day closing PCR">
        ${s.prev_day_pcr != null ? s.prev_day_pcr : '—'}
      </td>
      <td class="text-end ${_deltaColour(s.pcr_change)}" title="PCR change since yesterday (Current - Previous)">
        ${_fmtDelta(s.pcr_change, 2, true)}
      </td>
      <td>
        <div class="d-flex gap-1">
          <button class="btn btn-xs btn-outline-warning py-0 px-2"
            onclick="openStockDetail('${esc(s.symbol)}')" title="Stock detail & option chain">
            <i class="bi bi-box-arrow-up-right"></i>
          </button>
          <button class="btn btn-xs btn-outline-secondary py-0 px-2"
            onclick="analyzeStock('${esc(s.symbol)}')" title="Analyze with AI">
            <i class="bi bi-robot"></i>
          </button>
        </div>
      </td>`;
    tbody.appendChild(row);
  });
}

// Auto-refresh PCR table if it's visible (respects smart interval)
function refreshPCRIfVisible() {
  const tab = document.getElementById("tab-pcr");
  if (tab && tab.style.display !== "none") {
    loadPCRFullTable();
  }
}

// Called by dashboard's scheduleNextRefresh
const _origSchedule = typeof scheduleNextRefresh !== "undefined"
  ? scheduleNextRefresh : null;

function _initPCRTooltips() {
  // Bootstrap tooltips on th[data-tip]
  document.querySelectorAll("#pcrFullTable th[data-tip]").forEach(th => {
    th.title = th.getAttribute("data-tip");
  });
}

// ---------------------------------------------------------------------------
// PCR Table — filter
// ---------------------------------------------------------------------------
function filterPCRTable(query) {
  const q    = query.toUpperCase().trim();
  const rows = document.querySelectorAll("#pcrFullBody tr");
  rows.forEach(row => {
    const sym = row.querySelector("strong");
    if (!sym) return;
    row.style.display = (!q || sym.textContent.includes(q)) ? "" : "none";
  });
}

// ---------------------------------------------------------------------------
// PCR Table — sort
// ---------------------------------------------------------------------------
function sortPCRTable(colIndex) {
  if (_pcrSortCol === colIndex) {
    _pcrSortAsc = !_pcrSortAsc;
  } else {
    _pcrSortCol = colIndex;
    _pcrSortAsc = false;   // default: descending (highest first)
  }

  // Update header arrow
  document.querySelectorAll("#pcrFullTable th").forEach((th, i) => {
    th.classList.remove("sort-asc", "sort-desc");
    if (i === colIndex) th.classList.add(_pcrSortAsc ? "sort-asc" : "sort-desc");
  });

  const keys = [
    "symbol", "price_chg_pct", "call_oi", "put_oi", "max_pain",
    "pcr", "prev_day_pcr", "pcr_change"
  ];
  const key = keys[colIndex];
  if (!key) return;

  const sorted = [..._pcrData].sort((a, b) => {
    const av = a[key], bv = b[key];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    const cmp = typeof av === "string" ? av.localeCompare(bv) : av - bv;
    return _pcrSortAsc ? cmp : -cmp;
  });

  _renderPCRTable(sorted);
}


// ---------------------------------------------------------------------------
// Delta formatting helpers
// ---------------------------------------------------------------------------

function _deltaColour(val) {
  if (val == null) return "text-secondary";
  if (val > 0)     return "text-success";
  if (val < 0)     return "text-danger";
  return "text-secondary";
}

function _pcrColour(pcr) {
  if (pcr == null) return "";
  if (pcr > 1.2)   return "text-success";
  if (pcr >= 1.0)  return "text-success";
  if (pcr >= 0.8)  return "text-warning";
  return "text-danger";
}

function _fmtPrice(n) {
  if (!n) return "—";
  return Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function _fmtDelta(val, decimals = 2, showPlus = true) {
  if (val == null) return '<span class="text-secondary">—</span>';
  const sign = (showPlus && val > 0) ? "+" : "";
  return sign + val.toFixed(decimals);
}

function _fmtPct(val, decimals = 0) {
  if (val == null) return '<span class="text-secondary">—</span>';
  const sign = val > 0 ? "+" : "";
  return sign + val.toFixed(decimals) + "%";
}


// ---------------------------------------------------------------------------
// Watchlist tab — add from input box
// ---------------------------------------------------------------------------
async function loadWatchlistTab() {
  // dashboard.js renderWatchlist already targets #watchlistBody
  // Just refresh watchlist data
  try {
    const data = await apiFetch("/watchlist");
    renderWatchlist(data);
  } catch (_) {}
}

async function addSymbolFromInput() {
  const input = document.getElementById("watchlistAdd");
  if (!input) return;
  const sym = input.value.trim().toUpperCase();
  if (!sym) return;
  await addToWatchlist(sym);
  input.value = "";
  loadWatchlistTab();
}


// ---------------------------------------------------------------------------
// Market table filter (Markets tab)
// ---------------------------------------------------------------------------
function filterMarketTable(query) {
  const q    = query.toUpperCase().trim();
  const rows = document.querySelectorAll("#pcrTableBody tr");
  rows.forEach(row => {
    const sym = row.querySelector("strong");
    if (!sym) return;
    row.style.display = (!q || sym.textContent.includes(q)) ? "" : "none";
  });
}


// ---------------------------------------------------------------------------
// Market table sort
// ---------------------------------------------------------------------------
let _sortCol = 0, _sortAsc = true;

function sortMarketTable(col) {
  const tbody = document.getElementById("pcrTableBody");
  if (!tbody) return;
  _sortAsc = (_sortCol === col) ? !_sortAsc : true;
  _sortCol = col;

  const rows = Array.from(tbody.querySelectorAll("tr"));
  rows.sort((a, b) => {
    const av = a.cells[col - 1]?.textContent.replace(/[₹,]/g, "").trim() || "";
    const bv = b.cells[col - 1]?.textContent.replace(/[₹,]/g, "").trim() || "";
    const an = parseFloat(av), bn = parseFloat(bv);
    const cmp = isNaN(an) || isNaN(bn) ? av.localeCompare(bv) : an - bn;
    return _sortAsc ? cmp : -cmp;
  });
  rows.forEach(r => tbody.appendChild(r));
}


// ---------------------------------------------------------------------------
// Mobile sidebar
// ---------------------------------------------------------------------------
function toggleSidebar() {
  const sidebar = document.getElementById("mainSidebar");
  const overlay = document.getElementById("sidebarOverlay");
  sidebar?.classList.toggle("open");
  overlay?.classList.toggle("active");
}

function closeSidebar() {
  document.getElementById("mainSidebar")?.classList.remove("open");
  document.getElementById("sidebarOverlay")?.classList.remove("active");
}


// ---------------------------------------------------------------------------
// Last refresh label
// ---------------------------------------------------------------------------
function updateLastRefresh() {
  const el = document.getElementById("lastRefreshLabel");
  if (!el) return;
  const now = new Date();
  const pad = n => String(n).padStart(2, "0");
  el.textContent = `Last updated ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
}


// ---------------------------------------------------------------------------
// fmtOI helper (used in PCR full table)
// ---------------------------------------------------------------------------
function fmtOI(n) {
  if (!n) return "—";
  if (n >= 1e7) return (n / 1e7).toFixed(2) + " Cr";
  if (n >= 1e5) return (n / 1e5).toFixed(1) + " L";
  if (n >= 1e3) return (n / 1e3).toFixed(0) + " K";
  return String(n);
}
