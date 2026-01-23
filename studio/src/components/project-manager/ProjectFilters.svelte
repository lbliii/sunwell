<!--
  ProjectFilters — Filter bar with status, sort, and search (RFC-096)
-->
<script lang="ts">
  import {
    projectManager,
    setFilter,
    setSort,
    toggleSortDirection,
    setSearch,
    type ProjectFilter,
    type ProjectSort,
  } from '../../stores/projectManager.svelte';
  
  let searchValue = $state('');
  
  function handleSearchInput(e: Event) {
    const target = e.target as HTMLInputElement;
    searchValue = target.value;
    setSearch(target.value);
  }
  
  function handleFilterChange(e: Event) {
    const target = e.target as HTMLSelectElement;
    setFilter(target.value as ProjectFilter);
  }
  
  function handleSortChange(e: Event) {
    const target = e.target as HTMLSelectElement;
    setSort(target.value as ProjectSort);
  }
</script>

<div class="filters" role="search" aria-label="Project filters">
  <div class="filter-group">
    <select 
      class="filter-select"
      value={projectManager.filter}
      onchange={handleFilterChange}
      aria-label="Filter by status"
    >
      <option value="all">All</option>
      <option value="active">Active</option>
      <option value="interrupted">Interrupted</option>
      <option value="complete">Complete</option>
      <option value="failed">Failed</option>
    </select>
    
    <select 
      class="filter-select"
      value={projectManager.sort}
      onchange={handleSortChange}
      aria-label="Sort by"
    >
      <option value="recent">Recent</option>
      <option value="name">Name</option>
      <option value="status">Status</option>
      <option value="progress">Progress</option>
    </select>
    
    <button 
      class="sort-direction"
      onclick={toggleSortDirection}
      aria-label="Toggle sort direction"
      title={projectManager.sortDirection === 'asc' ? 'Ascending' : 'Descending'}
    >
      {projectManager.sortDirection === 'asc' ? '↑' : '↓'}
    </button>
  </div>
  
  <div class="search-wrapper">
    <span class="search-icon" aria-hidden="true">🔍</span>
    <input
      type="search"
      class="search-input"
      placeholder="Search projects..."
      value={searchValue}
      oninput={handleSearchInput}
      aria-label="Search projects"
    />
  </div>
</div>

<style>
  .filters {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3, 12px);
    flex-wrap: wrap;
  }
  
  .filter-group {
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
  }
  
  .filter-select {
    padding: var(--space-1, 4px) var(--space-2, 8px);
    background: var(--bg-secondary, #1e1e1e);
    border: 1px solid var(--border-subtle, #333);
    border-radius: var(--radius-sm, 4px);
    color: var(--text-secondary, #999);
    font-size: var(--text-xs, 12px);
    cursor: pointer;
    transition: all 0.15s ease;
  }
  
  .filter-select:hover {
    border-color: var(--border-default, #444);
  }
  
  .filter-select:focus {
    outline: 2px solid var(--gold, #ffd700);
    outline-offset: 2px;
  }
  
  .sort-direction {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg-secondary, #1e1e1e);
    border: 1px solid var(--border-subtle, #333);
    border-radius: var(--radius-sm, 4px);
    color: var(--text-secondary, #999);
    font-size: var(--text-sm, 14px);
    cursor: pointer;
    transition: all 0.15s ease;
  }
  
  .sort-direction:hover {
    border-color: var(--border-default, #444);
    color: var(--text-primary, #fff);
  }
  
  .sort-direction:focus {
    outline: 2px solid var(--gold, #ffd700);
    outline-offset: 2px;
  }
  
  .search-wrapper {
    position: relative;
    flex: 1;
    min-width: 150px;
    max-width: 250px;
  }
  
  .search-icon {
    position: absolute;
    left: var(--space-2, 8px);
    top: 50%;
    transform: translateY(-50%);
    font-size: var(--text-xs, 12px);
    opacity: 0.5;
  }
  
  .search-input {
    width: 100%;
    padding: var(--space-1, 4px) var(--space-2, 8px);
    padding-left: calc(var(--space-2, 8px) + 20px);
    background: var(--bg-secondary, #1e1e1e);
    border: 1px solid var(--border-subtle, #333);
    border-radius: var(--radius-sm, 4px);
    color: var(--text-primary, #fff);
    font-size: var(--text-xs, 12px);
    transition: all 0.15s ease;
  }
  
  .search-input::placeholder {
    color: var(--text-tertiary, #666);
  }
  
  .search-input:hover {
    border-color: var(--border-default, #444);
  }
  
  .search-input:focus {
    outline: 2px solid var(--gold, #ffd700);
    outline-offset: 2px;
  }
</style>
