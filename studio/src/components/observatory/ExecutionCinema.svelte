<!--
  ExecutionCinema — Enhanced DAG with cinematic particle effects (RFC-112)
  
  Shows task execution with flowing particles, glowing nodes, and completion celebrations.
  Uses animation primitives: GlowingNode, ParticleStream.
  
  Data contract:
  - Consumes real events via observatory.executionCinema
  - Falls back to demo data when no live execution
-->
<script lang="ts">
  import { fade, fly } from 'svelte/transition';
  import { GlowingNode, ParticleStream } from '../primitives';
  import {
    observatory,
    DEMO_CINEMA_TASKS,
    type CinemaTask,
  } from '../../stores';
  
  interface Props {
    isLive?: boolean;
  }
  
  let { isLive = true }: Props = $props();
  
  // Use real data if available, otherwise demo
  const cinemaState = $derived(observatory.executionCinema);
  const tasks = $derived(
    cinemaState.tasks.length > 0
      ? cinemaState.tasks
      : DEMO_CINEMA_TASKS
  );
  const isExecuting = $derived(observatory.isExecuting);
  
  // Layout: position tasks in a grid/flow
  interface TaskPosition {
    id: string;
    x: number;
    y: number;
  }
  
  const taskPositions = $derived<TaskPosition[]>(
    tasks.map((task, i) => ({
      id: task.id,
      x: 100 + (i % 3) * 200,
      y: 100 + Math.floor(i / 3) * 150,
    }))
  );
  
  // Define edges between tasks (simple linear flow for demo)
  interface TaskEdge {
    from: string;
    to: string;
  }
  
  const edges = $derived.by(() => {
    const result: TaskEdge[] = [];
    for (let i = 0; i < tasks.length - 1; i++) {
      result.push({ from: tasks[i].id, to: tasks[i + 1].id });
    }
    return result;
  });
  
  // Get task by ID
  function getTask(id: string): CinemaTask | undefined {
    return tasks.find(t => t.id === id);
  }
  
  // Get position by ID
  function getPosition(id: string): TaskPosition | undefined {
    return taskPositions.find(p => p.id === id);
  }
  
  // Generate edge path
  function getEdgePath(fromId: string, toId: string): string {
    const from = getPosition(fromId);
    const to = getPosition(toId);
    if (!from || !to) return '';
    return `M ${from.x + 60} ${from.y + 30} L ${to.x - 60} ${to.y + 30}`;
  }
  
  // Check if edge should show particles
  function shouldShowParticles(fromId: string, toId: string): boolean {
    const from = getTask(fromId);
    const to = getTask(toId);
    return from?.status === 'complete' && to?.status !== 'complete';
  }
  
  // Calculate overall progress
  const progress = $derived(
    tasks.length > 0
      ? Math.round((tasks.filter(t => t.status === 'complete').length / tasks.length) * 100)
      : 0
  );
  
  // Live feed messages
  const liveFeed = $derived.by(() => {
    const messages: string[] = [];
    const activeTask = tasks.find(t => t.status === 'active');
    if (activeTask) {
      messages.push(`Working on: ${activeTask.label}`);
      messages.push(`Progress: ${Math.round(activeTask.progress * 100)}%`);
    }
    const completed = tasks.filter(t => t.status === 'complete').length;
    if (completed > 0) {
      messages.push(`Completed: ${completed}/${tasks.length} tasks`);
    }
    return messages;
  });
</script>

<div class="execution-cinema" in:fade={{ duration: 300 }}>
  <div class="cinema-header">
    <h2>Execution Cinema</h2>
    <p class="description">Watch tasks flow through the execution pipeline</p>
    
    <!-- Status badges -->
    <div class="status-badges">
      {#if isExecuting}
        <span class="badge live">🔴 Executing</span>
      {:else if progress === 100}
        <span class="badge complete">✅ Complete</span>
      {:else}
        <span class="badge idle">Demo</span>
      {/if}
      <span class="badge progress">{progress}%</span>
    </div>
  </div>
  
  <div class="cinema-content">
    <svg viewBox="0 0 700 350" class="dag-svg">
      <defs>
        <filter id="edgeGlow">
          <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
          <feMerge>
            <feMergeNode in="coloredBlur"/>
            <feMergeNode in="SourceGraphic"/>
          </feMerge>
        </filter>
      </defs>
      
      <!-- Edges with particle streams -->
      {#each edges as edge}
        {@const from = getPosition(edge.from)}
        {@const to = getPosition(edge.to)}
        {@const fromTask = getTask(edge.from)}
        {#if from && to}
          <g class="edge-group">
            <!-- Base edge line -->
            <path
              d={getEdgePath(edge.from, edge.to)}
              fill="none"
              stroke={fromTask?.status === 'complete' ? 'var(--ui-gold-40)' : 'var(--border-subtle)'}
              stroke-width="2"
              class="edge-line"
            />
            
            <!-- ParticleStream for active data flow -->
            <ParticleStream
              path={getEdgePath(edge.from, edge.to)}
              count={6}
              speed={1500}
              active={shouldShowParticles(edge.from, edge.to)}
              color="var(--ui-gold)"
              minSize={3}
              maxSize={5}
              glow={true}
            />
          </g>
        {/if}
      {/each}
      
      <!-- Task nodes using GlowingNode primitive -->
      {#each tasks as task, i}
        {@const pos = taskPositions[i]}
        {#if pos}
          <g in:fly={{ y: 30, delay: i * 100, duration: 300 }}>
            <GlowingNode
              x={pos.x}
              y={pos.y + 30}
              width={120}
              height={60}
              label={task.label}
              status={task.status}
              progress={task.progress}
              celebrate={true}
            />
          </g>
        {/if}
      {/each}
    </svg>
    
    <!-- Live feed panel -->
    <div class="live-feed">
      <div class="feed-header">
        <span class="feed-title">Live Feed</span>
        {#if isExecuting}
          <span class="feed-indicator"></span>
        {/if}
      </div>
      <ul class="feed-messages">
        {#each liveFeed as message, i}
          <li class="feed-message" in:fly={{ y: 10, delay: i * 50, duration: 200 }}>
            {message}
          </li>
        {:else}
          <li class="feed-message placeholder">Waiting for execution...</li>
        {/each}
      </ul>
      
      <!-- Task status summary -->
      <div class="task-summary">
        <div class="summary-item">
          <span class="summary-count complete">{tasks.filter(t => t.status === 'complete').length}</span>
          <span class="summary-label">Complete</span>
        </div>
        <div class="summary-item">
          <span class="summary-count active">{tasks.filter(t => t.status === 'active').length}</span>
          <span class="summary-label">Active</span>
        </div>
        <div class="summary-item">
          <span class="summary-count pending">{tasks.filter(t => t.status === 'pending').length}</span>
          <span class="summary-label">Pending</span>
        </div>
        <div class="summary-item">
          <span class="summary-count failed">{tasks.filter(t => t.status === 'failed').length}</span>
          <span class="summary-label">Failed</span>
        </div>
      </div>
    </div>
  </div>
  
  <div class="cinema-footer">
    <span class="task-badge">{tasks.length} tasks</span>
    <span class="separator">•</span>
    <span class="progress-text">{progress}% complete</span>
    {#if isExecuting}
      <span class="separator">•</span>
      <span class="executing-badge">⚡ Executing</span>
    {/if}
  </div>
</div>

<style>
  .execution-cinema {
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: var(--space-6);
  }
  
  .cinema-header {
    text-align: center;
    margin-bottom: var(--space-4);
  }
  
  .cinema-header h2 {
    font-family: var(--font-serif);
    font-size: var(--text-xl);
    color: var(--text-primary);
    margin: 0 0 var(--space-2);
  }
  
  .description {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-tertiary);
    margin: 0 0 var(--space-2);
  }
  
  .status-badges {
    display: flex;
    justify-content: center;
    gap: var(--space-2);
  }
  
  .badge {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    background: var(--bg-tertiary);
    color: var(--text-secondary);
  }
  
  .badge.live {
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
    animation: pulse-opacity 1.5s ease-in-out infinite;
  }
  
  .badge.complete {
    background: rgba(var(--success-rgb), 0.15);
    color: var(--success);
  }
  
  .badge.progress {
    background: var(--ui-gold-15);
    color: var(--text-gold);
  }
  
  @keyframes pulse-opacity {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
  }
  
  .cinema-content {
    flex: 1;
    display: grid;
    grid-template-columns: 1.5fr 1fr;
    gap: var(--space-4);
  }
  
  .dag-svg {
    width: 100%;
    height: auto;
    background: var(--bg-primary);
    border-radius: var(--radius-md);
    border: 1px solid var(--border-subtle);
  }
  
  .edge-line {
    transition: stroke var(--transition-fast);
  }
  
  .live-feed {
    display: flex;
    flex-direction: column;
    background: var(--bg-primary);
    border-radius: var(--radius-md);
    border: 1px solid var(--border-subtle);
    overflow: hidden;
  }
  
  .feed-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-3);
    background: var(--bg-tertiary);
    border-bottom: 1px solid var(--border-subtle);
  }
  
  .feed-title {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-secondary);
  }
  
  .feed-indicator {
    width: 8px;
    height: 8px;
    background: #ef4444;
    border-radius: 50%;
    animation: pulse-scale 1s ease-in-out infinite;
  }
  
  @keyframes pulse-scale {
    0%, 100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.2); opacity: 0.7; }
  }
  
  .feed-messages {
    flex: 1;
    margin: 0;
    padding: var(--space-3);
    list-style: none;
    overflow: auto;
  }
  
  .feed-message {
    padding: var(--space-2) 0;
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-secondary);
    border-bottom: 1px solid var(--border-subtle);
  }
  
  .feed-message:last-child {
    border-bottom: none;
  }
  
  .feed-message.placeholder {
    color: var(--text-tertiary);
    font-style: italic;
  }
  
  .task-summary {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: var(--space-2);
    padding: var(--space-3);
    background: var(--bg-tertiary);
    border-top: 1px solid var(--border-subtle);
  }
  
  .summary-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-1);
  }
  
  .summary-count {
    font-family: var(--font-mono);
    font-size: var(--text-lg);
    font-weight: 700;
  }
  
  .summary-count.complete { color: var(--success); }
  .summary-count.active { color: var(--info); }
  .summary-count.pending { color: var(--text-tertiary); }
  .summary-count.failed { color: var(--error); }
  
  .summary-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  
  .cinema-footer {
    display: flex;
    justify-content: center;
    gap: var(--space-3);
    padding-top: var(--space-4);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .task-badge {
    padding: var(--space-1) var(--space-2);
    background: var(--bg-primary);
    border-radius: var(--radius-sm);
  }
  
  .separator {
    opacity: 0.4;
  }
  
  .progress-text {
    color: var(--text-gold);
  }
  
  .executing-badge {
    color: var(--info);
    animation: pulse-opacity 1s ease-in-out infinite;
  }
</style>
