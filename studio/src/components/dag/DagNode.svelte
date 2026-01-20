<!--
  DagNode — Individual node in the DAG visualization
  
  Shows status, progress, and responds to hover/click.
-->
<script lang="ts">
  import type { DagNode } from '$lib/types';
  import { hoverNode, selectNode, criticalPath, bottlenecks, wouldUnblock } from '../../stores/dag';
  
  export let node: DagNode;
  export let isSelected = false;
  export let isHovered = false;
  
  $: isCritical = $criticalPath.has(node.id);
  $: isBottleneck = $bottlenecks.has(node.id);
  $: willUnblock = $wouldUnblock.some(n => n.id === node.id);
  
  $: statusClass = `status-${node.status}`;
  $: sourceIcon = node.source === 'ai' ? '🤖' : node.source === 'human' ? '👤' : '🔗';
  
  function handleClick() {
    selectNode(isSelected ? null : node.id);
  }
  
  function handleMouseEnter() {
    hoverNode(node.id);
  }
  
  function handleMouseLeave() {
    hoverNode(null);
  }
  
  function formatProgress(progress: number): string {
    const filled = Math.round(progress / 10);
    const empty = 10 - filled;
    return '█'.repeat(filled) + '░'.repeat(empty);
  }
</script>

<g 
  class="dag-node {statusClass}"
  class:selected={isSelected}
  class:hovered={isHovered}
  class:critical={isCritical}
  class:bottleneck={isBottleneck}
  class:will-unblock={willUnblock}
  transform="translate({(node.x ?? 0) - (node.width ?? 180) / 2}, {(node.y ?? 0) - (node.height ?? 80) / 2})"
  on:click={handleClick}
  on:mouseenter={handleMouseEnter}
  on:mouseleave={handleMouseLeave}
  role="button"
  tabindex="0"
  on:keydown={(e) => e.key === 'Enter' && handleClick()}
>
  <!-- Background -->
  <rect 
    class="node-bg"
    width={node.width ?? 180}
    height={node.height ?? 80}
    rx="8"
    ry="8"
  />
  
  <!-- Status indicator (left border) -->
  <rect
    class="status-indicator"
    x="0"
    y="8"
    width="3"
    height={(node.height ?? 80) - 16}
    rx="1.5"
  />
  
  <!-- Content -->
  <foreignObject 
    x="12" 
    y="8" 
    width={(node.width ?? 180) - 24}
    height={(node.height ?? 80) - 16}
  >
    <div class="node-content">
      <!-- Header -->
      <div class="node-header">
        <span class="source-icon">{sourceIcon}</span>
        <span class="node-title">{node.title}</span>
      </div>
      
      <!-- Progress or Status -->
      {#if node.status === 'running'}
        <div class="node-progress">
          <span class="progress-bar">{formatProgress(node.progress)}</span>
          <span class="progress-percent">{node.progress}%</span>
        </div>
        {#if node.currentAction}
          <div class="current-action">{node.currentAction}</div>
        {/if}
      {:else if node.status === 'complete'}
        <div class="node-status complete">✓ Complete</div>
      {:else if node.status === 'ready'}
        <div class="node-status ready">▸ Ready</div>
      {:else if node.status === 'blocked'}
        <div class="node-status blocked">⏸ Blocked</div>
      {:else if node.status === 'failed'}
        <div class="node-status failed">✗ Failed</div>
      {:else}
        <div class="node-status pending">○ Pending</div>
      {/if}
      
      <!-- Metadata row -->
      <div class="node-meta">
        <span class="effort">{node.effort}</span>
        {#if node.dependsOn.length > 0}
          <span class="deps">🔗 {node.dependsOn.length}</span>
        {/if}
      </div>
    </div>
  </foreignObject>
  
  <!-- Bottleneck warning -->
  {#if isBottleneck}
    <g class="bottleneck-badge" transform="translate({(node.width ?? 180) - 20}, -8)">
      <circle r="10" fill="var(--warning)" />
      <text x="0" y="4" text-anchor="middle" font-size="12">⚠</text>
    </g>
  {/if}
</g>

<style>
  .dag-node {
    cursor: pointer;
    transition: transform 0.15s ease;
  }
  
  .dag-node:hover {
    transform: translate(var(--x), var(--y)) scale(1.02);
  }
  
  .node-bg {
    fill: var(--bg-secondary);
    stroke: var(--border-color);
    stroke-width: 1;
    transition: all 0.15s ease;
  }
  
  .dag-node:hover .node-bg,
  .dag-node.hovered .node-bg {
    fill: var(--bg-tertiary);
    stroke: var(--text-tertiary);
  }
  
  .dag-node.selected .node-bg {
    stroke: var(--accent);
    stroke-width: 2;
  }
  
  .dag-node.will-unblock .node-bg {
    stroke: var(--success);
    stroke-width: 2;
    stroke-dasharray: 4 2;
  }
  
  /* Status indicator colors */
  .status-indicator {
    fill: var(--text-tertiary);
    transition: fill 0.15s ease;
  }
  
  .status-complete .status-indicator { fill: var(--success); }
  .status-running .status-indicator { 
    fill: var(--info);
    animation: pulse 1.5s ease-in-out infinite;
  }
  .status-ready .status-indicator { fill: var(--warning); }
  .status-blocked .status-indicator { fill: var(--text-tertiary); }
  .status-failed .status-indicator { fill: var(--error); }
  .status-pending .status-indicator { fill: var(--accent-muted); }
  
  /* Critical path highlight */
  .dag-node.critical .node-bg {
    stroke: var(--warning);
    stroke-width: 1.5;
  }
  
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
  
  /* Content styles */
  .node-content {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-primary);
    height: 100%;
    overflow: hidden;
  }
  
  .node-header {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  
  .source-icon {
    font-size: 12px;
  }
  
  .node-title {
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex: 1;
  }
  
  .node-progress {
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--info);
  }
  
  .progress-bar {
    font-size: 8px;
    letter-spacing: -1px;
  }
  
  .progress-percent {
    font-size: 10px;
    font-weight: 500;
  }
  
  .current-action {
    font-size: 9px;
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  .node-status {
    font-size: 10px;
    font-weight: 500;
  }
  
  .node-status.complete { color: var(--success); }
  .node-status.ready { color: var(--warning); }
  .node-status.blocked { color: var(--text-tertiary); }
  .node-status.failed { color: var(--error); }
  .node-status.pending { color: var(--text-tertiary); }
  
  .node-meta {
    display: flex;
    gap: 8px;
    color: var(--text-tertiary);
    font-size: 9px;
    margin-top: auto;
  }
  
  .bottleneck-badge {
    filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));
  }
  
  .bottleneck-badge text {
    fill: var(--text-inverse);
  }
</style>
