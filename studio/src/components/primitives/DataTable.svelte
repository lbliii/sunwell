<!--
  DataTable Primitive (RFC-072, RFC-078)
  
  Spreadsheet view for data with sorting, filtering, and inline editing.
-->
<script lang="ts">
  import type { DataPrimitiveProps } from './types';
  
  interface Props extends DataPrimitiveProps {
    onEdit?: (row: number, column: string, newValue: unknown) => void;
    editable?: boolean;
  }
  
  let { 
    size, 
    data = [], 
    columns = [],
    onEdit,
    editable = false,
  }: Props = $props();
  
  type ColumnType = 'text' | 'number' | 'date' | 'boolean';

  // Infer columns from first row if not provided
  let inferredColumns = $derived.by(() => {
    if (columns && columns.length > 0) return columns;
    if (data && data.length > 0) {
      const first = data[0] as Record<string, unknown>;
      return Object.keys(first);
    }
    return [];
  });

  // Precompute column types once (O(m) instead of O(n*m) in template)
  const columnTypes = $derived.by(() => {
    const types: Record<string, ColumnType> = {};
    if (!data || data.length === 0) {
      for (const col of inferredColumns) {
        types[col] = 'text';
      }
      return types;
    }
    const first = data[0] as Record<string, unknown>;
    for (const col of inferredColumns) {
      const value = first[col];
      if (typeof value === 'number') {
        types[col] = 'number';
      } else if (typeof value === 'boolean') {
        types[col] = 'boolean';
      } else if (value instanceof Date) {
        types[col] = 'date';
      } else if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}/.test(value)) {
        types[col] = 'date';
      } else {
        types[col] = 'text';
      }
    }
    return types;
  });

  // Sort state
  let sortColumn: string | null = $state(null);
  let sortDirection: 'asc' | 'desc' = $state('asc');
  
  // Filter state (per-column)
  let filters: Record<string, string> = $state({});
  let showFilters = $state(false);
  
  // Editing state
  let editingCell: { row: number; column: string } | null = $state(null);
  let editValue: string = $state('');
  
  // Filtered and sorted data
  let processedData = $derived.by(() => {
    if (!data || data.length === 0) return [];
    
    let result = [...data] as Record<string, unknown>[];
    
    // Apply filters
    for (const [col, filterValue] of Object.entries(filters)) {
      if (filterValue) {
        const lowerFilter = filterValue.toLowerCase();
        result = result.filter(row => {
          const cellValue = String(row[col] ?? '').toLowerCase();
          return cellValue.includes(lowerFilter);
        });
      }
    }
    
    // Apply sort
    if (sortColumn) {
      result.sort((a, b) => {
        const aVal = a[sortColumn!];
        const bVal = b[sortColumn!];
        
        // Handle nulls
        if (aVal == null && bVal == null) return 0;
        if (aVal == null) return sortDirection === 'asc' ? 1 : -1;
        if (bVal == null) return sortDirection === 'asc' ? -1 : 1;
        
        // Compare
        if (typeof aVal === 'number' && typeof bVal === 'number') {
          return sortDirection === 'asc' ? aVal - bVal : bVal - aVal;
        }
        
        const aStr = String(aVal);
        const bStr = String(bVal);
        return sortDirection === 'asc' 
          ? aStr.localeCompare(bStr) 
          : bStr.localeCompare(aStr);
      });
    }
    
    return result;
  });
  
  function handleSort(column: string) {
    if (sortColumn === column) {
      sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      sortColumn = column;
      sortDirection = 'asc';
    }
  }
  
  function handleFilterChange(column: string, value: string) {
    filters = { ...filters, [column]: value };
  }
  
  function startEdit(rowIndex: number, column: string) {
    if (!editable) return;
    editingCell = { row: rowIndex, column };
    const row = processedData[rowIndex] as Record<string, unknown>;
    editValue = String(row[column] ?? '');
  }
  
  function commitEdit() {
    if (!editingCell || !onEdit) return;
    onEdit(editingCell.row, editingCell.column, editValue);
    editingCell = null;
    editValue = '';
  }
  
  function cancelEdit() {
    editingCell = null;
    editValue = '';
  }
  
  function formatCellValue(value: unknown): string {
    if (value == null) return '';
    if (typeof value === 'boolean') return value ? '✓' : '✗';
    if (value instanceof Date) return value.toLocaleDateString();
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  }

  function exportToCsv() {
    const cols = inferredColumns;
    const header = cols.join(',');
    const rows = processedData.map(row => 
      cols.map(col => {
        const value = (row as Record<string, unknown>)[col];
        const str = formatCellValue(value);
        // Escape quotes and wrap in quotes if contains comma
        if (str.includes(',') || str.includes('"')) {
          return `"${str.replace(/"/g, '""')}"`;
        }
        return str;
      }).join(',')
    );
    const csv = [header, ...rows].join('\n');
    
    // Download
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'data.csv';
    a.click();
    URL.revokeObjectURL(url);
  }
</script>

<div class="data-table" data-size={size}>
  <div class="table-header">
    <span>📊 Data Table</span>
    <div class="table-actions">
      <button class="icon-btn" onclick={() => showFilters = !showFilters} title="Toggle filters">
        🔍
      </button>
      <button class="icon-btn" onclick={exportToCsv} title="Export CSV">
        📥
      </button>
      <span class="row-count">{processedData.length} rows</span>
    </div>
  </div>
  
  <div class="table-content">
    {#if !data || data.length === 0}
      <p class="placeholder">No data loaded</p>
    {:else}
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              {#each inferredColumns as column (column)}
                <th 
                  class:sorted={sortColumn === column}
                  onclick={() => handleSort(column)}
                >
                  <span class="column-name">{column}</span>
                  {#if sortColumn === column}
                    <span class="sort-indicator">{sortDirection === 'asc' ? '↑' : '↓'}</span>
                  {/if}
                </th>
              {/each}
            </tr>
            {#if showFilters}
              <tr class="filter-row">
                {#each inferredColumns as column (`filter-${column}`)}
                  <th>
                    <input 
                      type="text"
                      class="filter-input"
                      placeholder="Filter..."
                      value={filters[column] ?? ''}
                      oninput={(e) => handleFilterChange(column, (e.target as HTMLInputElement).value)}
                    />
                  </th>
                {/each}
              </tr>
            {/if}
          </thead>
          <tbody>
            {#each processedData as row, rowIndex (rowIndex)}
              <tr>
                {#each inferredColumns as column (`${rowIndex}-${column}`)}
                  <td 
                    class={columnTypes[column]}
                    class:editable
                    ondblclick={() => startEdit(rowIndex, column)}
                  >
                    {#if editingCell?.row === rowIndex && editingCell?.column === column}
                      <input
                        type="text"
                        class="edit-input"
                        bind:value={editValue}
                        onblur={commitEdit}
                        onkeydown={(e) => {
                          if (e.key === 'Enter') commitEdit();
                          if (e.key === 'Escape') cancelEdit();
                        }}
                      />
                    {:else}
                      {formatCellValue((row as Record<string, unknown>)[column])}
                    {/if}
                  </td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>
</div>

<style>
  .data-table {
    height: 100%;
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    display: flex;
    flex-direction: column;
  }
  
  .table-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-sm) var(--spacing-md);
    border-bottom: 1px solid var(--border-subtle);
    color: var(--text-primary);
  }
  
  .table-actions {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
  }
  
  .icon-btn {
    background: none;
    border: none;
    cursor: pointer;
    padding: 4px 8px;
    border-radius: var(--radius-sm);
    font-size: 0.875rem;
  }
  
  .icon-btn:hover {
    background: var(--bg-tertiary);
  }
  
  .row-count {
    font-size: 0.75rem;
    color: var(--text-secondary);
    margin-left: var(--spacing-sm);
  }
  
  .table-content {
    flex: 1;
    overflow: hidden;
  }
  
  .table-scroll {
    height: 100%;
    overflow: auto;
  }
  
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
  }
  
  th, td {
    padding: var(--spacing-xs) var(--spacing-sm);
    text-align: left;
    border-bottom: 1px solid var(--border-subtle);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 200px;
  }
  
  th {
    position: sticky;
    top: 0;
    background: var(--bg-tertiary);
    cursor: pointer;
    user-select: none;
    font-weight: 600;
  }
  
  th:hover {
    background: var(--bg-hover);
  }
  
  th.sorted {
    color: var(--accent-primary);
  }
  
  .column-name {
    display: inline-block;
  }
  
  .sort-indicator {
    margin-left: 4px;
    font-size: 0.75rem;
  }
  
  .filter-row th {
    padding: 4px;
    cursor: default;
  }
  
  .filter-row th:hover {
    background: var(--bg-tertiary);
  }
  
  .filter-input {
    width: 100%;
    padding: 4px 8px;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    background: var(--bg-primary);
    color: var(--text-primary);
    font-size: 0.75rem;
  }
  
  .filter-input:focus {
    outline: none;
    border-color: var(--accent-primary);
  }
  
  tbody tr:hover {
    background: var(--bg-hover);
  }
  
  td.number {
    text-align: right;
    font-family: var(--font-mono);
  }
  
  td.boolean {
    text-align: center;
  }
  
  td.date {
    font-family: var(--font-mono);
    font-size: 0.8125rem;
  }
  
  td.editable {
    cursor: pointer;
  }
  
  td.editable:hover {
    background: var(--bg-tertiary);
  }
  
  .edit-input {
    width: 100%;
    padding: 2px 4px;
    border: 1px solid var(--accent-primary);
    border-radius: var(--radius-sm);
    background: var(--bg-primary);
    color: var(--text-primary);
    font-size: inherit;
    font-family: inherit;
  }
  
  .edit-input:focus {
    outline: none;
  }
  
  .placeholder {
    color: var(--text-tertiary);
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
  }
</style>
