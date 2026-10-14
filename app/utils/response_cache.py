"""
Thread-safe, TTL-based in-memory response cache.

Keyed by SHA-256(question + role) so raw query text is never stored as a key.
Two module-level singletons are exported:
  - rag_response_cache  (1 h TTL, 256 entries)
  - sql_response_cache  (30 min TTL, 512 entries)
"""
import hashlib
import logging
import threading
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TTLCache:
    """LRU-like in-memory cache with per-entry TTL and a max-size eviction policy."""

    def __init__(self, maxsize: int = 256, ttl_seconds: int = 3600):
        self._cache: dict[str, tuple[Any, float]] = {}
        self._maxsize = maxsize
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def make_key(self, *parts: str) -> str:
        """Return a stable SHA-256 hex key from one or more string parts."""
        combined = "|".join(str(p).strip().casefold() for p in parts)
        return hashlib.sha256(combined.encode()).hexdigest()

    def get(self, *key_parts: str) -> Optional[Any]:
        """Return cached value or None on miss / expiry."""
        key = self.make_key(*key_parts)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None
            value, expiry = entry
            if time.monotonic() > expiry:
                del self._cache[key]
                self._misses += 1
                return None
            self._hits += 1
            return value

    def set(self, value: Any, *key_parts: str) -> None:
        """Store value under the hash of key_parts."""
        key = self.make_key(*key_parts)
        with self._lock:
            if len(self._cache) >= self._maxsize:
                self._evict()
            self._cache[key] = (value, time.monotonic() + self._ttl)

    def invalidate(self, *key_parts: str) -> bool:
        """Remove a specific entry. Returns True if it existed."""
        key = self.make_key(*key_parts)
        with self._lock:
            return self._cache.pop(key, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    @property
    def stats(self) -> dict[str, int]:
        return {
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _evict(self) -> None:
        """Remove all expired entries; if none, remove the oldest one."""
        now = time.monotonic()
        expired = [k for k, (_, exp) in self._cache.items() if exp < now]
        if expired:
            for k in expired:
                del self._cache[k]
            logger.debug("[Cache] Evicted %d expired entries.", len(expired))
        elif self._cache:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            logger.debug("[Cache] Max-size reached — evicted oldest entry.")


# ---------------------------------------------------------------------------
# Module-level singletons (shared across the entire process lifetime)
# ---------------------------------------------------------------------------

# RAG answer cache: 1-hour TTL, up to 256 question+role pairs
rag_response_cache: TTLCache = TTLCache(maxsize=256, ttl_seconds=3600)

# SQL generation cache: 30-minute TTL, up to 512 question+role pairs
sql_response_cache: TTLCache = TTLCache(maxsize=512, ttl_seconds=1800)
