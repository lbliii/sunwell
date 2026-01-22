<!--
  ValidationBlock.svelte — Real-time feedback from lens validators (RFC-086)

  Shows warnings, errors, and suggestions as user writes.
  Collapsible; click warning to jump to line.
-->
<script lang="ts">
  import { fly, fade } from 'svelte/transition';
  import {
    writerState,
    dismissWarning,
    fixAllIssues,
    type ValidationWarning,
  } from '../../stores';

  interface Props {
    /** Override values (optional - uses writer store by default) */
    warnings?: ValidationWarning[];
    lensName?: string;
    isRunning?: boolean;
    onNavigate?: (line: number) => void;
    onFixAll?: () => void;
    onDismiss?: (warning: ValidationWarning) => void;
  }

  let {
    warnings: propWarnings,
    lensName: propLensName,
    isRunning: propIsRunning,
    onNavigate,
    onFixAll,
    onDismiss,
  }: Props = $props();

  // Use props if provided, otherwise use writer store
  const warnings = $derived(propWarnings ?? writerState.validationWarnings);
  const lensName = $derived(propLensName ?? writerState.lensName);
  const isRunning = $derived(propIsRunning ?? writerState.isValidating);

  function handleFixAll() {
    if (onFixAll) {
      onFixAll();
    } else {
      fixAllIssues();
    }
  }

  function handleDismissWarning(warning: ValidationWarning) {
    if (onDismiss) {
      onDismiss(warning);
    } else {
      dismissWarning(warning);
    }
  }

  let collapsed = $state(false);

  const warningCount = $derived(warnings.filter((w) => w.severity === 'warning').length);
  const errorCount = $derived(warnings.filter((w) => w.severity === 'error').length);
  const infoCount = $derived(warnings.filter((w) => w.severity === 'info').length);
  const totalCount = $derived(warnings.length);

  function handleWarningClick(warning: ValidationWarning) {
    onNavigate?.(warning.line);
  }

  function handleDismiss(e: MouseEvent, warning: ValidationWarning) {
    e.stopPropagation();
    handleDismissWarning(warning);
  }

  function getSeverityIcon(severity: string): string {
    switch (severity) {
      case 'error':
        return '❌';
      case 'warning':
        return '⚠️';
      case 'info':
        return '💡';
      default:
        return '•';
    }
  }
</script>

<div class="validation-block" class:collapsed>
  <button class="header" onclick={() => (collapsed = !collapsed)}>
    <span class="title">
      {#if isRunning}
        <span class="spinner">⟳</span>
      {:else}
        ✓
      {/if}
      Validation
    </span>
    <span class="counts">
      {#if errorCount > 0}
        <span class="error-count">❌ {errorCount}</span>
      {/if}
      {#if warningCount > 0}
        <span class="warning-count">⚠️ {warningCount}</span>
      {/if}
      {#if infoCount > 0}
        <span class="info-count">💡 {infoCount}</span>
      {/if}
      {#if totalCount === 0 && !isRunning}
        <span class="all-good">✅ All good</span>
      {/if}
    </span>
    <span class="lens-name">{lensName}</span>
    <span class="toggle">{collapsed ? '▶' : '▼'}</span>
  </button>

  {#if !collapsed}
    <div class="content" transition:fly={{ y: -10, duration: 150 }}>
      {#if warnings.length > 0 && errorCount > 0}
        <div class="actions">
          <button class="fix-all" onclick={handleFixAll}>Fix All ({errorCount + warningCount})</button>
        </div>
      {/if}

      <div class="warnings">
        {#each warnings as warning (warning.line + warning.rule)}
          <div
            class="warning-item {warning.severity}"
            onclick={() => handleWarningClick(warning)}
            onkeydown={(e) => e.key === 'Enter' && handleWarningClick(warning)}
            role="button"
            tabindex="0"
            transition:fade={{ duration: 100 }}
          >
            <span class="icon">{getSeverityIcon(warning.severity)}</span>
            <span class="line">L{warning.line}</span>
            <span class="message">{warning.message}</span>
            <span class="rule">{warning.rule}</span>
            {#if onDismiss}
              <button class="dismiss" onclick={(e) => handleDismiss(e, warning)}>✕</button>
            {/if}
          </div>
        {/each}

        {#if warnings.length === 0 && !isRunning}
          <div class="empty">
            <span class="icon">✨</span>
            No issues found
          </div>
        {/if}

        {#if isRunning}
          <div class="running">
            <span class="spinner">⟳</span>
            Validating...
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .validation-block {
    background: var(--surface-2, #1a1a2e);
    border-radius: 8px;
    overflow: hidden;
    font-family: var(--font-mono, 'JetBrains Mono', monospace);
    font-size: 12px;
  }

  .header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: var(--surface-3, #252547);
    cursor: pointer;
    border: none;
    width: 100%;
    text-align: left;
    color: inherit;
  }

  .header:hover {
    background: var(--surface-4, #2d2d5a);
  }

  .title {
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .spinner {
    animation: spin 1s linear infinite;
    display: inline-block;
  }

  @keyframes spin {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }

  .counts {
    display: flex;
    gap: 8px;
    flex: 1;
  }

  .error-count {
    color: var(--error, #ff6b6b);
  }

  .warning-count {
    color: var(--warning, #ffd93d);
  }

  .info-count {
    color: var(--info, #6bcbff);
  }

  .all-good {
    color: var(--success, #6bff6b);
  }

  .lens-name {
    color: var(--text-muted, #888);
    font-size: 10px;
  }

  .toggle {
    color: var(--text-muted, #888);
    font-size: 10px;
  }

  .content {
    padding: 8px;
  }

  .actions {
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border, #333);
    margin-bottom: 8px;
  }

  .fix-all {
    background: var(--accent, #6366f1);
    color: white;
    border: none;
    border-radius: 4px;
    padding: 4px 12px;
    font-size: 11px;
    cursor: pointer;
  }

  .fix-all:hover {
    background: var(--accent-hover, #4f46e5);
  }

  .warnings {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .warning-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 8px;
    border-radius: 4px;
    cursor: pointer;
    border: none;
    background: transparent;
    text-align: left;
    color: inherit;
    width: 100%;
  }

  .warning-item:hover {
    background: var(--surface-3, #252547);
  }

  .warning-item.error {
    background: rgba(255, 107, 107, 0.1);
  }

  .warning-item.error:hover {
    background: rgba(255, 107, 107, 0.2);
  }

  .warning-item.warning {
    background: rgba(255, 217, 61, 0.1);
  }

  .warning-item.warning:hover {
    background: rgba(255, 217, 61, 0.2);
  }

  .warning-item.info {
    background: rgba(107, 203, 255, 0.05);
  }

  .icon {
    flex-shrink: 0;
  }

  .line {
    color: var(--text-muted, #888);
    font-size: 10px;
    min-width: 32px;
  }

  .message {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .rule {
    color: var(--text-muted, #666);
    font-size: 10px;
    background: var(--surface-2, #1a1a2e);
    padding: 2px 6px;
    border-radius: 4px;
  }

  .dismiss {
    opacity: 0;
    background: none;
    border: none;
    color: var(--text-muted, #888);
    cursor: pointer;
    padding: 2px;
  }

  .warning-item:hover .dismiss {
    opacity: 1;
  }

  .empty,
  .running {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 16px;
    color: var(--text-muted, #888);
  }
</style>
