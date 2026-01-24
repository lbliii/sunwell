<!--
  MemoryLattice — Force-directed knowledge graph visualization (RFC-112)
  
  Shows project knowledge growing over time with facts, decisions, and patterns.
  Uses GlowingNode primitive for interactive nodes.
  
  Data contract:
  - Consumes real events via observatory.memoryLattice
  - Shows empty state when no data
-->
<script lang="ts">
  import { fade, fly, scale } from 'svelte/transition';
  import EmptyState from './EmptyState.svelte';
  import {
    observatory,
    type LatticeNode,
    type LatticeEdge,
    type LatticeNodeCategory,
  } from '../../stores';
  
  interface Props {
    isLive?: boolean;
  }
  
  let { isLive = true }: Props = $props();
  
  // Use real data only
  const latticeState = $derived(observatory.memoryLattice);
  const nodes = $derived(latticeState.nodes);
  const edges = $derived(latticeState.edges);
  const hasData = $derived(nodes.length > 0);
  
  let selectedNode = $state<string | null>(null);
  let hoveredNode = $state<string | null>(null);
  
  function getCategoryColor(category: LatticeNodeCategory): string {
    switch (category) {
      case 'fact': return 'var(--info)';
      case 'decision': return 'var(--ui-gold)';
      case 'dead_end': return 'var(--error)';
      case 'pattern': return 'var(--success)';
      case 'concept': return '#a855f7'; // purple
      default: return 'var(--text-secondary)';
    }
  }
  
  function getCategoryIcon(category: LatticeNodeCategory): string {
    switch (category) {
      case 'decision': return '◆';
      case 'dead_end': return '✕';
      case 'pattern': return '⬡';
      case 'concept': return '◉';
      default: return '●';
    }
  }
  
  function getRelationStyle(relation: string): string {
    switch (relation) {
      case 'contradicts': return '5, 5';
      case 'decided_on': return 'none';
      case 'depends_on': return 'none';
      case 'elaborates': return '2, 2';
      case 'uses': return '3, 3';
      default: return 'none';
    }
  }
  
  function getRelationColor(relation: string): string {
    switch (relation) {
      case 'contradicts': return 'var(--error)';
      case 'decided_on': return 'var(--ui-gold)';
      case 'uses': return 'var(--info)';
      default: return 'var(--border-default)';
    }
  }
  
  function getNodeById(id: string): LatticeNode | undefined {
    return nodes.find(n => n.id === id);
  }
  
  function getConnections(nodeId: string): number {
    return edges.filter(e => e.source === nodeId || e.target === nodeId).length;
  }
  
  function getCategoryCounts() {
    const counts: Record<LatticeNodeCategory, number> = {
      fact: 0,
      decision: 0,
      dead_end: 0,
      pattern: 0,
      concept: 0,
    };
    for (const node of nodes) {
      counts[node.category]++;
    }
    return counts;
  }
  
  const categoryCounts = $derived(getCategoryCounts());
</script>

{#if !hasData}
  <EmptyState
    icon="🧠"
    title="No memory data"
    message="Run a goal to build a knowledge graph of facts, decisions, and patterns about your project."
  />
{:else}
<div class="memory-lattice" in:fade={{ duration: 300 }}>
  <div class="lattice-header">
    <h2>Memory Lattice</h2>
    <p class="description">Explore the knowledge graph Sunwell built about your project</p>
    
    <!-- Status badges -->
    <div class="status-badges">
      <span class="badge live">🧠 Active</span>
      <span class="badge count">{nodes.length} nodes</span>
    </div>
  </div>
  
  <div class="lattice-content">
    <svg viewBox="0 0 700 450" class="lattice-svg">
      <defs>
        <filter id="nodeGlow">
          <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
          <feMerge>
            <feMergeNode in="coloredBlur"/>
            <feMergeNode in="SourceGraphic"/>
          </feMerge>
        </filter>
      </defs>
      
      <!-- Edges -->
      {#each edges as edge}
        {@const source = getNodeById(edge.source)}
        {@const target = getNodeById(edge.target)}
        {#if source && target}
          <line
            x1={source.x}
            y1={source.y}
            x2={target.x}
            y2={target.y}
            class="edge"
            class:highlighted={selectedNode === source.id || selectedNode === target.id}
            stroke={getRelationColor(edge.relation)}
            stroke-dasharray={getRelationStyle(edge.relation)}
          />
        {/if}
      {/each}
      
      <!-- Nodes -->
      {#each nodes as node, i}
        <g
          class="node"
          transform="translate({node.x}, {node.y})"
          onclick={() => selectedNode = selectedNode === node.id ? null : node.id}
          onkeydown={(e) => e.key === 'Enter' && (selectedNode = selectedNode === node.id ? null : node.id)}
          onmouseenter={() => hoveredNode = node.id}
          onmouseleave={() => hoveredNode = null}
          role="button"
          tabindex="0"
          in:scale={{ delay: i * 50, duration: 300 }}
        >
          <!-- Glow ring for selected/hovered -->
          {#if selectedNode === node.id || hoveredNode === node.id}
            <circle
              r="32"
              class="node-glow"
              style="stroke: {getCategoryColor(node.category)}"
            />
          {/if}
          
          <!-- Node circle -->
          <circle
            r="24"
            class="node-circle"
            class:selected={selectedNode === node.id}
            class:dead-end={node.category === 'dead_end'}
            style="fill: {getCategoryColor(node.category)}; opacity: {node.category === 'dead_end' ? 0.5 : 1}"
            filter={selectedNode === node.id ? 'url(#nodeGlow)' : undefined}
          />
          
          <!-- Node label -->
          <text y="40" class="node-label">{node.label}</text>
          
          <!-- Category icon -->
          <text y="6" class="node-icon">
            {getCategoryIcon(node.category)}
          </text>
        </g>
      {/each}
    </svg>
    
    <!-- Legend -->
    <div class="legend">
      {#if categoryCounts.fact > 0}
        <div class="legend-item">
          <span class="legend-dot" style="background: var(--info)"></span>
          <span>Facts ({categoryCounts.fact})</span>
        </div>
      {/if}
      {#if categoryCounts.decision > 0}
        <div class="legend-item">
          <span class="legend-dot" style="background: var(--ui-gold)"></span>
          <span>Decisions ({categoryCounts.decision})</span>
        </div>
      {/if}
      {#if categoryCounts.pattern > 0}
        <div class="legend-item">
          <span class="legend-dot" style="background: var(--success)"></span>
          <span>Patterns ({categoryCounts.pattern})</span>
        </div>
      {/if}
      {#if categoryCounts.concept > 0}
        <div class="legend-item">
          <span class="legend-dot" style="background: #a855f7"></span>
          <span>Concepts ({categoryCounts.concept})</span>
        </div>
      {/if}
      {#if categoryCounts.dead_end > 0}
        <div class="legend-item">
          <span class="legend-dot dead-end" style="background: var(--error)"></span>
          <span>Dead Ends ({categoryCounts.dead_end})</span>
        </div>
      {/if}
    </div>
    
    <!-- Detail panel -->
    {#if selectedNode}
      {@const node = getNodeById(selectedNode)}
      {#if node}
        <div class="detail-panel" in:fly={{ x: 20, duration: 200 }}>
          <div class="detail-header" style="border-color: {getCategoryColor(node.category)}">
            <span class="detail-category" style="color: {getCategoryColor(node.category)}">
              {getCategoryIcon(node.category)} {node.category.replace('_', ' ')}
            </span>
            <h3>{node.label}</h3>
          </div>
          <div class="detail-body">
            <p class="detail-description">
              {#if node.category === 'decision'}
                Sunwell decided to use {node.label} based on project requirements.
              {:else if node.category === 'dead_end'}
                This approach was tried but abandoned after failures.
              {:else if node.category === 'pattern'}
                Detected pattern: {node.label} is used throughout the project.
              {:else if node.category === 'concept'}
                Technology/framework detected in the project.
              {:else}
                Key fact about the project structure.
              {/if}
            </p>
            <div class="detail-stats">
              <div class="stat-item">
                <span class="stat-value">{getConnections(node.id)}</span>
                <span class="stat-label">Connections</span>
              </div>
              {#if node.timestamp}
                <div class="stat-item">
                  <span class="stat-value">{new Date(node.timestamp).toLocaleTimeString()}</span>
                  <span class="stat-label">Discovered</span>
                </div>
              {/if}
            </div>
          </div>
          <button class="close-btn" onclick={() => selectedNode = null}>
            ✕
          </button>
        </div>
      {/if}
    {/if}
  </div>
  
  <div class="lattice-footer">
    <span class="stat">Nodes: {nodes.length}</span>
    <span class="separator">•</span>
    <span class="stat">Edges: {edges.length}</span>
    <span class="separator">•</span>
    <span class="stat hint">Click a node to explore</span>
  </div>
</div>
{/if}

<style>
  .memory-lattice {
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: var(--space-6);
  }
  
  .lattice-header {
    text-align: center;
    margin-bottom: var(--space-4);
  }
  
  .lattice-header h2 {
    font-family: var(--font-serif);
    font-size: var(--text-xl);
    color: var(--text-primary);
    margin: 0 0 var(--space-2);
  }
  
  .description {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-tertiary);
    margin: 0 0 var(--space-2);
  }
  
  .status-badges {
    display: flex;
    justify-content: center;
    gap: var(--space-2);
  }
  
  .badge {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    background: var(--bg-tertiary);
    color: var(--text-secondary);
  }
  
  .badge.live {
    background: rgba(var(--info-rgb), 0.15);
    color: var(--info);
  }
  
  .badge.count {
    background: var(--ui-gold-15);
    color: var(--text-gold);
  }
  
  .lattice-content {
    flex: 1;
    position: relative;
    display: flex;
    justify-content: center;
  }
  
  .lattice-svg {
    width: 100%;
    max-width: 700px;
    height: auto;
  }
  
  .edge {
    stroke-width: 2;
    opacity: 0.4;
    transition: all var(--transition-fast);
  }
  
  .edge.highlighted {
    opacity: 1;
    stroke-width: 3;
  }
  
  .node {
    cursor: pointer;
    transition: transform var(--transition-fast);
  }
  
  .node:hover {
    transform: scale(1.1);
  }
  
  .node:focus {
    outline: none;
  }
  
  .node-glow {
    fill: none;
    stroke-width: 2;
    opacity: 0.4;
    animation: pulse-glow 2s ease-in-out infinite;
  }
  
  @keyframes pulse-glow {
    0%, 100% { r: 32; opacity: 0.4; }
    50% { r: 40; opacity: 0.2; }
  }
  
  .node-circle {
    stroke: var(--bg-primary);
    stroke-width: 3;
    transition: all var(--transition-fast);
  }
  
  .node-circle.selected {
    stroke-width: 4;
  }
  
  .node-circle.dead-end {
    animation: drift 8s ease-in-out infinite;
  }
  
  @keyframes drift {
    0%, 100% { transform: translate(0, 0); }
    50% { transform: translate(5px, -3px); }
  }
  
  .node-label {
    font-family: var(--font-mono);
    font-size: 11px;
    fill: var(--text-secondary);
    text-anchor: middle;
  }
  
  .node-icon {
    font-size: 14px;
    fill: var(--bg-primary);
    text-anchor: middle;
  }
  
  .legend {
    position: absolute;
    top: var(--space-4);
    left: var(--space-4);
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding: var(--space-3);
    background: var(--bg-primary);
    border-radius: var(--radius-md);
    border: 1px solid var(--border-subtle);
  }
  
  .legend-item {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-secondary);
  }
  
  .legend-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
  }
  
  .legend-dot.dead-end {
    opacity: 0.5;
  }
  
  .detail-panel {
    position: absolute;
    top: var(--space-4);
    right: var(--space-4);
    width: 240px;
    background: var(--bg-primary);
    border-radius: var(--radius-md);
    border: 1px solid var(--border-subtle);
    overflow: hidden;
  }
  
  .detail-header {
    padding: var(--space-3);
    border-bottom: 2px solid;
  }
  
  .detail-category {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }
  
  .detail-header h3 {
    font-family: var(--font-mono);
    font-size: var(--text-base);
    color: var(--text-primary);
    margin: var(--space-1) 0 0;
  }
  
  .detail-body {
    padding: var(--space-3);
  }
  
  .detail-description {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-secondary);
    line-height: 1.5;
    margin: 0 0 var(--space-3);
  }
  
  .detail-stats {
    display: flex;
    gap: var(--space-4);
  }
  
  .stat-item {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  
  .stat-value {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: 700;
    color: var(--text-gold);
  }
  
  .stat-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .close-btn {
    position: absolute;
    top: var(--space-2);
    right: var(--space-2);
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: var(--text-sm);
    color: var(--text-tertiary);
    background: none;
    border: none;
    cursor: pointer;
    transition: color var(--transition-fast);
  }
  
  .close-btn:hover {
    color: var(--text-primary);
  }
  
  .lattice-footer {
    display: flex;
    justify-content: center;
    gap: var(--space-3);
    padding-top: var(--space-4);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .separator {
    opacity: 0.4;
  }
  
  .hint {
    color: var(--text-gold);
  }
</style>
