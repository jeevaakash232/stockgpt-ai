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
  if (tabName === "pcr") loadPCRFullTable();
  if (tabName === "watchlist") loadWatchlistTab();
}


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
// PCR tab — full table with all columns
// ---------------------------------------------------------------------------
let _pcrLoaded = false;

async function loadPCRFullTable() {
  if (_pcrLoaded) return;   // already loaded
  const tbody = document.getElementById("pcrFullBody");
  if (!tbody) return;

  try {
    const data = await apiFetch("/market");
    tbody.innerHTML = "";
    data.forEach(s => {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>
          <strong class="stock-link" onclick="openStockDetail('${esc(s.symbol)}')"
            style="cursor:pointer">${esc(s.symbol)}</strong>
        </td>
        <td class="text-warning">₹${Number(s.ltp).toLocaleString("en-IN", {maximumFractionDigits:2})}</td>
        <td>${s.pcr}</td>
        <td class="${signalClass(s.signal)}">${esc(s.signal)}</td>
        <td>${fmtOI(s.call_oi)}</td>
        <td>${fmtOI(s.put_oi)}</td>
        <td>₹${Number(s.max_pain).toLocaleString("en-IN")}</td>
        <td>
          <button class="btn btn-xs btn-outline-warning py-0 px-2"
            onclick="openStockDetail('${esc(s.symbol)}')">
            <i class="bi bi-box-arrow-up-right"></i>
          </button>
          <button class="btn btn-xs btn-outline-secondary py-0 px-2 ms-1"
            onclick="analyzeStock('${esc(s.symbol)}')">
            <i class="bi bi-robot"></i>
          </button>
        </td>`;
      tbody.appendChild(row);
    });
    _pcrLoaded = true;
  } catch (err) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="text-danger text-center py-3">
      Failed: ${esc(err.message)}</td></tr>`;
  }
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
