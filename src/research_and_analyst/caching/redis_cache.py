"""
Redis-backed response cache for Tavily search results (and reusable for any
other JSON-serialisable LLM/tool output).

Falls back to a process-local in-memory dict if REDIS_URL isn't set or the
Redis connection fails at construction time, so the workflow keeps working
in local/dev environments without Redis installed — it just loses cross-
process/cross-restart cache reuse.
"""

import os
import json
import hashlib
import logging
from typing import Any, Optional

log = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 60 * 60 * 6  # 6 hours — search results go stale but not instantly


class SearchResultCache:
    """Key-value cache for search query -> result-list, Redis-backed with in-memory fallback."""

    def __init__(self, namespace: str = "tavily_search", ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self.namespace = namespace
        self.ttl_seconds = ttl_seconds
        self._memory_store: dict = {}
        self._redis = None

        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            try:
                import redis

                self._redis = redis.Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=2)
                self._redis.ping()
                log.info("Redis cache connected | namespace=%s | url=%s", namespace, self._mask_url(redis_url))
            except Exception as e:
                log.warning(
                    "Redis unavailable (%s) — falling back to in-memory cache for this process", str(e)
                )
                self._redis = None
        else:
            log.info("REDIS_URL not set — using in-memory cache (no cross-process reuse)")

    @staticmethod
    def _mask_url(url: str) -> str:
        # Avoid logging credentials embedded in redis://user:pass@host:port
        if "@" in url:
            return "redis://***@" + url.split("@", 1)[1]
        return url

    def _key(self, query: str) -> str:
        digest = hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()[:24]
        return f"{self.namespace}:{digest}"

    def get(self, query: str) -> Optional[Any]:
        key = self._key(query)
        if self._redis is not None:
            try:
                raw = self._redis.get(key)
                return json.loads(raw) if raw else None
            except Exception as e:
                log.warning("Redis GET failed, falling back to memory | error=%s", str(e))
        return self._memory_store.get(key)

    def set(self, query: str, value: Any) -> None:
        key = self._key(query)
        if self._redis is not None:
            try:
                self._redis.set(key, json.dumps(value), ex=self.ttl_seconds)
                return
            except Exception as e:
                log.warning("Redis SET failed, falling back to memory | error=%s", str(e))
        self._memory_store[key] = value

    @property
    def backend(self) -> str:
        return "redis" if self._redis is not None else "memory"
