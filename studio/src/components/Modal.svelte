<!--
  Modal — Accessible dialog component (Svelte 5)
  
  Implements WAI-ARIA dialog pattern with:
  - Focus trap
  - Escape to close
  - Click outside to close
  - aria-modal and aria-labelledby
-->
<script lang="ts">
  import type { Snippet } from 'svelte';
  import { trapFocus, uniqueId } from '$lib/a11y';
  
  interface Props {
    isOpen: boolean;
    title: string;
    description?: string;
    onClose: () => void;
    children: Snippet;
    footer?: Snippet;
  }
  
  let { isOpen, title, description, onClose, children, footer }: Props = $props();
  
  let dialogEl: HTMLDivElement | undefined = $state();
  let previousActiveElement: HTMLElement | null = null;
  let cleanupFocusTrap: (() => void) | null = null;
  
  const modalId = uniqueId('modal');
  const titleId = `${modalId}-title`;
  
  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
    }
  }
  
  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget) {
      onClose();
    }
  }
  
  $effect(() => {
    if (isOpen && dialogEl) {
      // Store current focus
      previousActiveElement = document.activeElement as HTMLElement;
      
      // Trap focus
      cleanupFocusTrap = trapFocus(dialogEl);
      
      // Prevent body scroll
      document.body.style.overflow = 'hidden';
      
      return () => {
        cleanupFocusTrap?.();
        document.body.style.overflow = '';
        previousActiveElement?.focus();
      };
    }
  });
</script>

{#if isOpen}
  <div 
    class="modal-backdrop" 
    onclick={handleBackdropClick}
    onkeydown={handleKeydown}
    role="presentation"
  >
    <div
      bind:this={dialogEl}
      class="modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      tabindex="-1"
    >
      <header class="modal-header">
        <h2 id={titleId} class="modal-title">{title}</h2>
        <button 
          class="modal-close" 
          onclick={onClose}
          aria-label="Close dialog"
          type="button"
        >
          ✕
        </button>
      </header>
      
      {#if description}
        <p class="modal-description">{description}</p>
      {/if}
      
      <div class="modal-content">
        {@render children()}
      </div>
      
      {#if footer}
        <footer class="modal-footer">
          {@render footer()}
        </footer>
      {/if}
    </div>
  </div>
{/if}

<style>
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--space-6);
    z-index: 100;
    backdrop-filter: blur(4px);
    animation: fadeIn 0.15s ease-out;
  }
  
  .modal {
    background: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    width: 100%;
    max-width: 500px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
    animation: slideUp 0.2s ease-out;
  }
  
  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-4);
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border-color);
  }
  
  .modal-title {
    font-size: var(--text-lg);
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
  }
  
  .modal-close {
    background: transparent;
    border: none;
    color: var(--text-tertiary);
    font-size: var(--text-lg);
    cursor: pointer;
    padding: var(--space-1);
    line-height: 1;
    transition: color var(--transition-fast);
  }
  
  .modal-close:hover {
    color: var(--text-primary);
  }
  
  .modal-close:focus-visible {
    outline: 2px solid var(--border-emphasis);
    outline-offset: 2px;
  }
  
  .modal-description {
    padding: 0 var(--space-4);
    margin: 0;
    color: var(--text-secondary);
    font-size: var(--text-sm);
    line-height: var(--leading-relaxed);
  }
  
  .modal-content {
    flex: 1;
    overflow-y: auto;
    padding: var(--space-4);
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  
  .modal-footer {
    display: flex;
    gap: var(--space-3);
    justify-content: flex-end;
    padding: var(--space-4);
    background: var(--bg-secondary);
    border-top: 1px solid var(--border-color);
  }
  
  /* Support for modal-actions pattern in children slot */
  .modal-content :global(.modal-actions) {
    display: flex;
    gap: var(--space-3);
    justify-content: flex-end;
    margin-top: var(--space-4);
  }
  
  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  
  @keyframes slideUp {
    from {
      opacity: 0;
      transform: translateY(20px) scale(0.95);
    }
    to {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }
</style>
