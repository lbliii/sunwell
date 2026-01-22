# RFC-093: Per-Skill Permission Breakdown

**Status:** Evaluated  
**Author:** AI Assistant  
**Created:** 2026-01-22  
**Updated:** 2026-01-22  
**Related:** RFC-089 (Security-First Skills), RFC-092 (Skill Permission Defaults)

---

## Executive Summary

RFC-089 shows **aggregated permissions** for an entire DAG before execution. Users see "this pipeline needs filesystem write + shell access" but not **which skill** needs what. This RFC adds **per-skill permission breakdown** to the security approval UI.

**Benefits:**
1. **Transparency**: "Skill X needs shell, Skill Y is read-only"
2. **Debugging**: Identify which skill is requesting risky permissions
3. **Trust calibration**: Users can assess if permissions match skill purpose
4. **Demo value**: Shows the DAG → permission mapping visually

---

## Problem Statement

### Current State (RFC-089)

```
┌─────────────────────────────────────────────────────────────────┐
│  🔒 Security Review                                              │
│                                                                  │
│  Pipeline: Build Forum App (4 skills)                            │
│                                                                  │
│  PERMISSIONS:                                                    │
│  ├── Filesystem: Read ✅ Write ✅                                │
│  ├── Network: ❌                                                 │
│  └── Shell: python, pytest, ruff                                 │
│                                                                  │
│  Risk: LOW                                                       │
│                                                                  │
│  [Approve]                                                       │
└─────────────────────────────────────────────────────────────────┘
```

**Problem**: User doesn't know:
- Which of the 4 skills needs shell access?
- Is `code-exploration` really read-only?
- Why does `test-and-lint` need write access?

### User Questions We Can't Answer

| Question | Current Answer |
|----------|----------------|
| "Which skill needs network?" | "Somewhere in the DAG" |
| "Can I approve just the safe skills?" | No granular control |
| "Why is this medium risk?" | "One skill has elevated perms" |

---

## Solution: Expandable Per-Skill Breakdown

### Default View (Collapsed)

```
┌─────────────────────────────────────────────────────────────────┐
│  🔒 Security Review                                              │
│                                                                  │
│  Pipeline: Build Forum App                                       │
│  Skills: 4                        [▼ Show breakdown]             │
│                                                                  │
│  AGGREGATED PERMISSIONS:                                         │
│  ├── 📁 Filesystem: Read ✅ Write ✅                             │
│  ├── 🌐 Network: ❌ Denied                                       │
│  └── 💻 Shell: python, pytest, ruff                              │
│                                                                  │
│  Risk: LOW ✅                                                    │
│                                                                  │
│  [Approve]                                                       │
└─────────────────────────────────────────────────────────────────┘
```

### Expanded View (Per-Skill)

```
┌─────────────────────────────────────────────────────────────────┐
│  🔒 Security Review                                              │
│                                                                  │
│  Pipeline: Build Forum App                                       │
│  Skills: 4                        [▲ Hide breakdown]             │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ SKILL BREAKDOWN                                             │ │
│  ├─────────────────────────────────────────────────────────────┤ │
│  │                                                             │ │
│  │ 1. code-exploration                                         │ │
│  │    Preset: read-only                                        │ │
│  │    📁 Read: ✅  Write: ❌  🌐 Net: ❌  💻 Shell: ❌          │ │
│  │    Risk: NONE                                               │ │
│  │                                                             │ │
│  │ 2. draft-documentation                                      │ │
│  │    Preset: workspace-write                                  │ │
│  │    📁 Read: ✅  Write: ✅  🌐 Net: ❌  💻 Shell: ❌          │ │
│  │    Risk: LOW (write to docs/)                               │ │
│  │                                                             │ │
│  │ 3. code-modification                                        │ │
│  │    Preset: workspace-write                                  │ │
│  │    📁 Read: ✅  Write: ✅  🌐 Net: ❌  💻 Shell: ❌          │ │
│  │    Risk: LOW (write to src/)                                │ │
│  │                                                             │ │
│  │ 4. test-and-lint                      ← HIGHEST PERMISSION  │ │
│  │    Preset: safe-shell                                       │ │
│  │    📁 Read: ✅  Write: ✅  🌐 Net: ❌  💻 Shell: ✅          │ │
│  │    Allowed: python, pytest, ruff, mypy                      │ │
│  │    Denied: curl, wget, ssh, sudo, rm -rf                    │ │
│  │    Risk: LOW (shell limited to dev tools)                   │ │
│  │                                                             │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  AGGREGATED: Read ✅ | Write ✅ | Network ❌ | Shell ✅          │
│  Risk: LOW ✅                                                    │
│                                                                  │
│  [Approve]                                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Do We Need a Log Tab?

### Analysis

RFC-089 already implements `AuditLogPanel.svelte` with:
- Timestamped execution history
- Per-skill action logging
- Integrity verification
- Violation tracking

**Question**: Does this need a dedicated UI tab, or is it background infrastructure?

### Recommendation: No Dedicated Tab (For Now)

| Approach | Pros | Cons |
|----------|------|------|
| **Dedicated "Security" tab** | Always visible, enterprise-friendly | Clutters nav for casual users |
| **Settings → Security panel** | Clean nav, power-user accessible | Hidden, less discoverable |
| **Inline in approval modal** | Contextual, shows recent history | Limited space |
| **No UI, CLI only** | Simplest | Poor UX for Studio users |

**Recommendation**: **Settings → Security panel** with:
- Recent audit log (last 20 entries)
- "Verify integrity" button
- Link to full log file
- Export for compliance

**Rationale**:
1. Most users don't need to see logs constantly
2. Power users / compliance can access via Settings
3. Keeps main nav clean (Home, Agent, Files, Terminal)
4. Violations still show as notifications/banners when they occur

### Future: Promote to Tab If Needed

If enterprise users demand it, we can add a "Security" tab later. The infrastructure (`security.svelte.ts` store, `AuditLogPanel.svelte`) already exists.

---

## Architecture

### Risk Thresholds

To ensure consistency between the per-skill breakdown and the aggregated score, we use the following thresholds for `risk_contribution`:

| Level | Score Range | Primary Triggers | UI Color |
|-------|-------------|------------------|----------|
| **NONE** | 0.0 | No permissions requested | Gray |
| **LOW** | 0.1 - 0.4 | Filesystem read/write in workspace | Green |
| **MEDIUM** | 0.5 - 0.7 | External network, restricted shell | Yellow |
| **HIGH** | 0.8 - 1.0 | Dangerous commands, credential access | Red |

*Note: Credential access or dangerous commands auto-escalate a skill to HIGH risk regardless of other permissions.*

### Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    PER-SKILL BREAKDOWN FLOW                      │
│                                                                  │
│  Python SkillLoader                                              │
│    ↓ resolves presets                                           │
│  skills: [                                                       │
│    { name: "code-exploration", preset: "read-only", perms: {...}│
│    { name: "test-and-lint", preset: "safe-shell", perms: {...} }│
│  ]                                                               │
│    ↓                                                            │
│  Python PermissionAnalyzer.analyze_dag_detailed()                │
│    ↓ returns                                                    │
│  {                                                               │
│    aggregated: PermissionScope,                                  │
│    risk: RiskAssessment,                                         │
│    breakdown: [                          ← NEW                   │
│      { skill: "code-exploration", preset: "read-only", ... },   │
│      { skill: "test-and-lint", preset: "safe-shell", ... },     │
│    ]                                                             │
│  }                                                               │
│    ↓                                                            │
│  JSON to Studio                                                  │
│    ↓                                                            │
│  SecurityApprovalModal shows breakdown (expandable)              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Cross-Language Types

#### Python (Source of Truth)

```python
# src/sunwell/security/analyzer.py — ADDITIONS

@dataclass(frozen=True, slots=True)
class SkillPermissionBreakdown:
    """Per-skill permission info for transparency."""
    
    skill_name: str
    preset: str | None
    permissions: PermissionScope
    risk_contribution: str  # "none", "low", "medium", "high"
    risk_reason: str | None  # "shell access", "network access", etc.


@dataclass(frozen=True, slots=True)
class DetailedSecurityAnalysis:
    """Full security analysis with per-skill breakdown."""
    
    # Aggregated (existing)
    aggregated_permissions: PermissionScope
    aggregated_risk: RiskAssessment
    
    # Per-skill breakdown (new)
    skill_breakdown: tuple[SkillPermissionBreakdown, ...]
    
    # Highest-risk skill (for quick identification)
    highest_risk_skill: str | None


class PermissionAnalyzer:
    # ... existing methods ...
    
    def analyze_dag_detailed(
        self, 
        dag: SkillGraph
    ) -> DetailedSecurityAnalysis:
        """Analyze DAG with per-skill breakdown."""
        
        breakdown: list[SkillPermissionBreakdown] = []
        total_scope = PermissionScope()
        highest_risk = ("", 0.0)
        
        for skill in dag.execution_order():
            skill_scope = self._extract_permissions(skill)
            skill_risk = self._compute_skill_risk(skill, skill_scope)
            
            breakdown.append(SkillPermissionBreakdown(
                skill_name=skill.name,
                preset=skill.preset,
                permissions=skill_scope,
                risk_contribution=skill_risk.level,
                risk_reason=skill_risk.primary_reason,
            ))
            
            if skill_risk.score > highest_risk[1]:
                highest_risk = (skill.name, skill_risk.score)
            
            total_scope = self._merge_scopes(total_scope, skill_scope)
        
        return DetailedSecurityAnalysis(
            aggregated_permissions=total_scope,
            aggregated_risk=self._compute_risk(total_scope, []),
            skill_breakdown=tuple(breakdown),
            highest_risk_skill=highest_risk[0] or None,
        )
```

#### TypeScript

```typescript
// studio/src/lib/security-types.ts — ADDITIONS

/** Per-skill permission info for UI display. */
export interface SkillPermissionBreakdown {
  skillName: string;
  preset?: string;
  permissions: PermissionScope;
  riskContribution: 'none' | 'low' | 'medium' | 'high';
  riskReason?: string;
}

/** Extended security approval with breakdown. */
export interface SecurityApprovalDetailed extends SecurityApproval {
  /** Per-skill permission breakdown (for expandable UI). */
  skillBreakdown: SkillPermissionBreakdown[];
  
  /** Skill contributing most to risk (highlighted in UI). */
  highestRiskSkill?: string;
}
```

#### Rust

```rust
// studio/src-tauri/src/security.rs — ADDITIONS

/// Per-skill permission info for UI display.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SkillPermissionBreakdown {
    #[serde(rename = "skillName")]
    pub skill_name: String,
    
    #[serde(skip_serializing_if = "Option::is_none")]
    pub preset: Option<String>,
    
    pub permissions: PermissionScope,
    
    #[serde(rename = "riskContribution")]
    pub risk_contribution: String,
    
    #[serde(skip_serializing_if = "Option::is_none", rename = "riskReason")]
    pub risk_reason: Option<String>,
}

/// Extended security approval with breakdown.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityApprovalDetailed {
    #[serde(flatten)]
    pub base: SecurityApproval,
    
    #[serde(rename = "skillBreakdown")]
    pub skill_breakdown: Vec<SkillPermissionBreakdown>,
    
    #[serde(skip_serializing_if = "Option::is_none", rename = "highestRiskSkill")]
    pub highest_risk_skill: Option<String>,
}
```

---

## UI Components

### SecurityApprovalModal.svelte Updates

```svelte
<!-- SecurityApprovalModal.svelte — UPDATED -->
<script lang="ts">
  import type { SecurityApprovalDetailed, SkillPermissionBreakdown } from '$lib/security-types';
  
  export let approval: SecurityApprovalDetailed;
  
  let showBreakdown = false;
  
  const riskColors = {
    none: 'text-gray-400',
    low: 'text-green-500',
    medium: 'text-yellow-500',
    high: 'text-red-500',
  };
</script>

<div class="modal">
  <div class="header">
    <h2>🔒 Security Review</h2>
    <div class="pipeline-info">
      <span>{approval.dagName}</span>
      <span class="skill-count">{approval.skillBreakdown.length} skills</span>
      <button 
        class="toggle-breakdown"
        onclick={() => showBreakdown = !showBreakdown}
      >
        {showBreakdown ? '▲ Hide' : '▼ Show'} breakdown
      </button>
    </div>
  </div>
  
  {#if showBreakdown}
    <div class="skill-breakdown">
      {#each approval.skillBreakdown as skill, i}
        <div 
          class="skill-row"
          class:highlighted={skill.skillName === approval.highestRiskSkill}
        >
          <div class="skill-header">
            <span class="skill-number">{i + 1}.</span>
            <span class="skill-name">{skill.skillName}</span>
            {#if skill.preset}
              <span class="preset-badge">{skill.preset}</span>
            {/if}
            {#if skill.skillName === approval.highestRiskSkill}
              <span class="highest-risk-badge">⚠️ Highest</span>
            {/if}
          </div>
          
          <div class="permission-icons">
            <span title="Filesystem Read">
              📁 {skill.permissions.filesystemRead.length > 0 ? '✅' : '❌'}
            </span>
            <span title="Filesystem Write">
              ✏️ {skill.permissions.filesystemWrite.length > 0 ? '✅' : '❌'}
            </span>
            <span title="Network">
              🌐 {skill.permissions.networkAllow.length > 0 ? '✅' : '❌'}
            </span>
            <span title="Shell">
              💻 {skill.permissions.shellAllow.length > 0 ? '✅' : '❌'}
            </span>
          </div>
          
          <div class="risk-contribution {riskColors[skill.riskContribution]}">
            {skill.riskContribution.toUpperCase()}
            {#if skill.riskReason}
              <span class="risk-reason">({skill.riskReason})</span>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}
  
  <!-- Aggregated view (always shown) -->
  <div class="aggregated-permissions">
    <!-- ... existing aggregated display ... -->
  </div>
  
  <div class="actions">
    <button class="reject">Reject</button>
    <button class="approve">Approve</button>
  </div>
</div>

<style>
  .skill-row.highlighted {
    background: var(--warning-bg);
    border-left: 3px solid var(--warning-color);
  }
  
  .preset-badge {
    font-size: 0.75rem;
    padding: 0.125rem 0.5rem;
    background: var(--surface-2);
    border-radius: 4px;
    font-family: monospace;
  }
  
  .highest-risk-badge {
    font-size: 0.75rem;
    color: var(--warning-color);
  }
  
  .permission-icons {
    display: flex;
    gap: 0.5rem;
    font-size: 0.875rem;
  }
</style>
```

---

## CLI Output

```bash
$ sunwell security analyze --detailed

📋 Security Analysis: Build Forum App
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SKILL BREAKDOWN:
┌────┬──────────────────────┬─────────────────┬──────┬───────┬─────┬───────┬──────────┐
│ #  │ Skill                │ Preset          │ Read │ Write │ Net │ Shell │ Risk     │
├────┼──────────────────────┼─────────────────┼──────┼───────┼─────┼───────┼──────────┤
│ 1  │ code-exploration     │ read-only       │  ✅  │  ❌   │ ❌  │  ❌   │ none     │
│ 2  │ draft-documentation  │ workspace-write │  ✅  │  ✅   │ ❌  │  ❌   │ low      │
│ 3  │ code-modification    │ workspace-write │  ✅  │  ✅   │ ❌  │  ❌   │ low      │
│ 4  │ test-and-lint        │ safe-shell      │  ✅  │  ✅   │ ❌  │  ✅   │ low ⚠️   │
└────┴──────────────────────┴─────────────────┴──────┴───────┴─────┴───────┴──────────┘

⚠️ Highest risk: test-and-lint (shell access)
   Allowed: python, pytest, ruff, mypy
   Denied:  curl, wget, ssh, sudo, rm -rf

AGGREGATED:
  Filesystem: Read ✅ Write ✅
  Network:    ❌ Denied
  Shell:      ✅ Limited (4 commands)

Risk: LOW ✅
```

---

## Implementation Plan

### Phase 1: Python Backend

1. Add `SkillPermissionBreakdown` dataclass
2. Add `DetailedSecurityAnalysis` dataclass
3. Implement `analyze_dag_detailed()` method
4. Update `sunwell security analyze` CLI to use detailed analysis

### Phase 2: Cross-Language Types

1. Add TypeScript types to `security-types.ts`
2. Add Rust types to `security.rs`
3. Update Tauri command `analyze_dag_permissions` to return detailed

### Phase 3: Studio UI

1. Update `SecurityApprovalModal.svelte` with expandable breakdown
2. Add toggle state and styling
3. Highlight highest-risk skill

### Phase 4: Settings → Security Panel (Log Access)

1. Add "Security" section to Settings page
2. Embed `AuditLogPanel` component
3. Add "Verify Integrity" button
4. Add export functionality

## UI Scalability

### Large DAG Handling

For pipelines with many skills (20+), the expanded breakdown could overwhelm the modal.

1. **Virtualization**: Use `svelte-virtual` or similar for the skill list to maintain 60fps.
2. **Search/Filter**: Add a small filter bar to the breakdown section to find specific skills or filter by risk level (e.g., "Show only HIGH risk").
3. **Summary**: Always keep the "Highest Risk Skill" highlighted and pinned if necessary.

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **UI Spoofing** | User approves a dangerous skill thinking it's safe. | Detailed analysis is computed in the backend and signed/verified before display. |
| **Information Overload** | User ignores the breakdown because it's too long. | Default view remains collapsed; "Highest Risk" is highlighted in the aggregated view. |
| **Truncated Permissions** | Long path lists or many shell commands get cut off. | Use tooltips and "Expand" links for individual permission lists within the row. |

---

## Success Metrics

1. **Transparency**: Users can identify which skill requests what
2. **Debugging**: Time to identify risky skill < 5 seconds
3. **Trust**: Survey shows increased confidence in approval decisions
4. **Adoption**: 80% of approvals use expanded view at least once

---

## Open Questions

### Resolved

| Question | Resolution |
|----------|------------|
| Show per-skill breakdown? | Yes, as expandable section |
| Dedicated log tab? | No, Settings → Security panel |
| Default collapsed or expanded? | Collapsed (show aggregated) |

### Still Open

1. **Can users approve/reject individual skills?**
   - *Proposal*: Not for MVP. All-or-nothing approval.
   - *Future*: Could allow "skip skill X" for optional skills

2. **Should breakdown show in CLI by default?**
   - *Proposal*: No, use `--detailed` flag
   - *Rationale*: Keep default output concise

3. **How to handle very long DAGs (20+ skills)?**
   - *Proposal*: Paginate or virtualize in UI
   - *CLI*: Show first 10, "... and 15 more (use --all)"

---

## References

- **RFC-089**: Security-First Skill Execution — infrastructure
- **RFC-092**: Skill Permission Defaults — presets
- `studio/src/components/security/SecurityApprovalModal.svelte` — existing component
- `studio/src/stores/security.svelte.ts` — security state store
- `src/sunwell/security/analyzer.py` — permission analysis
