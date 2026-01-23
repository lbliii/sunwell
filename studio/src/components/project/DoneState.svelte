<!--
  DoneState — S-Tier Completion Experience
  
  A celebration-first completion view with:
  - Clear success celebration with goal summary
  - Smart file categorization (source, tests, config, docs)  
  - Inline hero preview of key created file
  - Context-aware quick actions
  - Learnings & concepts summary
-->
<script lang="ts">
  import { invoke } from '@tauri-apps/api/core';
  import { fly, fade, scale } from 'svelte/transition';
  import type { FileEntry } from '$lib/types';
  import Button from '../Button.svelte';
  import LensBadge from '../LensBadge.svelte';
  import { project } from '../../stores/project.svelte';
  import { goToPreview } from '../../stores/app.svelte';
  import { agent, resetAgent, runGoal } from '../../stores/agent.svelte';
  import { formatDuration } from '$lib/format';
  import { getRunProvider } from '../../stores/settings.svelte';
  
  interface Props {
    projectFiles?: FileEntry[];
    isLoadingFiles?: boolean;
    onFileSelect?: (event: { path: string; name: string; isDir: boolean }) => void;
  }
  
  let { projectFiles = [], isLoadingFiles = false, onFileSelect }: Props = $props();
  
  // Hero file preview state
  let heroFile = $state<{ path: string; name: string; content: string } | null>(null);
  let isLoadingHero = $state(false);
  let expandedCategories = $state(new Set<string>(['source']));
  
  // Derived stats
  let taskCount = $derived(agent.tasks.length > 0 ? agent.tasks.length : agent.totalTasks);
  let completedCount = $derived(agent.completedTasks);
  let failedCount = $derived(agent.failedTasks);
  let skippedCount = $derived(agent.skippedTasks);
  
  // Categorize files smartly
  type FileCategory = 'source' | 'tests' | 'config' | 'docs' | 'assets' | 'other';
  
  interface CategorizedFile {
    entry: FileEntry;
    category: FileCategory;
    icon: string;
  }
  
  function categorizeFile(entry: FileEntry): CategorizedFile {
    const name = entry.name.toLowerCase();
    const path = entry.path.toLowerCase();
    
    // Tests
    if (name.startsWith('test_') || name.endsWith('_test.py') || 
        name.endsWith('.test.ts') || name.endsWith('.test.js') ||
        name.endsWith('.spec.ts') || name.endsWith('.spec.js') ||
        path.includes('/tests/') || path.includes('/test/')) {
      return { entry, category: 'tests', icon: '🧪' };
    }
    
    // Config files
    if (['pyproject.toml', 'package.json', 'cargo.toml', 'requirements.txt', 
         'setup.py', 'setup.cfg', '.env', '.gitignore', 'tsconfig.json',
         'vite.config.ts', 'tailwind.config.js', 'docker-compose.yml', 'dockerfile'].includes(name) ||
        name.endsWith('.yaml') || name.endsWith('.yml') || name.endsWith('.toml')) {
      return { entry, category: 'config', icon: '⚙️' };
    }
    
    // Documentation
    if (name.endsWith('.md') || name.endsWith('.rst') || name.endsWith('.txt') ||
        path.includes('/docs/')) {
      return { entry, category: 'docs', icon: '📄' };
    }
    
    // Assets
    if (name.endsWith('.css') || name.endsWith('.scss') || name.endsWith('.svg') ||
        name.endsWith('.png') || name.endsWith('.jpg') || name.endsWith('.ico')) {
      return { entry, category: 'assets', icon: '🎨' };
    }
    
    // Source code (default for code files)
    if (name.endsWith('.py') || name.endsWith('.ts') || name.endsWith('.js') ||
        name.endsWith('.tsx') || name.endsWith('.jsx') || name.endsWith('.rs') ||
        name.endsWith('.go') || name.endsWith('.svelte') || name.endsWith('.vue') ||
        name.endsWith('.html')) {
      return { entry, category: 'source', icon: '📝' };
    }
    
    return { entry, category: 'other', icon: '📁' };
  }
  
  function flattenFiles(entries: FileEntry[]): FileEntry[] {
    const result: FileEntry[] = [];
    for (const entry of entries) {
      if (entry.is_dir && entry.children) {
        result.push(...flattenFiles(entry.children));
      } else if (!entry.is_dir) {
        result.push(entry);
      }
    }
    return result;
  }
  
  let categorizedFiles = $derived.by(() => {
    const flat = flattenFiles(projectFiles);
    const categorized = flat.map(categorizeFile);
    
    // Group by category
    const groups: Record<FileCategory, CategorizedFile[]> = {
      source: [], tests: [], config: [], docs: [], assets: [], other: []
    };
    
    for (const file of categorized) {
      groups[file.category].push(file);
    }
    
    return groups;
  });
  
  let fileStats = $derived({
    total: flattenFiles(projectFiles).length,
    source: categorizedFiles.source.length,
    tests: categorizedFiles.tests.length,
    config: categorizedFiles.config.length,
    docs: categorizedFiles.docs.length,
  });
  
  // Find the hero file (main source file to preview)
  let suggestedHeroFile = $derived.by(() => {
    const sourceFiles = categorizedFiles.source;
    if (sourceFiles.length === 0) return null;
    
    // Priority: main.py, app.py, index.ts, main.ts, then first source file
    const priorities = ['main.py', 'app.py', 'index.ts', 'index.tsx', 'main.ts', 'main.tsx', 'mod.rs', 'lib.rs'];
    for (const name of priorities) {
      const found = sourceFiles.find(f => f.entry.name === name);
      if (found) return found.entry;
    }
    return sourceFiles[0]?.entry ?? null;
  });
  
  // Load hero file preview
  async function loadHeroFile() {
    if (!suggestedHeroFile || heroFile) return;
    
    isLoadingHero = true;
    try {
      const content = await invoke<string>('read_file_contents', {
        path: suggestedHeroFile.path,
        maxSize: 10000
      });
      heroFile = {
        path: suggestedHeroFile.path,
        name: suggestedHeroFile.name,
        content
      };
    } catch (e) {
      console.error('Failed to load hero file:', e);
    }
    isLoadingHero = false;
  }
  
  // Load hero on mount if files are ready
  $effect(() => {
    if (suggestedHeroFile && !heroFile && !isLoadingHero && !isLoadingFiles) {
      loadHeroFile();
    }
  });
  
  // Detect project type for smart actions
  let projectType = $derived.by(() => {
    const files = flattenFiles(projectFiles);
    const names = files.map(f => f.name.toLowerCase());
    
    if (names.some(n => n.includes('.svelte') || n.includes('.tsx') || n.includes('.vue') || n === 'index.html')) {
      return 'webapp';
    }
    if (names.includes('main.py') || names.includes('app.py') || names.includes('__main__.py')) {
      return 'python-app';
    }
    if (names.includes('cargo.toml')) {
      return 'rust';
    }
    return 'generic';
  });
  
  // Actions
  function handleTryIt() { goToPreview(); }
  
  async function handleOpenFiles() {
    if (!project.current?.path) {
      console.warn('No project path available');
      return;
    }
    try {
      await invoke('open_in_finder', { path: project.current.path });
    } catch (e) {
      console.error('Failed to open files:', e);
    }
  }
  
  async function handleOpenTerminal() {
    if (!project.current?.path) return;
    try {
      await invoke('open_terminal', { path: project.current.path });
    } catch (e) {
      console.error('Failed to open terminal:', e);
    }
  }
  
  async function handleOpenEditor() {
    if (!project.current?.path) return;
    try {
      await invoke('open_in_editor', { path: project.current.path });
    } catch (e) {
      console.error('Failed to open editor:', e);
    }
  }
  
  async function handleRebuild() {
    const goal = agent.goal;
    if (!goal || !project.current?.path) return;
    resetAgent();
    const provider = getRunProvider();
    await runGoal(goal, project.current.path, null, true, provider);
  }
  
  function handleFileClick(file: FileEntry) {
    if (file.is_dir) return;
    onFileSelect?.({ path: file.path, name: file.name, isDir: file.is_dir });
  }
  
  function toggleCategory(category: string) {
    const newSet = new Set(expandedCategories);
    if (newSet.has(category)) {
      newSet.delete(category);
    } else {
      newSet.add(category);
    }
    expandedCategories = newSet;
  }
  
  function getFileExtIcon(name: string): string {
    const ext = name.split('.').pop()?.toLowerCase();
    const icons: Record<string, string> = {
      py: '🐍', ts: '📘', tsx: '⚛️', js: '📜', jsx: '⚛️',
      rs: '🦀', go: '🔷', svelte: '🔶', vue: '💚',
      html: '🌐', css: '🎨', json: '📋', md: '📝',
    };
    return icons[ext || ''] || '📄';
  }
  
  const categoryLabels: Record<FileCategory, string> = {
    source: 'Source Code',
    tests: 'Tests',
    config: 'Configuration',
    docs: 'Documentation',
    assets: 'Assets',
    other: 'Other Files',
  };
</script>

<div class="done" in:fade={{ duration: 200 }}>
  <!-- Success Header -->
  <header class="done-header" in:fly={{ y: -10, duration: 300, delay: 100 }}>
    <div class="success-badge">
      <span class="success-icon" aria-hidden="true">◆</span>
      <span class="success-text">Complete</span>
    </div>
    
    <div class="header-meta">
      <LensBadge size="sm" showAuto={false} />
      <span class="stats">
        {completedCount} created
        {#if failedCount > 0}
          <span class="stat-failed">· {failedCount} failed</span>
        {/if}
        {#if skippedCount > 0}
          <span class="stat-skipped">· {skippedCount} cached</span>
        {/if}
        <span class="stat-duration">· {formatDuration(agent.duration)}</span>
      </span>
    </div>
  </header>
  
  <!-- Goal Summary -->
  {#if agent.goal}
    <div class="goal-summary" in:fly={{ y: 10, duration: 300, delay: 150 }}>
      <span class="goal-prompt">✓</span>
      <span class="goal-text">{agent.goal}</span>
    </div>
  {/if}
  
  <!-- Primary Action based on project type -->
  <div class="primary-action" in:scale={{ start: 0.95, duration: 300, delay: 200 }}>
    {#if projectType === 'webapp'}
      <Button variant="primary" size="lg" icon="»" onclick={handleTryIt}>
        Preview
      </Button>
      <p class="action-hint">Open the live preview</p>
    {:else if projectType === 'python-app'}
      <Button variant="primary" size="lg" icon="⊳" onclick={handleOpenTerminal}>
        Run It
      </Button>
      <p class="action-hint">Open terminal to run your app</p>
    {:else}
      <Button variant="primary" size="lg" icon="⊡" onclick={handleOpenEditor}>
        Open in Editor
      </Button>
      <p class="action-hint">Continue in your editor</p>
    {/if}
  </div>
  
  <!-- Quick Nav -->
  <nav class="quick-nav" in:fade={{ duration: 200, delay: 250 }}>
    <button class="nav-btn" onclick={handleOpenFiles} title="Open in Finder">
      <span class="nav-icon">▤</span>
      <span>Files</span>
    </button>
    <button class="nav-btn" onclick={handleOpenTerminal} title="Open Terminal">
      <span class="nav-icon">⊳</span>
      <span>Terminal</span>
    </button>
    <button class="nav-btn" onclick={handleOpenEditor} title="Open in Editor">
      <span class="nav-icon">⊡</span>
      <span>Editor</span>
    </button>
    <button class="nav-btn" onclick={handleRebuild} title="Rebuild from scratch">
      <span class="nav-icon">↻</span>
      <span>Rebuild</span>
    </button>
  </nav>
  
  <!-- Content Grid: Files + Preview -->
  <div class="content-grid" in:fly={{ y: 20, duration: 300, delay: 300 }}>
    <!-- File Summary -->
    <section class="file-summary">
      <h3 class="section-title">
        <span class="title-icon">▤</span>
        Created Files
        {#if fileStats.total > 0}
          <span class="file-count">{fileStats.total}</span>
        {/if}
      </h3>
      
      {#if isLoadingFiles}
        <div class="loading-files">
          <span class="loading-spinner">◌</span>
          Loading files...
        </div>
      {:else if fileStats.total === 0}
        <div class="empty-files">
          <p>No files found</p>
          <button class="refresh-btn" onclick={() => { /* trigger refresh */ }}>
            Refresh
          </button>
        </div>
      {:else}
        <div class="file-categories">
          {#each Object.entries(categorizedFiles) as [category, files]}
            {#if files.length > 0}
              <div class="category-group">
                <button 
                  class="category-header"
                  onclick={() => toggleCategory(category)}
                  aria-expanded={expandedCategories.has(category)}
                >
                  <span class="category-chevron">{expandedCategories.has(category) ? '▾' : '▸'}</span>
                  <span class="category-name">{categoryLabels[category as FileCategory]}</span>
                  <span class="category-count">{files.length}</span>
                </button>
                
                {#if expandedCategories.has(category)}
                  <div class="category-files" in:fly={{ y: -5, duration: 150 }}>
                    {#each files.slice(0, 10) as { entry }}
                      <button 
                        class="file-item"
                        onclick={() => handleFileClick(entry)}
                        title={entry.path}
                      >
                        <span class="file-icon">{getFileExtIcon(entry.name)}</span>
                        <span class="file-name">{entry.name}</span>
                      </button>
                    {/each}
                    {#if files.length > 10}
                      <span class="more-files">+{files.length - 10} more</span>
                    {/if}
                  </div>
                {/if}
              </div>
            {/if}
          {/each}
        </div>
      {/if}
    </section>
    
    <!-- Hero Preview -->
    <section class="hero-preview">
      <h3 class="section-title">
        <span class="title-icon">◇</span>
        Preview
        {#if heroFile}
          <span class="preview-filename">{heroFile.name}</span>
        {/if}
      </h3>
      
      {#if isLoadingHero}
        <div class="preview-loading">
          <span class="loading-spinner">◌</span>
          Loading preview...
        </div>
      {:else if heroFile}
        <div class="preview-content">
          <pre class="code-preview"><code>{heroFile.content}</code></pre>
        </div>
      {:else if fileStats.total > 0}
        <div class="preview-empty">
          <p>Click a file to preview</p>
        </div>
      {:else}
        <div class="preview-empty">
          <p>No files to preview</p>
        </div>
      {/if}
    </section>
  </div>
  
  <!-- Learnings (collapsed by default) -->
  {#if agent.learnings.length > 0}
    <details class="learnings-section" in:fade={{ duration: 200, delay: 350 }}>
      <summary class="learnings-header">
        <span class="learnings-icon">💡</span>
        <span>{agent.learnings.length} learnings</span>
      </summary>
      <ul class="learnings-list">
        {#each agent.learnings.slice(-5) as learning}
          <li class="learning-item">{learning}</li>
        {/each}
        {#if agent.learnings.length > 5}
          <li class="learning-more">+{agent.learnings.length - 5} more</li>
        {/if}
      </ul>
    </details>
  {/if}
  
  <!-- Concepts Tags -->
  {#if agent.concepts.length > 0}
    <div class="concepts" in:fade={{ duration: 200, delay: 400 }}>
      {#each agent.concepts.slice(0, 6) as concept}
        <span class="concept-tag">{concept.label}</span>
      {/each}
      {#if agent.concepts.length > 6}
        <span class="concept-more">+{agent.concepts.length - 6}</span>
      {/if}
    </div>
  {/if}
</div>

<style>
  .done {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--space-6);
    padding: var(--space-4);
    max-width: 900px;
    margin: 0 auto;
    width: 100%;
  }
  
  /* Header */
  .done-header {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-2);
  }
  
  .success-badge {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  
  .success-icon {
    color: var(--success);
    font-size: var(--text-2xl);
    animation: pulse-success 2s ease-in-out infinite;
  }
  
  @keyframes pulse-success {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.8; transform: scale(1.05); }
  }
  
  .success-text {
    font-size: var(--text-xl);
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .header-meta {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }
  
  .stats {
    color: var(--text-tertiary);
    font-size: var(--text-sm);
  }
  
  .stat-failed { color: var(--error); }
  .stat-skipped { color: var(--text-tertiary); }
  .stat-duration { color: var(--text-tertiary); }
  
  /* Goal Summary */
  .goal-summary {
    display: flex;
    align-items: flex-start;
    gap: var(--space-2);
    padding: var(--space-3) var(--space-4);
    background: rgba(34, 197, 94, 0.08);
    border: 1px solid rgba(34, 197, 94, 0.2);
    border-radius: var(--radius-md);
    max-width: 600px;
    margin: 0 auto;
  }
  
  .goal-prompt {
    color: var(--success);
    font-weight: 600;
    flex-shrink: 0;
  }
  
  .goal-text {
    color: var(--text-primary);
    font-size: var(--text-base);
    line-height: var(--leading-relaxed);
  }
  
  /* Primary Action */
  .primary-action {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-6) 0;
  }
  
  .action-hint {
    color: var(--text-tertiary);
    font-size: var(--text-sm);
    margin: 0;
  }
  
  /* Quick Nav */
  .quick-nav {
    display: flex;
    justify-content: center;
    gap: var(--space-2);
  }
  
  .nav-btn {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-2) var(--space-3);
    background: transparent;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    color: var(--text-secondary);
    font-size: var(--text-sm);
    font-family: var(--font-mono);
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  
  .nav-btn:hover {
    background: var(--accent-hover);
    border-color: var(--border-default);
    color: var(--text-primary);
  }
  
  .nav-btn:focus-visible {
    outline: 2px solid var(--border-emphasis);
    outline-offset: 2px;
  }
  
  .nav-icon {
    font-size: var(--text-base);
  }
  
  /* Content Grid */
  .content-grid {
    display: grid;
    grid-template-columns: 280px 1fr;
    gap: var(--space-4);
    min-height: 300px;
  }
  
  @media (max-width: 768px) {
    .content-grid {
      grid-template-columns: 1fr;
    }
  }
  
  /* Section Title */
  .section-title {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--text-secondary);
    margin: 0 0 var(--space-3) 0;
  }
  
  .title-icon {
    color: var(--text-tertiary);
  }
  
  .file-count, .preview-filename {
    color: var(--text-tertiary);
    font-weight: 400;
    font-size: var(--text-xs);
  }
  
  /* File Summary */
  .file-summary {
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: var(--space-3);
    overflow-y: auto;
    max-height: 400px;
  }
  
  .loading-files, .empty-files {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    padding: var(--space-6);
    color: var(--text-tertiary);
    font-size: var(--text-sm);
  }
  
  .loading-spinner {
    animation: spin 1s linear infinite;
  }
  
  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
  
  .refresh-btn {
    padding: var(--space-1) var(--space-2);
    background: transparent;
    border: 1px solid var(--border-default);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-size: var(--text-xs);
    cursor: pointer;
  }
  
  .refresh-btn:hover {
    background: var(--ui-gold-10);
  }
  
  /* Categories */
  .file-categories {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  
  .category-group {
    display: flex;
    flex-direction: column;
  }
  
  .category-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2);
    background: transparent;
    border: none;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-size: var(--text-sm);
    font-family: var(--font-mono);
    cursor: pointer;
    text-align: left;
    width: 100%;
    transition: background var(--transition-fast);
  }
  
  .category-header:hover {
    background: var(--bg-tertiary);
  }
  
  .category-chevron {
    color: var(--text-tertiary);
    font-size: 10px;
    width: 12px;
  }
  
  .category-name {
    flex: 1;
    font-weight: 500;
  }
  
  .category-count {
    color: var(--text-tertiary);
    font-size: var(--text-xs);
  }
  
  .category-files {
    display: flex;
    flex-direction: column;
    padding-left: var(--space-4);
  }
  
  .file-item {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1) var(--space-2);
    background: transparent;
    border: none;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-size: var(--text-xs);
    font-family: var(--font-mono);
    cursor: pointer;
    text-align: left;
    width: 100%;
    transition: all var(--transition-fast);
  }
  
  .file-item:hover {
    background: var(--bg-tertiary);
    color: var(--text-primary);
  }
  
  .file-icon {
    font-size: var(--text-sm);
  }
  
  .file-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .more-files {
    padding: var(--space-1) var(--space-2);
    color: var(--text-tertiary);
    font-size: var(--text-xs);
    font-style: italic;
  }
  
  /* Hero Preview */
  .hero-preview {
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: var(--space-3);
    display: flex;
    flex-direction: column;
    min-height: 200px;
  }
  
  .preview-loading, .preview-empty {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-tertiary);
    font-size: var(--text-sm);
  }
  
  .preview-content {
    flex: 1;
    overflow: auto;
    background: var(--bg-primary);
    border-radius: var(--radius-sm);
  }
  
  .code-preview {
    margin: 0;
    padding: var(--space-3);
    font-family: var(--font-mono);
    font-size: 11px;
    line-height: 1.5;
    color: var(--text-secondary);
    white-space: pre-wrap;
    word-break: break-word;
  }
  
  .code-preview code {
    display: block;
  }
  
  /* Learnings */
  .learnings-section {
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    overflow: hidden;
  }
  
  .learnings-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-3);
    cursor: pointer;
    color: var(--text-secondary);
    font-size: var(--text-sm);
    font-family: var(--font-mono);
  }
  
  .learnings-header:hover {
    background: var(--bg-tertiary);
  }
  
  .learnings-icon {
    font-size: var(--text-base);
  }
  
  .learnings-list {
    list-style: none;
    padding: 0 var(--space-3) var(--space-3);
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  
  .learning-item {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    padding: var(--space-1) 0;
    border-bottom: 1px solid var(--border-subtle);
  }
  
  .learning-item:last-child {
    border-bottom: none;
  }
  
  .learning-more {
    color: var(--text-tertiary);
    font-size: var(--text-xs);
    font-style: italic;
  }
  
  /* Concepts */
  .concepts {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    justify-content: center;
  }
  
  .concept-tag {
    padding: var(--space-1) var(--space-2);
    background: var(--ui-gold-10);
    border: 1px solid var(--ui-gold-20);
    border-radius: var(--radius-sm);
    color: var(--text-gold);
    font-size: var(--text-xs);
    font-family: var(--font-mono);
  }
  
  .concept-more {
    color: var(--text-tertiary);
    font-size: var(--text-xs);
    padding: var(--space-1);
  }
  
  /* Scrollbar */
  .file-summary::-webkit-scrollbar,
  .preview-content::-webkit-scrollbar {
    width: 6px;
  }
  
  .file-summary::-webkit-scrollbar-track,
  .preview-content::-webkit-scrollbar-track {
    background: transparent;
  }
  
  .file-summary::-webkit-scrollbar-thumb,
  .preview-content::-webkit-scrollbar-thumb {
    background: var(--border-subtle);
    border-radius: 3px;
  }
</style>
