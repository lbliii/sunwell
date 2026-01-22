<!--
  KanbanBoard Primitive (RFC-072)
  
  Task board for planning work.
-->
<script lang="ts">
  import { untrack } from 'svelte';
  import type { PlanningPrimitiveProps } from './types';
  
  interface Props extends PlanningPrimitiveProps {}
  
  let { size, seed }: Props = $props();
  
  // Extract initial values (intentional one-time capture from seed prop)
  const initialTodo = untrack(() => seed?.todo as string[] ?? ['Task 1', 'Task 2']);
  const initialProgress = untrack(() => seed?.progress as string[] ?? []);
  const initialDone = untrack(() => seed?.done as string[] ?? []);
  
  // Sample columns - would be driven by data in real implementation
  let columns = $state([
    { id: 'todo', title: 'To Do', items: initialTodo },
    { id: 'progress', title: 'In Progress', items: initialProgress },
    { id: 'done', title: 'Done', items: initialDone },
  ]);
</script>

<div class="kanban" data-size={size}>
  <div class="kanban-header">
    <h2>Task Board</h2>
  </div>
  <div class="kanban-columns">
    {#each columns as column}
      <div class="kanban-column">
        <div class="column-header">
          <span class="column-title">{column.title}</span>
          <span class="column-count">{column.items.length}</span>
        </div>
        <div class="column-items">
          {#each column.items as item}
            <div class="kanban-card">
              {item}
            </div>
          {/each}
        </div>
      </div>
    {/each}
  </div>
</div>

<style>
  .kanban {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: var(--bg-primary);
    overflow: hidden;
  }
  
  .kanban-header {
    padding: var(--spacing-md);
    border-bottom: 1px solid var(--border-subtle);
  }
  
  .kanban-header h2 {
    font-size: 1.25rem;
    font-weight: 500;
    color: var(--text-primary);
    margin: 0;
  }
  
  .kanban-columns {
    display: flex;
    flex: 1;
    gap: var(--spacing-md);
    padding: var(--spacing-md);
    overflow-x: auto;
  }
  
  .kanban-column {
    flex: 1;
    min-width: 250px;
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    display: flex;
    flex-direction: column;
  }
  
  .column-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-sm) var(--spacing-md);
    border-bottom: 1px solid var(--border-subtle);
  }
  
  .column-title {
    font-weight: 500;
    color: var(--text-primary);
  }
  
  .column-count {
    font-size: 0.75rem;
    color: var(--text-secondary);
    background: var(--bg-tertiary);
    padding: 2px 8px;
    border-radius: 12px;
  }
  
  .column-items {
    flex: 1;
    padding: var(--spacing-sm);
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
  }
  
  .kanban-card {
    padding: var(--spacing-sm) var(--spacing-md);
    background: var(--bg-primary);
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-subtle);
    color: var(--text-primary);
    cursor: grab;
    transition: transform 0.1s, box-shadow 0.1s;
  }
  
  .kanban-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }
</style>
