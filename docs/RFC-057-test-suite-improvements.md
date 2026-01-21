# RFC-057: Test Suite Improvements — Coverage, Quality, and Reliability

**Status**: Draft  
**Created**: 2026-01-18  
**Authors**: Sunwell Team  
**Confidence**: 88% 🟢  
**Depends on**: None  
**Enables**: 
- Reliable CI/CD pipelines
- Safe refactoring
- API contract enforcement
- Performance regression detection

---

## Summary

This RFC addresses critical gaps in Sunwell's test suite: **missing coverage** for major subsystems (CLI, Naaru, Simulacrum), **test quality issues** (no API contract tests, sparse integration tests), and **reliability problems** (failing tests, no coverage tracking).

**Current state**: 677 passing tests, 3 failing, 30 test files for 360 source files  
**Target state**: 1000+ tests, 90%+ coverage for critical modules, <1% failure rate, comprehensive integration test suite

**Core improvements**:
1. **Coverage expansion** — Add tests for CLI (34 files), Naaru (64 files, including benchmarks), Simulacrum (40 files)
2. **Quality enhancement** — API contract tests, integration tests, error handling tests
3. **Reliability** — Fix failing tests, add coverage tracking, performance benchmarks
4. **Organization** — Better test structure, fixtures, markers

**One-liner**: Transform test suite from "mostly working" to "comprehensive, reliable, and maintainable" foundation for safe development.

---

## Motivation

### The Current State

**What's working**:
- 677 passing tests covering core functionality
- Good unit test coverage for: adaptive, guardrails, tools, embedding, core
- Test fixtures and mocks in place
- Fast test execution (<30s for unit tests)

**What's broken**:
- 3 failing tests (team intelligence similarity matching — threshold bug: `> 0.5` should be `>= 0.5`)
- No tests for CLI commands (34 files, user-facing)
- No tests for Naaru (64 files including benchmarks, core planning system)
- No tests for Simulacrum (40 files, agent simulation)
- API changes not caught by tests (e.g., `frame_index` → `frame_id`)
- No integration tests for end-to-end flows
- No coverage tracking configured (`pytest-cov` installed but not configured)

### The Problem

**1. Refactoring Risk**

Without comprehensive tests, refactoring becomes dangerous:

```
Developer: "I'll refactor the Naaru planner to improve performance"
           → Changes 20 files
           → Runs tests: ✅ All pass
           → Deploys: 💥 Production breaks
           
Why? No tests for Naaru → changes weren't validated
```

**2. API Drift**

Tests didn't catch API changes:

```
Implementation: TemporalFrame(frame_id=..., ...)
Tests:          TemporalFrame(frame_index=..., ...)  # Wrong!

Result: Tests pass but code is broken
```

**3. Integration Gaps**

Unit tests verify components in isolation, but not together:

```
Unit tests: ✅ Agent planner works
           ✅ Task executor works  
           ✅ Checkpoint system works
           
Integration: ❓ Does agent → executor → checkpoint work end-to-end?
             → Unknown until production
```

**4. Missing Critical Paths**

User-facing features have no tests:

```
CLI commands: 34 files, 0 tests
→ User runs: sunwell agent run "build API"
→ Error: "Unknown command" (typo in command routing)
→ No test caught it
```

### The Opportunity

**Benefits of comprehensive test suite**:
- **Safe refactoring** — Change code with confidence
- **API contracts** — Catch breaking changes automatically
- **Documentation** — Tests show how code should be used
- **Regression prevention** — Catch bugs before they ship
- **Performance tracking** — Detect slowdowns early

### Non-Goals

This RFC does **not** aim to:
- Rewrite existing tests (unless they're broken)
- Achieve 100% coverage (target is 90%+ for critical modules)
- Replace manual testing (complements, not replaces)
- Add tests for third-party dependencies
- Create performance tests for all modules (only critical paths)

---

## Design

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    TEST SUITE STRUCTURE                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  tests/                                                     │
│  ├── unit/              # Fast, isolated tests              │
│  │   ├── core/         # Core types, lenses                │
│  │   ├── models/       # Model protocols                   │
│  │   ├── tools/        # Tool handlers                    │
│  │   └── ...           # Other unit tests                 │
│  │                                                         │
│  ├── integration/       # End-to-end tests                 │
│  │   ├── agent/        # Full agent cycle                 │
│  │   ├── bootstrap/     # Bootstrap flow                  │
│  │   ├── team/          # Team knowledge sync            │
│  │   └── cli/           # CLI command integration         │
│  │                                                         │
│  ├── fixtures/          # Reusable test data             │
│  │   ├── codebases/     # Sample codebases               │
│  │   ├── models/        # Mock model responses           │
│  │   └── git/           # Git repository fixtures        │
│  │                                                         │
│  └── performance/       # Performance benchmarks         │
│      ├── compound_eye/  # Compound eye scaling            │
│      └── planning/      # Planning performance            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Architecture Impact

**On Existing Code**:
- No breaking changes to production code
- Tests are additive only
- Existing test structure preserved (moved to `tests/unit/`)

**On CI/CD Pipeline**:
- Add coverage reporting step
- Separate fast/slow test runs
- Coverage gates (fail if coverage drops below threshold)
- Performance regression alerts

**On Development Workflow**:
- Developers run fast tests locally (`pytest -m "not slow"`)
- CI runs full suite including slow/integration tests
- Coverage reports generated automatically
- Performance benchmarks run nightly

**On Test Maintenance**:
- Clear test organization reduces maintenance burden
- Fixtures reduce duplication
- Markers enable selective test execution
- Contract tests catch API changes automatically

### Test Categories

#### 1. Unit Tests (Fast, Isolated)

**Purpose**: Test individual components in isolation  
**Target**: <100ms per test, 1000+ tests  
**Coverage**: All public APIs

**Examples**:
```python
# tests/unit/core/test_types.py
def test_temporal_frame_creation():
    """Test TemporalFrame creation with valid inputs."""
    frame = TemporalFrame(
        frame_id=0,
        content_hash="abc123",
        content="test content"
    )
    assert frame.frame_id == 0

# tests/unit/team/test_similarity.py
def test_similarity_exact_match():
    """Test similarity matching with exact strings."""
    store = TeamKnowledgeStore(tmp_path)
    assert store._similar("MySQL", "MySQL") is True
```

#### 2. Integration Tests (End-to-End)

**Purpose**: Test full workflows  
**Target**: <5s per test, 50+ tests  
**Coverage**: Critical user paths

**Examples**:
```python
# tests/integration/agent/test_full_cycle.py
@pytest.mark.integration
async def test_agent_full_cycle():
    """Test complete agent run from goal to completion."""
    # 1. Create goal
    goal = "Build a Flask API with users and posts"
    
    # 2. Run agent
    result = await agent.run(goal)
    
    # 3. Verify checkpoint created
    checkpoint = await load_checkpoint(result.checkpoint_id)
    assert checkpoint.goal == goal
    
    # 4. Verify tasks created
    assert len(checkpoint.tasks) > 0
    
    # 5. Verify execution
    assert result.status == "complete"
```

#### 3. API Contract Tests (Property-Based)

**Purpose**: Catch API changes automatically  
**Target**: Use Hypothesis for property-based testing  
**Coverage**: All public APIs

**Examples**:
```python
# tests/unit/core/test_contracts.py
from hypothesis import given, strategies as st

@given(
    frame_id=st.integers(min_value=0),
    content=st.text(),
    content_hash=st.text(min_size=1)
)
def test_temporal_frame_contract(frame_id, content, content_hash):
    """TemporalFrame accepts any valid parameters."""
    frame = TemporalFrame(
        frame_id=frame_id,
        content_hash=content_hash,
        content=content
    )
    assert frame.frame_id == frame_id
    assert frame.content == content
```

#### 4. Error Handling Tests

**Purpose**: Verify graceful error handling  
**Target**: All error paths covered  
**Coverage**: Network failures, invalid inputs, edge cases

**Examples**:
```python
# tests/unit/compound_eye/test_errors.py
@pytest.mark.asyncio
async def test_compound_eye_model_failure():
    """Test compound eye handles model failures gracefully."""
    mock_model = AsyncMock()
    mock_model.generate.side_effect = Exception("Model error")
    
    with pytest.raises(CompoundEyeError):
        await lateral_inhibition_scan(
            regions=["test"],
            question="Rate danger",
            model=mock_model
        )
```

#### 5. Performance Tests

**Purpose**: Detect performance regressions  
**Target**: Benchmark critical paths  
**Coverage**: Compound eye, planning, embedding

**Examples**:
```python
# tests/performance/test_compound_eye_scaling.py
@pytest.mark.performance
def test_compound_eye_scales_to_large_codebase():
    """Test compound eye handles 10k+ regions."""
    regions = [f"region_{i}" for i in range(10000)]
    
    start = time.time()
    result = await lateral_inhibition_scan(regions, ...)
    duration = time.time() - start
    
    assert duration < 60.0  # Should complete in <60s
    assert result.total_regions == 10000
```

---

## Implementation Plan

### Phase 1: Foundation (Week 1)

**Goal**: Fix immediate issues, set up infrastructure

**Tasks**:
1. ✅ Fix failing team tests (similarity threshold bug: `> 0.5` → `>= 0.5` in `src/sunwell/team/store.py:794`)
2. ✅ Verify pytest markers (already registered in `pyproject.toml:91-96` — `slow`, `integration`, `performance`, `external`)
3. ✅ Configure test coverage tracking (`pytest-cov` already in dev deps, add `[tool.coverage]` config)
4. ✅ Create test directory structure (`unit/`, `integration/`, `fixtures/`, `performance/`)
5. ✅ Add API contract test framework (add `hypothesis>=6.0` to dev deps, create `tests/unit/core/test_contracts.py`)

**Dependencies**:
- `hypothesis>=6.0` (property-based testing)
- `pytest-cov>=4.1` (already in dev deps)

**Deliverables**:
- All tests passing
- Coverage report showing current state (run: `pytest --cov=src/sunwell --cov-report=html`)
- Test structure in place
- Coverage configuration in `pyproject.toml`:
  ```toml
  [tool.coverage.run]
  source = ["src/sunwell"]
  omit = ["*/tests/*", "*/test_*"]
  
  [tool.coverage.report]
  exclude_lines = [
      "pragma: no cover",
      "def __repr__",
      "raise AssertionError",
      "raise NotImplementedError",
      "if __name__ == .__main__.:",
      "if TYPE_CHECKING:",
  ]
  precision = 2
  show_missing = true
  skip_covered = false
  ```

### Phase 2: Critical Coverage (Weeks 2-3)

**Goal**: Add tests for most critical missing modules

**Priority order**:
1. **CLI commands** (34 files) — User-facing, high impact
   - `test_cli_main.py` — Command routing
   - `test_cli_agent.py` — Agent commands
   - `test_cli_team.py` — Team commands
   - Error handling for invalid commands

2. **Naaru planner** (64 files, including benchmarks) — Core planning system
   - `test_naaru_planner.py` — Planning logic
   - `test_naaru_executor.py` — Task execution
   - `test_naaru_checkpoint.py` — State persistence
   - Integration test for full planning cycle
   - Note: Exclude `src/sunwell/benchmark/naaru/` from coverage targets (test utilities)

3. **Team intelligence fixes** — Fix similarity matching
   - Unit tests for `_similar()` method
   - Fix threshold bug (`> 0.5` → `>= 0.5`)
   - Add tests for `check_similar_failures()`

**Deliverables**:
- 200+ new tests
- CLI commands tested
- Naaru core functionality tested
- Team tests fixed

### Phase 3: Integration Tests (Week 4)

**Goal**: Add end-to-end integration tests

**Tests**:
1. **Agent full cycle** — Goal → Plan → Execute → Complete
2. **Bootstrap flow** — Init → Scan → Populate intelligence
3. **Team knowledge sync** — Create → Git → Sync → Read
4. **CLI integration** — Command → Execution → Output

**Deliverables**:
- 20+ integration tests
- End-to-end coverage for critical paths

### Phase 4: Quality & Performance (Weeks 5-6)

**Goal**: Improve test quality and add performance benchmarks

**Tasks**:
1. **API contract tests** — Use Hypothesis for all public APIs
2. **Error handling tests** — Cover all error paths
3. **Edge case tests** — Empty inputs, large inputs, concurrent access
4. **Performance benchmarks** — Compound eye, planning, embedding

**Deliverables**:
- 100+ contract tests
- Error handling coverage
- Performance benchmarks

### Phase 5: Simulacrum & Remaining (Weeks 7-8)

**Goal**: Complete coverage for remaining modules

**Tests**:
1. **Simulacrum** (40 files) — Agent simulation
2. **Bootstrap scanners** — Code/config/docs/git scanners
3. **External integrations** — Webhooks, scheduling, API clients
4. **Verification** — Code verification logic

**Deliverables**:
- 300+ new tests
- 90%+ coverage for critical modules

---

## Design Alternatives

### Alternative A: Minimal Coverage (Rejected)

**Approach**: Only test user-facing features (CLI)

**Pros**:
- Fast to implement
- Covers highest-risk areas

**Cons**:
- Doesn't catch internal bugs
- Refactoring still risky
- No API contract enforcement

**Verdict**: ❌ Rejected — Too narrow, doesn't solve core problems

### Alternative B: Property-Based Testing Only (Rejected)

**Approach**: Use Hypothesis for all tests, no unit tests

**Pros**:
- Catches edge cases automatically
- Less code to write

**Cons**:
- Slower test execution
- Harder to debug failures
- Less readable test output

**Verdict**: ❌ Rejected — Better as supplement, not replacement

### Alternative C: Integration Tests Only (Rejected)

**Approach**: Only test end-to-end flows

**Pros**:
- Tests real user scenarios
- Catches integration bugs

**Cons**:
- Slow execution
- Hard to isolate failures
- Doesn't catch unit-level bugs

**Verdict**: ❌ Rejected — Need both unit and integration tests

### Chosen Approach: Comprehensive Suite

**Approach**: Unit tests (fast) + Integration tests (thorough) + Contract tests (API safety) + Performance tests (regression detection)

**Pros**:
- Fast feedback (unit tests)
- Real-world validation (integration tests)
- API safety (contract tests)
- Performance tracking (benchmarks)

**Cons**:
- More work upfront
- More tests to maintain

**Verdict**: ✅ Chosen — Best long-term value

---

## Test Writing Guidelines

### Best Practices

1. **One assertion per test** (when possible)
2. **Descriptive names**: `test_<function>_<scenario>_<expected>`
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
    mock_dependency = Mock()
    
    # Act
    result = await feature_under_test(fixture, mock_dependency)
    
    # Assert
    assert result.expected_property == expected_value
    assert len(result.items) > 0
    mock_dependency.assert_called_once()
```

### Test Markers

```python
@pytest.mark.slow          # Slow test (>1s)
@pytest.mark.integration   # Integration test
@pytest.mark.performance   # Performance benchmark
@pytest.mark.external      # Requires external services
```

**Usage**:
```bash
# Run fast tests only
pytest -m "not slow"

# Run integration tests
pytest -m integration

# Run all except external
pytest -m "not external"
```

---

## Success Metrics

### Coverage Targets

| Module | Current | Target | Priority | Notes |
|--------|---------|--------|----------|-------|
| CLI | 0% | 80% | High | User-facing, critical |
| Naaru | 0% | 90% | High | Core planning system (exclude benchmarks) |
| Simulacrum | 0% | 80% | Medium | Agent simulation |
| Bootstrap | 20% | 80% | Medium | Project initialization |
| Team | 70% | 90% | High | Fix failing tests first |
| Compound Eye | 85% | 95% | Medium | Already well-tested |
| Core | 80% | 95% | High | Foundation for all modules |

**Overall target**: 90%+ coverage for critical modules, 80%+ for all modules

### Quality Metrics

- **Test count**: 677 → 1000+ tests
- **Failure rate**: <1% (currently 0.4%)
- **Test execution time**: <30s for fast tests, <5min for full suite
- **Flaky test rate**: 0%
- **API contract coverage**: 100% of public APIs

### Reliability Metrics

- **CI/CD pass rate**: >99%
- **Regression detection**: Catch 90%+ of bugs before merge
- **Refactoring confidence**: Developers can refactor safely

---

## Decisions

### D1: Test Data Management

**Decision**: Generate fixtures programmatically

**Rationale**: 
- More maintainable (no large binary files in repo)
- Smaller repo size
- Easier to update fixtures as code evolves
- Fixtures can be versioned with code

**Implementation**: Create `tests/fixtures/generators.py` with functions to generate test codebases, git repos, etc.

### D2: Performance Test Thresholds

**Decision**: Relative thresholds (<2x baseline) with fixed fallbacks

**Rationale**: 
- Adapts to hardware differences (CI vs. local)
- Still catches major regressions
- Baseline established in Phase 4

**Implementation**: 
- Store baseline in `tests/performance/baselines.json`
- Compare against baseline, fail if >2x slower
- If no baseline exists, use fixed thresholds as fallback

### D3: Integration Test Scope

**Decision**: Critical user paths only (Option A)

**Rationale**: 
- Balance coverage vs. speed
- Focus on highest-risk workflows
- Can expand later if needed

**Critical paths**:
1. Agent full cycle (goal → plan → execute → complete)
2. Bootstrap flow (init → scan → populate intelligence)
3. Team knowledge sync (create → git → sync → read)
4. CLI command execution (command → output)

---

## Risks & Mitigations

### Risk 1: Test Maintenance Burden

**Risk**: Too many tests become hard to maintain

**Mitigation**:
- Use fixtures to reduce duplication
- Document test patterns
- Regular test cleanup (remove obsolete tests)

### Risk 2: Slow Test Execution

**Risk**: Test suite becomes too slow for rapid development

**Mitigation**:
- Separate fast/slow tests with markers
- Run fast tests in CI, slow tests nightly
- Optimize slow tests

### Risk 3: Flaky Tests

**Risk**: Tests fail intermittently, reducing confidence

**Mitigation**:
- Avoid time-dependent tests
- Use deterministic mocks
- Retry flaky tests in CI

---

## Dependencies

**None** — This RFC is foundational and enables other work

**Enables**:
- Safe refactoring of any module
- API evolution with confidence
- Performance regression detection
- Reliable CI/CD pipelines

---

## References

- [Test Analysis Document](/docs/TEST-ANALYSIS.md) — Detailed analysis of current state
- [Hypothesis Documentation](https://hypothesis.readthedocs.io/) — Property-based testing
- [pytest Best Practices](https://docs.pytest.org/en/stable/goodpractices.html)
- RFC-045 (Project Intelligence) — Intelligence stores being tested
- RFC-052 (Team Intelligence) — Team knowledge system being tested

---

## Appendix: Test Examples

### Example 1: CLI Command Test

```python
# tests/integration/cli/test_agent_command.py
@pytest.mark.integration
def test_agent_run_command(tmp_path, monkeypatch):
    """Test agent run command end-to-end."""
    # Arrange
    goal = "Build a Flask API"
    monkeypatch.chdir(tmp_path)
    
    # Act
    result = run_command(["sunwell", "agent", "run", goal])
    
    # Assert
    assert result.exit_code == 0
    assert "Goal created" in result.stdout
    assert (tmp_path / ".sunwell" / "checkpoints").exists()
```

### Example 2: API Contract Test

```python
# tests/unit/core/test_contracts.py
from hypothesis import given, strategies as st

@given(
    index=st.integers(min_value=0),
    region_text=st.text(),
    frame_hashes=st.lists(st.text(), min_size=1),
    stability_score=st.floats(min_value=0.0, max_value=1.0),
    is_stable=st.booleans()
)
def test_region_stability_contract(
    index, region_text, frame_hashes, stability_score, is_stable
):
    """RegionStability accepts any valid parameters."""
    region = RegionStability(
        index=index,
        region_text=region_text,
        frame_hashes=tuple(frame_hashes),
        stability_score=stability_score,
        is_stable=is_stable
    )
    assert region.index == index
    assert region.stability_score == stability_score
```

### Example 3: Error Handling Test

```python
# tests/unit/compound_eye/test_errors.py
@pytest.mark.asyncio
async def test_lateral_inhibition_handles_model_timeout():
    """Test lateral inhibition handles model timeouts."""
    mock_model = AsyncMock()
    mock_model.generate.side_effect = asyncio.TimeoutError()
    
    with pytest.raises(CompoundEyeError) as exc_info:
        await lateral_inhibition_scan(
            regions=["test region"],
            question="Rate danger",
            model=mock_model
        )
    
    assert "timeout" in str(exc_info.value).lower()
```

---

**Status**: Ready for planning  
**Next Steps**: 
1. Move to `plan/evaluated/` after approval
2. Run `::plan` to convert RFC into actionable tasks
3. Begin Phase 1 implementation
4. Set up coverage tracking with configuration above
5. Fix failing tests (similarity threshold bug)
