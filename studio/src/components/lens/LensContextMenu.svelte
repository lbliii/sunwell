<!--
  LensContextMenu — Right-click context menu for lens cards (RFC-100)
-->
<script lang="ts">
  import { fly } from 'svelte/transition';
  import type { LensLibraryEntry } from '$lib/types';
  
  interface Props {
    lens: LensLibraryEntry;
    x: number;
    y: number;
    onView: () => void;
    onFork: () => void;
    onEdit?: () => void;
    onSetDefault?: () => void;
    onExport?: () => void;
    onClose: () => void;
  }
  
  let { lens, x, y, onView, onFork, onEdit, onSetDefault, onExport, onClose }: Props = $props();
  
  function handleAction(action: () => void) {
    action();
    onClose();
  }
</script>

<svelte:window onclick={onClose} onkeydown={(e) => e.key === 'Escape' && onClose()} />

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<!-- svelte-ignore a11y_interactive_supports_focus -->
<div 
  class="context-menu"
  style="top: {y}px; left: {x}px"
  in:fly={{ y: -8, duration: 100 }}
  role="menu"
  onclick={(e) => e.stopPropagation()}
  onkeydown={(e) => e.key === 'Escape' && onClose()}
>
  <button class="menu-item" onclick={() => handleAction(onView)} role="menuitem">
    <span class="menu-icon">👁</span>
    <span class="menu-label">View Details</span>
    <span class="menu-shortcut">Enter</span>
  </button>
  
  <button class="menu-item" onclick={() => handleAction(onFork)} role="menuitem">
    <span class="menu-icon">🔱</span>
    <span class="menu-label">Fork</span>
    <span class="menu-shortcut">f</span>
  </button>
  
  {#if lens.is_editable && onEdit}
    <button class="menu-item" onclick={() => handleAction(onEdit)} role="menuitem">
      <span class="menu-icon">✏️</span>
      <span class="menu-label">Edit</span>
      <span class="menu-shortcut">e</span>
    </button>
  {/if}
  
  <hr class="menu-divider" />
  
  {#if !lens.is_default && onSetDefault}
    <button class="menu-item" onclick={() => handleAction(onSetDefault)} role="menuitem">
      <span class="menu-icon">⭐</span>
      <span class="menu-label">Set as Default</span>
      <span class="menu-shortcut">d</span>
    </button>
  {/if}
  
  {#if onExport}
    <button class="menu-item" onclick={() => handleAction(onExport)} role="menuitem">
      <span class="menu-icon">📤</span>
      <span class="menu-label">Export</span>
    </button>
  {/if}
</div>

<style>
  .context-menu {
    position: fixed;
    background: var(--bg-elevated);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-lg);
    min-width: 200px;
    padding: var(--space-1);
    z-index: var(--z-dropdown);
  }
  
  .menu-item {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    padding: var(--space-2) var(--space-3);
    background: transparent;
    border: none;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-size: var(--text-sm);
    cursor: pointer;
    transition: all var(--transition-fast);
    text-align: left;
  }
  
  .menu-item:hover {
    background: var(--accent-hover);
    color: var(--text-primary);
  }
  
  .menu-icon {
    width: 20px;
    text-align: center;
    flex-shrink: 0;
  }
  
  .menu-label {
    flex: 1;
  }
  
  .menu-shortcut {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    padding: 2px 6px;
    background: var(--bg-tertiary);
    border-radius: var(--radius-sm);
    font-family: var(--font-mono);
  }
  
  .menu-divider {
    border: none;
    border-top: 1px solid var(--border-subtle);
    margin: var(--space-1) 0;
  }
</style>
