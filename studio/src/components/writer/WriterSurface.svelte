<!--
  WriterSurface.svelte — Universal Writing Environment (RFC-086)
  
  Complete writer layout with:
  - Prose editor (main)
  - Sidebar (outline, validation, skills)
  - Status bar (word count, Diataxis, lens)
  - View toggle (source/preview)
  - Selection menu
  - Lens selector
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { fly, fade } from 'svelte/transition';
  import {
    writerState,
    loadDocument,
    updateContent,
    saveDocument,
    setSelection,
    toggleView,
    detectDiataxis,
    validateDocument,
  } from '../../stores';
  import {
    workflowState,
  } from '../../stores';

  // Components
  import WriterStatusBar from './WriterStatusBar.svelte';
  import SelectionMenu from './SelectionMenu.svelte';
  import LensSelector from './LensSelector.svelte';
  import { ValidationBlock, SkillsBlock, DiataxisBlock, WorkflowPanel } from '../blocks';

  interface Props {
    filePath?: string;
    initialContent?: string;
    lensName?: string;
  }

  let { filePath, initialContent = '', lensName = 'tech-writer' }: Props = $props();

  // Local state
  let editorElement: HTMLTextAreaElement | null = $state(null);
  let showLensSelector = $state(false);
  let showOutline = $state(true);
  let showValidation = $state(true);
  let debounceTimer: ReturnType<typeof setTimeout> | null = null;

  // Derived state from stores
  const content = $derived(writerState.content || initialContent);
  const viewMode = $derived(writerState.viewMode);
  const wordCount = $derived(writerState.wordCount);
  const isValidating = $derived(writerState.isValidating);
  const validationWarnings = $derived(writerState.validationWarnings);
  const workflow = $derived(workflowState.execution);

  // Load document on mount
  onMount(async () => {
    if (filePath) {
      await loadDocument(filePath);
    }
  });

  // Handle content changes with debouncing
  function handleContentChange(e: Event) {
    const target = e.target as HTMLTextAreaElement;
    const newContent = target.value;

    updateContent(newContent);

    // Debounce validation and Diataxis detection
    if (debounceTimer) {
      clearTimeout(debounceTimer);
    }
    debounceTimer = setTimeout(async () => {
      await Promise.all([detectDiataxis(), validateDocument()]);
    }, 500);
  }

  // Handle text selection
  function handleSelection() {
    if (!editorElement) return;

    const start = editorElement.selectionStart;
    const end = editorElement.selectionEnd;

    if (start === end) {
      setSelection(null);
      return;
    }

    const text = content.slice(start, end);
    const lines = content.slice(0, start).split('\n');
    const line = lines.length;
    const column = lines[lines.length - 1].length;

    setSelection({ text, start, end, line, column });
  }

  // Keyboard shortcuts
  function handleKeydown(e: KeyboardEvent) {
    // ⌘S - Save
    if ((e.metaKey || e.ctrlKey) && e.key === 's') {
      e.preventDefault();
      saveDocument();
    }

    // ⌘L - Open lens selector
    if ((e.metaKey || e.ctrlKey) && e.key === 'l') {
      e.preventDefault();
      showLensSelector = true;
    }

    // ⌘B - Toggle outline sidebar
    if ((e.metaKey || e.ctrlKey) && e.key === 'b') {
      e.preventDefault();
      showOutline = !showOutline;
    }
  }

  // Navigate to line from validation warning
  function handleNavigateToLine(line: number) {
    if (!editorElement) return;

    const lines = content.split('\n');
    let charIndex = 0;
    for (let i = 0; i < line - 1 && i < lines.length; i++) {
      charIndex += lines[i].length + 1; // +1 for newline
    }

    editorElement.focus();
    editorElement.setSelectionRange(charIndex, charIndex);
  }

  // Simple markdown preview
  function renderPreview(text: string): string {
    return text
      .replace(/^### (.*$)/gim, '<h3>$1</h3>')
      .replace(/^## (.*$)/gim, '<h2>$1</h2>')
      .replace(/^# (.*$)/gim, '<h1>$1</h1>')
      .replace(/\*\*(.*)\*\*/gim, '<strong>$1</strong>')
      .replace(/\*(.*)\*/gim, '<em>$1</em>')
      .replace(/`([^`]+)`/gim, '<code>$1</code>')
      .replace(/\n/gim, '<br>');
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="writer-surface">
  <!-- Main content area -->
  <div class="main-area">
    <!-- Left sidebar (outline) -->
    {#if showOutline}
      <aside class="sidebar left" transition:fly={{ x: -20, duration: 150 }}>
        <div class="sidebar-section">
          <h3 class="sidebar-title">Outline</h3>
          <div class="outline-content">
            <!-- Extract headers from content -->
            {#each content.split('\n').filter((l) => l.startsWith('#')) as header, i}
              {@const level = header.match(/^#+/)?.[0].length ?? 1}
              {@const text = header.replace(/^#+\s*/, '')}
              <button
                class="outline-item"
                style="padding-left: {(level - 1) * 12 + 8}px"
                onclick={() => handleNavigateToLine(i + 1)}
              >
                {text || 'Untitled'}
              </button>
            {/each}
            {#if !content.split('\n').some((l) => l.startsWith('#'))}
              <p class="outline-empty">No headings found</p>
            {/if}
          </div>
        </div>
      </aside>
    {/if}

    <!-- Editor/Preview -->
    <main class="editor-area">
      {#if viewMode === 'source'}
        <textarea
          bind:this={editorElement}
          class="prose-editor"
          value={content}
          oninput={handleContentChange}
          onmouseup={handleSelection}
          onkeyup={handleSelection}
          placeholder="Start writing..."
          spellcheck="true"
        ></textarea>
      {:else}
        <div class="preview-area">
          {@html renderPreview(content)}
        </div>
      {/if}
    </main>

    <!-- Right sidebar (validation, skills) -->
    {#if showValidation}
      <aside class="sidebar right" transition:fly={{ x: 20, duration: 150 }}>
        <!-- Workflow panel (if active) -->
        {#if workflow}
          <div class="sidebar-section">
            <WorkflowPanel />
          </div>
        {/if}

        <!-- Diataxis detection -->
        <div class="sidebar-section">
          <DiataxisBlock />
        </div>

        <!-- Validation -->
        <div class="sidebar-section">
          <ValidationBlock onNavigate={handleNavigateToLine} />
        </div>

        <!-- Skills -->
        <div class="sidebar-section">
          <SkillsBlock />
        </div>
      </aside>
    {/if}
  </div>

  <!-- Status bar -->
  <WriterStatusBar
    onOpenLensSelector={() => (showLensSelector = true)}
  />

  <!-- Selection menu (floating) -->
  <SelectionMenu />

  <!-- Lens selector modal -->
  <LensSelector
    visible={showLensSelector}
    onClose={() => (showLensSelector = false)}
  />
</div>

<style>
  .writer-surface {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: var(--bg-primary);
    font-family: var(--font-sans);
  }

  .main-area {
    flex: 1;
    display: flex;
    min-height: 0; /* Removed overflow:hidden - clips selection menus */
  }

  .sidebar {
    width: 280px;
    background: var(--bg-primary);
    overflow-y: auto;
    flex-shrink: 0;
  }

  .sidebar.left {
    border-right: 1px solid var(--border-subtle);
  }

  .sidebar.right {
    border-left: 1px solid var(--border-subtle);
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding: var(--space-2);
  }

  .sidebar-section {
    /* Spacing handled by gap */
  }

  .sidebar-title {
    font-size: var(--text-xs);
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: var(--space-3) var(--space-3) var(--space-2);
    margin: 0;
  }

  .outline-content {
    padding: 0 var(--space-1) var(--space-3);
  }

  .outline-item {
    display: block;
    width: 100%;
    padding: var(--space-1) var(--space-2);
    background: transparent;
    border: none;
    border-radius: var(--radius-sm);
    text-align: left;
    font-family: inherit;
    font-size: var(--text-xs);
    color: var(--text-primary);
    cursor: pointer;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    transition: background var(--transition-fast);
  }

  .outline-item:hover {
    background: var(--bg-tertiary);
  }

  .outline-empty {
    padding: var(--space-3);
    color: var(--text-tertiary);
    font-size: var(--text-xs);
    font-style: italic;
  }

  .editor-area {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background: var(--bg-primary);
  }

  .prose-editor {
    flex: 1;
    width: 100%;
    padding: var(--space-8) var(--space-16);
    background: transparent;
    border: none;
    outline: none;
    resize: none;
    font-family: var(--font-serif);
    font-size: var(--text-lg);
    line-height: var(--leading-relaxed);
    color: var(--text-primary);
  }

  .prose-editor::placeholder {
    color: var(--text-tertiary);
  }

  .preview-area {
    flex: 1;
    padding: var(--space-8) var(--space-16);
    overflow-y: auto;
    font-family: var(--font-serif);
    font-size: var(--text-lg);
    line-height: var(--leading-relaxed);
    color: var(--text-primary);
  }

  .preview-area :global(h1) {
    font-size: 2em;
    margin: 0.5em 0;
    color: var(--text-primary);
  }

  .preview-area :global(h2) {
    font-size: 1.5em;
    margin: 0.5em 0;
    color: var(--text-primary);
  }

  .preview-area :global(h3) {
    font-size: 1.25em;
    margin: 0.5em 0;
    color: var(--text-primary);
  }

  .preview-area :global(code) {
    background: var(--bg-secondary);
    padding: var(--space-px) var(--space-1);
    border-radius: var(--radius-sm);
    font-family: var(--font-mono);
    font-size: 0.9em;
  }

  .preview-area :global(strong) {
    font-weight: 700;
  }

  .preview-area :global(em) {
    font-style: italic;
  }
</style>
