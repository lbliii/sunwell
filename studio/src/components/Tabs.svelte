<!--
  Tabs — Accessible tablist component (Svelte 5)
  
  Implements WAI-ARIA tab pattern with full keyboard navigation:
  - Arrow keys to navigate between tabs
  - Home/End for first/last tab
  - Proper focus management
  - ARIA roles and attributes
-->
<script lang="ts">
  import type { Snippet } from 'svelte';
  import { handleArrowNavigation } from '$lib/a11y';
  
  interface Tab {
    id: string;
    label: string;
    icon?: string;
  }
  
  interface Props {
    tabs: Tab[];
    activeTab: string;
    onchange: (tabId: string) => void;
    children: Snippet<[string]>;
    label?: string;
  }
  
  let { 
    tabs, 
    activeTab, 
    onchange, 
    children, 
    label = 'Tabs' 
  }: Props = $props();
  
  function handleKeydown(e: KeyboardEvent, index: number) {
    const newIndex = handleArrowNavigation(e, index, tabs.length, {
      wrap: true,
      orientation: 'horizontal',
    });
    
    if (newIndex !== null) {
      onchange(tabs[newIndex].id);
      // Focus the new tab
      document.getElementById(`tab-${tabs[newIndex].id}`)?.focus();
    }
  }
</script>

<div class="tabs">
  <div class="tab-list" role="tablist" aria-label={label}>
    {#each tabs as tab, i}
      <button
        role="tab"
        id="tab-{tab.id}"
        aria-selected={activeTab === tab.id}
        aria-controls="panel-{tab.id}"
        tabindex={activeTab === tab.id ? 0 : -1}
        onclick={() => onchange(tab.id)}
        onkeydown={(e) => handleKeydown(e, i)}
        class="tab"
        class:active={activeTab === tab.id}
        type="button"
      >
        {#if tab.icon}
          <span class="tab-icon" aria-hidden="true">{tab.icon}</span>
        {/if}
        <span class="tab-label">{tab.label}</span>
      </button>
    {/each}
  </div>
  
  {#each tabs as tab}
    <div
      role="tabpanel"
      id="panel-{tab.id}"
      aria-labelledby="tab-{tab.id}"
      hidden={activeTab !== tab.id}
      tabindex={activeTab === tab.id ? 0 : -1}
      class="tab-panel"
    >
      {#if activeTab === tab.id}
        {@render children(tab.id)}
      {/if}
    </div>
  {/each}
</div>

<style>
  .tabs {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0; /* Allow shrinking below content size */
  }
  
  .tab-list {
    display: flex;
    gap: var(--space-1);
    border-bottom: 1px solid var(--border-color);
    padding-bottom: var(--space-2);
    flex-shrink: 0;
  }
  
  .tab {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-4);
    font-size: var(--text-sm);
    font-family: var(--font-mono);
    color: var(--text-tertiary);
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    cursor: pointer;
    transition: all var(--transition-fast);
    margin-bottom: -1px;
  }
  
  .tab:hover {
    color: var(--text-secondary);
  }
  
  .tab.active {
    color: var(--text-gold);
    border-bottom-color: var(--ui-gold);
  }
  
  .tab:focus-visible {
    outline: 2px solid rgba(201, 162, 39, 0.4);
    outline-offset: 2px;
  }
  
  .tab-icon {
    font-size: var(--text-base);
  }
  
  .tab-label {
    font-weight: 500;
  }
  
  .tab-panel {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: var(--space-4) 0;
    min-height: 0; /* Allow proper flex behavior */
  }
  
  .tab-panel[hidden] {
    display: none;
  }
  
  .tab-panel:focus-visible {
    outline: none;
  }
</style>
