<!--
  Panel — Reusable panel/card component
  
  Used for sections, cards, and content areas.
-->
<script lang="ts">
  export let title: string | null = null;
  export let icon: string | null = null;
  export let collapsible = false;
  export let collapsed = false;
  export let padding = true;
  
  function toggle() {
    if (collapsible) {
      collapsed = !collapsed;
    }
  }
</script>

<div class="panel" class:collapsed class:no-padding={!padding}>
  {#if title}
    <button 
      class="panel-header" 
      class:clickable={collapsible}
      on:click={toggle}
      type="button"
      aria-expanded={!collapsed}
    >
      {#if icon}
        <span class="panel-icon">{icon}</span>
      {/if}
      <span class="panel-title">{title}</span>
      {#if collapsible}
        <span class="panel-chevron" class:rotated={collapsed}>›</span>
      {/if}
    </button>
  {/if}
  
  {#if !collapsed}
    <div class="panel-content">
      <slot />
    </div>
  {/if}
</div>

<style>
  .panel {
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    overflow: hidden;
  }
  
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
  }
  
  .panel-header.clickable {
    cursor: pointer;
    transition: background var(--transition-fast);
  }
  
  .panel-header.clickable:hover {
    background: var(--bg-tertiary);
  }
  
  .panel-icon {
    font-size: var(--text-base);
  }
  
  .panel-title {
    flex: 1;
  }
  
  .panel-chevron {
    color: var(--text-tertiary);
    font-size: var(--text-lg);
    transition: transform var(--transition-fast);
    transform: rotate(90deg);
  }
  
  .panel-chevron.rotated {
    transform: rotate(0deg);
  }
  
  .panel-content {
    padding: var(--space-4);
  }
  
  .no-padding .panel-content {
    padding: 0;
  }
  
  .collapsed .panel-header {
    border-bottom: none;
  }
</style>
