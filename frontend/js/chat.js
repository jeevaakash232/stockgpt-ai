/**
 * chat.js — AI Chat module for StockGPT
 *
 * Features:
 * - ChatGPT-style bubbles (user right, AI left)
 * - Markdown rendering via marked.js
 * - Auto-scroll to latest message
 * - Loading animation while waiting for AI
 * - Disable send button during request
 * - Press Enter to send (Shift+Enter for newline)
 * - Full error handling
 */

document.addEventListener("DOMContentLoaded", () => {
  const input  = document.getElementById("chatInput");
  const btn    = document.getElementById("chatSendBtn");

  if (!input || !btn) return;

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      askAI();
    }
  });

  btn.addEventListener("click", () => askAI());
});


/**
 * Main chat function — reads the input, calls the API,
 * appends messages to the chat window.
 * @param {string} [prefillSymbol] - optional symbol to send for richer AI context
 */
async function askAI(prefillSymbol = "") {
  const input   = document.getElementById("chatInput");
  const btn     = document.getElementById("chatSendBtn");
  const window_ = document.getElementById("chatWindow");

  const question = input.value.trim();
  if (!question) return;

  // Render user bubble
  appendMessage(window_, question, "user");

  // Clear input and disable controls
  input.value = "";
  setLoading(true, btn, input);

  // Show typing indicator
  const typingId = showTyping(window_);

  try {
    const body = { question };
    if (prefillSymbol) body.symbol = prefillSymbol;

    const data = await apiFetch("/chat", {
      method: "POST",
      body: JSON.stringify(body),
    });

    removeTyping(typingId, window_);
    appendMessage(window_, data.answer, "ai");
  } catch (err) {
    removeTyping(typingId, window_);
    appendMessage(
      window_,
      `⚠️ **Error:** ${err.message || "Could not reach StockGPT. Is the backend running?"}`,
      "ai error"
    );
  } finally {
    setLoading(false, btn, input);
    input.focus();
  }
}


// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function appendMessage(container, text, type) {
  const wrapper = document.createElement("div");
  wrapper.classList.add("chat-message", type === "user" ? "user-message" : "ai-message");

  const bubble = document.createElement("div");
  bubble.classList.add("chat-bubble");

  if (type === "user") {
    // Plain text for user messages (sanitised by textContent)
    bubble.textContent = text;
  } else {
    // Render Markdown for AI responses
    bubble.innerHTML = renderMarkdown(text);
  }

  wrapper.appendChild(bubble);
  container.appendChild(wrapper);
  scrollToBottom(container);
}

function showTyping(container) {
  const id = "typing-" + Date.now();
  const wrapper = document.createElement("div");
  wrapper.classList.add("chat-message", "ai-message");
  wrapper.id = id;
  wrapper.innerHTML = `
    <div class="chat-bubble typing-indicator">
      <span></span><span></span><span></span>
    </div>`;
  container.appendChild(wrapper);
  scrollToBottom(container);
  return id;
}

function removeTyping(id, container) {
  const el = container.querySelector(`#${id}`);
  if (el) el.remove();
}

function setLoading(loading, btn, input) {
  btn.disabled  = loading;
  input.disabled = loading;
  btn.innerHTML  = loading
    ? `<span class="spinner-border spinner-border-sm" role="status"></span>`
    : `Send`;
}

function scrollToBottom(el) {
  el.scrollTop = el.scrollHeight;
}

/**
 * Render Markdown to safe HTML.
 * Uses marked.js if available; falls back to basic formatting.
 */
function renderMarkdown(text) {
  if (typeof marked !== "undefined") {
    // marked v4+ uses marked.parse()
    return marked.parse(text);
  }
  // Basic fallback: escape HTML then convert newlines
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\n/g, "<br>");
}
