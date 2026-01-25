<!--
  LensHeroCard — Featured lens card with enhanced visual presence (RFC-100)
  
  Used in the Featured section for recommended/default lenses.
-->
<script lang="ts">
  import type { LensLibraryEntry } from '$lib/types';
  import LensCardMotes from './LensCardMotes.svelte';
  
  interface Props {
    lens: LensLibraryEntry;
    index?: number;
    onclick?: () => void;
  }
  
  let { lens, index = 0, onclick }: Props = $props();
  
  let motesComponent: LensCardMotes;
  
  function getDomainIcon(domain: string | null): string {
    const icons: Record<string, string> = {
      'software': '💻',
      'code': '💻',
      'documentation': '📝',
      'review': '🔍',
      'test': '🧪',
      'general': '🔮',
    };
    return icons[domain || 'general'] || '🔮';
  }
  
  function handleMouseEnter(e: MouseEvent) {
    motesComponent?.spawnMotes(e);
  }
</script>

<button 
  class="hero-card"
  class:is-default={lens.is_default}
  style="--index: {index}"
  onclick={onclick}
  onmouseenter={handleMouseEnter}
>
  <LensCardMotes bind:this={motesComponent} />
  
  <div class="hero-header">
    <span class="hero-icon">{getDomainIcon(lens.domain)}</span>
    {#if lens.is_default}
      <span class="default-badge">Default</span>
    {:else}
      <span class="featured-badge">Featured</span>
    {/if}
  </div>
  
  <h3 class="hero-title">{lens.name}</h3>
  
  <p class="hero-description">
    {lens.description || 'No description'}
  </p>
  
  <div class="hero-stats">
    <span class="stat">
      <span class="stat-value">{lens.heuristics_count}</span>
      <span class="stat-label">Heuristics</span>
    </span>
    <span class="stat">
      <span class="stat-value">{lens.skills_count}</span>
      <span class="stat-label">Skills</span>
    </span>
  </div>
  
  {#if lens.tags.length > 0}
    <div class="hero-tags">
      {#each lens.tags.slice(0, 3) as tag (tag)}
        <span class="tag">{tag}</span>
      {/each}
    </div>
  {/if}
</button>

<style>
  .hero-card {
    position: relative;
    background: linear-gradient(
      135deg,
      var(--bg-secondary) 0%,
      var(--bg-tertiary) 100%
    );
    border: 1px solid var(--border-default);
    border-radius: var(--radius-xl);
    padding: var(--space-5);
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    cursor: pointer;
    text-align: left;
    transition: all var(--transition-normal);
    animation: heroReveal 0.5s ease-out backwards;
    animation-delay: calc(var(--index) * 100ms);
    overflow: hidden;
  }
  
  @keyframes heroReveal {
    from {
      opacity: 0;
      transform: translateY(16px) scale(0.96);
    }
    to {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }
  
  .hero-card:hover {
    transform: translateY(-4px);
    border-color: var(--ui-gold-soft);
    box-shadow: var(--shadow-lg), var(--glow-gold);
  }
  
  .hero-card.is-default {
    border-color: var(--ui-gold);
    background: linear-gradient(
      135deg,
      var(--accent-hover) 0%,
      var(--bg-secondary) 100%
    );
  }
  
  .hero-card.is-default::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: var(--gradient-ui-gold);
  }
  
  .hero-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  
  .hero-icon {
    font-size: 2rem;
    filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3));
  }
  
  .default-badge,
  .featured-badge {
    font-size: var(--text-xs);
    padding: 3px 8px;
    border-radius: var(--radius-full);
    font-weight: 500;
  }
  
  .default-badge {
    background: var(--ui-gold);
    color: var(--bg-primary);
  }
  
  .featured-badge {
    background: var(--bg-tertiary);
    color: var(--text-secondary);
    border: 1px solid var(--border-subtle);
  }
  
  .hero-title {
    font-size: var(--text-lg);
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
  }
  
  .hero-description {
    font-size: var(--text-sm);
    color: var(--text-secondary);
    margin: 0;
    line-height: var(--leading-normal);
    flex: 1;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  
  .hero-stats {
    display: flex;
    gap: var(--space-4);
    padding-top: var(--space-3);
    border-top: 1px solid var(--border-subtle);
  }
  
  .stat {
    display: flex;
    flex-direction: column;
  }
  
  .stat-value {
    font-size: var(--text-lg);
    font-weight: 600;
    color: var(--ui-gold);
  }
  
  .stat-label {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  
  .hero-tags {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  
  .tag {
    font-size: var(--text-xs);
    padding: 2px 8px;
    background: var(--bg-tertiary);
    border-radius: var(--radius-full);
    color: var(--text-secondary);
  }
  
  @media (prefers-reduced-motion: reduce) {
    .hero-card { animation: none; }
  }
</style>
