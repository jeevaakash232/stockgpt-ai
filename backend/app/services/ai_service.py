"""
AI Service
----------
Wraps the Groq API to provide AI-powered stock analysis.
Credentials loaded from .env — re-read on every call so a key
change + restart always takes effect immediately.
"""

import os
import logging
from groq import Groq
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are StockGPT — an expert AI assistant for the Indian Stock Market.

Your areas of expertise:
- NSE/BSE equity and derivatives markets
- Option Chain analysis (Call/Put OI, Max Pain)
- Put-Call Ratio (PCR) interpretation
- Open Interest (OI) build-up and unwinding
- Support & Resistance levels (pivot-point based)
- Option strategies (covered calls, spreads, straddles, etc.)
- Risk analysis and position sizing
- NIFTY, BANKNIFTY, and individual stock analysis

Strict Rules:
1. NEVER guarantee profits or specific price targets.
2. Always explain your reasoning step by step.
3. Use ONLY the live market data supplied — do not hallucinate prices.
4. If the supplied data is insufficient, clearly state what is missing.
5. Always include a brief risk warning at the end of every analysis.
6. Format all responses using Markdown (headings, bullet points, bold).
7. Keep responses concise yet thorough — max 400 words unless asked for more.
8. Use Indian number format (Lakh, Crore) where appropriate.
"""


def _get_client() -> Groq:
    """Return a fresh Groq client using the current .env key."""
    load_dotenv(override=True)
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key or api_key.startswith("gsk_PASTE"):
        raise EnvironmentError(
            "GROQ_API_KEY is missing or a placeholder. "
            "Add your real key to backend/.env and restart."
        )
    return Groq(api_key=api_key)


def _get_model() -> str:
    load_dotenv(override=True)
    return os.getenv("MODEL_NAME", "meta-llama/llama-4-scout-17b-16e-instruct").strip()


def ask_ai(question: str, market_data: list[dict], extra_context: dict = None) -> str:
    """
    Send a question + market data to Groq and return the AI analysis.

    Args:
        question:      User's question.
        market_data:   List of stock dicts from get_market().
        extra_context: Optional dict with stock detail or index data.

    Returns:
        Markdown-formatted AI response string.
    """
    market_table   = _format_market_table(market_data)
    extra_sections = _format_extra_context(extra_context or {})

    prompt = f"""## Live Market Data — Indian Stock Market

{market_table}
{extra_sections}
## User Question

{question}
"""

    client = _get_client()
    model  = _get_model()
    logger.info("Groq request: model=%s question_len=%d", model, len(question))

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        temperature=0.3,
        max_tokens=1024,
    )

    return response.choices[0].message.content


def _format_market_table(market_data: list[dict]) -> str:
    """Convert market data list into a Markdown table."""
    if not market_data:
        return "_No market data available._"

    lines = [
        "| Symbol | LTP ₹ | PCR | Signal | Call OI | Put OI | Max Pain |",
        "|--------|--------|-----|--------|---------|--------|----------|",
    ]
    for s in market_data:
        ltp      = f"₹{s.get('ltp', 0):,.2f}"
        call_oi  = _fmt_oi(s.get("call_oi", 0))
        put_oi   = _fmt_oi(s.get("put_oi",  0))
        lines.append(
            f"| {s.get('symbol','-')} | {ltp} | {s.get('pcr',0)} "
            f"| {s.get('signal','-')} | {call_oi} | {put_oi} "
            f"| ₹{s.get('max_pain',0):,} |"
        )
    return "\n".join(lines)


def _format_extra_context(ctx: dict) -> str:
    """Format optional extra context (stock detail, indices) for the prompt."""
    sections = []

    # Live indices
    indices = ctx.get("indices", {})
    if indices:
        lines = ["\n## Live Index Prices\n"]
        for name, data in indices.items():
            if isinstance(data, dict) and data.get("current_price"):
                pct  = data.get("change_pct", 0)
                sign = "+" if pct >= 0 else ""
                lines.append(
                    f"- **{name}**: ₹{data['current_price']:,}  "
                    f"({sign}{pct}%)"
                )
        sections.append("\n".join(lines))

    # Stock detail (option chain + OHLCV)
    symbol = ctx.get("symbol")
    if symbol:
        detail_lines = [f"\n## Detailed Data — {symbol}\n"]
        fields = [
            ("Current Price", f"₹{ctx.get('current_price', 'N/A'):,}"),
            ("Open",          f"₹{ctx.get('open', 'N/A')}"),
            ("High",          f"₹{ctx.get('high', 'N/A')}"),
            ("Low",           f"₹{ctx.get('low',  'N/A')}"),
            ("Prev Close",    f"₹{ctx.get('prev_close', 'N/A')}"),
            ("PCR",           ctx.get("pcr", "N/A")),
            ("Signal",        ctx.get("signal", "N/A")),
            ("Call OI",       _fmt_oi(ctx.get("call_oi", 0))),
            ("Put OI",        _fmt_oi(ctx.get("put_oi",  0))),
            ("Max Pain",      f"₹{ctx.get('max_pain', 'N/A')}"),
            ("Support",       f"₹{ctx.get('support', 'N/A')}"),
            ("Resistance",    f"₹{ctx.get('resistance', 'N/A')}"),
            ("Pivot",         f"₹{ctx.get('pivot', 'N/A')}"),
        ]
        for label, val in fields:
            detail_lines.append(f"- **{label}**: {val}")
        sections.append("\n".join(detail_lines))

    return "\n".join(sections)


def _fmt_oi(value) -> str:
    """Format OI as Crore or Lakh."""
    try:
        n = int(value)
        if n >= 1_00_00_000:
            return f"{n / 1_00_00_000:.2f} Cr"
        if n >= 1_00_000:
            return f"{n / 1_00_000:.1f} L"
        return str(n)
    except (TypeError, ValueError):
        return str(value)
