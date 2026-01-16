# Quality Benchmark Report

**Generated**: 2026-01-15T22:55:06.589904
**Model**: ollama/gemma3:1b
**Tasks**: 2

## Summary

| Metric | Value |
|--------|-------|
| Win Rate | 0.0% (0W / 2L / 2T) |
| Effect Size (Cohen's d) | -0.234 (small) |
| Statistical Test | scipy_not_available |
| p-value | 1.0000 ✗ |
| 95% CI | [-7.288, 5.306] |
| **Claim Level** | insufficient evidence |

### Interpretation

❌ **Insufficient evidence** to claim improvement. More tasks needed.

## Category Breakdown

| Category | Tasks | Wins | Losses | Ties | Win Rate | Avg Δ |
|----------|-------|------|--------|------|----------|-------|
| review | 4 | 0 | 2 | 2 | 0% | -1.23 |

## Detailed Results

### review-bugs-001

**bare**: ⚠️
  - Missing: race condition, atomic
**flat**: ⚠️
  - Missing: race condition, atomic
**selective**: ⚠️
  - Missing: race condition, atomic

**selective_vs_bare**: BASELINE
  - Scores: baseline=8.6, selective=7.5
  - Agreement: 67%, Position bias: 1.00
**selective_vs_flat**: BASELINE
  - Scores: baseline=8.3, selective=7.2
  - Agreement: 67%, Position bias: 1.00

### review-perf-001

**bare**: ⚠️
  - Missing: Counter
**flat**: ✅
**selective**: ✅

**selective_vs_bare**: TIE
  - Scores: baseline=19.8, selective=18.2
  - Agreement: 67%, Position bias: 0.50
**selective_vs_flat**: TIE
  - Scores: baseline=12.8, selective=11.7
  - Agreement: 100%, Position bias: 0.00
