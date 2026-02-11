# Chirp Feature Adoptions - Complete ✅

**Date**: February 11, 2026

## What We Adopted

### 1. ✅ Markdown Support
**File**: `src/sunwell/interface/chirp/main.py`
```python
from chirp.markdown import register_markdown_filter
register_markdown_filter(app)
```

**Usage**: `{{ content | markdown }}` in templates
**Effort**: 2 lines of code

### 2. ⚠️ Contract Validation (Manual Tool)
**File**: `scripts/check_chirp_contracts.py`
```bash
python scripts/check_chirp_contracts.py
```

**Why manual?**
- Requires optional dependencies (`chirp[markdown]`)
- Requires full app initialization at import time
- `chirp check` CLI expects an App instance, not a factory function
- Better as a dev tool than automated check

**Alternative**: You could add it to CI if you:
1. Install `chirp[markdown]`
2. Create an app instance at module level (but this slows imports)

For now, it's available as a script you can run manually.

### 3. ✅ Form Helpers
**Files**:
- `pages/projects/new.py` - Uses `form_or_errors()`
- `pages/projects/new-form.html` - Uses `text_field()` macro

**Features**:
- Automatic form binding
- Inline error display
- Form value re-population on errors

---

## Summary

✅ **Markdown support** - Works great, ready to use
⚠️ **Contract validation** - Available as manual script (not automated)
✅ **Form helpers** - Demonstrated in project creation form

**Total**: 2/3 fully automated, 1 available as manual tool

---

## To Run Contract Validation

```bash
# Make sure you have markdown support
pip install 'chirp[markdown]'  # or add to pyproject.toml

# Run the script
python scripts/check_chirp_contracts.py
```

This will check:
- All hx-get/hx-post/hx-put targets exist
- Forms have POST handlers
- Fragments reference valid blocks
