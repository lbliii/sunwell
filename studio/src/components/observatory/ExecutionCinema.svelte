<!--
  ExecutionCinema — Enhanced DAG with cinematic particle effects (RFC-112)
  
  Shows task execution with flowing particles, glowing nodes, and completion celebrations.
  Uses the animation primitives: GlowingNode, ParticleStream, AnimatedPath.
  
  Data contract:
  - Uses existing DagNode[] and DagEdge[] from stores/dag.svelte
-->
<script lang="ts">
  import { fade, fly } from 'svelte/transition';
  import { GlowingNode, ParticleStream } from '../primitives';
  
  interface Props {
    isLive?: boolean;
  }
  
  let { isLive = true }: Props = $props();
  
  // Demo task data with typed status
  type TaskStatus = 'pending' | 'active' | 'complete' | 'failed';
  
  interface DemoTask {
    id: string;
    label: string;
    status: TaskStatus;
    progress: number;
    x: number;
    y: number;
  }
  
  const demoTasks: DemoTask[] = [
    { id: 'models', label: 'models/', status: 'complete', progress: 1, x: 100, y: 100 },
    { id: 'auth', label: 'auth/', status: 'active', progress: 0.7, x: 300, y: 100 },
    { id: 'api', label: 'api/', status: 'pending', progress: 0, x: 500, y: 100 },
    { id: 'tests', label: 'tests/', status: 'pending', progress: 0, x: 300, y: 250 },
  ];
  
  interface DemoEdge {
    from: string;
    to: string;
  }
  
  const demoEdges: DemoEdge[] = [
    { from: 'models', to: 'auth' },
    { from: 'models', to: 'tests' },
    { from: 'auth', to: 'api' },
    { from: 'auth', to: 'tests' },
    { from: 'api', to: 'tests' },
  ];
  
  // Get edge path between two tasks
  function getEdgePath(fromId: string, toId: string): string {
    const from = demoTasks.find(t => t.id === fromId);
    const to = demoTasks.find(t => t.id === toId);
    if (!from || !to) return '';
    return `M ${from.x + 60} ${from.y + 30} L ${to.x - 60} ${to.y + 30}`;
  }
  
  // Check if edge should show particles (from complete, to not complete)
  function shouldShowParticles(fromId: string, toId: string): boolean {
    const from = demoTasks.find(t => t.id === fromId);
    const to = demoTasks.find(t => t.id === toId);
    return from?.status === 'complete' && to?.status !== 'complete';
  }
  
  // Calculate total progress
  const totalProgress = $derived(
    Math.round(demoTasks.reduce((acc, t) => acc + t.progress * 100, 0) / demoTasks.length)
  );
</script>

<div class="execution-cinema" in:fade={{ duration: 300 }}>
  <div class="cinema-header">
    <h2>Execution Cinema</h2>
    <p class="description">Watch tasks flow through the execution DAG</p>
  </div>
  
  <div class="cinema-content">
    <svg viewBox="0 0 700 350" class="dag-svg">
      <!-- Edges with particle streams using primitives -->
      {#each demoEdges as edge}
        {@const from = demoTasks.find(t => t.id === edge.from)}
        {@const to = demoTasks.find(t => t.id === edge.to)}
        {#if from && to}
          <g class="edge-group">
            <!-- Base edge line -->
            <path
              d={getEdgePath(edge.from, edge.to)}
              fill="none"
              stroke={from.status === 'complete' ? 'var(--ui-gold-40)' : 'var(--border-subtle)'}
              stroke-width="2"
              class="edge-line"
            />
            
            <!-- ParticleStream primitive for active data flow -->
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
      {#each demoTasks as task, i}
        <g in:fly={{ y: 30, delay: i * 100, duration: 300 }}>
          <GlowingNode
            x={task.x}
            y={task.y + 30}
            width={120}
            height={60}
            label={task.label}
            status={task.status}
            progress={task.progress}
            celebrate={true}
          />
        </g>
      {/each}
    </svg>
    
    <!-- Live feed -->
    <div class="live-feed">
      <div class="feed-header">
        <span class="feed-indicator" class:active={isLive}></span>
        <span class="feed-label">LIVE</span>
      </div>
      <div class="feed-content">
        <p class="feed-message">auth/middleware.py: Adding OAuth verification...</p>
        <div class="feed-progress">
          <div class="feed-bar" style="width: 70%"></div>
        </div>
      </div>
    </div>
  </div>
  
  <!-- Overall progress bar -->
  <div class="cinema-progress">
    <div class="progress-track">
      <div class="progress-fill" style="width: {totalProgress}%">
        <div class="progress-shimmer"></div>
      </div>
    </div>
    <span class="progress-label">{totalProgress}% complete</span>
  </div>
  
  <div class="cinema-footer">
    <span class="stat">2 parallel</span>
    <span class="separator">•</span>
    <span class="stat">{demoTasks.filter(t => t.status === 'complete').length}/{demoTasks.length} tasks</span>
    <span class="separator">•</span>
    <span class="stat">34s elapsed</span>
    <span class="separator">•</span>
    <span class="stat estimate">~45s remaining</span>
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
    margin: 0;
  }
  
  .cinema-content {
    flex: 1;
    position: relative;
    display: flex;
    justify-content: center;
  }
  
  .dag-svg {
    width: 100%;
    max-width: 700px;
    height: auto;
  }
  
  .edge-line {
    transition: stroke var(--transition-fast);
  }
  
  .live-feed {
    position: absolute;
    bottom: var(--space-4);
    left: 50%;
    transform: translateX(-50%);
    width: 400px;
    background: var(--bg-primary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    overflow: hidden;
  }
  
  .feed-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    background: var(--bg-tertiary);
    border-bottom: 1px solid var(--border-subtle);
  }
  
  .feed-indicator {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--text-tertiary);
  }
  
  .feed-indicator.active {
    background: var(--error);
    animation: pulse-indicator 1s ease-in-out infinite;
  }
  
  @keyframes pulse-indicator {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
  
  .feed-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--error);
    font-weight: 600;
  }
  
  .feed-content {
    padding: var(--space-3);
  }
  
  .feed-message {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-secondary);
    margin: 0 0 var(--space-2);
  }
  
  .feed-progress {
    height: 4px;
    background: var(--bg-tertiary);
    border-radius: 2px;
    overflow: hidden;
  }
  
  .feed-bar {
    height: 100%;
    background: var(--info);
    transition: width 0.5s ease;
  }
  
  .cinema-progress {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    padding: var(--space-4) 0;
  }
  
  .progress-track {
    flex: 1;
    height: 8px;
    background: var(--bg-tertiary);
    border-radius: 4px;
    overflow: hidden;
  }
  
  .progress-fill {
    height: 100%;
    background: var(--gradient-ui-gold);
    border-radius: 4px;
    position: relative;
    transition: width 0.5s ease;
  }
  
  .progress-shimmer {
    position: absolute;
    inset: 0;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
    animation: shimmer 1.5s infinite;
  }
  
  @keyframes shimmer {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
  }
  
  .progress-label {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-gold);
    min-width: 100px;
    text-align: right;
  }
  
  .cinema-footer {
    display: flex;
    justify-content: center;
    gap: var(--space-3);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .separator {
    opacity: 0.4;
  }
  
  .estimate {
    color: var(--text-gold);
  }
</style>
