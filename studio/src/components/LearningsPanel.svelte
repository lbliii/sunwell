<!--
  LearningsPanel — Shows what the agent is learning in real-time (Svelte 5)
  
  Combines a scrollable list of learnings with the MemoryGraph visualization.
  Appears during running and done states.
-->
<script lang="ts">
  import type { Concept } from '$lib/types';
  import MemoryGraph from './MemoryGraph.svelte';
  
  interface Props {
    learnings?: string[];
    concepts?: Concept[];
    collapsed?: boolean;
  }
  
  let { 
    learnings = [], 
    concepts = [], 
    collapsed = $bindable(false) 
  }: Props = $props();
  
  // Limit visible learnings for performance
  let visibleLearnings = $derived(learnings.slice(-15));
  let hiddenCount = $derived(Math.max(0, learnings.length - 15));
</script>

<div class="learnings-panel" class:collapsed>
  <!-- Header with toggle -->
  <button 
    class="panel-header" 
    onclick={() => collapsed = !collapsed}
    aria-expanded={!collapsed}
    type="button"
  >
    <span class="header-icon" aria-hidden="true">✧</span>
    <span class="header-title">Learnings</span>
    {#if learnings.length > 0}
      <span class="header-count">{learnings.length}</span>
    {/if}
    <span class="header-toggle" aria-hidden="true">{collapsed ? '▸' : '▾'}</span>
  </button>
  
  {#if !collapsed}
    <div class="panel-content">
      <!-- Learnings list -->
      <div class="learnings-list" role="list" aria-label="Learnings">
        {#if hiddenCount > 0}
          <div class="hidden-indicator">
            +{hiddenCount} earlier...
          </div>
        {/if}
        
        {#if visibleLearnings.length === 0}
          <div class="empty-state">
            Analyzing project...
          </div>
        {:else}
          <ul>
            {#each visibleLearnings as learning, i (learning + i)}
              <li 
                class="learning-item"
                style="animation-delay: {i * 30}ms"
              >
                {learning}
              </li>
            {/each}
          </ul>
        {/if}
      </div>
      
      <!-- Memory visualization -->
      <div class="memory-section">
        <MemoryGraph {concepts} />
      </div>
    </div>
  {/if}
</div>

<style>
  .learnings-panel {
    border-top: 1px solid var(--border-color);
    margin-top: var(--space-6);
    padding-top: var(--space-4);
  }
  
  .panel-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    padding: var(--space-2) 0;
    color: var(--text-secondary);
    font-size: var(--text-sm);
    transition: color var(--transition-fast);
    background: transparent;
    border: none;
    cursor: pointer;
    text-align: left;
  }
  
  .panel-header:hover {
    color: var(--text-primary);
  }
  
  .panel-header:focus-visible {
    outline: 2px solid rgba(201, 162, 39, 0.4);
    outline-offset: 2px;
  }
  
  .header-icon {
    font-size: var(--text-base);
  }
  
  .header-title {
    font-weight: 500;
  }
  
  .header-count {
    background: var(--bg-tertiary);
    color: var(--text-tertiary);
    font-size: var(--text-xs);
    padding: 2px 6px;
    border-radius: 10px;
    font-family: var(--font-mono);
  }
  
  .header-toggle {
    margin-left: auto;
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .panel-content {
    display: flex;
    gap: var(--space-6);
    padding: var(--space-3) 0;
    animation: slideDown 0.2s ease-out;
  }
  
  .learnings-list {
    flex: 1;
    min-width: 0;
  }
  
  .learnings-list ul {
    list-style: none;
    padding: 0;
    margin: 0;
    max-height: 150px;
    overflow-y: auto;
  }
  
  .hidden-indicator {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    padding: var(--space-1) 0;
    font-style: italic;
  }
  
  .empty-state {
    font-size: var(--text-sm);
    color: var(--text-tertiary);
    font-style: italic;
    padding: var(--space-2) 0;
  }
  
  .learning-item {
    font-size: var(--text-sm);
    color: var(--text-secondary);
    padding: var(--space-1) 0;
    padding-left: var(--space-3);
    position: relative;
    animation: slideIn 0.3s ease-out backwards;
    border-left: 2px solid transparent;
    transition: border-color var(--transition-fast);
  }
  
  .learning-item::before {
    content: '▸';
    position: absolute;
    left: 0;
    color: var(--accent);
    opacity: 0.6;
  }
  
  .learning-item:last-child {
    border-left-color: var(--accent);
  }
  
  .memory-section {
    flex-shrink: 0;
  }
  
  /* Collapsed state */
  .collapsed .panel-content {
    display: none;
  }
  
  @keyframes slideIn {
    from {
      opacity: 0;
      transform: translateX(10px);
    }
    to {
      opacity: 1;
      transform: translateX(0);
    }
  }
  
  @keyframes slideDown {
    from {
      opacity: 0;
      transform: translateY(-10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
  
  /* Scrollbar styling */
  .learnings-list ul::-webkit-scrollbar {
    width: 4px;
  }
  
  .learnings-list ul::-webkit-scrollbar-track {
    background: transparent;
  }
  
  .learnings-list ul::-webkit-scrollbar-thumb {
    background: var(--border-color);
    border-radius: 2px;
  }
</style>
