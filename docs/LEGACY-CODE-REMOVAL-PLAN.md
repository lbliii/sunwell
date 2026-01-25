# Legacy Code Removal Plan

**Status**: Phase 1-3 Complete, Phase 4 Pending  
**Created**: 2026-01-25  
**Last Updated**: 2026-01-25  
**Goal**: Remove all legacy code, deprecated features, and backward-compatibility shims per `.cursor/rules/compatibility.mdc`

## Progress Summary

✅ **Phase 1 Complete**:
- Deleted `archive/` directory (18 files)
- Removed deprecated CLI comments from `main.py`
- Removed `naaru` backward compatibility alias
- Deferred CSS aliases removal (200+ references, requires migration)

✅ **Phase 2 Complete**:
- Removed legacy `skill-md` export format
- Removed `export_skill_md()` method (~90 lines)
- Updated tests to use YAML format
- Removed legacy lens version storage (`.versions` directory)
- Removed `_create_version()` method (~60 lines)
- Updated `_count_versions()` to use manifest
- Removed legacy session flat directory support
- Removed legacy workspace parameter from `ToolExecutor`
- Updated CLI and tests to use `Project` instead

✅ **Phase 3 Complete**:
- Removed legacy codebase indexer fallback (`_build_codebase_index_legacy` ~110 lines)
- Removed legacy CodebaseIndexer path in RAG function
- Removed legacy binding paths (`.sunwell/bindings/` flat directory)
- Removed legacy default_binding file support
- Removed legacy binding scanning from identity.py
- Updated workspace detector comments (still used, just cleaned up)
- Cleaned up Naaru execution method comments

🔄 **Remaining (Phase 4)**:
- Type aliases and module re-exports (requires external audit)
- CSS legacy aliases (deferred - 200+ references)

---

## Summary

This plan identifies and removes all legacy code from the Sunwell codebase. Per project policy (`.cursor/rules/compatibility.mdc`): **"Backwards compatibility is not a priority. Avoid shims and wrappers. Optimize for long-term clean code for latest solutions. Remove deprecations and dead code as you find them."**

**Total Categories**: 8  
**Estimated Files Affected**: 50+  
**Estimated Time**: 2-3 days

---

## Categories of Legacy Code

### 1. Archive Directory (Complete Removal)

**Location**: `archive/experiments_20260121/`

**Files**:
- `archive/experiments_20260121/__init__.py`
- `archive/experiments_20260121/automata.py`
- `archive/experiments_20260121/compound/` (entire directory)
- `archive/experiments_20260121/eye_tuning.py`
- `archive/experiments_20260121/gradient.py`
- `archive/experiments_20260121/hierarchy.py`
- `archive/experiments_20260121/interference.py`
- `archive/experiments_20260121/phase_transition.py`
- `archive/experiments_20260121/resonance_amp.py`
- `archive/experiments_20260121/swarm.py`

**Action**: Delete entire `archive/` directory  
**Risk**: Low (no imports found)  
**Priority**: High

---

### 2. Already Deleted Files (Git Cleanup)

**Files marked for deletion in git status**:
- `scripts/generate_event_types.py`
- `src/sunwell/agent/event_schema.py`
- `src/sunwell/benchmark/naaru/conditions.py`
- `src/sunwell/naaru/persistence.py`
- `src/sunwell/naaru/planners/artifact.py`
- `src/sunwell/naaru/planners/harmonic.py`
- `src/sunwell/schema/loader.py`
- `src/sunwell/tools/handlers.py`

**Action**: Complete git deletion (`git rm`)  
**Risk**: None (already staged for deletion)  
**Priority**: High

---

### 3. Legacy Format Support

#### 3.1 Skill Export: Legacy `skill-md` Format

**Location**: `src/sunwell/skills/interop.py`

**Code to Remove**:
- `export_skill_md()` method (lines ~310-400)
- `skill-md` format handling in `export()` method (lines ~295-301)
- Documentation references to "legacy Sunwell markdown format"

**Action**: Remove format option and method  
**Risk**: Medium (check if any external tools use this)  
**Priority**: Medium

#### 3.2 Lens Manager: Legacy Version Storage

**Location**: `src/sunwell/lens/manager.py`

**Code to Remove**:
- Legacy version storage paths (`.versions/` directory handling)
- `_create_legacy_version()` method (line ~410)
- `_delete_legacy_version()` method (line ~554)
- Fallback to legacy manifest (lines ~597-602)
- Legacy version snapshot creation (line ~505, ~815-829)
- Filesystem fallback for legacy lenses not in index (lines ~138-146, ~205-214)

**Action**: Remove all legacy storage paths, keep only RFC-101 manifest-based storage  
**Risk**: Medium (may break users with old lens versions)  
**Priority**: Medium

#### 3.3 Session Manager: Legacy Flat Sessions Directory

**Location**: `src/sunwell/simulacrum/core/session_manager.py`

**Code to Remove**:
- Legacy flat sessions directory check (lines ~125-144)
- Dual-write to legacy location (lines ~181-188)
- Fallback to legacy path (line ~225)

**Action**: Remove flat `sessions/` directory support, use only project-scoped storage  
**Risk**: Medium (may break users with old sessions)  
**Priority**: Medium

---

### 4. Backward Compatibility Aliases & Re-exports

#### 4.1 Type Aliases

**Locations**:
- `src/sunwell/types/__init__.py`:
  - `RetrievalResult` alias (lines ~27, ~75)
- `src/sunwell/core/types.py`:
  - Re-exports for backward compatibility (line ~121)
- `src/sunwell/agent/task_graph.py`:
  - Backward compatibility alias (line ~44)
- `src/sunwell/routing/exemplars.py`:
  - Backward compatibility alias (line ~185)
- `src/sunwell/routing/types.py`:
  - Backward compatibility alias (line ~137)
- `src/sunwell/agent/events/types.py`:
  - Backward compatibility alias (line ~262)
- `src/sunwell/types/memory.py`:
  - Alias for backward compatibility (line ~149)
- `src/sunwell/self/types.py`:
  - `ProposalTestCase` alias (lines ~219-220)
- `src/sunwell/simulacrum/extractors/facet_extractor.py`:
  - Backwards compatibility wrapper (lines ~149, ~282-289)
- `src/sunwell/simulacrum/extractors/extractor.py`:
  - Backwards compatibility (lines ~51, ~85, ~119)
- `src/sunwell/simulacrum/context/focus.py`:
  - Backwards compatibility alias (line ~29)
- `src/sunwell/environment/model.py`:
  - Re-export for backwards compatibility (line ~20)
- `src/sunwell/agent/learning.py`:
  - Re-export for backwards compatibility (lines ~4-8)
- `src/sunwell/naaru/planners/harmonic/__init__.py`:
  - Re-export for backward compatibility (line ~19)
- `src/sunwell/agent/events/schemas/__init__.py`:
  - Re-exports for backward compatibility (lines ~4, ~33)
- `src/sunwell/surface/types.py`:
  - Re-exports for backwards compatibility (line ~231)

**Action**: Remove all aliases, update imports to canonical names  
**Risk**: High (may break external code)  
**Priority**: Low (requires audit of external usage)

#### 4.2 Module Re-exports (RFC-138)

**Location**: `docs/RFC-138-module-architecture-consolidation.md` mentions deprecation re-exports

**Action**: Follow RFC-138 Phase 5 plan to remove deprecated module locations  
**Risk**: High (requires full migration)  
**Priority**: Low (tracked in RFC-138)

---

### 5. Legacy Code Paths & Fallbacks

#### 5.1 Legacy Codebase Indexer

**Location**: `src/sunwell/cli/chat.py`

**Code to Remove**:
- `_build_codebase_index_legacy()` function (lines ~251-260)
- Fallback to legacy indexer (lines ~184-185, ~418-420)
- Import fallback logic (lines ~181-185)

**Action**: Remove legacy indexer, require RFC-108 IndexingService  
**Risk**: Medium (may break if IndexingService unavailable)  
**Priority**: Medium

#### 5.2 Legacy Workspace Parameter

**Location**: `src/sunwell/tools/executor.py`

**Code to Remove**:
- `workspace` parameter support (line ~120)
- Fallback logic for `workspace` parameter (line ~116)
- Documentation mentioning backward compatibility

**Action**: Remove `workspace` parameter, require `project` parameter  
**Risk**: Medium (may break external tool usage)  
**Priority**: Medium

#### 5.3 Legacy Binding Paths

**Location**: `src/sunwell/binding/manager.py`

**Code to Remove**:
- Legacy paths for backwards compatibility (line ~223)
- Legacy flat bindings scan (line ~350 in `binding/identity.py`)
- Save to legacy location (line ~557)

**Action**: Remove legacy path support  
**Risk**: Medium  
**Priority**: Medium

#### 5.4 Legacy Workspace Detector

**Location**: `src/sunwell/workspace/detector.py`

**Code to Remove**:
- Legacy compatibility conversion (line ~85)
- Legacy compatibility comment (line ~25)

**Action**: Remove legacy Workspace type support  
**Risk**: Medium  
**Priority**: Medium

#### 5.5 Legacy Naaru Execution Method

**Location**: `src/sunwell/naaru/execution.py`

**Code to Remove**:
- Legacy method kept for backward compatibility (line ~216)

**Action**: Remove deprecated method  
**Risk**: Low  
**Priority**: Medium

#### 5.6 Legacy Tool-Calling Mode

**Location**: `src/sunwell/naaru/discernment.py`

**Code to Remove**:
- Tool-calling (legacy) mode references (lines ~451, ~511)

**Action**: Remove legacy mode, use unified approach  
**Risk**: Low  
**Priority**: Low

---

### 6. Deprecated CLI Commands

**Location**: `src/sunwell/cli/main.py`

**Code to Remove**:
- Comments about deprecated skill CLI (line ~534)
- Comments about legacy commands deleted (lines ~661, ~668)
- Hidden `naaru` alias for backward compatibility (line ~507)

**Action**: Remove comments and hidden alias  
**Risk**: Low  
**Priority**: Low

---

### 7. Legacy Event Schema Fields

**Location**: `src/sunwell/agent/events/schemas/`

**Code to Remove**:
- Legacy field comments in `base.py` (line ~19)
- Backward-compatible fields in `planning.py` (line ~7)
- Kept-for-backward-compat fields in `harmonic.py` (lines ~26-27)

**Action**: Remove legacy fields, update event consumers  
**Risk**: High (may break event processing)  
**Priority**: Low (requires careful migration)

---

### 8. CSS Legacy Aliases

**Location**: `studio/src/styles/variables.css`

**Code to Remove**:
- Legacy aliases section (line ~130)
- Legacy semantic aliases (line ~172)
- Legacy spacing aliases (line ~227)

**Action**: Remove legacy CSS variables, update all references  
**Risk**: Medium (may break UI)  
**Priority**: Low

---

## Removal Strategy

### Phase 1: Safe Removals (Day 1)

**Low Risk, High Impact**:
1. ✅ Delete `archive/` directory
2. ✅ Complete git deletion of already-deleted files
3. ✅ Remove deprecated CLI comments
4. ✅ Remove legacy CSS aliases (after updating references)

**Estimated Time**: 2-3 hours  
**Risk**: Low

---

### Phase 2: Format & Storage Cleanup (Day 1-2)

**Medium Risk**:
1. Remove legacy `skill-md` export format
2. Remove legacy lens version storage
3. Remove legacy session flat directory support
4. Remove legacy workspace parameter

**Estimated Time**: 4-6 hours  
**Risk**: Medium  
**Prerequisites**: 
- Audit external usage
- Update documentation
- Add migration notes if needed

---

### Phase 3: Code Path Cleanup (Day 2)

**Medium Risk**:
1. Remove legacy codebase indexer fallback
2. Remove legacy binding paths
3. Remove legacy workspace detector support
4. Remove legacy Naaru execution methods

**Estimated Time**: 3-4 hours  
**Risk**: Medium  
**Prerequisites**: Ensure new paths are stable

---

### Phase 4: Type & Module Cleanup (Day 2-3)

**High Risk, Requires Audit**:
1. Remove backward compatibility type aliases
2. Remove module re-exports (per RFC-138)
3. Remove legacy event schema fields

**Estimated Time**: 6-8 hours  
**Risk**: High  
**Prerequisites**:
- Full codebase audit for alias usage
- External dependency audit
- Migration plan for breaking changes

---

## Testing Strategy

### Pre-Removal
- [ ] Run full test suite baseline
- [ ] Document current test coverage
- [ ] Identify tests that exercise legacy code paths

### During Removal
- [ ] Run tests after each phase
- [ ] Update tests that reference legacy code
- [ ] Add tests for migration paths (if needed)

### Post-Removal
- [ ] Full test suite pass
- [ ] Integration tests
- [ ] Manual smoke tests

---

## Risk Mitigation

### High-Risk Items
1. **Type Aliases**: Audit all imports before removal
2. **Module Re-exports**: Follow RFC-138 migration plan
3. **Event Schema**: Coordinate with event consumers

### Medium-Risk Items
1. **Format Support**: Check external tool usage
2. **Storage Paths**: Provide migration script if needed
3. **Code Paths**: Ensure new paths are tested

### Low-Risk Items
1. **Archive Directory**: No dependencies found
2. **CLI Comments**: Documentation only
3. **CSS Aliases**: Update references first

---

## Migration Notes

### For External Users

If external code uses removed features:

1. **Legacy Skill Format**: Use `anthropic` or `yaml` format instead
2. **Legacy Lens Storage**: Migrate to RFC-101 manifest format
3. **Legacy Sessions**: Migrate to project-scoped storage
4. **Type Aliases**: Update imports to canonical names
5. **Workspace Parameter**: Use `project` parameter instead

---

## Success Criteria

- [ ] All legacy code removed
- [ ] All tests passing
- [ ] No backward-compatibility shims remaining
- [ ] Documentation updated
- [ ] Migration guide provided (if needed)
- [ ] Codebase is cleaner and easier to maintain

---

## Related Documents

- `.cursor/rules/compatibility.mdc` - Project policy
- `docs/RFC-138-module-architecture-consolidation.md` - Module migration plan
- `docs/RFC-101-*.md` - Lens storage migration
- `docs/RFC-108-*.md` - Indexing service migration
- `docs/RFC-117-*.md` - Project parameter migration

---

## Next Steps

1. **Review this plan** with team
2. **Prioritize phases** based on current work
3. **Start Phase 1** (safe removals)
4. **Audit external usage** before Phase 4
5. **Execute removal** phase by phase
6. **Update documentation** as code is removed

---

**Last Updated**: 2026-01-25
