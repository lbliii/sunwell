<!--
  Progress — Holy Light styled task progress visualization (Svelte 5)
  
  Shows task list with golden progress bars and shimmer effects.
  Running tasks glow with the signature gold pulse.
-->
<script lang="ts">
  import { TaskStatus } from '$lib/constants';
  import type { Task } from '$lib/types';
  import RisingMotes from './RisingMotes.svelte';
  import Spinner from './ui/Spinner.svelte';
  
  interface Props {
    tasks?: Task[];
    currentIndex?: number;
    showAll?: boolean;
    totalExpected?: number;
    showMotes?: boolean;
  }
  
  let { 
    tasks = [], 
    currentIndex = -1, 
    showAll = true, 
    totalExpected = 0, 
    showMotes = false 
  }: Props = $props();
  
  function getStatusIcon(status: Task['status']): string {
    switch (status) {
      case TaskStatus.COMPLETE: return '◆';
      case TaskStatus.FAILED: return '⊗';
      case TaskStatus.RUNNING: return ''; // Spinner component handles this
      default: return '○';
    }
  }
  
  function getStatusClass(status: Task['status']): string {
    return status;
  }
  
  // Calculate placeholder count for tasks we expect but haven't received
  let placeholderCount = $derived(Math.max(0, totalExpected - tasks.length));
  let placeholders = $derived(
    Array(placeholderCount).fill(null).map((_, i) => ({
      index: tasks.length + i,
    }))
  );
  
  let visibleTasks = $derived(showAll ? tasks : tasks.slice(0, 8));
  let visiblePlaceholders = $derived(
    showAll ? placeholders : placeholders.slice(0, Math.max(0, 8 - visibleTasks.length))
  );
  let hasMore = $derived(!showAll && (tasks.length + placeholders.length) > 8);
</script>

<div 
  class="progress-container" 
  role="list" 
  aria-label="Task progress"
>
  {#each visibleTasks as task, i}
    {@const isLast = i === tasks.length - 1 && placeholders.length === 0}
    {@const isRunning = task.status === TaskStatus.RUNNING}
    <div 
      class="task-row" 
      class:current={i === currentIndex} 
      class:running={isRunning}
      role="listitem"
      aria-label="{task.description} - {task.status}"
    >
      <span class="task-prefix" aria-hidden="true">
        {#if isLast}└─{:else}├─{/if}
      </span>
      <span class="task-number">[{i + 1}]</span>
      <span class="task-description">{task.description}</span>
      <div 
        class="task-progress" 
        class:running={isRunning}
        role="progressbar"
        aria-valuenow={task.progress}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Progress: {task.progress}%"
      >
        <div 
          class="progress-bar {getStatusClass(task.status)}"
          style="width: {task.progress}%"
        >
          {#if isRunning}
            <div class="shimmer"></div>
          {/if}
        </div>
        {#if showMotes && isRunning}
          <RisingMotes count={4} intensity="subtle" />
        {/if}
      </div>
      <span class="task-status {getStatusClass(task.status)}" aria-hidden="true">
        {#if task.status === TaskStatus.RUNNING}
          <Spinner style="moon" speed={100} />
        {:else}
          {getStatusIcon(task.status)}
        {/if}
      </span>
    </div>
  {/each}
  
  <!-- Placeholder rows for expected tasks not yet received -->
  {#each visiblePlaceholders as placeholder, i}
    {@const isLast = i === visiblePlaceholders.length - 1}
    <div class="task-row placeholder" role="listitem" aria-label="Queued task">
      <span class="task-prefix" aria-hidden="true">
        {#if isLast}└─{:else}├─{/if}
      </span>
      <span class="task-number">[{placeholder.index + 1}]</span>
      <span class="task-description placeholder-text">Queued...</span>
      <div class="task-progress" role="progressbar" aria-valuenow={0} aria-valuemin={0} aria-valuemax={100}>
        <div class="progress-bar"></div>
      </div>
      <span class="task-status" aria-hidden="true">◌</span>
    </div>
  {/each}
  
  {#if hasMore}
    <div class="task-row more" role="listitem">
      <span class="task-prefix" aria-hidden="true">└─</span>
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
  
  .task-row.running {
    color: var(--text-gold);
  }
  
  .task-prefix {
    color: var(--text-tertiary);
    font-size: var(--text-xs);
  }
  
  .task-number {
    color: var(--text-tertiary);
  }
  
  .running .task-number {
    color: var(--ui-gold-soft);
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
    position: relative;
  }
  
  .task-progress.running {
    box-shadow: var(--glow-gold-subtle);
  }
  
  .progress-bar {
    height: 100%;
    background: var(--gradient-progress);
    border-radius: var(--radius-full);
    transition: width var(--transition-slow);
    position: relative;
    overflow: hidden;
  }
  
  .progress-bar.complete {
    background: var(--progress-fill-complete);
  }
  
  .progress-bar.failed {
    background: var(--error);
  }
  
  .progress-bar.running {
    box-shadow: var(--glow-gold-subtle);
  }
  
  /* Shimmer effect for running progress bars */
  .shimmer {
    position: absolute;
    inset: 0;
    background: linear-gradient(
      90deg,
      transparent,
      rgba(255, 255, 255, 0.3),
      transparent
    );
    animation: shimmer 1.5s infinite;
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
    color: var(--ui-gold);
    animation: goldPulse 1s ease-in-out infinite;
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
  
  @keyframes shimmer {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
  }
  
  @keyframes goldPulse {
    0%, 100% { 
      opacity: 1;
      text-shadow: var(--glow-gold-subtle);
    }
    50% { 
      opacity: 0.7;
      text-shadow: var(--glow-gold);
    }
  }
  
  /* Reduced motion */
  @media (prefers-reduced-motion: reduce) {
    .shimmer {
      animation: none;
    }
    
    .task-status.running {
      animation: none;
    }
  }
</style>
