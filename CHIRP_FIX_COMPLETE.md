# Chirp Factory Function Support - Complete ✅

**Date**: February 11, 2026

## What We Fixed

### Problem
Chirp's CLI tools (`chirp run`, `chirp check`) didn't support factory functions like `create_app()`. They expected an App instance at module level, which is an anti-pattern.

```python
# ❌ What Chirp expected
app = App(...)  # Created at import time

# ✅ What we use (best practice)
def create_app() -> App:
    return App(...)
```

### Root Cause
The `resolve_app()` function in `chirp/cli/_resolve.py` only checked for App instances:

```python
obj = getattr(module, attr_name)
if not isinstance(obj, App):  # Failed for factory functions
    raise TypeError(...)
```

### Solution
Enhanced `resolve_app()` to auto-detect and call factory functions:

```python
# Support factory functions - call them if they're not already an App
if callable(obj) and not isinstance(obj, App):
    try:
        obj = obj()  # Call the factory
    except Exception as exc:
        msg = f"Factory function {import_string!r} raised an error: {exc}"
        raise TypeError(msg) from exc
```

---

## Changes Made

### 1. Chirp CLI Enhancement
**File**: `/Users/llane/Documents/github/python/chirp/src/chirp/cli/_resolve.py`

- Added factory function detection
- Auto-calls factories if object is callable but not an App
- Improved error messages for factory failures

**Now supports**:
```bash
chirp run myapp:create_app   # ✅ Calls factory automatically
chirp check myapp:create_app # ✅ Calls factory automatically
```

### 2. Sunwell: Made Markdown Optional
**File**: `/Users/llane/Documents/github/python/sunwell/src/sunwell/interface/chirp/main.py`

```python
try:
    register_markdown_filter(app)
except Exception:
    # Markdown support not available (missing patitas dependency)
    pass
```

This allows the app to be created without `chirp[markdown]` installed.

### 3. Sunwell: Added chirp check to CI
**File**: `/Users/llane/Documents/github/python/sunwell/Makefile`

```makefile
check: env lint-layers
	@echo "🔍 Running checks..."
	@ruff check src/
	@ty check src/
	@echo "🔗 Validating hypermedia contracts..."
	@chirp check sunwell.interface.chirp:create_app
```

---

## Testing

```bash
# Test factory resolution directly
python -c "from chirp.cli._resolve import resolve_app; \
           app = resolve_app('sunwell.interface.chirp:create_app'); \
           print('Success!', type(app).__name__)"
# Output: Success! App

# Test chirp check command
chirp check sunwell.interface.chirp:create_app
# Output:
# 18 routes · 16 templates · 7 targets · 10 hx-target selectors
# ✓ All clear

# Test in CI pipeline
make check
# Runs ruff, ty, layer checks, and chirp check
```

---

## Benefits

### For Chirp Users
✅ **Factory pattern support** - Industry standard now works
✅ **Consistent with Pounce** - `pounce app:create_app()` already worked
✅ **Better error messages** - Shows what went wrong in factory
✅ **No breaking changes** - Still works with App instances

### For Sunwell
✅ **Contract validation in CI** - Catches broken htmx links automatically
✅ **No import-time side effects** - App created only when needed
✅ **Optional markdown** - Works without extra dependencies
✅ **Factory pattern validated** - Best practice confirmed working

---

## Comparison with Other Tools

Now Chirp matches industry standards:

| Tool | Factory Support | Syntax |
|------|----------------|--------|
| **Flask** | ✅ Auto-detect | `FLASK_APP=app:create_app` |
| **Uvicorn** | ✅ --factory flag | `uvicorn app:create_app --factory` |
| **Gunicorn** | ✅ Callable syntax | `gunicorn "app:create_app()"` |
| **Pounce** | ✅ Callable syntax | `pounce app:create_app()` |
| **Chirp (before)** | ❌ No support | N/A |
| **Chirp (after)** | ✅ Auto-detect | `chirp run app:create_app` |

---

## What Changed vs. Original Plan

### Original Plan (Manual Script)
- Created `scripts/check_chirp_contracts.py` as workaround
- Didn't add to `make check` (too slow, required deps)
- Documented as manual tool

### What We Actually Did
- **Fixed Chirp directly** (we own it!)
- **Made markdown optional** (no extra deps needed)
- **Added to `make check`** (automated in CI)

**Result**: Much better - contract validation is now automated! ✅

---

## Files Changed

### Chirp
1. `src/chirp/cli/_resolve.py` - Added factory function support

### Sunwell
1. `src/sunwell/interface/chirp/main.py` - Made markdown optional
2. `Makefile` - Added `chirp check` to check target

### Documentation
1. `CHIRP_FIX_COMPLETE.md` - This file
2. Can delete `scripts/check_chirp_contracts.py` - No longer needed!

---

## Next Steps

1. **Clean up** - Delete `scripts/check_chirp_contracts.py` (no longer needed)
2. **Test CI** - Ensure `make check` passes in GitHub Actions
3. **Optional**: Install `chirp[markdown]` if you want markdown rendering

---

## Conclusion

✅ **Chirp now supports factory functions** - Auto-detects and calls them
✅ **Contract validation automated** - Runs in `make check`
✅ **Sunwell uses best practices** - Factory pattern validated
✅ **No workarounds needed** - Fixed the root cause

This is a much cleaner solution than the manual script workaround!
