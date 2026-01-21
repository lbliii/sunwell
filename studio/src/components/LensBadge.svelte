<!--
  LensBadge — Shows active lens during execution (RFC-064)
  
  Displays a small badge indicating which lens is active.
  Can show "Auto" when auto-detect is enabled.
-->
<script lang="ts">
  import { lens } from '../stores/lens.svelte';
  
  interface Props {
    size?: 'sm' | 'md';
    showAuto?: boolean;
  }
  
  let { size = 'md', showAuto = true }: Props = $props();
  
  const displayName = $derived.by(() => {
    if (lens.activeLens) return lens.activeLens;
    if (lens.selection.autoSelect && showAuto) return 'Auto';
    if (lens.selection.lens) return lens.selection.lens;
    return null;
  });
</script>

{#if displayName}
  <div class="lens-badge" class:sm={size === 'sm'}>
    <span class="icon">🔮</span>
    <span class="name">{displayName}</span>
  </div>
{/if}

<style>
  .lens-badge {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-1) var(--space-2);
    background: var(--bg-secondary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-sm);
    font-size: var(--text-sm);
    color: var(--text-secondary);
    font-family: var(--font-mono);
  }
  
  .lens-badge.sm {
    padding: 2px var(--space-1);
    font-size: var(--text-xs);
  }
  
  .icon {
    font-size: 0.9em;
  }
  
  .name {
    font-weight: 500;
  }
</style>
