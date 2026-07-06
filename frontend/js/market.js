/**
 * market.js — PCR/Market table for the Markets tab.
 *
 * Loads /api/market into #pcrTableBody (Markets tab).
 * analyzeStock() switches to the AI Chat tab and auto-sends.
 * Utility functions (esc, signalClass, fmt, fmtCr) live in dashboard.js.
 */

document.addEventListener("DOMContentLoaded", () => {
  loadPCRTable();
});


// ---------------------------------------------------------------------------
// PCR Table — Markets tab
// ---------------------------------------------------------------------------

async function loadPCRTable() {
  const tbody = document.getElementById("pcrTableBody");
  if (!tbody) return;

  try {
    const data = await apiFetch("/market");
    tbody.innerHTML = "";

    data.forEach((s, idx) => {
      const row = document.createElement("tr");
      row.setAttribute("data-symbol", s.symbol);
      row.innerHTML = `
        <td>${idx + 1}</td>
        <td>
          <strong class="stock-link" onclick="openStockDetail('${esc(s.symbol)}')"
            style="cursor:pointer">${esc(s.symbol)}</strong>
        </td>
        <td class="text-warning fw-semibold">
          ₹${Number(s.ltp).toLocaleString("en-IN", { maximumFractionDigits: 2 })}
        </td>
        <td>${s.pcr}</td>
        <td class="${signalClass(s.signal)}">${esc(s.signal)}</td>
        <td>
          <button class="btn btn-xs btn-outline-warning py-0 px-2"
            onclick="analyzeStock('${esc(s.symbol)}')">
            <i class="bi bi-robot"></i> Analyze
          </button>
          <button class="btn btn-xs btn-outline-secondary py-0 px-2 ms-1"
            onclick="addToWatchlist('${esc(s.symbol)}')">
            <i class="bi bi-star"></i>
          </button>
        </td>`;
      tbody.appendChild(row);
    });
  } catch (err) {
    if (tbody) tbody.innerHTML = `
      <tr><td colspan="6" class="text-danger text-center py-3">
        <i class="bi bi-exclamation-triangle me-1"></i>${esc(err.message)}
      </td></tr>`;
    console.error("loadPCRTable:", err);
  }
}


// ---------------------------------------------------------------------------
// analyzeStock — pre-fills chat and switches to AI Chat tab
// ---------------------------------------------------------------------------
function analyzeStock(symbol) {
  const input = document.getElementById("chatInput");
  if (input) {
    input.value = `Analyze ${symbol} — PCR, OI build-up, Max Pain, Support & Resistance, and overall outlook.`;
  }

  // Switch to the AI Chat tab
  const chatLink = document.querySelector('.sidebar-link[onclick*="chat"]');
  showTab("chat", chatLink);

  // Scroll chat into view and fire
  const chatSection = document.getElementById("tab-chat");
  if (chatSection) chatSection.scrollIntoView({ behavior: "smooth" });

  setTimeout(() => askAI(symbol), 350);
}
