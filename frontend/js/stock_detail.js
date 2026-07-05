/**
 * stock_detail.js — Stock detail modal with live data + TradingView chart.
 *
 * Opens a Bootstrap modal with:
 *   - OHLCV + 52-week range
 *   - PCR / OI / Max Pain / Support / Resistance
 *   - TradingView Advanced Chart widget (1m/5m/15m/1h/1D/1W)
 *   - "Analyze with AI" button that pre-fills chat
 */

function openStockDetail(symbol) {
  const modal = document.getElementById("stockModal");
  if (!modal) return;

  const bsModal = bootstrap.Modal.getOrCreateInstance(modal);

  // Reset and show modal with loading state
  setModalLoading(symbol);
  bsModal.show();

  loadStockDetail(symbol);
}

async function loadStockDetail(symbol) {
  try {
    const data = await apiFetch(`/stock/${encodeURIComponent(symbol)}`);
    renderStockModal(data);
  } catch (err) {
    document.getElementById("modalBody").innerHTML = `
      <div class="alert alert-danger">
        <i class="bi bi-exclamation-triangle me-2"></i>
        Failed to load data for <strong>${esc(symbol)}</strong>: ${esc(err.message)}
      </div>`;
  }
}

function setModalLoading(symbol) {
  const title = document.getElementById("modalStockTitle");
  const body  = document.getElementById("modalBody");
  if (title) title.textContent = symbol;
  if (body)  body.innerHTML = `
    <div class="text-center py-5">
      <div class="spinner-border text-warning" role="status"></div>
      <p class="mt-3 text-muted">Loading ${esc(symbol)}…</p>
    </div>`;
}

function renderStockModal(d) {
  const title = document.getElementById("modalStockTitle");
  if (title) title.textContent = `${d.symbol} — ₹${fmt(d.current_price)}`;

  const chg    = d.change_pct ?? 0;
  const sign   = chg >= 0 ? "+" : "";
  const cls    = chg >= 0 ? "text-success" : "text-danger";
  const arrow  = chg >= 0 ? "bi-arrow-up-short" : "bi-arrow-down-short";

  document.getElementById("modalBody").innerHTML = `
    <!-- Price header -->
    <div class="d-flex align-items-baseline gap-3 mb-3">
      <h3 class="mb-0 text-warning">₹${fmt(d.current_price)}</h3>
      <span class="${cls} fs-5">
        <i class="bi ${arrow}"></i>${sign}${chg}% (₹${fmt(d.change)})
      </span>
    </div>

    <!-- OHLCV grid -->
    <div class="row g-2 mb-3">
      ${statBox("Open",       fmtINR(d.open))}
      ${statBox("High",       fmtINR(d.high))}
      ${statBox("Low",        fmtINR(d.low))}
      ${statBox("Prev Close", fmtINR(d.prev_close))}
      ${statBox("Volume",     fmtVol(d.volume))}
      ${statBox("Mkt Cap",    fmtCap(d.market_cap))}
      ${statBox("52W High",   fmtINR(d.week_52_high))}
      ${statBox("52W Low",    fmtINR(d.week_52_low))}
    </div>

    <!-- Derivatives -->
    <div class="row g-2 mb-3">
      ${statBox("PCR",         d.pcr ?? "N/A", signalClass(d.signal))}
      ${statBox("Signal",      d.signal ?? "N/A", signalClass(d.signal))}
      ${statBox("Call OI",     fmtCr(d.call_oi))}
      ${statBox("Put OI",      fmtCr(d.put_oi))}
      ${statBox("Max Pain",    fmtINR(d.max_pain))}
      ${statBox("Pivot",       fmtINR(d.pivot))}
      ${statBox("Support",     fmtINR(d.support),  "text-success")}
      ${statBox("Resistance",  fmtINR(d.resistance), "text-danger")}
    </div>

    <!-- TradingView Chart -->
    <div class="mb-3">
      <div class="d-flex gap-2 mb-2 flex-wrap">
        ${["1", "5", "15", "60", "D", "W"].map(tf =>
          `<button class="btn btn-sm btn-outline-secondary tv-tf-btn" data-tf="${tf}"
            onclick="changeTVInterval('${esc(d.symbol)}', '${tf}', this)">
            ${tf === "D" ? "1D" : tf === "W" ? "1W" : tf + "m"}
          </button>`
        ).join("")}
      </div>
      <div id="tvChartContainer" class="tv-chart-wrap"></div>
    </div>

    <!-- AI Analyze button -->
    <button class="btn btn-warning w-100"
      onclick="analyzeStock('${esc(d.symbol)}'); bootstrap.Modal.getInstance(document.getElementById('stockModal')).hide()">
      <i class="bi bi-robot me-2"></i>Analyze ${esc(d.symbol)} with StockGPT AI
    </button>

    <!-- Option Chain Table (loaded async) -->
    <div id="optionChainSection" class="mt-3">
      <div class="d-flex align-items-center justify-content-between mb-2 flex-wrap gap-2">
        <h6 class="mb-0 text-warning"><i class="bi bi-table me-2"></i>Option Chain — ${esc(d.symbol)}</h6>
        <div class="d-flex align-items-center gap-2">
          <label for="ocExpirySelect" class="text-muted small mb-0">Expiry Date:</label>
          <select id="ocExpirySelect" class="form-select form-select-sm bg-dark text-white border-secondary"
            style="width: 145px; font-size: 0.8rem; height: 31px; padding: 2px 8px;"
            onchange="loadOptionChain('${esc(d.symbol)}', this.value)">
            <option value="">Loading…</option>
          </select>
        </div>
      </div>
      <div id="optionChainTable">
        <div class="text-center py-3 text-muted">
          <span class="spinner-border spinner-border-sm me-2"></span>Loading option chain…
        </div>
      </div>
    </div>
  `;

  // Load default chart (Daily)
  loadTVChart(d.symbol, "D");
  // Load option chain async (doesn't block modal render)
  loadOptionChain(d.symbol);

  // Highlight D button
  document.querySelectorAll(".tv-tf-btn").forEach(btn => {
    btn.classList.toggle("btn-warning", btn.dataset.tf === "D");
    btn.classList.toggle("btn-outline-secondary", btn.dataset.tf !== "D");
  });
}

function statBox(label, value, extraClass = "") {
  return `
    <div class="col-6 col-md-3">
      <div class="stat-box">
        <div class="stat-label">${label}</div>
        <div class="stat-value ${extraClass}">${value}</div>
      </div>
    </div>`;
}

// ---------------------------------------------------------------------------
// TradingView widget
// ---------------------------------------------------------------------------

function loadTVChart(symbol, interval) {
  const container = document.getElementById("tvChartContainer");
  if (!container) return;
  container.innerHTML = "";

  // Map interval to TradingView format
  const tvInterval = interval;

  // TradingView expects NSE:SYMBOL format
  const tvSymbol = `NSE:${symbol}`;

  const script  = document.createElement("script");
  script.type   = "text/javascript";
  script.src    = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
  script.async  = true;
  script.innerHTML = JSON.stringify({
    autosize:         true,
    height:           380,
    symbol:           tvSymbol,
    interval:         tvInterval,
    timezone:         "Asia/Kolkata",
    theme:            "dark",
    style:            "1",
    locale:           "en",
    gridColor:        "rgba(255,193,7,0.06)",
    toolbar_bg:       "#0d1117",
    enable_publishing: false,
    allow_symbol_change: true,
    container_id:     "tvChartContainer",
  });
  container.appendChild(script);
}

function changeTVInterval(symbol, interval, btn) {
  document.querySelectorAll(".tv-tf-btn").forEach(b => {
    b.classList.remove("btn-warning");
    b.classList.add("btn-outline-secondary");
  });
  btn.classList.add("btn-warning");
  btn.classList.remove("btn-outline-secondary");
  loadTVChart(symbol, interval);
}

// ---------------------------------------------------------------------------
// Format helpers (shared with dashboard.js via global scope)
// ---------------------------------------------------------------------------
function fmtCap(n) {
  if (n == null) return "N/A";
  if (n >= 1e12) return `₹${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e7)  return `₹${(n / 1e7).toFixed(2)} Cr`;
  return `₹${fmt(n)}`;
}


// ---------------------------------------------------------------------------
// Option Chain — loaded async after modal renders
// ---------------------------------------------------------------------------

async function loadOptionChain(symbol, targetExpiry = null) {
  const tableDiv = document.getElementById("optionChainTable");
  const select   = document.getElementById("ocExpirySelect");
  if (!tableDiv) return;

  try {
    const url = targetExpiry
      ? `/option-chain/${encodeURIComponent(symbol)}?expiry=${encodeURIComponent(targetExpiry)}`
      : `/option-chain/${encodeURIComponent(symbol)}`;
    const oc = await apiFetch(url);

    // Populate expiry dropdown selector
    if (select) {
      const dates = oc.expiry_dates && oc.expiry_dates.length
        ? oc.expiry_dates
        : (oc.expiry ? [oc.expiry] : []);

      if (dates.length) {
        select.innerHTML = dates.map(d =>
          `<option value="${esc(d)}" ${d === oc.expiry ? 'selected' : ''}>${esc(d)}</option>`
        ).join("");
      } else {
        select.innerHTML = `<option value="">Unavailable</option>`;
      }
    }

    const strikes = oc.strikes || [];
    if (!strikes.length) {
      tableDiv.innerHTML = `<p class="text-muted text-center py-2 small">
        Option chain data unavailable — live data requires market hours.
        ${oc.note ? '<br><em>' + esc(oc.note) + '</em>' : ''}
      </p>`;
      return;
    }

    // Find ATM strike (closest to underlying)
    const atm = oc.underlying || 0;
    const atmStrike = strikes.reduce((prev, curr) =>
      Math.abs(curr.strike - atm) < Math.abs(prev.strike - atm) ? curr : prev
    ).strike;

    // Sort by strike descending for display
    const sorted = [...strikes].sort((a, b) => b.strike - a.strike);

    tableDiv.innerHTML = `
      <div class="table-responsive" style="max-height:260px;overflow-y:auto">
        <table class="table table-dark table-sm mb-0" style="font-size:0.8rem">
          <thead class="sticky-top">
            <tr>
              <th class="text-success text-end">Call OI</th>
              <th class="text-success text-end">Call LTP</th>
              <th class="text-center text-warning">Strike</th>
              <th class="text-danger">Put LTP</th>
              <th class="text-danger">Put OI</th>
            </tr>
          </thead>
          <tbody>
            ${sorted.map(s => {
              const isATM = s.strike === atmStrike;
              const callBar = _oiBar(s.call_oi, oc.total_call_oi, "success");
              const putBar  = _oiBar(s.put_oi,  oc.total_put_oi,  "danger");
              return `<tr class="${isATM ? 'table-warning' : ''}">
                <td class="text-end text-success">
                  ${callBar}
                  <span>${fmtOI(s.call_oi)}</span>
                </td>
                <td class="text-end text-success">${s.call_ltp ? '₹' + fmt(s.call_ltp) : '—'}</td>
                <td class="text-center fw-bold ${isATM ? 'text-warning' : ''}">
                  ${fmt(s.strike)}${isATM ? ' ◄ ATM' : ''}
                </td>
                <td class="text-danger">${s.put_ltp ? '₹' + fmt(s.put_ltp) : '—'}</td>
                <td class="text-danger">
                  <span>${fmtOI(s.put_oi)}</span>
                  ${putBar}
                </td>
              </tr>`;
            }).join("")}
          </tbody>
        </table>
      </div>
      <div class="d-flex gap-3 mt-2 px-1 flex-wrap" style="font-size:0.75rem;color:var(--text-muted)">
        <span>Total Call OI: <strong class="text-success">${fmtOI(oc.total_call_oi)}</strong></span>
        <span>Total Put OI: <strong class="text-danger">${fmtOI(oc.total_put_oi)}</strong></span>
        <span>PCR: <strong class="${signalClass(oc.signal)}">${oc.pcr}</strong></span>
        <span>Max Pain: <strong class="text-warning">₹${fmt(oc.max_pain)}</strong></span>
        <span class="${oc.source === 'angel_one_live' ? 'text-success' : 'text-muted'}">
          ${oc.source === 'angel_one_live' ? '● Live' : '○ Estimated'}
        </span>
      </div>
    `;
  } catch (err) {
    if (tableDiv) tableDiv.innerHTML = `<p class="text-danger small py-2">
      <i class="bi bi-exclamation-triangle me-1"></i>Failed to load option chain: ${esc(err.message)}
    </p>`;
  }
}

function _oiBar(oi, total, color) {
  if (!total || !oi) return "";
  const pct = Math.min(100, Math.round((oi / total) * 100));
  return `<div class="d-inline-block bg-${color} bg-opacity-25 me-1"
    style="width:${pct}px;max-width:80px;height:6px;vertical-align:middle;border-radius:2px"></div>`;
}

function fmtOI(n) {
  if (!n) return "—";
  if (n >= 1e7) return (n / 1e7).toFixed(2) + " Cr";
  if (n >= 1e5) return (n / 1e5).toFixed(1) + " L";
  if (n >= 1e3) return (n / 1e3).toFixed(0) + " K";
  return String(n);
}
