"""Redis caching layer — schema, metrics, and query results.

Centralized caching strategy for the GenBI platform. Every cacheable entity
routes through this module with consistent TTL policies and cache invalidation.

Cache tiers:
    Level 1: In-memory LRU (sub-millisecond, per-process, 1000-entry max)
    Level 2: Redis (millisecond, shared across workers, persistent)

What's cached:
    - Schema embeddings (TTL: 24h — only changes on nightly sync)
    - Metric definitions (TTL: 5min — Cube.dev /meta)
    - Query results (TTL: 5min — read-heavy analytics)
    - LLM response cache (TTL: 1h — same query/schema = same SQL)
    - Rate limit counters (TTL: window-based)
    - Session state (TTL: 30min idle)

Cache keys are namespaced: genbi:{tenant_id}:{entity_type}:{hash}

Usage:
    cache = get_cache()

    # Schema
    schema = await cache.get_schema_context(query, tenant_id)
    await cache.set_schema_context(query, tenant_id, schema)

    # Metrics
    metrics = await cache.get_metric_definitions(tenant_id)
    await cache.set_metric_definitions(tenant_id, metrics)

    # Query results
    result = await cache.get_query_result(sql_hash, tenant_id)
    await cache.set_query_result(sql_hash, tenant_id, rows)

    # Invalidate
    await cache.invalidate_tenant(tenant_id)
    await cache.invalidate_schema(tenant_id)
"""

import contextlib
import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.core.logging import logger

# ---------------------------------------------------------------------------
# TTL configuration
# ---------------------------------------------------------------------------


class CacheTTL:
    """Time-to-live constants for each cache category."""

    SCHEMA_EMBEDDINGS = 86_400  # 24 hours
    METRIC_DEFINITIONS = 300  # 5 minutes
    QUERY_RESULTS = 300  # 5 minutes
    LLM_RESPONSE = 3_600  # 1 hour
    RATE_LIMIT = 60  # 1 minute window
    SESSION_STATE = 1_800  # 30 minutes
    CHART_SPEC = 3_600  # 1 hour


# ---------------------------------------------------------------------------
# Cache namespace helpers
# ---------------------------------------------------------------------------


def _key(tenant_id: str, entity: str, identifier: str) -> str:
    """Build a namespaced cache key."""
    return f"genbi:{tenant_id}:{entity}:{identifier}"


def _hash_query(query: str) -> str:
    """Hash a query string for deterministic cache keys."""
    return hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]


def _hash_sql(sql: str) -> str:
    """Hash a SQL string — normalize before hashing."""
    normalized = " ".join(sql.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _hash_data(data: list[dict]) -> str:
    """Hash query result data for cache identity."""
    canonical = json.dumps(data[:10], sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# In-memory LRU cache (Level 1)
# ---------------------------------------------------------------------------


class LRUCache:
    """Simple LRU cache with max size and TTL support.

    Used as the Level 1 in-memory cache before hitting Redis.
    Thread-safe via Python's GIL for the async single-thread model.
    """

    def __init__(self, max_size: int = 1000):
        self._max_size = max_size
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()

    def get(self, key: str, ttl_seconds: int = 300) -> Any | None:
        """Get a value if it exists and hasn't expired."""
        if key not in self._store:
            return None

        value, stored_at = self._store[key]
        age = time.time() - stored_at

        if age > ttl_seconds:
            del self._store[key]
            return None

        # Move to end (most recently used)
        self._store.move_to_end(key)
        return value

    def set(self, key: str, value: Any) -> None:
        """Set a value, evicting the least recently used if at capacity."""
        if key in self._store:
            self._store.move_to_end(key)

        self._store[key] = (value, time.time())

        # Evict LRU if over capacity
        while len(self._store) > self._max_size:
            self._store.popitem(last=False)

    def invalidate(self, prefix: str | None = None) -> int:
        """Invalidate all entries, or those matching a prefix."""
        count = 0
        if prefix is None:
            count = len(self._store)
            self._store.clear()
        else:
            keys_to_delete = [k for k in self._store if k.startswith(prefix)]
            for k in keys_to_delete:
                del self._store[k]
            count = len(keys_to_delete)
        return count

    def stats(self) -> dict:
        """Return cache stats."""
        return {
            "size": len(self._store),
            "max_size": self._max_size,
            "utilization_pct": round(len(self._store) / self._max_size * 100, 1),
        }


# ---------------------------------------------------------------------------
# Redis-based cache (Level 2)
# ---------------------------------------------------------------------------


class RedisCache:
    """Redis-backed cache — shared across workers, persistent.

    Uses connection pooling and graceful degradation: if Redis is down,
    operations are no-ops rather than failures.
    """

    def __init__(self):
        self._redis = None
        self._available = False
        self._init_attempted = False

    async def ping(self) -> bool:
        """Health probe — True if Redis is reachable right now.

        Distinct from ``_ensure``: ``_ensure`` is lazy and memoizes a failure for
        the process lifetime (so a transient Redis blip at startup never
        recovers). ``ping`` re-checks on every call, making it suitable for
        readiness probes.
        """
        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=2,
            )
            try:
                await client.ping()
                return True
            finally:
                await client.aclose()
        except Exception as e:
            logger.debug(f"Redis ping failed: {e}")
            return False

    async def _ensure(self) -> bool:
        """Lazy-init Redis connection. Returns True if available."""
        if self._init_attempted:
            return self._available

        self._init_attempted = True
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=False,
                socket_connect_timeout=3,
                socket_keepalive=True,
                health_check_interval=30,
                max_connections=20,
            )
            await self._redis.ping()
            self._available = True
            logger.info("Redis cache connected")
        except ImportError:
            logger.warning("redis package not installed — Redis cache disabled")
            self._available = False
        except Exception as e:
            logger.warning(f"Redis unavailable, using in-memory cache only — {e}")
            self._available = False

        return self._available

    async def get(self, key: str) -> Any | None:
        """Get a raw value from Redis."""
        if not await self._ensure():
            return None

        try:
            raw = await self._redis.get(key)
            if raw is None:
                return None

            data = json.loads(raw if isinstance(raw, (str, bytes)) else raw.decode("utf-8"))
            return data
        except Exception:
            return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set a value with TTL in Redis."""
        if not await self._ensure():
            return

        try:
            await self._redis.setex(key, ttl, json.dumps(value, default=str))
        except Exception as e:
            logger.debug(f"Redis set failed (non-fatal): {e}")

    async def delete(self, key: str) -> None:
        """Delete a key from Redis."""
        if not await self._ensure():
            return

        with contextlib.suppress(Exception):
            await self._redis.delete(key)

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern. Returns count of deleted keys."""
        if not await self._ensure():
            return 0

        try:
            cursor = 0
            count = 0
            while True:
                cursor, keys = await self._redis.scan(cursor, match=pattern, count=100)
                if keys:
                    await self._redis.delete(*keys)
                    count += len(keys)
                if cursor == 0:
                    break
            return count
        except Exception:
            return 0

    async def exists(self, key: str) -> bool:
        """Check if a key exists in Redis."""
        if not await self._ensure():
            return False

        try:
            return bool(await self._redis.exists(key))
        except Exception:
            return False

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis:
            with contextlib.suppress(Exception):
                await self._redis.close()
            self._redis = None
            self._available = False


# ---------------------------------------------------------------------------
# Unified Cache Service
# ---------------------------------------------------------------------------


@dataclass
class CacheStats:
    """Aggregate cache statistics."""

    l1_size: int = 0
    l1_max: int = 1000
    l1_hits: int = 0
    l1_misses: int = 0
    l2_hits: int = 0
    l2_misses: int = 0
    writes: int = 0
    invalidations: int = 0

    @property
    def l1_hit_rate(self) -> float:
        total = self.l1_hits + self.l1_misses
        return self.l1_hits / total * 100 if total > 0 else 0.0

    @property
    def l2_hit_rate(self) -> float:
        total = self.l2_hits + self.l2_misses
        return self.l2_hits / total * 100 if total > 0 else 0.0


class CacheService:
    """Two-level cache: in-memory LRU (L1) + Redis (L2).

    Read path: L1 → L2 → miss → compute → L2 → L1
    Write path: compute → L2 + L1 simultaneously

    All operations are async-safe. Cache misses are returned as None —
    the caller is responsible for computing and re-caching the value.
    """

    def __init__(self, l1_max_size: int = 1000):
        self._l1 = LRUCache(max_size=l1_max_size)
        self._l2 = RedisCache()
        self._stats = CacheStats()

    # ------------------------------------------------------------------
    # Schema context cache
    # ------------------------------------------------------------------

    async def get_schema_context(self, query: str, tenant_id: str) -> list[dict] | None:
        """Get cached schema context for a query."""
        query_hash = _hash_query(query)
        key = _key(tenant_id, "schema", query_hash)

        # L1
        value = self._l1.get(key, CacheTTL.SCHEMA_EMBEDDINGS)
        if value is not None:
            self._stats.l1_hits += 1
            return value

        # L2
        value = await self._l2.get(key)
        if value is not None:
            self._stats.l2_hits += 1
            self._l1.set(key, value)  # Promote to L1
            return value

        self._stats.l2_misses += 1
        return None

    async def set_schema_context(self, query: str, tenant_id: str, context: list[dict]) -> None:
        """Cache schema context for a query."""
        query_hash = _hash_query(query)
        key = _key(tenant_id, "schema", query_hash)

        self._l1.set(key, context)
        await self._l2.set(key, context, ttl=CacheTTL.SCHEMA_EMBEDDINGS)
        self._stats.writes += 1

    # ------------------------------------------------------------------
    # Few-shot examples cache
    # ------------------------------------------------------------------

    async def get_few_shot_examples(self, query: str, tenant_id: str) -> list[dict] | None:
        """Get cached few-shot examples for a query."""
        query_hash = _hash_query(query)
        key = _key(tenant_id, "fewshot", query_hash)

        value = self._l1.get(key, CacheTTL.LLM_RESPONSE)
        if value is not None:
            self._stats.l1_hits += 1
            return value

        value = await self._l2.get(key)
        if value is not None:
            self._stats.l2_hits += 1
            self._l1.set(key, value)
            return value

        self._stats.l2_misses += 1
        return None

    async def set_few_shot_examples(self, query: str, tenant_id: str, examples: list[dict]) -> None:
        """Cache few-shot examples for a query."""
        query_hash = _hash_query(query)
        key = _key(tenant_id, "fewshot", query_hash)

        self._l1.set(key, examples)
        await self._l2.set(key, examples, ttl=CacheTTL.LLM_RESPONSE)
        self._stats.writes += 1

    # ------------------------------------------------------------------
    # Metric definitions cache
    # ------------------------------------------------------------------

    async def get_metric_definitions(self, tenant_id: str) -> dict | None:
        """Get cached metric definitions from Cube.dev."""
        key = _key(tenant_id, "metrics", "all")

        # L1
        value = self._l1.get(key, CacheTTL.METRIC_DEFINITIONS)
        if value is not None:
            self._stats.l1_hits += 1
            return value

        # L2
        value = await self._l2.get(key)
        if value is not None:
            self._stats.l2_hits += 1
            self._l1.set(key, value)
            return value

        self._stats.l2_misses += 1
        return None

    async def set_metric_definitions(self, tenant_id: str, metrics: dict) -> None:
        """Cache metric definitions."""
        key = _key(tenant_id, "metrics", "all")
        self._l1.set(key, metrics)
        await self._l2.set(key, metrics, ttl=CacheTTL.METRIC_DEFINITIONS)
        self._stats.writes += 1

    async def get_metric_catalog(self, tenant_id: str) -> list | None:
        """Get the cached /metrics/list catalog (Phase 20)."""
        key = _key(tenant_id, "metric_catalog", "all")

        value = self._l1.get(key, CacheTTL.METRIC_DEFINITIONS)
        if value is not None:
            self._stats.l1_hits += 1
            return value

        value = await self._l2.get(key)
        if value is not None:
            self._stats.l2_hits += 1
            self._l1.set(key, value)
            return value

        self._stats.l2_misses += 1
        return None

    async def set_metric_catalog(self, tenant_id: str, catalog: list) -> None:
        """Cache the /metrics/list catalog (Phase 20)."""
        key = _key(tenant_id, "metric_catalog", "all")
        self._l1.set(key, catalog)
        await self._l2.set(key, catalog, ttl=CacheTTL.METRIC_DEFINITIONS)
        self._stats.writes += 1

    # ------------------------------------------------------------------
    # Query result cache
    # ------------------------------------------------------------------

    async def get_query_result(self, sql: str, tenant_id: str) -> list[dict] | None:
        """Get cached query result."""
        sql_hash = _hash_sql(sql)
        key = _key(tenant_id, "query", sql_hash)

        # L1
        value = self._l1.get(key, CacheTTL.QUERY_RESULTS)
        if value is not None:
            self._stats.l1_hits += 1
            logger.debug("Query result cache hit (L1)", key=key[:40])
            return value

        # L2
        value = await self._l2.get(key)
        if value is not None:
            self._stats.l2_hits += 1
            self._l1.set(key, value)
            logger.debug("Query result cache hit (L2)", key=key[:40])
            return value

        self._stats.l2_misses += 1
        return None

    async def set_query_result(self, sql: str, tenant_id: str, rows: list[dict]) -> None:
        """Cache a query result."""
        sql_hash = _hash_sql(sql)
        key = _key(tenant_id, "query", sql_hash)

        self._l1.set(key, rows)
        await self._l2.set(key, rows, ttl=CacheTTL.QUERY_RESULTS)
        self._stats.writes += 1

    # ------------------------------------------------------------------

    async def get_cube_query_result(self, cube_query: dict, tenant_id: str) -> dict | None:
        """Get a cached Cube (semantic-layer) query result.

        Keyed by tenant + a hash of the canonical query JSON — same query,
        same tenant, same answer within the QUERY_RESULTS TTL.
        """
        key = _key(tenant_id, "cube_query", _hash_sql(json.dumps(cube_query, sort_keys=True)))

        value = self._l1.get(key, CacheTTL.QUERY_RESULTS)
        if value is not None:
            self._stats.l1_hits += 1
            return value

        value = await self._l2.get(key)
        if value is not None:
            self._stats.l2_hits += 1
            self._l1.set(key, value)
            return value

        self._stats.l2_misses += 1
        return None

    async def set_cube_query_result(self, cube_query: dict, tenant_id: str, result: dict) -> None:
        """Cache a Cube (semantic-layer) query result."""
        key = _key(tenant_id, "cube_query", _hash_sql(json.dumps(cube_query, sort_keys=True)))

        self._l1.set(key, result)
        await self._l2.set(key, result, ttl=CacheTTL.QUERY_RESULTS)
        self._stats.writes += 1

    # ------------------------------------------------------------------
    # LLM response cache
    # ------------------------------------------------------------------

    async def get_llm_response(self, prompt_hash: str, tenant_id: str) -> dict | None:
        """Get a cached LLM response.

        LLM responses are cached by prompt hash + tenant_id.
        Same question + same schema = same SQL (deterministic at temp=0).
        """
        key = _key(tenant_id, "llm", prompt_hash)

        # L2 only for LLM responses (too large for L1 with many variants)
        value = await self._l2.get(key)
        if value is not None:
            self._stats.l2_hits += 1
            return value

        self._stats.l2_misses += 1
        return None

    async def set_llm_response(self, prompt_hash: str, tenant_id: str, response: dict) -> None:
        """Cache an LLM response."""
        key = _key(tenant_id, "llm", prompt_hash)
        await self._l2.set(key, response, ttl=CacheTTL.LLM_RESPONSE)
        self._stats.writes += 1

    # ------------------------------------------------------------------
    # Chart spec cache
    # ------------------------------------------------------------------

    async def get_chart_spec(self, data_hash: str, tenant_id: str) -> dict | None:
        """Get a cached chart spec for a data signature."""
        key = _key(tenant_id, "chart", data_hash)

        value = self._l1.get(key, CacheTTL.CHART_SPEC)
        if value is not None:
            self._stats.l1_hits += 1
            return value

        value = await self._l2.get(key)
        if value is not None:
            self._stats.l2_hits += 1
            self._l1.set(key, value)
            return value

        self._stats.l2_misses += 1
        return None

    async def set_chart_spec(self, data_hash: str, tenant_id: str, spec: dict) -> None:
        """Cache a chart spec."""
        key = _key(tenant_id, "chart", data_hash)
        self._l1.set(key, spec)
        await self._l2.set(key, spec, ttl=CacheTTL.CHART_SPEC)
        self._stats.writes += 1

    # ------------------------------------------------------------------
    # Session state
    # ------------------------------------------------------------------

    async def get_session(self, session_id: str) -> dict | None:
        """Get cached session state."""
        key = f"genbi:session:{session_id}"
        return await self._l2.get(key)

    async def set_session(
        self, session_id: str, state: dict, ttl: int = CacheTTL.SESSION_STATE
    ) -> None:
        """Cache session state."""
        key = f"genbi:session:{session_id}"
        await self._l2.set(key, state, ttl=ttl)

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    async def check_rate_limit(
        self, user_id: str, max_requests: int = 30, window_seconds: int = 60
    ) -> tuple[bool, int]:
        """Rate-limit check using Redis INCR + TTL.

        Returns:
            (allowed, remaining_requests)
        """
        if not await self._l2._ensure():
            return True, max_requests  # Allow all if Redis is down

        key = f"genbi:ratelimit:{user_id}"
        try:
            current = await self._l2._redis.incr(key)
            if current == 1:
                await self._l2._redis.expire(key, window_seconds)

            remaining = max(0, max_requests - current)
            return current <= max_requests, remaining
        except Exception:
            return True, max_requests

    # ------------------------------------------------------------------

    async def register_failed_login(self, email: str) -> int:
        """Count a failed login attempt for an email (Redis INCR + TTL).

        Returns the failure count in the current lockout window. Fails open
        (returns 0) when Redis is unavailable — availability over lockout.
        """
        from app.core.config import settings

        if not await self._l2._ensure():
            return 0

        key = f"genbi:loginfail:{email.strip().lower()}"
        with contextlib.suppress(Exception):
            current = await self._l2._redis.incr(key)
            if current == 1:
                await self._l2._redis.expire(key, settings.LOGIN_LOCKOUT_SECONDS)
            return int(current)
        return 0

    async def login_failures(self, email: str) -> int:
        """Current failed-login count for an email (0 when Redis is down)."""
        if not await self._l2._ensure():
            return 0

        with contextlib.suppress(Exception):
            value = await self._l2._redis.get(f"genbi:loginfail:{email.strip().lower()}")
            return int(value or 0)
        return 0

    async def clear_failed_logins(self, email: str) -> None:
        """Reset the failure counter after a successful login."""
        if not await self._l2._ensure():
            return

        with contextlib.suppress(Exception):
            await self._l2._redis.delete(f"genbi:loginfail:{email.strip().lower()}")

    # ------------------------------------------------------------------
    # Invalidation
    # ------------------------------------------------------------------

    async def invalidate_tenant(self, tenant_id: str) -> int:
        """Invalidate all cached data for a tenant."""
        pattern = f"genbi:{tenant_id}:*"
        l1_count = self._l1.invalidate(prefix=f"genbi:{tenant_id}:")
        l2_count = await self._l2.delete_pattern(pattern)
        total = l1_count + l2_count
        logger.info(f"Invalidated {total} cache entries for tenant {tenant_id}")
        self._stats.invalidations += total
        return total

    async def invalidate_schema(self, tenant_id: str) -> int:
        """Invalidate schema-related caches (after nightly embed sync)."""
        schema_pattern = f"genbi:{tenant_id}:schema:*"
        l1_count = self._l1.invalidate(prefix=f"genbi:{tenant_id}:schema:")
        l2_count = await self._l2.delete_pattern(schema_pattern)
        total = l1_count + l2_count
        logger.info(f"Invalidated {total} schema cache entries")
        self._stats.invalidations += total
        return total

    async def invalidate_metrics(self, tenant_id: str) -> int:
        """Invalidate metric definition caches."""
        metrics_pattern = f"genbi:{tenant_id}:metrics:*"
        l1_count = self._l1.invalidate(prefix=f"genbi:{tenant_id}:metrics:")
        l2_count = await self._l2.delete_pattern(metrics_pattern)
        total = l1_count + l2_count
        self._stats.invalidations += total
        return total

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    async def ping(self) -> bool:
        """Health probe — True if Redis (L2) is reachable right now.

        Used by the /health/ready readiness check. Does not probe L1 (in-memory),
        which is always available if the process is running.
        """
        return await self._l2.ping()

    def get_stats(self) -> dict:
        """Get cache performance metrics."""
        return {
            "l1": self._l1.stats(),
            "l1_hits": self._stats.l1_hits,
            "l1_misses": self._stats.l1_misses,
            "l1_hit_rate": f"{self._stats.l1_hit_rate:.1f}%",
            "l2_hits": self._stats.l2_hits,
            "l2_misses": self._stats.l2_misses,
            "l2_hit_rate": f"{self._stats.l2_hit_rate:.1f}%",
            "writes": self._stats.writes,
            "invalidations": self._stats.invalidations,
        }

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close Redis connection."""
        await self._l2.close()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_cache_service: CacheService | None = None


def get_cache() -> CacheService:
    """Get or create the singleton CacheService."""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService(l1_max_size=1000)
    return _cache_service
