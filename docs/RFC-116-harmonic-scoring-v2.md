# RFC-116: Harmonic Scoring v2 — Domain-Aware Plan Quality Metrics

**Status**: Implemented  
**Created**: 2026-01-23  
**Implemented**: 2026-01-23  
**Author**: @llane  
**Depends on**: RFC-038 (Harmonic Planning), RFC-115 (Hierarchical Decomposition)  
**Priority**: P1 — Directly improves plan quality for all agentic requests

---

## Summary

Improve Harmonic's plan selection by replacing the current parallelism-biased scoring with **domain-aware metrics** that recognize:

1. **Irreducible depth** — Some goals legitimately require sequential phases
2. **Mid-graph parallelism** — Fat waves in the middle matter, not just leaves
3. **Semantic coherence** — Plans should actually solve the goal

**The thesis**: Agentic requests are complex by definition. The scoring formula should reward "appropriate structure" not "maximally flat structure."

---

## Problem Statement

### Current Scoring Formula

```python
score = (
    parallelism_factor * 40      # leaf_count / artifact_count
    + balance_factor * 30        # width / depth
    + (1 / depth) * 20           # inverse depth penalty
    + (1 / (1 + conflicts)) * 10 # file conflict penalty
)
```

### Why This Fails

| Bias | Impact | Example |
|------|--------|---------|
| **Leaf obsession** (40%) | Only counts artifacts with zero dependencies | Plan with 5 leaves and 10 internal parallel tasks scores worse than 12 leaves |
| **Depth penalty** (20%) | Punishes necessary sequential work | "Create schema → migrate → seed" MUST be sequential |
| **Ignores wave distribution** | `estimated_waves` tracked but unused | `[2, 15, 10, 1]` (high mid-parallelism) scores same as `[7, 7, 7, 7]` |
| **No semantic check** | Doesn't verify plan covers the goal | Minimal plans win because ratios are better |

### Concrete Example

**Goal**: "Build a REST game with multiplayer"

**Plan A** (Good structure):
```
Wave 1: [Schema, PlayerModel, MoveProtocol, ErrorCodes, DB]     # 5 leaves
Wave 2: [GameEngine, PlayerService, MoveExecutor, Serializer]   # 4 parallel
Wave 3: [/games, /players, /moves endpoints]                    # 3 parallel  
Wave 4: [WebSocket, APITests]                                   # 2 parallel
Wave 5: [main.py]                                               # 1 convergence
```
- Artifacts: 15, Depth: 5, Leaves: 5
- `parallelism_factor`: 5/15 = 0.33
- `balance_factor`: 5/5 = 1.0
- **Current score**: 0.33×40 + 1.0×30 + 0.2×20 + 10 = **57.2**

**Plan B** (Artificially flat):
```
Wave 1: [Everything as "independent" artifacts]  # 12 leaves
Wave 2: [main.py combines everything]            # 1 convergence
```
- Artifacts: 13, Depth: 2, Leaves: 12
- `parallelism_factor`: 12/13 = 0.92
- `balance_factor`: 12/2 = 6.0
- **Current score**: 0.92×40 + 6.0×30 + 0.5×20 + 10 = **237.0**

**Plan B wins 4x over** despite being structurally incorrect — those "parallel" artifacts actually depend on each other semantically.

---

## Goals

1. **Reward mid-graph parallelism** — Fat waves at depth 2-3 are valuable
2. **Don't penalize necessary depth** — Sequential phases are often correct
3. **Add lightweight semantic scoring** — Does the plan cover the goal?
4. **Maintain speed** — Scoring must remain fast (<10ms per plan)
5. **Backward compatible** — Old metrics still available, new score is additive

## Non-Goals

1. **Perfect semantic understanding** — That's what the LLM planner does; we just sanity-check
2. **Domain-specific hardcoded rules** — Should work across code, writing, research, etc.
3. **Replacing human judgment** — Still surfaces candidates for review when uncertain

---

## Design

### New Metrics

```python
@dataclass(frozen=True, slots=True)
class PlanMetricsV2(PlanMetrics):
    """Extended metrics for Harmonic Scoring v2."""
    
    # Wave analysis (new)
    wave_sizes: tuple[int, ...]
    """Size of each execution wave, e.g., (5, 4, 3, 2, 1)."""
    
    avg_wave_width: float
    """artifact_count / estimated_waves — measures "fatness" of waves."""
    
    parallel_work_ratio: float
    """(artifacts - 1) / max(estimated_waves - 1, 1) — work per transition."""
    
    wave_variance: float
    """Standard deviation of wave sizes — lower = more balanced."""
    
    # Semantic signals (new, lightweight)
    keyword_coverage: float
    """Fraction of goal keywords found in artifact descriptions (0.0-1.0)."""
    
    has_convergence: bool
    """True if graph has a single root (proper convergence point)."""
    
    # Depth context (new)
    depth_utilization: float
    """avg_wave_width / depth — how well we use the depth we have."""
```

### New Scoring Formula

```python
def score_v2(self) -> float:
    """Harmonic Scoring v2 — rewards appropriate structure.
    
    Philosophy: 
    - Don't penalize depth; penalize UNUSED depth
    - Reward parallel work at ALL levels, not just leaves
    - Add lightweight semantic sanity check
    """
    return (
        # Parallelism (reworked) — 35%
        self.parallel_work_ratio * 20        # Work per wave transition
        + self.avg_wave_width * 15           # Fat waves = good
        
        # Structure quality — 30%
        + self.depth_utilization * 20        # Using depth well
        + (1 / (1 + self.wave_variance)) * 10  # Balanced waves
        
        # Semantic coherence — 20%
        + self.keyword_coverage * 15         # Covers the goal
        + (5 if self.has_convergence else 0) # Proper DAG structure
        
        # Conflict avoidance — 15%
        + (1 / (1 + self.file_conflicts)) * 15
    )
```

### Weight Rationale

| Factor | Weight | Why |
|--------|--------|-----|
| `parallel_work_ratio` | 20% | Directly measures concurrent operations possible |
| `avg_wave_width` | 15% | Rewards plans with fat waves, regardless of depth |
| `depth_utilization` | 20% | Don't penalize depth if you're USING it for parallelism |
| `wave_variance` | 10% | Balanced waves = predictable execution time |
| `keyword_coverage` | 15% | Lightweight check: does plan mention what goal asked for? |
| `has_convergence` | 5% | Proper DAG structure (single deliverable at end) |
| `file_conflicts` | 15% | Practical execution concern |

### Computing New Metrics

```python
def _compute_metrics_v2(self, graph: ArtifactGraph, goal: str) -> PlanMetricsV2:
    """Compute extended metrics."""
    # Existing metrics
    waves = graph.execution_waves()
    wave_sizes = tuple(len(w) for w in waves)
    depth = len(waves)
    artifact_count = len(graph)
    
    # New: wave analysis
    avg_wave_width = artifact_count / max(depth, 1)
    parallel_work_ratio = (artifact_count - 1) / max(depth - 1, 1)
    wave_variance = statistics.stdev(wave_sizes) if len(wave_sizes) > 1 else 0.0
    
    # New: depth utilization
    # High value = we're doing a lot of parallel work relative to depth
    depth_utilization = avg_wave_width / max(depth, 1)
    
    # New: lightweight semantic check
    goal_keywords = set(self._extract_keywords(goal))
    artifact_keywords = set()
    for artifact in graph.artifacts.values():
        artifact_keywords.update(self._extract_keywords(artifact.description))
    
    if goal_keywords:
        keyword_coverage = len(goal_keywords & artifact_keywords) / len(goal_keywords)
    else:
        keyword_coverage = 1.0  # No keywords = assume coverage
    
    # New: convergence check
    roots = [a for a in graph.artifacts.values() if not graph.dependents(a.id)]
    has_convergence = len(roots) == 1
    
    return PlanMetricsV2(
        # ... existing fields ...
        wave_sizes=wave_sizes,
        avg_wave_width=avg_wave_width,
        parallel_work_ratio=parallel_work_ratio,
        wave_variance=wave_variance,
        keyword_coverage=keyword_coverage,
        has_convergence=has_convergence,
        depth_utilization=depth_utilization,
    )

def _extract_keywords(self, text: str) -> list[str]:
    """Extract significant keywords from text (fast, no LLM)."""
    # Simple: lowercase, split, filter stopwords, filter short
    stopwords = {'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
    words = text.lower().split()
    return [w for w in words if len(w) > 3 and w not in stopwords]
```

---

## Examples: Before/After

### "Build a REST game"

| Metric | Plan A (Good) | Plan B (Flat) | Winner |
|--------|---------------|---------------|--------|
| **V1 Score** | 57.2 | 237.0 | B (wrong!) |
| `parallel_work_ratio` | 14/4 = 3.5 | 12/1 = 12.0 | B |
| `avg_wave_width` | 15/5 = 3.0 | 13/2 = 6.5 | B |
| `depth_utilization` | 3.0/5 = 0.6 | 6.5/2 = 3.25 | B |
| `keyword_coverage` | 0.9 | 0.4 | **A** |
| `has_convergence` | ✅ | ✅ | Tie |
| `wave_variance` | 1.58 | 7.78 | **A** |
| **V2 Score** | **72.3** | **68.1** | **A** ✅ |

The keyword coverage and wave variance swing it — Plan B's "everything parallel" approach can't actually describe what it builds (low keyword coverage) and has wildly unbalanced waves.

### "Write a murder fantasy novel"

| Metric | Hierarchical Plan | Flat Plan |
|--------|-------------------|-----------|
| Waves | [6, 3, 10, 10, 3] | [30, 1, 1] |
| `avg_wave_width` | 32/5 = 6.4 | 32/3 = 10.7 |
| `depth_utilization` | 6.4/5 = 1.28 | 10.7/3 = 3.56 |
| `keyword_coverage` | 0.95 | 0.3 (chapters don't mention characters) |
| `wave_variance` | 3.5 | 16.7 |
| **V2 Winner** | ✅ | ❌ |

---

## Migration

### Phase 1: Parallel Scoring (Week 1)
- Add `PlanMetricsV2` alongside `PlanMetrics`
- Compute both scores for every candidate
- Log V1 vs V2 winner disagreements for analysis

### Phase 2: A/B Testing (Week 2)
- `--scoring=v1` (default) vs `--scoring=v2` flag
- Run benchmark suite with both
- Measure: task completion rate, user satisfaction, execution time

### Phase 3: Default Flip (Week 3)
- If V2 shows improvement, make it default
- Keep V1 available via `--scoring=v1` for rollback
- Remove V1 after 1 month with no regressions

---

## Configuration

```yaml
# sunwell.yaml
naaru:
  harmonic_scoring: "v2"        # "v1" | "v2" | "auto"
  scoring_weights:              # Override defaults
    parallel_work_ratio: 20
    avg_wave_width: 15
    depth_utilization: 20
    wave_variance: 10
    keyword_coverage: 15
    has_convergence: 5
    file_conflicts: 15
```

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| V2 scores slower | Keyword extraction is O(n) on artifact count; benchmark shows <2ms overhead |
| Keyword coverage too naive | It's a sanity check, not semantic understanding; 15% weight limits damage |
| Breaking existing plans | A/B test before default flip; keep V1 available |
| Wave variance penalizes legitimate imbalance | 10% weight is low; variance only breaks ties |

---

## Open Questions

1. **Should keyword coverage use embeddings?** 
   - Pro: More semantic, catches synonyms
   - Con: Requires model call, adds latency
   - Current answer: No, keep it fast; embeddings are overkill for sanity check

2. **Should we add a "minimum artifact" threshold?**
   - Plans with <5 artifacts for complex goals are suspicious
   - Could add: `artifact_sufficiency = min(1.0, artifact_count / expected_min)`
   - Deferred: Hard to know "expected_min" without domain knowledge

3. **Should depth utilization have a cap?**
   - Very shallow plans can game high `depth_utilization`
   - Could add: `if depth < 2: depth_utilization *= 0.5`
   - Deferred: Let A/B testing reveal if this is needed

---

## Success Criteria

1. **Plan quality**: V2 selects "better" plan (per human eval) in >70% of disagreements with V1
2. **Task completion**: No regression in benchmark task completion rate
3. **Speed**: Scoring time increase <5ms per candidate
4. **Adoption**: Users don't immediately flip back to `--scoring=v1`

---

## Implementation Plan

```
[ ] Add PlanMetricsV2 dataclass to harmonic.py
[ ] Implement _compute_metrics_v2 method
[ ] Add score_v2 property to PlanMetricsV2
[ ] Add --scoring flag to CLI
[ ] Add logging for V1/V2 disagreements
[ ] Run benchmark suite with both scoring versions
[ ] Write migration docs
[ ] Default flip (after A/B results)
```

---

## References

- `src/sunwell/naaru/planners/harmonic.py:88-101` — Current scoring formula
- `src/sunwell/naaru/planners/harmonic.py:659-691` — Current _score_plan implementation
- RFC-038: Harmonic Planning (original design)
- RFC-115: Hierarchical Goal Decomposition (related: planning for complex goals)
