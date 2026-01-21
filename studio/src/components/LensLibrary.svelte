<!--
  LensLibrary — Full lens library browser (RFC-070)
  
  Browse, filter, and manage lenses with detail views and editing.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import Button from './Button.svelte';
  import Modal from './Modal.svelte';
  import { 
    lensLibrary, 
    getFilteredEntries,
    getAvailableDomains,
    getDefaultLens,
    loadLibrary,
    selectLens,
    openEditor,
    forkLens,
    deleteLens,
    setFilter,
    setDefaultLens,
    goToLibrary,
    loadVersions,
    rollbackLens,
    saveLens,
    clearError,
  } from '../stores/lensLibrary.svelte';
  import type { LensLibraryEntry } from '$lib/types';
  
  interface Props {
    onSelect?: (lensName: string) => void;
    showSelectButton?: boolean;
  }
  
  let { onSelect, showSelectButton = false }: Props = $props();
  
  // Fork modal state
  let showForkModal = $state(false);
  let forkSourceName = $state('');
  let forkNewName = $state('');
  let forkMessage = $state('');
  let isForkingLens = $state(false);
  
  // Delete confirmation state
  let showDeleteModal = $state(false);
  let deleteTargetName = $state('');
  
  // Save modal state
  let showSaveModal = $state(false);
  let saveMessage = $state('');
  let saveBump = $state<'major' | 'minor' | 'patch'>('patch');
  let editedContent = $state('');
  
  onMount(() => {
    if (lensLibrary.entries.length === 0) {
      loadLibrary();
    }
  });
  
  function handleForkClick(sourceName: string) {
    forkSourceName = sourceName;
    forkNewName = `${sourceName}-custom`;
    forkMessage = '';
    showForkModal = true;
  }
  
  async function handleForkConfirm() {
    if (!forkNewName.trim()) return;
    
    isForkingLens = true;
    const result = await forkLens(forkSourceName, forkNewName, forkMessage || undefined);
    isForkingLens = false;
    
    if (result?.success) {
      showForkModal = false;
    }
  }
  
  function handleDeleteClick(name: string) {
    deleteTargetName = name;
    showDeleteModal = true;
  }
  
  async function handleDeleteConfirm() {
    await deleteLens(deleteTargetName);
    showDeleteModal = false;
  }
  
  function handleEditClick(entry: LensLibraryEntry) {
    openEditor(entry);
    editedContent = lensLibrary.editorContent || '';
  }
  
  function handleSaveClick() {
    saveMessage = '';
    saveBump = 'patch';
    showSaveModal = true;
  }
  
  async function handleSaveConfirm() {
    const result = await saveLens(editedContent, saveMessage || undefined, saveBump);
    if (result?.success) {
      showSaveModal = false;
    }
  }
  
  function getDomainIcon(domain: string | null): string {
    const icons: Record<string, string> = {
      'software': '💻',
      'code': '💻',
      'documentation': '📝',
      'review': '🔍',
      'test': '🧪',
      'general': '🔮',
    };
    return icons[domain || 'general'] || '🔮';
  }
  
  // Reactive derived state
  const filteredEntries = $derived(getFilteredEntries());
  const availableDomains = $derived(getAvailableDomains());
  // Note: defaultLens is available for future features like showing "★ Current default" status
  void getDefaultLens;
</script>

<div class="lens-library">
  {#if lensLibrary.view === 'library'}
    <!-- Library Browser -->
    <header class="library-header">
      <h2>Lens Library</h2>
      <p class="subtitle">Browse and manage your expertise containers</p>
    </header>
    
    <!-- Filters -->
    <div class="filters">
      <input
        type="text"
        placeholder="Search lenses..."
        class="search-input"
        value={lensLibrary.filter.search}
        oninput={(e) => setFilter({ search: e.currentTarget.value })}
      />
      
      <select 
        class="filter-select"
        value={lensLibrary.filter.source}
        onchange={(e) => setFilter({ source: e.currentTarget.value as 'all' | 'builtin' | 'user' })}
      >
        <option value="all">All Sources</option>
        <option value="user">My Lenses</option>
        <option value="builtin">Built-in</option>
      </select>
      
      <select 
        class="filter-select"
        value={lensLibrary.filter.domain || ''}
        onchange={(e) => setFilter({ domain: e.currentTarget.value || null })}
      >
        <option value="">All Domains</option>
        {#each availableDomains as domain}
          <option value={domain}>{domain}</option>
        {/each}
      </select>
    </div>
    
    <!-- Error display -->
    {#if lensLibrary.error}
      <div class="error-banner">
        <span>{lensLibrary.error}</span>
        <button onclick={clearError}>×</button>
      </div>
    {/if}
    
    <!-- Lens Grid -->
    {#if lensLibrary.isLoading}
      <div class="loading-state">Loading lenses...</div>
    {:else if filteredEntries.length === 0}
      <div class="empty-state">No lenses found</div>
    {:else}
      <div class="lens-grid">
        {#each filteredEntries as entry (entry.path)}
          <div 
            class="lens-card"
            class:is-default={entry.is_default}
            class:is-user={entry.source === 'user'}
          >
            <div class="card-header">
              <span class="lens-icon">{getDomainIcon(entry.domain)}</span>
              <div class="lens-title">
                <h3>{entry.name}</h3>
                <span class="lens-version">v{entry.version}</span>
              </div>
              {#if entry.is_default}
                <span class="default-badge">Default</span>
              {/if}
            </div>
            
            <p class="lens-description">
              {entry.description || 'No description'}
            </p>
            
            <div class="lens-meta">
              <span class="meta-item" title="Heuristics">
                📋 {entry.heuristics_count}
              </span>
              <span class="meta-item" title="Skills">
                ⚡ {entry.skills_count}
              </span>
              {#if entry.version_count > 0}
                <span class="meta-item" title="Versions">
                  📚 {entry.version_count}
                </span>
              {/if}
              <span class="meta-source">{entry.source}</span>
            </div>
            
            {#if entry.tags.length > 0}
              <div class="lens-tags">
                {#each entry.tags.slice(0, 3) as tag}
                  <span class="tag">{tag}</span>
                {/each}
              </div>
            {/if}
            
            <div class="card-actions">
              <Button 
                variant="ghost" 
                size="sm"
                onclick={() => selectLens(entry)}
              >
                View
              </Button>
              
              {#if showSelectButton && onSelect}
                <Button 
                  variant="primary" 
                  size="sm"
                  onclick={() => onSelect(entry.name)}
                >
                  Select
                </Button>
              {/if}
              
              <div class="action-menu">
                <Button variant="ghost" size="sm" onclick={() => handleForkClick(entry.name)}>
                  Fork
                </Button>
                
                {#if entry.is_editable}
                  <Button variant="ghost" size="sm" onclick={() => handleEditClick(entry)}>
                    Edit
                  </Button>
                  <Button variant="ghost" size="sm" onclick={() => loadVersions(entry.name)}>
                    History
                  </Button>
                  <Button variant="ghost" size="sm" onclick={() => handleDeleteClick(entry.name)}>
                    Delete
                  </Button>
                {/if}
                
                {#if !entry.is_default}
                  <Button variant="ghost" size="sm" onclick={() => setDefaultLens(entry.name)}>
                    Set Default
                  </Button>
                {/if}
              </div>
            </div>
          </div>
        {/each}
      </div>
    {/if}
    
  {:else if lensLibrary.view === 'detail'}
    <!-- Detail View -->
    <div class="detail-view">
      <button class="back-button" onclick={goToLibrary}>← Back to Library</button>
      
      {#if lensLibrary.isLoadingDetail}
        <div class="loading-state">Loading lens details...</div>
      {:else if lensLibrary.detail}
        <div class="detail-header">
          <span class="lens-icon large">{getDomainIcon(lensLibrary.detail.domain)}</span>
          <div>
            <h2>{lensLibrary.detail.name}</h2>
            <p class="detail-meta">
              v{lensLibrary.detail.version}
              {#if lensLibrary.detail.author}
                · by {lensLibrary.detail.author}
              {/if}
              {#if lensLibrary.detail.domain}
                · {lensLibrary.detail.domain}
              {/if}
            </p>
          </div>
        </div>
        
        {#if lensLibrary.detail.description}
          <p class="detail-description">{lensLibrary.detail.description}</p>
        {/if}
        
        {#if lensLibrary.detail.heuristics.length > 0}
          <section class="detail-section">
            <h3>Heuristics ({lensLibrary.detail.heuristics.length})</h3>
            <ul class="heuristic-list">
              {#each lensLibrary.detail.heuristics as h}
                <li>
                  <strong>{h.name}</strong>
                  <p>{h.rule}</p>
                </li>
              {/each}
            </ul>
          </section>
        {/if}
        
        {#if lensLibrary.detail.skills.length > 0}
          <section class="detail-section">
            <h3>Skills ({lensLibrary.detail.skills.length})</h3>
            <ul class="skill-list">
              {#each lensLibrary.detail.skills as skill}
                <li>{skill}</li>
              {/each}
            </ul>
          </section>
        {/if}
        
        {#if lensLibrary.detail.communication_style}
          <section class="detail-section">
            <h3>Communication Style</h3>
            <p>{lensLibrary.detail.communication_style}</p>
          </section>
        {/if}
      {/if}
    </div>
    
  {:else if lensLibrary.view === 'editor'}
    <!-- Editor View -->
    <div class="editor-view">
      <div class="editor-header">
        <button class="back-button" onclick={goToLibrary}>← Back to Library</button>
        <h2>Editing: {lensLibrary.selectedLens?.name}</h2>
        <Button 
          variant="primary" 
          onclick={handleSaveClick}
          disabled={lensLibrary.isSaving}
        >
          {lensLibrary.isSaving ? 'Saving...' : 'Save'}
        </Button>
      </div>
      
      {#if lensLibrary.isLoadingDetail}
        <div class="loading-state">Loading lens content...</div>
      {:else}
        <textarea
          class="lens-editor"
          bind:value={editedContent}
          placeholder="Lens YAML content..."
          spellcheck="false"
        ></textarea>
      {/if}
    </div>
    
  {:else if lensLibrary.view === 'versions'}
    <!-- Versions View -->
    <div class="versions-view">
      <button class="back-button" onclick={goToLibrary}>← Back to Library</button>
      <h2>Version History: {lensLibrary.selectedLens?.name}</h2>
      
      {#if lensLibrary.isLoadingVersions}
        <div class="loading-state">Loading version history...</div>
      {:else if lensLibrary.versions.length === 0}
        <div class="empty-state">No version history available</div>
      {:else}
        <div class="version-list">
          {#each [...lensLibrary.versions].reverse() as v, i}
            <div class="version-item" class:is-current={i === 0}>
              <div class="version-header">
                <span class="version-number">v{v.version}</span>
                <span class="version-date">{v.created_at.slice(0, 10)}</span>
                {#if i === 0}
                  <span class="current-badge">Current</span>
                {:else}
                  <Button 
                    variant="ghost" 
                    size="sm"
                    onclick={() => rollbackLens(lensLibrary.selectedLens?.name || '', v.version)}
                  >
                    Rollback
                  </Button>
                {/if}
              </div>
              {#if v.message}
                <p class="version-message">{v.message}</p>
              {/if}
              <p class="version-checksum">{v.checksum}</p>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {/if}
</div>

<!-- Fork Modal -->
<Modal 
  isOpen={showForkModal} 
  onClose={() => showForkModal = false} 
  title="Fork Lens"
>
  <div class="modal-content">
    <p>Create an editable copy of <strong>{forkSourceName}</strong></p>
    
    <label class="field">
      <span>New Name</span>
      <input 
        type="text" 
        bind:value={forkNewName}
        placeholder="my-custom-lens"
      />
    </label>
    
    <label class="field">
      <span>Message (optional)</span>
      <input 
        type="text" 
        bind:value={forkMessage}
        placeholder="Initial fork from..."
      />
    </label>
    
    <div class="modal-actions">
      <Button variant="ghost" onclick={() => showForkModal = false}>
        Cancel
      </Button>
      <Button 
        variant="primary" 
        onclick={handleForkConfirm}
        disabled={isForkingLens || !forkNewName.trim()}
      >
        {isForkingLens ? 'Forking...' : 'Fork Lens'}
      </Button>
    </div>
  </div>
</Modal>

<!-- Delete Confirmation Modal -->
<Modal 
  isOpen={showDeleteModal} 
  onClose={() => showDeleteModal = false} 
  title="Delete Lens"
>
  <div class="modal-content">
    <p>Are you sure you want to delete <strong>{deleteTargetName}</strong>?</p>
    <p class="warning">This action cannot be undone. Version history will be preserved.</p>
    
    <div class="modal-actions">
      <Button variant="ghost" onclick={() => showDeleteModal = false}>
        Cancel
      </Button>
      <button class="delete-button" onclick={handleDeleteConfirm}>
        Delete
      </button>
    </div>
  </div>
</Modal>

<!-- Save Modal -->
<Modal 
  isOpen={showSaveModal} 
  onClose={() => showSaveModal = false} 
  title="Save Lens"
>
  <div class="modal-content">
    <label class="field">
      <span>Version Message (optional)</span>
      <input 
        type="text" 
        bind:value={saveMessage}
        placeholder="What changed?"
      />
    </label>
    
    <label class="field">
      <span>Version Bump</span>
      <select bind:value={saveBump}>
        <option value="patch">Patch (x.x.1)</option>
        <option value="minor">Minor (x.1.0)</option>
        <option value="major">Major (1.0.0)</option>
      </select>
    </label>
    
    <div class="modal-actions">
      <Button variant="ghost" onclick={() => showSaveModal = false}>
        Cancel
      </Button>
      <Button variant="primary" onclick={handleSaveConfirm}>
        Save
      </Button>
    </div>
  </div>
</Modal>

<style>
  .lens-library {
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: var(--spacing-lg);
    overflow-y: auto;
  }
  
  .library-header {
    margin-bottom: var(--spacing-lg);
  }
  
  .library-header h2 {
    font-size: var(--font-xl);
    margin: 0 0 var(--spacing-xs);
    color: var(--text-primary);
  }
  
  .subtitle {
    color: var(--text-secondary);
    margin: 0;
  }
  
  .filters {
    display: flex;
    gap: var(--spacing-md);
    margin-bottom: var(--spacing-lg);
    flex-wrap: wrap;
  }
  
  .search-input {
    flex: 1;
    min-width: 200px;
    padding: var(--spacing-sm) var(--spacing-md);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    color: var(--text-primary);
    font-size: var(--font-sm);
  }
  
  .search-input:focus {
    outline: none;
    border-color: var(--gold);
  }
  
  .filter-select {
    padding: var(--spacing-sm) var(--spacing-md);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    color: var(--text-primary);
    cursor: pointer;
    font-size: var(--font-sm);
  }
  
  .error-banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-sm) var(--spacing-md);
    background: var(--error-surface);
    border: 1px solid var(--error);
    border-radius: var(--radius-md);
    margin-bottom: var(--spacing-md);
    color: var(--error);
  }
  
  .error-banner button {
    background: none;
    border: none;
    color: var(--error);
    cursor: pointer;
    font-size: var(--font-lg);
  }
  
  .lens-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: var(--spacing-md);
  }
  
  .lens-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: var(--spacing-md);
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
    transition: all 0.15s ease;
  }
  
  .lens-card:hover {
    border-color: var(--border-default);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }
  
  .lens-card.is-default {
    border-color: var(--gold);
    background: var(--gold-surface);
  }
  
  .lens-card.is-user {
    border-left: 3px solid var(--accent-green);
  }
  
  .card-header {
    display: flex;
    align-items: flex-start;
    gap: var(--spacing-sm);
  }
  
  .lens-icon {
    font-size: 1.5rem;
    line-height: 1;
  }
  
  .lens-icon.large {
    font-size: 2.5rem;
  }
  
  .lens-title {
    flex: 1;
    min-width: 0;
  }
  
  .lens-title h3 {
    margin: 0;
    font-size: var(--font-md);
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .lens-version {
    font-size: var(--font-xs);
    color: var(--text-tertiary);
  }
  
  .default-badge {
    font-size: var(--font-xs);
    padding: 2px 6px;
    background: var(--gold);
    color: var(--bg-primary);
    border-radius: var(--radius-sm);
    font-weight: 500;
  }
  
  .current-badge {
    font-size: var(--font-xs);
    padding: 2px 6px;
    background: var(--accent-green);
    color: var(--bg-primary);
    border-radius: var(--radius-sm);
    font-weight: 500;
  }
  
  .lens-description {
    color: var(--text-secondary);
    font-size: var(--font-sm);
    margin: 0;
    line-height: 1.4;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
  }
  
  .lens-meta {
    display: flex;
    gap: var(--spacing-md);
    font-size: var(--font-xs);
    color: var(--text-tertiary);
  }
  
  .meta-source {
    margin-left: auto;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  
  .lens-tags {
    display: flex;
    gap: var(--spacing-xs);
    flex-wrap: wrap;
  }
  
  .tag {
    font-size: var(--font-xs);
    padding: 2px 6px;
    background: var(--bg-tertiary);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
  }
  
  .card-actions {
    display: flex;
    gap: var(--spacing-xs);
    margin-top: auto;
    padding-top: var(--spacing-sm);
    border-top: 1px solid var(--border-subtle);
    flex-wrap: wrap;
  }
  
  .action-menu {
    display: flex;
    gap: var(--spacing-xs);
    margin-left: auto;
    flex-wrap: wrap;
  }
  
  .loading-state,
  .empty-state {
    padding: var(--spacing-xl);
    text-align: center;
    color: var(--text-secondary);
  }
  
  /* Detail View */
  .detail-view,
  .editor-view,
  .versions-view {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-md);
  }
  
  .back-button {
    background: none;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    font-size: var(--font-sm);
    padding: 0;
    align-self: flex-start;
  }
  
  .back-button:hover {
    color: var(--text-primary);
  }
  
  .detail-header {
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
  }
  
  .detail-header h2 {
    margin: 0;
    color: var(--text-primary);
  }
  
  .detail-meta {
    color: var(--text-secondary);
    font-size: var(--font-sm);
    margin: 0;
  }
  
  .detail-description {
    color: var(--text-secondary);
    line-height: 1.5;
  }
  
  .detail-section {
    margin-top: var(--spacing-md);
  }
  
  .detail-section h3 {
    font-size: var(--font-md);
    margin: 0 0 var(--spacing-sm);
    color: var(--text-primary);
  }
  
  .heuristic-list,
  .skill-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
  }
  
  .heuristic-list li {
    padding: var(--spacing-sm);
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
  }
  
  .heuristic-list li strong {
    color: var(--text-primary);
  }
  
  .heuristic-list li p {
    margin: var(--spacing-xs) 0 0;
    color: var(--text-secondary);
    font-size: var(--font-sm);
  }
  
  .skill-list li {
    padding: var(--spacing-xs) var(--spacing-sm);
    background: var(--bg-secondary);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
  }
  
  /* Editor View */
  .editor-header {
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
  }
  
  .editor-header h2 {
    flex: 1;
    margin: 0;
    color: var(--text-primary);
  }
  
  .lens-editor {
    flex: 1;
    min-height: 400px;
    padding: var(--spacing-md);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    color: var(--text-primary);
    font-family: var(--font-mono);
    font-size: var(--font-sm);
    resize: vertical;
  }
  
  .lens-editor:focus {
    outline: none;
    border-color: var(--gold);
  }
  
  /* Versions View */
  .version-list {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
  }
  
  .version-item {
    padding: var(--spacing-md);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
  }
  
  .version-item.is-current {
    border-color: var(--gold);
  }
  
  .version-header {
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
  }
  
  .version-number {
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .version-date {
    color: var(--text-tertiary);
    font-size: var(--font-sm);
  }
  
  .version-message {
    margin: var(--spacing-xs) 0 0;
    color: var(--text-secondary);
  }
  
  .version-checksum {
    margin: var(--spacing-xs) 0 0;
    color: var(--text-tertiary);
    font-family: var(--font-mono);
    font-size: var(--font-xs);
  }
  
  /* Modal styles */
  .modal-content {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-md);
    min-width: 350px;
  }
  
  .field {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
  }
  
  .field span {
    font-size: var(--font-sm);
    color: var(--text-secondary);
  }
  
  .field input,
  .field select {
    padding: var(--spacing-sm) var(--spacing-md);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    color: var(--text-primary);
    font-size: var(--font-sm);
  }
  
  .field input:focus,
  .field select:focus {
    outline: none;
    border-color: var(--gold);
  }
  
  .warning {
    color: var(--warning);
    font-size: var(--font-sm);
  }
  
  .delete-button {
    padding: var(--spacing-sm) var(--spacing-md);
    background: var(--error);
    color: white;
    border: none;
    border-radius: var(--radius-md);
    cursor: pointer;
    font-size: var(--font-sm);
    font-weight: 500;
  }
  
  .delete-button:hover {
    opacity: 0.9;
  }
  
  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--spacing-sm);
    padding-top: var(--spacing-md);
  }
</style>
