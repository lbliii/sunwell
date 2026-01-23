<!--
  Code — Holy Light styled inline code (Svelte 5)
  
  Features:
  - Inline code styling
  - Copy button option
  - Color variants
-->
<script lang="ts">
  import type { Snippet } from 'svelte';
  
  interface Props {
    color?: 'default' | 'gold' | 'success' | 'error';
    copyable?: boolean;
    children: Snippet;
  }
  
  let {
    color = 'default',
    copyable = false,
    children,
  }: Props = $props();
  
  let copied = $state(false);
  let codeEl: HTMLElement | undefined = $state();
  
  async function copyToClipboard() {
    if (codeEl) {
      const text = codeEl.textContent || '';
      await navigator.clipboard.writeText(text);
      copied = true;
      setTimeout(() => copied = false, 2000);
    }
  }
</script>

<span class="code-wrapper">
  <code bind:this={codeEl} class="code {color}">
    {@render children()}
  </code>
  {#if copyable}
    <button 
      class="copy-btn" 
      onclick={copyToClipboard}
      aria-label={copied ? 'Copied!' : 'Copy to clipboard'}
      title={copied ? 'Copied!' : 'Copy'}
    >
      {copied ? '✓' : '⧉'}
    </button>
  {/if}
</span>

<style>
  .code-wrapper {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
  }
  
  /* ═══════════════════════════════════════════════════════════════
     CODE
     ═══════════════════════════════════════════════════════════════ */
  .code {
    font-family: var(--font-mono);
    font-size: 0.9em;
    padding: 0.1em 0.4em;
    background: var(--bg-tertiary);
    border-radius: var(--radius-sm);
    white-space: nowrap;
  }
  
  /* ═══════════════════════════════════════════════════════════════
     COLORS
     ═══════════════════════════════════════════════════════════════ */
  .default {
    color: var(--text-primary);
  }
  
  .gold {
    color: var(--text-gold);
    background: rgba(201, 162, 39, 0.1);
  }
  
  .success {
    color: var(--success);
    background: var(--success-bg);
  }
  
  .error {
    color: var(--error);
    background: var(--error-bg);
  }
  
  /* ═══════════════════════════════════════════════════════════════
     COPY BUTTON
     ═══════════════════════════════════════════════════════════════ */
  .copy-btn {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    padding: 2px 4px;
    border-radius: var(--radius-sm);
    transition: 
      color var(--transition-fast),
      background var(--transition-fast);
  }
  
  .copy-btn:hover {
    color: var(--text-gold);
    background: rgba(201, 162, 39, 0.1);
  }
  
  .copy-btn:focus-visible {
    outline: 2px solid var(--border-emphasis);
    outline-offset: 2px;
  }
</style>
