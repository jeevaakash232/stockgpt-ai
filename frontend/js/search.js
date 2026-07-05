/**
 * search.js — Navbar stock search with autocomplete suggestions.
 *
 * Typing in the search box calls /api/search?q=...
 * Selecting a result opens the stock detail modal.
 */

document.addEventListener("DOMContentLoaded", initSearch);

function initSearch() {
  const input = document.getElementById("stockSearch");
  if (!input) return;

  // Create dropdown container
  const dropdown = document.createElement("ul");
  dropdown.id        = "searchDropdown";
  dropdown.className = "search-dropdown list-unstyled";
  dropdown.style.display = "none";
  input.parentNode.style.position = "relative";
  input.parentNode.appendChild(dropdown);

  let _debounce = null;

  input.addEventListener("input", () => {
    clearTimeout(_debounce);
    const q = input.value.trim();
    if (q.length < 1) { hideDropdown(dropdown); return; }
    _debounce = setTimeout(() => fetchSuggestions(q, dropdown, input), 220);
  });

  // Hide on outside click
  document.addEventListener("click", e => {
    if (!input.parentNode.contains(e.target)) hideDropdown(dropdown);
  });

  // Keyboard navigation
  input.addEventListener("keydown", e => {
    const items = dropdown.querySelectorAll("li[data-symbol]");
    const active = dropdown.querySelector("li.active");
    let idx = [...items].indexOf(active);
    if (e.key === "ArrowDown") {
      e.preventDefault();
      idx = Math.min(idx + 1, items.length - 1);
      items.forEach((li, i) => li.classList.toggle("active", i === idx));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      idx = Math.max(idx - 1, 0);
      items.forEach((li, i) => li.classList.toggle("active", i === idx));
    } else if (e.key === "Enter") {
      if (active) { active.click(); return; }
      if (input.value.trim()) openStockDetail(input.value.trim().toUpperCase());
      hideDropdown(dropdown);
    } else if (e.key === "Escape") {
      hideDropdown(dropdown);
    }
  });
}

async function fetchSuggestions(q, dropdown, input) {
  try {
    const results = await apiFetch(`/search?q=${encodeURIComponent(q)}`);
    renderSuggestions(results, dropdown, input);
  } catch (_) {
    hideDropdown(dropdown);
  }
}

function renderSuggestions(results, dropdown, input) {
  dropdown.innerHTML = "";
  if (!results.length) { hideDropdown(dropdown); return; }

  results.forEach(item => {
    const li = document.createElement("li");
    li.setAttribute("data-symbol", item.symbol);
    li.innerHTML = `
      <span class="fw-bold">${esc(item.symbol)}</span>
      <span class="text-muted ms-2 small">${esc(item.label)}</span>`;
    li.addEventListener("click", () => {
      input.value = item.symbol;
      hideDropdown(dropdown);
      openStockDetail(item.symbol);
    });
    dropdown.appendChild(li);
  });

  dropdown.style.display = "block";
}

function hideDropdown(dropdown) {
  dropdown.style.display = "none";
  dropdown.innerHTML = "";
}

// esc is defined in dashboard.js (loaded before this file)
