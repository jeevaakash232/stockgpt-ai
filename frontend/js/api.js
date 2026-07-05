/**
 * api.js — Central API config and fetch wrapper.
 *
 * AUTO-DETECTS environment:
 *  - localhost / file://  → talks to local backend (127.0.0.1:8000)
 *  - Netlify / any other  → talks to the Render backend URL
 *
 * To deploy: set RENDER_BACKEND_URL below to your Render service URL.
 */

const RENDER_BACKEND_URL = "https://stockgpt-ai.onrender.com";

const API_BASE = (
  window.location.hostname === "localhost" ||
  window.location.hostname === "127.0.0.1" ||
  window.location.protocol === "file:"
)
  ? "http://127.0.0.1:8000/api"
  : `${RENDER_BACKEND_URL}/api`;


/**
 * Fetch wrapper with JSON serialisation and descriptive errors.
 *
 * @param {string} path    - e.g. "/chat" or "/market"
 * @param {object} options - Standard fetch options
 * @returns {Promise<any>} - Parsed JSON
 */
async function apiFetch(path, options = {}) {
  const url = `${API_BASE}${path}`;

  // On production (Render), allow up to 2 minutes for cold starts
  const isLocal = window.location.hostname === "localhost" ||
                  window.location.hostname === "127.0.0.1";
  const controller = new AbortController();
  const timeoutMs  = isLocal ? 30000 : 120000;
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      ...options,
    });

    if (!response.ok) {
      let message = `HTTP ${response.status}`;
      try {
        const err = await response.json();
        message = err.detail || message;
      } catch (_) {}
      throw new Error(message);
    }

    return response.json();
  } finally {
    clearTimeout(timer);
  }
}
