<!--
  StateDagView — Visualization of project State DAG (RFC-100 Phase 0)
  
  Shows brownfield project health:
  - 🟢 Healthy (90-100%)
  - 🟡 Needs review (70-89%)
  - 🟠 Issues found (50-69%)
  - 🔴 Critical (< 50%)
  
  Click nodes to give intent and spawn Execution DAGs.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import DagCanvas from '../dag/DagCanvas.svelte';
  import { 
    coordinatorStore, 
    loadStateDag, 
    getStateDagNode,
    getConnectedNodes,
    type StateDagNode 
  } from '../../stores/coordinator.svelte';
  
  interface Props {
    projectPath: string;
    onNodeClick?: (node: StateDagNode) => void;
  }
  
  let { projectPath, onNodeClick }: Props = $props();
  
  let selectedNodeId = $state<string | null>(null);
  let hoveredNodeId = $state<string | null>(null);
  let showIntentDialog = $state(false);
  let intentInput = $state('');
  
  onMount(() => {
    loadStateDag(projectPath);
  });
  
  let selectedNode = $derived(
    selectedNodeId ? getStateDagNode(selectedNodeId) : null
  );
  
  let connections = $derived(
    selectedNodeId ? getConnectedNodes(selectedNodeId) : { parents: [], children: [] }
  );
  
  function healthToEmoji(score: number): string {
    const pct = score * 100;
    if (pct >= 90) return '🟢';
    if (pct >= 70) return '🟡';
    if (pct >= 50) return '🟠';
    return '🔴';
  }
  
  function healthToColor(score: number): string {
    const pct = score * 100;
    if (pct >= 90) return 'var(--success)';
    if (pct >= 70) return 'var(--warning)';
    if (pct >= 50) return 'var(--orange, #f97316)';
    return 'var(--error)';
  }
  
  function handleNodeClick(node: StateDagNode) {
    selectedNodeId = node.id;
    if (onNodeClick) {
      onNodeClick(node);
    }
  }
  
  function handleGiveIntent() {
    if (!selectedNode) return;
    showIntentDialog = true;
  }
  
  function handleIntentSubmit() {
    if (!selectedNode || !intentInput.trim()) return;
    
    // TODO: Spawn Execution DAG with intent
    console.log('Intent for', selectedNode.path, ':', intentInput);
    
    showIntentDialog = false;
    intentInput = '';
  }
  
  // Transform State DAG to DAG canvas format
  let dagNodes = $derived(
    coordinatorStore.stateDag?.nodes.map(node => ({
      id: node.id,
      title: node.title,
      description: node.path,
      status: node.health_score >= 0.7 ? 'complete' : 
              node.health_score >= 0.5 ? 'ready' : 'failed',
      source: 'ai' as const,
      progress: node.health_score * 100,
      priority: node.health_score,
      effort: 'small' as const,
      dependsOn: [],
      category: node.artifact_type,
    })) ?? []
  );
  
  let dagEdges = $derived(
    coordinatorStore.stateDag?.edges.map((edge, i) => ({
      id: `e-${i}`,
      source: edge.source,
      target: edge.target,
      artifact: edge.edge_type,
    })) ?? []
  );
</script>

<div class="state-dag-view">
  <header class="dag-header">
    <div class="header-left">
      <h1>📊 Project Health</h1>
      <span class="project-badge">{projectPath.split('/').pop()}</span>
    </div>
    
    <div class="header-right">
      {#if coordinatorStore.stateDag}
        <div class="health-indicator" style="color: {healthToColor(coordinatorStore.overallHealth)}">
          {healthToEmoji(coordinatorStore.overallHealth)}
          {Math.round(coordinatorStore.overallHealth * 100)}%
        </div>
        <span class="stats">
          {coordinatorStore.stateDag.node_count} nodes •
          {coordinatorStore.unhealthyNodes.length} need attention
        </span>
      {/if}
      
      <button class="refresh-btn" onclick={() => loadStateDag(projectPath)}>
        ↻ Refresh
      </button>
    </div>
  </header>
  
  {#if coordinatorStore.stateDagLoading}
    <div class="loading">
      <div class="spinner"></div>
      <p>Scanning project...</p>
    </div>
  {:else if coordinatorStore.stateDagError}
    <div class="error">
      <p>⚠️ {coordinatorStore.stateDagError}</p>
      <button onclick={() => loadStateDag(projectPath)}>Retry</button>
    </div>
  {:else if coordinatorStore.stateDag}
    <div class="dag-container">
      <!-- Summary Cards -->
      <div class="summary-cards">
        <div class="summary-card critical" class:has-items={coordinatorStore.criticalNodes.length > 0}>
          <span class="emoji">🔴</span>
          <span class="count">{coordinatorStore.criticalNodes.length}</span>
          <span class="label">Critical</span>
        </div>
        <div class="summary-card warning" class:has-items={coordinatorStore.unhealthyNodes.length - coordinatorStore.criticalNodes.length > 0}>
          <span class="emoji">🟡</span>
          <span class="count">{coordinatorStore.unhealthyNodes.length - coordinatorStore.criticalNodes.length}</span>
          <span class="label">Needs Review</span>
        </div>
        <div class="summary-card healthy">
          <span class="emoji">🟢</span>
          <span class="count">{coordinatorStore.stateDag.node_count - coordinatorStore.unhealthyNodes.length}</span>
          <span class="label">Healthy</span>
        </div>
      </div>
      
      <!-- Node List -->
      <div class="node-list">
        <h3>Files & Modules</h3>
        
        {#each coordinatorStore.stateDag.nodes.sort((a, b) => a.health_score - b.health_score) as node}
          <button 
            class="node-item"
            class:selected={selectedNodeId === node.id}
            class:critical={node.health_score < 0.5}
            class:warning={node.health_score >= 0.5 && node.health_score < 0.7}
            onclick={() => handleNodeClick(node)}
          >
            <span class="node-health">{healthToEmoji(node.health_score)}</span>
            <span class="node-title">{node.title}</span>
            <span class="node-score">{Math.round(node.health_score * 100)}%</span>
          </button>
        {/each}
      </div>
      
      <!-- Selected Node Detail -->
      {#if selectedNode}
        <aside class="node-detail">
          <div class="detail-header">
            <span class="health-badge" style="background: {healthToColor(selectedNode.health_score)}">
              {Math.round(selectedNode.health_score * 100)}%
            </span>
            <h3>{selectedNode.title}</h3>
          </div>
          
          <div class="detail-path">{selectedNode.path}</div>
          
          <div class="detail-meta">
            <span>Type: {selectedNode.artifact_type}</span>
            {#if selectedNode.line_count}
              <span>Lines: {selectedNode.line_count}</span>
            {/if}
            {#if selectedNode.last_modified}
              <span>Updated: {new Date(selectedNode.last_modified).toLocaleDateString()}</span>
            {/if}
          </div>
          
          {#if selectedNode.health_probes.length > 0}
            <div class="probes">
              <h4>Health Probes</h4>
              {#each selectedNode.health_probes as probe}
                <div class="probe" class:failing={probe.score < 0.7}>
                  <span class="probe-icon">{probe.score >= 0.7 ? '✓' : '✗'}</span>
                  <span class="probe-name">{probe.probe_name.replace('_', ' ')}</span>
                  <span class="probe-score">{Math.round(probe.score * 100)}%</span>
                </div>
                {#if probe.issues.length > 0}
                  <ul class="probe-issues">
                    {#each probe.issues.slice(0, 3) as issue}
                      <li>{issue}</li>
                    {/each}
                  </ul>
                {/if}
              {/each}
            </div>
          {/if}
          
          <div class="detail-actions">
            <button class="intent-btn" onclick={handleGiveIntent}>
              ✨ Give Intent
            </button>
            <button class="open-btn" onclick={() => console.log('Open in editor:', selectedNode?.path)}>
              📄 Open File
            </button>
          </div>
        </aside>
      {/if}
    </div>
  {:else}
    <div class="empty-state">
      <p>No State DAG loaded.</p>
      <button onclick={() => loadStateDag(projectPath)}>Scan Project</button>
    </div>
  {/if}
  
  <!-- Intent Dialog -->
  {#if showIntentDialog && selectedNode}
    <div class="dialog-overlay" role="presentation" onclick={() => showIntentDialog = false} onkeydown={(e) => e.key === 'Escape' && (showIntentDialog = false)}>
      <div class="dialog" role="dialog" aria-modal="true" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
        <h3>Give Intent for {selectedNode.title}</h3>
        <p class="dialog-hint">What would you like to do with this file?</p>
        
        <textarea 
          bind:value={intentInput}
          placeholder="e.g., Fix the broken links, Update to match current API, Add missing tests..."
          rows="4"
        ></textarea>
        
        <div class="dialog-actions">
          <button class="cancel-btn" onclick={() => showIntentDialog = false}>
            Cancel
          </button>
          <button class="confirm-btn" onclick={handleIntentSubmit}>
            Execute Intent
          </button>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .state-dag-view {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }
  
  .dag-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 24px;
    border-bottom: 1px solid var(--border-color);
    background: var(--bg-secondary);
  }
  
  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  
  .header-left h1 {
    margin: 0;
    font-size: 20px;
    font-weight: 600;
  }
  
  .project-badge {
    padding: 4px 10px;
    background: var(--bg-tertiary);
    border-radius: 12px;
    font-size: 12px;
    font-family: var(--font-mono);
    color: var(--text-secondary);
  }
  
  .header-right {
    display: flex;
    align-items: center;
    gap: 16px;
  }
  
  .health-indicator {
    font-size: 16px;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  
  .stats {
    font-size: 13px;
    color: var(--text-tertiary);
  }
  
  .refresh-btn {
    padding: 8px 14px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    font-size: 13px;
    cursor: pointer;
    color: var(--text-secondary);
  }
  
  .refresh-btn:hover {
    background: var(--bg-primary);
    border-color: var(--text-tertiary);
  }
  
  .dag-container {
    flex: 1;
    display: grid;
    grid-template-columns: 1fr 320px;
    grid-template-rows: auto 1fr;
    gap: 16px;
    padding: 20px;
    overflow: hidden;
  }
  
  .summary-cards {
    grid-column: 1 / -1;
    display: flex;
    gap: 12px;
  }
  
  .summary-card {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 18px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    opacity: 0.6;
  }
  
  .summary-card.has-items {
    opacity: 1;
  }
  
  .summary-card.critical.has-items {
    border-color: var(--error);
    background: color-mix(in srgb, var(--error) 5%, var(--bg-secondary));
  }
  
  .summary-card.warning.has-items {
    border-color: var(--warning);
    background: color-mix(in srgb, var(--warning) 5%, var(--bg-secondary));
  }
  
  .summary-card .emoji {
    font-size: 20px;
  }
  
  .summary-card .count {
    font-size: 24px;
    font-weight: 700;
    color: var(--text-primary);
  }
  
  .summary-card .label {
    font-size: 13px;
    color: var(--text-secondary);
  }
  
  .node-list {
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  
  .node-list h3 {
    margin: 0 0 12px;
    font-size: 14px;
    color: var(--text-tertiary);
  }
  
  .node-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    cursor: pointer;
    text-align: left;
    transition: all 0.15s ease;
  }
  
  .node-item:hover {
    background: var(--bg-tertiary);
    border-color: var(--text-tertiary);
  }
  
  .node-item.selected {
    border-color: var(--accent);
    background: color-mix(in srgb, var(--accent) 5%, var(--bg-secondary));
  }
  
  .node-item.critical {
    border-color: var(--error);
  }
  
  .node-item.warning {
    border-color: var(--warning);
  }
  
  .node-health {
    font-size: 14px;
  }
  
  .node-title {
    flex: 1;
    font-size: 13px;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  .node-score {
    font-size: 12px;
    font-family: var(--font-mono);
    color: var(--text-tertiary);
  }
  
  .node-detail {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    overflow-y: auto;
  }
  
  .detail-header {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  
  .health-badge {
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    color: var(--bg-primary);
  }
  
  .detail-header h3 {
    margin: 0;
    font-size: 16px;
    color: var(--text-primary);
  }
  
  .detail-path {
    font-size: 12px;
    font-family: var(--font-mono);
    color: var(--text-tertiary);
    word-break: break-all;
  }
  
  .detail-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    font-size: 12px;
    color: var(--text-secondary);
  }
  
  .probes h4 {
    margin: 0 0 10px;
    font-size: 13px;
    color: var(--text-secondary);
  }
  
  .probe {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 0;
    border-bottom: 1px solid var(--border-color);
    font-size: 12px;
  }
  
  .probe-icon {
    color: var(--success);
  }
  
  .probe.failing .probe-icon {
    color: var(--error);
  }
  
  .probe-name {
    flex: 1;
    color: var(--text-primary);
  }
  
  .probe-score {
    font-family: var(--font-mono);
    color: var(--text-tertiary);
  }
  
  .probe-issues {
    margin: 8px 0 0 24px;
    padding: 0;
    list-style: disc;
    font-size: 11px;
    color: var(--error);
  }
  
  .detail-actions {
    display: flex;
    gap: 10px;
    margin-top: auto;
    padding-top: 16px;
    border-top: 1px solid var(--border-color);
  }
  
  .intent-btn {
    flex: 1;
    padding: 10px;
    background: var(--accent);
    border: none;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 600;
    color: var(--bg-primary);
    cursor: pointer;
  }
  
  .intent-btn:hover {
    filter: brightness(1.1);
  }
  
  .open-btn {
    padding: 10px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    font-size: 13px;
    cursor: pointer;
    color: var(--text-secondary);
  }
  
  .open-btn:hover {
    background: var(--bg-primary);
  }
  
  /* Loading, Error, Empty States */
  .loading, .error, .empty-state {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 16px;
    color: var(--text-tertiary);
  }
  
  .spinner {
    width: 32px;
    height: 32px;
    border: 3px solid var(--border-color);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  
  /* Dialog */
  .dialog-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }
  
  .dialog {
    background: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: 16px;
    padding: 24px;
    width: 480px;
    max-width: 90vw;
  }
  
  .dialog h3 {
    margin: 0 0 8px;
    font-size: 18px;
  }
  
  .dialog-hint {
    margin: 0 0 16px;
    font-size: 13px;
    color: var(--text-tertiary);
  }
  
  .dialog textarea {
    width: 100%;
    padding: 12px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    font-size: 14px;
    color: var(--text-primary);
    resize: vertical;
    font-family: inherit;
  }
  
  .dialog textarea:focus {
    outline: none;
    border-color: var(--accent);
  }
  
  .dialog-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 16px;
  }
  
  .cancel-btn {
    padding: 10px 20px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    font-size: 14px;
    color: var(--text-secondary);
    cursor: pointer;
  }
  
  .confirm-btn {
    padding: 10px 20px;
    background: var(--accent);
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    color: var(--bg-primary);
    cursor: pointer;
  }
</style>
