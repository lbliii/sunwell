<!--
  WorkspaceDeleteDialog — Multi-step deletion dialog (RFC-141)
  
  Features:
  - Select deletion mode (unregister/purge/full)
  - Show impact preview (what will be deleted)
  - Require confirmation for destructive operations
  - Show progress and results
-->
<script lang="ts">
  import Button from '../Button.svelte';
  import {
    deleteWorkspace,
    checkActiveRuns,
    type DeletionMode,
    type WorkspaceInfo,
  } from '../../stores/workspaceManager.svelte';

  interface Props {
    workspace: WorkspaceInfo;
    onClose: () => void;
    onDeleted?: () => void;
  }

  let { workspace, onClose, onDeleted }: Props = $props();

  // State
  let step = $state<'select' | 'confirm' | 'progress' | 'result'>('select');
  let mode = $state<DeletionMode>('unregister');
  let deleteRuns = $state(false);
  let force = $state(false);
  let confirmInput = $state('');
  let isLoading = $state(false);
  let error = $state<string | null>(null);
  let activeRuns = $state<string[]>([]);
  let result = $state<{
    success: boolean;
    deletedItems: string[];
    failedItems: string[];
    runsDeleted: number;
    runsOrphaned: number;
  } | null>(null);

  // Check for active runs when mode changes
  $effect(() => {
    if (step === 'confirm' && (mode === 'purge' || mode === 'full')) {
      checkForActiveRuns();
    }
  });

  async function checkForActiveRuns() {
    try {
      const result = await checkActiveRuns(workspace.id);
      activeRuns = result.activeRuns;
    } catch (e) {
      console.error('Failed to check active runs:', e);
    }
  }

  function getModeName(m: DeletionMode): string {
    switch (m) {
      case 'unregister':
        return 'Unregister';
      case 'purge':
        return 'Purge Data';
      case 'full':
        return 'Full Delete';
    }
  }

  function getModeDescription(m: DeletionMode): string {
    switch (m) {
      case 'unregister':
        return 'Remove from registry, keep all files';
      case 'purge':
        return 'Remove from registry and delete .sunwell/ directory';
      case 'full':
        return 'Delete entire workspace directory including all files';
    }
  }

  function getModeColor(m: DeletionMode): string {
    switch (m) {
      case 'unregister':
        return 'var(--text-secondary)';
      case 'purge':
        return 'var(--warning)';
      case 'full':
        return 'var(--error)';
    }
  }

  function nextStep() {
    if (step === 'select') {
      step = 'confirm';
    }
  }

  function prevStep() {
    if (step === 'confirm') {
      step = 'select';
      confirmInput = '';
    }
  }

  async function handleDelete() {
    if (mode !== 'unregister' && confirmInput !== workspace.id) {
      error = 'Please type the workspace ID to confirm';
      return;
    }

    step = 'progress';
    isLoading = true;
    error = null;

    try {
      const deleteResult = await deleteWorkspace(workspace.id, {
        mode,
        confirm: true,
        deleteRuns,
        force,
      });

      result = {
        success: deleteResult.status === 'deleted',
        deletedItems: deleteResult.deletedItems,
        failedItems: deleteResult.failedItems,
        runsDeleted: deleteResult.runsDeleted,
        runsOrphaned: deleteResult.runsOrphaned,
      };
      step = 'result';
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
      step = 'confirm';
    } finally {
      isLoading = false;
    }
  }

  function handleDone() {
    if (result?.success) {
      onDeleted?.();
    }
    onClose();
  }
</script>

<div class="dialog-overlay" onclick={onClose}>
  <div class="dialog" onclick={(e) => e.stopPropagation()}>
    <header class="dialog-header">
      <h2 class="dialog-title">
        {#if step === 'result'}
          {result?.success ? 'Workspace Deleted' : 'Delete Failed'}
        {:else}
          Delete Workspace
        {/if}
      </h2>
      <button class="close-button" onclick={onClose}>&times;</button>
    </header>

    <div class="dialog-content">
      {#if step === 'select'}
        <!-- Step 1: Select deletion mode -->
        <div class="workspace-info">
          <span class="workspace-name">{workspace.name}</span>
          <span class="workspace-path">{workspace.path}</span>
        </div>

        <div class="mode-options">
          <label class="mode-option" class:selected={mode === 'unregister'}>
            <input type="radio" bind:group={mode} value="unregister" />
            <div class="mode-content">
              <span class="mode-name">Unregister</span>
              <span class="mode-description">Remove from registry, keep all files</span>
              <ul class="mode-details">
                <li class="keeps">Keeps: All files, .sunwell/ data</li>
                <li class="removes">Removes: Registry entry</li>
              </ul>
            </div>
          </label>

          <label class="mode-option" class:selected={mode === 'purge'}>
            <input type="radio" bind:group={mode} value="purge" />
            <div class="mode-content">
              <span class="mode-name warning">Purge Data</span>
              <span class="mode-description">Delete Sunwell data, keep source code</span>
              <ul class="mode-details">
                <li class="keeps">Keeps: Source code and project files</li>
                <li class="removes">Removes: .sunwell/ directory, registry entry</li>
              </ul>
            </div>
          </label>

          <label class="mode-option" class:selected={mode === 'full'}>
            <input type="radio" bind:group={mode} value="full" />
            <div class="mode-content">
              <span class="mode-name danger">Full Delete</span>
              <span class="mode-description">Delete everything including source code</span>
              <ul class="mode-details">
                <li class="removes">Removes: EVERYTHING - cannot be undone!</li>
              </ul>
            </div>
          </label>
        </div>

      {:else if step === 'confirm'}
        <!-- Step 2: Confirm deletion -->
        <div class="confirm-section">
          <div class="mode-summary" style="border-color: {getModeColor(mode)}">
            <span class="mode-label">Mode:</span>
            <span class="mode-value" style="color: {getModeColor(mode)}">{getModeName(mode)}</span>
          </div>

          <div class="workspace-info">
            <span class="workspace-name">{workspace.name}</span>
            <span class="workspace-path">{workspace.path}</span>
          </div>

          {#if activeRuns.length > 0}
            <div class="warning-box">
              <strong>Warning:</strong> This workspace has {activeRuns.length} active run(s):
              <ul>
                {#each activeRuns.slice(0, 3) as runId}
                  <li>{runId}</li>
                {/each}
                {#if activeRuns.length > 3}
                  <li>...and {activeRuns.length - 3} more</li>
                {/if}
              </ul>
              <label class="checkbox-label">
                <input type="checkbox" bind:checked={force} />
                Force delete (abort active runs)
              </label>
            </div>
          {/if}

          {#if mode !== 'unregister'}
            <label class="checkbox-label">
              <input type="checkbox" bind:checked={deleteRuns} />
              Also delete associated runs from history
            </label>
          {/if}

          {#if mode !== 'unregister'}
            <div class="confirm-input-section">
              <p class="confirm-prompt">
                Type <strong>{workspace.id}</strong> to confirm:
              </p>
              <input
                type="text"
                class="confirm-input"
                bind:value={confirmInput}
                placeholder={workspace.id}
              />
            </div>
          {/if}

          {#if error}
            <div class="error-message">{error}</div>
          {/if}
        </div>

      {:else if step === 'progress'}
        <!-- Step 3: Progress -->
        <div class="progress-section">
          <div class="spinner"></div>
          <p class="progress-text">Deleting workspace...</p>
        </div>

      {:else if step === 'result'}
        <!-- Step 4: Result -->
        <div class="result-section">
          {#if result?.success}
            <div class="success-icon">✓</div>
            <p class="result-text">Workspace successfully deleted</p>
          {:else}
            <div class="error-icon">✗</div>
            <p class="result-text">Some items could not be deleted</p>
          {/if}

          {#if result}
            <div class="result-details">
              {#if result.deletedItems.length > 0}
                <div class="result-group">
                  <span class="result-label">Deleted:</span>
                  <ul class="result-list">
                    {#each result.deletedItems.slice(0, 5) as item}
                      <li>{item}</li>
                    {/each}
                    {#if result.deletedItems.length > 5}
                      <li>...and {result.deletedItems.length - 5} more</li>
                    {/if}
                  </ul>
                </div>
              {/if}

              {#if result.failedItems.length > 0}
                <div class="result-group error">
                  <span class="result-label">Failed:</span>
                  <ul class="result-list">
                    {#each result.failedItems as item}
                      <li>{item}</li>
                    {/each}
                  </ul>
                </div>
              {/if}

              {#if result.runsDeleted > 0}
                <p class="result-stat">Runs deleted: {result.runsDeleted}</p>
              {/if}

              {#if result.runsOrphaned > 0}
                <p class="result-stat">Runs orphaned: {result.runsOrphaned}</p>
              {/if}
            </div>
          {/if}
        </div>
      {/if}
    </div>

    <footer class="dialog-footer">
      {#if step === 'select'}
        <Button variant="ghost" onclick={onClose}>Cancel</Button>
        <Button variant="primary" onclick={nextStep}>Next</Button>
      {:else if step === 'confirm'}
        <Button variant="ghost" onclick={prevStep}>Back</Button>
        <Button
          variant={mode === 'full' ? 'destructive' : 'primary'}
          onclick={handleDelete}
          disabled={isLoading || (mode !== 'unregister' && confirmInput !== workspace.id)}
        >
          {mode === 'unregister' ? 'Unregister' : mode === 'purge' ? 'Purge' : 'Delete'}
        </Button>
      {:else if step === 'progress'}
        <!-- No buttons during progress -->
      {:else if step === 'result'}
        <Button variant="primary" onclick={handleDone}>Done</Button>
      {/if}
    </footer>
  </div>
</div>

<style>
  .dialog-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .dialog {
    background: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    width: 100%;
    max-width: 500px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .dialog-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-4);
    border-bottom: 1px solid var(--border-color);
  }

  .dialog-title {
    margin: 0;
    font-size: var(--text-lg);
    font-weight: 600;
  }

  .close-button {
    background: none;
    border: none;
    font-size: 24px;
    color: var(--text-tertiary);
    cursor: pointer;
    padding: 0;
    line-height: 1;
  }

  .close-button:hover {
    color: var(--text-primary);
  }

  .dialog-content {
    flex: 1;
    padding: var(--space-4);
    overflow-y: auto;
  }

  .dialog-footer {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-2);
    padding: var(--space-4);
    border-top: 1px solid var(--border-color);
  }

  .workspace-info {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    padding: var(--space-3);
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    margin-bottom: var(--space-4);
  }

  .workspace-name {
    font-weight: 600;
    color: var(--text-primary);
  }

  .workspace-path {
    font-size: var(--text-sm);
    font-family: var(--font-mono);
    color: var(--text-tertiary);
  }

  .mode-options {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .mode-option {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3);
    padding: var(--space-3);
    background: var(--bg-secondary);
    border: 2px solid var(--border-color);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all var(--transition-fast);
  }

  .mode-option:hover {
    border-color: var(--border-subtle);
  }

  .mode-option.selected {
    border-color: var(--gold);
    background: var(--bg-tertiary);
  }

  .mode-option input {
    margin-top: 4px;
  }

  .mode-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .mode-name {
    font-weight: 600;
    color: var(--text-primary);
  }

  .mode-name.warning {
    color: var(--warning);
  }

  .mode-name.danger {
    color: var(--error);
  }

  .mode-description {
    font-size: var(--text-sm);
    color: var(--text-secondary);
  }

  .mode-details {
    margin: var(--space-2) 0 0 0;
    padding: 0;
    list-style: none;
    font-size: var(--text-xs);
  }

  .mode-details li {
    padding: var(--space-1) 0;
  }

  .mode-details .keeps {
    color: var(--success);
  }

  .mode-details .removes {
    color: var(--error);
  }

  .confirm-section {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .mode-summary {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    border: 2px solid;
    border-radius: var(--radius-md);
  }

  .mode-label {
    color: var(--text-secondary);
  }

  .mode-value {
    font-weight: 600;
  }

  .warning-box {
    padding: var(--space-3);
    background: var(--warning-bg);
    border: 1px solid var(--warning);
    border-radius: var(--radius-md);
    color: var(--warning);
  }

  .warning-box ul {
    margin: var(--space-2) 0;
    padding-left: var(--space-4);
  }

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    cursor: pointer;
    color: var(--text-secondary);
  }

  .confirm-input-section {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .confirm-prompt {
    margin: 0;
    color: var(--text-secondary);
  }

  .confirm-input {
    padding: var(--space-2) var(--space-3);
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    font-family: var(--font-mono);
    color: var(--text-primary);
  }

  .confirm-input:focus {
    outline: none;
    border-color: var(--gold);
  }

  .error-message {
    padding: var(--space-2) var(--space-3);
    background: var(--error-bg);
    border: 1px solid var(--error);
    border-radius: var(--radius-md);
    color: var(--error);
  }

  .progress-section {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: var(--space-8);
    gap: var(--space-4);
  }

  .spinner {
    width: 32px;
    height: 32px;
    border: 3px solid var(--border-color);
    border-top-color: var(--gold);
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .progress-text {
    margin: 0;
    color: var(--text-secondary);
  }

  .result-section {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-4);
    padding: var(--space-4);
  }

  .success-icon {
    width: 48px;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--success-bg);
    color: var(--success);
    border-radius: 50%;
    font-size: 24px;
    font-weight: bold;
  }

  .error-icon {
    width: 48px;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--error-bg);
    color: var(--error);
    border-radius: 50%;
    font-size: 24px;
    font-weight: bold;
  }

  .result-text {
    margin: 0;
    font-size: var(--text-lg);
    font-weight: 500;
  }

  .result-details {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .result-group {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .result-group.error {
    color: var(--error);
  }

  .result-label {
    font-weight: 500;
  }

  .result-list {
    margin: 0;
    padding-left: var(--space-4);
    font-size: var(--text-sm);
    font-family: var(--font-mono);
    color: var(--text-secondary);
  }

  .result-stat {
    margin: 0;
    font-size: var(--text-sm);
    color: var(--text-tertiary);
  }
</style>
