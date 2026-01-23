<!--
  ProjectBulkActions — Bulk action toolbar (RFC-096)
-->
<script lang="ts">
  interface Props {
    count: number;
    onArchive?: () => void;
    onDelete?: () => void;
    onClear?: () => void;
  }
  
  let { count, onArchive, onDelete, onClear }: Props = $props();
</script>

<div class="bulk-actions" role="toolbar" aria-label="Bulk actions">
  <span class="selection-count">{count} selected</span>
  
  <div class="actions">
    <button 
      class="action-btn archive"
      onclick={onArchive}
      aria-label="Archive selected projects"
    >
      Archive
    </button>
    
    <button 
      class="action-btn delete"
      onclick={onDelete}
      aria-label="Delete selected projects"
    >
      Delete
    </button>
    
    <button 
      class="action-btn clear"
      onclick={onClear}
      aria-label="Clear selection"
    >
      ✕
    </button>
  </div>
</div>

<style>
  .bulk-actions {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-2) var(--space-3);
    background: var(--radiant-gold-10);
    border: 1px solid var(--radiant-gold-20);
    border-radius: var(--radius-md);
    animation: slideIn 0.15s ease;
  }
  
  @keyframes slideIn {
    from {
      opacity: 0;
      transform: translateY(-4px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
  
  .selection-count {
    font-size: var(--text-xs);
    color: var(--text-gold);
    font-weight: 500;
  }
  
  .actions {
    display: flex;
    align-items: center;
    gap: var(--space-1);
  }
  
  .action-btn {
    padding: var(--space-1) var(--space-2);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-size: var(--text-xs);
    cursor: pointer;
    transition: all 0.15s ease;
  }
  
  .action-btn:hover {
    background: var(--bg-tertiary);
    color: var(--text-primary);
  }
  
  .action-btn:focus {
    outline: 2px solid var(--gold);
    outline-offset: 2px;
  }
  
  .action-btn.archive:hover {
    border-color: var(--warning);
    color: var(--warning);
  }
  
  .action-btn.delete:hover {
    border-color: var(--error);
    color: var(--error);
  }
  
  .action-btn.clear {
    padding: var(--space-1);
    min-width: 24px;
  }
</style>
