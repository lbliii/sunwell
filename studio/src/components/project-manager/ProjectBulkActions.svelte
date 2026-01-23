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
    gap: var(--space-3, 12px);
    padding: var(--space-2, 8px) var(--space-3, 12px);
    background: rgba(255, 215, 0, 0.1);
    border: 1px solid rgba(255, 215, 0, 0.2);
    border-radius: var(--radius-md, 8px);
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
    font-size: var(--text-xs, 12px);
    color: var(--text-gold, #ffd700);
    font-weight: 500;
  }
  
  .actions {
    display: flex;
    align-items: center;
    gap: var(--space-1, 4px);
  }
  
  .action-btn {
    padding: var(--space-1, 4px) var(--space-2, 8px);
    background: var(--bg-secondary, #1e1e1e);
    border: 1px solid var(--border-subtle, #333);
    border-radius: var(--radius-sm, 4px);
    color: var(--text-secondary, #999);
    font-size: var(--text-xs, 12px);
    cursor: pointer;
    transition: all 0.15s ease;
  }
  
  .action-btn:hover {
    background: var(--bg-tertiary, #2a2a2a);
    color: var(--text-primary, #fff);
  }
  
  .action-btn:focus {
    outline: 2px solid var(--gold, #ffd700);
    outline-offset: 2px;
  }
  
  .action-btn.archive:hover {
    border-color: var(--warning, #f59e0b);
    color: var(--warning, #f59e0b);
  }
  
  .action-btn.delete:hover {
    border-color: var(--error, #ef4444);
    color: var(--error, #ef4444);
  }
  
  .action-btn.clear {
    padding: var(--space-1, 4px);
    min-width: 24px;
  }
</style>
