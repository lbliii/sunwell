<!--
  SessionManager — Autonomous session management UI (Mental Models Integration)
  
  Lists all sessions with status, allows resuming paused sessions,
  viewing session details, and deleting old sessions.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import Button from '../Button.svelte';
  import {
    sessionStore,
    loadSessions,
    getSession,
    resumeSession,
    pauseSession,
    deleteSession,
    clearCurrentSession,
    type SessionSummary,
    type SessionDetail,
  } from '../../stores/session.svelte';

  interface Props {
    onSessionResume?: (sessionId: string) => void;
    compact?: boolean;
  }

  let { onSessionResume, compact = false }: Props = $props();

  let statusFilter = $state<string>('all');
  let showDetails = $state(false);
  let deleteConfirm = $state<string | null>(null);

  const filteredSessions = $derived.by(() => {
    if (statusFilter === 'all') return sessionStore.sessions;
    return sessionStore.sessions.filter(s => s.status === statusFilter);
  });

  function formatDate(dateString: string): string {
    const date = new Date(dateString);
    return date.toLocaleString();
  }

  function formatDuration(seconds: number): string {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    return `${Math.round(seconds / 3600)}h ${Math.round((seconds % 3600) / 60)}m`;
  }

  function getStatusClass(status: string): string {
    switch (status) {
      case 'running': return 'status-running';
      case 'paused': return 'status-paused';
      case 'completed': return 'status-completed';
      case 'failed': return 'status-failed';
      default: return '';
    }
  }

  async function handleViewDetails(session: SessionSummary) {
    await getSession(session.sessionId);
    showDetails = true;
  }

  async function handleResume(sessionId: string) {
    await resumeSession(sessionId);
    onSessionResume?.(sessionId);
  }

  async function handlePause(sessionId: string) {
    await pauseSession(sessionId);
  }

  async function handleDelete(sessionId: string) {
    if (deleteConfirm === sessionId) {
      await deleteSession(sessionId);
      deleteConfirm = null;
      if (sessionStore.currentSession?.sessionId === sessionId) {
        showDetails = false;
      }
    } else {
      deleteConfirm = sessionId;
      // Auto-clear confirm after 3 seconds
      setTimeout(() => {
        if (deleteConfirm === sessionId) deleteConfirm = null;
      }, 3000);
    }
  }

  function closeDetails() {
    showDetails = false;
    clearCurrentSession();
  }

  onMount(() => {
    loadSessions();
  });
</script>

<div class="session-manager" class:compact>
  <header class="manager-header">
    <h2 class="manager-title">Autonomous Sessions</h2>
    {#if sessionStore.hasResumable}
      <span class="resumable-badge">{sessionStore.resumableCount} resumable</span>
    {/if}
  </header>

  <div class="manager-controls">
    <select 
      class="status-filter"
      bind:value={statusFilter}
    >
      <option value="all">All Sessions</option>
      <option value="running">Running</option>
      <option value="paused">Paused</option>
      <option value="completed">Completed</option>
      <option value="failed">Failed</option>
    </select>
    <Button variant="ghost" size="sm" onclick={() => loadSessions()} disabled={sessionStore.isLoading}>
      {sessionStore.isLoading ? 'Loading...' : 'Refresh'}
    </Button>
  </div>

  {#if sessionStore.error}
    <div class="manager-error" role="alert">
      {sessionStore.error}
    </div>
  {/if}

  {#if filteredSessions.length === 0}
    <div class="empty-state">
      <p>No sessions found.</p>
      {#if statusFilter !== 'all'}
        <p class="empty-hint">Try changing the filter or run an autonomous session.</p>
      {/if}
    </div>
  {:else}
    <div class="session-list">
      {#each filteredSessions as session (session.sessionId)}
        <div class="session-card">
          <div class="session-header">
            <span class="session-status {getStatusClass(session.status)}">
              {session.status}
            </span>
            <span class="session-date">{formatDate(session.startedAt)}</span>
          </div>

          <div class="session-goals">
            {#each session.goals.slice(0, 2) as goal}
              <span class="goal-tag">{goal}</span>
            {/each}
            {#if session.goals.length > 2}
              <span class="goal-more">+{session.goals.length - 2} more</span>
            {/if}
          </div>

          <div class="session-progress">
            <div class="progress-bar">
              <div 
                class="progress-fill"
                style:width={`${session.opportunitiesTotal > 0 
                  ? (session.opportunitiesCompleted / session.opportunitiesTotal) * 100 
                  : 0}%`}
              ></div>
            </div>
            <span class="progress-text">
              {session.opportunitiesCompleted}/{session.opportunitiesTotal} completed
            </span>
          </div>

          {#if session.projectId || session.workspaceId}
            <div class="session-context">
              {#if session.workspaceId}
                <span class="context-tag workspace">{session.workspaceId}</span>
              {/if}
              {#if session.projectId}
                <span class="context-tag project">{session.projectId}</span>
              {/if}
            </div>
          {/if}

          <div class="session-actions">
            <Button variant="ghost" size="sm" onclick={() => handleViewDetails(session)}>
              Details
            </Button>
            {#if session.status === 'paused' || session.status === 'running'}
              {#if session.status === 'paused'}
                <Button variant="primary" size="sm" onclick={() => handleResume(session.sessionId)}>
                  Resume
                </Button>
              {:else}
                <Button variant="ghost" size="sm" onclick={() => handlePause(session.sessionId)}>
                  Pause
                </Button>
              {/if}
            {/if}
            <Button 
              variant="ghost" 
              size="sm" 
              onclick={() => handleDelete(session.sessionId)}
            >
              {deleteConfirm === session.sessionId ? 'Confirm?' : 'Delete'}
            </Button>
          </div>
        </div>
      {/each}
    </div>
  {/if}

  <!-- Session Details Modal -->
  {#if showDetails && sessionStore.currentSession}
    {@const session = sessionStore.currentSession}
    <div class="details-overlay" onclick={closeDetails} role="presentation">
      <div class="details-modal" onclick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <header class="details-header">
          <h3>Session Details</h3>
          <button class="close-button" onclick={closeDetails} type="button">×</button>
        </header>

        <div class="details-content">
          <div class="detail-row">
            <span class="detail-label">Status</span>
            <span class="session-status {getStatusClass(session.status)}">{session.status}</span>
          </div>

          <div class="detail-row">
            <span class="detail-label">Started</span>
            <span class="detail-value">{formatDate(session.startedAt)}</span>
          </div>

          {#if session.stoppedAt}
            <div class="detail-row">
              <span class="detail-label">Stopped</span>
              <span class="detail-value">{formatDate(session.stoppedAt)}</span>
            </div>
          {/if}

          <div class="detail-row">
            <span class="detail-label">Runtime</span>
            <span class="detail-value">{formatDuration(session.totalRuntimeSeconds)}</span>
          </div>

          {#if session.stopReason}
            <div class="detail-row">
              <span class="detail-label">Stop Reason</span>
              <span class="detail-value">{session.stopReason}</span>
            </div>
          {/if}

          <div class="detail-section">
            <h4>Goals</h4>
            <ul class="goals-list">
              {#each session.goals as goal}
                <li>{goal}</li>
              {/each}
            </ul>
          </div>

          <div class="detail-section">
            <h4>Progress</h4>
            <div class="stats-grid">
              <div class="stat-item">
                <span class="stat-value">{session.opportunitiesCompleted}</span>
                <span class="stat-label">Completed</span>
              </div>
              <div class="stat-item">
                <span class="stat-value">{session.opportunitiesRemaining}</span>
                <span class="stat-label">Remaining</span>
              </div>
              <div class="stat-item">
                <span class="stat-value">{session.proposalsCreated}</span>
                <span class="stat-label">Proposals</span>
              </div>
              <div class="stat-item">
                <span class="stat-value">{session.proposalsAutoApplied}</span>
                <span class="stat-label">Auto-Applied</span>
              </div>
            </div>
          </div>
        </div>

        <footer class="details-footer">
          {#if session.status === 'paused'}
            <Button variant="primary" onclick={() => handleResume(session.sessionId)}>
              Resume Session
            </Button>
          {/if}
          <Button variant="ghost" onclick={closeDetails}>
            Close
          </Button>
        </footer>
      </div>
    </div>
  {/if}
</div>

<style>
  .session-manager {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .session-manager.compact {
    gap: var(--space-2);
  }

  .manager-header {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  .manager-title {
    margin: 0;
    font-size: var(--text-lg);
    font-weight: 600;
    color: var(--text-primary);
  }

  .compact .manager-title {
    font-size: var(--text-base);
  }

  .resumable-badge {
    padding: var(--space-1) var(--space-2);
    background: var(--accent-subtle);
    color: var(--accent);
    border-radius: var(--radius-full);
    font-size: var(--text-xs);
    font-weight: 500;
  }

  .manager-controls {
    display: flex;
    gap: var(--space-2);
    align-items: center;
  }

  .status-filter {
    padding: var(--space-1) var(--space-2);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    background: var(--bg-primary);
    color: var(--text-primary);
    font-size: var(--text-sm);
  }

  .manager-error {
    padding: var(--space-2) var(--space-3);
    background: var(--error-bg);
    color: var(--error);
    border-radius: var(--radius-md);
    font-size: var(--text-sm);
  }

  .empty-state {
    padding: var(--space-6);
    text-align: center;
    color: var(--text-secondary);
  }

  .empty-hint {
    font-size: var(--text-sm);
    color: var(--text-tertiary);
  }

  .session-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .session-card {
    padding: var(--space-3);
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .session-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .session-status {
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-full);
    font-size: var(--text-xs);
    font-weight: 500;
    text-transform: capitalize;
  }

  .status-running {
    background: var(--success-bg);
    color: var(--success);
  }

  .status-paused {
    background: var(--warning-bg);
    color: var(--warning);
  }

  .status-completed {
    background: var(--accent-subtle);
    color: var(--accent);
  }

  .status-failed {
    background: var(--error-bg);
    color: var(--error);
  }

  .session-date {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }

  .session-goals {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
  }

  .goal-tag {
    padding: var(--space-1) var(--space-2);
    background: var(--bg-tertiary);
    border-radius: var(--radius-md);
    font-size: var(--text-xs);
    color: var(--text-secondary);
  }

  .goal-more {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }

  .session-progress {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .progress-bar {
    flex: 1;
    height: 4px;
    background: var(--bg-tertiary);
    border-radius: var(--radius-full);
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: var(--accent);
    transition: width 0.3s ease;
  }

  .progress-text {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    white-space: nowrap;
  }

  .session-context {
    display: flex;
    gap: var(--space-1);
  }

  .context-tag {
    padding: 2px var(--space-1);
    border-radius: var(--radius-sm);
    font-size: var(--text-xs);
  }

  .context-tag.workspace {
    background: var(--accent-subtle);
    color: var(--accent);
  }

  .context-tag.project {
    background: var(--bg-tertiary);
    color: var(--text-secondary);
  }

  .session-actions {
    display: flex;
    gap: var(--space-1);
    justify-content: flex-end;
  }

  /* Details Modal */
  .details-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
  }

  .details-modal {
    width: 90%;
    max-width: 500px;
    max-height: 80vh;
    background: var(--bg-primary);
    border-radius: var(--radius-xl);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .details-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-4);
    border-bottom: 1px solid var(--border-color);
  }

  .details-header h3 {
    margin: 0;
    font-size: var(--text-lg);
    font-weight: 600;
  }

  .close-button {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: none;
    border: none;
    border-radius: var(--radius-md);
    font-size: var(--text-xl);
    color: var(--text-tertiary);
    cursor: pointer;
  }

  .close-button:hover {
    background: var(--bg-secondary);
    color: var(--text-primary);
  }

  .details-content {
    padding: var(--space-4);
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .detail-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .detail-label {
    font-size: var(--text-sm);
    color: var(--text-secondary);
  }

  .detail-value {
    font-size: var(--text-sm);
    color: var(--text-primary);
  }

  .detail-section h4 {
    margin: 0 0 var(--space-2) 0;
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--text-secondary);
  }

  .goals-list {
    margin: 0;
    padding-left: var(--space-4);
    font-size: var(--text-sm);
    color: var(--text-primary);
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-3);
  }

  .stat-item {
    text-align: center;
    padding: var(--space-2);
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
  }

  .stat-value {
    display: block;
    font-size: var(--text-xl);
    font-weight: 600;
    color: var(--text-primary);
  }

  .stat-label {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }

  .details-footer {
    display: flex;
    gap: var(--space-2);
    justify-content: flex-end;
    padding: var(--space-4);
    border-top: 1px solid var(--border-color);
  }
</style>
