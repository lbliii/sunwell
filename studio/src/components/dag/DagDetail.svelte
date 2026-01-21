<!--
  DagDetail — Expanded detail panel for selected node (Svelte 5)
-->
<script lang="ts">
  import { invoke } from '@tauri-apps/api/core';
  import { dag, selectNode, completeNode, updateNode } from '../../stores/dag.svelte';
  import { project } from '../../stores/project.svelte';
  import { agent } from '../../stores/agent.svelte';
  import Button from '../Button.svelte';
  
  let node = $derived(dag.selectedNode);
  let dependencyNodes = $derived(node ? dag.layouted.nodes.filter(n => node.dependsOn.includes(n.id)) : []);
  let dependentNodes = $derived(node ? dag.layouted.nodes.filter(n => n.dependsOn.includes(node.id)) : []);
  
  let isExecuting = $state(false);
  let executeError = $state<string | null>(null);
  
  function handleClose() { selectNode(null); }
  
  async function handleExecute() {
    const currentNode = node;
    const projectPath = project.current?.path;
    if (!currentNode || !projectPath) return;
    
    if (agent.isRunning) { executeError = 'Agent is already running. Stop it first.'; return; }
    if (currentNode.status !== 'ready' && currentNode.status !== 'pending') { executeError = 'Node is not ready to execute'; return; }
    
    isExecuting = true;
    executeError = null;
    
    try {
      updateNode(currentNode.id, { status: 'running', currentAction: 'Starting...' });
      await invoke('execute_dag_node', { path: projectPath, nodeId: currentNode.id });
    } catch (e) {
      console.error('Failed to execute:', e);
      executeError = e instanceof Error ? e.message : String(e);
      updateNode(currentNode.id, { status: 'ready', currentAction: undefined });
    } finally {
      isExecuting = false;
    }
  }
  
  function handleMarkComplete() { if (node) completeNode(node.id); }
  
  function formatProgress(progress: number): string {
    const filled = Math.round(progress / 5);
    return '█'.repeat(filled) + '░'.repeat(20 - filled);
  }
</script>

{#if node}
  <aside class="dag-detail" aria-label="Task details">
    <header class="detail-header">
      <div class="header-left">
        <span class="source-badge" class:ai={node.source === 'ai'} class:human={node.source === 'human'}>
          {node.source === 'ai' ? '🤖 AI' : node.source === 'human' ? '👤 Human' : '🔗 External'}
        </span>
        <h2 class="detail-title">{node.title}</h2>
      </div>
      <button class="close-btn" onclick={handleClose} aria-label="Close detail panel">✕</button>
    </header>
    
    <div class="status-bar status-{node.status}">
      {#if node.status === 'running'}
        <div class="progress-section">
          <span class="progress-bar">{formatProgress(node.progress)}</span>
          <span class="progress-value">{node.progress}%</span>
        </div>
        {#if node.currentAction}<p class="current-action">{node.currentAction}</p>{/if}
      {:else if node.status === 'complete'}<span class="status-text">✓ Complete</span>
      {:else if node.status === 'ready'}<span class="status-text">▸ Ready to execute</span>
      {:else if node.status === 'blocked'}<span class="status-text">⏸ Waiting on dependencies</span>
      {:else if node.status === 'failed'}<span class="status-text">✗ Failed</span>
      {:else}<span class="status-text">○ Pending</span>
      {/if}
    </div>
    
    <section class="detail-section"><p class="description">{node.description}</p></section>
    
    <section class="detail-section">
      <div class="meta-grid">
        <div class="meta-item">
          <span class="meta-label">Priority</span>
          <span class="meta-value priority">{'█'.repeat(Math.round(node.priority * 5))}{'░'.repeat(5 - Math.round(node.priority * 5))}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">Effort</span>
          <span class="meta-value">{node.effort}</span>
        </div>
        {#if node.category}
          <div class="meta-item"><span class="meta-label">Category</span><span class="meta-value">{node.category}</span></div>
        {/if}
      </div>
    </section>
    
    {#if dependencyNodes.length > 0}
      <section class="detail-section">
        <h3 class="section-title">Dependencies ({dependencyNodes.length})</h3>
        <ul class="node-list">
          {#each dependencyNodes as dep}
            <li class="node-list-item" class:complete={dep.status === 'complete'}>
              <span class="node-status-icon">{dep.status === 'complete' ? '✓' : dep.status === 'running' ? '◐' : '○'}</span>
              <span class="node-name">{dep.title}</span>
            </li>
          {/each}
        </ul>
      </section>
    {/if}
    
    {#if dependentNodes.length > 0}
      <section class="detail-section">
        <h3 class="section-title">Blocks ({dependentNodes.length})</h3>
        <ul class="node-list">
          {#each dependentNodes as dep}
            <li class="node-list-item">
              <span class="node-status-icon">{dep.status === 'blocked' ? '⏸' : '○'}</span>
              <span class="node-name">{dep.title}</span>
            </li>
          {/each}
        </ul>
      </section>
    {/if}
    
    <footer class="detail-actions">
      {#if executeError}<p class="execute-error" role="alert">{executeError}</p>{/if}
      {#if node.status === 'ready' || node.status === 'pending'}
        <Button variant="primary" size="sm" icon={isExecuting ? '...' : '▶'} onclick={handleExecute} disabled={isExecuting || agent.isRunning}>
          {isExecuting ? 'Starting...' : agent.isRunning ? 'Agent busy' : 'Execute'}
        </Button>
      {:else if node.status === 'running'}
        <Button variant="secondary" size="sm" disabled>Running...</Button>
      {/if}
      {#if node.status !== 'complete' && node.status !== 'failed' && node.status !== 'running'}
        <Button variant="ghost" size="sm" onclick={handleMarkComplete}>Mark Complete</Button>
      {/if}
    </footer>
  </aside>
{/if}

<style>
  .dag-detail { width: 320px; background: var(--bg-secondary); border-left: 1px solid var(--border-color); display: flex; flex-direction: column; overflow: hidden; }
  .detail-header { display: flex; align-items: flex-start; justify-content: space-between; padding: 16px; border-bottom: 1px solid var(--border-color); }
  .header-left { display: flex; flex-direction: column; gap: 8px; flex: 1; min-width: 0; }
  .source-badge { font-size: 10px; padding: 2px 6px; border-radius: 4px; background: var(--bg-tertiary); color: var(--text-secondary); width: fit-content; }
  .source-badge.ai { background: var(--info-muted); color: var(--info); }
  .source-badge.human { background: var(--warning-muted); color: var(--warning); }
  .detail-title { font-size: 16px; font-weight: 600; color: var(--text-primary); margin: 0; word-wrap: break-word; }
  .close-btn { background: transparent; border: none; color: var(--text-tertiary); font-size: 18px; cursor: pointer; padding: 4px; line-height: 1; }
  .close-btn:hover { color: var(--text-primary); }
  .status-bar { padding: 12px 16px; border-bottom: 1px solid var(--border-color); }
  .status-bar.status-complete { background: var(--success-muted); }
  .status-bar.status-running { background: var(--info-muted); }
  .status-bar.status-ready { background: var(--warning-muted); }
  .status-bar.status-failed { background: var(--error-muted); }
  .progress-section { display: flex; align-items: center; gap: 8px; }
  .progress-bar { font-size: 10px; letter-spacing: -1px; color: var(--info); }
  .progress-value { font-weight: 600; color: var(--text-primary); }
  .current-action { font-size: 11px; color: var(--text-secondary); margin: 4px 0 0; }
  .status-text { font-size: 13px; font-weight: 500; }
  .status-complete .status-text { color: var(--success); }
  .status-running .status-text { color: var(--info); }
  .status-ready .status-text { color: var(--warning); }
  .status-failed .status-text { color: var(--error); }
  .status-blocked .status-text { color: var(--text-tertiary); }
  .detail-section { padding: 16px; border-bottom: 1px solid var(--border-color); }
  .description { font-size: 13px; color: var(--text-secondary); line-height: 1.5; margin: 0; }
  .section-title { font-size: 11px; font-weight: 600; color: var(--text-tertiary); text-transform: uppercase; letter-spacing: 0.5px; margin: 0 0 8px; }
  .meta-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
  .meta-item { display: flex; flex-direction: column; gap: 4px; }
  .meta-label { font-size: 10px; color: var(--text-tertiary); text-transform: uppercase; }
  .meta-value { font-size: 12px; color: var(--text-primary); }
  .meta-value.priority { font-size: 10px; letter-spacing: -1px; color: var(--warning); }
  .node-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 6px; }
  .node-list-item { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--text-secondary); }
  .node-list-item.complete { color: var(--text-tertiary); }
  .node-status-icon { font-size: 10px; }
  .node-list-item.complete .node-status-icon { color: var(--success); }
  .detail-actions { padding: 16px; margin-top: auto; display: flex; flex-wrap: wrap; gap: 8px; }
  .execute-error { width: 100%; font-size: 11px; color: var(--error); margin: 0 0 8px 0; }
</style>
