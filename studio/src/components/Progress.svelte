<!--
  Progress — Task progress visualization
  
  Shows task list with progress bars, matching the RFC mockups.
-->
<script lang="ts">
  import type { Task } from '$lib/types';
  
  export let tasks: Task[] = [];
  export let currentIndex = -1;
  export let showAll = true;
  
  function getStatusIcon(status: Task['status']): string {
    switch (status) {
      case 'complete': return '✓';
      case 'failed': return '✗';
      case 'running': return '•';
      default: return '○';
    }
  }
  
  function getStatusClass(status: Task['status']): string {
    return status;
  }
  
  $: visibleTasks = showAll ? tasks : tasks.slice(0, 8);
  $: hasMore = !showAll && tasks.length > 8;
</script>

<div class="progress-container">
  {#each visibleTasks as task, i}
    <div class="task-row" class:current={i === currentIndex}>
      <span class="task-prefix">
        {#if i === currentIndex}├─{:else if i === tasks.length - 1}└─{:else}├─{/if}
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
  
  {#if hasMore}
    <div class="task-row more">
      <span class="task-prefix">└─</span>
      <span class="task-description">... {tasks.length - 8} more</span>
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
  
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
</style>
