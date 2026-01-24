<!--
  RunHistory — Show all runs from CLI and Studio (RFC-119)
  
  Displays run history with source badges showing where each run originated.
  Subscribes to global event stream for real-time updates.
-->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { fade, fly } from 'svelte/transition';
  import {
    subscribeToGlobalEvents,
    onGlobalEvent,
    listRuns,
    globalStats,
    type RunInfo,
    type GlobalEvent,
  } from '$lib/socket';

  let runs = $state<RunInfo[]>([]);
  let isLoading = $state(true);
  let error = $state<string | null>(null);
  
  // Cleanup functions
  let cleanupGlobalStream: (() => void) | null = null;
  let cleanupEventListener: (() => void) | null = null;

  onMount(async () => {
    // Load initial runs
    try {
      const result = await listRuns();
      runs = result.runs;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load runs';
    } finally {
      isLoading = false;
    }

    // Subscribe to global event stream
    cleanupGlobalStream = subscribeToGlobalEvents();

    // Listen for run updates
    cleanupEventListener = onGlobalEvent((event: GlobalEvent) => {
      // Update run list when we see relevant events
      if (event.type === 'task_start' || event.type === 'complete' || event.type === 'error') {
        updateRunFromEvent(event);
      }
    });
  });

  onDestroy(() => {
    cleanupGlobalStream?.();
    cleanupEventListener?.();
  });

  function updateRunFromEvent(event: GlobalEvent) {
    const existingIndex = runs.findIndex(r => r.run_id === event.run_id);
    
    if (existingIndex >= 0) {
      // Update existing run
      runs = runs.map((r, i) => {
        if (i !== existingIndex) return r;
        return {
          ...r,
          status: event.type === 'complete' ? 'complete' : 
                  event.type === 'error' ? 'error' : 'running',
          event_count: r.event_count + 1,
        };
      });
    } else if (event.type === 'task_start') {
      // New run detected - add to list
      const newRun: RunInfo = {
        run_id: event.run_id,
        goal: (event.data.goal as string) || 'Unknown goal',
        status: 'running',
        source: event.source,
        started_at: event.timestamp,
        completed_at: null,
        event_count: 1,
      };
      runs = [newRun, ...runs];
    }
  }

  function getSourceBadge(source: string): { icon: string; label: string; class: string } {
    switch (source) {
      case 'cli':
        return { icon: '⌨️', label: 'CLI', class: 'source-cli' };
      case 'studio':
        return { icon: '🖥️', label: 'Studio', class: 'source-studio' };
      case 'api':
        return { icon: '🔌', label: 'API', class: 'source-api' };
      default:
        return { icon: '❓', label: source, class: 'source-unknown' };
    }
  }

  function getStatusBadge(status: string): { icon: string; class: string } {
    switch (status) {
      case 'running':
        return { icon: '⚡', class: 'status-running' };
      case 'complete':
        return { icon: '✅', class: 'status-complete' };
      case 'error':
        return { icon: '❌', class: 'status-error' };
      case 'cancelled':
        return { icon: '⏹️', class: 'status-cancelled' };
      case 'pending':
        return { icon: '⏳', class: 'status-pending' };
      default:
        return { icon: '❓', class: 'status-unknown' };
    }
  }

  function formatTime(timestamp: string): string {
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function formatRelativeTime(timestamp: string): string {
    const now = Date.now();
    const then = new Date(timestamp).getTime();
    const diffSeconds = Math.floor((now - then) / 1000);
    
    if (diffSeconds < 60) return 'just now';
    if (diffSeconds < 3600) return `${Math.floor(diffSeconds / 60)}m ago`;
    if (diffSeconds < 86400) return `${Math.floor(diffSeconds / 3600)}h ago`;
    return `${Math.floor(diffSeconds / 86400)}d ago`;
  }
</script>

<div class="run-history" in:fade={{ duration: 200 }}>
  <header class="header">
    <h2 class="title">🏃 Run History</h2>
    <div class="connection-status" class:connected={globalStats.connected}>
      <span class="status-dot"></span>
      <span class="status-label">{globalStats.connected ? 'Live' : 'Offline'}</span>
    </div>
  </header>

  {#if isLoading}
    <div class="loading">
      <span class="spinner">⏳</span>
      <span>Loading runs...</span>
    </div>
  {:else if error}
    <div class="error">
      <span class="error-icon">⚠️</span>
      <span>{error}</span>
    </div>
  {:else if runs.length === 0}
    <div class="empty">
      <span class="empty-icon">📭</span>
      <span class="empty-text">No runs yet</span>
      <span class="empty-hint">Start a run from CLI or Studio</span>
    </div>
  {:else}
    <ul class="run-list">
      {#each runs as run, i (run.run_id)}
        {@const source = getSourceBadge(run.source)}
        {@const status = getStatusBadge(run.status)}
        <li 
          class="run-item" 
          class:running={run.status === 'running'}
          in:fly={{ y: 20, delay: i * 30, duration: 200 }}
        >
          <div class="run-header">
            <span class="source-badge {source.class}" title="Source: {source.label}">
              {source.icon} {source.label}
            </span>
            <span class="status-badge {status.class}" title="Status: {run.status}">
              {status.icon}
            </span>
          </div>
          
          <div class="run-goal" title={run.goal}>
            {run.goal.length > 50 ? run.goal.slice(0, 50) + '...' : run.goal}
          </div>
          
          <div class="run-meta">
            <span class="run-time" title={run.started_at}>
              {formatRelativeTime(run.started_at)}
            </span>
            <span class="run-events">
              {run.event_count} events
            </span>
          </div>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .run-history {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: var(--bg-secondary);
    border-radius: var(--radius-lg);
    overflow: hidden;
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-4);
    border-bottom: 1px solid var(--border-subtle);
  }

  .title {
    font-family: var(--font-serif);
    font-size: var(--text-lg);
    color: var(--text-primary);
    margin: 0;
  }

  .connection-status {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }

  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--text-tertiary);
    transition: all var(--transition-fast);
  }

  .connection-status.connected .status-dot {
    background: var(--success);
    box-shadow: 0 0 8px var(--success);
    animation: pulse 2s ease-in-out infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
  }

  .loading,
  .error,
  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: var(--space-8);
    gap: var(--space-2);
    color: var(--text-tertiary);
    font-family: var(--font-mono);
  }

  .spinner {
    font-size: var(--text-2xl);
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  .error {
    color: var(--error);
  }

  .error-icon {
    font-size: var(--text-2xl);
  }

  .empty-icon {
    font-size: var(--text-3xl);
  }

  .empty-text {
    font-size: var(--text-sm);
    color: var(--text-secondary);
  }

  .empty-hint {
    font-size: var(--text-xs);
  }

  .run-list {
    list-style: none;
    margin: 0;
    padding: 0;
    overflow-y: auto;
    flex: 1;
  }

  .run-item {
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--border-subtle);
    transition: background var(--transition-fast);
  }

  .run-item:hover {
    background: var(--bg-tertiary);
  }

  .run-item.running {
    background: linear-gradient(
      90deg,
      transparent,
      var(--ui-gold-10) 50%,
      transparent
    );
    background-size: 200% 100%;
    animation: shimmer 2s linear infinite;
  }

  @keyframes shimmer {
    from { background-position: 100% 0; }
    to { background-position: -100% 0; }
  }

  .run-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-1);
  }

  .source-badge {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    padding: 2px var(--space-2);
    border-radius: var(--radius-sm);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
  }

  .source-cli {
    background: var(--ui-gold-15);
    color: var(--text-gold);
    border: 1px solid var(--ui-gold-40);
  }

  .source-studio {
    background: rgba(99, 102, 241, 0.15);
    color: #818cf8;
    border: 1px solid rgba(99, 102, 241, 0.4);
  }

  .source-api {
    background: rgba(34, 197, 94, 0.15);
    color: #4ade80;
    border: 1px solid rgba(34, 197, 94, 0.4);
  }

  .source-unknown {
    background: var(--bg-tertiary);
    color: var(--text-tertiary);
    border: 1px solid var(--border-subtle);
  }

  .status-badge {
    font-size: var(--text-sm);
  }

  .status-running {
    animation: pulse-status 1s ease-in-out infinite;
  }

  @keyframes pulse-status {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }

  .run-goal {
    font-size: var(--text-sm);
    color: var(--text-primary);
    margin-bottom: var(--space-1);
    line-height: 1.4;
  }

  .run-meta {
    display: flex;
    gap: var(--space-3);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
</style>
