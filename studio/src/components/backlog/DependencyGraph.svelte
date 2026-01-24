<!--
  DependencyGraph — Mini DAG visualization for goal dependencies (RFC-114 Phase 3)
  
  Shows which goals block others with an interactive graph view.
-->
<script lang="ts">
  import type { Goal } from '../../stores/backlog.svelte';
  import { getStatusInfo } from '../../stores/backlog.svelte';

  interface Props {
    goals: Goal[];
    selectedGoalId?: string;
    onSelectGoal?: (goalId: string) => void;
  }

  let { goals, selectedGoalId, onSelectGoal }: Props = $props();

  // Build dependency edges
  interface Edge {
    from: string;
    to: string;
  }

  interface Node {
    id: string;
    title: string;
    status: string;
    x: number;
    y: number;
    level: number;
  }

  // Compute graph layout
  let graphData = $derived.by(() => {
    const nodes: Node[] = [];
    const edges: Edge[] = [];
    const goalMap = new Map(goals.map(g => [g.id, g]));

    // Build edges
    for (const goal of goals) {
      for (const reqId of goal.requires) {
        if (goalMap.has(reqId)) {
          edges.push({ from: reqId, to: goal.id });
        }
      }
    }

    // Calculate levels (topological sort)
    const levels = new Map<string, number>();
    const visited = new Set<string>();

    function getLevel(goalId: string): number {
      if (levels.has(goalId)) return levels.get(goalId)!;
      if (visited.has(goalId)) return 0; // Cycle detection

      visited.add(goalId);
      const goal = goalMap.get(goalId);
      if (!goal || goal.requires.length === 0) {
        levels.set(goalId, 0);
        return 0;
      }

      const maxParentLevel = Math.max(
        ...goal.requires
          .filter(id => goalMap.has(id))
          .map(id => getLevel(id))
      );
      const level = maxParentLevel + 1;
      levels.set(goalId, level);
      return level;
    }

    // Calculate levels for all goals
    for (const goal of goals) {
      getLevel(goal.id);
    }

    // Group nodes by level
    const levelGroups = new Map<number, Goal[]>();
    for (const goal of goals) {
      const level = levels.get(goal.id) || 0;
      if (!levelGroups.has(level)) {
        levelGroups.set(level, []);
      }
      levelGroups.get(level)!.push(goal);
    }

    // Calculate positions
    const nodeWidth = 140;
    const nodeHeight = 50;
    const levelGap = 80;
    const nodeGap = 20;

    const maxLevel = Math.max(...Array.from(levels.values()), 0);

    for (const [level, levelGoals] of levelGroups) {
      const levelX = level * (nodeWidth + levelGap) + 20;
      const totalHeight = levelGoals.length * (nodeHeight + nodeGap) - nodeGap;
      const startY = (200 - totalHeight) / 2;

      levelGoals.forEach((goal, i) => {
        nodes.push({
          id: goal.id,
          title: goal.title.length > 20 ? goal.title.slice(0, 18) + '...' : goal.title,
          status: goal.status,
          x: levelX,
          y: startY + i * (nodeHeight + nodeGap),
          level,
        });
      });
    }

    const width = (maxLevel + 1) * (nodeWidth + levelGap) + 40;
    const height = 200;

    return { nodes, edges, width, height, nodeWidth, nodeHeight };
  });

  function getNodePosition(nodeId: string): { x: number; y: number } | null {
    const node = graphData.nodes.find(n => n.id === nodeId);
    return node ? { x: node.x, y: node.y } : null;
  }

  function handleNodeClick(nodeId: string) {
    onSelectGoal?.(nodeId);
  }

  function getStatusColor(status: string): string {
    const colors: Record<string, string> = {
      pending: 'var(--text-tertiary)',
      blocked: 'var(--warning)',
      claimed: 'var(--accent)',
      executing: 'var(--success)',
      completed: 'var(--success)',
      failed: 'var(--error)',
      skipped: 'var(--text-tertiary)',
    };
    return colors[status] || 'var(--text-tertiary)';
  }
</script>

{#if goals.length === 0}
  <div class="empty-state">
    <span class="empty-icon">🔗</span>
    <span>No dependencies to display</span>
  </div>
{:else if graphData.edges.length === 0}
  <div class="empty-state">
    <span class="empty-icon">✓</span>
    <span>No dependencies — all goals are independent</span>
  </div>
{:else}
  <div class="graph-container">
    <svg 
      width={graphData.width} 
      height={graphData.height}
      viewBox="0 0 {graphData.width} {graphData.height}"
    >
      <!-- Edges -->
      <g class="edges">
        {#each graphData.edges as edge}
          {@const fromPos = getNodePosition(edge.from)}
          {@const toPos = getNodePosition(edge.to)}
          {#if fromPos && toPos}
            <path
              d="M {fromPos.x + graphData.nodeWidth} {fromPos.y + graphData.nodeHeight / 2} 
                 C {fromPos.x + graphData.nodeWidth + 40} {fromPos.y + graphData.nodeHeight / 2},
                   {toPos.x - 40} {toPos.y + graphData.nodeHeight / 2},
                   {toPos.x} {toPos.y + graphData.nodeHeight / 2}"
              class="edge-path"
            />
            <!-- Arrow head -->
            <polygon
              points="{toPos.x},{toPos.y + graphData.nodeHeight / 2} 
                      {toPos.x - 8},{toPos.y + graphData.nodeHeight / 2 - 4} 
                      {toPos.x - 8},{toPos.y + graphData.nodeHeight / 2 + 4}"
              class="edge-arrow"
            />
          {/if}
        {/each}
      </g>

      <!-- Nodes -->
      <g class="nodes">
        {#each graphData.nodes as node}
          <g
            class="node"
            class:selected={selectedGoalId === node.id}
            transform="translate({node.x}, {node.y})"
            onclick={() => handleNodeClick(node.id)}
            role="button"
            tabindex="0"
            onkeydown={(e) => e.key === 'Enter' && handleNodeClick(node.id)}
          >
            <rect
              width={graphData.nodeWidth}
              height={graphData.nodeHeight}
              rx="8"
              class="node-rect"
              style="stroke: {getStatusColor(node.status)}"
            />
            <text
              x={graphData.nodeWidth / 2}
              y={graphData.nodeHeight / 2 - 6}
              class="node-title"
            >
              {node.title}
            </text>
            <text
              x={graphData.nodeWidth / 2}
              y={graphData.nodeHeight / 2 + 10}
              class="node-status"
              style="fill: {getStatusColor(node.status)}"
            >
              {getStatusInfo(node.status as any).emoji} {node.status}
            </text>
          </g>
        {/each}
      </g>
    </svg>
  </div>
{/if}

<style>
  .graph-container {
    overflow-x: auto;
    padding: 16px;
    background: var(--bg-tertiary);
    border-radius: 8px;
  }

  .empty-state {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 24px;
    color: var(--text-tertiary);
    font-size: 13px;
    background: var(--bg-tertiary);
    border-radius: 8px;
  }

  .empty-icon {
    font-size: 16px;
  }

  .edge-path {
    fill: none;
    stroke: var(--border-color);
    stroke-width: 2;
  }

  .edge-arrow {
    fill: var(--border-color);
  }

  .node {
    cursor: pointer;
  }

  .node:focus {
    outline: none;
  }

  .node:focus .node-rect,
  .node:hover .node-rect {
    fill: var(--bg-secondary);
  }

  .node.selected .node-rect {
    fill: var(--bg-secondary);
    stroke-width: 2;
  }

  .node-rect {
    fill: var(--bg-primary);
    stroke-width: 1;
    transition: all 0.15s ease;
  }

  .node-title {
    font-size: 11px;
    font-weight: 500;
    fill: var(--text-primary);
    text-anchor: middle;
    pointer-events: none;
  }

  .node-status {
    font-size: 9px;
    text-anchor: middle;
    pointer-events: none;
  }
</style>
