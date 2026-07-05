/**
 * dashboard.js — Full dashboard data loading and rendering.
 *
 * Loads: indices, top gainers/losers, most active, watchlist.
 * Auto-refreshes every 60 seconds (only updates changed values).
 */

const REFRESH_INTERVAL = 60_000; // ms
let _refreshTimer = null;
let _prevValues   = {};   // track previous values to flash changes
let _dashData     = {};   // store full dashboard data for limit changes

// Per-table limits (changed by dropdown)
let _limits = { gainers: 25, losers: 25, mostActive: 25 };

document.addEventListener("DOMContentLoaded", () => {
  loadDashboard();
  _refreshTimer = setInterval(loadDashboard, REFRESH_INTERVAL);
});


// ---------------------------------------------------------------------------
// Main dashboard loader
// ---------------------------------------------------------------------------

async function loadDashboard() {
  try {
    const data = await apiFetch("/dashboard");

    // Store full data so limit changes re-render without re-fetching
    _dashData = data;

    renderIndices(data.indices       || {});
    renderMarketOverview(data.marketOverview || {});
    _renderMoversWithLimit("gainers",    data.topGainers  || []);
    _renderMoversWithLimit("losers",     data.topLosers   || []);
    _renderMoversWithLimit("mostActive", data.mostActive  || []);
    renderWatchlist(data.watchlist || []);
    hideBanner("offlineBanner");
    if (typeof updateLastRefresh === "function") updateLastRefresh();
  } catch (err) {
    console.error("Dashboard load failed:", err);
    // Show "waking up" if it's a network error (Render free tier sleep)
    const isWaking = err.message.includes("Failed to fetch") ||
                     err.message.includes("NetworkError") ||
                     err.message.includes("502") ||
                     err.message.includes("503");
    showBanner("offlineBanner",
      isWaking
        ? `<span class="spinner-border spinner-border-sm me-2"></span>
           <strong>Waking up the server…</strong> Render free tier sleeps after 15 min of inactivity.
           This takes up to 60 seconds. <span id="wakeCountdown"></span>`
        : `<i class="bi bi-exclamation-triangle-fill me-2"></i>
           <strong>Backend offline.</strong> Run <code>python run.py</code> in <code>backend/</code>`
    );
    if (isWaking) startWakeCountdown();
  }
}


// ---------------------------------------------------------------------------
// Limit dropdown handler — called by HTML onchange
// ---------------------------------------------------------------------------

function setMoversLimit(type, value) {
  _limits[type] = value === "all" ? Infinity : parseInt(value, 10);

  // Re-render with new limit from stored data (no API call needed)
  const map = {
    gainers:    { bodyId: "gainersBody",    key: "topGainers" },
    losers:     { bodyId: "losersBody",     key: "topLosers"  },
    mostActive: { bodyId: "mostActiveBody", key: "mostActive" },
  };
  const { bodyId, key } = map[type] || {};
  if (bodyId && _dashData[key]) {
    _renderMoversWithLimit(type, _dashData[key]);
  }
}


// Apply current limit and call renderMoversTable
function _renderMoversWithLimit(type, rows) {
  const bodyMap = {
    gainers:    "gainersBody",
    losers:     "losersBody",
    mostActive: "mostActiveBody",
  };
  const limit  = _limits[type] || 25;
  const sliced = isFinite(limit) ? rows.slice(0, limit) : rows;
  renderMoversTable(bodyMap[type], sliced, type);
}


// ---------------------------------------------------------------------------
// setMoversLimit — called by the single dropdown in the inner tab bar
// ---------------------------------------------------------------------------
function setMoversLimit(type, value) {
  const n = value === "all" ? Infinity : parseInt(value, 10);
  if (type === "all") {
    // apply to whichever inner tab is currently visible
    _limits.gainers    = n;
    _limits.losers     = n;
    _limits.mostActive = n;
    if (_dashData.topGainers)  _renderMoversWithLimit("gainers",    _dashData.topGainers);
    if (_dashData.topLosers)   _renderMoversWithLimit("losers",     _dashData.topLosers);
    if (_dashData.mostActive)  _renderMoversWithLimit("mostActive", _dashData.mostActive);
  } else {
    _limits[type] = n;
    const key = type === "gainers" ? "topGainers" : type === "losers" ? "topLosers" : "mostActive";
    if (_dashData[key]) _renderMoversWithLimit(type, _dashData[key]);
  }
}


// ---------------------------------------------------------------------------
// Indices row (NIFTY / BANKNIFTY / SENSEX / VIX)
// ---------------------------------------------------------------------------

function renderIndices(indices) {
  // ── Navbar strip ────────────────────────────────────────
  const navMap = {
    "idxNifty":     "NIFTY",
    "idxBankNifty": "BANKNIFTY",
    "idxSensex":    "SENSEX",
    "idxVix":       "INDIAVIX",
  };
  for (const [elemId, key] of Object.entries(navMap)) {
    const idx  = indices[key] || {};
    const wrap = document.getElementById(elemId);
    if (!wrap) continue;
    const priceEl = wrap.querySelector(".idx-price");
    const chgEl   = wrap.querySelector(".idx-change");
    if (priceEl) flashUpdate(priceEl, fmt(idx.current_price), `nav-price:${key}`);
    if (chgEl) {
      const pct = idx.change_pct ?? 0;
      const sign = pct >= 0 ? "+" : "";
      chgEl.textContent = `${sign}${pct}%`;
      chgEl.className   = "idx-change " + (pct >= 0 ? "text-success" : "text-danger");
    }
  }

  // ── Index section cards ──────────────────────────────────
  const cardMap = [
    { priceId: "idxCardNiftyPrice",  chgId: "idxCardNiftyChg",  key: "NIFTY" },
    { priceId: "idxCardBankPrice",   chgId: "idxCardBankChg",   key: "BANKNIFTY" },
    { priceId: "idxCardSensexPrice", chgId: "idxCardSensexChg", key: "SENSEX" },
    { priceId: "idxCardVixPrice",    chgId: "idxCardVixChg",    key: "INDIAVIX" },
  ];
  for (const { priceId, chgId, key } of cardMap) {
    const idx  = indices[key] || {};
    const pct  = idx.change_pct ?? 0;
    const sign = pct >= 0 ? "+" : "";
    flashUpdate(byId(priceId), fmt(idx.current_price), `card-price:${key}`);
    const chgEl = byId(chgId);
    if (chgEl) {
      chgEl.textContent = `${sign}${pct}%`;
      chgEl.className   = "idx-card-change " + (pct >= 0 ? "text-success" : "text-danger");
    }
  }
}


// ---------------------------------------------------------------------------
// Market overview cards (NIFTY PCR / Signal / OI)
// ---------------------------------------------------------------------------

function renderMarketOverview(ov) {
  flashUpdate(byId("cardLTP"),       fmtINR(ov.nifty_ltp),    "cardLTP");
  flashUpdate(byId("cardPCR"),       ov.pcr ?? "—",            "cardPCR");
  flashUpdate(byId("cardMaxPain"),   fmtINR(ov.max_pain),      "cardMaxPain");
  flashUpdate(byId("cardSentiment"), ov.signal ?? "—",         "cardSentiment");
  flashUpdate(byId("cardCallOI"),    fmtCr(ov.total_call_oi),  "cardCallOI");
  flashUpdate(byId("cardPutOI"),     fmtCr(ov.total_put_oi),   "cardPutOI");

  const sent = byId("cardSentiment");
  if (sent) sent.className = "summary-value " + signalClass(ov.signal);
}


// ---------------------------------------------------------------------------
// Gainers / Losers / Most-Active tables
// ---------------------------------------------------------------------------

function renderMoversTable(tbodyId, rows, type) {
  const tbody = byId(tbodyId);
  if (!tbody) return;

  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">No data</td></tr>`;
    return;
  }

  tbody.innerHTML = rows.map((s, i) => {
    const pct      = s.change_pct ?? 0;
    const sign     = pct >= 0 ? "+" : "";
    const cls      = pct >= 0 ? "text-success" : "text-danger";
    const arrow    = pct >= 0 ? "bi-arrow-up-short" : "bi-arrow-down-short";
    const volStr   = s.volume ? fmtVol(s.volume) : "—";

    return `<tr>
      <td class="text-muted">${i + 1}</td>
      <td>
        <strong class="stock-link" onclick="openStockDetail('${esc(s.symbol)}')"
          style="cursor:pointer">${esc(s.symbol)}</strong>
      </td>
      <td>₹${fmt(s.price)}</td>
      <td class="${cls}">
        <i class="bi ${arrow}"></i>${sign}${pct}%
      </td>
      <td class="text-muted">${volStr}</td>
      <td>
        <button class="btn btn-xs btn-outline-warning py-0 px-2"
          onclick="analyzeStock('${esc(s.symbol)}')">
          <i class="bi bi-robot"></i>
        </button>
        <button class="btn btn-xs btn-outline-secondary py-0 px-2 ms-1"
          onclick="addToWatchlist('${esc(s.symbol)}')">
          <i class="bi bi-star"></i>
        </button>
      </td>
    </tr>`;
  }).join("");
}


// ---------------------------------------------------------------------------
// Watchlist
// ---------------------------------------------------------------------------

function renderWatchlist(items) {
  const tbody = byId("watchlistBody");
  if (!tbody) return;

  if (!items.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-3">
      <i class="bi bi-star me-1"></i>Your watchlist is empty.
      Add stocks using the <i class="bi bi-star"></i> button in any table.
    </td></tr>`;
    return;
  }

  tbody.innerHTML = items.map(s => {
    const pct   = s.change_pct ?? 0;
    const sign  = pct >= 0 ? "+" : "";
    const cls   = pct >= 0 ? "text-success" : "text-danger";
    const price = s.price != null ? `₹${fmt(s.price)}` : "—";

    return `<tr>
      <td>
        <strong class="stock-link" onclick="openStockDetail('${esc(s.symbol)}')"
          style="cursor:pointer">${esc(s.symbol)}</strong>
      </td>
      <td>${price}</td>
      <td class="${cls}">${sign}${pct}%</td>
      <td>
        <button class="btn btn-xs btn-outline-warning py-0 px-2"
          onclick="analyzeStock('${esc(s.symbol)}')">
          <i class="bi bi-robot"></i>
        </button>
      </td>
      <td>
        <button class="btn btn-xs btn-outline-danger py-0 px-2"
          onclick="removeFromWatchlist('${esc(s.symbol)}')">
          <i class="bi bi-trash3"></i>
        </button>
      </td>
    </tr>`;
  }).join("");
}


// ---------------------------------------------------------------------------
// Watchlist actions
// ---------------------------------------------------------------------------

async function addToWatchlist(symbol) {
  try {
    await apiFetch("/watchlist", {
      method:  "POST",
      body:    JSON.stringify({ symbol }),
    });
    showToast(`${symbol} added to watchlist`, "success");
    loadDashboard();
  } catch (err) {
    showToast(err.message, "warning");
  }
}

async function removeFromWatchlist(symbol) {
  try {
    await apiFetch(`/watchlist/${symbol}`, { method: "DELETE" });
    showToast(`${symbol} removed`, "info");
    loadDashboard();
  } catch (err) {
    showToast(err.message, "danger");
  }
}


// ---------------------------------------------------------------------------
// Flash animation: highlight a value only when it changes
// ---------------------------------------------------------------------------

function flashUpdate(el, value, cacheKey) {
  if (!el) return;
  const strVal = String(value ?? "—");
  if (_prevValues[cacheKey] !== strVal) {
    _prevValues[cacheKey] = strVal;
    el.textContent = strVal;
    el.classList.add("value-flash");
    setTimeout(() => el.classList.remove("value-flash"), 800);
  }
}


// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function byId(id) { return document.getElementById(id); }
function fmt(n)   { return n != null ? Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 }) : "—"; }
function fmtINR(n) { return n != null ? `₹${fmt(n)}` : "—"; }
function fmtCr(n)  { return n != null ? `${(n / 1e7).toFixed(2)} Cr` : "—"; }
function fmtVol(n) {
  if (n >= 1e7) return `${(n / 1e7).toFixed(1)}Cr`;
  if (n >= 1e5) return `${(n / 1e5).toFixed(1)}L`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return String(n);
}

function signalClass(sig) {
  const s = (sig || "").toLowerCase();
  if (s.includes("strong bullish")) return "text-success fw-bold";
  if (s.includes("bullish"))        return "text-success";
  if (s.includes("bearish"))        return "text-danger";
  return "text-warning";
}

function esc(str) {
  return String(str)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function hideBanner(id) {
  const el = byId(id);
  if (el) el.remove();
}

function showBanner(id, html) {
  if (byId(id)) { byId(id).innerHTML = html; return; }
  const el = document.createElement("div");
  el.id        = id;
  el.className = "alert alert-warning d-flex align-items-center gap-2 mb-4";
  el.innerHTML = html;
  const main   = document.querySelector(".main-content");
  if (main) main.prepend(el);
}

// Wake-up countdown — retries every 8 seconds
let _wakeTimer = null;
let _wakeSeconds = 0;

function startWakeCountdown() {
  clearInterval(_wakeTimer);
  _wakeSeconds = 0;
  _wakeTimer = setInterval(() => {
    _wakeSeconds += 8;
    const el = document.getElementById("wakeCountdown");
    if (el) el.textContent = `(${_wakeSeconds}s elapsed)`;

    // Try again every 8 seconds
    fetch(`${API_BASE}/`)
      .then(r => { if (r.ok) { clearInterval(_wakeTimer); loadDashboard(); } })
      .catch(() => {});

    // Give up after 90 seconds
    if (_wakeSeconds >= 90) {
      clearInterval(_wakeTimer);
      showBanner("offlineBanner",
        `<i class="bi bi-exclamation-triangle-fill me-2"></i>
         <strong>Server unreachable.</strong>
         Backend at <code>${API_BASE.replace("/api","")}</code> is not responding.
         <a href="${API_BASE.replace("/api","")}/docs" target="_blank" class="ms-2">Check status</a>`
      );
    }
  }, 8000);
}

function showToast(message, type = "info") {
  const container = byId("toastContainer");
  if (!container) return;
  const id   = "toast-" + Date.now();
  const html = `
    <div id="${id}" class="toast align-items-center text-bg-${type} border-0 show" role="alert">
      <div class="d-flex">
        <div class="toast-body">${esc(message)}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto"
          onclick="document.getElementById('${id}').remove()"></button>
      </div>
    </div>`;
  container.insertAdjacentHTML("beforeend", html);
  setTimeout(() => { const el = byId(id); if (el) el.remove(); }, 3500);
}
