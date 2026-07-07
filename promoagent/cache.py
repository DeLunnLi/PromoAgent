"""Simple disk cache for Source2Launch.

Caches expensive network calls (GitHub API, Firecrawl) to avoid repeated requests.
Uses JSON files with TTL support.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable

# Default cache directory
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "promoagent"
DEFAULT_TTL_SECONDS = 3600  # 1 hour


def _make_key(*args: str) -> str:
    """Create a cache key from arguments."""
    combined = "|".join(args)
    return hashlib.sha256(combined.encode()).hexdigest()[:32]


def _cache_path(key: str, cache_dir: Path) -> Path:
    """Get the full path for a cache key."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{key}.json"


def _is_valid(entry: dict[str, Any], ttl_seconds: int) -> bool:
    """Check if a cache entry is still valid."""
    timestamp = entry.get("_cached_at", 0)
    return time.time() - timestamp < ttl_seconds


def get(
    *key_parts: str,
    cache_dir: Path | None = None,
    ttl_seconds: int | None = None,
) -> Any | None:
    """Get a value from cache if it exists and is valid.

    Args:
        key_parts: Parts that make up the cache key
        cache_dir: Custom cache directory (default: ~/.cache/promoagent)
        ttl_seconds: Time-to-live in seconds (default: 3600)

    Returns:
        Cached value or None if not found or expired
    """
    cache_dir = cache_dir or DEFAULT_CACHE_DIR
    ttl = ttl_seconds if ttl_seconds is not None else DEFAULT_TTL_SECONDS

    # Respect environment override
    env_ttl = os.environ.get("PROMOAGENT_CACHE_TTL")
    if env_ttl:
        try:
            ttl = int(env_ttl)
        except ValueError:
            pass

    key = _make_key(*key_parts)
    path = _cache_path(key, cache_dir)

    if not path.exists():
        return None

    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
        if _is_valid(entry, ttl):
            return entry.get("data")
    except (json.JSONDecodeError, OSError):
        pass

    return None


def set(
    *key_parts: str,
    data: Any,
    cache_dir: Path | None = None,
) -> None:
    """Save a value to cache.

    Args:
        key_parts: Parts that make up the cache key
        data: Data to cache (must be JSON serializable)
        cache_dir: Custom cache directory
    """
    cache_dir = cache_dir or DEFAULT_CACHE_DIR
    key = _make_key(*key_parts)
    path = _cache_path(key, cache_dir)

    entry = {
        "_cached_at": time.time(),
        "_key": key,
        "_key_parts": list(key_parts),  # Store original key parts for prefix matching
        "data": data,
    }

    try:
        path.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
    except (OSError, TypeError):
        pass  # Cache write failure is non-fatal


def cached(
    *key_prefix: str,
    ttl_seconds: int | None = None,
    cache_dir: Path | None = None,
    key_func: Callable | None = None,
) -> Callable:
    """Decorator to cache function results.

    Args:
        key_prefix: Prefix for cache key
        ttl_seconds: Cache TTL
        cache_dir: Custom cache directory
        key_func: Function to extract cache key from arguments

    Example:
        @cached("github", "repo", ttl_seconds=1800)
        def fetch_repo(owner: str, repo: str) -> dict:
            ...
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Build cache key
            if key_func:
                key_args = key_func(*args, **kwargs)
            else:
                key_args = [str(a) for a in args] + [f"{k}={v}" for k, v in kwargs.items()]

            key_parts = key_prefix + tuple(key_args)

            # Try cache first
            cached_value = get(*key_parts, cache_dir=cache_dir, ttl_seconds=ttl_seconds)
            if cached_value is not None:
                return cached_value

            # Call function and cache result
            result = func(*args, **kwargs)
            set(*key_parts, data=result, cache_dir=cache_dir)
            return result

        # Expose cache clear method
        def clear_cache() -> None:
            clear(*key_prefix, cache_dir=cache_dir)

        wrapper.clear_cache = clear_cache  # type: ignore
        return wrapper
    return decorator


def clear(
    *key_prefix: str,
    cache_dir: Path | None = None,
) -> int:
    """Clear cache entries matching a key prefix.

    A cache entry matches if its key starts with all the provided prefix parts.
    For example, clear('github') matches entries with key ('github', 'api', ...).

    Returns:
        Number of entries cleared
    """
    cache_dir = cache_dir or DEFAULT_CACHE_DIR
    if not cache_dir.exists():
        return 0

    count = 0
    prefix_len = len(key_prefix)

    for path in cache_dir.glob("*.json"):
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))

            if not key_prefix:
                # No prefix - clear all entries
                path.unlink()
                count += 1
            else:
                # Check if stored key parts start with the prefix
                stored_parts = entry.get("_key_parts", [])
                if len(stored_parts) >= prefix_len:
                    if stored_parts[:prefix_len] == list(key_prefix):
                        path.unlink()
                        count += 1
        except (json.JSONDecodeError, OSError):
            continue

    return count


def get_stats(cache_dir: Path | None = None) -> dict[str, Any]:
    """Get cache statistics.

    Returns:
        Dict with total entries, total size, hit/miss stats (if available)
    """
    cache_dir = cache_dir or DEFAULT_CACHE_DIR
    if not cache_dir.exists():
        return {
            "entries": 0,
            "valid_entries": 0,
            "expired_entries": 0,
            "size_bytes": 0,
            "size_human": _human_readable_size(0),
            "cache_dir": str(cache_dir),
        }

    entries = 0
    total_size = 0
    valid_entries = 0

    for path in cache_dir.glob("*.json"):
        try:
            stat = path.stat()
            total_size += stat.st_size
            entries += 1

            entry = json.loads(path.read_text(encoding="utf-8"))
            if _is_valid(entry, DEFAULT_TTL_SECONDS):
                valid_entries += 1
        except (OSError, json.JSONDecodeError):
            continue

    return {
        "entries": entries,
        "valid_entries": valid_entries,
        "expired_entries": entries - valid_entries,
        "size_bytes": total_size,
        "size_human": _human_readable_size(total_size),
        "cache_dir": str(cache_dir),
    }


def _human_readable_size(size_bytes: int) -> str:
    """Convert bytes to human readable format."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f}MB"


def disable_cache() -> None:
    """Disable caching for the current process."""
    os.environ["PROMOAGENT_CACHE_DISABLED"] = "1"


def is_cache_enabled() -> bool:
    """Check if caching is enabled."""
    return os.environ.get("PROMOAGENT_CACHE_DISABLED") != "1"
