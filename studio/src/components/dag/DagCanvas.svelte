<!--
  DagCanvas — Main SVG container for the DAG visualization (Svelte 5)
-->
<script lang="ts">
  import DagNode from './DagNode.svelte';
  import DagEdge from './DagEdge.svelte';
  import { dag, setZoom, setPan } from '../../stores/dag.svelte';
  import type { DagNode as DagNodeType } from '$lib/types';
  
  let svgElement: SVGSVGElement;
  let containerWidth = $state(800);
  let containerHeight = $state(600);
  let isPanning = $state(false);
  let panStart = $state({ x: 0, y: 0 });
  
  let graphBounds = $derived(computeBounds(dag.layouted.nodes));
  
  function computeBounds(nodes: DagNodeType[]) {
    if (nodes.length === 0) return { minX: 0, minY: 0, maxX: 800, maxY: 600, width: 800, height: 600 };
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const node of nodes) {
      const x = node.x ?? 0, y = node.y ?? 0, w = node.width ?? 180, h = node.height ?? 80;
      minX = Math.min(minX, x - w / 2); minY = Math.min(minY, y - h / 2);
      maxX = Math.max(maxX, x + w / 2); maxY = Math.max(maxY, y + h / 2);
    }
    const padding = 60;
    return { minX: minX - padding, minY: minY - padding, maxX: maxX + padding, maxY: maxY + padding, width: maxX - minX + padding * 2, height: maxY - minY + padding * 2 };
  }
  
  function getNode(id: string): DagNodeType | undefined { return dag.layouted.nodes.find(n => n.id === id); }
  
  function isEdgeHighlighted(sourceId: string, targetId: string): boolean {
    const hovered = dag.hoveredNodeId;
    if (!hovered) return false;
    if (sourceId === hovered) return true;
    if (dag.wouldUnblock.some(n => n.id === targetId && dag.layouted.edges.some(e => e.source === hovered && e.target === targetId))) return true;
    return false;
  }
  
  function handleMouseDown(e: MouseEvent) {
    if (e.button === 1 || (e.button === 0 && e.shiftKey)) {
      isPanning = true; panStart = { x: e.clientX - dag.pan.x, y: e.clientY - dag.pan.y }; e.preventDefault();
    }
  }
  function handleMouseMove(e: MouseEvent) { if (isPanning) setPan(e.clientX - panStart.x, e.clientY - panStart.y); }
  function handleMouseUp() { isPanning = false; }
  function handleWheel(e: WheelEvent) { e.preventDefault(); setZoom(dag.zoom + (e.deltaY > 0 ? -0.1 : 0.1)); }
  
  export function fitToView() {
    if (containerWidth === 0 || containerHeight === 0) return;
    const scaleX = containerWidth / graphBounds.width, scaleY = containerHeight / graphBounds.height;
    const scale = Math.min(scaleX, scaleY, 1.5);
    const centerX = (graphBounds.minX + graphBounds.maxX) / 2, centerY = (graphBounds.minY + graphBounds.maxY) / 2;
    setZoom(scale); setPan(containerWidth / 2 - centerX * scale, containerHeight / 2 - centerY * scale);
  }
  
  $effect(() => {
    const resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) { containerWidth = entry.contentRect.width; containerHeight = entry.contentRect.height; }
    });
    if (svgElement?.parentElement) resizeObserver.observe(svgElement.parentElement);
    setTimeout(fitToView, 100);
    return () => resizeObserver.disconnect();
  });
</script>

<div class="dag-canvas-container">
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <svg bind:this={svgElement} class="dag-canvas" width="100%" height="100%" role="application" aria-label="Interactive task dependency graph"
    onmousedown={handleMouseDown} onmousemove={handleMouseMove} onmouseup={handleMouseUp} onmouseleave={handleMouseUp} onwheel={handleWheel}>
    <defs>
      <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto" markerUnits="strokeWidth">
        <polygon points="0 0, 10 3.5, 0 7" fill="var(--accent-muted)" />
      </marker>
      <marker id="arrowhead-highlight" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto" markerUnits="strokeWidth">
        <polygon points="0 0, 10 3.5, 0 7" fill="var(--success)" />
      </marker>
      <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
        <circle cx="20" cy="20" r="1" fill="var(--accent-muted)" opacity="0.3" />
      </pattern>
    </defs>
    <rect width="100%" height="100%" fill="url(#grid)" transform="translate({dag.pan.x % 40}, {dag.pan.y % 40})" />
    <g class="dag-content" transform="translate({dag.pan.x}, {dag.pan.y}) scale({dag.zoom})">
      <g class="edges">
        {#each dag.layouted.edges as edge (edge.id)}
          <DagEdge {edge} sourceNode={getNode(edge.source)} targetNode={getNode(edge.target)} isHighlighted={isEdgeHighlighted(edge.source, edge.target)} />
        {/each}
      </g>
      <g class="nodes">
        {#each dag.layouted.nodes as node (node.id)}
          {#if dag.showCompleted || node.status !== 'complete'}
            <DagNode {node} isSelected={dag.selectedNodeId === node.id} isHovered={dag.hoveredNodeId === node.id} />
          {/if}
        {/each}
      </g>
    </g>
  </svg>
  <div class="legend">
    {#if dag.incrementalPlan}
      <!-- RFC-074: Incremental execution legend -->
      <div class="legend-item"><span class="legend-dot skip"></span><span>Skip (cached)</span></div>
      <div class="legend-item"><span class="legend-dot execute"></span><span>Execute</span></div>
    {:else}
      <div class="legend-item"><span class="legend-dot complete"></span><span>Complete</span></div>
      <div class="legend-item"><span class="legend-dot running"></span><span>Running</span></div>
      <div class="legend-item"><span class="legend-dot ready"></span><span>Ready</span></div>
      <div class="legend-item"><span class="legend-dot blocked"></span><span>Blocked</span></div>
    {/if}
  </div>
</div>

<style>
  .dag-canvas-container { position: relative; width: 100%; height: 100%; overflow: hidden; background: var(--bg-primary); }
  .dag-canvas { display: block; cursor: grab; }
  .dag-canvas:active { cursor: grabbing; }
  .legend { position: absolute; bottom: 16px; right: 16px; display: flex; gap: 16px; padding: 8px 12px; background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: var(--radius-md); font-family: var(--font-mono); font-size: 10px; color: var(--text-secondary); }
  .legend-item { display: flex; align-items: center; gap: 6px; }
  .legend-dot { width: 8px; height: 8px; border-radius: 50%; }
  .legend-dot.complete { background: var(--success); }
  .legend-dot.running { background: var(--info); }
  .legend-dot.ready { background: var(--warning); }
  .legend-dot.blocked { background: var(--text-tertiary); }
  /* RFC-074: Incremental execution legend */
  .legend-dot.skip { background: var(--success); }
  .legend-dot.execute { background: var(--warning); border: 2px solid var(--warning); background: transparent; }
</style>
