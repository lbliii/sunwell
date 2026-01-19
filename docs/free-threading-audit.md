# Free-Threading Safety Audit

This document summarizes the free-threading safety issues found and fixed in the Sunwell codebase.

## Issues Found and Fixed

### 1. Race Condition in Singleton Initialization (`cli/state.py`)

**Issue**: Classic double-check locking bug. Two threads could both see `_simulacrum_manager is None` and both create instances.

**Location**: `src/sunwell/cli/state.py:33-40`

**Fix**: Added `threading.Lock` with proper double-check locking pattern:
- Fast path: check if initialized (no lock)
- Slow path: acquire lock, double-check, initialize

**Status**: ✅ Fixed

### 2. Unsynchronized Global TRACER (`simulacrum/tracer.py`)

**Issue**: Global `TRACER` instance modified from multiple threads without synchronization:
- `traces.append()` - list mutation
- `_current_trace` assignment - reference mutation  
- `_turn_counter += 1` - counter increment
- `traces.clear()` - list mutation

**Location**: `src/sunwell/simulacrum/tracer.py:366`

**Fix**: Added `threading.Lock` to `TurnTracer` class:
- All state mutations protected by `self._lock`
- Read operations snapshot data under lock
- I/O operations (persist) happen outside lock

**Status**: ✅ Fixed

### 3. UnifiedRouter Cache Pattern (`routing/unified.py`)

**Status**: ✅ Safe (no fix needed)

The cache uses a standard lock-free read optimization:
- Fast path: read cache outside lock (safe - dict reads are atomic)
- Slow path: acquire lock, double-check, compute, update

This pattern is correct for free-threading.

### 4. ChunkCache Unsynchronized Access (`runtime/parallel.py`)

**Issue**: `ChunkCache` class had mutable dicts (`_cache` and `_embeddings`) without any synchronization. Multiple threads calling `get_or_create` or `set_embedding` could cause data races.

**Location**: `src/sunwell/runtime/parallel.py:232-273`

**Fix**: Added `threading.Lock` with double-check locking:
- Fast path: check cache without lock
- Slow path: acquire lock, double-check, create/update
- `stats` property snapshots under lock

**Status**: ✅ Fixed

### 5. Config Singleton Without Lock (`config.py`)

**Issue**: Global `_config` singleton used lazy initialization without synchronization. Multiple threads could both see `_config is None` and both call `load_config()`.

**Location**: `src/sunwell/config.py:356-367`

**Fix**: Added `threading.Lock` with double-check locking:
- Fast path: check if config exists (no lock)
- Slow path: acquire lock, double-check, load
- `reset_config()` also protected by lock

**Status**: ✅ Fixed

## Patterns Verified as Safe

### Thread-Safe Patterns Found

1. **ContextVar usage** (`runtime/parallel.py:35-36`)
   - Thread-local state via `ContextVar` - safe for free-threading

2. **ThreadPoolExecutor with locks** (`naaru/parallel.py:106,118`)
   - Worker threads use `threading.Lock` for shared state updates
   - Each worker gets its own `MirrorHandler` instance (no sharing)

3. **Immutable module-level constants**
   - `IMMUTABLE_MODULES`, `BLOCKED_MODIFICATION_TARGETS` use `frozenset` - safe
   - String constants and regex patterns - safe
   - `LENS_NAME_MAP`, `INTENT_LENS_MAP`, etc. are read-only dicts - safe

4. **Dataclass with frozen=True**
   - Many dataclasses use `frozen=True` - immutable, thread-safe
   - `RoutingDecision`, `ParallelResult`, `HashedChunk`, `ParallelStats`

5. **@cache decorators** (`core/freethreading.py:52,81`)
   - `is_free_threaded()` and `cpu_count()` use `@cache`
   - Safe because: called at module load, return immutable values, idempotent

## Recommendations

### Best Practices for Free-Threading

1. **Use locks for shared mutable state**
   ```python
   self._lock = threading.Lock()
   with self._lock:
       # mutate shared state
   ```

2. **Prefer immutable data structures**
   ```python
   # Good: frozenset (immutable)
   ALLOWED = frozenset({"a", "b"})
   
   # Bad: set (mutable)
   ALLOWED = {"a", "b"}  # Could be modified
   ```

3. **Use ContextVar for thread-local state**
   ```python
   from contextvars import ContextVar
   context: ContextVar[dict] = ContextVar("context", default={})
   ```

4. **Snapshot data for read operations**
   ```python
   with self._lock:
       snapshot = list(self._data)  # Copy under lock
   # Use snapshot outside lock
   ```

5. **Double-check locking for singletons and caches**
   ```python
   # Fast path: check without lock
   if key in cache:
       return cache[key]
   
   # Slow path: lock, double-check, compute
   with lock:
       if key in cache:  # Double-check
           return cache[key]
       cache[key] = compute()
       return cache[key]
   ```

## Testing Recommendations

1. **Stress test with multiple threads**
   ```python
   import threading
   threads = [threading.Thread(target=func) for _ in range(10)]
   for t in threads:
       t.start()
   for t in threads:
       t.join()
   ```

2. **Use Python 3.14t for testing**
   - Run tests with free-threaded Python to catch race conditions
   - Standard Python (GIL) may hide threading bugs

3. **Check for data races**
   - Use tools like `python -X dev` for runtime checks
   - Consider static analysis tools

## Future Considerations

1. **Consider using `@dataclass(frozen=True)` more widely**
   - Immutable data structures eliminate many race conditions

2. **Review async/thread interactions**
   - Ensure proper synchronization when mixing async and threads

3. **Document thread-safety guarantees**
   - Add docstrings indicating which classes/methods are thread-safe

## Related Files

- `src/sunwell/cli/state.py` - Singleton pattern
- `src/sunwell/simulacrum/tracer.py` - Global mutable state
- `src/sunwell/routing/unified.py` - Cache with lock-free reads
- `src/sunwell/core/freethreading.py` - Free-threading utilities
- `src/sunwell/runtime/parallel.py` - Parallel execution, ChunkCache
- `src/sunwell/naaru/parallel.py` - Parallel autonomous runner
- `src/sunwell/config.py` - Config singleton with thread-safe lazy loading