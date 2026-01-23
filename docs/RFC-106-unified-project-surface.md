# RFC-106: Unified Project Surface — Consolidating Overview and Progress

**Status**: Implemented  
**Created**: 2026-01-23  
**Last Updated**: 2026-01-23  
**Authors**: Sunwell Team  
**Confidence**: 92% 🟢  
**Supersedes**: Portions of RFC-079 (Project Intent Analyzer) UI design  
**Depends on**:
- RFC-079 (Project Intent Analyzer) — Analysis data model (retained)
- RFC-062 (Frontend Excellence) — Svelte 5 patterns

---

## Summary

Consolidate the **Overview** and **Progress** tabs into a single **unified project surface**. The Overview tab (RFC-079) and Progress tab's IdleState serve the same fundamental purpose—answering "what should I do next?"—but fragment this answer across two tabs, forcing unnecessary navigation.

**The insight**: When a user opens a project, they want ONE place that shows project context AND lets them act. Currently:
- Overview shows analysis but redirects to Progress for input
- Progress (Idle) shows input but lacks analysis depth

**Core change**:

| Before | After |
|--------|-------|
| 7 tabs: Overview, Progress, Pipeline, Memory, Health, State, Workers | 6 tabs: **Project**, Pipeline, Memory, Health, State, Workers |
| Overview = analysis view → redirects to Progress | Project (Idle) = analysis + input unified |
| "Add Goal" → switches tabs | "Add Goal" → stays in place |
| Project understanding split from action | Project understanding enables action |

---

## Goals

1. **Single landing surface** — One tab for "what is this project + what should I do"
2. **Eliminate redirect dance** — No more "click action → switch tab"
3. **Preserve analysis depth** — Keep RFC-079's project type detection, pipeline, suggestions
4. **Maintain state clarity** — Idle/Working/Done/Error states remain distinct
5. **Reduce tab count** — Simpler navigation, less cognitive load

## Non-Goals

1. **Change RFC-079 backend** — Analysis model stays the same
2. **Remove other tabs** — Pipeline, Memory, Health, State, Workers unchanged
3. **Change execution flow** — Working/Done/Error states unchanged
4. **Alter keyboard shortcuts** — Existing shortcuts preserved

---

## Motivation

### The Redirect Dance Problem

Current user flow when opening a project:

```
User opens project
    ↓
Lands on Progress tab (default)
    ↓
Sees IdleState with basic project info
    ↓
Wants richer context → clicks Overview tab
    ↓
Sees project analysis, pipeline, suggestions
    ↓
Clicks "Work on this" or "Add Goal"
    ↓
Gets redirected BACK to Progress tab
    ↓
Enters goal in InputBar
```

This is **4 navigations** for a single conceptual action: "understand project → start work".

### Evidence: Overview Actions Redirect to Progress

```typescript:studio/src/routes/Project.svelte
function handleAddGoal() {
  // Switch to progress tab where user can enter a new goal
  activeTab = ViewTab.PROGRESS;
}

async function handleWorkOnGoal(goalId: string) {
  const goal = project.analysis?.goals.find(g => g.id === goalId);
  if (goal && project.current?.path) {
    await runGoal(goal.title, project.current.path);
    activeTab = ViewTab.PROGRESS;  // ← Redirect
  }
}
```

**Every meaningful action in Overview navigates away from Overview.**

### Information Fragmentation

| Information | Overview | Progress (Idle) |
|-------------|:--------:|:---------------:|
| Project type + confidence | ✅ | ❌ |
| Full goal pipeline | ✅ | ❌ (last run only) |
| Suggested next action | ✅ | ⚠️ (implicit Resume) |
| Detection signals | ✅ | ❌ |
| Project name + path | ⚠️ (in header) | ✅ |
| Briefing panel | ❌ | ✅ |
| Goal input bar | ❌ | ✅ |
| File tree | ❌ | ✅ |
| Quick actions | ✅ | ✅ (duplicated) |
| Dev server button | ✅ | ✅ (duplicated) |

The user must mentally merge two incomplete views.

---

## Design

### Unified IdleState

Merge `ProjectOverview` content into `IdleState`, creating a single comprehensive "project landing" view:

```
┌─────────────────────────────────────────────────────────────────┐
│ my-project                                              [⚙️] [×] │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📁 Code Project (Svelte + Tauri)              92% confident   │
│  ▸ Detection signals (3)                                        │
│                                                                 │
│  ───────────────────────────────────────────────────────────── │
│                                                                 │
│  📋 Pipeline                                        3/7 done   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  ✅ Setup project structure                              │   │
│  │  ✅ Implement core components                            │   │
│  │  ✅ Add DAG visualization                                │   │
│  │  🔄 Fix run command detection  ← current                 │   │
│  │  ⏳ Add project intent analyzer                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  💡 Suggested: Continue "Fix run command detection"            │
│                                                                 │
│  ┌──────────────────┐  ┌─────────────────┐  ┌──────────────┐  │
│  │ ▶ Work on this   │  │ 🖥️ Dev Server   │  │ ↻ Rebuild    │  │
│  └──────────────────┘  └─────────────────┘  └──────────────┘  │
│                                                                 │
│  ───────────────────────────────────────────────────────────── │
│                                                                 │
│  ▾ Last Run: Complete                          2 hours ago     │
│    "Implement authentication flow"                              │
│                                                                 │
│  ───────────────────────────────────────────────────────────── │
│                                                                 │
│  // What would you like to build?                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ describe your goal...                           [Model ▾] │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ▸ Project Files (24)                                          │
│                                                                 │
│  ┌─────────┐ ┌──────────┐ ┌────────┐ ┌────────────┐           │
│  │ ▤ Files │ │ ⊳ Term   │ │ ⊡ Edit │ │ ▶ Preview  │           │
│  └─────────┘ └──────────┘ └────────┘ └────────────┘           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Information Architecture

**Section Order** (top to bottom, progressive disclosure):

1. **Project Identity** — Type badge, confidence, signals (collapsed)
2. **Pipeline** — Current progress toward goals (if any)
3. **Suggested Action** — What to do next with CTA buttons
4. **Last Run Status** — Resume interrupted work (collapsed if complete)
5. **Goal Input** — Text input with provider selector
6. **File Tree** — Browse project (collapsed by default)
7. **Quick Actions** — Files, Terminal, Editor, Preview

### Component Structure

**Decision**: Show skeleton during analysis, then progressively reveal sections. If analysis fails, show goal input immediately (graceful degradation).

```svelte
<!-- IdleState.svelte (unified) -->
<script lang="ts">
  import { project } from '$stores/project.svelte';
  import { ProjectIdentity, PipelineSection, SuggestedAction, LastRunStatus } from './';
  import { AnalysisSkeleton, EmptyPipelineState } from './';
  // ... other imports
</script>

<div class="idle">
  <!-- Section 1: Project Analysis -->
  {#if project.isAnalyzing}
    <AnalysisSkeleton />
  {:else if project.analysis}
    <ProjectIdentity analysis={project.analysis} />
  {/if}
  
  <!-- Section 2: Pipeline -->
  {#if project.isAnalyzing}
    <!-- Skeleton handled above -->
  {:else if project.analysis?.pipeline.length > 0}
    <PipelineSection 
      pipeline={project.analysis.pipeline}
      currentStep={project.analysis.current_step}
      completionPercent={project.analysis.completion_percent}
    />
  {:else if project.analysis}
    <EmptyPipelineState projectType={project.analysis.project_type} />
  {/if}
  
  <!-- Section 3: Suggested Action -->
  {#if project.analysis?.suggested_action}
    <SuggestedAction 
      action={project.analysis.suggested_action}
      devCommand={project.analysis.dev_command}
      onWorkOnGoal={handleWorkOnGoal}
      onStartServer={handleStartServer}
    />
  {/if}
  
  <!-- Section 4: Last Run -->
  {#if projectStatus && projectStatus.status !== 'none'}
    <LastRunStatus status={projectStatus} onResume={handleResume} />
  {/if}
  
  <!-- Section 5: Briefing -->
  {#if hasBriefing()}
    <BriefingPanel />
  {/if}
  
  <!-- Section 6: Goal Input (always visible) -->
  <GoalInputSection onSubmit={handleNewGoal} />
  
  <!-- Section 7: Files (collapsed) -->
  <CollapsibleSection title="Project Files" count={files.length}>
    <FileTree files={projectFiles} onselect={handleFileSelect} />
  </CollapsibleSection>
  
  <!-- Section 8: Quick Actions -->
  <QuickActions 
    onOpenFiles={handleOpenFiles}
    onOpenTerminal={handleOpenTerminal}
    onOpenEditor={handleOpenEditor}
    onPreview={handlePreview}
  />
</div>
```

### Tab Configuration Change

**Decision**: Rename "Progress" → "Project". Rationale: "Progress" implies state change happening; "Project" describes what you're looking at. The tab shows project context regardless of agent state.

```typescript
// Before (7 tabs)
const tabs = [
  { id: 'overview', label: 'Overview' },
  { id: ViewTab.PROGRESS, label: 'Progress' },
  { id: ViewTab.PIPELINE, label: 'Pipeline' },
  { id: ViewTab.MEMORY, label: 'Memory' },
  { id: 'health', label: 'Health' },
  { id: ViewTab.STATE_DAG, label: 'State' },
  { id: ViewTab.WORKERS, label: 'Workers' },
];

// After (6 tabs)
const tabs = [
  { id: ViewTab.PROJECT, label: 'Project' },  // Renamed enum + label
  { id: ViewTab.PIPELINE, label: 'Pipeline' },
  { id: ViewTab.MEMORY, label: 'Memory' },
  { id: 'health', label: 'Health' },
  { id: ViewTab.STATE_DAG, label: 'State' },
  { id: ViewTab.WORKERS, label: 'Workers' },
];
```

**Enum update** (`lib/constants.ts`):
```typescript
export enum ViewTab {
  PROJECT = 'project',    // was PROGRESS = 'progress'
  PIPELINE = 'pipeline',
  MEMORY = 'memory',
  STATE_DAG = 'state',
  WORKERS = 'workers',
}
```

### State Machine (Unchanged)

Project tab content still depends on agent state:

```
agent.isRunning  → WorkingState (unchanged)
agent.isDone     → DoneState (unchanged)
agent.hasError   → ErrorState (unchanged)
else             → IdleState (enhanced with analysis content)
```

### Error Handling

Analysis is **enhancement, not blocker**. If analysis fails:

```svelte
<!-- IdleState.svelte error handling -->
{#if project.isAnalyzing}
  <AnalysisSkeleton />
{:else if project.analysisError}
  <!-- Subtle error, not blocking -->
  <div class="analysis-error">
    <span>⚠️ Analysis unavailable</span>
    <button onclick={() => analyzeProject(project.current?.path, true)}>Retry</button>
  </div>
{:else if project.analysis}
  <ProjectIdentity analysis={project.analysis} />
{/if}

<!-- Goal input ALWAYS visible regardless of analysis state -->
<GoalInputSection onSubmit={handleNewGoal} />
```

**Principle**: User can always enter a goal. Analysis provides context but doesn't gate action.

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Merge direction** | Overview → IdleState | IdleState has input; Overview has analysis. Input is the primary action. |
| **Tab naming** | Rename "Progress" → "Project" | Better reflects unified purpose |
| **Collapsed sections** | Detection signals, File tree | Progressive disclosure; most users don't need these immediately |
| **Action button placement** | After suggested action | CTA near the suggestion |
| **Last run position** | After suggested action | Less prominent than forward-looking pipeline |
| **Analysis loading** | Show skeleton while analyzing | User sees structure immediately |

---

## Detailed Component Specifications

### ProjectIdentity Component

Extracted from `ProjectOverview.svelte` header section:

```svelte
<script lang="ts">
  import type { ProjectAnalysis } from '$lib/types';
  import { getAnalysisTypeEmoji, getAnalysisTypeName } from '$stores/project.svelte';
  
  interface Props {
    analysis: ProjectAnalysis;
  }
  
  let { analysis }: Props = $props();
  
  const typeEmoji = $derived(getAnalysisTypeEmoji(analysis.project_type));
  const typeName = $derived(getAnalysisTypeName(analysis.project_type));
  const confidenceColor = $derived(
    analysis.confidence_level === 'high' ? 'var(--green)' :
    analysis.confidence_level === 'medium' ? 'var(--yellow)' : 'var(--red)'
  );
</script>

<header class="project-identity">
  <div class="type-badge">
    <span class="type-emoji">{typeEmoji}</span>
    <span class="type-name">{typeName} Project</span>
    {#if analysis.project_subtype}
      <span class="subtype">({analysis.project_subtype})</span>
    {/if}
  </div>
  <span class="confidence" style:color={confidenceColor}>
    {Math.round(analysis.confidence * 100)}% confident
  </span>
</header>

{#if analysis.detection_signals.length > 0}
  <details class="signals">
    <summary>Detection signals ({analysis.detection_signals.length})</summary>
    <div class="signal-tags">
      {#each analysis.detection_signals as signal}
        <span class="signal">{signal}</span>
      {/each}
    </div>
  </details>
{/if}
```

### PipelineSection Component

Extracted from `ProjectOverview.svelte` pipeline section:

```svelte
<script lang="ts">
  import type { PipelineStep } from '$lib/types';
  
  interface Props {
    pipeline: PipelineStep[];
    currentStep: string | null;
    completionPercent: number;
  }
  
  let { pipeline, currentStep, completionPercent }: Props = $props();
  
  function getStepIcon(step: PipelineStep): string {
    switch (step.status) {
      case 'completed': return '✅';
      case 'in_progress': return '🔄';
      default: return '⏳';
    }
  }
</script>

<section class="pipeline-section">
  <h3>
    📋 Pipeline
    <span class="completion">{Math.round(completionPercent * 100)}% done</span>
  </h3>
  <div class="pipeline">
    {#each pipeline as step}
      <div class="step" class:current={step.id === currentStep}>
        <span class="step-icon">{getStepIcon(step)}</span>
        <span class="step-title">{step.title}</span>
        {#if step.id === currentStep}
          <span class="current-marker">← current</span>
        {/if}
      </div>
    {/each}
  </div>
</section>
```

### SuggestedAction Component

Extracted from `ProjectOverview.svelte` suggested action section:

```svelte
<script lang="ts">
  import type { SuggestedAction, DevCommand } from '$lib/types';
  import Button from '$components/Button.svelte';
  
  interface Props {
    action: SuggestedAction;
    devCommand: DevCommand | null;
    onWorkOnGoal: (goalId: string) => void;
    onStartServer: (command: string) => void;
  }
  
  let { action, devCommand, onWorkOnGoal, onStartServer }: Props = $props();
</script>

<section class="suggested-action">
  <h3>💡 Suggested</h3>
  <p class="action-description">{action.description}</p>
  {#if action.command}
    <code class="action-command">{action.command}</code>
  {/if}
  
  <div class="action-buttons">
    <Button variant="primary" onclick={() => action.goal_id && onWorkOnGoal(action.goal_id)}>
      ▶ Work on this
    </Button>
    
    {#if devCommand}
      <Button variant="secondary" onclick={() => onStartServer(devCommand.command)}>
        🖥️ Dev Server
      </Button>
    {/if}
  </div>
</section>
```

### LastRunStatus Component

Enhanced from `IdleState.svelte` last-run section:

```svelte
<script lang="ts">
  import type { ProjectStatus } from '$lib/types';
  import Button from '$components/Button.svelte';
  import { formatRelativeTime } from '$lib/format';
  
  interface Props {
    status: ProjectStatus;
    onResume: () => void;
  }
  
  let { status, onResume }: Props = $props();
</script>

<details class="last-run" open={status.status === 'interrupted'}>
  <summary>
    <span class="status-badge" class:interrupted={status.status === 'interrupted'}>
      {#if status.status === 'interrupted'}◐ Interrupted
      {:else if status.status === 'complete'}◆ Last Run Complete
      {:else if status.status === 'failed'}⊗ Last Run Failed
      {/if}
    </span>
    {#if status.last_activity}
      <span class="time">{formatRelativeTime(new Date(status.last_activity))}</span>
    {/if}
  </summary>
  
  <div class="last-run-details">
    {#if status.last_goal}
      <p class="last-goal">"{status.last_goal}"</p>
    {/if}
    {#if status.tasks_completed !== null}
      <p class="progress">{status.tasks_completed}/{status.tasks_total} tasks</p>
    {/if}
    {#if status.status === 'interrupted'}
      <Button variant="primary" size="sm" onclick={onResume}>Resume</Button>
    {/if}
  </div>
</details>
```

### AnalysisSkeleton Component

New component for loading state:

```svelte
<script lang="ts">
  // Pure presentational — no props needed
</script>

<div class="analysis-skeleton" aria-busy="true" aria-label="Analyzing project...">
  <!-- Type badge skeleton -->
  <header class="skeleton-header">
    <div class="skeleton-badge">
      <span class="skeleton-emoji"></span>
      <span class="skeleton-text" style="width: 140px;"></span>
    </div>
    <span class="skeleton-text" style="width: 80px;"></span>
  </header>
  
  <!-- Pipeline skeleton -->
  <section class="skeleton-pipeline">
    <div class="skeleton-title" style="width: 100px;"></div>
    <div class="skeleton-steps">
      {#each Array(3) as _}
        <div class="skeleton-step">
          <span class="skeleton-icon"></span>
          <span class="skeleton-text" style="width: 180px;"></span>
        </div>
      {/each}
    </div>
  </section>
</div>

<style>
  .analysis-skeleton {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    animation: pulse 1.5s ease-in-out infinite;
  }
  
  .skeleton-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .skeleton-badge {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  
  .skeleton-emoji,
  .skeleton-icon {
    width: 20px;
    height: 20px;
    background: var(--bg-tertiary);
    border-radius: var(--radius-sm);
  }
  
  .skeleton-text,
  .skeleton-title {
    height: 16px;
    background: var(--bg-tertiary);
    border-radius: var(--radius-sm);
  }
  
  .skeleton-steps {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding: var(--space-2);
    background: var(--bg-tertiary);
    border-radius: var(--radius-md);
  }
  
  .skeleton-step {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1) 0;
  }
  
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
</style>
```

### EmptyPipelineState Component

New component for projects without goals:

```svelte
<script lang="ts">
  import { getAnalysisTypeName } from '$stores/project.svelte';
  
  interface Props {
    projectType: string;
  }
  
  let { projectType }: Props = $props();
  
  const typeName = $derived(getAnalysisTypeName(projectType).toLowerCase());
</script>

<section class="empty-pipeline">
  <p class="empty-title">📋 No goals yet</p>
  <p class="empty-hint">
    This looks like a {typeName} project. Describe what you'd like to accomplish below.
  </p>
</section>

<style>
  .empty-pipeline {
    text-align: center;
    padding: var(--space-6);
    background: var(--bg-tertiary);
    border-radius: var(--radius-md);
  }
  
  .empty-title {
    margin: 0 0 var(--space-2) 0;
    font-size: var(--text-base);
    color: var(--text-primary);
  }
  
  .empty-hint {
    margin: 0;
    color: var(--text-secondary);
    font-size: var(--text-sm);
  }
</style>
```

### CollapsibleSection Component

Reusable wrapper for progressive disclosure:

```svelte
<script lang="ts">
  import type { Snippet } from 'svelte';
  
  interface Props {
    title: string;
    count?: number;
    open?: boolean;
    children: Snippet;
  }
  
  let { title, count, open = false, children }: Props = $props();
</script>

<details class="collapsible" {open}>
  <summary>
    <span class="title">{title}</span>
    {#if count !== undefined}
      <span class="count">({count})</span>
    {/if}
  </summary>
  <div class="content">
    {@render children()}
  </div>
</details>

<style>
  .collapsible {
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
  }
  
  .collapsible summary {
    padding: var(--space-3);
    cursor: pointer;
    user-select: none;
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--text-secondary);
  }
  
  .collapsible summary:hover {
    background: var(--bg-secondary);
  }
  
  .count {
    color: var(--text-tertiary);
    font-weight: 400;
  }
  
  .content {
    padding: var(--space-3);
    border-top: 1px solid var(--border-color);
  }
</style>
```

---

## Migration Path

### Phase 1: Create New Components (no breaking changes)

1. Create `AnalysisSkeleton.svelte` — loading state
2. Create `EmptyPipelineState.svelte` — no-goals state
3. Create `CollapsibleSection.svelte` — reusable wrapper
4. Create `ProjectIdentity.svelte` — extracted from Overview header
5. Create `PipelineSection.svelte` — extracted from Overview pipeline
6. Create `SuggestedAction.svelte` — extracted from Overview actions
7. Create `LastRunStatus.svelte` — refactored from IdleState

**Test**: All new components independently, Overview still works.

### Phase 2: Enhance IdleState

1. Import new components into `IdleState.svelte`
2. Add `project.analysis` and `project.isAnalyzing` dependencies
3. Compose unified layout with progressive disclosure
4. Handle loading, loaded, and error states

**Test**: IdleState shows analysis when available, skeleton when loading.

### Phase 3: Remove Overview Tab

1. Update `ViewTab` enum: rename `PROGRESS` → `PROJECT`
2. Update tabs array: remove `'overview'`, rename label
3. Move `handleWorkOnGoal`, `handleStartServer` handlers to IdleState context
4. Remove Overview-specific conditional in `Project.svelte`

**Test**: "Project" tab shows unified view, no redirects needed.

### Phase 4: Clean Up

1. Delete `ProjectOverview.svelte`
2. Update `components/project/index.ts` exports
3. Update any tests referencing Overview tab
4. Search for `ViewTab.PROGRESS` references and update

---

## File Changes

| File | Change |
|------|--------|
| `studio/src/components/project/IdleState.svelte` | **Major**: Merge Overview content |
| `studio/src/components/project/ProjectIdentity.svelte` | **New**: Extracted from Overview header |
| `studio/src/components/project/PipelineSection.svelte` | **New**: Extracted from Overview pipeline |
| `studio/src/components/project/SuggestedAction.svelte` | **New**: Extracted from Overview actions |
| `studio/src/components/project/LastRunStatus.svelte` | **New**: Refactored from IdleState |
| `studio/src/components/project/AnalysisSkeleton.svelte` | **New**: Loading state |
| `studio/src/components/project/EmptyPipelineState.svelte` | **New**: No-goals state |
| `studio/src/components/project/CollapsibleSection.svelte` | **New**: Reusable wrapper |
| `studio/src/components/project/ProjectOverview.svelte` | **Delete**: Obsolete |
| `studio/src/components/project/index.ts` | Update exports |
| `studio/src/routes/Project.svelte` | Remove overview tab, rename PROGRESS → PROJECT |
| `studio/src/lib/constants.ts` | Rename `ViewTab.PROGRESS` → `ViewTab.PROJECT` |

---

## Backwards Compatibility

### Breaking Changes

1. **Overview tab removed** — Users expecting separate tab won't find it
2. **Tab order changed** — "Progress" is now "Project" at same position

### Mitigation

1. Tab removal is additive (consolidation), not losing features
2. All functionality preserved, just reorganized
3. No API changes (RFC-079 backend unchanged)

---

## Alternatives Considered

### A: Keep Overview as landing, remove IdleState duplication

**Rejected**: Overview lacks the input bar, which is the primary action. Would require adding InputBar to Overview, effectively duplicating IdleState anyway.

### B: Make Overview the default tab

**Rejected**: Still requires redirect dance. Problem is the split, not the default.

### C: Tabs inside Progress tab (sub-navigation)

**Rejected**: Over-engineering. The states (Idle/Working/Done/Error) already provide natural transitions.

### D: Remove analysis from Progress, keep Overview

**Rejected**: Analysis context is valuable for informed goal input. Users shouldn't have to switch tabs to understand their project before acting.

---

## Success Metrics

1. **Navigation reduction**: 0 tab switches from project open to goal input (was: 2+)
2. **Time to first action**: <5s from project open to goal submission
3. **Feature parity**: 100% of Overview features accessible in new IdleState
4. **User sentiment**: "Everything I need is in one place"

---

## Resolved Decisions

| Question | Decision | Rationale |
|----------|----------|-----------|
| **Tab naming** | "Project" | Describes content, not state. "Progress" implies change happening; "Project" is stable. |
| **Analysis loading** | Skeleton → populate | Show structure immediately (reduces perceived latency). Sections appear as data arrives. |
| **Empty pipeline** | "No goals yet" + project type | Contextual prompt: "This looks like a {type} project. Describe what you'd like to accomplish." |
| **Analysis failure** | Graceful degradation | If analysis fails, show goal input immediately. User can still work; analysis is enhancement, not blocker. |

---

## References

- RFC-079: Project Intent Analyzer
- RFC-062: Frontend Excellence
- RFC-071: Briefing System
- RFC-046: Autonomous Backlog
