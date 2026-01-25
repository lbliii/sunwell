<!--
  BatchAddForm — Paste multiple goals at once (RFC-114 Phase 3)
  
  Allows users to paste a list of goals (one per line) to add them all at once.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import Modal from '../Modal.svelte';
  import Button from '../Button.svelte';
  import type { GoalCategory } from '../../stores/backlog.svelte';
  import { addGoal, getCategoryInfo } from '../../stores/backlog.svelte';

  interface Props {
    onClose: () => void;
    onSuccess?: () => void;
  }

  let { onClose, onSuccess }: Props = $props();

  // Form state
  let goalsText = $state('');
  let category = $state<GoalCategory>('add');
  let isSubmitting = $state(false);
  let error = $state<string | null>(null);
  let results = $state<{ title: string; success: boolean; error?: string }[]>([]);
  let textArea: HTMLTextAreaElement | undefined = $state();

  const categories: GoalCategory[] = ['fix', 'improve', 'add', 'refactor', 'document', 'test', 'security', 'performance'];

  // Parse goals from text (one per line, ignore empty lines)
  let parsedGoals = $derived(
    goalsText
      .split('\n')
      .map(line => line.trim())
      .filter(line => line.length > 0 && !line.startsWith('#'))
  );

  let isValid = $derived(parsedGoals.length > 0);
  let showResults = $derived(results.length > 0);
  let successCount = $derived(results.filter(r => r.success).length);
  let failCount = $derived(results.filter(r => !r.success).length);

  onMount(() => {
    textArea?.focus();
  });

  async function handleSubmit(e: Event) {
    e.preventDefault();
    if (!isValid || isSubmitting) return;

    isSubmitting = true;
    error = null;
    results = [];

    // Add goals one by one, collecting results
    const newResults: typeof results = [];

    for (const title of parsedGoals) {
      try {
        await addGoal(title, undefined, category, 0.5);
        newResults.push({ title, success: true });
      } catch (e) {
        newResults.push({
          title,
          success: false,
          error: e instanceof Error ? e.message : 'Unknown error',
        });
      }
    }

    results = newResults;
    isSubmitting = false;

    // If all succeeded, close after a brief delay
    if (newResults.every(r => r.success)) {
      setTimeout(() => {
        onSuccess?.();
        onClose();
      }, 1000);
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      onClose();
    }
  }

  function handleClear() {
    goalsText = '';
    results = [];
    error = null;
  }
</script>

<Modal isOpen={true} title="Add Multiple Goals" onClose={onClose}>
  {#if showResults}
    <!-- Results view -->
    <div class="results-summary">
      <span class="summary-success">✅ {successCount} added</span>
      {#if failCount > 0}
        <span class="summary-fail">❌ {failCount} failed</span>
      {/if}
    </div>

    <div class="results-list">
      {#each results as result, i (result.title + i)}
        <div class="result-item" class:success={result.success} class:fail={!result.success}>
          <span class="result-icon">{result.success ? '✓' : '✕'}</span>
          <span class="result-title">{result.title}</span>
          {#if result.error}
            <span class="result-error">{result.error}</span>
          {/if}
        </div>
      {/each}
    </div>

    <div class="modal-actions">
      {#if failCount > 0}
        <Button variant="ghost" onclick={handleClear}>Try Again</Button>
      {/if}
      <Button variant="primary" onclick={onClose}>Done</Button>
    </div>
  {:else}
    <!-- Input form -->
    <form class="batch-form" onsubmit={handleSubmit}>
      <div class="instructions">
        <p>Enter one goal per line. Empty lines and lines starting with <code>#</code> are ignored.</p>
      </div>

      <div class="form-group">
        <label for="goals-text">Goals</label>
        <textarea
          bind:this={textArea}
          id="goals-text"
          bind:value={goalsText}
          placeholder="Fix login bug
Add password reset
Create admin dashboard
# This is a comment
Write API tests
Update documentation"
          rows="10"
        ></textarea>
        <div class="char-info">
          {parsedGoals.length} goal{parsedGoals.length !== 1 ? 's' : ''} detected
        </div>
      </div>

      <div class="form-group">
        <label for="batch-category">Default Category</label>
        <select id="batch-category" bind:value={category}>
          {#each categories as cat (cat)}
            {@const info = getCategoryInfo(cat)}
            <option value={cat}>{info.emoji} {info.label}</option>
          {/each}
        </select>
      </div>

      {#if error}
        <div class="error-message">
          ⚠️ {error}
        </div>
      {/if}

      <div class="modal-actions">
        <Button variant="ghost" onclick={onClose}>Cancel</Button>
        <Button variant="primary" disabled={!isValid || isSubmitting} onclick={handleSubmit}>
          {isSubmitting ? 'Adding...' : `Add ${parsedGoals.length} Goal${parsedGoals.length !== 1 ? 's' : ''}`}
        </Button>
      </div>
    </form>
  {/if}
</Modal>

<style>
  .batch-form {
    display: contents;
  }

  .instructions {
    padding: 12px 16px;
    background: var(--bg-secondary);
    border-radius: 8px;
    font-size: 13px;
    color: var(--text-secondary);
  }

  .instructions p {
    margin: 0;
  }

  .instructions code {
    background: var(--bg-tertiary);
    padding: 2px 4px;
    border-radius: 4px;
    font-family: var(--font-mono);
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .form-group label {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-secondary);
  }

  .form-group textarea,
  .form-group select {
    width: 100%;
    padding: 10px 12px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    font-size: 14px;
    color: var(--text-primary);
    transition: border-color 0.15s ease;
    font-family: var(--font-mono);
  }

  .form-group textarea:focus,
  .form-group select:focus {
    outline: none;
    border-color: var(--accent);
  }

  .form-group textarea {
    resize: vertical;
    min-height: 200px;
    line-height: 1.5;
  }

  .form-group select {
    cursor: pointer;
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23888' d='M6 8L2 4h8z'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 12px center;
    padding-right: 32px;
    font-family: inherit;
  }

  .char-info {
    font-size: 11px;
    color: var(--text-tertiary);
    text-align: right;
  }

  .error-message {
    padding: 10px 12px;
    background: color-mix(in srgb, var(--error) 10%, transparent);
    border: 1px solid var(--error);
    border-radius: 8px;
    font-size: 13px;
    color: var(--error);
  }

  /* Results */
  .results-summary {
    display: flex;
    gap: 16px;
    padding: 12px 16px;
    background: var(--bg-secondary);
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
  }

  .summary-success {
    color: var(--success);
  }

  .summary-fail {
    color: var(--error);
  }

  .results-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-height: 300px;
    overflow-y: auto;
  }

  .result-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: var(--bg-secondary);
    border-radius: 6px;
    font-size: 13px;
  }

  .result-item.success {
    border-left: 3px solid var(--success);
  }

  .result-item.fail {
    border-left: 3px solid var(--error);
  }

  .result-icon {
    font-size: 12px;
  }

  .result-item.success .result-icon {
    color: var(--success);
  }

  .result-item.fail .result-icon {
    color: var(--error);
  }

  .result-title {
    flex: 1;
    color: var(--text-primary);
  }

  .result-error {
    font-size: 11px;
    color: var(--error);
  }
</style>
