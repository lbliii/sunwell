<!--
  LensHoverPreview — Hover popover showing lens heuristics (RFC-100)
  
  Appears after a delay when hovering a lens card.
-->
<script lang="ts">
  import { fly } from 'svelte/transition';
  import type { LensLibraryEntry, HeuristicSummary } from '$lib/types';
  import Button from '../Button.svelte';
  
  interface Props {
    lens: LensLibraryEntry;
    topHeuristics?: HeuristicSummary[];
    onQuickTest?: () => void;
    onView?: () => void;
  }
  
  let { lens, topHeuristics = [], onQuickTest, onView }: Props = $props();
</script>

<div 
  class="preview-popover"
  in:fly={{ y: 8, duration: 150 }}
  role="tooltip"
>
  <div class="preview-arrow"></div>
  
  <div class="preview-header">
    <span class="preview-title">Top Heuristics</span>
    <span class="preview-count">{lens.heuristics_count} total</span>
  </div>
  
  {#if topHeuristics.length > 0}
    <ul class="preview-heuristics">
      {#each topHeuristics.slice(0, 3) as h (h.name)}
        <li>
          <span 
            class="priority-dot" 
            style="--priority: {h.priority}"
          ></span>
          <span class="heuristic-name">{h.name}</span>
        </li>
      {/each}
    </ul>
  {:else}
    <p class="no-preview">Hover preview data not available</p>
  {/if}
  
  {#if lens.skills_count > 0}
    <div class="preview-skills">
      <span class="skills-label">Skills:</span>
      <span class="skills-count">{lens.skills_count}</span>
    </div>
  {/if}
  
  <div class="preview-actions">
    {#if onQuickTest}
      <Button size="sm" variant="ghost" onclick={onQuickTest}>
        ⚡ Test
      </Button>
    {/if}
    {#if onView}
      <Button size="sm" variant="ghost" onclick={onView}>
        View →
      </Button>
    {/if}
  </div>
</div>

<style>
  .preview-popover {
    position: absolute;
    top: calc(100% + var(--space-2));
    left: 50%;
    transform: translateX(-50%);
    width: 260px;
    background: var(--bg-elevated);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    padding: var(--space-3);
    box-shadow: var(--shadow-lg), var(--glow-gold-subtle);
    z-index: var(--z-dropdown);
  }
  
  .preview-arrow {
    position: absolute;
    top: -6px;
    left: 50%;
    transform: translateX(-50%) rotate(45deg);
    width: 12px;
    height: 12px;
    background: var(--bg-elevated);
    border-top: 1px solid var(--border-default);
    border-left: 1px solid var(--border-default);
  }
  
  .preview-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-2);
  }
  
  .preview-title {
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .preview-count {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .preview-heuristics {
    list-style: none;
    padding: 0;
    margin: 0 0 var(--space-2);
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  
  .preview-heuristics li {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-sm);
    color: var(--text-secondary);
  }
  
  .priority-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: color-mix(
      in oklch,
      var(--ui-gold-pale) calc(100% - var(--priority, 0.5) * 100%),
      var(--radiant-gold) calc(var(--priority, 0.5) * 100%)
    );
    flex-shrink: 0;
  }
  
  .heuristic-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .no-preview {
    font-size: var(--text-sm);
    color: var(--text-tertiary);
    margin: var(--space-2) 0;
  }
  
  .preview-skills {
    display: flex;
    gap: var(--space-2);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    margin-bottom: var(--space-2);
    padding-top: var(--space-2);
    border-top: 1px solid var(--border-subtle);
  }
  
  .preview-actions {
    display: flex;
    gap: var(--space-2);
    justify-content: flex-end;
    padding-top: var(--space-2);
    border-top: 1px solid var(--border-subtle);
  }
</style>
