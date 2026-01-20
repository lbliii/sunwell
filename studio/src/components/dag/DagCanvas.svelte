<!--
  DagCanvas — Main SVG container for the DAG visualization
  
  Handles pan, zoom, and renders all nodes and edges.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import DagNode from './DagNode.svelte';
  import DagEdge from './DagEdge.svelte';
  import { 
    layoutedGraph, 
    dagViewState, 
    selectedNode,
    setZoom, 
    setPan,
    wouldUnblock
  } from '../../stores/dag';
  import type { DagNode as DagNodeType } from '$lib/types';
  
  let svgElement: SVGSVGElement;
  let containerWidth = 800;
  let containerHeight = 600;
  
  // Pan state
  let isPanning = false;
  let panStart = { x: 0, y: 0 };
  
  // Computed graph bounds for auto-fit
  $: graphBounds = computeBounds($layoutedGraph.nodes);
  
  function computeBounds(nodes: DagNodeType[]) {
    if (nodes.length === 0) {
      return { minX: 0, minY: 0, maxX: 800, maxY: 600, width: 800, height: 600 };
    }
    
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    
    for (const node of nodes) {
      const x = node.x ?? 0;
      const y = node.y ?? 0;
      const w = node.width ?? 180;
      const h = node.height ?? 80;
      
      minX = Math.min(minX, x - w / 2);
      minY = Math.min(minY, y - h / 2);
      maxX = Math.max(maxX, x + w / 2);
      maxY = Math.max(maxY, y + h / 2);
    }
    
    const padding = 60;
    return {
      minX: minX - padding,
      minY: minY - padding,
      maxX: maxX + padding,
      maxY: maxY + padding,
      width: maxX - minX + padding * 2,
      height: maxY - minY + padding * 2,
    };
  }
  
  // Get node by ID for edge rendering
  function getNode(id: string): DagNodeType | undefined {
    return $layoutedGraph.nodes.find(n => n.id === id);
  }
  
  // Check if edge should be highlighted
  function isEdgeHighlighted(sourceId: string, targetId: string): boolean {
    const hovered = $dagViewState.hoveredNodeId;
    if (!hovered) return false;
    
    // Highlight edges from hovered node
    if (sourceId === hovered) return true;
    
    // Highlight edges leading to nodes that would unblock
    if ($wouldUnblock.some(n => n.id === targetId && 
      $layoutedGraph.edges.some(e => e.source === hovered && e.target === targetId)
    )) {
      return true;
    }
    
    return false;
  }
  
  // Pan handlers
  function handleMouseDown(e: MouseEvent) {
    if (e.button === 1 || (e.button === 0 && e.shiftKey)) {
      isPanning = true;
      panStart = { x: e.clientX - $dagViewState.pan.x, y: e.clientY - $dagViewState.pan.y };
      e.preventDefault();
    }
  }
  
  function handleMouseMove(e: MouseEvent) {
    if (isPanning) {
      setPan(e.clientX - panStart.x, e.clientY - panStart.y);
    }
  }
  
  function handleMouseUp() {
    isPanning = false;
  }
  
  // Zoom handler
  function handleWheel(e: WheelEvent) {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.1 : 0.1;
    setZoom($dagViewState.zoom + delta);
  }
  
  // Fit to view
  export function fitToView() {
    if (containerWidth === 0 || containerHeight === 0) return;
    
    const scaleX = containerWidth / graphBounds.width;
    const scaleY = containerHeight / graphBounds.height;
    const scale = Math.min(scaleX, scaleY, 1.5);
    
    const centerX = (graphBounds.minX + graphBounds.maxX) / 2;
    const centerY = (graphBounds.minY + graphBounds.maxY) / 2;
    
    setZoom(scale);
    setPan(
      containerWidth / 2 - centerX * scale,
      containerHeight / 2 - centerY * scale
    );
  }
  
  onMount(() => {
    const resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        containerWidth = entry.contentRect.width;
        containerHeight = entry.contentRect.height;
      }
    });
    
    if (svgElement?.parentElement) {
      resizeObserver.observe(svgElement.parentElement);
    }
    
    // Initial fit
    setTimeout(fitToView, 100);
    
    return () => resizeObserver.disconnect();
  });
</script>

<div class="dag-canvas-container">
  <svg
    bind:this={svgElement}
    class="dag-canvas"
    width="100%"
    height="100%"
    role="img"
    aria-label="Task dependency graph"
    on:mousedown={handleMouseDown}
    on:mousemove={handleMouseMove}
    on:mouseup={handleMouseUp}
    on:mouseleave={handleMouseUp}
    on:wheel={handleWheel}
  >
    <!-- Definitions -->
    <defs>
      <!-- Arrowhead marker -->
      <marker
        id="arrowhead"
        markerWidth="10"
        markerHeight="7"
        refX="9"
        refY="3.5"
        orient="auto"
        markerUnits="strokeWidth"
      >
        <polygon
          points="0 0, 10 3.5, 0 7"
          fill="var(--accent-muted)"
        />
      </marker>
      
      <!-- Highlighted arrowhead -->
      <marker
        id="arrowhead-highlight"
        markerWidth="10"
        markerHeight="7"
        refX="9"
        refY="3.5"
        orient="auto"
        markerUnits="strokeWidth"
      >
        <polygon
          points="0 0, 10 3.5, 0 7"
          fill="var(--success)"
        />
      </marker>
      
      <!-- Grid pattern -->
      <pattern
        id="grid"
        width="40"
        height="40"
        patternUnits="userSpaceOnUse"
      >
        <circle cx="20" cy="20" r="1" fill="var(--accent-muted)" opacity="0.3" />
      </pattern>
    </defs>
    
    <!-- Background grid -->
    <rect
      width="100%"
      height="100%"
      fill="url(#grid)"
      transform="translate({$dagViewState.pan.x % 40}, {$dagViewState.pan.y % 40})"
    />
    
    <!-- Main content group with transform -->
    <g 
      class="dag-content"
      transform="translate({$dagViewState.pan.x}, {$dagViewState.pan.y}) scale({$dagViewState.zoom})"
    >
      <!-- Edges (render first, behind nodes) -->
      <g class="edges">
        {#each $layoutedGraph.edges as edge (edge.id)}
          <DagEdge
            {edge}
            sourceNode={getNode(edge.source)}
            targetNode={getNode(edge.target)}
            isHighlighted={isEdgeHighlighted(edge.source, edge.target)}
          />
        {/each}
      </g>
      
      <!-- Nodes -->
      <g class="nodes">
        {#each $layoutedGraph.nodes as node (node.id)}
          {#if $dagViewState.showCompleted || node.status !== 'complete'}
            <DagNode
              {node}
              isSelected={$dagViewState.selectedNodeId === node.id}
              isHovered={$dagViewState.hoveredNodeId === node.id}
            />
          {/if}
        {/each}
      </g>
    </g>
  </svg>
  
  <!-- Legend -->
  <div class="legend">
    <div class="legend-item">
      <span class="legend-dot complete"></span>
      <span>Complete</span>
    </div>
    <div class="legend-item">
      <span class="legend-dot running"></span>
      <span>Running</span>
    </div>
    <div class="legend-item">
      <span class="legend-dot ready"></span>
      <span>Ready</span>
    </div>
    <div class="legend-item">
      <span class="legend-dot blocked"></span>
      <span>Blocked</span>
    </div>
  </div>
</div>

<style>
  .dag-canvas-container {
    position: relative;
    width: 100%;
    height: 100%;
    overflow: hidden;
    background: var(--bg-primary);
  }
  
  .dag-canvas {
    display: block;
    cursor: grab;
  }
  
  .dag-canvas:active {
    cursor: grabbing;
  }
  
  .legend {
    position: absolute;
    bottom: 16px;
    right: 16px;
    display: flex;
    gap: 16px;
    padding: 8px 12px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--text-secondary);
  }
  
  .legend-item {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  
  .legend-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }
  
  .legend-dot.complete { background: var(--success); }
  .legend-dot.running { background: var(--info); }
  .legend-dot.ready { background: var(--warning); }
  .legend-dot.blocked { background: var(--text-tertiary); }
</style>
