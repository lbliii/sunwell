<!--
  GoalForm — Add/edit goal modal for Backlog panel (RFC-114)
  
  Form for creating new goals with title, description, category, complexity, and priority.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import type { GoalCategory, GoalComplexity } from '../../stores/backlog.svelte';
  import { addGoal, getCategoryInfo, getComplexityInfo } from '../../stores/backlog.svelte';

  interface Props {
    onClose: () => void;
    onSuccess?: () => void;
  }

  let { onClose, onSuccess }: Props = $props();

  // Form state
  let title = $state('');
  let description = $state('');
  let category = $state<GoalCategory>('add');
  let complexity = $state<GoalComplexity>('moderate');
  let priority = $state(0.5);
  let autoApprovable = $state(false);
  let isSubmitting = $state(false);
  let error = $state<string | null>(null);
  let titleInput: HTMLInputElement | undefined = $state();

  const categories: GoalCategory[] = ['fix', 'improve', 'add', 'refactor', 'document', 'test', 'security', 'performance'];
  const complexities: GoalComplexity[] = ['trivial', 'simple', 'moderate', 'complex'];

  let isValid = $derived(title.trim().length > 0);

  // Programmatic autofocus to avoid browser conflicts
  onMount(() => {
    titleInput?.focus();
  });

  async function handleSubmit(e: Event) {
    e.preventDefault();
    if (!isValid || isSubmitting) return;

    isSubmitting = true;
    error = null;

    try {
      await addGoal(title.trim(), description.trim() || undefined, category, priority);
      onSuccess?.();
      onClose();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to add goal';
    } finally {
      isSubmitting = false;
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      onClose();
    }
  }
</script>

<div
  class="modal-overlay"
  role="presentation"
  onclick={onClose}
  onkeydown={handleKeydown}
>
  <div
    class="modal"
    role="dialog"
    aria-modal="true"
    aria-labelledby="modal-title"
    tabindex="-1"
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => e.stopPropagation()}
  >
    <header class="modal-header">
      <h3 id="modal-title">Add Goal</h3>
      <button class="close-btn" onclick={onClose} aria-label="Close">✕</button>
    </header>

    <form onsubmit={handleSubmit}>
      <div class="form-body">
        <!-- Title -->
        <div class="form-group">
          <label for="goal-title">Title <span class="required">*</span></label>
          <input
            bind:this={titleInput}
            id="goal-title"
            type="text"
            bind:value={title}
            placeholder="Implement user authentication"
            maxlength="60"
          />
          <span class="char-count">{title.length}/60</span>
        </div>

        <!-- Description -->
        <div class="form-group">
          <label for="goal-description">Description <span class="optional">(optional)</span></label>
          <textarea
            id="goal-description"
            bind:value={description}
            placeholder="Add OAuth2 login flow supporting Google and GitHub providers. Include session management and logout."
            rows="3"
          ></textarea>
        </div>

        <!-- Category + Complexity Row -->
        <div class="form-row">
          <div class="form-group">
            <label for="goal-category">Category</label>
            <select id="goal-category" bind:value={category}>
              {#each categories as cat (cat)}
                {@const info = getCategoryInfo(cat)}
                <option value={cat}>{info.emoji} {info.label}</option>
              {/each}
            </select>
          </div>

          <div class="form-group">
            <label for="goal-complexity">Complexity</label>
            <select id="goal-complexity" bind:value={complexity}>
              {#each complexities as comp (comp)}
                {@const info = getComplexityInfo(comp)}
                <option value={comp}>{info.emoji} {info.label}</option>
              {/each}
            </select>
          </div>
        </div>

        <!-- Priority Slider -->
        <div class="form-group">
          <label for="goal-priority">
            Priority
            <span class="priority-value">{Math.round(priority * 100)}%</span>
          </label>
          <div class="priority-slider-container">
            <span class="priority-label low">Low</span>
            <input
              id="goal-priority"
              type="range"
              min="0"
              max="1"
              step="0.05"
              bind:value={priority}
              class="priority-slider"
            />
            <span class="priority-label high">High</span>
          </div>
        </div>

        <!-- Auto-approvable -->
        <div class="form-group checkbox-group">
          <label class="checkbox-label">
            <input type="checkbox" bind:checked={autoApprovable} />
            <span class="checkbox-text">
              <span class="checkbox-title">⚡ Auto-approve if tests pass</span>
              <span class="checkbox-hint">Allows execution without manual review</span>
            </span>
          </label>
        </div>

        <!-- Error -->
        {#if error}
          <div class="error-message">
            ⚠️ {error}
          </div>
        {/if}
      </div>

      <footer class="modal-footer">
        <button type="button" class="btn secondary" onclick={onClose}>
          Cancel
        </button>
        <button
          type="submit"
          class="btn primary"
          disabled={!isValid || isSubmitting}
        >
          {isSubmitting ? 'Adding...' : 'Add Goal'}
        </button>
      </footer>
    </form>
  </div>
</div>

<style>
  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    backdrop-filter: blur(2px);
  }

  .modal {
    background: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: 16px;
    width: min(480px, 90vw);
    max-height: 90vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.3);
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 24px;
    border-bottom: 1px solid var(--border-color);
  }

  .modal-header h3 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .close-btn {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: none;
    border-radius: 8px;
    font-size: 16px;
    color: var(--text-tertiary);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .close-btn:hover {
    background: var(--bg-tertiary);
    color: var(--text-primary);
  }

  .form-body {
    padding: 20px 24px;
    display: flex;
    flex-direction: column;
    gap: 18px;
    overflow-y: auto;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
    position: relative;
  }

  .form-group label {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .required {
    color: var(--error);
  }

  .optional {
    font-weight: 400;
    color: var(--text-tertiary);
  }

  .form-group input[type="text"],
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
  }

  .form-group input:focus,
  .form-group textarea:focus,
  .form-group select:focus {
    outline: none;
    border-color: var(--accent);
  }

  .form-group textarea {
    resize: vertical;
    min-height: 80px;
  }

  .form-group select {
    cursor: pointer;
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23888' d='M6 8L2 4h8z'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 12px center;
    padding-right: 32px;
  }

  .char-count {
    position: absolute;
    right: 8px;
    bottom: 8px;
    font-size: 10px;
    color: var(--text-tertiary);
    pointer-events: none;
  }

  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }

  .priority-value {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--accent);
    margin-left: auto;
  }

  .priority-slider-container {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .priority-label {
    font-size: 11px;
    color: var(--text-tertiary);
    min-width: 30px;
  }

  .priority-label.high {
    text-align: right;
  }

  .priority-slider {
    flex: 1;
    height: 6px;
    -webkit-appearance: none;
    appearance: none;
    background: var(--bg-tertiary);
    border-radius: 3px;
    outline: none;
    cursor: pointer;
  }

  .priority-slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 18px;
    height: 18px;
    background: var(--accent);
    border-radius: 50%;
    cursor: pointer;
    transition: transform 0.15s ease;
  }

  .priority-slider::-webkit-slider-thumb:hover {
    transform: scale(1.1);
  }

  .priority-slider::-moz-range-thumb {
    width: 18px;
    height: 18px;
    background: var(--accent);
    border-radius: 50%;
    border: none;
    cursor: pointer;
  }

  .checkbox-group {
    margin-top: 4px;
  }

  .checkbox-label {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    cursor: pointer;
  }

  .checkbox-label input[type="checkbox"] {
    width: 18px;
    height: 18px;
    margin-top: 2px;
    accent-color: var(--accent);
    cursor: pointer;
  }

  .checkbox-text {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .checkbox-title {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-primary);
  }

  .checkbox-hint {
    font-size: 11px;
    color: var(--text-tertiary);
  }

  .error-message {
    padding: 10px 12px;
    background: color-mix(in srgb, var(--error) 10%, transparent);
    border: 1px solid var(--error);
    border-radius: 8px;
    font-size: 13px;
    color: var(--error);
  }

  .modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    padding: 16px 24px;
    border-top: 1px solid var(--border-color);
    background: var(--bg-secondary);
  }

  .btn {
    padding: 10px 20px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .btn.secondary {
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    color: var(--text-secondary);
  }

  .btn.secondary:hover {
    background: var(--bg-primary);
    color: var(--text-primary);
  }

  .btn.primary {
    background: var(--accent);
    border: none;
    color: var(--bg-primary);
  }

  .btn.primary:hover:not(:disabled) {
    filter: brightness(1.1);
  }

  .btn.primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
