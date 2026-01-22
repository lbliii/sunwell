<!--
  WriterStatusBar.svelte — Status bar for Universal Writing Environment (RFC-086)
  
  Shows:
  - Word count
  - Diataxis badge with confidence
  - Validation warnings count
  - Active lens
  - View toggle (source/preview)
-->
<script lang="ts">
  import { fade, fly } from 'svelte/transition';
  import {
    writerState,
    toggleView,
    type ViewMode,
    type DiataxisType,
  } from '../../stores';

  interface Props {
    /** Override values (optional - uses writer store by default) */
    wordCount?: number;
    viewMode?: ViewMode;
    diataxisType?: DiataxisType | null;
    diataxisConfidence?: number;
    errorCount?: number;
    warningCount?: number;
    lensName?: string;
    isDirty?: boolean;
    onToggleView?: () => void;
    onOpenLensSelector?: () => void;
  }

  let {
    wordCount: propWordCount,
    viewMode: propViewMode,
    diataxisType: propDiataxisType,
    diataxisConfidence: propConfidence,
    errorCount: propErrorCount,
    warningCount: propWarningCount,
    lensName: propLensName,
    isDirty: propIsDirty,
    onToggleView,
    onOpenLensSelector,
  }: Props = $props();

  // Use props if provided, otherwise use writer store
  const wordCount = $derived(propWordCount ?? writerState.wordCount);
  const viewMode = $derived(propViewMode ?? writerState.viewMode);
  const diataxisType = $derived(propDiataxisType ?? writerState.diataxisType);
  const diataxisConfidence = $derived(propConfidence ?? writerState.diataxisConfidence);
  const errorCount = $derived(propErrorCount ?? writerState.errorCount);
  const warningCount = $derived(propWarningCount ?? writerState.warningCount);
  const lensName = $derived(propLensName ?? writerState.lensName);
  const isDirty = $derived(propIsDirty ?? writerState.isDirty);

  // Diataxis type colors and labels
  const diataxisConfig: Record<string, { label: string; color: string; icon: string }> = {
    TUTORIAL: { label: 'Tutorial', color: '#6bff6b', icon: '📚' },
    HOW_TO: { label: 'How-To', color: '#6bcbff', icon: '📋' },
    EXPLANATION: { label: 'Explanation', color: '#ffd93d', icon: '💡' },
    REFERENCE: { label: 'Reference', color: '#ff6b6b', icon: '📖' },
  };

  const diataxisInfo = $derived(diataxisType ? diataxisConfig[diataxisType] : null);
  const confidencePct = $derived(Math.round(diataxisConfidence * 100));

  function handleToggleView() {
    if (onToggleView) {
      onToggleView();
    } else {
      toggleView();
    }
  }

  // Keyboard shortcut for view toggle (⌘P)
  function handleKeydown(e: KeyboardEvent) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'p') {
      e.preventDefault();
      handleToggleView();
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="status-bar" transition:fly={{ y: 20, duration: 200 }}>
  <!-- Left section: Word count and dirty indicator -->
  <div class="section left">
    <span class="word-count">
      {wordCount.toLocaleString()} words
    </span>
    {#if isDirty}
      <span class="dirty-indicator" title="Unsaved changes">●</span>
    {/if}
  </div>

  <!-- Center section: Diataxis badge and validation -->
  <div class="section center">
    {#if diataxisInfo}
      <button
        class="diataxis-badge"
        style="--badge-color: {diataxisInfo.color}"
        title="Detected content type: {diataxisInfo.label} ({confidencePct}% confidence)"
      >
        <span class="badge-icon">{diataxisInfo.icon}</span>
        <span class="badge-label">{diataxisInfo.label}</span>
        <span class="badge-confidence">{confidencePct}%</span>
      </button>
    {:else}
      <span class="diataxis-unknown" title="Content type not detected">
        ❓ Unknown
      </span>
    {/if}

    {#if errorCount > 0 || warningCount > 0}
      <div class="validation-summary">
        {#if errorCount > 0}
          <span class="error-count" title="{errorCount} errors">
            ❌ {errorCount}
          </span>
        {/if}
        {#if warningCount > 0}
          <span class="warning-count" title="{warningCount} warnings">
            ⚠️ {warningCount}
          </span>
        {/if}
      </div>
    {:else}
      <span class="all-good" title="No issues">✅</span>
    {/if}
  </div>

  <!-- Right section: Lens and view toggle -->
  <div class="section right">
    <button
      class="lens-button"
      onclick={onOpenLensSelector}
      title="Change lens"
    >
      <span class="lens-icon">🔮</span>
      <span class="lens-name">{lensName}</span>
    </button>

    <div class="view-toggle">
      <button
        class="toggle-btn"
        class:active={viewMode === 'source'}
        onclick={handleToggleView}
        title="Source view (⌘P)"
      >
        <span class="icon">📝</span>
      </button>
      <button
        class="toggle-btn"
        class:active={viewMode === 'preview'}
        onclick={handleToggleView}
        title="Preview (⌘P)"
      >
        <span class="icon">👁</span>
      </button>
    </div>
  </div>
</div>

<style>
  .status-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 12px;
    background: var(--surface-2, #1a1a2e);
    border-top: 1px solid var(--border, #333);
    font-family: var(--font-mono, 'JetBrains Mono', monospace);
    font-size: 11px;
    color: var(--text-muted, #888);
    user-select: none;
  }

  .section {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .section.left {
    min-width: 120px;
  }

  .section.center {
    flex: 1;
    justify-content: center;
  }

  .section.right {
    min-width: 200px;
    justify-content: flex-end;
  }

  .word-count {
    color: var(--text, #fff);
    font-weight: 500;
  }

  .dirty-indicator {
    color: var(--warning, #ffd93d);
    font-size: 8px;
  }

  .diataxis-badge {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--badge-color, #888);
    border-radius: 12px;
    cursor: pointer;
    font-family: inherit;
    font-size: inherit;
    color: var(--badge-color, #888);
  }

  .diataxis-badge:hover {
    background: rgba(255, 255, 255, 0.1);
  }

  .badge-icon {
    font-size: 12px;
  }

  .badge-label {
    font-weight: 500;
  }

  .badge-confidence {
    opacity: 0.7;
    font-size: 10px;
  }

  .diataxis-unknown {
    opacity: 0.5;
  }

  .validation-summary {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .error-count {
    color: var(--error, #ff6b6b);
  }

  .warning-count {
    color: var(--warning, #ffd93d);
  }

  .all-good {
    opacity: 0.7;
  }

  .lens-button {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    background: transparent;
    border: 1px solid var(--border, #333);
    border-radius: 4px;
    cursor: pointer;
    font-family: inherit;
    font-size: inherit;
    color: var(--text-muted, #888);
  }

  .lens-button:hover {
    background: var(--surface-3, #252547);
    color: var(--text, #fff);
  }

  .lens-icon {
    font-size: 12px;
  }

  .lens-name {
    max-width: 100px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .view-toggle {
    display: flex;
    background: var(--surface-1, #0f0f1a);
    border-radius: 4px;
    overflow: hidden;
  }

  .toggle-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 24px;
    background: transparent;
    border: none;
    cursor: pointer;
    color: var(--text-muted, #888);
    transition: all 0.15s ease;
  }

  .toggle-btn:hover {
    background: var(--surface-3, #252547);
  }

  .toggle-btn.active {
    background: var(--accent, #6366f1);
    color: white;
  }

  .toggle-btn .icon {
    font-size: 12px;
  }
</style>
