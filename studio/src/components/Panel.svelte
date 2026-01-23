<!--
  Panel — Holy Light styled panel/card component (Svelte 5)
  
  Supports active state with gold border glow and subtle aura.
  Used for sections, cards, and content areas.
-->
<script lang="ts">
  import type { Snippet } from 'svelte';
  import { uniqueId } from '$lib/a11y';
  
  interface Props {
    title?: string | null;
    icon?: string | null;
    collapsible?: boolean;
    collapsed?: boolean;
    padding?: boolean;
    active?: boolean;
    children: Snippet;
  }
  
  let { 
    title = null, 
    icon = null, 
    collapsible = false, 
    collapsed = $bindable(false), 
    padding = true, 
    active = false,
    children 
  }: Props = $props();
  
  const panelId = uniqueId('panel');
  const contentId = `${panelId}-content`;
  
  function toggle() {
    if (collapsible) {
      collapsed = !collapsed;
    }
  }
</script>

<div class="panel" class:collapsed class:no-padding={!padding} class:active>
  {#if active}
    <div class="panel-aura"></div>
  {/if}
  
  {#if title}
    <button 
      class="panel-header" 
      class:clickable={collapsible}
      onclick={toggle}
      type="button"
      aria-expanded={!collapsed}
      aria-controls={contentId}
    >
      {#if icon}
        <span class="panel-icon" aria-hidden="true">{icon}</span>
      {/if}
      <span class="panel-title">{title}</span>
      {#if collapsible}
        <span class="panel-chevron" class:rotated={collapsed} aria-hidden="true">▸</span>
      {/if}
    </button>
  {/if}
  
  {#if !collapsed}
    <div class="panel-content" id={contentId}>
      {@render children()}
    </div>
  {/if}
</div>

<style>
  .panel {
    background: var(--bg-secondary);
    border: 1px solid var(--accent-muted);
    border-radius: var(--radius-lg);
    overflow: hidden;
    position: relative;
    transition: 
      border-color var(--transition-fast),
      box-shadow var(--transition-fast);
  }
  
  /* ═══════════════════════════════════════════════════════════════
     ACTIVE STATE — Soft border with subtle glow
     ═══════════════════════════════════════════════════════════════ */
  .panel.active {
    border-color: var(--border-emphasis);
    box-shadow: var(--glow-gold-subtle);
  }
  
  .panel-aura {
    position: absolute;
    inset: 0;
    background: var(--gradient-aura);
    border-radius: inherit;
    pointer-events: none;
    z-index: 0;
  }
  
  /* ═══════════════════════════════════════════════════════════════
     HEADER
     ═══════════════════════════════════════════════════════════════ */
  .panel-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    padding: var(--space-3) var(--space-4);
    background: transparent;
    border: none;
    border-bottom: var(--border-width) solid var(--border-color);
    color: var(--text-primary);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: 500;
    text-align: left;
    cursor: default;
    position: relative;
    z-index: 1;
  }
  
  .active .panel-header {
    border-bottom-color: var(--border-default);
  }
  
  .panel-header.clickable {
    cursor: pointer;
    transition: background var(--transition-fast);
  }
  
  .panel-header.clickable:hover {
    background: var(--bg-tertiary);
  }
  
  .active .panel-header.clickable:hover {
    background: rgba(201, 162, 39, 0.04);
  }
  
  .panel-header:focus-visible {
    outline: 2px solid var(--ui-gold-soft);
    outline-offset: -2px;
  }
  
  .panel-icon {
    font-size: var(--text-base);
  }
  
  .active .panel-icon {
    color: var(--text-gold);
  }
  
  .panel-title {
    flex: 1;
  }
  
  .active .panel-title {
    color: var(--text-gold);
  }
  
  .panel-chevron {
    color: var(--text-tertiary);
    font-size: var(--text-sm);
    transition: transform var(--transition-fast);
    transform: rotate(90deg);
  }
  
  .panel-chevron.rotated {
    transform: rotate(0deg);
  }
  
  .active .panel-chevron {
    color: var(--ui-gold-soft);
  }
  
  /* ═══════════════════════════════════════════════════════════════
     CONTENT
     ═══════════════════════════════════════════════════════════════ */
  .panel-content {
    padding: var(--space-4);
    position: relative;
    z-index: 1;
  }
  
  .no-padding .panel-content {
    padding: 0;
  }
  
  .collapsed .panel-header {
    border-bottom: none;
  }
</style>
