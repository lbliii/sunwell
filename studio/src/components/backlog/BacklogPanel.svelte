<!--
  BacklogPanel — Main container for goal queue management (RFC-114)
  
  Unified view showing:
  - Epic progress (RFC-115 hierarchy) when active
  - Goal queue with drag-to-reorder
  - Add goal form (single + batch)
  - Dependency graph visualization
  - Status filtering
  - Refresh from signals
-->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import type { Goal } from '../../stores/backlog.svelte';
  import {
    backlogStore,
    setBacklogProjectPath,
    loadBacklog,
    startBacklogPolling,
    stopBacklogPolling,
    reorderGoals,
    refreshBacklog,
  } from '../../stores/backlog.svelte';
  import { apiPost } from '$lib/socket';
  import GoalCard from './GoalCard.svelte';
  import GoalForm from './GoalForm.svelte';
  import BatchAddForm from './BatchAddForm.svelte';
  import DependencyGraph from './DependencyGraph.svelte';
  import EpicProgress from './EpicProgress.svelte';

  interface Props {
    projectPath: string;
    onRunGoal?: (goal: Goal) => void;
  }

  let { projectPath, onRunGoal }: Props = $props();

  // Local state
  let showAddForm = $state(false);
  let showBatchForm = $state(false);
  let showCompleted = $state(false);
  let showDependencyGraph = $state(false);
  let showHierarchy = $state(true); // RFC-115: Show hierarchy view by default
  let isRefreshing = $state(false);
  let isRunningGoal = $state<string | null>(null);
  let draggedIndex = $state<number | null>(null);
  let dropTargetIndex = $state<number | null>(null);

  // RFC-115: Hierarchy-aware computed values
  let hasActiveEpic = $derived(backlogStore.hasActiveEpic);
  let epicProgress = $derived(backlogStore.epicProgress);
  
  // Filter goals based on hierarchy mode
  let displayedGoals = $derived.by(() => {
    const allGoals = showCompleted
      ? backlogStore.goals
      : backlogStore.goals.filter((g) => g.status !== 'completed' && g.status !== 'skipped');
    
    // In hierarchy mode with active epic, only show current milestone tasks
    if (showHierarchy && hasActiveEpic && backlogStore.activeMilestoneId) {
      return allGoals.filter((g) => 
        g.goal_type === 'task' && g.parent_goal_id === backlogStore.activeMilestoneId
      );
    }
    
    // In flat mode or no epic, show all non-epic/milestone goals
    if (!showHierarchy) {
      return allGoals.filter((g) => g.goal_type !== 'epic' && g.goal_type !== 'milestone');
    }
    
    return allGoals;
  });

  let hasGoals = $derived(backlogStore.goals.length > 0);
  let pendingCount = $derived(backlogStore.pendingCount);
  let completedCount = $derived(backlogStore.completedCount);
  
  // Check if any goals have dependencies
  let hasDependencies = $derived(
    backlogStore.goals.some((g) => g.requires.length > 0)
  );

  // RFC-115: Epic/milestone helpers
  let currentMilestoneTitle = $derived(
    epicProgress?.current_milestone_title ?? null
  );

  onMount(() => {
    setBacklogProjectPath(projectPath);
    startBacklogPolling(5000); // Poll every 5 seconds
  });

  onDestroy(() => {
    stopBacklogPolling();
  });

  async function handleRefresh() {
    if (isRefreshing) return;
    isRefreshing = true;
    try {
      await refreshBacklog();
    } catch (e) {
      console.error('Failed to refresh backlog:', e);
    } finally {
      isRefreshing = false;
    }
  }

  async function handleRunGoal(goal: Goal) {
    // First, try the callback if provided
    if (onRunGoal) {
      onRunGoal(goal);
      return;
    }
    
    // Otherwise, run the goal directly via API
    if (isRunningGoal) return;
    isRunningGoal = goal.id;
    
    try {
      // Start a single-goal execution
      await apiPost('/api/run', {
        goal: goal.description || goal.title,
        workspace: projectPath,
      });
      
      // Reload backlog to reflect status change
      await loadBacklog();
    } catch (e) {
      console.error('Failed to run goal:', e);
    } finally {
      isRunningGoal = null;
    }
  }

  // Drag and drop handlers
  function handleDragStart(e: DragEvent, index: number) {
    if (!e.dataTransfer) return;
    draggedIndex = index;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', String(index));
  }

  function handleDragOver(e: DragEvent, index: number) {
    e.preventDefault();
    if (draggedIndex === null || draggedIndex === index) return;
    dropTargetIndex = index;
  }

  function handleDragLeave() {
    dropTargetIndex = null;
  }

  function handleDrop(e: DragEvent, targetIndex: number) {
    e.preventDefault();
    if (draggedIndex === null || draggedIndex === targetIndex) {
      draggedIndex = null;
      dropTargetIndex = null;
      return;
    }

    // Reorder the pending goals
    const pendingGoals = displayedGoals.filter((g) => g.status === 'pending');
    const newOrder = [...pendingGoals.map((g) => g.id)];

    // Get the actual IDs based on visible indices
    const draggedId = pendingGoals[draggedIndex]?.id;
    if (!draggedId) return;

    // Remove from old position and insert at new position
    const oldIndex = newOrder.indexOf(draggedId);
    if (oldIndex !== -1) {
      newOrder.splice(oldIndex, 1);
      newOrder.splice(targetIndex, 0, draggedId);
    }

    // Update backend
    reorderGoals(newOrder);

    draggedIndex = null;
    dropTargetIndex = null;
  }

  function handleDragEnd() {
    draggedIndex = null;
    dropTargetIndex = null;
  }
</script>

<div class="backlog-panel">
  <!-- Header -->
  <header class="panel-header">
    <div class="header-left">
      <h2>📋 Backlog</h2>
      <span class="goal-count">
        {#if hasActiveEpic && currentMilestoneTitle}
          <span class="milestone-badge">🎯 {currentMilestoneTitle}</span>
        {:else}
          {pendingCount} pending
          {#if completedCount > 0}
            • {completedCount} done
          {/if}
        {/if}
      </span>
    </div>
    <div class="header-actions">
      <button
        class="btn icon-btn"
        onclick={handleRefresh}
        disabled={isRefreshing}
        title="Refresh from project signals"
      >
        <span class:spinning={isRefreshing}>🔄</span>
      </button>
      {#if hasActiveEpic}
        <button
          class="btn icon-btn"
          class:active={showHierarchy}
          onclick={() => (showHierarchy = !showHierarchy)}
          title={showHierarchy ? 'Show flat view' : 'Show hierarchy view'}
        >
          {showHierarchy ? '🏗️' : '📋'}
        </button>
      {/if}
      {#if hasDependencies}
        <button
          class="btn icon-btn"
          class:active={showDependencyGraph}
          onclick={() => (showDependencyGraph = !showDependencyGraph)}
          title="Show dependency graph"
        >
          🔗
        </button>
      {/if}
      <div class="add-dropdown">
        <button
          class="btn primary"
          onclick={() => (showAddForm = true)}
        >
          + Add
        </button>
        <button
          class="btn secondary add-more"
          onclick={() => (showBatchForm = true)}
          title="Add multiple goals"
        >
          ⋯
        </button>
      </div>
    </div>
  </header>

  <!-- RFC-115: Epic Progress (when active) -->
  {#if hasActiveEpic && showHierarchy}
    <EpicProgress />
  {/if}

  <!-- Goals List -->
  <div class="goals-container">
    {#if backlogStore.isLoading && !hasGoals}
      <div class="loading-state">
        <div class="spinner"></div>
        <span>Loading backlog...</span>
      </div>
    {:else if !hasGoals}
      <div class="empty-state">
        <div class="empty-icon">📭</div>
        <h3>No goals yet</h3>
        <p>Add your first goal to get started, or refresh to scan for project signals.</p>
        <div class="empty-actions">
          <button class="btn secondary" onclick={handleRefresh} disabled={isRefreshing}>
            🔍 Scan Project
          </button>
          <button class="btn primary" onclick={() => (showAddForm = true)}>
            + Add Goal
          </button>
        </div>
      </div>
    {:else}
      <!-- Dependency Graph (collapsible) -->
      {#if showDependencyGraph && hasDependencies}
        <div class="dependency-section">
          <DependencyGraph goals={backlogStore.goals} />
        </div>
      {/if}

      <!-- Section header for hierarchy mode -->
      {#if hasActiveEpic && showHierarchy && currentMilestoneTitle}
        <div class="milestone-tasks-header">
          <span class="tasks-label">Tasks for: {currentMilestoneTitle}</span>
          <span class="tasks-count">{displayedGoals.length} tasks</span>
        </div>
      {/if}

      <!-- Filter toggle -->
      {#if completedCount > 0 && (!hasActiveEpic || !showHierarchy)}
        <div class="filter-bar">
          <label class="filter-toggle">
            <input type="checkbox" bind:checked={showCompleted} />
            <span>Show completed ({completedCount})</span>
          </label>
        </div>
      {/if}

      <!-- Goals list with drag-drop -->
      <div class="goals-list" role="list">
        {#each displayedGoals as goal, index (goal.id)}
          {@const isPending = goal.status === 'pending'}
          <div
            class="goal-item"
            class:dragging={draggedIndex === index}
            class:drop-target={dropTargetIndex === index}
            role="listitem"
            draggable={isPending}
            ondragstart={(e) => isPending && handleDragStart(e, index)}
            ondragover={(e) => isPending && handleDragOver(e, index)}
            ondragleave={handleDragLeave}
            ondrop={(e) => isPending && handleDrop(e, index)}
            ondragend={handleDragEnd}
          >
            <GoalCard
              {goal}
              {index}
              onRun={handleRunGoal}
              draggable={isPending}
            />
          </div>
        {/each}
      </div>

      <!-- Collapsed completed goals summary -->
      {#if !showCompleted && completedCount > 0 && (!hasActiveEpic || !showHierarchy)}
        <button
          class="completed-summary"
          onclick={() => (showCompleted = true)}
        >
          <span class="check-icon">✅</span>
          <span>{completedCount} completed goal{completedCount > 1 ? 's' : ''}</span>
          <span class="expand-icon">›</span>
        </button>
      {/if}
    {/if}
  </div>

  <!-- Error Banner -->
  {#if backlogStore.error}
    <div class="error-banner">
      ⚠️ {backlogStore.error}
    </div>
  {/if}

  <!-- Add Goal Modal -->
  {#if showAddForm}
    <GoalForm
      onClose={() => (showAddForm = false)}
      onSuccess={() => loadBacklog()}
    />
  {/if}

  <!-- Batch Add Modal -->
  {#if showBatchForm}
    <BatchAddForm
      onClose={() => (showBatchForm = false)}
      onSuccess={() => loadBacklog()}
    />
  {/if}
</div>

<style>
  .backlog-panel {
    display: flex;
    flex-direction: column;
    gap: 16px;
    position: relative;
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .header-left {
    display: flex;
    align-items: baseline;
    gap: 12px;
  }

  .header-left h2 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .goal-count {
    font-size: 12px;
    color: var(--text-tertiary);
  }

  .milestone-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    background: color-mix(in srgb, var(--accent) 15%, transparent);
    color: var(--accent);
    border-radius: 12px;
    font-size: 11px;
    font-weight: 500;
  }

  .milestone-tasks-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    background: var(--bg-tertiary);
    border-radius: 8px;
    margin-bottom: 8px;
  }

  .tasks-label {
    font-size: 12px;
    font-weight: 500;
    color: var(--text-primary);
  }

  .tasks-count {
    font-size: 11px;
    color: var(--text-tertiary);
  }

  .header-actions {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .add-dropdown {
    display: flex;
    gap: 0;
  }

  .add-dropdown .btn.primary {
    border-radius: 8px 0 0 8px;
  }

  .add-dropdown .btn.add-more {
    border-radius: 0 8px 8px 0;
    padding: 8px 10px;
    border-left: none;
  }

  .btn.icon-btn.active {
    background: var(--accent);
    color: var(--bg-primary);
    border-color: var(--accent);
  }

  .btn {
    padding: 8px 14px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .btn.icon-btn {
    padding: 8px 10px;
  }

  .btn.secondary {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    color: var(--text-secondary);
  }

  .btn.secondary:hover:not(:disabled) {
    background: var(--bg-tertiary);
    color: var(--text-primary);
  }

  .btn.primary {
    background: var(--accent);
    border: none;
    color: var(--bg-primary);
  }

  .btn.primary:hover:not(:disabled) {
    filter: brightness(1.1);
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .spinning {
    display: inline-block;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  .goals-container {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .dependency-section {
    margin-bottom: 8px;
  }

  .loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    padding: 48px;
    color: var(--text-tertiary);
  }

  .spinner {
    width: 24px;
    height: 24px;
    border: 2px solid var(--border-color);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  .empty-state {
    text-align: center;
    padding: 48px 24px;
    background: var(--bg-secondary);
    border: 1px dashed var(--border-color);
    border-radius: 12px;
  }

  .empty-icon {
    font-size: 48px;
    margin-bottom: 16px;
  }

  .empty-state h3 {
    margin: 0 0 8px;
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .empty-state p {
    margin: 0 0 20px;
    font-size: 13px;
    color: var(--text-secondary);
  }

  .empty-actions {
    display: flex;
    justify-content: center;
    gap: 12px;
  }

  .filter-bar {
    display: flex;
    align-items: center;
    padding: 8px 0;
  }

  .filter-toggle {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--text-secondary);
    cursor: pointer;
  }

  .filter-toggle input[type="checkbox"] {
    accent-color: var(--accent);
  }

  .goals-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .goal-item {
    transition: transform 0.15s ease, opacity 0.15s ease;
  }

  .goal-item.dragging {
    opacity: 0.5;
    transform: scale(0.98);
  }

  .goal-item.drop-target {
    position: relative;
  }

  .goal-item.drop-target::before {
    content: '';
    position: absolute;
    top: -4px;
    left: 0;
    right: 0;
    height: 2px;
    background: var(--accent);
    border-radius: 1px;
  }

  .completed-summary {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    background: color-mix(in srgb, var(--success) 5%, var(--bg-secondary));
    border: 1px solid var(--border-color);
    border-radius: 8px;
    font-size: 13px;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.15s ease;
    width: 100%;
  }

  .completed-summary:hover {
    background: color-mix(in srgb, var(--success) 10%, var(--bg-secondary));
    border-color: var(--success);
  }

  .check-icon {
    font-size: 14px;
  }

  .expand-icon {
    margin-left: auto;
    font-size: 16px;
    color: var(--text-tertiary);
    transition: transform 0.15s ease;
  }

  .completed-summary:hover .expand-icon {
    transform: rotate(90deg);
    color: var(--success);
  }

  .error-banner {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    padding: 10px 16px;
    background: color-mix(in srgb, var(--error) 15%, var(--bg-secondary));
    border: 1px solid var(--error);
    border-radius: 8px;
    font-size: 13px;
    color: var(--error);
  }
</style>
