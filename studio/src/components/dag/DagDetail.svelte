<!--
  DagDetail — Expanded detail panel for selected node
-->
<script lang="ts">
  import { selectedNode, selectNode, completeNode, layoutedGraph } from '../../stores/dag';
  import Button from '../Button.svelte';
  
  $: node = $selectedNode;
  $: dependencyNodes = node 
    ? $layoutedGraph.nodes.filter(n => node.dependsOn.includes(n.id))
    : [];
  $: dependentNodes = node
    ? $layoutedGraph.nodes.filter(n => n.dependsOn.includes(node.id))
    : [];
  
  function handleClose() {
    selectNode(null);
  }
  
  function handleExecute() {
    if (!node) return;
    // TODO: Wire to actual execution
    console.log('Execute:', node.id);
  }
  
  function handleMarkComplete() {
    if (!node) return;
    completeNode(node.id);
  }
  
  function formatProgress(progress: number): string {
    const filled = Math.round(progress / 5);
    const empty = 20 - filled;
    return '█'.repeat(filled) + '░'.repeat(empty);
  }
</script>

{#if node}
  <div class="dag-detail">
    <!-- Header -->
    <header class="detail-header">
      <div class="header-left">
        <span class="source-badge" class:ai={node.source === 'ai'} class:human={node.source === 'human'}>
          {node.source === 'ai' ? '🤖 AI' : node.source === 'human' ? '👤 Human' : '🔗 External'}
        </span>
        <h2 class="detail-title">{node.title}</h2>
      </div>
      <button class="close-btn" on:click={handleClose}>✕</button>
    </header>
    
    <!-- Status bar -->
    <div class="status-bar status-{node.status}">
      {#if node.status === 'running'}
        <div class="progress-section">
          <span class="progress-bar">{formatProgress(node.progress)}</span>
          <span class="progress-value">{node.progress}%</span>
        </div>
        {#if node.currentAction}
          <p class="current-action">{node.currentAction}</p>
        {/if}
      {:else if node.status === 'complete'}
        <span class="status-text">✓ Complete</span>
      {:else if node.status === 'ready'}
        <span class="status-text">▸ Ready to execute</span>
      {:else if node.status === 'blocked'}
        <span class="status-text">⏸ Waiting on dependencies</span>
      {:else if node.status === 'failed'}
        <span class="status-text">✗ Failed</span>
      {:else}
        <span class="status-text">○ Pending</span>
      {/if}
    </div>
    
    <!-- Description -->
    <section class="detail-section">
      <p class="description">{node.description}</p>
    </section>
    
    <!-- Metadata -->
    <section class="detail-section">
      <div class="meta-grid">
        <div class="meta-item">
          <span class="meta-label">Priority</span>
          <span class="meta-value priority">
            {'█'.repeat(Math.round(node.priority * 5))}{'░'.repeat(5 - Math.round(node.priority * 5))}
          </span>
        </div>
        <div class="meta-item">
          <span class="meta-label">Effort</span>
          <span class="meta-value">{node.effort}</span>
        </div>
        {#if node.category}
          <div class="meta-item">
            <span class="meta-label">Category</span>
            <span class="meta-value">{node.category}</span>
          </div>
        {/if}
      </div>
    </section>
    
    <!-- Dependencies -->
    {#if dependencyNodes.length > 0}
      <section class="detail-section">
        <h3 class="section-title">Dependencies ({dependencyNodes.length})</h3>
        <ul class="node-list">
          {#each dependencyNodes as dep}
            <li class="node-list-item" class:complete={dep.status === 'complete'}>
              <span class="node-status-icon">
                {dep.status === 'complete' ? '✓' : dep.status === 'running' ? '◐' : '○'}
              </span>
              <span class="node-name">{dep.title}</span>
            </li>
          {/each}
        </ul>
      </section>
    {/if}
    
    <!-- Dependents (blocks) -->
    {#if dependentNodes.length > 0}
      <section class="detail-section">
        <h3 class="section-title">Blocks ({dependentNodes.length})</h3>
        <ul class="node-list">
          {#each dependentNodes as dep}
            <li class="node-list-item">
              <span class="node-status-icon">
                {dep.status === 'blocked' ? '⏸' : '○'}
              </span>
              <span class="node-name">{dep.title}</span>
            </li>
          {/each}
        </ul>
      </section>
    {/if}
    
    <!-- Actions -->
    <footer class="detail-actions">
      {#if node.status === 'ready' || node.status === 'pending'}
        <Button variant="primary" size="sm" icon="▶" on:click={handleExecute}>
          Execute
        </Button>
      {/if}
      {#if node.status !== 'complete' && node.status !== 'failed'}
        <Button variant="ghost" size="sm" on:click={handleMarkComplete}>
          Mark Complete
        </Button>
      {/if}
    </footer>
  </div>
{/if}

<style>
  .dag-detail {
    width: 320px;
    background: var(--bg-secondary);
    border-left: 1px solid var(--border-color);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  
  .detail-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    padding: 16px;
    border-bottom: 1px solid var(--border-color);
  }
  
  .header-left {
    display: flex;
    flex-direction: column;
    gap: 8px;
    flex: 1;
    min-width: 0;
  }
  
  .source-badge {
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 4px;
    background: var(--bg-tertiary);
    color: var(--text-secondary);
    width: fit-content;
  }
  
  .source-badge.ai { background: var(--info-muted); color: var(--info); }
  .source-badge.human { background: var(--warning-muted); color: var(--warning); }
  
  .detail-title {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
    word-wrap: break-word;
  }
  
  .close-btn {
    background: transparent;
    border: none;
    color: var(--text-tertiary);
    font-size: 18px;
    cursor: pointer;
    padding: 4px;
    line-height: 1;
  }
  
  .close-btn:hover {
    color: var(--text-primary);
  }
  
  .status-bar {
    padding: 12px 16px;
    border-bottom: 1px solid var(--border-color);
  }
  
  .status-bar.status-complete { background: var(--success-muted); }
  .status-bar.status-running { background: var(--info-muted); }
  .status-bar.status-ready { background: var(--warning-muted); }
  .status-bar.status-failed { background: var(--error-muted); }
  
  .progress-section {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  
  .progress-bar {
    font-size: 10px;
    letter-spacing: -1px;
    color: var(--info);
  }
  
  .progress-value {
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .current-action {
    font-size: 11px;
    color: var(--text-secondary);
    margin: 4px 0 0;
  }
  
  .status-text {
    font-size: 13px;
    font-weight: 500;
  }
  
  .status-complete .status-text { color: var(--success); }
  .status-running .status-text { color: var(--info); }
  .status-ready .status-text { color: var(--warning); }
  .status-failed .status-text { color: var(--error); }
  .status-blocked .status-text { color: var(--text-tertiary); }
  
  .detail-section {
    padding: 16px;
    border-bottom: 1px solid var(--border-color);
  }
  
  .description {
    font-size: 13px;
    color: var(--text-secondary);
    line-height: 1.5;
    margin: 0;
  }
  
  .section-title {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin: 0 0 8px;
  }
  
  .meta-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }
  
  .meta-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  
  .meta-label {
    font-size: 10px;
    color: var(--text-tertiary);
    text-transform: uppercase;
  }
  
  .meta-value {
    font-size: 12px;
    color: var(--text-primary);
  }
  
  .meta-value.priority {
    font-size: 10px;
    letter-spacing: -1px;
    color: var(--warning);
  }
  
  .node-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  
  .node-list-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--text-secondary);
  }
  
  .node-list-item.complete {
    color: var(--text-tertiary);
  }
  
  .node-status-icon {
    font-size: 10px;
  }
  
  .node-list-item.complete .node-status-icon {
    color: var(--success);
  }
  
  .detail-actions {
    padding: 16px;
    margin-top: auto;
    display: flex;
    gap: 8px;
  }
</style>
