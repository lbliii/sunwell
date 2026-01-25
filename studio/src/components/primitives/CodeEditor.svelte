<!--
  CodeEditor Primitive (RFC-072, RFC-097)
  
  Primary code editing primitive with syntax highlighting.
  
  RFC-097 Enhancement:
  - Integrated CodeBlock for syntax highlighting in view mode
  - Toggle between edit and view mode
  - Copy button and line numbers
  - Holy Light theme colors
-->
<script lang="ts">
  import { untrack } from 'svelte';
  import { fade } from 'svelte/transition';
  import type { CodePrimitiveProps } from './types';
  import { emitPrimitiveEvent } from '../../stores/surface.svelte';
  import CodeBlock from './CodeBlock.svelte';
  
  interface Props extends CodePrimitiveProps {
    readonly?: boolean;
    showLineNumbers?: boolean;
  }
  
  let { 
    size, 
    file, 
    language, 
    seed, 
    readonly = false,
    showLineNumbers = true,
  }: Props = $props();
  
  // Extract initial value (intentional one-time capture from seed prop)
  const initialContent = untrack(() => seed?.content as string ?? '// Start coding...');
  let content = $state(initialContent);
  // Use derived to react to readonly prop changes
  let isEditingOverride = $state<boolean | null>(null);
  let isEditing = $derived(isEditingOverride ?? !readonly);
  let textareaRef = $state<HTMLTextAreaElement | null>(null);
  
  // Pre-compute lines for O(1) template access (avoids .split() on every render)
  const contentLines = $derived(content.split('\n'));
  
  // Detect language from file extension if not provided
  const detectedLanguage = $derived.by(() => {
    if (language) return language;
    if (!file) return 'text';
    const ext = file.split('.').pop()?.toLowerCase();
    const langMap: Record<string, string> = {
      py: 'python',
      ts: 'typescript',
      js: 'javascript',
      rs: 'rust',
      go: 'go',
      json: 'json',
      yaml: 'yaml',
      yml: 'yaml',
      md: 'markdown',
      css: 'css',
      html: 'html',
      svelte: 'svelte',
      sh: 'bash',
      bash: 'bash',
      sql: 'sql',
    };
    return langMap[ext ?? ''] ?? 'text';
  });
  
  function handleChange(e: Event) {
    const target = e.target as HTMLTextAreaElement;
    content = target.value;
    emitPrimitiveEvent('CodeEditor', 'file_edit', { file, content });
  }
  
  function startEditing() {
    if (readonly) return;
    isEditingOverride = true;
    // Focus textarea after transition
    requestAnimationFrame(() => {
      textareaRef?.focus();
    });
  }
  
  function stopEditing() {
    isEditingOverride = false;
  }
  
  // Keyboard shortcuts
  function handleKeydown(e: KeyboardEvent) {
    // Escape to exit edit mode
    if (e.key === 'Escape') {
      stopEditing();
    }
    // Tab handling for proper indentation
    if (e.key === 'Tab' && textareaRef) {
      e.preventDefault();
      const start = textareaRef.selectionStart;
      const end = textareaRef.selectionEnd;
      const spaces = '  '; // 2 space indent
      
      // Insert spaces at cursor
      content = content.substring(0, start) + spaces + content.substring(end);
      
      // Move cursor after spaces
      requestAnimationFrame(() => {
        if (textareaRef) {
          textareaRef.selectionStart = textareaRef.selectionEnd = start + spaces.length;
        }
      });
    }
  }
</script>

<div class="code-editor" data-size={size}>
  <div class="editor-header">
    <div class="file-info">
      <span class="file-icon">📄</span>
      <span class="file-name">{file ?? 'Untitled'}</span>
    </div>
    <div class="header-right">
      <span class="language">{detectedLanguage}</span>
      {#if !readonly}
        <button 
          class="mode-toggle"
          class:active={isEditing}
          onclick={() => isEditing ? stopEditing() : startEditing()}
          title={isEditing ? 'View mode (Esc)' : 'Edit mode'}
        >
          {isEditing ? '👁' : '✏️'}
        </button>
      {/if}
    </div>
  </div>
  
  <div class="editor-body">
    {#if isEditing}
      <div class="edit-mode" in:fade={{ duration: 100 }}>
        {#if showLineNumbers}
          <div class="line-numbers">
            {#each contentLines as _, i (i)}
              <span class="line-number">{i + 1}</span>
            {/each}
          </div>
        {/if}
        <textarea 
          bind:this={textareaRef}
          class="editor-textarea"
          value={content}
          oninput={handleChange}
          onkeydown={handleKeydown}
          onblur={stopEditing}
          spellcheck="false"
          autocomplete="off"
          autocapitalize="off"
        ></textarea>
      </div>
    {:else}
      <div 
        class="view-mode" 
        in:fade={{ duration: 100 }}
        onclick={startEditing}
        role="button"
        tabindex="0"
        onkeydown={(e) => e.key === 'Enter' && startEditing()}
      >
        <CodeBlock 
          code={content}
          language={detectedLanguage}
          showLineNumbers={showLineNumbers}
        />
      </div>
    {/if}
  </div>
</div>

<style>
  .code-editor {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: var(--bg-primary);
    border-radius: var(--radius-md);
    border: 1px solid var(--border-subtle);
    overflow: hidden;
    transition: border-color var(--transition-fast);
  }
  
  .code-editor:focus-within {
    border-color: var(--border-emphasis);
  }
  
  .editor-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-2) var(--space-3);
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border-subtle);
    min-height: 40px;
  }
  
  .file-info {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  
  .file-icon {
    font-size: var(--text-sm);
    opacity: 0.7;
  }
  
  .file-name {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-primary);
    font-weight: 500;
  }
  
  .header-right {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }
  
  .language {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  
  .mode-toggle {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all var(--transition-fast);
    font-size: var(--text-sm);
  }
  
  .mode-toggle:hover {
    background: var(--accent-hover);
    border-color: var(--border-default);
    color: var(--text-primary);
  }
  
  .mode-toggle.active {
    background: var(--accent-hover);
    border-color: var(--accent-muted);
    color: var(--text-gold);
  }
  
  .editor-body {
    flex: 1;
    overflow: hidden;
    position: relative;
  }
  
  .edit-mode {
    display: flex;
    height: 100%;
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
    min-width: 48px;
  }
  
  .line-number {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-tertiary);
    line-height: 1.6;
    height: 1.6em;
  }
  
  .editor-textarea {
    flex: 1;
    padding: var(--space-3);
    background: var(--bg-primary);
    color: var(--text-primary);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    line-height: 1.6;
    border: none;
    resize: none;
    outline: none;
    overflow: auto;
    white-space: pre;
    tab-size: 2;
  }
  
  .editor-textarea::placeholder {
    color: var(--text-tertiary);
  }
  
  .view-mode {
    height: 100%;
    cursor: text;
    overflow: auto;
  }
  
  .view-mode:hover {
    background: var(--bg-secondary);
  }
  
  /* Override CodeBlock styles when embedded */
  .view-mode :global(.code-block) {
    border: none;
    border-radius: 0;
    height: 100%;
  }
  
  .view-mode :global(.code-content) {
    height: 100%;
  }
</style>
