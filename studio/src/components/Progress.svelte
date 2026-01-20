<!--
  Progress — Task progress visualization
  
  Shows task list with progress bars, matching the RFC mockups.
  Includes placeholders for expected tasks not yet received.
-->
<script lang="ts">
  import type { Task } from '$lib/types';
  
  export let tasks: Task[] = [];
  export let currentIndex = -1;
  export let showAll = true;
  export let totalExpected = 0;
  
  function getStatusIcon(status: Task['status']): string {
    switch (status) {
      case 'complete': return '[ok]';
      case 'failed': return '[x]';
      case 'running': return '[..]';
      default: return '[ ]';
    }
  }
  
  function getStatusClass(status: Task['status']): string {
    return status;
  }
  
  // Calculate placeholder count for tasks we expect but haven't received
  $: placeholderCount = Math.max(0, totalExpected - tasks.length);
  $: placeholders = Array(placeholderCount).fill(null).map((_, i) => ({
    index: tasks.length + i,
  }));
  
  $: visibleTasks = showAll ? tasks : tasks.slice(0, 8);
  $: visiblePlaceholders = showAll ? placeholders : placeholders.slice(0, Math.max(0, 8 - visibleTasks.length));
  $: hasMore = !showAll && (tasks.length + placeholders.length) > 8;
</script>

<div class="progress-container">
  {#each visibleTasks as task, i}
    {@const isLast = i === tasks.length - 1 && placeholders.length === 0}
    <div class="task-row" class:current={i === currentIndex}>
      <span class="task-prefix">
        {#if isLast}└─{:else}├─{/if}
      </span>
      <span class="task-number">[{i + 1}]</span>
      <span class="task-description">{task.description}</span>
      <div class="task-progress">
        <div 
          class="progress-bar {getStatusClass(task.status)}"
          style="width: {task.progress}%"
        ></div>
      </div>
      <span class="task-status {getStatusClass(task.status)}">
        {getStatusIcon(task.status)}
      </span>
    </div>
  {/each}
  
  <!-- Placeholder rows for expected tasks not yet received -->
  {#each visiblePlaceholders as placeholder, i}
    {@const isLast = i === visiblePlaceholders.length - 1}
    <div class="task-row placeholder">
      <span class="task-prefix">
        {#if isLast}└─{:else}├─{/if}
      </span>
      <span class="task-number">[{placeholder.index + 1}]</span>
      <span class="task-description placeholder-text">Queued...</span>
      <div class="task-progress">
        <div class="progress-bar"></div>
      </div>
      <span class="task-status">○</span>
    </div>
  {/each}
  
  {#if hasMore}
    <div class="task-row more">
      <span class="task-prefix">└─</span>
      <span class="task-description">... {tasks.length + placeholders.length - 8} more</span>
    </div>
  {/if}
</div>

<style>
  .progress-container {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
  }
  
  .task-row {
    display: grid;
    grid-template-columns: 24px 40px 1fr 200px 24px;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1) 0;
    color: var(--text-secondary);
  }
  
  .task-row.current {
    color: var(--text-primary);
  }
  
  .task-prefix {
    color: var(--text-tertiary);
    font-size: var(--text-xs);
  }
  
  .task-number {
    color: var(--text-tertiary);
  }
  
  .task-description {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .task-progress {
    height: var(--progress-height);
    background: var(--progress-bg);
    border-radius: var(--radius-full);
    overflow: hidden;
  }
  
  .progress-bar {
    height: 100%;
    background: var(--progress-fill);
    border-radius: var(--radius-full);
    transition: width var(--transition-slow);
  }
  
  .progress-bar.complete {
    background: var(--progress-fill-complete);
  }
  
  .progress-bar.failed {
    background: var(--error);
  }
  
  .task-status {
    text-align: center;
    font-weight: 500;
  }
  
  .task-status.complete {
    color: var(--success);
  }
  
  .task-status.failed {
    color: var(--error);
  }
  
  .task-status.running {
    color: var(--accent);
    animation: pulse 1s ease-in-out infinite;
  }
  
  .more {
    color: var(--text-tertiary);
  }
  
  .placeholder {
    opacity: 0.5;
  }
  
  .placeholder-text {
    font-style: italic;
    color: var(--text-tertiary);
  }
  
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
</style>
