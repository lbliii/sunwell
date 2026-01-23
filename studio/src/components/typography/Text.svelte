<!--
  Text — Holy Light styled text component (Svelte 5)
  
  Features:
  - Size variants (xs, sm, base, lg, xl)
  - Color variants (primary, secondary, tertiary, gold, error, success)
  - Font variants (mono, sans, serif)
  - Weight variants (normal, medium, semibold, bold)
  - Inline or block display
-->
<script lang="ts">
  import type { Snippet } from 'svelte';
  
  interface Props {
    as?: 'p' | 'span' | 'div';
    size?: 'xs' | 'sm' | 'base' | 'lg' | 'xl';
    color?: 'primary' | 'secondary' | 'tertiary' | 'gold' | 'error' | 'success' | 'warning';
    font?: 'mono' | 'sans' | 'serif';
    weight?: 'normal' | 'medium' | 'semibold' | 'bold';
    leading?: 'tight' | 'normal' | 'relaxed' | 'prose';
    truncate?: boolean;
    clamp?: number;
    children: Snippet;
  }
  
  let {
    as = 'p',
    size = 'base',
    color = 'primary',
    font = 'mono',
    weight = 'normal',
    leading = 'normal',
    truncate = false,
    clamp,
    children,
  }: Props = $props();
  
  const lineClampStyle = $derived(clamp ? `display: -webkit-box; -webkit-line-clamp: ${clamp}; -webkit-box-orient: vertical; overflow: hidden;` : '');
</script>

{#if as === 'span'}
  <span 
    class="text size-{size} color-{color} font-{font} weight-{weight} leading-{leading}"
    class:truncate
    style={lineClampStyle}
  >
    {@render children()}
  </span>
{:else if as === 'div'}
  <div 
    class="text size-{size} color-{color} font-{font} weight-{weight} leading-{leading}"
    class:truncate
    style={lineClampStyle}
  >
    {@render children()}
  </div>
{:else}
  <p 
    class="text size-{size} color-{color} font-{font} weight-{weight} leading-{leading}"
    class:truncate
    style={lineClampStyle}
  >
    {@render children()}
  </p>
{/if}

<style>
  .text {
    margin: 0;
  }
  
  /* ═══════════════════════════════════════════════════════════════
     SIZES
     ═══════════════════════════════════════════════════════════════ */
  .size-xs { font-size: var(--text-xs); }
  .size-sm { font-size: var(--text-sm); }
  .size-base { font-size: var(--text-base); }
  .size-lg { font-size: var(--text-lg); }
  .size-xl { font-size: var(--text-xl); }
  
  /* ═══════════════════════════════════════════════════════════════
     COLORS
     ═══════════════════════════════════════════════════════════════ */
  .color-primary { color: var(--text-primary); }
  .color-secondary { color: var(--text-secondary); }
  .color-tertiary { color: var(--text-tertiary); }
  .color-gold { color: var(--text-gold); }
  .color-error { color: var(--error); }
  .color-success { color: var(--success); }
  .color-warning { color: var(--warning); }
  
  /* ═══════════════════════════════════════════════════════════════
     FONTS
     ═══════════════════════════════════════════════════════════════ */
  .font-mono { font-family: var(--font-mono); }
  .font-sans { font-family: var(--font-sans); }
  .font-serif { font-family: var(--font-serif); }
  
  /* ═══════════════════════════════════════════════════════════════
     WEIGHTS
     ═══════════════════════════════════════════════════════════════ */
  .weight-normal { font-weight: 400; }
  .weight-medium { font-weight: 500; }
  .weight-semibold { font-weight: 600; }
  .weight-bold { font-weight: 700; }
  
  /* ═══════════════════════════════════════════════════════════════
     LINE HEIGHT
     ═══════════════════════════════════════════════════════════════ */
  .leading-tight { line-height: var(--leading-tight); }
  .leading-normal { line-height: var(--leading-normal); }
  .leading-relaxed { line-height: var(--leading-relaxed); }
  .leading-prose { line-height: var(--leading-prose); }
  
  /* ═══════════════════════════════════════════════════════════════
     TRUNCATE
     ═══════════════════════════════════════════════════════════════ */
  .truncate {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
