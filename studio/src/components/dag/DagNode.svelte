<!--
  DagNode — Individual node in the DAG visualization (Svelte 5)
  
  RFC-074: Extended with incremental execution status visualization.
-->
<script lang="ts">
  import type { DagNode as DagNodeType } from '$lib/types';
  import { dag, hoverNode, selectNode } from '../../stores/dag.svelte';
  
  interface Props {
    node: DagNodeType;
    isSelected?: boolean;
    isHovered?: boolean;
  }
  
  let { node, isSelected = false, isHovered = false }: Props = $props();
  
  let isCritical = $derived(dag.criticalPath.has(node.id));
  let isBottleneck = $derived(dag.bottlenecks.has(node.id));
  let willUnblock = $derived(dag.wouldUnblock.some(n => n.id === node.id));
  
  let statusClass = $derived(`status-${node.status}`);
  let sourceIcon = $derived(node.source === 'ai' ? '◈' : node.source === 'human' ? '◉' : '⊶');
  
  // RFC-067: Task type styling
  let taskType = $derived(node.taskType ?? 'create');
  let isWireTask = $derived(taskType === 'wire');
  let isVerifyTask = $derived(taskType === 'verify');
  let taskTypeBadge = $derived(
    isWireTask ? { icon: '⬌', label: 'Wire', color: 'var(--info)' } :
    isVerifyTask ? { icon: '✓', label: 'Verify', color: 'var(--success)' } :
    taskType === 'refactor' ? { icon: '↻', label: 'Refactor', color: 'var(--warning)' } :
    null
  );
  
  // RFC-074: Incremental execution status
  let canSkip = $derived(dag.skipSet.has(node.id));
  let willExecute = $derived(dag.executeSet.has(node.id));
  let hasIncrementalPlan = $derived(dag.incrementalPlan !== null);
  let incrementalStatus = $derived(dag.getNodeIncrementalStatus(node.id));
  
  // Format relative time (e.g., "2h ago")
  function formatRelativeTime(isoString?: string): string {
    if (!isoString) return '';
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  }
  
  function handleClick() { selectNode(isSelected ? null : node.id); }
  function handleMouseEnter() { hoverNode(node.id); }
  function handleMouseLeave() { hoverNode(null); }
  function handleKeydown(e: KeyboardEvent) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleClick(); } }
  function formatProgress(progress: number): string { const filled = Math.round(progress / 10); return '█'.repeat(filled) + '░'.repeat(10 - filled); }
</script>

<g 
  class="dag-node {statusClass}"
  class:selected={isSelected}
  class:hovered={isHovered}
  class:critical={isCritical}
  class:bottleneck={isBottleneck}
  class:will-unblock={willUnblock}
  class:wire-task={isWireTask}
  class:verify-task={isVerifyTask}
  class:can-skip={canSkip && hasIncrementalPlan}
  class:will-execute={willExecute && hasIncrementalPlan}
  transform="translate({(node.x ?? 0) - (node.width ?? 180) / 2}, {(node.y ?? 0) - (node.height ?? 80) / 2})"
  onclick={handleClick}
  onmouseenter={handleMouseEnter}
  onmouseleave={handleMouseLeave}
  onkeydown={handleKeydown}
  role="button"
  tabindex="0"
  aria-pressed={isSelected}
  aria-label="{node.title} - {node.status}"
>
  <rect class="node-bg" width={node.width ?? 180} height={node.height ?? 80} rx="8" ry="8" />
  <rect class="status-indicator" x="0" y="8" width="3" height={(node.height ?? 80) - 16} rx="1.5" />
  
  <foreignObject x="12" y="8" width={(node.width ?? 180) - 24} height={(node.height ?? 80) - 16}>
    <div class="node-content">
      <div class="node-header">
        <span class="source-icon">{sourceIcon}</span>
        <span class="node-title">{node.title}</span>
      </div>
      
      {#if node.status === 'running'}
        <div class="node-progress">
          <span class="progress-bar">{formatProgress(node.progress)}</span>
          <span class="progress-percent">{node.progress}%</span>
        </div>
        {#if node.currentAction}<div class="current-action">{node.currentAction}</div>{/if}
      {:else if hasIncrementalPlan && canSkip}
        <!-- RFC-074: Incremental skip status -->
        <div class="node-status skip">● skip</div>
        {#if incrementalStatus?.lastExecutedAt}
          <div class="incremental-meta">{formatRelativeTime(incrementalStatus.lastExecutedAt)}</div>
        {/if}
      {:else if hasIncrementalPlan && willExecute}
        <!-- RFC-074: Incremental execute status -->
        <div class="node-status execute">○ exec</div>
        <div class="incremental-meta">changed</div>
      {:else if node.status === 'complete'}<div class="node-status complete">◆ Complete</div>
      {:else if node.status === 'ready'}<div class="node-status ready">▸ Ready</div>
      {:else if node.status === 'blocked'}<div class="node-status blocked">◐ Blocked</div>
      {:else if node.status === 'failed'}<div class="node-status failed">⊗ Failed</div>
      {:else}<div class="node-status pending">◌ Pending</div>
      {/if}
      
      <div class="node-meta">
        <span class="effort">{node.effort}</span>
        {#if node.dependsOn.length > 0}<span class="deps">⊶ {node.dependsOn.length}</span>{/if}
      </div>
    </div>
  </foreignObject>
  
  {#if isBottleneck}
    <g class="bottleneck-badge" transform="translate({(node.width ?? 180) - 20}, -8)">
      <circle r="10" fill="var(--warning)" />
      <text x="0" y="4" text-anchor="middle" font-size="12">▲</text>
    </g>
  {/if}
  
  <!-- RFC-074: Skip badge for cached nodes -->
  {#if hasIncrementalPlan && canSkip}
    <g class="skip-badge" transform="translate({(node.width ?? 180) - 28}, -8)">
      <rect x="-12" y="-10" width="24" height="16" rx="8" fill="var(--success)" opacity="0.9" />
      <text x="0" y="2" text-anchor="middle" font-size="9" font-weight="600" fill="var(--bg-primary)">●</text>
    </g>
  {/if}
  
  <!-- RFC-067: Task type badge for wire/verify/refactor tasks -->
  {#if taskTypeBadge}
    <g class="task-type-badge" transform="translate(8, -8)">
      <rect x="-6" y="-10" width="36" height="16" rx="4" fill={taskTypeBadge.color} opacity="0.9" />
      <text x="12" y="2" text-anchor="middle" font-size="9" font-weight="600" fill="var(--bg-primary)">{taskTypeBadge.label}</text>
    </g>
  {/if}
</g>

<style>
  .dag-node { cursor: pointer; transition: transform 0.15s ease; }
  .dag-node:hover { transform: translate(var(--x), var(--y)) scale(1.02); }
  .node-bg { fill: var(--bg-secondary); stroke: var(--border-color); stroke-width: 1; transition: all 0.15s ease; }
  .dag-node:hover .node-bg, .dag-node.hovered .node-bg { fill: var(--bg-tertiary); stroke: var(--text-tertiary); }
  .dag-node.selected .node-bg { stroke: var(--accent); stroke-width: 2; }
  .dag-node.will-unblock .node-bg { stroke: var(--success); stroke-width: 2; stroke-dasharray: 4 2; }
  .status-indicator { fill: var(--text-tertiary); transition: fill 0.15s ease; }
  .status-complete .status-indicator { fill: var(--success); }
  .status-running .status-indicator { fill: var(--info); animation: pulse 1.5s ease-in-out infinite; }
  .status-ready .status-indicator { fill: var(--warning); }
  .status-blocked .status-indicator { fill: var(--text-tertiary); }
  .status-failed .status-indicator { fill: var(--error); }
  .status-pending .status-indicator { fill: var(--accent-muted); }
  .dag-node.critical .node-bg { stroke: var(--warning); stroke-width: 1.5; }
  @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
  .node-content { display: flex; flex-direction: column; gap: 4px; font-family: var(--font-mono); font-size: 11px; color: var(--text-primary); height: 100%; overflow: hidden; }
  .node-header { display: flex; align-items: center; gap: 6px; }
  .source-icon { font-size: 12px; }
  .node-title { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1; }
  .node-progress { display: flex; align-items: center; gap: 6px; color: var(--info); }
  .progress-bar { font-size: 8px; letter-spacing: -1px; }
  .progress-percent { font-size: 10px; font-weight: 500; }
  .current-action { font-size: 9px; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .node-status { font-size: 10px; font-weight: 500; }
  .node-status.complete { color: var(--success); }
  .node-status.ready { color: var(--warning); }
  .node-status.blocked { color: var(--text-tertiary); }
  .node-status.failed { color: var(--error); }
  .node-status.pending { color: var(--text-tertiary); }
  .node-meta { display: flex; gap: 8px; color: var(--text-tertiary); font-size: 9px; margin-top: auto; }
  .bottleneck-badge { filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3)); }
  .bottleneck-badge text { fill: var(--text-inverse); }
  
  /* RFC-067: Wire task styling */
  .dag-node.wire-task .node-bg { stroke-dasharray: 4 2; stroke: var(--info); }
  .dag-node.wire-task .status-indicator { fill: var(--info); }
  
  /* RFC-067: Verify task styling */
  .dag-node.verify-task .node-bg { stroke-dasharray: 2 2; stroke: var(--success); }
  .dag-node.verify-task .status-indicator { fill: var(--success); }
  
  .task-type-badge { filter: drop-shadow(0 1px 2px rgba(0,0,0,0.2)); }
  
  /* RFC-074: Incremental execution styling */
  .dag-node.can-skip .node-bg { stroke: var(--success); stroke-width: 1.5; }
  .dag-node.can-skip .status-indicator { fill: var(--success); }
  .dag-node.will-execute .node-bg { stroke: var(--warning); stroke-width: 1.5; stroke-dasharray: 3 3; }
  .dag-node.will-execute .status-indicator { fill: var(--warning); }
  
  .node-status.skip { color: var(--success); }
  .node-status.execute { color: var(--warning); }
  .incremental-meta { font-size: 9px; color: var(--text-tertiary); }
  
  .skip-badge { filter: drop-shadow(0 1px 2px rgba(0,0,0,0.2)); }
</style>
