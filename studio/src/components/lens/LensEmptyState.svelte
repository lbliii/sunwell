<!--
  LensEmptyState — Illustrated empty state for lens library (RFC-100)
  
  Shows when no lenses match the current filter, with actionable CTAs.
-->
<script lang="ts">
  import { fade } from 'svelte/transition';
  import Button from '../Button.svelte';
  import SparkleField from '../ui/SparkleField.svelte';
  
  interface Props {
    hasFilters: boolean;
    searchQuery?: string;
    onClearFilters?: () => void;
    onCreateLens?: () => void;
    onBrowseExamples?: () => void;
  }
  
  let { 
    hasFilters, 
    searchQuery = '', 
    onClearFilters, 
    onCreateLens, 
    onBrowseExamples 
  }: Props = $props();
</script>

<div class="empty-state" in:fade={{ duration: 200 }}>
  <div class="empty-illustration">
    <SparkleField width={16} height={6} density={0.15} speed={250} />
    <span class="empty-orb">🔮</span>
  </div>
  
  {#if hasFilters}
    <h3>No lenses match "{searchQuery}"</h3>
    <p>Try a different search term or clear your filters</p>
    {#if onClearFilters}
      <Button 
        variant="secondary"
        onclick={onClearFilters}
      >
        Clear Filters
      </Button>
    {/if}
  {:else}
    <h3>No Lenses Yet</h3>
    <p>Lenses give Sunwell specialized expertise for different tasks</p>
    <div class="empty-actions">
      {#if onCreateLens}
        <Button variant="primary" onclick={onCreateLens}>
          ✨ Create Your First Lens
        </Button>
      {/if}
      {#if onBrowseExamples}
        <Button variant="ghost" onclick={onBrowseExamples}>
          Browse Examples
        </Button>
      {/if}
    </div>
  {/if}
</div>

<style>
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: var(--space-12);
    min-height: 300px;
  }
  
  .empty-illustration {
    position: relative;
    width: 200px;
    height: 120px;
    margin-bottom: var(--space-6);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  
  .empty-orb {
    position: absolute;
    font-size: 48px;
    animation: orbFloat 3s ease-in-out infinite;
    filter: drop-shadow(0 0 20px var(--radiant-gold-30));
  }
  
  @keyframes orbFloat {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-8px); }
  }
  
  @media (prefers-reduced-motion: reduce) {
    .empty-orb { animation: none; }
  }
  
  .empty-state h3 {
    font-size: var(--text-xl);
    color: var(--text-primary);
    margin: 0 0 var(--space-2);
  }
  
  .empty-state p {
    font-size: var(--text-base);
    color: var(--text-secondary);
    margin: 0 0 var(--space-6);
    max-width: 400px;
  }
  
  .empty-actions {
    display: flex;
    gap: var(--space-3);
    flex-wrap: wrap;
    justify-content: center;
  }
</style>
