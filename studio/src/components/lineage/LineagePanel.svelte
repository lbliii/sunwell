<script lang="ts">
  /**
   * LineagePanel — Display artifact lineage and edit history (RFC-121)
   *
   * Shows:
   * - File creation info (goal, reason, model)
   * - Edit history with attribution
   * - Dependencies (imports/imported_by)
   */

  import {
    lineageState,
    loadFileLineage,
    loadDependencies,
    analyzeImpact,
    clearLineage,
    getSourceIcon,
    getEditTypeLabel,
    formatTimestamp,
    getLanguageIcon,
    type ArtifactLineage,
    type ArtifactEdit,
  } from '../../stores/lineage.svelte';

  interface Props {
    path?: string;
    workspace?: string;
    showDependencies?: boolean;
    showImpact?: boolean;
    compact?: boolean;
  }

  let {
    path = undefined,
    workspace = undefined,
    showDependencies = true,
    showImpact = false,
    compact = false,
  }: Props = $props();

  // Load lineage when path changes
  $effect(() => {
    if (path) {
      loadFileLineage(path, workspace);
      if (showDependencies) {
        loadDependencies(path, workspace);
      }
      if (showImpact) {
        analyzeImpact(path, workspace);
      }
    } else {
      clearLineage();
    }
  });

  // Derived state
  const lineage = $derived(lineageState.currentLineage);
  const deps = $derived(lineageState.dependencies);
  const impact = $derived(lineageState.impact);
  const loading = $derived(lineageState.loading);
  const error = $derived(lineageState.error);

  // Tab state
  let activeTab: 'history' | 'deps' | 'impact' = $state('history');
</script>

<div class="lineage-panel" class:compact>
  {#if loading}
    <div class="loading">
      <span class="spinner"></span>
      <span>Loading lineage...</span>
    </div>
  {:else if error}
    <div class="error">
      <span class="icon">⚠️</span>
      <span>{error}</span>
    </div>
  {:else if !lineage}
    <div class="empty">
      <span class="icon">📜</span>
      <span>No lineage data</span>
      <span class="hint">This file was not tracked by Sunwell</span>
    </div>
  {:else}
    <!-- Header -->
    <header class="header">
      <div class="file-info">
        <span class="icon">{getLanguageIcon(lineage.path)}</span>
        <span class="path">{lineage.path}</span>
        {#if lineage.human_edited}
          <span class="badge human">Human Edited</span>
        {/if}
      </div>
    </header>

    <!-- Tabs -->
    {#if !compact}
      <nav class="tabs">
        <button
          class="tab"
          class:active={activeTab === 'history'}
          onclick={() => activeTab = 'history'}
        >
          History ({lineage.edits.length})
        </button>
        {#if showDependencies}
          <button
            class="tab"
            class:active={activeTab === 'deps'}
            onclick={() => activeTab = 'deps'}
          >
            Dependencies
          </button>
        {/if}
        {#if showImpact}
          <button
            class="tab"
            class:active={activeTab === 'impact'}
            onclick={() => activeTab = 'impact'}
          >
            Impact
          </button>
        {/if}
      </nav>
    {/if}

    <!-- Content -->
    <div class="content">
      {#if activeTab === 'history' || compact}
        <!-- Creation Info -->
        <section class="creation">
          <h4>Created</h4>
          <div class="meta">
            {#if lineage.created_by_goal}
              <div class="meta-item">
                <span class="label">Goal:</span>
                <span class="value goal-id">{lineage.created_by_goal}</span>
              </div>
            {:else}
              <div class="meta-item dim">
                <span>Pre-existing file</span>
              </div>
            {/if}
            <div class="meta-item">
              <span class="label">Reason:</span>
              <span class="value">{lineage.created_reason}</span>
            </div>
            <div class="meta-item">
              <span class="label">Time:</span>
              <span class="value">{formatTimestamp(lineage.created_at)}</span>
            </div>
            {#if lineage.model}
              <div class="meta-item">
                <span class="label">Model:</span>
                <span class="value model">{lineage.model}</span>
              </div>
            {/if}
          </div>
        </section>

        <!-- Edit History -->
        {#if lineage.edits.length > 0}
          <section class="history">
            <h4>Edit History</h4>
            <div class="edit-list">
              {#each lineage.edits as edit, i (edit.edit_id)}
                <div class="edit-item">
                  <div class="edit-header">
                    <span class="version">v{i + 1}</span>
                    <span class="time">{formatTimestamp(edit.timestamp)}</span>
                    <span class="type">{getEditTypeLabel(edit.edit_type)}</span>
                    <span class="source" title={edit.source}>
                      {getSourceIcon(edit.source)}
                    </span>
                  </div>
                  <div class="edit-details">
                    <span class="changes">
                      +{edit.lines_added} / -{edit.lines_removed}
                    </span>
                    {#if edit.goal_id}
                      <span class="goal-link" title="Goal">
                        {edit.goal_id.slice(0, 8)}
                      </span>
                    {/if}
                  </div>
                </div>
              {/each}
            </div>
          </section>
        {/if}
      {/if}

      {#if activeTab === 'deps' && deps && !compact}
        <section class="dependencies">
          {#if deps.imports.length > 0}
            <div class="dep-section">
              <h4>Imports ({deps.imports.length})</h4>
              <ul class="dep-list">
                {#each deps.imports as imp}
                  <li class="dep-item">
                    <span class="icon">{getLanguageIcon(imp)}</span>
                    <span class="path">{imp}</span>
                  </li>
                {/each}
              </ul>
            </div>
          {/if}

          {#if deps.imported_by.length > 0}
            <div class="dep-section">
              <h4>Imported By ({deps.imported_by.length})</h4>
              <ul class="dep-list">
                {#each deps.imported_by as imp}
                  <li class="dep-item">
                    <span class="icon">{getLanguageIcon(imp)}</span>
                    <span class="path">{imp}</span>
                  </li>
                {/each}
              </ul>
            </div>
          {/if}

          {#if deps.imports.length === 0 && deps.imported_by.length === 0}
            <div class="empty-deps">
              <span>No dependencies tracked</span>
            </div>
          {/if}
        </section>
      {/if}

      {#if activeTab === 'impact' && impact && !compact}
        <section class="impact-analysis">
          {#if impact.affected_files.length === 0}
            <div class="safe">
              <span class="icon">✅</span>
              <span>No files depend on this file</span>
              <span class="hint">Safe to modify or delete</span>
            </div>
          {:else}
            <div class="warning">
              <span class="icon">⚠️</span>
              <span>{impact.affected_files.length} files will be affected</span>
            </div>

            <div class="impact-stats">
              <div class="stat">
                <span class="label">Max Depth:</span>
                <span class="value">{impact.max_depth}</span>
              </div>
              <div class="stat">
                <span class="label">Related Goals:</span>
                <span class="value">{impact.affected_goals.length}</span>
              </div>
            </div>

            <div class="affected-files">
              <h4>Affected Files</h4>
              <ul class="file-list">
                {#each impact.affected_files.slice(0, 20) as file}
                  <li class="file-item">
                    <span class="icon">{getLanguageIcon(file)}</span>
                    <span class="path">{file}</span>
                  </li>
                {/each}
                {#if impact.affected_files.length > 20}
                  <li class="more">
                    ... and {impact.affected_files.length - 20} more
                  </li>
                {/if}
              </ul>
            </div>
          {/if}
        </section>
      {/if}
    </div>
  {/if}
</div>

<style>
  .lineage-panel {
    display: flex;
    flex-direction: column;
    gap: var(--space-md, 1rem);
    padding: var(--space-md, 1rem);
    background: var(--surface-1, #1a1a1a);
    border-radius: var(--radius-md, 8px);
    font-size: 0.875rem;
  }

  .lineage-panel.compact {
    padding: var(--space-sm, 0.5rem);
    gap: var(--space-sm, 0.5rem);
  }

  /* Loading & Error */
  .loading, .error, .empty {
    display: flex;
    align-items: center;
    gap: var(--space-sm, 0.5rem);
    padding: var(--space-lg, 1.5rem);
    justify-content: center;
    flex-direction: column;
    color: var(--text-2, #888);
  }

  .error {
    color: var(--error, #f44);
  }

  .spinner {
    width: 20px;
    height: 20px;
    border: 2px solid var(--text-3, #444);
    border-top-color: var(--accent, #6cf);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .hint {
    font-size: 0.75rem;
    color: var(--text-3, #666);
  }

  /* Header */
  .header {
    display: flex;
    align-items: center;
    gap: var(--space-sm, 0.5rem);
  }

  .file-info {
    display: flex;
    align-items: center;
    gap: var(--space-xs, 0.25rem);
  }

  .file-info .path {
    font-family: var(--font-mono, monospace);
    color: var(--text-1, #eee);
  }

  .badge {
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.7rem;
    text-transform: uppercase;
  }

  .badge.human {
    background: var(--warning-bg, #442);
    color: var(--warning, #fa0);
  }

  /* Tabs */
  .tabs {
    display: flex;
    gap: var(--space-xs, 0.25rem);
    border-bottom: 1px solid var(--border, #333);
    padding-bottom: var(--space-xs, 0.25rem);
  }

  .tab {
    padding: var(--space-xs, 0.25rem) var(--space-sm, 0.5rem);
    background: transparent;
    border: none;
    color: var(--text-2, #888);
    cursor: pointer;
    border-radius: 4px;
    transition: background 0.15s, color 0.15s;
  }

  .tab:hover {
    background: var(--surface-2, #252525);
  }

  .tab.active {
    color: var(--accent, #6cf);
    background: var(--surface-2, #252525);
  }

  /* Sections */
  section {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm, 0.5rem);
  }

  section h4 {
    margin: 0;
    font-size: 0.75rem;
    text-transform: uppercase;
    color: var(--text-3, #666);
    letter-spacing: 0.05em;
  }

  /* Creation Info */
  .meta {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs, 0.25rem);
  }

  .meta-item {
    display: flex;
    gap: var(--space-sm, 0.5rem);
  }

  .meta-item .label {
    color: var(--text-3, #666);
    min-width: 60px;
  }

  .meta-item .value {
    color: var(--text-1, #eee);
  }

  .meta-item.dim {
    color: var(--text-3, #666);
    font-style: italic;
  }

  .goal-id {
    font-family: var(--font-mono, monospace);
    color: var(--accent, #6cf);
  }

  .model {
    font-family: var(--font-mono, monospace);
    color: var(--success, #4f8);
  }

  /* Edit History */
  .edit-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs, 0.25rem);
  }

  .edit-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: var(--space-xs, 0.25rem);
    background: var(--surface-2, #252525);
    border-radius: 4px;
  }

  .edit-header {
    display: flex;
    align-items: center;
    gap: var(--space-sm, 0.5rem);
  }

  .edit-header .version {
    font-family: var(--font-mono, monospace);
    color: var(--text-3, #666);
    font-size: 0.7rem;
  }

  .edit-header .time {
    color: var(--text-2, #888);
    font-size: 0.75rem;
  }

  .edit-header .type {
    color: var(--text-1, #eee);
  }

  .edit-header .source {
    margin-left: auto;
  }

  .edit-details {
    display: flex;
    align-items: center;
    gap: var(--space-sm, 0.5rem);
    font-size: 0.75rem;
  }

  .edit-details .changes {
    font-family: var(--font-mono, monospace);
    color: var(--text-2, #888);
  }

  .edit-details .goal-link {
    font-family: var(--font-mono, monospace);
    color: var(--accent, #6cf);
    cursor: pointer;
  }

  /* Dependencies */
  .dep-section {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs, 0.25rem);
  }

  .dep-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .dep-item {
    display: flex;
    align-items: center;
    gap: var(--space-xs, 0.25rem);
    padding: var(--space-xs, 0.25rem);
    background: var(--surface-2, #252525);
    border-radius: 4px;
    cursor: pointer;
  }

  .dep-item:hover {
    background: var(--surface-3, #333);
  }

  .dep-item .path {
    font-family: var(--font-mono, monospace);
    font-size: 0.75rem;
    color: var(--text-1, #eee);
  }

  .empty-deps {
    text-align: center;
    color: var(--text-3, #666);
    padding: var(--space-md, 1rem);
  }

  /* Impact Analysis */
  .safe {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-xs, 0.25rem);
    padding: var(--space-md, 1rem);
    background: var(--success-bg, #143);
    border-radius: 8px;
    color: var(--success, #4f8);
  }

  .warning {
    display: flex;
    align-items: center;
    gap: var(--space-sm, 0.5rem);
    padding: var(--space-sm, 0.5rem);
    background: var(--warning-bg, #442);
    border-radius: 4px;
    color: var(--warning, #fa0);
  }

  .impact-stats {
    display: flex;
    gap: var(--space-lg, 1.5rem);
  }

  .impact-stats .stat {
    display: flex;
    gap: var(--space-xs, 0.25rem);
  }

  .impact-stats .label {
    color: var(--text-3, #666);
  }

  .impact-stats .value {
    color: var(--text-1, #eee);
    font-family: var(--font-mono, monospace);
  }

  .affected-files .file-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
    max-height: 300px;
    overflow-y: auto;
  }

  .file-item {
    display: flex;
    align-items: center;
    gap: var(--space-xs, 0.25rem);
    padding: var(--space-xs, 0.25rem);
  }

  .file-item .path {
    font-family: var(--font-mono, monospace);
    font-size: 0.75rem;
    color: var(--text-2, #888);
  }

  .more {
    color: var(--text-3, #666);
    font-style: italic;
    padding: var(--space-xs, 0.25rem);
  }
</style>
