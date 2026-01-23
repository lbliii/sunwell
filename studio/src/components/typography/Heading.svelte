<!--
  Heading — Holy Light styled headings (Svelte 5)
  
  Features:
  - h1-h6 with consistent sizing
  - Optional gold accent color
  - Truncation support
  - Monospace variant
-->
<script lang="ts">
  import type { Snippet } from 'svelte';
  
  interface Props {
    level?: 1 | 2 | 3 | 4 | 5 | 6;
    color?: 'default' | 'gold' | 'secondary' | 'tertiary';
    mono?: boolean;
    truncate?: boolean;
    children: Snippet;
  }
  
  let {
    level = 2,
    color = 'default',
    mono = false,
    truncate = false,
    children,
  }: Props = $props();
</script>

{#if level === 1}
  <h1 class="heading h1 {color}" class:mono class:truncate>{@render children()}</h1>
{:else if level === 2}
  <h2 class="heading h2 {color}" class:mono class:truncate>{@render children()}</h2>
{:else if level === 3}
  <h3 class="heading h3 {color}" class:mono class:truncate>{@render children()}</h3>
{:else if level === 4}
  <h4 class="heading h4 {color}" class:mono class:truncate>{@render children()}</h4>
{:else if level === 5}
  <h5 class="heading h5 {color}" class:mono class:truncate>{@render children()}</h5>
{:else}
  <h6 class="heading h6 {color}" class:mono class:truncate>{@render children()}</h6>
{/if}

<style>
  .heading {
    font-family: var(--font-sans);
    font-weight: 600;
    line-height: var(--leading-tight);
    margin: 0;
  }
  
  /* ═══════════════════════════════════════════════════════════════
     SIZES
     ═══════════════════════════════════════════════════════════════ */
  .h1 {
    font-size: var(--text-3xl);
    letter-spacing: -0.02em;
  }
  
  .h2 {
    font-size: var(--text-2xl);
    letter-spacing: -0.01em;
  }
  
  .h3 {
    font-size: var(--text-xl);
  }
  
  .h4 {
    font-size: var(--text-lg);
  }
  
  .h5 {
    font-size: var(--text-base);
  }
  
  .h6 {
    font-size: var(--text-sm);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  
  /* ═══════════════════════════════════════════════════════════════
     COLORS
     ═══════════════════════════════════════════════════════════════ */
  .default {
    color: var(--text-primary);
  }
  
  .gold {
    color: var(--text-gold);
  }
  
  .secondary {
    color: var(--text-secondary);
  }
  
  .tertiary {
    color: var(--text-tertiary);
  }
  
  /* ═══════════════════════════════════════════════════════════════
     VARIANTS
     ═══════════════════════════════════════════════════════════════ */
  .mono {
    font-family: var(--font-mono);
    font-weight: 500;
  }
  
  .truncate {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
