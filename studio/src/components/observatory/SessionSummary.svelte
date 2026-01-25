<!--
  SessionSummary — Activity summary for coding session (Svelte 5, RFC-120)
  
  Shows what was accomplished during a session: goals, files, code changes.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  
  interface GoalSummary {
    goal_id: string;
    goal: string;
    status: string;
    source: string;
    started_at: string;
    duration_seconds: number;
    tasks_completed: number;
    tasks_failed: number;
    files_touched: string[];
  }
  
  interface SessionData {
    session_id: string;
    started_at: string;
    ended_at: string | null;
    source: string;
    goals_started: number;
    goals_completed: number;
    goals_failed: number;
    files_created: number;
    files_modified: number;
    files_deleted: number;
    lines_added: number;
    lines_removed: number;
    learnings_added: number;
    dead_ends_recorded: number;
    total_duration_seconds: number;
    top_files: [string, number][];
    goals: GoalSummary[];
  }
  
  interface Props {
    sessionId?: string;
    compact?: boolean;
  }
  
  let { sessionId, compact = false }: Props = $props();
  
  let session = $state<SessionData | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  
  async function loadSession() {
    loading = true;
    error = null;
    
    try {
      const url = sessionId 
        ? `/api/session/summary?session_id=${sessionId}`
        : '/api/session/summary';
      
      const response = await fetch(url);
      const data = await response.json();
      
      if (data.error) {
        error = data.error;
      } else {
        session = data;
      }
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load session';
    } finally {
      loading = false;
    }
  }
  
  function formatDuration(seconds: number): string {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
  }
  
  function formatTime(isoString: string): string {
    return new Date(isoString).toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
    });
  }
  
  function getStatusIcon(status: string): string {
    return status === 'completed' ? '✓' : status === 'failed' ? '✗' : '○';
  }
  
  onMount(() => {
    loadSession();
  });
  
  // Refresh periodically for live session
  $effect(() => {
    if (!sessionId) {
      const interval = setInterval(loadSession, 30000); // Every 30 seconds
      return () => clearInterval(interval);
    }
  });
</script>

<div class="session-summary" class:compact>
  {#if loading}
    <div class="loading">Loading session...</div>
  {:else if error}
    <div class="empty-state">
      <span class="empty-icon">📊</span>
      <span class="empty-text">No session data yet</span>
      <span class="empty-hint">Start working to see activity here</span>
    </div>
  {:else if session}
    <div class="summary-header">
      <div class="duration">
        <span class="duration-value">{formatDuration(session.total_duration_seconds)}</span>
        <span class="duration-label">session</span>
      </div>
      
      <div class="stats-grid">
        <div class="stat">
          <span class="stat-value">{session.goals_completed}</span>
          <span class="stat-label">goals</span>
        </div>
        <div class="stat">
          <span class="stat-value">{session.files_modified + session.files_created}</span>
          <span class="stat-label">files</span>
        </div>
        <div class="stat">
          <span class="stat-value green">+{session.lines_added}</span>
          <span class="stat-label">lines</span>
        </div>
        <div class="stat">
          <span class="stat-value red">-{session.lines_removed}</span>
          <span class="stat-label">lines</span>
        </div>
      </div>
    </div>
    
    {#if !compact}
      {#if session.top_files.length > 0}
        <div class="section">
          <h4>Top Files</h4>
          <div class="top-files">
            {#each session.top_files.slice(0, 5) as [path, count] (path)}
              <div class="file-item">
                <span class="file-path">{path.split('/').pop()}</span>
                <span class="file-count">{count}</span>
              </div>
            {/each}
          </div>
        </div>
      {/if}
      
      {#if session.goals.length > 0}
        <div class="section">
          <h4>Timeline</h4>
          <div class="timeline">
            {#each session.goals.slice(-8) as goal (goal.started_at)}
              <div class="timeline-item" class:completed={goal.status === 'completed'} class:failed={goal.status === 'failed'}>
                <span class="timeline-time">{formatTime(goal.started_at)}</span>
                <span class="timeline-icon">{getStatusIcon(goal.status)}</span>
                <span class="timeline-goal">{goal.goal.slice(0, 40)}{goal.goal.length > 40 ? '...' : ''}</span>
              </div>
            {/each}
          </div>
        </div>
      {/if}
      
      {#if session.learnings_added > 0 || session.dead_ends_recorded > 0}
        <div class="section meta-section">
          <div class="meta-stat">
            <span class="meta-icon">💡</span>
            <span class="meta-value">{session.learnings_added}</span>
            <span class="meta-label">learnings</span>
          </div>
          <div class="meta-stat">
            <span class="meta-icon">🚫</span>
            <span class="meta-value">{session.dead_ends_recorded}</span>
            <span class="meta-label">dead ends</span>
          </div>
        </div>
      {/if}
    {/if}
  {/if}
</div>

<style>
  .session-summary {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    padding: var(--space-4);
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
  }
  
  .session-summary.compact {
    padding: var(--space-3);
    gap: var(--space-2);
  }
  
  .loading {
    text-align: center;
    padding: var(--space-4);
    color: var(--text-muted);
    font-size: var(--text-sm);
  }
  
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-6);
    text-align: center;
  }
  
  .empty-icon {
    font-size: var(--text-2xl);
    opacity: 0.5;
  }
  
  .empty-text {
    font-size: var(--text-sm);
    color: var(--text-secondary);
  }
  
  .empty-hint {
    font-size: var(--text-xs);
    color: var(--text-muted);
  }
  
  .summary-header {
    display: flex;
    align-items: center;
    gap: var(--space-4);
  }
  
  .duration {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: var(--space-3);
    background: var(--bg-primary);
    border-radius: var(--radius-md);
    min-width: 80px;
  }
  
  .duration-value {
    font-family: var(--font-mono);
    font-size: var(--text-xl);
    font-weight: 600;
    color: var(--color-accent);
  }
  
  .duration-label {
    font-size: var(--text-xs);
    color: var(--text-muted);
  }
  
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: var(--space-2);
    flex: 1;
  }
  
  .stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: var(--space-2);
    background: var(--bg-primary);
    border-radius: var(--radius-sm);
  }
  
  .stat-value {
    font-family: var(--font-mono);
    font-size: var(--text-lg);
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .stat-value.green {
    color: var(--color-success);
  }
  
  .stat-value.red {
    color: var(--color-error);
  }
  
  .stat-label {
    font-size: var(--text-xs);
    color: var(--text-muted);
  }
  
  .section {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  
  .section h4 {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 500;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin: 0;
  }
  
  .top-files {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  
  .file-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-1) var(--space-2);
    background: var(--bg-primary);
    border-radius: var(--radius-sm);
  }
  
  .file-path {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-primary);
  }
  
  .file-count {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-muted);
  }
  
  .timeline {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  
  .timeline-item {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1) var(--space-2);
    background: var(--bg-primary);
    border-radius: var(--radius-sm);
    border-left: 2px solid var(--border-primary);
  }
  
  .timeline-item.completed {
    border-left-color: var(--color-success);
  }
  
  .timeline-item.failed {
    border-left-color: var(--color-error);
  }
  
  .timeline-time {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-muted);
    min-width: 3rem;
  }
  
  .timeline-icon {
    font-size: var(--text-xs);
  }
  
  .timeline-item.completed .timeline-icon {
    color: var(--color-success);
  }
  
  .timeline-item.failed .timeline-icon {
    color: var(--color-error);
  }
  
  .timeline-goal {
    font-size: var(--text-sm);
    color: var(--text-primary);
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .meta-section {
    display: flex;
    gap: var(--space-4);
    padding: var(--space-2) 0;
    border-top: 1px solid var(--border-primary);
  }
  
  .meta-stat {
    display: flex;
    align-items: center;
    gap: var(--space-1);
  }
  
  .meta-icon {
    font-size: var(--text-sm);
  }
  
  .meta-value {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .meta-label {
    font-size: var(--text-xs);
    color: var(--text-muted);
  }
</style>
