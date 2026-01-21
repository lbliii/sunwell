<!--
  MemoryGraph — Ambient visualization of agent's learned concepts (Svelte 5)
  
  A small SVG graph that grows as the agent discovers concepts.
  Max 8 visible nodes, older ones fade out.
-->
<script lang="ts">
  import type { Concept } from '$lib/types';
  
  interface Props {
    concepts?: Concept[];
  }
  
  let { concepts = [] }: Props = $props();
  
  // Fixed positions for up to 8 nodes in an organic cluster
  const NODE_POSITIONS = [
    { x: 60, y: 15 },   // top center
    { x: 95, y: 30 },   // top right
    { x: 105, y: 55 },  // right
    { x: 85, y: 80 },   // bottom right
    { x: 50, y: 85 },   // bottom center
    { x: 25, y: 70 },   // bottom left
    { x: 15, y: 45 },   // left
    { x: 45, y: 50 },   // center
  ];
  
  // Category colors - muted, cohesive palette
  const CATEGORY_COLORS: Record<string, string> = {
    framework: '#60a5fa',  // blue
    database: '#34d399',   // green
    testing: '#fbbf24',    // amber
    pattern: '#a78bfa',    // purple
    tool: '#f472b6',       // pink
    language: '#fb923c',   // orange
  };
  
  // Take the most recent 8 concepts
  let visibleConcepts = $derived(concepts.slice(-8));
  
  // Map concepts to positioned nodes (with bounds check for safety)
  let nodes = $derived(
    visibleConcepts
      .filter((c): c is Concept => c != null)
      .slice(0, NODE_POSITIONS.length)
      .map((c, i) => ({
        ...c,
        x: NODE_POSITIONS[i]!.x,
        y: NODE_POSITIONS[i]!.y,
        color: CATEGORY_COLORS[c.category] ?? 'var(--text-tertiary)',
        delay: i * 100,
      }))
  );
  
  // Create edges between sequential nodes
  let edges = $derived(
    nodes.slice(1).map((node, i) => ({
      x1: nodes[i].x,
      y1: nodes[i].y,
      x2: node.x,
      y2: node.y,
      key: `${nodes[i].id}-${node.id}`,
    }))
  );
</script>

<div class="memory-graph-container" aria-hidden="true">
  <svg viewBox="0 0 120 100" class="memory-graph">
    <!-- Edges -->
    {#each edges as edge (edge.key)}
      <line
        x1={edge.x1}
        y1={edge.y1}
        x2={edge.x2}
        y2={edge.y2}
        class="edge"
      />
    {/each}
    
    <!-- Cross-links for visual interest (connect some non-adjacent nodes) -->
    {#if nodes.length >= 3}
      <line
        x1={nodes[0].x}
        y1={nodes[0].y}
        x2={nodes[nodes.length - 1].x}
        y2={nodes[nodes.length - 1].y}
        class="edge edge-faint"
      />
    {/if}
    {#if nodes.length >= 5}
      <line
        x1={nodes[1].x}
        y1={nodes[1].y}
        x2={nodes[nodes.length - 2].x}
        y2={nodes[nodes.length - 2].y}
        class="edge edge-faint"
      />
    {/if}
    
    <!-- Nodes -->
    {#each nodes as node (node.id)}
      <g class="node-group" style="--delay: {node.delay}ms">
        <!-- Glow effect -->
        <circle
          cx={node.x}
          cy={node.y}
          r="10"
          fill={node.color}
          class="node-glow"
        />
        <!-- Main node -->
        <circle
          cx={node.x}
          cy={node.y}
          r="5"
          fill={node.color}
          class="node"
        />
        <!-- Tooltip on hover -->
        <title>{node.label}</title>
      </g>
    {/each}
    
    <!-- Empty state placeholder -->
    {#if nodes.length === 0}
      <circle cx="60" cy="50" r="4" class="node-placeholder" />
      <text x="60" y="70" class="placeholder-text">...</text>
    {/if}
  </svg>
  <span class="graph-label">memory</span>
</div>

<style>
  .memory-graph-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    min-width: 120px;
  }
  
  .memory-graph {
    width: 120px;
    height: 100px;
  }
  
  .edge {
    stroke: var(--border-color);
    stroke-width: 1;
    opacity: 0.3;
  }
  
  .edge-faint {
    opacity: 0.15;
    stroke-dasharray: 2 2;
  }
  
  .node-group {
    animation: nodeAppear 0.5s ease-out forwards;
    animation-delay: var(--delay);
    opacity: 0;
  }
  
  .node-glow {
    opacity: 0.15;
    filter: blur(4px);
  }
  
  .node {
    opacity: 0.85;
  }
  
  .node-placeholder {
    fill: var(--text-tertiary);
    opacity: 0.3;
    animation: pulse 2s ease-in-out infinite;
  }
  
  .placeholder-text {
    fill: var(--text-tertiary);
    font-size: 10px;
    text-anchor: middle;
    opacity: 0.3;
  }
  
  .graph-label {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    margin-top: var(--space-1);
    font-family: var(--font-mono);
  }
  
  @keyframes nodeAppear {
    0% {
      opacity: 0;
      transform: scale(0);
    }
    60% {
      opacity: 1;
      transform: scale(1.3);
    }
    100% {
      opacity: 1;
      transform: scale(1);
    }
  }
  
  @keyframes pulse {
    0%, 100% {
      opacity: 0.2;
    }
    50% {
      opacity: 0.4;
    }
  }
</style>
