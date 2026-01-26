<!--
  ProjectDisambiguator — Choose between multiple projects with same slug (RFC-133 Phase 2)
  
  Shown when a URL slug matches multiple projects (shouldn't happen with proper
  registry management, but provides a safety net).
-->
<script lang="ts">
  interface ProjectCandidate {
    id: string;
    name: string;
    root: string;
    valid: boolean;
    lastUsed: string | null;
  }
  
  interface Props {
    slug: string;
    candidates: ProjectCandidate[];
    onSelect: (project: ProjectCandidate) => void;
    onCancel: () => void;
  }
  
  let { slug, candidates, onSelect, onCancel }: Props = $props();
  
  function formatPath(path: string): string {
    // Truncate long paths
    if (path.length > 50) {
      return '...' + path.slice(-47);
    }
    return path;
  }
  
  function formatLastUsed(lastUsed: string | null): string {
    if (!lastUsed) return 'Never';
    try {
      const date = new Date(lastUsed);
      return date.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
    } catch {
      return 'Unknown';
    }
  }
</script>

<div class="disambiguator">
  <h2 class="title">Multiple Projects Found</h2>
  <p class="message">
    The slug <code>{slug}</code> matches multiple projects. Please select one:
  </p>
  
  <ul class="candidates">
    {#each candidates as project (project.id)}
      <li>
        <button 
          class="candidate"
          class:invalid={!project.valid}
          disabled={!project.valid}
          onclick={() => onSelect(project)}
        >
          <div class="info">
            <strong class="name">{project.name}</strong>
            <span class="path" title={project.root}>{formatPath(project.root)}</span>
            <span class="last-used">Last used: {formatLastUsed(project.lastUsed)}</span>
          </div>
          {#if !project.valid}
            <span class="badge invalid">Unavailable</span>
          {/if}
        </button>
      </li>
    {/each}
  </ul>
  
  <div class="actions">
    <button class="cancel-btn" onclick={onCancel}>Cancel</button>
  </div>
</div>

<style>
  .disambiguator {
    padding: var(--space-4);
    max-width: 500px;
    margin: 0 auto;
  }
  
  .title {
    font-size: var(--text-lg);
    font-weight: 600;
    color: var(--text-primary);
    margin: 0 0 var(--space-2) 0;
  }
  
  .message {
    color: var(--text-secondary);
    margin: 0 0 var(--space-4) 0;
  }
  
  .message code {
    background: var(--bg-tertiary);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-primary);
  }
  
  .candidates {
    list-style: none;
    padding: 0;
    margin: 0 0 var(--space-4) 0;
  }
  
  .candidate {
    width: 100%;
    text-align: left;
    padding: var(--space-3);
    background: var(--bg-secondary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    margin-bottom: var(--space-2);
    cursor: pointer;
    transition: all var(--transition-fast);
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  
  .candidate:hover:not(:disabled) {
    background: var(--bg-tertiary);
    border-color: var(--border-emphasis);
  }
  
  .candidate:focus-visible {
    outline: 2px solid var(--border-emphasis);
    outline-offset: 2px;
  }
  
  .candidate.invalid {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  .info {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    flex: 1;
    min-width: 0;
  }
  
  .name {
    color: var(--text-primary);
    font-weight: 500;
  }
  
  .path {
    font-size: var(--text-xs);
    font-family: var(--font-mono);
    color: var(--text-tertiary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  .last-used {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .badge {
    font-size: var(--text-xs);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
  }
  
  .badge.invalid {
    background: rgba(var(--error-rgb), 0.15);
    color: var(--status-error);
  }
  
  .actions {
    display: flex;
    justify-content: flex-end;
  }
  
  .cancel-btn {
    background: transparent;
    border: 1px solid var(--border-default);
    color: var(--text-secondary);
    padding: var(--space-2) var(--space-4);
    border-radius: var(--radius-md);
    cursor: pointer;
    font-size: var(--text-sm);
    transition: all var(--transition-fast);
  }
  
  .cancel-btn:hover {
    border-color: var(--border-emphasis);
    color: var(--text-primary);
  }
</style>
