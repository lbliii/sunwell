<!--
  MemoryLattice — Force-directed knowledge graph visualization (RFC-112)
  
  Shows project knowledge growing over time with facts, decisions, and dead ends.
  
  Data contract:
  - nodes: Array<{ id, label, category, timestamp, recall_count }>
  - edges: Array<{ source, target, relation, confidence }>
  - timeline: { start, end }
-->
<script lang="ts">
  import { fade } from 'svelte/transition';
  import { onMount } from 'svelte';
  
  interface Props {
    isLive?: boolean;
  }
  
  let { isLive = true }: Props = $props();
  
  // Demo data
  const demoNodes = [
    { id: 'auth', label: 'OAuth', category: 'decision', x: 300, y: 150 },
    { id: 'jwt', label: 'JWT', category: 'dead_end', x: 450, y: 100 },
    { id: 'module', label: 'auth module', category: 'fact', x: 250, y: 250 },
    { id: 'billing', label: 'billing.py', category: 'fact', x: 200, y: 350 },
    { id: 'patterns', label: 'snake_case', category: 'pattern', x: 400, y: 300 },
    { id: 'types', label: 'type hints', category: 'pattern', x: 500, y: 250 },
  ];
  
  const demoEdges = [
    { source: 'auth', target: 'jwt', relation: 'contradicts' },
    { source: 'auth', target: 'module', relation: 'decided_on' },
    { source: 'module', target: 'billing', relation: 'depends_on' },
    { source: 'patterns', target: 'types', relation: 'elaborates' },
  ];
  
  let selectedNode = $state<string | null>(null);
  let hoveredNode = $state<string | null>(null);
  
  function getCategoryColor(category: string): string {
    switch (category) {
      case 'fact': return 'var(--info)';
      case 'decision': return 'var(--ui-gold)';
      case 'dead_end': return 'var(--error)';
      case 'pattern': return 'var(--success)';
      default: return 'var(--text-secondary)';
    }
  }
  
  function getRelationStyle(relation: string): string {
    switch (relation) {
      case 'contradicts': return '5, 5';
      case 'decided_on': return 'none';
      case 'depends_on': return 'none';
      case 'elaborates': return '2, 2';
      default: return 'none';
    }
  }
</script>

<div class="memory-lattice" in:fade={{ duration: 300 }}>
  <div class="lattice-header">
    <h2>Memory Lattice</h2>
    <p class="description">Explore the knowledge graph Sunwell built about your project</p>
  </div>
  
  <div class="lattice-content">
    <svg viewBox="0 0 700 450" class="lattice-svg">
      <!-- Edges -->
      {#each demoEdges as edge}
        {@const source = demoNodes.find(n => n.id === edge.source)}
        {@const target = demoNodes.find(n => n.id === edge.target)}
        {#if source && target}
          <line
            x1={source.x}
            y1={source.y}
            x2={target.x}
            y2={target.y}
            class="edge"
            class:highlighted={selectedNode === source.id || selectedNode === target.id}
            stroke-dasharray={getRelationStyle(edge.relation)}
          />
        {/if}
      {/each}
      
      <!-- Nodes -->
      {#each demoNodes as node}
        <g
          class="node"
          transform="translate({node.x}, {node.y})"
          onclick={() => selectedNode = selectedNode === node.id ? null : node.id}
          onmouseenter={() => hoveredNode = node.id}
          onmouseleave={() => hoveredNode = null}
          role="button"
          tabindex="0"
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
          />
          
          <!-- Node label -->
          <text y="40" class="node-label">{node.label}</text>
          
          <!-- Category icon -->
          <text y="6" class="node-icon">
            {#if node.category === 'decision'}◆
            {:else if node.category === 'dead_end'}✕
            {:else if node.category === 'pattern'}⬡
            {:else}●{/if}
          </text>
        </g>
      {/each}
    </svg>
    
    <!-- Legend -->
    <div class="legend">
      <div class="legend-item">
        <span class="legend-dot" style="background: var(--info)"></span>
        <span>Facts ({demoNodes.filter(n => n.category === 'fact').length})</span>
      </div>
      <div class="legend-item">
        <span class="legend-dot" style="background: var(--ui-gold)"></span>
        <span>Decisions ({demoNodes.filter(n => n.category === 'decision').length})</span>
      </div>
      <div class="legend-item">
        <span class="legend-dot" style="background: var(--success)"></span>
        <span>Patterns ({demoNodes.filter(n => n.category === 'pattern').length})</span>
      </div>
      <div class="legend-item">
        <span class="legend-dot dead-end" style="background: var(--error)"></span>
        <span>Dead Ends ({demoNodes.filter(n => n.category === 'dead_end').length})</span>
      </div>
    </div>
    
    <!-- Detail panel -->
    {#if selectedNode}
      {@const node = demoNodes.find(n => n.id === selectedNode)}
      {#if node}
        <div class="detail-panel" in:fade={{ duration: 200 }}>
          <div class="detail-header" style="border-color: {getCategoryColor(node.category)}">
            <span class="detail-category" style="color: {getCategoryColor(node.category)}">
              {node.category}
            </span>
            <h3>{node.label}</h3>
          </div>
          <div class="detail-body">
            <p class="detail-description">
              {#if node.category === 'decision'}
                Sunwell decided to use {node.label} based on project requirements and previous failures.
              {:else if node.category === 'dead_end'}
                This approach was tried but abandoned after multiple failures.
              {:else if node.category === 'pattern'}
                Detected pattern: {node.label} is consistently used throughout the project.
              {:else}
                Key fact about the project structure.
              {/if}
            </p>
            <div class="detail-connections">
              <span class="connections-label">Connections:</span>
              <span class="connections-count">
                {demoEdges.filter(e => e.source === node.id || e.target === node.id).length}
              </span>
            </div>
          </div>
        </div>
      {/if}
    {/if}
  </div>
  
  <div class="lattice-footer">
    <span class="stat">Total Nodes: {demoNodes.length}</span>
    <span class="separator">•</span>
    <span class="stat">Edges: {demoEdges.length}</span>
    <span class="separator">•</span>
    <span class="stat hint">Click a node to explore</span>
  </div>
</div>

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
    margin: 0;
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
    stroke: var(--border-default);
    stroke-width: 2;
    opacity: 0.4;
    transition: all var(--transition-fast);
  }
  
  .edge.highlighted {
    stroke: var(--ui-gold);
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
    filter: drop-shadow(0 0 12px currentColor);
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
    width: 220px;
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
  
  .detail-connections {
    display: flex;
    justify-content: space-between;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
  }
  
  .connections-label {
    color: var(--text-tertiary);
  }
  
  .connections-count {
    color: var(--text-gold);
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
