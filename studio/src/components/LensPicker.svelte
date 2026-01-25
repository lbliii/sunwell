<!--
  LensPicker — Lens selection modal (RFC-064)
  
  Allows user to select a lens before starting a project.
  Features auto-detect option and lens preview.
-->
<script lang="ts">
  import { untrack } from 'svelte';
  import Modal from './Modal.svelte';
  import Button from './Button.svelte';
  import Spinner from './ui/Spinner.svelte';
  import { 
    lens, 
    loadLenses, 
    loadLensDetail, 
    clearLensPreview,
    getDomainIcon,
  } from '../stores/lens.svelte';
  import { goToLibrary } from '../stores/app.svelte';
  
  interface Props {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: (lensName: string | null, autoSelect: boolean) => void;
  }
  
  let { isOpen, onClose, onConfirm }: Props = $props();
  
  let selectedLens = $state<string | null>(null);
  let autoSelect = $state(true);
  let searchQuery = $state('');
  
  // Load lenses when modal opens - use untrack to prevent reactive loop
  $effect(() => {
    if (isOpen) {
      untrack(() => {
        if (lens.available.length === 0 && !lens.isLoading) {
          loadLenses();
        }
      });
    }
  });
  
  // Filter lenses by search
  const filteredLenses = $derived.by(() => {
    if (!searchQuery) return lens.available;
    const q = searchQuery.toLowerCase();
    return lens.available.filter(l => 
      l.name.toLowerCase().includes(q) ||
      (l.domain?.toLowerCase().includes(q)) ||
      (l.description?.toLowerCase().includes(q))
    );
  });
  
  // Group lenses by domain
  const groupedLenses = $derived.by(() => {
    const grouped = new Map<string, typeof lens.available>();
    for (const l of filteredLenses) {
      const domain = l.domain || 'general';
      const existing = grouped.get(domain) || [];
      grouped.set(domain, [...existing, l]);
    }
    return grouped;
  });
  
  function handleSelect(lens: { name: string; path: string }) {
    selectedLens = lens.name;
    autoSelect = false;
    // Extract slug from path (e.g., "tech-writer" from "/path/to/tech-writer.lens")
    const slug = lens.path.split('/').pop()?.replace('.lens', '') ?? lens.name;
    loadLensDetail(slug);
  }
  
  function handleAutoSelect() {
    selectedLens = null;
    autoSelect = true;
    clearLensPreview();
  }
  
  function handleConfirm() {
    onConfirm(selectedLens, autoSelect);
    onClose();
  }
  
  function handleClose() {
    clearLensPreview();
    onClose();
  }
  
  function handleBrowseLibrary() {
    clearLensPreview();
    onClose();
    goToLibrary();
  }
</script>

<Modal isOpen={isOpen} onClose={handleClose} title="Select Expertise">
  <div class="lens-picker">
    <!-- Search -->
    <div class="search-section">
      <input
        type="text"
        placeholder="Search lenses..."
        bind:value={searchQuery}
        class="search-input"
      />
    </div>
    
    <!-- Auto-select option -->
    <button
      class="lens-option auto-option"
      class:selected={autoSelect}
      onclick={handleAutoSelect}
      type="button"
    >
      <div class="lens-icon">✨</div>
      <div class="lens-info">
        <div class="lens-name">Auto-detect</div>
        <div class="lens-description">Let Sunwell choose based on your goal</div>
      </div>
      {#if autoSelect}
        <div class="check-mark">✓</div>
      {/if}
    </button>
    
    <!-- Lens list -->
    <div class="lens-list">
      {#if lens.isLoading}
        <div class="loading-state">
          <Spinner style="dots" />
          <span>Loading lenses...</span>
        </div>
      {:else if lens.error}
        <div class="error-state">{lens.error}</div>
      {:else}
        {#each [...groupedLenses] as [domain, lenses] (domain)}
          <div class="domain-group">
            <div class="domain-header">{domain}</div>
            {#each lenses as l (l.name)}
              <button
                class="lens-option"
                class:selected={selectedLens === l.name}
                onclick={() => handleSelect(l)}
                type="button"
              >
                <div class="lens-icon">{getDomainIcon(l.domain)}</div>
                <div class="lens-info">
                  <div class="lens-name">{l.name}</div>
                  <div class="lens-description">
                    {l.description || `${l.heuristics_count} heuristics`}
                  </div>
                </div>
                {#if selectedLens === l.name}
                  <div class="check-mark">✓</div>
                {/if}
              </button>
            {/each}
          </div>
        {/each}
      {/if}
    </div>
    
    <!-- Preview panel -->
    {#if lens.previewLens}
      <div class="lens-preview">
        <div class="preview-header">
          <h3>{lens.previewLens.name}</h3>
          <span class="version">v{lens.previewLens.version}</span>
        </div>
        {#if lens.previewLens.description}
          <p class="preview-description">{lens.previewLens.description}</p>
        {/if}
        {#if lens.previewLens.heuristics.length > 0}
          <div class="preview-section">
            <h4>Heuristics</h4>
            <ul class="heuristics-list">
              {#each lens.previewLens.heuristics.slice(0, 3) as h (h.name)}
                <li>
                  <strong>{h.name}</strong>
                  <span>{h.rule}</span>
                </li>
              {/each}
              {#if lens.previewLens.heuristics.length > 3}
                <li class="more">+{lens.previewLens.heuristics.length - 3} more</li>
              {/if}
            </ul>
          </div>
        {/if}
        {#if lens.previewLens.communication_style}
          <div class="preview-section">
            <h4>Communication</h4>
            <p>{lens.previewLens.communication_style}</p>
          </div>
        {/if}
      </div>
    {/if}
    
    <!-- Actions -->
    <div class="actions">
      <button class="browse-library-link" onclick={handleBrowseLibrary}>
        📚 Browse Full Library
      </button>
      <div class="action-buttons">
        <Button variant="ghost" onclick={handleClose}>Cancel</Button>
        <Button variant="primary" onclick={handleConfirm}>
          {autoSelect ? 'Use Auto-detect' : `Use ${selectedLens}`}
        </Button>
      </div>
    </div>
  </div>
</Modal>

<style>
  .lens-picker {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    min-width: 400px;
    max-height: 60vh;
  }
  
  .search-section {
    padding: 0 var(--space-2);
  }
  
  .search-input {
    width: 100%;
    padding: var(--space-2) var(--space-3);
    background: var(--bg-secondary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    color: var(--text-primary);
    font-size: var(--text-sm);
    font-family: var(--font-mono);
  }
  
  .search-input::placeholder {
    color: var(--text-tertiary);
  }
  
  .search-input:focus {
    outline: none;
    border-color: var(--gold-dim);
    box-shadow: 0 0 0 2px var(--ui-gold-15);
  }
  
  .lens-list {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    max-height: 250px;
  }
  
  .domain-group {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  
  .domain-header {
    font-size: var(--text-xs);
    font-weight: 600;
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: var(--space-2) var(--space-3);
  }
  
  .lens-option {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3);
    background: transparent;
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all 0.15s ease;
    text-align: left;
    width: 100%;
    font-family: inherit;
  }
  
  .lens-option:hover {
    background: var(--accent-hover);
    border-color: var(--border-emphasis);
  }
  
  .lens-option.selected {
    background: rgba(201, 162, 39, 0.12);
    border-color: var(--gold-dim);
  }
  
  .auto-option {
    background: var(--bg-secondary);
  }
  
  .lens-icon {
    font-size: 1.25rem;
    width: 2rem;
    text-align: center;
  }
  
  .lens-info {
    flex: 1;
    min-width: 0;
  }
  
  .lens-name {
    font-weight: 500;
    color: var(--text-primary);
  }
  
  .lens-description {
    font-size: var(--text-sm);
    color: var(--text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .check-mark {
    color: var(--gold);
    font-weight: bold;
    font-size: var(--text-lg);
  }
  
  .lens-preview {
    background: var(--bg-secondary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    padding: var(--space-3);
  }
  
  .preview-header {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
    margin-bottom: var(--space-2);
  }
  
  .preview-header h3 {
    margin: 0;
    font-size: var(--text-base);
    color: var(--text-primary);
  }
  
  .version {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .preview-description {
    font-size: var(--text-sm);
    color: var(--text-secondary);
    margin: 0 0 var(--space-3) 0;
  }
  
  .preview-section h4 {
    font-size: var(--text-xs);
    font-weight: 600;
    color: var(--text-tertiary);
    text-transform: uppercase;
    margin: 0 0 var(--space-1) 0;
  }
  
  .heuristics-list {
    list-style: none;
    padding: 0;
    margin: 0;
    font-size: var(--text-sm);
  }
  
  .heuristics-list li {
    padding: var(--space-1) 0;
    border-bottom: 1px solid var(--border-subtle);
  }
  
  .heuristics-list li:last-child {
    border-bottom: none;
  }
  
  .heuristics-list li strong {
    color: var(--text-primary);
    display: block;
    font-size: var(--text-xs);
  }
  
  .heuristics-list li span {
    color: var(--text-secondary);
    font-size: var(--text-xs);
  }
  
  .heuristics-list .more {
    color: var(--text-tertiary);
    font-style: italic;
  }
  
  .actions {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: var(--space-3);
    border-top: 1px solid var(--border-default);
  }
  
  .action-buttons {
    display: flex;
    gap: var(--space-2);
  }
  
  .browse-library-link {
    background: none;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    font-size: var(--text-sm);
    padding: 0;
    font-family: inherit;
  }
  
  .browse-library-link:hover {
    color: var(--gold);
  }
  
  .loading-state,
  .error-state {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    padding: var(--space-6);
    color: var(--text-secondary);
  }
  
  .error-state {
    color: var(--error);
  }
</style>
