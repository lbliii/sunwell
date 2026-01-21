<!--
  SavedPrompts — List of saved prompts for reuse (Svelte 5)
  
  Shows recently used prompts that can be clicked to reuse.
-->
<script lang="ts">
  import type { SavedPrompt } from '$lib/types';
  
  interface Props {
    prompts?: SavedPrompt[];
    loading?: boolean;
    onselect?: (text: string) => void;
    onremove?: (text: string) => void;
  }
  
  let { 
    prompts = [], 
    loading = false,
    onselect,
    onremove,
  }: Props = $props();
  
  // Track which prompt's menu is open
  let openMenuId = $state<string | null>(null);
  
  function formatTime(timestamp: number): string {
    const date = new Date(timestamp * 1000);
    const now = Date.now();
    const diff = now - date.getTime();
    
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    
    return date.toLocaleDateString();
  }
  
  function handleSelect(prompt: SavedPrompt) {
    if (openMenuId) {
      openMenuId = null;
      return;
    }
    onselect?.(prompt.text);
  }
  
  function toggleMenu(event: Event, promptText: string) {
    event.stopPropagation();
    openMenuId = openMenuId === promptText ? null : promptText;
  }
  
  function handleRemove(event: Event, prompt: SavedPrompt) {
    event.stopPropagation();
    openMenuId = null;
    onremove?.(prompt.text);
  }
  
  function handleKeydown(e: KeyboardEvent, prompt: SavedPrompt) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleSelect(prompt);
    }
  }
  
  function handleMenuKeydown(e: KeyboardEvent, promptText: string) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      toggleMenu(e, promptText);
    }
  }
  
  // Close menu when clicking outside
  function handleWindowClick(event: MouseEvent) {
    const target = event.target as HTMLElement;
    if (!target.closest('.action-menu') && !target.closest('.menu-trigger')) {
      openMenuId = null;
    }
  }
</script>

<svelte:window onclick={handleWindowClick} />

<div class="prompts-section">
  <div class="section-header">
    <h3 class="section-title">Saved Prompts</h3>
  </div>
  
  {#if loading}
    <div class="loading" role="status" aria-live="polite">Loading prompts...</div>
  {:else if prompts.length === 0}
    <div class="empty">
      <p>No saved prompts yet</p>
      <p class="hint">Prompts you use will be saved here</p>
    </div>
  {:else}
    <div class="prompt-list" role="list">
      {#each prompts as prompt (prompt.text)}
        <div 
          class="prompt-item"
          class:menu-open={openMenuId === prompt.text}
          role="listitem"
        >
          <button 
            class="prompt-button"
            onclick={() => handleSelect(prompt)}
            onkeydown={(e) => handleKeydown(e, prompt)}
            aria-label="Use prompt: {prompt.text}"
          >
            <span class="prompt-text" title={prompt.text}>
              {prompt.text}
            </span>
            <span class="prompt-time">{formatTime(prompt.last_used)}</span>
          </button>
          
          <!-- Action buttons -->
          <div class="prompt-actions">
            <button
              class="action-button menu-trigger"
              onclick={(e) => toggleMenu(e, prompt.text)}
              onkeydown={(e) => handleMenuKeydown(e, prompt.text)}
              title="Remove prompt"
              aria-label="Remove this prompt"
              aria-expanded={openMenuId === prompt.text}
              aria-haspopup="menu"
            >
              ✕
            </button>
            
            <!-- Dropdown menu -->
            {#if openMenuId === prompt.text}
              <div class="action-menu" role="menu">
                <button 
                  class="menu-item remove"
                  onclick={(e) => handleRemove(e, prompt)}
                  title="Remove from saved prompts"
                  role="menuitem"
                >
                  <span class="menu-icon" aria-hidden="true">✕</span>
                  <span class="menu-label">Remove</span>
                </button>
              </div>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .prompts-section {
    width: 100%;
    max-width: 700px;
  }
  
  .section-header {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
  }
  
  .section-title {
    color: var(--text-primary);
    font-size: var(--text-base);
    font-weight: 500;
    margin: 0;
  }
  
  .loading, .empty {
    color: var(--text-tertiary);
    font-size: var(--text-sm);
    text-align: center;
    padding: var(--space-6) var(--space-4);
  }
  
  .empty .hint {
    margin-top: var(--space-2);
    font-size: var(--text-xs);
  }
  
  .prompt-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  
  .prompt-item {
    position: relative;
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    transition: all var(--transition-fast);
  }
  
  .prompt-item:hover {
    background: var(--bg-tertiary);
    border-color: var(--border-default);
  }
  
  .prompt-item.menu-open {
    z-index: 50;
  }
  
  .prompt-button {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    width: 100%;
    padding: var(--space-3);
    background: transparent;
    border: none;
    color: var(--text-secondary);
    text-align: left;
    cursor: pointer;
    transition: color var(--transition-fast);
  }
  
  .prompt-item:hover .prompt-button {
    color: var(--text-primary);
  }
  
  .prompt-text {
    flex: 1;
    font-size: var(--text-sm);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .prompt-time {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    white-space: nowrap;
  }
  
  /* Action buttons container */
  .prompt-actions {
    position: absolute;
    right: var(--space-3);
    top: 50%;
    transform: translateY(-50%);
    display: flex;
    align-items: center;
    gap: var(--space-2);
    opacity: 0;
    transition: opacity var(--transition-fast);
  }
  
  .prompt-item:hover .prompt-actions,
  .prompt-item:focus-within .prompt-actions {
    opacity: 1;
  }
  
  .action-button {
    background: var(--bg-tertiary);
    color: var(--text-secondary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-sm);
    padding: var(--space-1) var(--space-2);
    font-size: var(--text-xs);
    cursor: pointer;
    transition: all var(--transition-fast);
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
  }
  
  .action-button:hover,
  .action-button:focus {
    background: var(--bg-secondary);
    border-color: var(--text-tertiary);
    color: var(--text-primary);
  }
  
  .action-button:focus {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
  
  .menu-trigger {
    font-size: var(--text-sm);
  }
  
  /* Dropdown menu */
  .action-menu {
    position: absolute;
    top: calc(100% + var(--space-1));
    right: 0;
    display: flex;
    align-items: center;
    gap: 1px;
    background: var(--border-subtle);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
    z-index: 100;
    overflow: hidden;
    animation: menuSlide 0.12s ease;
  }
  
  @keyframes menuSlide {
    from {
      opacity: 0;
      transform: translateY(-2px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
  
  .menu-item {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-2) var(--space-3);
    background: var(--bg-primary);
    border: none;
    color: var(--text-tertiary);
    font-size: var(--text-xs);
    cursor: pointer;
    transition: all var(--transition-fast);
    white-space: nowrap;
  }
  
  .menu-item:hover,
  .menu-item:focus {
    color: var(--text-primary);
  }
  
  .menu-item:focus {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
  }
  
  .menu-item .menu-icon {
    font-size: var(--text-sm);
  }
  
  .menu-item .menu-label {
    font-weight: 500;
  }
  
  .menu-item.remove:hover,
  .menu-item.remove:focus {
    background: rgba(var(--error-rgb), 0.1);
    color: var(--error);
  }
</style>
