<!--
  DagEdge — Connection line between nodes (Svelte 5)
  
  Draws a smooth bezier curve with optional artifact label.
-->
<script lang="ts">
  import type { DagEdge as DagEdgeType, DagNode } from '$lib/types';
  
  interface Props {
    edge: DagEdgeType;
    sourceNode?: DagNode;
    targetNode?: DagNode;
    isHighlighted?: boolean;
  }
  
  let { edge, sourceNode, targetNode, isHighlighted = false }: Props = $props();
  
  // Compute path from edge points or calculate from nodes
  let pathD = $derived(computePath(edge, sourceNode, targetNode));
  let midpoint = $derived(computeMidpoint(edge, sourceNode, targetNode));
  
  let isComplete = $derived(sourceNode?.status === 'complete');
  let isActive = $derived(sourceNode?.status === 'running');
  
  // RFC-067: Integration edge styling
  let isIntegration = $derived(edge.edgeType === 'integration');
  let verificationStatus = $derived(edge.verificationStatus ?? 'pending');
  let isMissing = $derived(verificationStatus === 'missing');
  let isVerified = $derived(verificationStatus === 'verified');
  
  function computePath(
    edge: DagEdgeType, 
    source: DagNode | undefined, 
    target: DagNode | undefined
  ): string {
    // If dagre provided points, use them
    if (edge.points && edge.points.length >= 2) {
      const [first, ...rest] = edge.points;
      let d = `M ${first.x} ${first.y}`;
      
      if (rest.length === 1) {
        d += ` L ${rest[0].x} ${rest[0].y}`;
      } else {
        // Create smooth curve through points
        for (let i = 0; i < rest.length; i++) {
          const p = rest[i];
          if (i === rest.length - 1) {
            d += ` L ${p.x} ${p.y}`;
          } else {
            const next = rest[i + 1];
            const midX = (p.x + next.x) / 2;
            const midY = (p.y + next.y) / 2;
            d += ` Q ${p.x} ${p.y} ${midX} ${midY}`;
          }
        }
      }
      return d;
    }
    
    // Fallback: compute from node positions
    if (!source || !target) return '';
    
    const sourceX = source.x ?? 0;
    const sourceY = (source.y ?? 0) + (source.height ?? 80) / 2;
    const targetX = target.x ?? 0;
    const targetY = (target.y ?? 0) - (target.height ?? 80) / 2;
    
    // Bezier control points for smooth curve
    const midY = (sourceY + targetY) / 2;
    
    return `M ${sourceX} ${sourceY} C ${sourceX} ${midY}, ${targetX} ${midY}, ${targetX} ${targetY}`;
  }
  
  function computeMidpoint(
    edge: DagEdgeType,
    source: DagNode | undefined,
    target: DagNode | undefined
  ): { x: number; y: number } {
    if (edge.points && edge.points.length >= 2) {
      const midIndex = Math.floor(edge.points.length / 2);
      return edge.points[midIndex];
    }
    
    if (!source || !target) return { x: 0, y: 0 };
    
    return {
      x: ((source.x ?? 0) + (target.x ?? 0)) / 2,
      y: ((source.y ?? 0) + (target.y ?? 0)) / 2,
    };
  }
</script>

<g class="dag-edge" class:highlighted={isHighlighted} class:complete={isComplete} class:active={isActive} class:integration={isIntegration} class:missing={isMissing} class:verified={isVerified}>
  <!-- Shadow/glow for highlighted edges -->
  {#if isHighlighted}
    <path
      class="edge-glow"
      d={pathD}
      fill="none"
    />
  {/if}
  
  <!-- Main line -->
  <path
    class="edge-line"
    d={pathD}
    fill="none"
    marker-end="url(#arrowhead)"
  />
  
  <!-- Artifact label (if present) -->
  {#if edge.artifact && isHighlighted}
    <g class="edge-label" transform="translate({midpoint.x}, {midpoint.y})">
      <rect
        x="-30"
        y="-10"
        width="60"
        height="20"
        rx="4"
        fill="var(--bg-elevated)"
        stroke="var(--border-color)"
      />
      <text
        x="0"
        y="4"
        text-anchor="middle"
        font-size="9"
        fill="var(--text-secondary)"
      >
        {edge.artifact}
      </text>
    </g>
  {/if}
  
  <!-- RFC-067: Missing integration warning -->
  {#if isIntegration && isMissing}
    <g class="integration-warning" transform="translate({midpoint.x}, {midpoint.y})">
      <circle r="8" fill="var(--error)" />
      <text x="0" y="4" text-anchor="middle" font-size="10" fill="var(--bg-primary)">⚠</text>
    </g>
  {/if}
  
  <!-- RFC-067: Verified integration indicator -->
  {#if isIntegration && isVerified}
    <g class="integration-verified" transform="translate({midpoint.x}, {midpoint.y})">
      <circle r="6" fill="var(--success)" />
      <text x="0" y="3" text-anchor="middle" font-size="8" fill="var(--bg-primary)">✓</text>
    </g>
  {/if}
</g>

<style>
  .dag-edge {
    pointer-events: none;
  }
  
  .edge-line {
    stroke: var(--accent-muted);
    stroke-width: 1.5;
    transition: stroke 0.15s ease, stroke-width 0.15s ease;
  }
  
  .dag-edge.complete .edge-line {
    stroke: var(--success);
    opacity: 0.5;
  }
  
  .dag-edge.active .edge-line {
    stroke: var(--info);
    stroke-dasharray: 8 4;
    animation: flow 1s linear infinite;
  }
  
  .dag-edge.highlighted .edge-line {
    stroke: var(--success);
    stroke-width: 2;
  }
  
  .edge-glow {
    stroke: var(--success);
    stroke-width: 6;
    opacity: 0.2;
    filter: blur(4px);
  }
  
  @keyframes flow {
    from { stroke-dashoffset: 24; }
    to { stroke-dashoffset: 0; }
  }
  
  .edge-label {
    pointer-events: none;
  }
  
  /* RFC-067: Integration edge styling */
  .dag-edge.integration .edge-line {
    stroke-dasharray: 8 4;
    stroke-width: 2;
    stroke: var(--info);
  }
  
  .dag-edge.integration.missing .edge-line {
    stroke: var(--error);
    animation: missing-pulse 1s ease-in-out infinite;
  }
  
  .dag-edge.integration.verified .edge-line {
    stroke: var(--success);
    opacity: 0.7;
  }
  
  @keyframes missing-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }
  
  .integration-warning {
    filter: drop-shadow(0 1px 2px rgba(0,0,0,0.3));
    animation: warning-bounce 0.5s ease-in-out infinite;
  }
  
  @keyframes warning-bounce {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-2px); }
  }
  
  .integration-verified {
    filter: drop-shadow(0 1px 2px rgba(0,0,0,0.2));
  }
</style>
