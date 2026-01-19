# Quality Benchmark Report

**Generated**: 2026-01-18T18:53:12.314340
**Model**: ollama/qwen2.5:1.5b
**Tasks**: 1

## Summary

| Metric | Value |
|--------|-------|
| Win Rate | 50.0% (1W / 1L / 0T) |
| Effect Size (Cohen's d) | -1.569 (large) |
| Statistical Test | scipy_not_available |
| p-value | 1.0000 ✗ |
| 95% CI | [-3.167, -0.167] |
| **Claim Level** | insufficient evidence |

### Interpretation

❌ **Insufficient evidence** to claim improvement. More tasks needed.

## Category Breakdown

| Category | Tasks | Wins | Losses | Ties | Win Rate | Avg Δ |
|----------|-------|------|--------|------|----------|-------|
| code | 2 | 1 | 1 | 0 | 50% | -1.67 |

## Detailed Results

### code-function-001

**bare**: ⚠️
  - Missing: def retry
**flat**: ⚠️
  - Missing: def retry
**selective**: ✅
**self_directed**: ⚠️
  - Missing: max_retries, base_delay, async
**prefetch**: ✅

**selective_vs_bare**: BASELINE
  - Scores: baseline=9.5, selective=7.9
  - Agreement: 67%, Position bias: 1.00
**selective_vs_flat**: SELECTIVE
  - Scores: baseline=8.1, selective=6.3
  - Agreement: 67%, Position bias: 1.00

## Self-Directed Expertise (RFC-027)

Tasks where the model used expertise tools during generation:

### Aggregate Statistics

| Metric | Value |
|--------|-------|
| Tasks Using Expertise Tools | 1 / 1 |
| Total Tool Calls | 1 |
| - get_expertise() | 1 |
| - verify_against_expertise() | 0 |
| - list_expertise_areas() | 0 |
| Followed ReAct Pattern | 0 / 1 (0%) |
| Verification Passed | 0 / 1 |
| Avg Tool Latency | 19ms |

### Per-Task Breakdown

| Task | Calls | Topics | Heuristics | ReAct? | Verify? |
|------|-------|--------|------------|--------|---------|
| code-function-001 | 1 | retry decorator patterns | 1 | ✗ | - |
