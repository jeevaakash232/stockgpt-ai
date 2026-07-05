/**
 * export.js — Excel and CSV download functions.
 * Uses the backend /api/export/excel and /api/export/csv endpoints.
 * No external JS library needed — browser handles the file download natively.
 */

/**
 * Download all stock data as a formatted Excel file.
 * Shows a loading state on the button while the server generates the file.
 */
async function downloadExcel() {
  const btn = document.getElementById("btnExcel");
  const fab = document.querySelector(".floating-download .btn");

  _setDownloadLoading(btn, true, "Excel");
  _setDownloadLoading(fab, true, "Downloading…");

  try {
    const response = await fetch(`${API_BASE}/export/excel`, {
      method: "GET",
      headers: { "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" },
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }

    // Get filename from Content-Disposition header if available
    const disposition = response.headers.get("Content-Disposition") || "";
    const match       = disposition.match(/filename="?([^";\n]+)"?/);
    const filename    = match ? match[1] : `StockGPT_${_dateStamp()}.xlsx`;

    // Stream the blob and trigger browser download
    const blob = await response.blob();
    _triggerDownload(blob, filename);

    showToast("Excel file downloaded: " + filename, "success");
  } catch (err) {
    console.error("Excel download failed:", err);
    showToast("Download failed: " + err.message, "danger");
  } finally {
    _setDownloadLoading(btn, false, "Excel");
    _setDownloadLoading(fab, false, "Download Excel");
  }
}


/**
 * Download all stock data as a plain CSV file.
 */
async function downloadCSV() {
  const btn = document.getElementById("btnCSV");
  _setDownloadLoading(btn, true, "CSV");

  try {
    const response = await fetch(`${API_BASE}/export/csv`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const text     = await response.text();
    const blob     = new Blob([text], { type: "text/csv;charset=utf-8;" });
    const filename = `StockGPT_${_dateStamp()}.csv`;

    _triggerDownload(blob, filename);
    showToast("CSV file downloaded: " + filename, "success");
  } catch (err) {
    console.error("CSV download failed:", err);
    showToast("CSV download failed: " + err.message, "danger");
  } finally {
    _setDownloadLoading(btn, false, "CSV");
  }
}


// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function _triggerDownload(blob, filename) {
  const url  = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href     = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  // Release the object URL after a short delay
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

function _setDownloadLoading(btn, loading, label) {
  if (!btn) return;
  btn.disabled = loading;
  if (loading) {
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1" role="status"></span>${label}…`;
  } else {
    // Restore icon based on label
    const icon = label.toLowerCase().includes("csv")
      ? "bi-filetype-csv"
      : "bi-file-earmark-excel";
    btn.innerHTML = `<i class="bi ${icon} me-1"></i>${label}`;
  }
}

function _dateStamp() {
  const now = new Date();
  const pad = n => String(n).padStart(2, "0");
  return `${now.getFullYear()}${pad(now.getMonth()+1)}${pad(now.getDate())}_${pad(now.getHours())}${pad(now.getMinutes())}`;
}
