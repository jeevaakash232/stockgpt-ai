"""
Cache Service
-------------
In-memory TTL cache. All external API calls go through here.
Frontend always reads cached data — never hits Yahoo/NSE directly.
Cache refreshes automatically every 60 seconds per key.
"""

import time
import threading
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# RLock (reentrant) allows the same thread to acquire the lock multiple times.
# This prevents deadlocks when cached functions call other cached functions.
_lock  = threading.RLock()
_store: dict[str, dict] = {}   # key -> {data, expires_at, refresh_fn}

TTL = 60  # seconds


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get(key: str) -> Optional[Any]:
    """Return cached value if still fresh, else None."""
    with _lock:
        entry = _store.get(key)
        if entry and time.time() < entry["expires_at"]:
            return entry["data"]
    return None


def set(key: str, data: Any, ttl: int = TTL) -> None:
    """Store a value with a TTL (seconds)."""
    with _lock:
        _store[key] = {
            "data":       data,
            "expires_at": time.time() + ttl,
        }


def get_or_fetch(key: str, fetch_fn: Callable, ttl: int = TTL) -> Any:
    """
    Return cached value if fresh; otherwise call fetch_fn(), cache and return.
    Thread-safe — only one fetch runs per key even under concurrent requests.
    """
    cached = get(key)
    if cached is not None:
        return cached

    # Re-check inside lock to avoid duplicate fetches
    with _lock:
        entry = _store.get(key)
        if entry and time.time() < entry["expires_at"]:
            return entry["data"]

        try:
            data = fetch_fn()
            _store[key] = {
                "data":       data,
                "expires_at": time.time() + ttl,
            }
            logger.debug("Cache MISS → fetched [%s]", key)
            return data
        except Exception as exc:
            # On fetch failure return stale data if available
            if entry:
                logger.warning("Fetch failed for [%s], returning stale data: %s", key, exc)
                return entry["data"]
            raise


def invalidate(key: str) -> None:
    """Force-expire a cache key so it refreshes on next access."""
    with _lock:
        if key in _store:
            _store[key]["expires_at"] = 0


def start_background_refresh(key: str, fetch_fn: Callable, interval: int = TTL) -> None:
    """
    Spawn a daemon thread that proactively refreshes a cache key every
    `interval` seconds so it's always warm when the frontend requests it.
    """
    def _worker():
        while True:
            time.sleep(interval)
            try:
                data = fetch_fn()
                set(key, data, ttl=interval + 10)
                logger.debug("Background refresh OK [%s]", key)
            except Exception as exc:
                logger.warning("Background refresh failed [%s]: %s", key, exc)

    t = threading.Thread(target=_worker, daemon=True, name=f"cache-refresh-{key}")
    t.start()
    logger.info("Background refresh thread started for [%s] every %ds", key, interval)
