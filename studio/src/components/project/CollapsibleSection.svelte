<!--
  CollapsibleSection — RFC-106 reusable wrapper for progressive disclosure
  
  Wraps content in a collapsible details element with consistent styling.
-->
<script lang="ts">
  import type { Snippet } from 'svelte';
  
  interface Props {
    title: string;
    count?: number;
    open?: boolean;
    children: Snippet;
  }
  
  let { title, count, open = false, children }: Props = $props();
</script>

<details class="collapsible" {open}>
  <summary>
    <span class="title">{title}</span>
    {#if count !== undefined}
      <span class="count">({count})</span>
    {/if}
  </summary>
  <div class="content">
    {@render children()}
  </div>
</details>

<style>
  .collapsible {
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
  }
  
  .collapsible summary {
    padding: var(--space-3);
    cursor: pointer;
    user-select: none;
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--text-secondary);
    list-style: none;
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  
  .collapsible summary::-webkit-details-marker {
    display: none;
  }
  
  .collapsible summary::before {
    content: '▸';
    font-size: var(--text-xs);
    transition: transform var(--transition-fast);
  }
  
  .collapsible[open] summary::before {
    transform: rotate(90deg);
  }
  
  .collapsible summary:hover {
    background: var(--bg-secondary);
  }
  
  .title {
    flex: 1;
  }
  
  .count {
    color: var(--text-tertiary);
    font-weight: 400;
  }
  
  .content {
    padding: var(--space-3);
    border-top: 1px solid var(--border-color);
  }
</style>
