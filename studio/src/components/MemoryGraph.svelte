<!--
  MemoryGraph — Visualization of ConceptGraph relationships (Svelte 5, RFC-084)
  
  Renders the actual ConceptGraph from Simulacrum memory as an SVG graph.
  Shows concept relationships: ELABORATES, CONTRADICTS, DEPENDS_ON, etc.
-->
<script lang="ts">
  import { apiGet, apiPost } from '$lib/socket';
  import type { ConceptEdge, RelationType } from '$lib/types';
  
  interface ConceptNode {
    id: string;
    x: number;
    y: number;
    label: string;
  }
  
  interface Props {
    projectPath?: string;
    concepts?: { id: string; label: string; category: string }[];
  }
  
  let { projectPath = '', concepts = [] }: Props = $props();
  
  // State
  let edges: ConceptEdge[] = $state([]);
  let nodes: ConceptNode[] = $state([]);
  let loading = $state(false);
  let error = $state<string | null>(null);
  
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
  
  // Color by relation type - Holy Light palette
  const RELATION_COLORS: Record<RelationType, string> = {
    elaborates: 'var(--ui-gold)',       // gold (primary)
    summarizes: 'var(--ui-gold-soft)',  // soft gold
    exemplifies: 'var(--text-gold)',    // bright gold
    contradicts: 'var(--error)',        // error red
    supports: 'var(--success)',         // success green
    qualifies: 'var(--warning)',        // warning amber
    depends_on: 'var(--info)',          // info blue
    supersedes: 'var(--warning)',       // amber
    relates_to: 'var(--text-secondary)', // muted
    follows: 'var(--info)',             // info
    updates: 'var(--success)',          // success
  };
  
  // Load graph when project path changes
  $effect(() => {
    if (projectPath) {
      loadGraph();
    }
  });
  
  async function loadGraph() {
    loading = true;
    error = null;
    
    try {
      // RFC-113: Uses HTTP API instead of Tauri invoke
      const result = await apiGet<{ edges: ConceptEdge[] }>(`/api/memory/graph?path=${encodeURIComponent(projectPath)}`);
      
      edges = result?.edges || [];
      
      // Extract unique nodes from edges
      const nodeSet = new Set<string>();
      for (const edge of edges) {
        nodeSet.add(edge.sourceId);
        nodeSet.add(edge.targetId);
      }
      
      // Assign positions using force-directed-like layout
      const nodeIds = Array.from(nodeSet).slice(0, 8);
      nodes = nodeIds.map((id, i) => ({
        id,
        x: NODE_POSITIONS[i % NODE_POSITIONS.length].x,
        y: NODE_POSITIONS[i % NODE_POSITIONS.length].y,
        label: id.slice(0, 12),
      }));
    } catch (e) {
      console.warn('Failed to load concept graph:', e);
      error = String(e);
      edges = [];
      nodes = [];
    } finally {
      loading = false;
    }
  }
  
  // If no project path, fall back to legacy concept display
  let legacyNodes = $derived(
    !projectPath && concepts.length > 0
      ? concepts.slice(-8).map((c, i) => ({
          id: c.id,
          x: NODE_POSITIONS[i % NODE_POSITIONS.length].x,
          y: NODE_POSITIONS[i % NODE_POSITIONS.length].y,
          label: c.label,
          color: {
            framework: '#60a5fa',
            database: '#34d399',
            testing: '#fbbf24',
            pattern: '#a78bfa',
            tool: '#f472b6',
            language: '#fb923c',
          }[c.category] ?? 'var(--text-tertiary)',
        }))
      : []
  );
  
  // Create edges from sequential legacy nodes
  let legacyEdges = $derived(
    legacyNodes.slice(1).map((node, i) => ({
      x1: legacyNodes[i].x,
      y1: legacyNodes[i].y,
      x2: node.x,
      y2: node.y,
      key: `${legacyNodes[i].id}-${node.id}`,
    }))
  );
  
  // Node lookup for edge rendering
  let nodeMap = $derived(new Map(nodes.map(n => [n.id, n])));
</script>

<div class="memory-graph-container" aria-hidden="true">
  <svg viewBox="0 0 120 100" class="memory-graph">
    {#if projectPath && edges.length > 0}
      <!-- RFC-084: Render actual ConceptGraph edges -->
      {#each edges as edge (`${edge.sourceId}-${edge.targetId}-${edge.relation}`)}
        {@const source = nodeMap.get(edge.sourceId)}
        {@const target = nodeMap.get(edge.targetId)}
        {#if source && target}
          <line
            x1={source.x}
            y1={source.y}
            x2={target.x}
            y2={target.y}
            stroke={RELATION_COLORS[edge.relation] ?? 'var(--border-color)'}
            stroke-width={Math.max(1, edge.confidence * 2)}
            opacity={0.4 + edge.confidence * 0.4}
            class="edge"
          >
            <title>{edge.sourceId} —{edge.relation}→ {edge.targetId}</title>
          </line>
        {/if}
      {/each}
      
      <!-- Render nodes -->
      {#each nodes as node, i (node.id)}
        <g class="node-group" style="--delay: {i * 100}ms">
          <!-- Glow effect -->
          <circle
            cx={node.x}
            cy={node.y}
            r="10"
            fill="var(--accent)"
            class="node-glow"
          />
          <!-- Main node -->
          <circle
            cx={node.x}
            cy={node.y}
            r="5"
            fill="var(--accent)"
            class="node"
          />
          <title>{node.label}</title>
        </g>
      {/each}
    {:else if legacyNodes.length > 0}
      <!-- Legacy: Sequential concept nodes -->
      {#each legacyEdges as edge (edge.key)}
        <line
          x1={edge.x1}
          y1={edge.y1}
          x2={edge.x2}
          y2={edge.y2}
          class="edge"
        />
      {/each}
      
      <!-- Cross-links for visual interest -->
      {#if legacyNodes.length >= 3}
        <line
          x1={legacyNodes[0].x}
          y1={legacyNodes[0].y}
          x2={legacyNodes[legacyNodes.length - 1].x}
          y2={legacyNodes[legacyNodes.length - 1].y}
          class="edge edge-faint"
        />
      {/if}
      
      {#each legacyNodes as node (node.id)}
        <g class="node-group" style="--delay: {legacyNodes.indexOf(node) * 100}ms">
          <circle
            cx={node.x}
            cy={node.y}
            r="10"
            fill={node.color}
            class="node-glow"
          />
          <circle
            cx={node.x}
            cy={node.y}
            r="5"
            fill={node.color}
            class="node"
          />
          <title>{node.label}</title>
        </g>
      {/each}
    {:else}
      <!-- Empty state placeholder -->
      <circle cx="60" cy="50" r="4" class="node-placeholder" />
      <text x="60" y="70" class="placeholder-text">
        {#if loading}loading...{:else if error}error{:else}...{/if}
      </text>
    {/if}
  </svg>
  <span class="graph-label">
    {#if edges.length > 0}
      {edges.length} relationships
    {:else}
      memory
    {/if}
  </span>
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
    transition: opacity 0.2s ease;
  }
  
  .edge:hover {
    opacity: 0.7;
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
    cursor: pointer;
    transition: r 0.2s ease;
  }
  
  .node:hover {
    r: 7;
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
