<!--
  GlowingNode — SVG node with pulse/glow states (RFC-112)
  
  A primitive for Observatory visualizations representing task nodes
  with multiple visual states: pending, active, complete, failed.
  
  Usage:
    <svg viewBox="0 0 500 300">
      <GlowingNode 
        x={100} y={100} 
        status="active"
        label="auth/"
        progress={0.7}
      />
    </svg>
-->
<script lang="ts">
  interface Props {
    /** X position (center) */
    x: number;
    /** Y position (center) */
    y: number;
    /** Node width */
    width?: number;
    /** Node height */
    height?: number;
    /** Display label */
    label: string;
    /** Current status */
    status: 'pending' | 'active' | 'complete' | 'failed';
    /** Progress (0-1) for progress bar, only shown when running */
    progress?: number;
    /** Whether to show completion celebration (motes) */
    celebrate?: boolean;
    /** Corner radius */
    radius?: number;
    /** Optional click handler */
    onclick?: () => void;
    /** Whether node is interactive */
    interactive?: boolean;
  }
  
  let { 
    x, 
    y, 
    width = 120, 
    height = 60, 
    label, 
    status, 
    progress = 0,
    celebrate = true,
    radius = 8,
    onclick,
    interactive = false,
  }: Props = $props();
  
  // Status-based colors
  const statusColors = {
    pending: 'var(--text-tertiary)',
    active: 'var(--info)',
    complete: 'var(--success)',
    failed: 'var(--error)',
  };
  
  const statusColor = $derived(statusColors[status]);
  
  // Status icons
  const statusIcons = {
    pending: '○',
    active: '◐',
    complete: '✓',
    failed: '✕',
  };
  
  const statusIcon = $derived(statusIcons[status]);
  
  // Position calculations
  const nodeX = $derived(x - width / 2);
  const nodeY = $derived(y - height / 2);
  const glowX = $derived(nodeX - 4);
  const glowY = $derived(nodeY - 4);
  const glowWidth = $derived(width + 8);
  const glowHeight = $derived(height + 8);
  
  // Progress bar dimensions
  const progressBarY = $derived(nodeY + height - 12);
  const progressBarWidth = $derived((width - 16) * Math.min(1, Math.max(0, progress)));
  
  // Generate unique IDs for this instance
  const instanceId = Math.random().toString(36).slice(2, 9);
  const glowFilterId = `node-glow-${instanceId}`;
  
  // Motes for celebration
  const motes = [
    { delay: 0, x: -20, size: 3 },
    { delay: 0.2, x: 0, size: 4 },
    { delay: 0.4, x: 20, size: 3 },
  ];
</script>

<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<g 
  class="glowing-node" 
  class:active={status === 'active'} 
  class:complete={status === 'complete'}
  class:interactive
  role={interactive ? 'button' : undefined}
  tabindex={interactive ? 0 : -1}
  onclick={onclick}
  onkeydown={(e) => e.key === 'Enter' && onclick?.()}
>
  <!-- Glow filter definition -->
  <defs>
    <filter id={glowFilterId} x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur in="SourceGraphic" stdDeviation="3" result="blur" />
      <feMerge>
        <feMergeNode in="blur" />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>
  </defs>
  
  <!-- Pulse ring (active only) -->
  {#if status === 'active'}
    <rect
      x={glowX}
      y={glowY}
      width={glowWidth}
      height={glowHeight}
      rx={radius + 4}
      class="pulse-ring"
      fill="none"
      stroke={statusColor}
      stroke-width="2"
    />
  {/if}
  
  <!-- Main node background -->
  <rect
    x={nodeX}
    y={nodeY}
    {width}
    {height}
    rx={radius}
    class="node-bg"
    fill="var(--bg-secondary)"
    stroke={statusColor}
    stroke-width="1.5"
  />
  
  <!-- Progress bar (only when running with progress) -->
  {#if status === 'active' && progress > 0 && progress < 1}
    <rect
      x={nodeX + 8}
      y={progressBarY}
      width={progressBarWidth}
      height="4"
      rx="2"
      class="progress-bar"
      fill={statusColor}
    />
  {/if}
  
  <!-- Label -->
  <text
    {x}
    y={y - 4}
    class="node-label"
    text-anchor="middle"
    dominant-baseline="middle"
    fill="var(--text-primary)"
  >
    {label}
  </text>
  
  <!-- Status indicator -->
  <text
    {x}
    y={y + 14}
    class="node-status"
    text-anchor="middle"
    fill={statusColor}
  >
    {statusIcon} {status}
  </text>
  
  <!-- Celebration motes (complete only) -->
  {#if status === 'complete' && celebrate}
    {#each motes as mote}
      <circle
        cx={x + mote.x}
        cy={nodeY - 10}
        r={mote.size}
        class="mote"
        fill="var(--ui-gold)"
        style:animation-delay="{mote.delay}s"
      />
    {/each}
  {/if}
</g>

<style>
  .glowing-node {
    transition: transform 0.2s ease;
  }
  
  .glowing-node.interactive {
    cursor: pointer;
  }
  
  .glowing-node.interactive:hover {
    transform: scale(1.02);
  }
  
  .glowing-node.interactive:focus-visible {
    outline: none;
  }
  
  .glowing-node.interactive:focus-visible .node-bg {
    stroke-width: 2.5;
  }
  
  .node-bg {
    transition: all 0.2s ease;
  }
  
  .glowing-node.active .node-bg {
    filter: drop-shadow(0 0 8px var(--info));
  }
  
  .glowing-node.complete .node-bg {
    filter: drop-shadow(0 0 8px var(--success));
  }
  
  .pulse-ring {
    animation: pulse-ring 1.5s ease-in-out infinite;
    transform-origin: center;
  }
  
  @keyframes pulse-ring {
    0%, 100% {
      opacity: 0.3;
      transform: scale(1);
    }
    50% {
      opacity: 0.8;
      transform: scale(1.02);
    }
  }
  
  .node-label {
    font-family: var(--font-mono);
    font-size: 12px;
    font-weight: 500;
    pointer-events: none;
  }
  
  .node-status {
    font-family: var(--font-mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    pointer-events: none;
  }
  
  .progress-bar {
    transition: width 0.3s ease;
  }
  
  .mote {
    animation: rise-mote 2s ease-out infinite;
    filter: drop-shadow(0 0 4px var(--ui-gold));
  }
  
  @keyframes rise-mote {
    0% {
      transform: translateY(0);
      opacity: 1;
    }
    100% {
      transform: translateY(-30px);
      opacity: 0;
    }
  }
  
  /* Complete state celebration */
  .glowing-node.complete {
    animation: complete-pop 0.4s ease-out;
  }
  
  @keyframes complete-pop {
    0% { transform: scale(1); }
    50% { transform: scale(1.05); }
    100% { transform: scale(1); }
  }
</style>
