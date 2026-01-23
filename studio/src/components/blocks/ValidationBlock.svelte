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
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    overflow: hidden;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
  }

  .header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    background: var(--bg-tertiary);
    cursor: pointer;
    border: none;
    width: 100%;
    text-align: left;
    color: inherit;
    transition: background var(--transition-fast);
  }

  .header:hover {
    background: var(--accent-hover);
  }

  .title {
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: var(--space-1);
  }

  .spinner {
    animation: spin 1s linear infinite;
    display: inline-block;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  .counts {
    display: flex;
    gap: var(--space-2);
    flex: 1;
  }

  .error-count { color: var(--error); }
  .warning-count { color: var(--warning); }
  .info-count { color: var(--info); }
  .all-good { color: var(--success); }

  .lens-name {
    color: var(--text-secondary);
    font-size: var(--text-xs);
  }

  .toggle {
    color: var(--text-secondary);
    font-size: var(--text-xs);
  }

  .content {
    padding: var(--space-2);
  }

  .actions {
    padding-bottom: var(--space-2);
    border-bottom: 1px solid var(--border-subtle);
    margin-bottom: var(--space-2);
  }

  .fix-all {
    background: var(--ui-gold);
    color: var(--bg-primary);
    border: none;
    border-radius: var(--radius-sm);
    padding: var(--space-1) var(--space-3);
    font-size: var(--text-xs);
    cursor: pointer;
    transition: background var(--transition-fast);
  }

  .fix-all:hover {
    background: var(--ui-gold-soft);
  }

  .warnings {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .warning-item {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    cursor: pointer;
    border: none;
    background: transparent;
    text-align: left;
    color: inherit;
    width: 100%;
    transition: background var(--transition-fast);
  }

  .warning-item:hover {
    background: var(--bg-tertiary);
  }

  .warning-item.error {
    background: var(--error-bg);
  }

  .warning-item.error:hover {
    background: rgba(239, 68, 68, 0.2);
  }

  .warning-item.warning {
    background: var(--warning-bg);
  }

  .warning-item.warning:hover {
    background: rgba(245, 158, 11, 0.2);
  }

  .warning-item.info {
    background: var(--info-bg);
  }

  .icon {
    flex-shrink: 0;
  }

  .line {
    color: var(--text-secondary);
    font-size: var(--text-xs);
    min-width: 32px;
  }

  .message {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .rule {
    color: var(--text-tertiary);
    font-size: var(--text-xs);
    background: var(--bg-secondary);
    padding: var(--space-px) var(--space-1);
    border-radius: var(--radius-sm);
  }

  .dismiss {
    opacity: 0;
    background: none;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    padding: var(--space-px);
    transition: opacity var(--transition-fast);
  }

  .warning-item:hover .dismiss {
    opacity: 1;
  }

  .empty,
  .running {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    padding: var(--space-4);
    color: var(--text-secondary);
  }
</style>
