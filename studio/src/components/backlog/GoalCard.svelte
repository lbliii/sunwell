<!--
  GoalCard — Individual goal card for Backlog panel (RFC-114)
  
  Displays goal status, priority, category, and controls for run/remove/skip.
  RFC-115: Shows goal_type indicator (epic/milestone/task)
-->
<script lang="ts">
  import type { Goal, GoalType } from '../../stores/backlog.svelte';
  import {
    getCategoryInfo,
    getComplexityInfo,
    getPriorityLevel,
    removeGoal,
    skipGoal,
    updateGoalPriority,
  } from '../../stores/backlog.svelte';

  interface Props {
    goal: Goal;
    index: number;
    onRun?: (goal: Goal) => void;
    draggable?: boolean;
  }

  let { goal, index, onRun, draggable = true }: Props = $props();

  let categoryInfo = $derived(getCategoryInfo(goal.category));
  let complexityInfo = $derived(getComplexityInfo(goal.estimated_complexity));
  let priorityLevel = $derived(getPriorityLevel(goal.priority));

  // RFC-115: Goal type helpers
  let goalType = $derived<GoalType>(goal.goal_type ?? 'task');
  let isEpic = $derived(goalType === 'epic');
  let isMilestone = $derived(goalType === 'milestone');
  let isTask = $derived(goalType === 'task');
  
  function getGoalTypeInfo(type: GoalType): { emoji: string; label: string; color: string } {
    const typeMap: Record<GoalType, { emoji: string; label: string; color: string }> = {
      epic: { emoji: '🎯', label: 'Epic', color: 'var(--accent)' },
      milestone: { emoji: '🏁', label: 'Milestone', color: 'var(--success)' },
      task: { emoji: '📋', label: 'Task', color: 'var(--text-tertiary)' },
    };
    return typeMap[type];
  }
  
  let goalTypeInfo = $derived(getGoalTypeInfo(goalType));

  let isExecuting = $derived(goal.status === 'executing' || goal.status === 'claimed');
  let isCompleted = $derived(goal.status === 'completed');
  let isBlocked = $derived(goal.status === 'blocked');
  let isPending = $derived(goal.status === 'pending');
  let isSkipped = $derived(goal.status === 'skipped');

  let isDeleting = $state(false);
  let showPrioritySlider = $state(false);
  let priorityOverride = $state<number | null>(null);
  
  // Use override when editing, otherwise use goal's actual priority
  let localPriority = $derived(priorityOverride ?? goal.priority);

  function handlePriorityChange(newPriority: number) {
    priorityOverride = newPriority;
  }

  async function handlePriorityCommit() {
    if (priorityOverride !== null && priorityOverride !== goal.priority) {
      try {
        await updateGoalPriority(goal.id, priorityOverride);
      } catch (e) {
        console.error('Failed to update priority:', e);
      }
    }
    priorityOverride = null;
    showPrioritySlider = false;
  }

  async function handleRemove() {
    if (isDeleting) return;
    isDeleting = true;
    try {
      await removeGoal(goal.id);
    } catch (e) {
      console.error('Failed to remove goal:', e);
    } finally {
      isDeleting = false;
    }
  }

  async function handleSkip() {
    try {
      await skipGoal(goal.id);
    } catch (e) {
      console.error('Failed to skip goal:', e);
    }
  }

  function handleRun() {
    onRun?.(goal);
  }
</script>

<div
  class="goal-card"
  class:executing={isExecuting}
  class:completed={isCompleted}
  class:blocked={isBlocked}
  class:skipped={isSkipped}
  class:epic={isEpic}
  class:milestone={isMilestone}
  class:draggable
  role="listitem"
>
  <!-- Drag Handle + Index -->
  {#if draggable && isPending && isTask}
    <div class="drag-handle" title="Drag to reorder">
      <span class="handle-icon">≡</span>
    </div>
  {/if}

  <div class="card-content">
    <!-- Header: Title + Priority -->
    <div class="card-header">
      <div class="goal-title">
        {#if isCompleted}
          <span class="status-icon">✓</span>
        {:else if isEpic || isMilestone}
          <span class="type-icon" style="color: {goalTypeInfo.color}">{goalTypeInfo.emoji}</span>
        {/if}
        {#if isTask}
          <span class="index">{index + 1}.</span>
        {/if}
        <span class="title" title={goal.title}>{goal.title}</span>
      </div>
      {#if showPrioritySlider && isPending}
        <div class="priority-editor">
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={localPriority}
            oninput={(e) => handlePriorityChange(parseFloat(e.currentTarget.value))}
            onchange={handlePriorityCommit}
            onblur={handlePriorityCommit}
            class="priority-slider"
          />
          <span class="priority-value">{Math.round(localPriority * 100)}%</span>
        </div>
      {:else}
        <button
          class="priority-badge"
          class:high={priorityLevel === 'high'}
          class:medium={priorityLevel === 'medium'}
          class:low={priorityLevel === 'low'}
          class:clickable={isPending}
          onclick={() => isPending && (showPrioritySlider = true)}
          disabled={!isPending}
          title={isPending ? 'Click to adjust priority' : ''}
        >
          <span class="priority-dot"></span>
          {priorityLevel.charAt(0).toUpperCase() + priorityLevel.slice(1)}
        </button>
      {/if}
    </div>

    <!-- Description (if blocked, show dependency) -->
    {#if isBlocked && goal.requires.length > 0}
      <div class="blocked-info">
        <span class="blocked-icon">⏳</span>
        Blocked by: {goal.requires.join(', ')}
      </div>
    {:else if goal.description && goal.description !== goal.title}
      <div class="description">{goal.description}</div>
    {/if}

    <!-- Executing progress -->
    {#if isExecuting}
      <div class="executing-info">
        <span class="executing-icon">🔄</span>
        {#if goal.claimed_by !== undefined}
          Worker {goal.claimed_by}
        {:else}
          Running...
        {/if}
      </div>
    {/if}

    <!-- RFC-115: Milestone produces -->
    {#if isMilestone && goal.milestone_produces && goal.milestone_produces.length > 0}
      <div class="produces-info">
        <span class="produces-label">Produces:</span>
        <span class="produces-list">
          {goal.milestone_produces.slice(0, 4).join(', ')}
          {#if goal.milestone_produces.length > 4}
            <span class="more">+{goal.milestone_produces.length - 4} more</span>
          {/if}
        </span>
      </div>
    {/if}

    <!-- Meta: Category + Complexity + Auto-approve + Goal Type -->
    <div class="card-meta">
      {#if isEpic || isMilestone}
        <span class="meta-tag goal-type" style="color: {goalTypeInfo.color}">
          {goalTypeInfo.emoji} {goalTypeInfo.label}
        </span>
      {/if}
      <span class="meta-tag category" style="color: {categoryInfo.color}">
        {categoryInfo.emoji} {categoryInfo.label}
      </span>
      <span class="meta-tag complexity" style="color: {complexityInfo.color}">
        {complexityInfo.emoji} {complexityInfo.label}
      </span>
      {#if goal.auto_approvable}
        <span class="meta-tag auto-approve" title="Can be auto-approved">
          ⚡ Auto
        </span>
      {/if}
    </div>

    <!-- Actions -->
    {#if !isCompleted && !isExecuting}
      <div class="card-actions">
        {#if isPending && onRun}
          <button
            class="action-btn run"
            onclick={handleRun}
            title="Run this goal now"
          >
            ▶
          </button>
        {/if}
        {#if isPending}
          <button
            class="action-btn skip"
            onclick={handleSkip}
            title="Skip this goal"
          >
            ⏭
          </button>
        {/if}
        <button
          class="action-btn remove"
          onclick={handleRemove}
          disabled={isDeleting}
          title="Remove from backlog"
        >
          ✕
        </button>
      </div>
    {/if}
  </div>
</div>

<style>
  .goal-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 14px 16px;
    display: flex;
    gap: 12px;
    transition: all 0.2s ease;
    position: relative;
  }

  .goal-card:hover {
    border-color: var(--text-tertiary);
    background: var(--bg-tertiary);
  }

  .goal-card.executing {
    border-color: var(--success);
    background: color-mix(in srgb, var(--success) 5%, var(--bg-secondary));
  }

  .goal-card.completed {
    opacity: 0.7;
    background: color-mix(in srgb, var(--success) 3%, var(--bg-secondary));
  }

  .goal-card.blocked {
    border-color: var(--warning);
    background: color-mix(in srgb, var(--warning) 5%, var(--bg-secondary));
  }

  .goal-card.skipped {
    opacity: 0.6;
    text-decoration: line-through;
  }

  /* RFC-115: Epic and Milestone styles */
  .goal-card.epic {
    border-color: var(--accent);
    border-width: 2px;
    background: color-mix(in srgb, var(--accent) 5%, var(--bg-secondary));
  }

  .goal-card.milestone {
    border-color: var(--success);
    border-left-width: 4px;
    background: color-mix(in srgb, var(--success) 3%, var(--bg-secondary));
  }

  .goal-card.draggable {
    cursor: grab;
  }

  .goal-card.draggable:active {
    cursor: grabbing;
  }

  .drag-handle {
    display: flex;
    align-items: center;
    color: var(--text-tertiary);
    font-size: 16px;
    padding-right: 4px;
    cursor: grab;
    user-select: none;
  }

  .drag-handle:hover {
    color: var(--text-secondary);
  }

  .handle-icon {
    opacity: 0.5;
  }

  .card-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-width: 0;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
  }

  .goal-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 14px;
    font-weight: 500;
    color: var(--text-primary);
    min-width: 0;
  }

  .status-icon {
    color: var(--success);
    font-size: 12px;
  }

  .type-icon {
    font-size: 14px;
    flex-shrink: 0;
  }

  .index {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-tertiary);
    min-width: 20px;
  }

  .title {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .priority-badge {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    font-weight: 500;
    padding: 3px 8px;
    border-radius: 12px;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .priority-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
  }

  .priority-badge.high {
    color: var(--error);
    background: color-mix(in srgb, var(--error) 15%, transparent);
  }

  .priority-badge.medium {
    color: var(--warning);
    background: color-mix(in srgb, var(--warning) 15%, transparent);
  }

  .priority-badge.low {
    color: var(--text-tertiary);
    background: var(--bg-tertiary);
  }

  .priority-badge.clickable {
    cursor: pointer;
    border: none;
    font-family: inherit;
    transition: all 0.15s ease;
  }

  .priority-badge.clickable:hover {
    filter: brightness(1.1);
    transform: scale(1.02);
  }

  .priority-badge:disabled {
    cursor: default;
  }

  .priority-editor {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 8px;
    background: var(--bg-tertiary);
    border-radius: 8px;
  }

  .priority-slider {
    width: 80px;
    height: 4px;
    -webkit-appearance: none;
    appearance: none;
    background: var(--border-color);
    border-radius: 2px;
    outline: none;
    cursor: pointer;
  }

  .priority-slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 14px;
    height: 14px;
    background: var(--accent);
    border-radius: 50%;
    cursor: pointer;
  }

  .priority-slider::-moz-range-thumb {
    width: 14px;
    height: 14px;
    background: var(--accent);
    border-radius: 50%;
    border: none;
    cursor: pointer;
  }

  .priority-value {
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 500;
    color: var(--text-secondary);
    min-width: 32px;
  }

  .blocked-info {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--warning);
    padding: 4px 8px;
    background: color-mix(in srgb, var(--warning) 10%, transparent);
    border-radius: 6px;
  }

  .blocked-icon {
    font-size: 10px;
  }

  .executing-info {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--success);
    padding: 4px 8px;
    background: color-mix(in srgb, var(--success) 10%, transparent);
    border-radius: 6px;
  }

  .executing-icon {
    font-size: 10px;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  .description {
    font-size: 12px;
    color: var(--text-secondary);
    line-height: 1.4;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  /* RFC-115: Milestone produces */
  .produces-info {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    font-size: 11px;
    padding: 4px 8px;
    background: var(--bg-tertiary);
    border-radius: 6px;
  }

  .produces-label {
    color: var(--text-tertiary);
  }

  .produces-list {
    color: var(--text-secondary);
  }

  .produces-list .more {
    color: var(--text-tertiary);
    opacity: 0.7;
  }

  .card-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .meta-tag {
    font-size: 11px;
    padding: 2px 6px;
    background: var(--bg-tertiary);
    border-radius: 4px;
    display: flex;
    align-items: center;
    gap: 3px;
  }

  .meta-tag.auto-approve {
    color: var(--accent);
  }

  .meta-tag.goal-type {
    font-weight: 600;
  }

  .card-actions {
    position: absolute;
    top: 12px;
    right: 12px;
    display: flex;
    gap: 4px;
    opacity: 0;
    transition: opacity 0.15s ease;
  }

  .goal-card:hover .card-actions {
    opacity: 1;
  }

  .action-btn {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s ease;
    color: var(--text-secondary);
  }

  .action-btn:hover:not(:disabled) {
    border-color: var(--text-tertiary);
    color: var(--text-primary);
  }

  .action-btn.run:hover {
    border-color: var(--success);
    color: var(--success);
    background: color-mix(in srgb, var(--success) 10%, var(--bg-primary));
  }

  .action-btn.skip:hover {
    border-color: var(--warning);
    color: var(--warning);
  }

  .action-btn.remove:hover {
    border-color: var(--error);
    color: var(--error);
  }

  .action-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
