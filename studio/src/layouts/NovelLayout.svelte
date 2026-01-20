<!--
  NovelLayout — Layout for novel/prose projects
  
  Sidebar: Chapters, Plot Threads
  Main: Writing area (prose style)
  Right: Characters, Word Count
-->
<script lang="ts">
  import BaseLayout from './BaseLayout.svelte';
  import Panel from '../components/Panel.svelte';
  
  // Placeholder data
  let chapters = [
    { name: 'Chapter 1: The Beginning', wordCount: 3420, complete: true },
    { name: 'Chapter 2: Discovery', wordCount: 4150, complete: true },
    { name: 'Chapter 3: Confrontation', wordCount: 2800, complete: false },
    { name: 'Chapter 4: Resolution', wordCount: 0, complete: false },
  ];
  
  let characters = [
    { name: 'Sarah', role: 'protagonist', description: 'Detective, 34' },
    { name: 'Marcus', role: 'antagonist?', description: 'Ex-husband, presumed dead' },
    { name: 'Chen', role: 'ally', description: "Sarah's partner" },
  ];
  
  let totalWords = chapters.reduce((sum, ch) => sum + ch.wordCount, 0);
</script>

<BaseLayout>
  <svelte:fragment slot="sidebar-header">
    <span class="sidebar-title">📑 Chapters</span>
  </svelte:fragment>
  
  <svelte:fragment slot="sidebar">
    <div class="chapter-list">
      {#each chapters as chapter, i}
        <button class="chapter-item" class:active={i === 2}>
          <span class="chapter-status">
            {chapter.complete ? '✓' : '○'}
          </span>
          <div class="chapter-info">
            <span class="chapter-name">{chapter.name}</span>
            <span class="chapter-words">{chapter.wordCount.toLocaleString()} words</span>
          </div>
        </button>
      {/each}
    </div>
    
    <Panel title="Plot Threads" icon="🧵" collapsible>
      <div class="thread-list">
        <div class="thread-item">
          <span class="thread-status unresolved">○</span>
          <span class="thread-name">The missing artifact</span>
        </div>
        <div class="thread-item">
          <span class="thread-status unresolved">○</span>
          <span class="thread-name">Sarah's past</span>
        </div>
        <div class="thread-item">
          <span class="thread-status unresolved">○</span>
          <span class="thread-name">The lighthouse secret</span>
        </div>
      </div>
    </Panel>
  </svelte:fragment>
  
  <!-- Main content (prose area) -->
  <div class="writing-area">
    <slot />
  </div>
  
  <svelte:fragment slot="panel">
    <aside class="right-panel">
      <Panel title="Characters" icon="👥">
        <div class="character-list">
          {#each characters as char}
            <div class="character-item">
              <span class="character-name">{char.name}</span>
              <span class="character-role">({char.role})</span>
              <span class="character-desc">{char.description}</span>
            </div>
          {/each}
        </div>
      </Panel>
      
      <Panel title="Stats" icon="📊">
        <div class="stats">
          <div class="stat">
            <span class="stat-value">{totalWords.toLocaleString()}</span>
            <span class="stat-label">words</span>
          </div>
          <div class="stat">
            <span class="stat-value">{chapters.length}</span>
            <span class="stat-label">chapters</span>
          </div>
          <div class="stat">
            <span class="stat-value">{characters.length}</span>
            <span class="stat-label">characters</span>
          </div>
        </div>
      </Panel>
    </aside>
  </svelte:fragment>
</BaseLayout>

<style>
  .sidebar-title {
    font-size: var(--text-sm);
    font-weight: 500;
  }
  
  /* Chapters */
  .chapter-list {
    padding: var(--space-2);
  }
  
  .chapter-item {
    display: flex;
    align-items: flex-start;
    gap: var(--space-2);
    width: 100%;
    padding: var(--space-2) var(--space-3);
    text-align: left;
    font-size: var(--text-sm);
    color: var(--text-secondary);
    border-radius: var(--radius-sm);
    transition: background var(--transition-fast), color var(--transition-fast);
  }
  
  .chapter-item:hover,
  .chapter-item.active {
    background: var(--bg-tertiary);
    color: var(--text-primary);
  }
  
  .chapter-status {
    color: var(--text-tertiary);
    font-size: var(--text-xs);
  }
  
  .chapter-info {
    flex: 1;
    display: flex;
    flex-direction: column;
  }
  
  .chapter-name {
    font-weight: 500;
  }
  
  .chapter-words {
    color: var(--text-tertiary);
    font-size: var(--text-xs);
  }
  
  /* Threads */
  .thread-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  
  .thread-item {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-sm);
    color: var(--text-secondary);
  }
  
  .thread-status {
    font-size: var(--text-xs);
  }
  
  .thread-status.unresolved {
    color: var(--warning);
  }
  
  /* Writing Area */
  .writing-area {
    flex: 1;
    padding: var(--space-8);
    overflow: auto;
    display: flex;
    justify-content: center;
  }
  
  /* Right Panel */
  .right-panel {
    width: 280px;
    flex-shrink: 0;
    border-left: var(--border-width) solid var(--border-color);
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding: var(--space-2);
  }
  
  /* Characters */
  .character-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  
  .character-item {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
    font-size: var(--text-sm);
  }
  
  .character-name {
    font-weight: 500;
    color: var(--text-primary);
  }
  
  .character-role {
    color: var(--text-tertiary);
  }
  
  .character-desc {
    width: 100%;
    color: var(--text-secondary);
    font-size: var(--text-xs);
  }
  
  /* Stats */
  .stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--space-3);
    text-align: center;
  }
  
  .stat {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  
  .stat-value {
    font-size: var(--text-lg);
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .stat-label {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
</style>
