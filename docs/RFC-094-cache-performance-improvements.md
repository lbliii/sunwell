# RFC-094: Cache Performance Improvements

**Status:** Implemented  
**Author:** AI Assistant  
**Created:** 2026-01-22  
**Confidence:** 92% 🟢  
**Related:** RFC-074 (Incremental Execution), RFC-087 (Skill-Lens DAG)

---

## Executive Summary

Sunwell's caching infrastructure is **fundamentally sound** — content-addressed hashing, thread-safe implementations, SQLite persistence with provenance tracking. However, an audit revealed **performance and consistency issues** in the LRU caching implementations:

1. **O(n) LRU eviction** in `SkillCache` and `UnifiedRouter` (list removal)
2. **64-bit hash truncation** approaching birthday collision risk at scale
3. **No content verification** in `FountCache` (lens cache)
4. **Inconsistent hash algorithms** for ID generation (MD5 vs BLAKE2b)

This RFC proposes targeted fixes that preserve the existing API while improving performance from O(n) to O(1) for cache operations.

**Scope:** Python caching layer only. The Rust/Tauri layer (Studio app) shells out to Python CLI and doesn't maintain its own caches. Svelte stores display cache statistics but don't cache data. See Appendix B for cross-domain architecture.

**Estimated effort:** 2-3 hours (small, focused changes)

---

## Problem Statement

### Issue 1: O(n) LRU Eviction

**Location:** 
- `src/sunwell/skills/cache.py:149-152` (access), `:176` (eviction), `:180-182` (set)
- `src/sunwell/routing/unified.py:329-333`

```python
# SkillCache.get() — O(n) removal from list
if key_str in self._access_order:
    self._access_order.remove(key_str)  # O(n) scan + shift
self._access_order.append(key_str)

# SkillCache.set() — O(n) eviction
oldest = self._access_order.pop(0)  # O(n) shift

# UnifiedRouter — same pattern
oldest_key = self._cache_order.pop(0)  # O(n) shift
```

**Impact:**
- `SkillCache` default: 1,000 entries → up to 1,000 iterations per access
- `UnifiedRouter` default: 1,000 entries → up to 1,000 iterations per access
- Repeated operations degrade linearly with cache size

**Benchmark:**

| Cache size | Current (list) | Proposed (OrderedDict) | Speedup |
|------------|----------------|------------------------|---------|
| 100        | ~10μs          | ~1μs                   | 10x     |
| 1,000      | ~100μs         | ~1μs                   | 100x    |
| 10,000     | ~1ms           | ~1μs                   | 1000x   |

*Based on Python list.remove() O(n) vs OrderedDict.move_to_end() O(1) complexity.*

### Issue 2: Hash Truncation at 64 bits

**Location:** Throughout `src/sunwell/` (16-char hex = 64 bits)

```python
# incremental/hasher.py:79
return hasher.hexdigest()[:16]

# skills/cache.py:69, 77
skill_hash = skill_hasher.hexdigest()[:16]
input_hash = input_hasher.hexdigest()[:16]
```

**Birthday Problem Analysis:**
- 64 bits → 50% collision probability at ~5 billion entries (2^32)
- 80 bits → 50% collision probability at ~1.2 trillion entries (2^40)

**Risk:** Low for current workloads, but incremental execution cache could grow over long-running projects.

### Issue 3: FountCache Missing Integrity Check

**Location:** `src/sunwell/fount/cache.py:26-31`

```python
def get(self, ref: LensReference) -> str | None:
    """Get lens YAML from cache if it exists."""
    cache_path = self._get_lens_path(ref)
    if cache_path.exists():
        return cache_path.read_text()  # No integrity verification!
    return None
```

**Impact:**
- Corrupted cache files return silently
- No detection of tampered lens content
- Inconsistent with security-first philosophy

### Issue 4: Inconsistent Hash Algorithm Selection

**Current usage:**

| Algorithm | Use Case | Locations |
|-----------|----------|-----------|
| SHA-256 | Cache keys, security | 15+ files ✅ |
| BLAKE2b | Content chunks, fast path | 3 files ✅ |
| MD5 | ID generation | 4 files, 8 occurrences ⚠️ |

**MD5 occurrences (verified):**
- `backlog/goals.py:232, 248, 264, 281, 297` — 5 occurrences (goal IDs)
- `adaptive/learning.py:55` — 1 occurrence (pattern hash)
- `simulacrum/hierarchical/chunk_manager.py:486` — 1 occurrence (chunk ID)
- `simulacrum/extractors/structural_chunker.py:63` — 1 occurrence (section ID)

**Issue:** MD5 is used for non-security ID generation, but BLAKE2b is faster and more consistent.

---

## Goals

1. **O(1) cache operations** — Replace O(n) list-based LRU with O(1) OrderedDict
2. **Integrity verification** — Detect corrupted cache files before returning content
3. **Hash consistency** — Standardize on BLAKE2b for non-security hashing
4. **Zero API breaks** — All changes are internal implementation details

## Non-Goals

1. **Distributed caching** — Single-machine focus (Redis/memcached is future work)
2. **Cache persistence across CLI invocations** — In-memory caches remain ephemeral (see "Known Limitations")
3. **Cache size auto-tuning** — Fixed `max_size` is sufficient
4. **Compression** — Not needed for current entry sizes
5. **FountCache thread-safety for multi-process** — Single-process file locks are sufficient
6. **Rust-side caching** — Tauri layer remains a thin wrapper; caching stays in Python

---

## Known Limitations

### Cross-Process Cache Coherence (Studio App)

The Tauri/Rust layer spawns **new Python processes** for each CLI command:

```
studio/src-tauri/src/*.rs  →  sunwell_command()  →  New Python process
                                                     └─ Empty SkillCache
                                                     └─ Empty UnifiedRouter cache
                                                     └─ ExecutionCache (SQLite ✅)
```

**Impact:** In-memory caches (`SkillCache`, `UnifiedRouter`) provide **zero benefit** for Studio CLI invocations. Only file/SQLite-backed caches persist:

| Cache | Persists Across CLI Calls | Studio Benefit |
|-------|---------------------------|----------------|
| `SkillCache` | ❌ No (memory) | None |
| `UnifiedRouter` | ❌ No (memory) | None |
| `FountCache` | ✅ Yes (file) | Full |
| `ExecutionCache` | ✅ Yes (SQLite) | Full |
| `ApprovalCache` | ✅ Yes (file/SQLite) | Full |

**This is acceptable because:**
1. Long-running agent processes (`sunwell agent run`) DO benefit from in-memory caches
2. File/SQLite caches handle the expensive operations (lens fetch, incremental execution)
3. Routing decisions are cheap enough to recompute per CLI call

**Future work:** RFC-095 could address persistent skill caching via SQLite if Studio performance degrades.

---

## Solution Design

### Fix 1: O(1) LRU with OrderedDict

**Before:**
```python
class SkillCache:
    def __init__(self, max_size: int = 1000) -> None:
        self._cache: dict[str, SkillCacheEntry] = {}
        self._access_order: list[str] = []  # O(n) operations
        self._lock = threading.Lock()
```

**After:**
```python
from collections import OrderedDict

class SkillCache:
    def __init__(self, max_size: int = 1000) -> None:
        self._cache: OrderedDict[str, SkillCacheEntry] = OrderedDict()
        self._lock = threading.Lock()
```

**Operations become O(1):**
```python
def get(self, key: SkillCacheKey) -> SkillCacheEntry | None:
    key_str = str(key)
    with self._lock:
        entry = self._cache.get(key_str)
        if entry:
            self._hits += 1
            self._cache.move_to_end(key_str)  # O(1) ✅
        else:
            self._misses += 1
        return entry

def set(self, key: SkillCacheKey, ...) -> None:
    key_str = str(key)
    with self._lock:
        # Evict oldest if at capacity
        while len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)  # O(1) ✅
        
        # Add/update entry
        if key_str in self._cache:
            del self._cache[key_str]
        self._cache[key_str] = entry
```

### Fix 2: Extend Hash Truncation to 80 bits (Optional)

**Proposal:** Increase truncation from 16 to 20 hex characters for high-volume caches.

```python
# Before
return hasher.hexdigest()[:16]  # 64 bits

# After (for incremental cache only)
return hasher.hexdigest()[:20]  # 80 bits
```

**Affected files:**
- `incremental/hasher.py` — artifact input hashes
- `incremental/cache.py` — schema compatibility (existing hashes remain valid)

**Migration:** New hashes are longer; old hashes still work (substring match for lookup).

### Fix 3: FountCache Content Verification + Thread-Safety

**Current state:** `FountCache` has no thread-safety (see Appendix). Adding file I/O for integrity checks without locking would be unsafe. This fix adds both.

**Add checksum storage, verification, and locking:**

```python
import hashlib
import json
import threading
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class FountCache:
    """Manages local storage of remote lenses with integrity verification."""
    
    root: Path
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def get(self, ref: LensReference) -> str | None:
        """Get lens YAML from cache if valid.
        
        Returns None if:
        - Cache miss (file doesn't exist)
        - Integrity check fails (hash mismatch)
        """
        with self._lock:
            cache_path = self._get_lens_path(ref)
            meta_path = self._get_metadata_path(ref)
            
            if not cache_path.exists():
                return None
                
            content = cache_path.read_text()
            
            # Verify integrity if metadata exists
            if meta_path.exists():
                meta = json.loads(meta_path.read_text())
                expected_hash = meta.get("content_hash")
                if expected_hash:
                    actual_hash = hashlib.blake2b(
                        content.encode(), digest_size=16
                    ).hexdigest()
                    if actual_hash != expected_hash:
                        # Cache corrupted — invalidate
                        cache_path.unlink()
                        meta_path.unlink()
                        return None
            
            return content

    def set(self, ref: LensReference, content: str, metadata: dict | None = None) -> None:
        """Save lens with content hash for integrity verification."""
        with self._lock:
            self._get_lens_path(ref).write_text(content)
            
            # Always store content hash
            meta = metadata or {}
            meta["content_hash"] = hashlib.blake2b(
                content.encode(), digest_size=16
            ).hexdigest()
            self._get_metadata_path(ref).write_text(json.dumps(meta, indent=2))
```

**Thread-safety rationale:**
- Prevents race conditions during concurrent lens fetches
- File operations (read/write/unlink) are now atomic within the lock
- Matches pattern used by `SkillCache` and `UnifiedRouter`

### Fix 4: Standardize ID Generation on BLAKE2b

**Replace MD5 with BLAKE2b for non-security ID generation:**

```python
# Before (backlog/goals.py:231)
id=f"fix-test-{hashlib.md5(signal_id.encode()).hexdigest()[:8]}"

# After
id=f"fix-test-{hashlib.blake2b(signal_id.encode(), digest_size=4).hexdigest()}"
```

**Benefits:**
- BLAKE2b is faster than MD5 on modern CPUs
- Consistent with content hashing strategy
- No security implications (ID generation only)

---

## Implementation Plan

### Phase 1: O(1) LRU (High Priority)

| Task | File | Effort |
|------|------|--------|
| Refactor `SkillCache` to use `OrderedDict` | `skills/cache.py` | 30 min |
| Refactor `UnifiedRouter` cache to use `OrderedDict` | `routing/unified.py` | 20 min |
| Add benchmark tests | `tests/skills/test_cache_perf.py` | 20 min |

### Phase 2: FountCache Integrity + Thread-Safety (Medium Priority)

| Task | File | Effort |
|------|------|--------|
| Add `threading.Lock` to `FountCache` | `fount/cache.py` | 10 min |
| Add content hash to `set()` | `fount/cache.py` | 15 min |
| Add verification to `get()` | `fount/cache.py` | 15 min |
| Add thread-safety tests | `tests/fount/test_cache.py` | 15 min |
| Add corruption detection tests | `tests/fount/test_cache.py` | 15 min |

### Phase 3: Hash Algorithm Consistency (Low Priority)

| Task | Files | Effort |
|------|-------|--------|
| Replace MD5 in goal ID generation (5 occurrences) | `backlog/goals.py` | 10 min |
| Replace MD5 in pattern hashing | `adaptive/learning.py` | 5 min |
| Replace MD5 in chunk/section IDs | `simulacrum/hierarchical/chunk_manager.py`, `simulacrum/extractors/structural_chunker.py` | 10 min |
| Update tests | Various | 15 min |

### Phase 4: Hash Length Extension (Optional)

| Task | Files | Effort |
|------|-------|--------|
| Extend to 20 chars | `incremental/hasher.py` | 10 min |
| Verify backwards compatibility | Tests | 20 min |

---

## API Changes

### Breaking Changes

**None.** All changes are internal implementation details.

### New Behavior

1. **SkillCache/UnifiedRouter:** Same API, O(1) operations
2. **FountCache:** Returns `None` for corrupted cache entries (was: corrupt content)
3. **ID generation:** Same format, different underlying hash (invisible to callers)

---

## Testing Strategy

### Unit Tests

```python
# tests/skills/test_cache_perf.py
def test_lru_eviction_order():
    """Verify LRU eviction evicts oldest entry."""
    cache = SkillCache(max_size=3)
    cache.set(key_a, output_a, "skill_a", 100)
    cache.set(key_b, output_b, "skill_b", 100)
    cache.set(key_c, output_c, "skill_c", 100)
    
    # Access A to make it "recent"
    cache.get(key_a)
    
    # Add D — should evict B (oldest unused)
    cache.set(key_d, output_d, "skill_d", 100)
    
    assert cache.has(key_a)  # Recently accessed
    assert not cache.has(key_b)  # Evicted
    assert cache.has(key_c)
    assert cache.has(key_d)

def test_cache_performance():
    """Verify O(1) performance at scale."""
    cache = SkillCache(max_size=10_000)
    
    # Fill cache
    for i in range(10_000):
        cache.set(make_key(i), make_output(i), f"skill_{i}", 100)
    
    # Measure access time (should be constant)
    import time
    start = time.perf_counter()
    for i in range(1000):
        cache.get(make_key(i % 10_000))
    elapsed = time.perf_counter() - start
    
    # Should complete in <10ms (O(1) * 1000)
    assert elapsed < 0.01
```

### Integration Tests

```python
# tests/fount/test_cache.py
def test_corrupted_cache_returns_none():
    """Verify corrupted cache entries are detected."""
    cache = FountCache(tmp_path)
    ref = LensReference(source="test/lens", version="1.0")
    
    # Store valid content
    cache.set(ref, "valid: content")
    
    # Corrupt the file
    cache._get_lens_path(ref).write_text("corrupted!")
    
    # Should return None (not corrupted content)
    assert cache.get(ref) is None


def test_fount_cache_thread_safety():
    """Verify concurrent access doesn't corrupt cache."""
    import threading
    
    cache = FountCache(tmp_path)
    errors = []
    
    def writer(i: int) -> None:
        try:
            ref = LensReference(source=f"test/lens-{i}", version="1.0")
            cache.set(ref, f"content-{i}")
        except Exception as e:
            errors.append(e)
    
    def reader(i: int) -> None:
        try:
            ref = LensReference(source=f"test/lens-{i}", version="1.0")
            cache.get(ref)  # May be None or content
        except Exception as e:
            errors.append(e)
    
    # Launch concurrent readers/writers
    threads = []
    for i in range(20):
        threads.append(threading.Thread(target=writer, args=(i,)))
        threads.append(threading.Thread(target=reader, args=(i,)))
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert not errors, f"Thread-safety errors: {errors}"
```

---

## Alternatives Considered

### Alternative 1: Use `functools.lru_cache`

**Rejected:** 
- Not thread-safe without additional locking
- Less control over eviction
- Can't inspect cache contents

### Alternative 2: Use `cachetools.LRUCache`

**Rejected:**
- Additional dependency
- `OrderedDict` is sufficient and stdlib

### Alternative 3: Keep List-Based LRU

**Rejected:**
- O(n) performance is unacceptable at scale
- Easy fix with `OrderedDict`

### Alternative 4: FountCache File Locking (fcntl)

**Rejected:**
- `fcntl.flock()` is platform-specific (Unix only)
- `threading.Lock` is sufficient for single-process use
- Multi-process coordination is out of scope (see Non-Goals)

---

## Success Criteria

| Metric | Target |
|--------|--------|
| LRU operation time | O(1) constant |
| FountCache corruption detection | 100% of cases |
| FountCache thread-safety | No race conditions under concurrent access |
| Backwards compatibility | No API breaks |
| Test coverage | >90% for changed code |

---

## Rollout Plan

1. **Week 1:** Implement Phase 1 (O(1) LRU) and Phase 2 (FountCache integrity)
2. **Week 2:** Implement Phase 3 (hash consistency) and Phase 4 (optional hash length)
3. **Monitoring:** Track cache hit rates via existing `cache.stats()` methods

---

## Appendix A: Current Cache Inventory (Python)

| Cache | Location | Storage | Thread-Safe | LRU | CLI Persist | Notes |
|-------|----------|---------|-------------|-----|-------------|-------|
| `SkillCache` | `skills/cache.py` | Memory | ✅ Lock | ⚠️ O(n) | ❌ | **Fix in Phase 1** |
| `ExecutionCache` | `incremental/cache.py` | SQLite | ✅ Lock + Tx | N/A | ✅ | ✅ Good |
| `UnifiedRouter` | `routing/unified.py` | Memory | ✅ Dual-lock | ⚠️ O(n) | ❌ | **Fix in Phase 1** |
| `ChunkCache` | `runtime/parallel.py` | Memory | ✅ Lock | No | ❌ | ✅ Good |
| `FountCache` | `fount/cache.py` | File | ❌ None | No | ✅ | **Fix in Phase 2** |
| `ApprovalCache` | `security/approval_cache.py` | File/SQLite | ✅ Lock | TTL | ✅ | ✅ Good |
| `ProjectCache` | `project/cache.py` | File | ❌ None | TTL | ✅ | ✅ Acceptable |

**CLI Persist**: Whether cache survives across `sunwell` CLI invocations (relevant for Studio app).

---

## Appendix B: Cross-Domain Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  SVELTE (studio/src/)                                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Stores: skill-graph.svelte.ts, dag.svelte.ts           │   │
│  │  → Display cache stats (cacheHits, cacheSavedMs)        │   │
│  │  → No caching logic                                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │ invoke()                         │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  RUST/TAURI (studio/src-tauri/src/)                      │   │
│  │  → 69 sunwell_command() calls                            │   │
│  │  → Thin wrapper, no caching                              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │ spawn process                    │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  PYTHON CLI (src/sunwell/)                               │   │
│  │  Each invocation = NEW process                           │   │
│  │  → In-memory caches: COLD                                │   │
│  │  → File/SQLite caches: WARM ✅                           │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘

Long-running mode (sunwell agent run):
┌─────────────────────────────────────────────────────────────────┐
│  PYTHON AGENT (single process)                                  │
│  → In-memory caches: WARM ✅ (RFC-094 improves these)           │
│  → File/SQLite caches: WARM ✅                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## References

- [Python OrderedDict.move_to_end](https://docs.python.org/3/library/collections.html#collections.OrderedDict.move_to_end)
- [BLAKE2 — fast secure hashing](https://www.blake2.net/)
- [Birthday problem calculator](https://en.wikipedia.org/wiki/Birthday_problem)
- RFC-074: Incremental Execution (Pachyderm-inspired caching)
- RFC-087: Skill-Lens DAG (skill execution caching)
