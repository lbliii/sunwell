<!--
  ModelParadox — Quality vs. cost/parameters visualization (RFC-112)
  
  Proves that small models + Sunwell beats big models raw.
  The paradox: 3B + architecture > 20B raw.
  
  Data contract:
  - Consumes real events via observatory.modelParadox
  - Shows empty state when no evaluation data
-->
<script lang="ts">
  import { fade, fly, scale } from 'svelte/transition';
  import { spring } from 'svelte/motion';
  import EmptyState from './EmptyState.svelte';
  import {
    observatory,
    type ParadoxComparison,
  } from '../../stores';
  
  interface Props {
    isLive?: boolean;
  }
  
  let { isLive = true }: Props = $props();
  
  // Use real data only
  const paradoxState = $derived(observatory.modelParadox);
  const comparisons = $derived(paradoxState.comparisons);
  const hasData = $derived(comparisons.length > 0);
  
  // Animation state
  let showSunwell = $state(false);
  let animationPlayed = $state(false);
  
  // Spring values as state (reactive)
  let springValues = $state([
    { raw: 0, sunwell: 0 },
    { raw: 0, sunwell: 0 },
    { raw: 0, sunwell: 0 },
    { raw: 0, sunwell: 0 },
  ]);
  
  // Springs for animation
  const rawSprings = [
    spring(0, { stiffness: 0.03, damping: 0.3 }),
    spring(0, { stiffness: 0.03, damping: 0.3 }),
    spring(0, { stiffness: 0.03, damping: 0.3 }),
    spring(0, { stiffness: 0.03, damping: 0.3 }),
  ];
  
  const sunwellSprings = [
    spring(0, { stiffness: 0.03, damping: 0.3 }),
    spring(0, { stiffness: 0.03, damping: 0.3 }),
    spring(0, { stiffness: 0.03, damping: 0.3 }),
    spring(0, { stiffness: 0.03, damping: 0.3 }),
  ];
  
  // Subscribe to spring updates
  rawSprings.forEach((s, i) => {
    s.subscribe(v => {
      springValues[i] = { ...springValues[i], raw: v };
    });
  });
  
  sunwellSprings.forEach((s, i) => {
    s.subscribe(v => {
      springValues[i] = { ...springValues[i], sunwell: v };
    });
  });
  
  function playAnimation() {
    showSunwell = false;
    animationPlayed = true;
    
    // Reset springs
    rawSprings.forEach(s => s.set(0, { hard: true }));
    sunwellSprings.forEach(s => s.set(0, { hard: true }));
    
    // Animate raw scores first
    setTimeout(() => {
      comparisons.forEach((comp, i) => {
        if (i < rawSprings.length) {
          rawSprings[i].set(comp.rawScore);
        }
      });
    }, 500);
    
    // Show Sunwell activation flash
    setTimeout(() => {
      showSunwell = true;
    }, 2000);
    
    // Animate Sunwell scores
    setTimeout(() => {
      comparisons.forEach((comp, i) => {
        if (i < sunwellSprings.length) {
          sunwellSprings[i].set(comp.sunwellScore);
        }
      });
    }, 2500);
  }
  
  function reset() {
    showSunwell = false;
    animationPlayed = false;
    rawSprings.forEach(s => s.set(0, { hard: true }));
    sunwellSprings.forEach(s => s.set(0, { hard: true }));
  }
  
  // SVG dimensions
  const width = 600;
  const height = 300;
  const padding = { top: 40, right: 100, bottom: 60, left: 60 };
  
  function scoreToY(score: number): number {
    const maxScore = 10;
    return height - padding.bottom - ((score / maxScore) * (height - padding.top - padding.bottom));
  }
  
  // Colors for different models
  const colors = ['#3b82f6', '#22c55e', '#a855f7', '#f97316'];
</script>

{#if !hasData}
  <EmptyState
    icon="⚡"
    title="No evaluation data"
    message="Run evaluations to see the Model Paradox — how small models + Sunwell beat large models raw."
  />
{:else}
<div class="model-paradox" in:fade={{ duration: 300 }}>
  <div class="paradox-header">
    <h2>Model Paradox</h2>
    <p class="thesis">"{paradoxState.thesis}"</p>
    
    <!-- Status badges -->
    <div class="status-badges">
      <span class="badge live">📊 Real Data</span>
      <span class="badge count">{paradoxState.totalRuns} runs</span>
    </div>
  </div>
  
  <div class="paradox-content">
    <svg viewBox="0 0 {width} {height}" class="chart-svg">
      <!-- Grid lines -->
      {#each [2, 4, 6, 8, 10] as score}
        <line 
          x1={padding.left}
          y1={scoreToY(score)}
          x2={width - padding.right}
          y2={scoreToY(score)}
          class="grid-line"
        />
        <text x={padding.left - 10} y={scoreToY(score) + 4} class="y-label">{score}</text>
      {/each}
      
      <!-- Y-axis label -->
      <text 
        x={20} 
        y={height / 2} 
        class="axis-title"
        transform="rotate(-90, 20, {height / 2})"
      >
        Quality Score
      </text>
      
      <!-- X-axis labels -->
      <text x={padding.left + 30} y={height - 20} class="x-label">Raw</text>
      <text x={width - padding.right - 30} y={height - 20} class="x-label">+Sunwell</text>
      
      <!-- Sunwell activation flash -->
      {#if showSunwell}
        <rect 
          x={padding.left} 
          y={padding.top} 
          width={width - padding.left - padding.right}
          height={height - padding.top - padding.bottom}
          class="activation-flash"
          in:fade={{ duration: 300 }}
        />
      {/if}
      
      <!-- Data lines for each comparison -->
      {#each comparisons.slice(0, springValues.length) as comp, i}
        {@const color = colors[i % colors.length]}
        {@const rawY = scoreToY(springValues[i].raw)}
        {@const sunwellY = scoreToY(springValues[i].sunwell)}
        {@const xStart = padding.left + 50}
        {@const xEnd = width - padding.right - 50}
        
        <!-- Raw data point and label -->
        {#if animationPlayed}
          <circle 
            cx={xStart} 
            cy={rawY} 
            r="6" 
            fill={color}
            opacity="0.6"
          />
          <text 
            x={xStart - 10} 
            y={rawY + 4} 
            class="data-label"
            text-anchor="end"
            fill={color}
          >
            {comp.params}: {springValues[i].raw.toFixed(1)}
          </text>
        {/if}
        
        <!-- Connecting line -->
        {#if showSunwell}
          <line
            x1={xStart}
            y1={rawY}
            x2={xEnd}
            y2={sunwellY}
            stroke={color}
            stroke-width="3"
            stroke-linecap="round"
            class="connector-line"
            style="filter: drop-shadow(0 0 4px {color})"
            in:fade={{ duration: 500 }}
          />
          
          <!-- Sunwell data point and label -->
          <circle 
            cx={xEnd} 
            cy={sunwellY} 
            r="8" 
            fill={color}
            style="filter: drop-shadow(0 0 8px {color})"
            in:scale={{ duration: 300 }}
          />
          <text 
            x={xEnd + 15} 
            y={sunwellY + 4} 
            class="data-label sunwell"
            fill={color}
            in:fly={{ x: -10, duration: 300 }}
          >
            {springValues[i].sunwell.toFixed(1)}
          </text>
        {/if}
      {/each}
    </svg>
    
    <!-- Stats cards -->
    <div class="stats-row">
      {#each comparisons.slice(0, 2) as comp, i}
        <div class="stat-card" in:fly={{ y: 20, delay: i * 100, duration: 300 }}>
          <div class="stat-header">
            <span class="stat-model">{comp.model}</span>
            <span class="stat-params">{comp.params} • {comp.cost}</span>
          </div>
          <div class="stat-comparison">
            <div class="stat-value raw">
              <span class="value-label">Raw</span>
              <span class="value-number">{comp.rawScore.toFixed(1)}</span>
            </div>
            <span class="stat-arrow">→</span>
            <div class="stat-value sunwell">
              <span class="value-label">+Sunwell</span>
              <span class="value-number">{comp.sunwellScore.toFixed(1)}</span>
            </div>
            <span class="stat-improvement">+{comp.improvement.toFixed(0)}%</span>
          </div>
        </div>
      {/each}
    </div>
    
    <!-- Summary stats -->
    {#if paradoxState.totalRuns > 0}
      <div class="summary-stats" in:fade={{ duration: 300 }}>
        <div class="summary-item">
          <span class="summary-value">{paradoxState.avgImprovement.toFixed(0)}%</span>
          <span class="summary-label">Avg Improvement</span>
        </div>
        <div class="summary-item">
          <span class="summary-value">{paradoxState.sunwellWins}</span>
          <span class="summary-label">Sunwell Wins</span>
        </div>
        <div class="summary-item">
          <span class="summary-value">{paradoxState.totalRuns}</span>
          <span class="summary-label">Total Runs</span>
        </div>
      </div>
    {/if}
  </div>
  
  <div class="paradox-controls">
    <button class="play-btn" onclick={playAnimation} disabled={animationPlayed && showSunwell}>
      {animationPlayed ? (showSunwell ? '✨ Revealed!' : '⏳ Revealing...') : '▶ Reveal the Paradox'}
    </button>
    {#if animationPlayed}
      <button class="reset-btn" onclick={reset}>
        ↺ Reset
      </button>
    {/if}
  </div>
  
  <div class="paradox-footer">
    <span class="punchline">💡 $0 beats $50 with the right architecture.</span>
  </div>
</div>
{/if}

<style>
  .model-paradox {
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: var(--space-6);
  }
  
  .paradox-header {
    text-align: center;
    margin-bottom: var(--space-4);
  }
  
  .paradox-header h2 {
    font-family: var(--font-serif);
    font-size: var(--text-xl);
    color: var(--text-primary);
    margin: 0 0 var(--space-2);
  }
  
  .thesis {
    font-family: var(--font-serif);
    font-size: var(--text-base);
    font-style: italic;
    color: var(--text-secondary);
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
    background: rgba(var(--success-rgb), 0.15);
    color: var(--success);
  }
  
  .badge.count {
    background: var(--ui-gold-15);
    color: var(--text-gold);
  }
  
  .paradox-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-4);
  }
  
  .chart-svg {
    width: 100%;
    max-width: 600px;
    height: auto;
    background: var(--bg-primary);
    border-radius: var(--radius-md);
  }
  
  .grid-line {
    stroke: var(--border-subtle);
    stroke-width: 1;
    stroke-dasharray: 4 4;
  }
  
  .y-label, .x-label {
    font-family: var(--font-mono);
    font-size: 10px;
    fill: var(--text-tertiary);
    text-anchor: end;
  }
  
  .x-label {
    text-anchor: middle;
  }
  
  .axis-title {
    font-family: var(--font-mono);
    font-size: 11px;
    fill: var(--text-tertiary);
    text-anchor: middle;
  }
  
  .data-label {
    font-family: var(--font-mono);
    font-size: 10px;
  }
  
  .data-label.sunwell {
    font-weight: 600;
  }
  
  .connector-line {
    opacity: 0.8;
  }
  
  .activation-flash {
    fill: var(--ui-gold);
    opacity: 0;
    animation: flash 0.5s ease-out;
  }
  
  @keyframes flash {
    0% { opacity: 0.3; }
    100% { opacity: 0; }
  }
  
  .stats-row {
    display: flex;
    gap: var(--space-4);
    width: 100%;
    max-width: 600px;
  }
  
  .stat-card {
    flex: 1;
    padding: var(--space-4);
    background: var(--bg-primary);
    border-radius: var(--radius-md);
    border: 1px solid var(--border-subtle);
  }
  
  .stat-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: var(--space-3);
    padding-bottom: var(--space-2);
    border-bottom: 1px solid var(--border-subtle);
  }
  
  .stat-model {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .stat-params {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .stat-comparison {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  
  .stat-value {
    display: flex;
    flex-direction: column;
    align-items: center;
  }
  
  .value-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .value-number {
    font-family: var(--font-mono);
    font-size: var(--text-lg);
    font-weight: 600;
  }
  
  .stat-value.raw .value-number {
    color: var(--text-tertiary);
  }
  
  .stat-value.sunwell .value-number {
    color: var(--text-gold);
  }
  
  .stat-arrow {
    color: var(--text-tertiary);
    font-size: var(--text-lg);
  }
  
  .stat-improvement {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--success);
    margin-left: auto;
  }
  
  .summary-stats {
    display: flex;
    gap: var(--space-6);
    padding: var(--space-4);
    background: var(--bg-primary);
    border-radius: var(--radius-md);
    border: 1px solid var(--border-subtle);
  }
  
  .summary-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-1);
  }
  
  .summary-value {
    font-family: var(--font-mono);
    font-size: var(--text-xl);
    font-weight: 700;
    color: var(--text-gold);
  }
  
  .summary-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .paradox-controls {
    display: flex;
    justify-content: center;
    gap: var(--space-3);
    padding: var(--space-4) 0;
  }
  
  .play-btn {
    padding: var(--space-3) var(--space-6);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--bg-primary);
    background: var(--gradient-ui-gold);
    border: none;
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  
  .play-btn:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: var(--glow-gold);
  }
  
  .play-btn:disabled {
    opacity: 0.8;
    cursor: default;
  }
  
  .reset-btn {
    padding: var(--space-2) var(--space-4);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-secondary);
    background: var(--bg-primary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  
  .reset-btn:hover {
    border-color: var(--border-default);
    background: var(--bg-secondary);
  }
  
  .paradox-footer {
    text-align: center;
  }
  
  .punchline {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-gold);
    padding: var(--space-2) var(--space-4);
    background: var(--ui-gold-10);
    border-radius: var(--radius-md);
  }
</style>
