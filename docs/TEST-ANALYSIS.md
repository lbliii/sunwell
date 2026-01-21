# Test Suite Analysis & Recommendations

**Date**: 2026-01-18  
**Status**: 677 passing, 3 failing  
**Coverage**: ~27 test files for ~360 source files

---

## 🔴 Critical: Fix Failing Tests

### 1. Team Intelligence Tests (2 failures)

**Issue**: Tests expect functionality that may not be working correctly.

#### `test_check_contradiction`
```python
# Test expects: "MySQL database" should match rejected "MySQL"
# Current: Uses _similar() with 0.5 threshold
# Problem: May need better similarity matching or test setup
```

**Recommendation**:
- Add unit tests for `_similar()` method with various edge cases
- Test similarity thresholds (0.3, 0.5, 0.7)
- Add test for exact matches vs partial matches
- Consider using embedding-based similarity for better matching

#### `test_check_approach_with_failure`
```python
# Test expects: "use Redis caching" should match failure "Redis caching approach"
# Current: Uses check_similar_failures() which may not be matching correctly
```

**Recommendation**:
- Add unit tests for `check_similar_failures()` 
- Test with various similarity thresholds
- Add integration test with actual failure data
- Consider fuzzy matching improvements

---

## 🟡 Missing Test Coverage

### High Priority Modules (No Tests)

#### 1. **CLI Commands** (`src/sunwell/cli/`)
**Impact**: High - User-facing functionality  
**Files**: 34 files, 0 tests

**Needed Tests**:
- `test_cli_main.py` - Command routing, argument parsing
- `test_cli_agent.py` - Agent command integration
- `test_cli_bootstrap.py` - Bootstrap command
- `test_cli_team.py` - Team command
- `test_cli_helpers.py` - Helper functions
- Error handling for invalid commands
- Exit codes and error messages

**Example**:
```python
def test_agent_run_command():
    """Test agent run command with mock."""
    # Test goal parsing
    # Test checkpoint creation
    # Test error handling
```

#### 2. **Naaru** (`src/sunwell/naaru/`)
**Impact**: High - Core planning system  
**Files**: 59 files, 0 tests

**Needed Tests**:
- `test_naaru_planner.py` - Planning logic
- `test_naaru_executor.py` - Task execution
- `test_naaru_checkpoint.py` - State persistence
- Integration tests for full planning cycle

#### 3. **Simulacrum** (`src/sunwell/simulacrum/`)
**Impact**: Medium-High - Agent simulation  
**Files**: 40 files, 0 tests

**Needed Tests**:
- `test_simulacrum_agent.py` - Agent behavior
- `test_simulacrum_memory.py` - Memory management
- `test_simulacrum_tools.py` - Tool usage

#### 4. **Bootstrap** (`src/sunwell/bootstrap/`)
**Impact**: Medium - Project initialization  
**Files**: 5 files, only `incremental.py` tested

**Needed Tests**:
- `test_bootstrap_orchestrator.py` - Full bootstrap flow
- `test_bootstrap_scanners.py` - Code/config/docs/git scanners
- `test_bootstrap_ownership.py` - Ownership detection
- Integration test: full bootstrap from scratch

#### 5. **External Integrations** (`src/sunwell/external/`)
**Impact**: Medium - External API integration  
**Files**: 14 files, 0 tests

**Needed Tests**:
- `test_external_webhooks.py` - Webhook handling
- `test_external_scheduler.py` - Cron scheduling
- `test_external_api.py` - API client
- Mock external services for testing
- Error handling for network failures

#### 6. **Verification** (`src/sunwell/verification/`)
**Impact**: Medium - Code verification  
**Files**: 8 files, 0 tests

**Needed Tests**:
- `test_verification_validator.py` - Validation logic
- `test_verification_checks.py` - Type/lint checks
- Integration with tools

#### 7. **Intelligence** (`src/sunwell/intelligence/`)
**Impact**: Medium - AI intelligence layer  
**Files**: 7 files, 0 tests

**Needed Tests**:
- `test_intelligence_queries.py` - Query processing
- `test_intelligence_context.py` - Context building

---

## 🟢 Test Quality Improvements

### 1. **API Contract Tests**

**Problem**: Tests didn't catch API changes (e.g., `frame_index` → `frame_id`)

**Solution**: Add property-based tests using Hypothesis
```python
from hypothesis import given, strategies as st

@given(
    frame_id=st.integers(min_value=0),
    content=st.text(),
    content_hash=st.text(min_size=1)
)
def test_temporal_frame_contract(frame_id, content, content_hash):
    """Test TemporalFrame always accepts correct parameters."""
    frame = TemporalFrame(
        frame_id=frame_id,
        content_hash=content_hash,
        content=content
    )
    assert frame.frame_id == frame_id
```

### 2. **Integration Tests**

**Current**: Mostly unit tests  
**Needed**: End-to-end integration tests

**Examples**:
- `test_integration_agent_full_cycle.py` - Full agent run from goal to completion
- `test_integration_bootstrap.py` - Bootstrap → scan → plan → execute
- `test_integration_team_knowledge.py` - Team store → git → sync

### 3. **Error Handling Tests**

**Missing**: Tests for error conditions

**Needed**:
```python
def test_compound_eye_handles_model_errors():
    """Test compound eye gracefully handles model failures."""
    # Mock model that raises exceptions
    # Verify error handling

def test_team_store_handles_git_errors():
    """Test team store handles git failures."""
    # Mock git failures
    # Verify fallback behavior
```

### 4. **Edge Case Tests**

**Missing**: Boundary conditions, empty inputs, etc.

**Examples**:
- Empty file lists
- Very large inputs
- Unicode/special characters
- Concurrent access (free-threading)
- Network timeouts
- Disk full scenarios

### 5. **Performance Tests**

**Missing**: Tests for performance characteristics

**Needed**:
```python
@pytest.mark.performance
def test_compound_eye_scales_to_large_codebase():
    """Test compound eye handles 10k+ regions."""
    # Measure time/memory
    # Assert reasonable performance
```

### 6. **Mock/Fixture Improvements**

**Current**: Basic mocks  
**Needed**: More realistic test fixtures

**Examples**:
- Realistic codebase fixtures (not just single files)
- Mock models with varied responses
- Git repository fixtures
- File system fixtures

---

## 📊 Test Organization Improvements

### 1. **Test Structure**

**Current**: Flat test files  
**Recommended**: Organize by subsystem

```
tests/
  unit/
    core/
    models/
    tools/
  integration/
    agent/
    bootstrap/
    team/
  fixtures/
    codebases/
    models/
```

### 2. **Test Markers**

**Add**:
```python
@pytest.mark.slow  # Already used but not registered
@pytest.mark.integration
@pytest.mark.performance
@pytest.mark.external  # Requires external services
```

**Register in `pyproject.toml`**:
```toml
[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests as integration tests",
    "performance: marks tests as performance tests",
    "external: marks tests that require external services",
]
```

### 3. **Test Coverage Tracking**

**Add**: Coverage reporting
```bash
pytest --cov=src/sunwell --cov-report=html
```

**Goal**: 80%+ coverage for critical modules

---

## 🔧 Specific Test Improvements

### Compound Eye Tests

**Current Issues**:
- Tests use private functions directly
- Missing tests for error cases
- Missing tests for edge cases (empty inputs, single element)

**Improvements**:
```python
def test_lateral_inhibition_empty_input():
    """Test lateral inhibition with empty input."""
    result = await lateral_inhibition_scan([], ...)
    assert result.edges_found == 0

def test_temporal_diff_single_frame():
    """Test temporal diff with only one frame."""
    # Should handle gracefully

def test_compound_eye_model_failure():
    """Test compound eye handles model failures."""
    # Mock model that fails
    # Verify error handling
```

### Team Tests

**Current Issues**:
- Failing similarity matching tests
- Missing tests for git integration
- Missing tests for concurrent access

**Improvements**:
```python
def test_team_store_similarity_matching():
    """Test various similarity matching scenarios."""
    # Test exact matches
    # Test partial matches
    # Test threshold boundaries

def test_team_store_git_conflicts():
    """Test handling git merge conflicts."""
    # Mock git conflict scenario
    # Verify conflict resolution

def test_team_store_concurrent_writes():
    """Test concurrent writes to team store."""
    # Use threading to simulate concurrent access
    # Verify no data corruption
```

### Adaptive Tests

**Current**: Good coverage  
**Improvements**:
- Add tests for learning store persistence
- Add tests for event handling edge cases
- Add performance tests for signal routing

### Guardrails Tests

**Current**: Good coverage  
**Improvements**:
- Add tests for trust zone edge cases
- Add tests for escalation handling
- Add tests for scope tracking limits

---

## 🎯 Priority Recommendations

### Immediate (This Week)
1. ✅ Fix failing team tests (2 tests)
2. ✅ Add API contract tests for compound eye types
3. ✅ Register pytest markers
4. ✅ Add error handling tests for critical paths

### Short Term (This Month)
1. Add CLI command tests (start with main commands)
2. Add Naaru planner tests (core functionality)
3. Add integration tests for agent full cycle
4. Add test coverage reporting

### Medium Term (Next Quarter)
1. Add Simulacrum tests
2. Add Bootstrap integration tests
3. Add External integration tests
4. Add performance benchmarks

---

## 📝 Test Writing Guidelines

### Best Practices
1. **One assertion per test** (when possible)
2. **Descriptive test names**: `test_<function>_<scenario>_<expected>`
3. **Arrange-Act-Assert** pattern
4. **Use fixtures** for common setup
5. **Mock external dependencies**
6. **Test edge cases** (empty, None, large inputs)
7. **Test error conditions**

### Example Template
```python
@pytest.mark.asyncio
async def test_feature_scenario_expected_behavior():
    """Test description explaining what this tests."""
    # Arrange
    fixture = create_test_fixture()
    
    # Act
    result = await feature_under_test(fixture)
    
    # Assert
    assert result.expected_property == expected_value
    assert len(result.items) > 0
```

---

## 🔍 Test Discovery

**Run specific test categories**:
```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests
pytest -m integration -v

# Fast tests only
pytest -m "not slow" -v

# Coverage report
pytest --cov=src/sunwell --cov-report=term-missing
```

---

## 📈 Metrics to Track

1. **Test count**: Currently 680 tests
2. **Coverage**: Target 80%+ for critical modules
3. **Test execution time**: Target < 30s for fast tests
4. **Flaky test rate**: Target 0%
5. **Test failure rate**: Currently 0.4% (3/680)

---

## 🚀 Next Steps

1. Create test plan for CLI commands
2. Set up test coverage tracking
3. Fix failing team tests
4. Add API contract tests
5. Create integration test suite structure
