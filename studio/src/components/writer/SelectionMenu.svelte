<!--
  SelectionMenu.svelte — Floating action menu on text selection (RFC-086)
  
  Shows contextual actions when text is selected:
  - Quick skills (audit, polish, simplify)
  - Ask AI
  - Copy/Cut actions
-->
<script lang="ts">
  import { fly, fade } from 'svelte/transition';
  import { createEventDispatcher } from 'svelte';
  import {
    writerState,
    executeSkill,
    hideActionMenu,
    type SelectionContext,
  } from '../../stores';

  interface Props {
    /** Override values (optional - uses writer store by default) */
    selection?: SelectionContext | null;
    visible?: boolean;
    position?: { x: number; y: number };
    onAction?: (action: string, selection: SelectionContext) => void;
  }

  let {
    selection: propSelection,
    visible: propVisible,
    position: propPosition,
    onAction,
  }: Props = $props();

  // Use props if provided, otherwise use writer store
  const selection = $derived(propSelection ?? writerState.selection);
  const visible = $derived(propVisible ?? writerState.showActionMenu);

  let menuPosition = $state({ x: 0, y: 0 });

  // Update position when selection changes
  $effect(() => {
    if (propPosition) {
      menuPosition = propPosition;
    } else if (selection && typeof window !== 'undefined') {
      const sel = window.getSelection();
      if (sel && sel.rangeCount > 0) {
        const range = sel.getRangeAt(0);
        const rect = range.getBoundingClientRect();
        menuPosition = {
          x: rect.left + rect.width / 2,
          y: rect.top - 10,
        };
      }
    }
  });

  interface Action {
    id: string;
    label: string;
    icon: string;
    shortcut?: string;
  }

  const actions: Action[] = [
    { id: 'ask', label: 'Ask AI', icon: '✨', shortcut: '⌘K' },
    { id: 'audit', label: 'Audit', icon: '🔍' },
    { id: 'polish', label: 'Polish', icon: '✏️' },
    { id: 'simplify', label: 'Simplify', icon: '📉' },
    { id: 'expand', label: 'Expand', icon: '📈' },
  ];

  function handleAction(actionId: string) {
    if (!selection) return;

    if (onAction) {
      onAction(actionId, selection);
    } else {
      // Default behavior: execute as skill
      if (actionId === 'ask') {
        // Open AI dialog (would emit event)
      } else {
        executeSkill(actionId);
      }
    }

    hideActionMenu();
  }

  function handleClickOutside(e: MouseEvent) {
    const target = e.target as HTMLElement;
    if (!target.closest('.selection-menu')) {
      hideActionMenu();
    }
  }
</script>

<svelte:window onclick={handleClickOutside} />

{#if visible && selection}
  <div
    class="selection-menu"
    style="left: {menuPosition.x}px; top: {menuPosition.y}px;"
    transition:fly={{ y: 5, duration: 150 }}
  >
    <div class="menu-content">
      <!-- Selected text preview -->
      <div class="selection-preview">
        {#if selection.text.length > 40}
          "{selection.text.slice(0, 40)}..."
        {:else}
          "{selection.text}"
        {/if}
      </div>

      <!-- Action buttons -->
      <div class="actions">
        {#each actions as action}
          <button
            class="action-btn"
            onclick={() => handleAction(action.id)}
            title={action.shortcut ? `${action.label} (${action.shortcut})` : action.label}
          >
            <span class="action-icon">{action.icon}</span>
            <span class="action-label">{action.label}</span>
          </button>
        {/each}
      </div>

      <!-- Secondary actions -->
      <div class="secondary-actions">
        <button class="secondary-btn" onclick={() => handleAction('copy')}>
          📋 Copy
        </button>
        <button class="secondary-btn" onclick={() => handleAction('quote')}>
          💬 Quote
        </button>
      </div>
    </div>

    <!-- Arrow pointing to selection -->
    <div class="arrow"></div>
  </div>
{/if}

<style>
  .selection-menu {
    position: fixed;
    transform: translate(-50%, -100%);
    z-index: 1000;
    pointer-events: auto;
  }

  .menu-content {
    background: var(--bg-secondary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    padding: var(--space-2);
    box-shadow: var(--shadow-lg);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    min-width: 200px;
    max-width: 300px;
  }

  .selection-preview {
    padding: var(--space-1) var(--space-2);
    background: var(--bg-primary);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-size: var(--text-xs);
    margin-bottom: var(--space-2);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
    margin-bottom: var(--space-2);
    padding-bottom: var(--space-2);
    border-bottom: 1px solid var(--border-subtle);
  }

  .action-btn {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-1) var(--space-2);
    background: var(--bg-tertiary);
    border: none;
    border-radius: var(--radius-sm);
    cursor: pointer;
    font-family: inherit;
    font-size: inherit;
    color: var(--text-primary);
    transition: all var(--transition-fast);
  }

  .action-btn:hover {
    background: var(--accent-hover);
  }

  .action-btn:first-child {
    background: var(--ui-gold);
    color: var(--bg-primary);
  }

  .action-btn:first-child:hover {
    background: var(--ui-gold-soft);
  }

  .action-icon {
    font-size: var(--text-xs);
  }

  .action-label {
    font-weight: 500;
  }

  .secondary-actions {
    display: flex;
    gap: var(--space-1);
  }

  .secondary-btn {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-1);
    padding: var(--space-1) var(--space-2);
    background: transparent;
    border: 1px solid var(--border-default);
    border-radius: var(--radius-sm);
    cursor: pointer;
    font-family: inherit;
    font-size: var(--text-xs);
    color: var(--text-secondary);
    transition: all var(--transition-fast);
  }

  .secondary-btn:hover {
    background: var(--bg-tertiary);
    color: var(--text-primary);
  }

  .arrow {
    position: absolute;
    bottom: -6px;
    left: 50%;
    transform: translateX(-50%);
    width: 0;
    height: 0;
    border-left: 6px solid transparent;
    border-right: 6px solid transparent;
    border-top: 6px solid var(--bg-secondary);
  }
</style>
