# Test Gap: HarmonicPlanner Execution Interface

**Status**: Fixed + Test Added  
**Date**: 2026-01-20  
**Issue**: HarmonicPlanner missing `create_artifact` method caused execution to stop after planning

---

## The Problem

HarmonicPlanner was tested for **planning** but not for **execution**:

1. ✅ Tests existed for `plan_with_metrics()`, `discover_graph()`, `plan()`
2. ❌ **No test** for `create_artifact()` method
3. ❌ **No integration test** for full execution flow with HarmonicPlanner

When `Naaru.run()` tried to execute artifacts after planning:
- Planning completed → `plan_winner` event emitted
- Execution started → called `planner.create_artifact()`
- **AttributeError** → execution stopped silently

## Why We Missed It

### 1. **Interface Compliance Not Tested**

HarmonicPlanner claims compatibility with ArtifactPlanner interface via `discover_graph()`, but doesn't implement the full interface:

```python
# HarmonicPlanner has:
- discover_graph() ✅
- plan_with_metrics() ✅
- plan() ✅

# But missing:
- create_artifact() ❌  # Required for execution!
```

### 2. **Unit Tests Only Covered Planning**

`test_harmonic_planning.py` only tested:
- Plan generation
- Plan scoring
- Plan selection

**Missing**: Execution phase tests

### 3. **No Integration Test for Full Flow**

No test that runs:
```python
planner = HarmonicPlanner(...)
graph = await planner.discover_graph(goal)  # Planning
# ... then ...
content = await planner.create_artifact(artifact)  # Execution
```

## The Fix

1. ✅ Added `create_artifact()` method to HarmonicPlanner (delegates to ArtifactPlanner)
2. ✅ Added test: `test_harmonic_planner_has_create_artifact_method()`
3. ✅ Added test: `test_create_artifact_delegates_to_base_planner()`

## Lessons Learned

### What We Should Test

1. **Interface Compliance**: If a class claims to implement an interface, test ALL methods
2. **End-to-End Flow**: Test planning → execution, not just planning
3. **Method Existence**: Use `hasattr()` checks for critical methods (like `test_artifact_planner_has_create_artifact_method`)

### Test Patterns to Follow

```python
def test_planner_has_required_methods(planner):
    """Test that planner implements full interface."""
    assert hasattr(planner, "discover_graph")
    assert hasattr(planner, "create_artifact")  # This would have caught it!
    assert callable(planner.discover_graph)
    assert callable(planner.create_artifact)

@pytest.mark.asyncio
async def test_planner_full_cycle(planner, mock_model):
    """Test planning → execution cycle."""
    # Plan
    graph = await planner.discover_graph("goal")
    
    # Execute
    artifact = list(graph.values())[0]
    content = await planner.create_artifact(artifact)  # Would fail if missing!
    
    assert isinstance(content, str)
```

## Recommendations

1. **Add interface compliance tests** for all planners
2. **Add integration tests** that test full planning → execution flow
3. **Use protocol/ABC** to enforce interface compliance at type level
4. **Test method existence** not just method behavior

## Related Files

- `src/sunwell/naaru/planners/harmonic.py` - Fixed by adding `create_artifact()`
- `tests/test_harmonic_planning.py` - Should add execution tests
- `tests/test_artifact_planner.py` - Good example: tests `create_artifact` existence
