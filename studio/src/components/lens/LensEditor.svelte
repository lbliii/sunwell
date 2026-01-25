<!--
  LensEditor — Enhanced YAML editor for lenses (RFC-100)
  
  Features:
  - Syntax highlighting (via Shiki - already in deps)
  - Real-time validation panel
  - Line numbers
  - Error highlighting
  
  TODO: Upgrade to CodeMirror when deps are added for full editing experience
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { codeToHtml } from 'shiki';
  
  interface Props {
    value: string;
    onchange?: (value: string) => void;
    readonly?: boolean;
  }
  
  let { value, onchange, readonly = false }: Props = $props();
  
  interface ValidationError {
    line: number;
    message: string;
    severity: 'error' | 'warning';
  }
  
  let highlightedHtml = $state('');
  let textareaRef: HTMLTextAreaElement;
  let lineCount = $derived(value.split('\n').length);
  
  // Validation
  const validationErrors = $derived.by(() => {
    const errors: ValidationError[] = [];
    const lines = value.split('\n');
    
    let hasLens = false;
    let hasMetadata = false;
    let hasHeuristics = false;
    let indentSize = 0;
    
    lines.forEach((line, i) => {
      const lineNum = i + 1;
      
      // Track structure
      if (line.match(/^lens:/)) hasLens = true;
      if (line.match(/^\s*metadata:/)) hasMetadata = true;
      if (line.match(/^\s*heuristics:/)) hasHeuristics = true;
      
      // Check for tabs
      if (line.includes('\t')) {
        errors.push({
          line: lineNum,
          message: 'Use spaces instead of tabs',
          severity: 'error',
        });
      }
      
      // Check for inconsistent indentation
      const leadingSpaces = line.match(/^(\s*)/)?.[1].length ?? 0;
      if (leadingSpaces > 0 && line.trim()) {
        if (indentSize === 0) {
          indentSize = leadingSpaces;
        } else if (leadingSpaces % indentSize !== 0) {
          errors.push({
            line: lineNum,
            message: `Inconsistent indentation (expected multiple of ${indentSize})`,
            severity: 'warning',
          });
        }
      }
      
      // Check for common YAML issues
      if (line.match(/:\s*{/) || line.match(/:\s*\[/)) {
        // JSON-style inline syntax - valid but warn for consistency
      }
      
      // Check for trailing whitespace
      if (line.match(/\s+$/)) {
        errors.push({
          line: lineNum,
          message: 'Trailing whitespace',
          severity: 'warning',
        });
      }
    });
    
    // Structure validation
    if (!hasLens) {
      errors.unshift({ line: 1, message: 'Missing "lens:" root key', severity: 'error' });
    }
    if (!hasMetadata) {
      errors.push({ line: 1, message: 'Missing "metadata:" section', severity: 'warning' });
    }
    if (!hasHeuristics) {
      errors.push({ line: 1, message: 'Missing "heuristics:" section', severity: 'warning' });
    }
    
    return errors;
  });
  
  // Single pass categorization instead of 4x O(n) filter calls
  const validationSummary = $derived.by(() => {
    const errorLines = new Set<number>();
    const warningLines = new Set<number>();
    for (const e of validationErrors) {
      if (e.severity === 'error') errorLines.add(e.line);
      else if (e.severity === 'warning') warningLines.add(e.line);
    }
    return { errorLines, warningLines, errorCount: errorLines.size, warningCount: warningLines.size };
  });

  const errorLines = $derived(validationSummary.errorLines);
  const warningLines = $derived(validationSummary.warningLines);
  const errorCount = $derived(validationSummary.errorCount);
  const warningCount = $derived(validationSummary.warningCount);
  
  // Syntax highlighting with Shiki
  async function updateHighlighting() {
    try {
      highlightedHtml = await codeToHtml(value, {
        lang: 'yaml',
        theme: 'github-dark',
      });
    } catch {
      // Fallback to plain text
      highlightedHtml = `<pre><code>${escapeHtml(value)}</code></pre>`;
    }
  }
  
  function escapeHtml(text: string): string {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }
  
  function handleInput(e: Event) {
    const target = e.currentTarget as HTMLTextAreaElement;
    onchange?.(target.value);
  }
  
  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === 'Tab') {
      e.preventDefault();
      const target = e.currentTarget as HTMLTextAreaElement;
      const start = target.selectionStart;
      const end = target.selectionEnd;
      
      // Insert 2 spaces
      const newValue = value.substring(0, start) + '  ' + value.substring(end);
      onchange?.(newValue);
      
      // Restore cursor position
      requestAnimationFrame(() => {
        target.selectionStart = target.selectionEnd = start + 2;
      });
    }
  }
  
  onMount(() => {
    updateHighlighting();
  });
  
  $effect(() => {
    updateHighlighting();
  });
</script>

<div class="editor-layout">
  <div class="editor-pane">
    <div class="editor-container">
      <!-- Line numbers -->
      <div class="line-numbers" aria-hidden="true">
        {#each Array(lineCount) as _, i (i)}
          <span 
            class="line-number"
            class:error={errorLines.has(i + 1)}
            class:warning={warningLines.has(i + 1)}
          >{i + 1}</span>
        {/each}
      </div>
      
      <!-- Highlighted background -->
      <div 
        class="highlight-layer"
        aria-hidden="true"
      >
        {@html highlightedHtml}
      </div>
      
      <!-- Actual textarea -->
      <textarea
        bind:this={textareaRef}
        class="editor-input"
        value={value}
        oninput={handleInput}
        onkeydown={handleKeyDown}
        {readonly}
        spellcheck="false"
        autocomplete="off"
        autocapitalize="off"
        placeholder="lens:
  metadata:
    name: my-lens
    version: 1.0.0
  heuristics:
    - name: Example
      rule: Do something useful"
      ></textarea>
    </div>
  </div>
  
  <aside class="validation-pane">
    <h4 class="validation-title">
      Validation
      {#if errorCount > 0}
        <span class="badge error">{errorCount}</span>
      {/if}
      {#if warningCount > 0}
        <span class="badge warning">{warningCount}</span>
      {/if}
    </h4>
    
    {#if validationErrors.length === 0}
      <div class="validation-ok">
        <span class="ok-icon">✓</span>
        <span>Valid lens structure</span>
      </div>
    {:else}
      <ul class="validation-errors">
        {#each validationErrors as error (error.line + ':' + error.message)}
          <li class="validation-error {error.severity}">
            <button
              type="button"
              class="error-button"
              onclick={() => {
                // Jump to line
                const lines = value.split('\n');
                let pos = 0;
                for (let i = 0; i < error.line - 1; i++) {
                  pos += lines[i].length + 1;
                }
                textareaRef?.focus();
                textareaRef.selectionStart = pos;
                textareaRef.selectionEnd = pos + (lines[error.line - 1]?.length ?? 0);
              }}
            >
              <span class="error-indicator">{error.severity === 'error' ? '✕' : '⚠'}</span>
              <span class="error-line">:{error.line}</span>
              <span class="error-message">{error.message}</span>
            </button>
          </li>
        {/each}
      </ul>
    {/if}
    
    <div class="validation-hints">
      <h5>Quick Reference</h5>
      <ul>
        <li><code>lens:</code> — Root key (required)</li>
        <li><code>metadata:</code> — Name, version, author</li>
        <li><code>heuristics:</code> — List of rules</li>
        <li><code>skills:</code> — Capabilities list</li>
      </ul>
    </div>
  </aside>
</div>

<style>
  .editor-layout {
    display: grid;
    grid-template-columns: 1fr 250px;
    gap: var(--space-4);
    height: 100%;
    min-height: 400px;
  }
  
  .editor-pane {
    display: flex;
    flex-direction: column;
  }
  
  .editor-container {
    position: relative;
    flex: 1;
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    overflow: hidden;
    background: var(--bg-primary);
  }
  
  .line-numbers {
    position: absolute;
    top: 0;
    left: 0;
    width: 48px;
    padding: var(--space-3) 0;
    background: var(--bg-secondary);
    border-right: 1px solid var(--border-subtle);
    display: flex;
    flex-direction: column;
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    line-height: 1.5;
    color: var(--text-tertiary);
    user-select: none;
    z-index: 2;
  }
  
  .line-number {
    padding: 0 var(--space-2);
    text-align: right;
  }
  
  .line-number.error {
    color: var(--error);
    background: var(--error-bg);
  }
  
  .line-number.warning {
    color: var(--warning);
    background: var(--warning-bg);
  }
  
  .highlight-layer {
    position: absolute;
    top: 0;
    left: 48px;
    right: 0;
    bottom: 0;
    padding: var(--space-3);
    overflow: auto;
    pointer-events: none;
    z-index: 1;
  }
  
  .highlight-layer :global(pre) {
    margin: 0;
    padding: 0;
    background: transparent !important;
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    line-height: 1.5;
  }
  
  .highlight-layer :global(code) {
    background: transparent !important;
  }
  
  .editor-input {
    position: relative;
    width: 100%;
    height: 100%;
    padding: var(--space-3);
    padding-left: calc(48px + var(--space-3));
    background: transparent;
    border: none;
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    line-height: 1.5;
    color: transparent;
    caret-color: var(--ui-gold);
    resize: none;
    z-index: 3;
  }
  
  .editor-input::selection {
    background: var(--border-emphasis);
  }
  
  .editor-input:focus {
    outline: none;
  }
  
  .editor-input::placeholder {
    color: var(--text-tertiary);
  }
  
  /* Validation pane */
  .validation-pane {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    padding: var(--space-3);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    overflow-y: auto;
  }
  
  .validation-title {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin: 0;
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .badge {
    font-size: var(--text-xs);
    padding: 2px 6px;
    border-radius: var(--radius-full);
    font-weight: 500;
  }
  
  .badge.error {
    background: var(--error-bg);
    color: var(--error);
  }
  
  .badge.warning {
    background: var(--warning-bg);
    color: var(--warning);
  }
  
  .validation-ok {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2);
    background: var(--success-bg);
    border-radius: var(--radius-sm);
    color: var(--success);
    font-size: var(--text-sm);
  }
  
  .ok-icon {
    font-weight: bold;
  }
  
  .validation-errors {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  
  .validation-error {
    list-style: none;
  }
  
  .error-button {
    display: flex;
    align-items: flex-start;
    gap: var(--space-2);
    width: 100%;
    padding: var(--space-2);
    background: transparent;
    border: none;
    border-radius: var(--radius-sm);
    font-size: var(--text-sm);
    cursor: pointer;
    transition: background var(--transition-fast);
    text-align: left;
  }
  
  .error-button:hover {
    background: var(--bg-tertiary);
  }
  
  .validation-error.error .error-button {
    color: var(--error);
  }
  
  .validation-error.warning .error-button {
    color: var(--warning);
  }
  
  .error-indicator {
    flex-shrink: 0;
    font-weight: bold;
  }
  
  .error-line {
    flex-shrink: 0;
    font-family: var(--font-mono);
    color: var(--text-tertiary);
  }
  
  .error-message {
    color: var(--text-secondary);
  }
  
  .validation-hints {
    margin-top: auto;
    padding-top: var(--space-3);
    border-top: 1px solid var(--border-subtle);
  }
  
  .validation-hints h5 {
    margin: 0 0 var(--space-2);
    font-size: var(--text-xs);
    font-weight: 600;
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  
  .validation-hints ul {
    list-style: none;
    padding: 0;
    margin: 0;
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .validation-hints li {
    padding: 2px 0;
  }
  
  .validation-hints code {
    color: var(--ui-gold-soft);
  }
  
  @media (max-width: 768px) {
    .editor-layout {
      grid-template-columns: 1fr;
      grid-template-rows: 1fr auto;
    }
    
    .validation-pane {
      max-height: 200px;
    }
  }
</style>
