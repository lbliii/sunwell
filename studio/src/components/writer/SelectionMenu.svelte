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
    background: var(--surface-2, #1a1a2e);
    border: 1px solid var(--border, #333);
    border-radius: 8px;
    padding: 8px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    font-family: var(--font-mono, 'JetBrains Mono', monospace);
    font-size: 11px;
    min-width: 200px;
    max-width: 300px;
  }

  .selection-preview {
    padding: 6px 8px;
    background: var(--surface-1, #0f0f1a);
    border-radius: 4px;
    color: var(--text-muted, #888);
    font-size: 10px;
    margin-bottom: 8px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-bottom: 8px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border, #333);
  }

  .action-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px 8px;
    background: var(--surface-3, #252547);
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-family: inherit;
    font-size: inherit;
    color: var(--text, #fff);
    transition: all 0.15s ease;
  }

  .action-btn:hover {
    background: var(--accent, #6366f1);
  }

  .action-btn:first-child {
    background: var(--accent, #6366f1);
  }

  .action-btn:first-child:hover {
    background: var(--accent-hover, #4f46e5);
  }

  .action-icon {
    font-size: 12px;
  }

  .action-label {
    font-weight: 500;
  }

  .secondary-actions {
    display: flex;
    gap: 4px;
  }

  .secondary-btn {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 4px 8px;
    background: transparent;
    border: 1px solid var(--border, #333);
    border-radius: 4px;
    cursor: pointer;
    font-family: inherit;
    font-size: 10px;
    color: var(--text-muted, #888);
    transition: all 0.15s ease;
  }

  .secondary-btn:hover {
    background: var(--surface-3, #252547);
    color: var(--text, #fff);
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
    border-top: 6px solid var(--surface-2, #1a1a2e);
  }
</style>
