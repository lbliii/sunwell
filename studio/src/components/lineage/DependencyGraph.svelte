<script lang="ts">
  /**
   * DependencyGraph — Interactive dependency visualization (RFC-121)
   *
   * Displays:
   * - Nodes for tracked files
   * - Edges for import relationships
   * - Color coding for human-edited vs sunwell-generated
   * - Click to select and show lineage
   */

  import {
    lineageState,
    loadGraph,
    loadFileLineage,
    getLanguageIcon,
    type DependencyNode,
    type DependencyEdge,
  } from '../../stores/lineage.svelte';

  interface Props {
    workspace?: string;
    width?: number;
    height?: number;
    onNodeClick?: (path: string) => void;
  }

  let {
    workspace = undefined,
    width = 800,
    height = 600,
    onNodeClick = undefined,
  }: Props = $props();

  // Load graph on mount
  $effect(() => {
    loadGraph(workspace);
  });

  // State
  let selectedNode: string | null = $state(null);
  let hoveredNode: string | null = $state(null);
  let transform = $state({ x: 0, y: 0, scale: 1 });

  // Derived
  const graph = $derived(lineageState.graph);
  const loading = $derived(lineageState.loading);

  // Layout calculation (simple force-directed simulation)
  const layout = $derived.by(() => {
    if (!graph || graph.nodes.length === 0) return { nodes: [], edges: [] };

    const nodes = graph.nodes.map((node, i) => {
      // Simple circular layout for now
      const angle = (2 * Math.PI * i) / graph.nodes.length;
      const radius = Math.min(width, height) * 0.35;
      return {
        ...node,
        x: width / 2 + radius * Math.cos(angle),
        y: height / 2 + radius * Math.sin(angle),
      };
    });

    const nodeMap = new Map(nodes.map(n => [n.id, n]));

    const edges = graph.edges
      .filter(e => nodeMap.has(e.source) && nodeMap.has(e.target))
      .map(edge => ({
        ...edge,
        sourceNode: nodeMap.get(edge.source)!,
        targetNode: nodeMap.get(edge.target)!,
      }));

    return { nodes, edges };
  });

  // Handlers
  function handleNodeClick(node: DependencyNode & { x: number; y: number }) {
    selectedNode = node.id;
    loadFileLineage(node.id, workspace);
    onNodeClick?.(node.id);
  }

  function handleNodeHover(nodeId: string | null) {
    hoveredNode = nodeId;
  }

  function handleWheel(e: WheelEvent) {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    transform.scale = Math.max(0.1, Math.min(3, transform.scale * delta));
  }

  function handlePan(e: MouseEvent) {
    if (e.buttons === 1) {
      transform.x += e.movementX;
      transform.y += e.movementY;
    }
  }

  function resetView() {
    transform = { x: 0, y: 0, scale: 1 };
  }

  // Node color based on state
  function getNodeColor(node: DependencyNode): string {
    if (node.id === selectedNode) return 'var(--accent, #6cf)';
    if (node.human_edited) return 'var(--warning, #fa0)';
    return 'var(--success, #4f8)';
  }

  function getNodeStroke(node: DependencyNode): string {
    if (node.id === hoveredNode) return 'var(--text-1, #fff)';
    return 'transparent';
  }
</script>

<div class="dependency-graph">
  {#if loading}
    <div class="loading">
      <span class="spinner"></span>
      <span>Loading dependency graph...</span>
    </div>
  {:else if !graph || graph.nodes.length === 0}
    <div class="empty">
      <span class="icon">🕸️</span>
      <span>No dependency data</span>
      <span class="hint">Run lineage tracking to build the graph</span>
    </div>
  {:else}
    <!-- Controls -->
    <div class="controls">
      <button class="control-btn" onclick={resetView} title="Reset view">
        ⌖
      </button>
      <span class="stats">
        {graph.node_count} files · {graph.edge_count} deps
      </span>
    </div>

    <!-- Legend -->
    <div class="legend">
      <div class="legend-item">
        <span class="dot sunwell"></span>
        <span>Sunwell</span>
      </div>
      <div class="legend-item">
        <span class="dot human"></span>
        <span>Human Edited</span>
      </div>
    </div>

    <!-- SVG Graph -->
    <svg
      {width}
      {height}
      class="graph-svg"
      onwheel={handleWheel}
      onmousemove={handlePan}
    >
      <g transform="translate({transform.x}, {transform.y}) scale({transform.scale})">
        <!-- Edges -->
        <g class="edges">
          {#each layout.edges as edge (edge.source + '-' + edge.target)}
            <line
              x1={edge.sourceNode.x}
              y1={edge.sourceNode.y}
              x2={edge.targetNode.x}
              y2={edge.targetNode.y}
              class="edge"
              class:highlighted={
                hoveredNode === edge.source || hoveredNode === edge.target
              }
            />
          {/each}
        </g>

        <!-- Nodes -->
        <g class="nodes">
          {#each layout.nodes as node (node.id)}
            <g
              class="node"
              transform="translate({node.x}, {node.y})"
              onclick={() => handleNodeClick(node)}
              onmouseenter={() => handleNodeHover(node.id)}
              onmouseleave={() => handleNodeHover(null)}
            >
              <circle
                r={node.id === selectedNode ? 12 : 8}
                fill={getNodeColor(node)}
                stroke={getNodeStroke(node)}
                stroke-width="2"
              />
              {#if node.id === hoveredNode || node.id === selectedNode}
                <text
                  y={-15}
                  text-anchor="middle"
                  class="node-label"
                >
                  {node.id.split('/').pop()}
                </text>
              {/if}
            </g>
          {/each}
        </g>
      </g>
    </svg>

    <!-- Tooltip -->
    {#if hoveredNode}
      {@const node = layout.nodes.find(n => n.id === hoveredNode)}
      {#if node}
        <div class="tooltip" style="left: {node.x * transform.scale + transform.x + 20}px; top: {node.y * transform.scale + transform.y}px;">
          <div class="tooltip-header">
            <span class="icon">{getLanguageIcon(node.id)}</span>
            <span class="path">{node.id}</span>
          </div>
          <div class="tooltip-body">
            <div class="tooltip-row">
              <span class="label">Edits:</span>
              <span class="value">{node.edit_count}</span>
            </div>
            {#if node.created_by_goal}
              <div class="tooltip-row">
                <span class="label">Goal:</span>
                <span class="value">{node.created_by_goal.slice(0, 8)}</span>
              </div>
            {/if}
            {#if node.model}
              <div class="tooltip-row">
                <span class="label">Model:</span>
                <span class="value">{node.model}</span>
              </div>
            {/if}
          </div>
        </div>
      {/if}
    {/if}
  {/if}
</div>

<style>
  .dependency-graph {
    position: relative;
    background: var(--surface-1, #1a1a1a);
    border-radius: var(--radius-md, 8px);
    overflow: hidden;
  }

  /* Loading & Empty */
  .loading, .empty {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    gap: var(--space-sm, 0.5rem);
    height: 400px;
    color: var(--text-2, #888);
  }

  .spinner {
    width: 24px;
    height: 24px;
    border: 2px solid var(--text-3, #444);
    border-top-color: var(--accent, #6cf);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .hint {
    font-size: 0.75rem;
    color: var(--text-3, #666);
  }

  /* Controls */
  .controls {
    position: absolute;
    top: var(--space-sm, 0.5rem);
    right: var(--space-sm, 0.5rem);
    display: flex;
    align-items: center;
    gap: var(--space-sm, 0.5rem);
    z-index: 10;
  }

  .control-btn {
    width: 32px;
    height: 32px;
    border: none;
    background: var(--surface-2, #252525);
    color: var(--text-1, #eee);
    border-radius: 4px;
    cursor: pointer;
    font-size: 1rem;
  }

  .control-btn:hover {
    background: var(--surface-3, #333);
  }

  .stats {
    font-size: 0.75rem;
    color: var(--text-3, #666);
    background: var(--surface-2, #252525);
    padding: 4px 8px;
    border-radius: 4px;
  }

  /* Legend */
  .legend {
    position: absolute;
    bottom: var(--space-sm, 0.5rem);
    left: var(--space-sm, 0.5rem);
    display: flex;
    gap: var(--space-md, 1rem);
    z-index: 10;
    background: var(--surface-2, #252525);
    padding: 4px 8px;
    border-radius: 4px;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: var(--space-xs, 0.25rem);
    font-size: 0.75rem;
    color: var(--text-2, #888);
  }

  .dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
  }

  .dot.sunwell {
    background: var(--success, #4f8);
  }

  .dot.human {
    background: var(--warning, #fa0);
  }

  /* SVG */
  .graph-svg {
    cursor: grab;
    user-select: none;
  }

  .graph-svg:active {
    cursor: grabbing;
  }

  /* Edges */
  .edge {
    stroke: var(--text-3, #444);
    stroke-width: 1;
    opacity: 0.5;
    transition: opacity 0.15s, stroke 0.15s;
  }

  .edge.highlighted {
    stroke: var(--accent, #6cf);
    opacity: 1;
    stroke-width: 2;
  }

  /* Nodes */
  .node {
    cursor: pointer;
    transition: transform 0.15s;
  }

  .node:hover {
    transform: scale(1.2);
  }

  .node-label {
    font-size: 10px;
    fill: var(--text-1, #eee);
    font-family: var(--font-mono, monospace);
    pointer-events: none;
  }

  /* Tooltip */
  .tooltip {
    position: absolute;
    background: var(--surface-3, #333);
    border: 1px solid var(--border, #444);
    border-radius: 4px;
    padding: var(--space-sm, 0.5rem);
    z-index: 100;
    pointer-events: none;
    min-width: 150px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  }

  .tooltip-header {
    display: flex;
    align-items: center;
    gap: var(--space-xs, 0.25rem);
    padding-bottom: var(--space-xs, 0.25rem);
    border-bottom: 1px solid var(--border, #444);
    margin-bottom: var(--space-xs, 0.25rem);
  }

  .tooltip-header .path {
    font-family: var(--font-mono, monospace);
    font-size: 0.75rem;
    color: var(--text-1, #eee);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 200px;
  }

  .tooltip-body {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .tooltip-row {
    display: flex;
    gap: var(--space-sm, 0.5rem);
    font-size: 0.7rem;
  }

  .tooltip-row .label {
    color: var(--text-3, #666);
  }

  .tooltip-row .value {
    color: var(--text-1, #eee);
    font-family: var(--font-mono, monospace);
  }
</style>
