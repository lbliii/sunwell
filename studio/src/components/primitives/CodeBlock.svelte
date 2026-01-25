<!--
  CodeBlock.svelte — Syntax-highlighted code display (RFC-097)
  
  Features:
  - Lazy-loaded Shiki syntax highlighting with Holy Light theme
  - Copy button on hover
  - Optional line numbers
  - Language indicator
  - Graceful fallback to plain text
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { fade, fly } from 'svelte/transition';
  import { highlight, preloadHighlighter, isHighlighterReady } from '../../lib/syntax';

  interface Props {
    code: string;
    language?: string;
    filename?: string;
    showLineNumbers?: boolean;
    maxHeight?: string;
  }

  let {
    code,
    language = 'text',
    filename = '',
    showLineNumbers = false,
    maxHeight = 'none',
  }: Props = $props();

  let highlightedHtml = $state<string | null>(null);
  let copied = $state(false);
  let hovering = $state(false);

  // Highlight code on mount and when code/language changes
  $effect(() => {
    highlightCode(code, language);
  });

  async function highlightCode(codeToHighlight: string, lang: string) {
    try {
      highlightedHtml = await highlight(codeToHighlight, lang);
    } catch {
      // Fallback to plain text
      highlightedHtml = null;
    }
  }

  // Preload highlighter early
  onMount(() => {
    if (!isHighlighterReady()) {
      preloadHighlighter();
    }
  });

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(code);
      copied = true;
      setTimeout(() => {
        copied = false;
      }, 2000);
    } catch {
      // Clipboard API not available
    }
  }

  // Add line numbers to highlighted code (reserved for future use)
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  function _addLineNumbers(html: string): string {
    if (!showLineNumbers) return html;

    const lines = code.split('\n');
    const lineNumbersHtml = lines
      .map((_, i) => `<span class="line-number">${i + 1}</span>`)
      .join('\n');

    return `<div class="line-numbers">${lineNumbersHtml}</div>${html}`;
  }
</script>

<div
  class="code-block"
  class:with-line-numbers={showLineNumbers}
  style:max-height={maxHeight}
  onmouseenter={() => (hovering = true)}
  onmouseleave={() => (hovering = false)}
  role="region"
  aria-label="Code block"
>
  {#if filename || language !== 'text'}
    <div class="code-header">
      {#if filename}
        <span class="filename">{filename}</span>
      {/if}
      <span class="language">{language}</span>
    </div>
  {/if}

  <div class="code-content">
    {#if highlightedHtml}
      <div class="highlighted" class:with-numbers={showLineNumbers}>
        {#if showLineNumbers}
          <div class="line-numbers">
            {#each code.split('\n') as _, i}
              <span class="line-number">{i + 1}</span>
            {/each}
          </div>
        {/if}
        <!-- eslint-disable-next-line svelte/no-at-html-tags -->
        {@html highlightedHtml}
      </div>
    {:else}
      <pre class="plain"><code>{code}</code></pre>
    {/if}
  </div>

  {#if hovering || copied}
    <button
      class="copy-btn"
      class:copied
      onclick={copyCode}
      transition:fade={{ duration: 150 }}
      aria-label={copied ? 'Copied!' : 'Copy code'}
    >
      {#if copied}
        <span class="check" in:fly={{ y: -5, duration: 150 }}>✓</span>
      {:else}
        <span class="copy-icon" in:fly={{ y: 5, duration: 150 }}>⎘</span>
      {/if}
    </button>
  {/if}
</div>

<style>
  .code-block {
    position: relative;
    background: var(--bg-primary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    overflow: hidden;
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    line-height: 1.4;
  }

  .code-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-2) var(--space-3);
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border-subtle);
  }

  .filename {
    color: var(--text-primary);
    font-size: var(--text-xs);
  }

  .language {
    color: var(--text-tertiary);
    font-size: var(--text-xs);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .code-content {
    overflow: auto;
    scrollbar-width: thin;
    scrollbar-color: var(--border-default) transparent;
  }

  .highlighted {
    display: flex;
  }

  .highlighted.with-numbers {
    display: grid;
    grid-template-columns: auto 1fr;
  }

  .line-numbers {
    display: flex;
    flex-direction: column;
    padding: var(--space-3) var(--space-2);
    padding-right: var(--space-3);
    background: var(--bg-secondary);
    border-right: 1px solid var(--border-subtle);
    text-align: right;
    user-select: none;
  }

  .line-number {
    color: var(--text-tertiary);
    font-size: var(--text-xs);
    line-height: 1.4;
  }

  /* Shiki output styling */
  .highlighted :global(pre) {
    margin: 0;
    padding: var(--space-3);
    background: transparent !important;
    overflow: visible;
  }

  .highlighted :global(code) {
    display: block;
    background: transparent;
  }

  .highlighted :global(.line) {
    display: block;
    min-height: 1.4em;
  }

  /* Plain text fallback */
  .plain {
    margin: 0;
    padding: var(--space-3);
    color: var(--text-primary);
    white-space: pre;
    overflow: auto;
  }

  .plain code {
    display: block;
    background: transparent;
  }

  /* Copy button */
  .copy-btn {
    position: absolute;
    top: var(--space-2);
    right: var(--space-2);
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all var(--transition-fast);
  }

  .copy-btn:hover {
    background: var(--bg-tertiary);
    color: var(--text-primary);
    border-color: var(--border-emphasis);
  }

  .copy-btn.copied {
    background: var(--success-muted);
    border-color: var(--success);
    color: var(--success);
  }

  .check,
  .copy-icon {
    font-size: var(--text-sm);
  }

  /* If header exists, adjust copy button position */
  .code-block:has(.code-header) .copy-btn {
    top: calc(var(--space-2) + 32px);
  }

  /* Max height scrolling */
  .code-block[style*='max-height'] .code-content {
    max-height: inherit;
    overflow: auto;
  }
</style>
