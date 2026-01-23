<!--
  LensSelector.svelte — Dropdown for quick lens switching (RFC-086)
  
  Shows available lenses with descriptions and allows quick switching.
-->
<script lang="ts">
  import { fly, fade } from 'svelte/transition';
  import { writerState, setLens, lens, loadLenses } from '../../stores';
  import { onMount } from 'svelte';

  interface Props {
    visible?: boolean;
    onClose?: () => void;
    onSelect?: (lensName: string) => void;
  }

  let { visible = false, onClose, onSelect }: Props = $props();

  interface LensOption {
    name: string;
    domain: string;
    description: string;
    icon: string;
  }

  // Common lenses
  const lensOptions: LensOption[] = [
    {
      name: 'tech-writer',
      domain: 'documentation',
      description: 'Technical documentation with Diataxis framework',
      icon: '📝',
    },
    {
      name: 'coder',
      domain: 'software',
      description: 'Code-focused writing with code examples',
      icon: '💻',
    },
    {
      name: 'novelist',
      domain: 'creative',
      description: 'Long-form creative writing',
      icon: '📖',
    },
    {
      name: 'academic',
      domain: 'research',
      description: 'Academic papers and citations',
      icon: '🎓',
    },
    {
      name: 'marketer',
      domain: 'marketing',
      description: 'Marketing copy and campaigns',
      icon: '📣',
    },
    {
      name: 'api-docs',
      domain: 'documentation',
      description: 'API reference documentation',
      icon: '🔌',
    },
  ];

  let searchQuery = $state('');
  let selectedIndex = $state(0);

  const filteredLenses = $derived(
    lensOptions.filter(
      (l) =>
        l.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        l.domain.toLowerCase().includes(searchQuery.toLowerCase()) ||
        l.description.toLowerCase().includes(searchQuery.toLowerCase()),
    ),
  );

  const currentLens = $derived(writerState.lensName);

  function handleSelect(lensName: string) {
    if (onSelect) {
      onSelect(lensName);
    } else {
      setLens(lensName);
    }
    onClose?.();
  }

  function handleKeydown(e: KeyboardEvent) {
    if (!visible) return;

    switch (e.key) {
      case 'Escape':
        e.preventDefault();
        onClose?.();
        break;
      case 'ArrowDown':
        e.preventDefault();
        selectedIndex = Math.min(selectedIndex + 1, filteredLenses.length - 1);
        break;
      case 'ArrowUp':
        e.preventDefault();
        selectedIndex = Math.max(selectedIndex - 1, 0);
        break;
      case 'Enter':
        e.preventDefault();
        if (filteredLenses[selectedIndex]) {
          handleSelect(filteredLenses[selectedIndex].name);
        }
        break;
    }
  }

  function handleClickOutside(e: MouseEvent) {
    const target = e.target as HTMLElement;
    if (!target.closest('.lens-selector')) {
      onClose?.();
    }
  }

  // Reset selection when search changes
  $effect(() => {
    searchQuery;
    selectedIndex = 0;
  });
</script>

<svelte:window onkeydown={handleKeydown} onclick={handleClickOutside} />

{#if visible}
  <div class="lens-selector-overlay" transition:fade={{ duration: 100 }}>
    <div
      class="lens-selector"
      transition:fly={{ y: -10, duration: 150 }}
      role="dialog"
      aria-label="Select lens"
    >
      <div class="header">
        <span class="title">🔮 Select Lens</span>
        <span class="current">Current: {currentLens}</span>
      </div>

      <div class="search-container">
        <!-- svelte-ignore a11y_autofocus -->
        <input
          type="text"
          class="search-input"
          placeholder="Search lenses..."
          bind:value={searchQuery}
          autofocus
        />
      </div>

      <div class="lens-list">
        {#each filteredLenses as lensOption, i (lensOption.name)}
          <button
            class="lens-item"
            class:selected={i === selectedIndex}
            class:active={lensOption.name === currentLens}
            onclick={() => handleSelect(lensOption.name)}
            onmouseenter={() => (selectedIndex = i)}
          >
            <span class="lens-icon">{lensOption.icon}</span>
            <div class="lens-info">
              <span class="lens-name">{lensOption.name}</span>
              <span class="lens-description">{lensOption.description}</span>
            </div>
            <span class="lens-domain">{lensOption.domain}</span>
            {#if lensOption.name === currentLens}
              <span class="active-indicator">✓</span>
            {/if}
          </button>
        {/each}

        {#if filteredLenses.length === 0}
          <div class="empty-state">
            <span>No lenses found</span>
          </div>
        {/if}
      </div>

      <div class="footer">
        <span class="hint">↑↓ Navigate</span>
        <span class="hint">↵ Select</span>
        <span class="hint">Esc Close</span>
      </div>
    </div>
  </div>
{/if}

<style>
  .lens-selector-overlay {
    position: fixed;
    inset: 0;
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding-top: 100px;
    background: rgba(0, 0, 0, 0.5);
    z-index: 1000;
  }

  .lens-selector {
    background: var(--bg-secondary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-lg);
    width: 400px;
    max-height: 500px;
    overflow: hidden;
    box-shadow: var(--shadow-lg);
    font-family: var(--font-mono);
  }

  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--border-subtle);
  }

  .title {
    font-weight: 600;
    font-size: var(--text-sm);
    color: var(--text-primary);
  }

  .current {
    font-size: var(--text-xs);
    color: var(--text-secondary);
  }

  .search-container {
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--border-subtle);
  }

  .search-input {
    width: 100%;
    padding: var(--space-2) var(--space-3);
    background: var(--bg-primary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    font-family: inherit;
    font-size: var(--text-sm);
    color: var(--text-primary);
    outline: none;
    transition: border-color var(--transition-fast);
  }

  .search-input:focus {
    border-color: var(--ui-gold);
  }

  .search-input::placeholder {
    color: var(--text-tertiary);
  }

  .lens-list {
    max-height: 300px;
    overflow-y: auto;
  }

  .lens-item {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    width: 100%;
    padding: var(--space-2) var(--space-4);
    background: transparent;
    border: none;
    cursor: pointer;
    text-align: left;
    font-family: inherit;
    color: var(--text-primary);
    transition: background var(--transition-fast);
  }

  .lens-item:hover,
  .lens-item.selected {
    background: var(--bg-tertiary);
  }

  .lens-item.active {
    background: var(--accent-hover);
  }

  .lens-icon {
    font-size: var(--text-xl);
    flex-shrink: 0;
  }

  .lens-info {
    flex: 1;
    min-width: 0;
  }

  .lens-name {
    display: block;
    font-weight: 500;
    font-size: var(--text-sm);
  }

  .lens-description {
    display: block;
    font-size: var(--text-xs);
    color: var(--text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .lens-domain {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    background: var(--bg-primary);
    padding: var(--space-px) var(--space-1);
    border-radius: var(--radius-sm);
    flex-shrink: 0;
  }

  .active-indicator {
    color: var(--text-gold);
    font-weight: bold;
    flex-shrink: 0;
  }

  .empty-state {
    padding: var(--space-6);
    text-align: center;
    color: var(--text-secondary);
    font-size: var(--text-sm);
  }

  .footer {
    display: flex;
    gap: var(--space-4);
    padding: var(--space-2) var(--space-4);
    border-top: 1px solid var(--border-subtle);
    background: var(--bg-primary);
  }

  .hint {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
</style>
