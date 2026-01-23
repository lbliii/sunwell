<!--
  Link — Holy Light styled anchor (Svelte 5)
  
  Features:
  - Gold hover state
  - External link indicator
  - Underline variants
-->
<script lang="ts">
  import type { Snippet } from 'svelte';
  
  interface Props {
    href: string;
    external?: boolean;
    underline?: 'always' | 'hover' | 'none';
    color?: 'default' | 'gold' | 'secondary';
    children: Snippet;
  }
  
  let {
    href,
    external = false,
    underline = 'hover',
    color = 'default',
    children,
  }: Props = $props();
  
  // Auto-detect external links
  const isExternal = $derived(external || (href.startsWith('http') && !href.includes(window.location.hostname)));
</script>

<a 
  {href}
  class="link {color} underline-{underline}"
  target={isExternal ? '_blank' : undefined}
  rel={isExternal ? 'noopener noreferrer' : undefined}
>
  {@render children()}
  {#if isExternal}
    <span class="external-icon" aria-label="(opens in new tab)">↗</span>
  {/if}
</a>

<style>
  .link {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    font-family: inherit;
    transition: color var(--transition-fast);
  }
  
  /* ═══════════════════════════════════════════════════════════════
     COLORS
     ═══════════════════════════════════════════════════════════════ */
  .default {
    color: var(--text-primary);
  }
  
  .default:hover {
    color: var(--text-gold);
  }
  
  .gold {
    color: var(--text-gold);
  }
  
  .gold:hover {
    color: var(--radiant-gold);
  }
  
  .secondary {
    color: var(--text-secondary);
  }
  
  .secondary:hover {
    color: var(--text-primary);
  }
  
  /* ═══════════════════════════════════════════════════════════════
     UNDERLINE
     ═══════════════════════════════════════════════════════════════ */
  .underline-always {
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  
  .underline-hover {
    text-decoration: none;
  }
  
  .underline-hover:hover {
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  
  .underline-none {
    text-decoration: none;
  }
  
  /* ═══════════════════════════════════════════════════════════════
     FOCUS
     ═══════════════════════════════════════════════════════════════ */
  .link:focus-visible {
    outline: 2px solid var(--border-emphasis);
    outline-offset: 2px;
    border-radius: var(--radius-sm);
  }
  
  /* ═══════════════════════════════════════════════════════════════
     EXTERNAL ICON
     ═══════════════════════════════════════════════════════════════ */
  .external-icon {
    font-size: 0.8em;
    opacity: 0.7;
  }
</style>
