import pytest
import time
from app.utils.response_cache import TTLCache, rag_response_cache, sql_response_cache


def test_ttl_cache_basic_set_get():
    cache = TTLCache(maxsize=10, ttl_seconds=60)
    cache.set("value_1", "q1", "role1")
    assert cache.get("q1", "role1") == "value_1"
    assert cache.get("q1", "role2") is None


def test_ttl_cache_case_insensitivity():
    cache = TTLCache(maxsize=10, ttl_seconds=60)
    cache.set("result", "  What is the REVENUE? ", " C-LEVEL ")
    assert cache.get("what is the revenue?", "c-level") == "result"


def test_ttl_cache_expiry():
    cache = TTLCache(maxsize=10, ttl_seconds=1)
    cache.set("temp_val", "q_temp", "general")
    assert cache.get("q_temp", "general") == "temp_val"
    time.sleep(1.1)
    assert cache.get("q_temp", "general") is None


def test_ttl_cache_eviction_maxsize():
    cache = TTLCache(maxsize=2, ttl_seconds=60)
    cache.set("v1", "k1")
    cache.set("v2", "k2")
    cache.set("v3", "k3")  # Evicts k1
    assert cache.get("k1") is None
    assert cache.get("k2") == "v2"
    assert cache.get("k3") == "v3"


def test_ttl_cache_stats():
    cache = TTLCache(maxsize=10, ttl_seconds=60)
    cache.set("val", "k1")
    _ = cache.get("k1")  # Hit
    _ = cache.get("k2")  # Miss
    stats = cache.stats
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["size"] == 1
