<!--
  LensLibrary — Full lens library browser (RFC-070, RFC-100)
  
  S-Tier lens library with:
  - Featured section for recommended lenses
  - Staggered card animations
  - Keyboard navigation (j/k/Enter/Escape)
  - Hover previews with heuristics
  - Context menus
  - Loading skeletons
  - Power indicators
  - View mode toggle (grid/list)
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { fly } from 'svelte/transition';
  import Button from './Button.svelte';
  import Modal from './Modal.svelte';
  import { 
    LensCardSkeleton,
    LensCardMotes,
    LensHoverPreview,
    LensContextMenu,
    LensEmptyState,
    LensHeroCard,
    LensEditor,
  } from './lens';
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
    backToList,
    loadVersions,
    rollbackLens,
    saveLens,
    clearError,
    exportLens,
    recordLensUsage,
  } from '../stores/lensLibrary.svelte';
  import type { LensLibraryEntry } from '$lib/types';
  
  interface Props {
    onSelect?: (lensName: string) => void;
    showSelectButton?: boolean;
  }
  
  let { onSelect, showSelectButton = false }: Props = $props();
  
  // View mode
  type ViewMode = 'grid' | 'list';
  let viewMode = $state<ViewMode>('grid');
  
  // Keyboard navigation
  let focusIndex = $state(-1);
  let searchInputRef = $state<HTMLInputElement | null>(null);
  
  // Hover preview
  let previewLens = $state<LensLibraryEntry | null>(null);
  let previewTimeout: ReturnType<typeof setTimeout>;
  
  // Context menu
  let contextMenu = $state<{ visible: boolean; x: number; y: number; lens: LensLibraryEntry | null }>({
    visible: false,
    x: 0,
    y: 0,
    lens: null,
  });
  
  // Search suggestions
  let showSuggestions = $state(false);
  
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
  
  // Motes ref - single component for current hover
  let activeMoteComponent: LensCardMotes | null = $state(null);
  
  onMount(() => {
    const entries = lensLibrary.entries;
    if (!Array.isArray(entries) || entries.length === 0) {
      loadLibrary();
    }
  });
  
  // Computed: Filtered entries
  const filteredEntries = $derived(getFilteredEntries());
  const availableDomains = $derived(getAvailableDomains());
  // defaultLens available for future features
  void getDefaultLens;
  
  // Computed: Featured lenses (default + top by heuristics)
  const featuredLenses = $derived.by(() => {
    const entries = lensLibrary.entries;
    if (!Array.isArray(entries)) return [];
    
    const featured: LensLibraryEntry[] = [];
    
    // Always include default
    const defLens = entries.find(e => e.is_default);
    if (defLens) featured.push(defLens);
    
    // Add top by heuristics count (proxy for "power")
    const byPower = [...entries]
      .filter(e => !e.is_default)
      .sort((a, b) => b.heuristics_count - a.heuristics_count)
      .slice(0, 2);
    
    return [...featured, ...byPower];
  });
  
  // Computed: Search suggestions
  const searchSuggestions = $derived.by(() => {
    if (!lensLibrary.filter.search || lensLibrary.filter.search.length < 2) return [];
    
    const entries = lensLibrary.entries;
    if (!Array.isArray(entries)) return [];
    
    const q = lensLibrary.filter.search.toLowerCase();
    const suggestions = new Set<string>();
    
    for (const entry of entries) {
      if (entry.name.toLowerCase().includes(q)) {
        suggestions.add(entry.name);
      }
      if (entry.domain?.toLowerCase().includes(q)) {
        suggestions.add(`domain:${entry.domain}`);
      }
      for (const tag of entry.tags) {
        if (tag.toLowerCase().includes(q)) {
          suggestions.add(`tag:${tag}`);
        }
      }
    }
    
    return Array.from(suggestions).slice(0, 5);
  });
  
  // Computed: Power level for card
  function getPowerLevel(entry: LensLibraryEntry): 'high' | 'medium' | 'low' {
    if (entry.heuristics_count >= 8) return 'high';
    if (entry.heuristics_count >= 4) return 'medium';
    return 'low';
  }
  
  // Check if showing featured section
  const showFeatured = $derived(
    !lensLibrary.filter.search && 
    lensLibrary.filter.source === 'all' && 
    !lensLibrary.filter.domain &&
    featuredLenses.length > 0
  );
  
  // Computed: Similar lenses for detail view (O(n) once, not O(n²) in template)
  const similarLenses = $derived.by(() => {
    if (!lensLibrary.detail) return [];
    const entries = lensLibrary.entries;
    if (!Array.isArray(entries)) return [];
    const detailName = lensLibrary.detail.name;
    const detailDomain = lensLibrary.detail.domain;
    return entries
      .filter(e => e.name !== detailName && e.domain === detailDomain)
      .slice(0, 4);
  });
  
  // Keyboard navigation handler
  function handleKeydown(e: KeyboardEvent) {
    if (lensLibrary.view !== 'library') return;
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
      if (e.key === 'Escape') {
        (e.target as HTMLElement).blur();
        focusIndex = -1;
      }
      return;
    }
    
    const entries = filteredEntries;
    
    switch (e.key) {
      case 'j':
      case 'ArrowDown':
        e.preventDefault();
        focusIndex = Math.min(focusIndex + 1, entries.length - 1);
        break;
      case 'k':
      case 'ArrowUp':
        e.preventDefault();
        focusIndex = Math.max(focusIndex - 1, 0);
        break;
      case '/':
        e.preventDefault();
        searchInputRef?.focus();
        break;
      case 'Enter':
        if (focusIndex >= 0 && entries[focusIndex]) {
          handleSelectLens(entries[focusIndex]);
        }
        break;
      case 'Escape':
        focusIndex = -1;
        contextMenu = { ...contextMenu, visible: false };
        break;
      case 'f':
        if (focusIndex >= 0 && entries[focusIndex]) {
          e.preventDefault();
          handleForkClick(entries[focusIndex].name);
        }
        break;
      case 'e':
        if (focusIndex >= 0 && entries[focusIndex]?.is_editable) {
          e.preventDefault();
          handleEditClick(entries[focusIndex]);
        }
        break;
      case 'd':
        if (focusIndex >= 0 && entries[focusIndex] && !entries[focusIndex].is_default) {
          e.preventDefault();
          setDefaultLens(entries[focusIndex].name);
        }
        break;
    }
  }
  
  // Hover preview handlers
  function schedulePreview(lens: LensLibraryEntry) {
    previewTimeout = setTimeout(() => {
      previewLens = lens;
    }, 300);
  }
  
  function cancelPreview() {
    clearTimeout(previewTimeout);
    previewLens = null;
  }
  
  // Context menu handler
  function showContextMenuHandler(e: MouseEvent, lens: LensLibraryEntry) {
    e.preventDefault();
    contextMenu = {
      visible: true,
      x: e.clientX,
      y: e.clientY,
      lens,
    };
  }
  
  function hideContextMenu() {
    contextMenu = { ...contextMenu, visible: false };
  }
  
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
  
  function handleClearFilters() {
    setFilter({ search: '', source: 'all', domain: null });
    focusIndex = -1;
  }
  
  async function handleExportLens(lens: LensLibraryEntry) {
    const result = await exportLens(lens.name);
    if (result?.success) {
      // Could show a toast notification here
      console.log(`Exported lens to: ${result.path}`);
    }
  }
  
  async function handleSelectLens(entry: LensLibraryEntry) {
    // Record usage for sparklines (RFC-100)
    recordLensUsage(entry.name);
    selectLens(entry);
  }
  
  function handleCardMouseEnter(e: MouseEvent, entry: LensLibraryEntry) {
    schedulePreview(entry);
    activeMoteComponent?.spawnMotes(e);
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="lens-library">
  {#if lensLibrary.view === 'library'}
    <!-- Library Browser -->
    <header class="library-header">
      <div class="header-content">
        <h2>Lens Library</h2>
        <p class="subtitle">Browse and manage your expertise containers</p>
      </div>
      
      <!-- View mode toggle -->
      <div class="view-toggle">
        <button 
          class="toggle-btn"
          class:active={viewMode === 'grid'}
          onclick={() => viewMode = 'grid'}
          title="Grid view"
          aria-label="Grid view"
        >
          ⊞
        </button>
        <button 
          class="toggle-btn"
          class:active={viewMode === 'list'}
          onclick={() => viewMode = 'list'}
          title="List view"
          aria-label="List view"
        >
          ≡
        </button>
      </div>
    </header>
    
    <!-- Filters -->
    <div class="filters">
      <div class="search-wrapper">
        <input
          type="text"
          placeholder="Search lenses... (press /)"
          class="search-input"
          bind:this={searchInputRef}
          value={lensLibrary.filter.search}
          oninput={(e) => setFilter({ search: e.currentTarget.value })}
          onfocus={() => showSuggestions = true}
          onblur={() => setTimeout(() => showSuggestions = false, 200)}
        />
        
        {#if showSuggestions && searchSuggestions.length > 0}
          <div class="search-suggestions" transition:fly={{ y: -8, duration: 100 }}>
            {#each searchSuggestions as suggestion (suggestion)}
              <button 
                class="suggestion"
                onmousedown={(e) => { e.preventDefault(); setFilter({ search: suggestion }); }}
              >
                🔍 {suggestion}
              </button>
            {/each}
          </div>
        {/if}
      </div>
      
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
        {#each availableDomains as domain (domain)}
          <option value={domain}>{domain}</option>
        {/each}
      </select>
    </div>
    
    <!-- Error display -->
    {#if lensLibrary.error}
      <div class="error-banner" transition:fly={{ y: -10, duration: 150 }}>
        <span>{lensLibrary.error}</span>
        <button onclick={clearError}>×</button>
      </div>
    {/if}
    
    <!-- Loading skeleton -->
    {#if lensLibrary.isLoading}
      <LensCardSkeleton count={6} />
    {:else if filteredEntries.length === 0}
      <!-- Empty state -->
      <LensEmptyState 
        hasFilters={!!lensLibrary.filter.search || lensLibrary.filter.source !== 'all' || !!lensLibrary.filter.domain}
        searchQuery={lensLibrary.filter.search}
        onClearFilters={handleClearFilters}
      />
    {:else}
      <!-- Featured section -->
      {#if showFeatured}
        <section class="featured-section" transition:fly={{ y: -20, duration: 300 }}>
          <h3 class="section-title">
            <span class="section-icon">✨</span>
            Recommended
          </h3>
          <div class="featured-grid">
            {#each featuredLenses as lens, i (lens.path)}
              <LensHeroCard 
                {lens} 
                index={i}
                onclick={() => handleSelectLens(lens)}
              />
            {/each}
          </div>
        </section>
      {/if}
      
      <!-- All lenses section -->
      <section class="all-lenses-section">
        {#if showFeatured}
          <h3 class="section-title">
            <span class="section-icon">📚</span>
            All Lenses
          </h3>
        {/if}
        
        <!-- Lens Grid/List -->
        <div 
          class="lens-grid"
          class:list-view={viewMode === 'list'}
          role="listbox" 
          aria-label="Lens library"
        >
          {#each filteredEntries as entry, i (entry.path)}
            <div 
              class="lens-card"
              class:is-default={entry.is_default}
              class:is-user={entry.source === 'user'}
              class:keyboard-focus={focusIndex === i}
              data-power={getPowerLevel(entry)}
              style="--index: {i}; --heuristics-count: {entry.heuristics_count}"
              role="option"
              aria-selected={focusIndex === i}
              tabindex={focusIndex === i ? 0 : -1}
              onmouseenter={(e) => handleCardMouseEnter(e, entry)}
              onmouseleave={cancelPreview}
              oncontextmenu={(e) => showContextMenuHandler(e, entry)}
              transition:fly={{ y: 12, duration: 300, delay: Math.min(i * 50, 300) }}
            >
              <LensCardMotes bind:this={activeMoteComponent} />
              
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
                  {#each entry.tags.slice(0, 3) as tag (tag)}
                    <span class="tag">{tag}</span>
                  {/each}
                </div>
              {/if}
              
              <div class="card-actions">
              <Button 
                variant="ghost" 
                size="sm"
                onclick={() => handleSelectLens(entry)}
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
              
              <!-- Hover preview -->
              {#if previewLens?.name === entry.name}
                <LensHoverPreview 
                  lens={entry}
                  topHeuristics={entry.top_heuristics}
                  onView={() => handleSelectLens(entry)}
                />
              {/if}
            </div>
          {/each}
        </div>
      </section>
    {/if}
    
    <!-- Keyboard hints -->
    <div class="keyboard-hints">
      <span class="hint"><kbd>j</kbd>/<kbd>k</kbd> navigate</span>
      <span class="hint"><kbd>Enter</kbd> view</span>
      <span class="hint"><kbd>/</kbd> search</span>
      <span class="hint"><kbd>f</kbd> fork</span>
    </div>
    
  {:else if lensLibrary.view === 'detail'}
    <!-- Detail View -->
    <div class="detail-view" transition:fly={{ x: 20, duration: 200 }}>
      <button class="back-button" onclick={backToList}>← Back to Library</button>
      
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
              {#each lensLibrary.detail.heuristics as h, i (h.name)}
                <li transition:fly={{ y: 8, delay: i * 30 }}>
                  <div class="heuristic-header">
                    <span 
                      class="priority-indicator" 
                      style="--priority: {h.priority}"
                    ></span>
                    <strong>{h.name}</strong>
                  </div>
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
              {#each lensLibrary.detail.skills as skill (skill)}
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
        
        <!-- Similar lenses -->
        {#if similarLenses.length > 0}
          <section class="detail-section similar-section">
            <h3>Similar Expertise</h3>
            <div class="similar-grid">
              {#each similarLenses as similar (similar.path)}
                <button 
                  class="mini-lens-card"
                  onclick={() => handleSelectLens(similar)}
                >
                  <span class="mini-icon">{getDomainIcon(similar.domain)}</span>
                  <span class="mini-name">{similar.name}</span>
                  <span class="mini-count">{similar.heuristics_count} heuristics</span>
                </button>
              {/each}
            </div>
          </section>
        {/if}
      {/if}
    </div>
    
  {:else if lensLibrary.view === 'editor'}
    <!-- Editor View -->
    <div class="editor-view" transition:fly={{ x: 20, duration: 200 }}>
      <div class="editor-header">
        <button class="back-button" onclick={backToList}>← Back to Library</button>
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
        <LensEditor 
          value={editedContent}
          onchange={(v) => editedContent = v}
        />
      {/if}
    </div>
    
  {:else if lensLibrary.view === 'versions'}
    <!-- Versions View -->
    <div class="versions-view" transition:fly={{ x: 20, duration: 200 }}>
      <button class="back-button" onclick={backToList}>← Back to Library</button>
      <h2>Version History: {lensLibrary.selectedLens?.name}</h2>
      
      {#if lensLibrary.isLoadingVersions}
        <div class="loading-state">Loading version history...</div>
      {:else if lensLibrary.versions.length === 0}
        <div class="empty-state">No version history available</div>
      {:else}
        <div class="version-list">
          {#each [...lensLibrary.versions].reverse() as v, i (v.version)}
            <div 
              class="version-item" 
              class:is-current={i === 0}
              transition:fly={{ y: 8, delay: i * 50 }}
            >
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

<!-- Context Menu -->
{#if contextMenu.visible && contextMenu.lens}
  <LensContextMenu 
    lens={contextMenu.lens}
    x={contextMenu.x}
    y={contextMenu.y}
    onView={() => handleSelectLens(contextMenu.lens!)}
    onFork={() => handleForkClick(contextMenu.lens!.name)}
    onEdit={contextMenu.lens.is_editable ? () => handleEditClick(contextMenu.lens!) : undefined}
    onSetDefault={!contextMenu.lens.is_default ? () => setDefaultLens(contextMenu.lens!.name) : undefined}
    onExport={() => handleExportLens(contextMenu.lens!)}
    onClose={hideContextMenu}
  />
{/if}

<!-- Fork Modal -->
<Modal 
  isOpen={showForkModal} 
  onClose={() => showForkModal = false} 
  title="Fork Lens"
>
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
</Modal>

<!-- Delete Confirmation Modal -->
<Modal 
  isOpen={showDeleteModal} 
  onClose={() => showDeleteModal = false} 
  title="Delete Lens"
>
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
</Modal>

<!-- Save Modal -->
<Modal 
  isOpen={showSaveModal} 
  onClose={() => showSaveModal = false} 
  title="Save Lens"
>
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
</Modal>

<style>
  .lens-library {
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: var(--space-4);
    overflow-y: auto;
  }
  
  /* Header */
  .library-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: var(--space-4);
  }
  
  .header-content h2 {
    font-size: var(--text-xl);
    margin: 0 0 var(--space-1);
    color: var(--text-primary);
  }
  
  .subtitle {
    color: var(--text-secondary);
    margin: 0;
    font-size: var(--text-sm);
  }
  
  .view-toggle {
    display: flex;
    gap: 2px;
    background: var(--bg-secondary);
    padding: 2px;
    border-radius: var(--radius-md);
    border: 1px solid var(--border-subtle);
  }
  
  .toggle-btn {
    padding: var(--space-2);
    background: transparent;
    border: none;
    border-radius: var(--radius-sm);
    color: var(--text-tertiary);
    cursor: pointer;
    font-size: var(--text-base);
    line-height: 1;
    transition: all var(--transition-fast);
  }
  
  .toggle-btn:hover {
    color: var(--text-secondary);
  }
  
  .toggle-btn.active {
    background: var(--bg-tertiary);
    color: var(--text-primary);
  }
  
  /* Filters */
  .filters {
    display: flex;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
    flex-wrap: wrap;
  }
  
  .search-wrapper {
    position: relative;
    flex: 1;
    min-width: 200px;
  }
  
  .search-input {
    width: 100%;
    padding: var(--space-2) var(--space-3);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    color: var(--text-primary);
    font-size: var(--text-sm);
  }
  
  .search-input:focus {
    outline: none;
    border-color: var(--ui-gold);
    box-shadow: var(--glow-gold-subtle);
  }
  
  .search-suggestions {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    background: var(--bg-elevated);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-lg);
    z-index: var(--z-dropdown);
    margin-top: var(--space-1);
    overflow: hidden;
  }
  
  .suggestion {
    display: block;
    width: 100%;
    padding: var(--space-2) var(--space-3);
    background: transparent;
    border: none;
    color: var(--text-secondary);
    font-size: var(--text-sm);
    text-align: left;
    cursor: pointer;
  }
  
  .suggestion:hover {
    background: var(--accent-hover);
    color: var(--text-primary);
  }
  
  .filter-select {
    padding: var(--space-2) var(--space-3);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    color: var(--text-primary);
    cursor: pointer;
    font-size: var(--text-sm);
  }
  
  .error-banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-2) var(--space-3);
    background: var(--error-bg);
    border: 1px solid var(--error);
    border-radius: var(--radius-md);
    margin-bottom: var(--space-3);
    color: var(--error);
    font-size: var(--text-sm);
  }
  
  .error-banner button {
    background: none;
    border: none;
    color: var(--error);
    cursor: pointer;
    font-size: var(--text-lg);
    line-height: 1;
  }
  
  /* Featured section */
  .featured-section {
    margin-bottom: var(--space-6);
  }
  
  .section-title {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin: 0 0 var(--space-3);
  }
  
  .section-icon {
    font-size: var(--text-base);
  }
  
  .featured-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: var(--space-4);
  }
  
  /* All lenses */
  .all-lenses-section {
    flex: 1;
  }
  
  .lens-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: var(--space-3);
  }
  
  .lens-grid.list-view {
    grid-template-columns: 1fr;
  }
  
  .lens-grid.list-view .lens-card {
    flex-direction: row;
    align-items: center;
    gap: var(--space-4);
  }
  
  .lens-grid.list-view .card-header {
    flex-shrink: 0;
    width: 180px;
  }
  
  .lens-grid.list-view .lens-description {
    flex: 1;
    -webkit-line-clamp: 1;
    line-clamp: 1;
  }
  
  .lens-grid.list-view .lens-meta,
  .lens-grid.list-view .lens-tags {
    flex-shrink: 0;
  }
  
  /* Lens card */
  .lens-card {
    position: relative;
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: var(--space-3);
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    transition: all var(--transition-normal);
    animation: cardReveal 0.4s ease-out backwards;
    animation-delay: calc(var(--index) * var(--card-stagger));
    
    /* Power indicator via border */
    border-left: 3px solid;
    border-left-color: var(--lens-power-low);
  }
  
  .lens-card[data-power="medium"] {
    border-left-color: var(--lens-power-medium);
  }
  
  .lens-card[data-power="high"] {
    border-left-color: var(--lens-power-high);
    box-shadow: var(--glow-gold-subtle);
  }
  
  @keyframes cardReveal {
    from {
      opacity: 0;
      transform: translateY(12px) scale(0.97);
    }
    to {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }
  
  .lens-card:hover {
    border-color: var(--border-default);
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
  }
  
  .lens-card.keyboard-focus {
    outline: 2px solid var(--ui-gold);
    outline-offset: 2px;
    box-shadow: var(--glow-gold);
  }
  
  .lens-card.is-default {
    border-color: var(--ui-gold);
    background: linear-gradient(
      135deg,
      var(--accent-hover) 0%,
      var(--bg-secondary) 100%
    );
  }
  
  .lens-card.is-user {
    border-left-color: var(--success);
  }
  
  .card-header {
    display: flex;
    align-items: flex-start;
    gap: var(--space-2);
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
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .lens-version {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .default-badge {
    font-size: var(--text-xs);
    padding: 2px 6px;
    background: var(--ui-gold);
    color: var(--bg-primary);
    border-radius: var(--radius-sm);
    font-weight: 500;
  }
  
  .current-badge {
    font-size: var(--text-xs);
    padding: 2px 6px;
    background: var(--success);
    color: var(--bg-primary);
    border-radius: var(--radius-sm);
    font-weight: 500;
  }
  
  .lens-description {
    color: var(--text-secondary);
    font-size: var(--text-sm);
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
    gap: var(--space-3);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .meta-source {
    margin-left: auto;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  
  .lens-tags {
    display: flex;
    gap: var(--space-1);
    flex-wrap: wrap;
  }
  
  .tag {
    font-size: var(--text-xs);
    padding: 2px 6px;
    background: var(--bg-tertiary);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
  }
  
  .card-actions {
    display: flex;
    gap: var(--space-1);
    margin-top: auto;
    padding-top: var(--space-2);
    border-top: 1px solid var(--border-subtle);
    flex-wrap: wrap;
  }
  
  .action-menu {
    display: flex;
    gap: var(--space-1);
    margin-left: auto;
    flex-wrap: wrap;
  }
  
  .loading-state,
  .empty-state {
    padding: var(--space-8);
    text-align: center;
    color: var(--text-secondary);
  }
  
  /* Keyboard hints */
  .keyboard-hints {
    display: flex;
    gap: var(--space-4);
    padding: var(--space-3);
    margin-top: var(--space-4);
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    justify-content: center;
  }
  
  .hint {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .hint kbd {
    display: inline-block;
    padding: 2px 6px;
    background: var(--bg-tertiary);
    border-radius: var(--radius-sm);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-secondary);
    margin: 0 2px;
  }
  
  /* Detail View */
  .detail-view,
  .editor-view,
  .versions-view {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  
  .back-button {
    background: none;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    font-size: var(--text-sm);
    padding: 0;
    align-self: flex-start;
    transition: color var(--transition-fast);
  }
  
  .back-button:hover {
    color: var(--text-primary);
  }
  
  .detail-header {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }
  
  .detail-header h2 {
    margin: 0;
    color: var(--text-primary);
  }
  
  .detail-meta {
    color: var(--text-secondary);
    font-size: var(--text-sm);
    margin: 0;
  }
  
  .detail-description {
    color: var(--text-secondary);
    line-height: 1.5;
  }
  
  .detail-section {
    margin-top: var(--space-3);
  }
  
  .detail-section h3 {
    font-size: var(--text-base);
    margin: 0 0 var(--space-2);
    color: var(--text-primary);
  }
  
  .heuristic-list,
  .skill-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  
  .heuristic-list li {
    padding: var(--space-2);
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
  }
  
  .heuristic-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  
  .priority-indicator {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: color-mix(
      in oklch,
      var(--ui-gold-pale) calc(100% - var(--priority, 0.5) * 100%),
      var(--radiant-gold) calc(var(--priority, 0.5) * 100%)
    );
  }
  
  .heuristic-list li strong {
    color: var(--text-primary);
  }
  
  .heuristic-list li p {
    margin: var(--space-1) 0 0;
    color: var(--text-secondary);
    font-size: var(--text-sm);
  }
  
  .skill-list li {
    padding: var(--space-1) var(--space-2);
    background: var(--bg-secondary);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-size: var(--text-sm);
  }
  
  /* Similar lenses */
  .similar-section {
    padding-top: var(--space-4);
    border-top: 1px solid var(--border-subtle);
  }
  
  .similar-grid {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  
  .mini-lens-card {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  
  .mini-lens-card:hover {
    background: var(--bg-tertiary);
    border-color: var(--border-default);
  }
  
  .mini-icon {
    font-size: var(--text-base);
  }
  
  .mini-name {
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--text-primary);
  }
  
  .mini-count {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  /* Editor View */
  .editor-header {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }
  
  .editor-header h2 {
    flex: 1;
    margin: 0;
    color: var(--text-primary);
  }
  
  /* Versions View */
  .version-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  
  .version-item {
    padding: var(--space-3);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
  }
  
  .version-item.is-current {
    border-color: var(--ui-gold);
  }
  
  .version-header {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }
  
  .version-number {
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .version-date {
    color: var(--text-tertiary);
    font-size: var(--text-sm);
  }
  
  .version-message {
    margin: var(--space-1) 0 0;
    color: var(--text-secondary);
    font-size: var(--text-sm);
  }
  
  .version-checksum {
    margin: var(--space-1) 0 0;
    color: var(--text-tertiary);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
  }
  
  /* Modal form styles */
  .field {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  
  .field span {
    font-size: var(--text-sm);
    color: var(--text-secondary);
  }
  
  .field input,
  .field select {
    padding: var(--space-2) var(--space-3);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    color: var(--text-primary);
    font-size: var(--text-sm);
  }
  
  .field input:focus,
  .field select:focus {
    outline: none;
    border-color: var(--ui-gold);
  }
  
  .warning {
    color: var(--warning);
    font-size: var(--text-sm);
  }
  
  .delete-button {
    padding: var(--space-2) var(--space-3);
    background: var(--error);
    color: white;
    border: none;
    border-radius: var(--radius-md);
    cursor: pointer;
    font-size: var(--text-sm);
    font-weight: 500;
  }
  
  .delete-button:hover {
    opacity: 0.9;
  }
  
  @media (prefers-reduced-motion: reduce) {
    .lens-card {
      animation: none;
    }
  }
</style>
