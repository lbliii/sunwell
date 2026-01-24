<!--
  ResonanceWave — Quality emergence through resonance iterations (RFC-112)
  
  Visualizes how code quality improves through refinement cycles.
  Shows: Wave chart from R0 → RN with quality scores, animated transitions.
  
  Data contract:
  - Consumes real events via observatory store
  - Shows empty state when no data
  - Supports playback controls (scrub, speed, live/replay)
-->
<script lang="ts">
  import { fade, fly } from 'svelte/transition';
  import { spring, tweened } from 'svelte/motion';
  import { cubicOut } from 'svelte/easing';
  import { AnimatedPath } from '../primitives';
  import EmptyState from './EmptyState.svelte';
  import {
    observatory,
    startPlayback,
    pausePlayback,
    resumePlayback,
    stopPlayback,
    scrubToRound,
    setPlaybackSpeed,
    goLive,
    type ResonanceIteration,
  } from '../../stores';
  
  interface Props {
    isLive?: boolean;
  }
  
  let { isLive = true }: Props = $props();
  
  // Use real data only
  const iterations = $derived(observatory.resonanceWave.iterations);
  const hasData = $derived(iterations.length > 0);
  
  const playback = $derived(observatory.playback);
  const isRefining = $derived(observatory.isRefining);
  
  // Current round for display
  const displayRound = $derived(
    playback.mode === 'replay'
      ? playback.currentRound
      : iterations.length - 1
  );
  
  const currentIteration = $derived(
    iterations[Math.min(displayRound, iterations.length - 1)] ?? iterations[0]
  );
  
  // Animated score using spring
  const scoreSpring = spring(1.0, { stiffness: 0.08, damping: 0.4 });
  
  $effect(() => {
    if (currentIteration) {
      scoreSpring.set(currentIteration.score);
    }
  });
  
  // Playback animation loop
  let playbackTimer: ReturnType<typeof setInterval> | null = null;
  
  $effect(() => {
    if (playback.isPlaying && !playback.isPaused) {
      const delay = 1500 / playback.speed;
      playbackTimer = setInterval(() => {
        if (playback.currentRound < iterations.length - 1) {
          scrubToRound(playback.currentRound + 1);
        } else {
          stopPlayback();
        }
      }, delay);
    } else if (playbackTimer) {
      clearInterval(playbackTimer);
      playbackTimer = null;
    }
    
    return () => {
      if (playbackTimer) clearInterval(playbackTimer);
    };
  });
  
  function handlePlayPause() {
    if (!playback.isPlaying) {
      startPlayback();
    } else if (playback.isPaused) {
      resumePlayback();
    } else {
      pausePlayback();
    }
  }
  
  function handleStop() {
    stopPlayback();
  }
  
  function handleLive() {
    goLive();
  }
  
  // SVG dimensions
  const svgWidth = 600;
  const svgHeight = 200;
  const padding = 40;
  
  // Calculate wave path up to current round
  function getWavePath(upToRound: number): string {
    const maxRound = Math.min(upToRound + 1, iterations.length);
    const points = iterations.slice(0, maxRound).map((iter, i) => {
      const x = padding + (i / Math.max(iterations.length - 1, 1)) * (svgWidth - padding * 2);
      const y = svgHeight - padding - ((iter.score / 10) * (svgHeight - padding * 2));
      return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
    });
    return points.join(' ');
  }
  
  // Calculate current point position
  const currentX = $derived(
    padding + (displayRound / Math.max(iterations.length - 1, 1)) * (svgWidth - padding * 2)
  );
  const currentY = $derived(
    svgHeight - padding - ((currentIteration?.score ?? 1) / 10) * (svgHeight - padding * 2)
  );
  
  // Calculate improvement stats
  const initialScore = $derived(iterations[0]?.score ?? 1);
  const finalScore = $derived(iterations[iterations.length - 1]?.score ?? 1);
  const improvementPct = $derived(
    initialScore > 0 ? ((finalScore / initialScore - 1) * 100).toFixed(0) : '0'
  );
</script>

{#if !hasData}
  <EmptyState
    icon="📈"
    title="No refinement data"
    message="Start a goal with resonance enabled to watch quality emerge through iterative refinement."
  />
{:else}
<div class="resonance-wave" in:fade={{ duration: 300 }}>
  <div class="wave-header">
    <h2>Resonance Wave</h2>
    <p class="description">Watch quality emerge through iterative refinement</p>
    
    <!-- Status indicators -->
    <div class="status-badges">
      {#if isRefining}
        <span class="badge live">🔴 Live</span>
      {:else if playback.mode === 'replay'}
        <span class="badge replay">⏪ Replay</span>
      {:else}
        <span class="badge idle">Recorded</span>
      {/if}
      
      {#if playback.speed !== 1}
        <span class="badge speed">{playback.speed}x</span>
      {/if}
    </div>
  </div>
  
  <div class="wave-content">
    <div class="chart-container">
      <svg viewBox="0 0 {svgWidth} {svgHeight}" class="wave-chart">
        <!-- Grid lines -->
        {#each [2, 4, 6, 8, 10] as score}
          {@const y = svgHeight - padding - ((score / 10) * (svgHeight - padding * 2))}
          <line 
            x1={padding} 
            y1={y} 
            x2={svgWidth - padding} 
            y2={y} 
            class="grid-line"
          />
          <text x={padding - 8} y={y + 4} class="axis-label">{score}</text>
        {/each}
        
        <!-- Gradient definition -->
        <defs>
          <linearGradient id="goldGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="var(--ui-gold)" />
            <stop offset="100%" stop-color="var(--radiant-gold)" />
          </linearGradient>
          <filter id="glow">
            <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
        </defs>
        
        <!-- Wave path using AnimatedPath primitive -->
        <AnimatedPath
          d={getWavePath(displayRound)}
          duration={500}
          color="url(#goldGradient)"
          strokeWidth={3}
          glow={true}
          active={true}
        />
        
        <!-- Future path (dimmed) -->
        {#if displayRound < iterations.length - 1}
          <path
            d={getWavePath(iterations.length - 1)}
            fill="none"
            stroke="var(--border-subtle)"
            stroke-width="2"
            stroke-dasharray="4 4"
            opacity="0.3"
          />
        {/if}
        
        <!-- Round markers -->
        {#each iterations as iter, i}
          {@const x = padding + (i / Math.max(iterations.length - 1, 1)) * (svgWidth - padding * 2)}
          {@const y = svgHeight - padding - ((iter.score / 10) * (svgHeight - padding * 2))}
          <circle
            cx={x}
            cy={y}
            r={i === displayRound ? 0 : 4}
            fill={i <= displayRound ? 'var(--ui-gold)' : 'var(--border-subtle)'}
            opacity={i <= displayRound ? 1 : 0.3}
          />
        {/each}
        
        <!-- Current point with glow -->
        <circle
          cx={currentX}
          cy={currentY}
          r="8"
          class="current-point"
          filter="url(#glow)"
        />
        <circle
          cx={currentX}
          cy={currentY}
          r="16"
          class="current-point-ring"
        />
      </svg>
      
      <!-- Round scrubber -->
      <div class="round-scrubber">
        {#each iterations as iter, i}
          <button 
            class="round-marker" 
            class:active={i === displayRound}
            class:passed={i < displayRound}
            onclick={() => scrubToRound(i)}
            title="Round {iter.round}: Score {iter.score.toFixed(1)}"
          >
            R{iter.round}
          </button>
        {/each}
      </div>
    </div>
    
    <div class="details-panel">
      <!-- Score display -->
      <div class="score-display">
        <span class="score-label">Quality Score</span>
        <span class="score-value">
          {$scoreSpring.toFixed(1)}<span class="score-max">/10</span>
        </span>
        {#if displayRound > 0 && currentIteration?.delta}
          <span class="score-delta" in:fly={{ y: -10, duration: 300 }}>
            +{currentIteration.delta.toFixed(1)}
          </span>
        {/if}
      </div>
      
      <!-- Improvements list -->
      <div class="improvements-panel">
        <div class="improvements-header">
          <span class="improvements-title">Round {currentIteration?.round ?? 0} Improvements</span>
        </div>
        <ul class="improvements-list">
          {#if currentIteration?.improvements?.length}
            {#each currentIteration.improvements as improvement, i}
              <li class="improvement-item" in:fly={{ y: 10, delay: i * 50, duration: 200 }}>
                <span class="improvement-icon">✨</span>
                {improvement}
              </li>
            {/each}
          {:else}
            <li class="improvement-item placeholder">Initial state</li>
          {/if}
        </ul>
        {#if currentIteration?.reason}
          <p class="improvement-reason">{currentIteration.reason}</p>
        {/if}
      </div>
      
      <!-- Playback controls -->
      <div class="playback-controls">
        <div class="control-row">
          <button class="control-btn" onclick={handlePlayPause} title={playback.isPlaying ? (playback.isPaused ? 'Resume' : 'Pause') : 'Play'}>
            {#if playback.isPlaying && !playback.isPaused}
              ⏸
            {:else}
              ▶
            {/if}
          </button>
          
          <button class="control-btn" onclick={handleStop} disabled={!playback.isPlaying} title="Stop">
            ⏹
          </button>
          
          <button 
            class="control-btn" 
            class:active={playback.mode === 'live'}
            onclick={handleLive} 
            title="Go Live"
            disabled={!isRefining}
          >
            🔴
          </button>
          
          <div class="speed-controls">
            {#each [0.5, 1, 2] as speed}
              <button 
                class="speed-btn"
                class:active={playback.speed === speed}
                onclick={() => setPlaybackSpeed(speed)}
              >
                {speed}x
              </button>
            {/each}
          </div>
        </div>
        
      </div>
    </div>
  </div>
  
  <div class="wave-footer">
    <span class="model-badge">llama3.2:3b</span>
    <span class="separator">•</span>
    <span class="iterations">{iterations.length} iterations</span>
    <span class="separator">•</span>
    <span class="improvement">+{improvementPct}% improvement</span>
  </div>
</div>
{/if}

<style>
  .resonance-wave {
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: var(--space-6);
  }
  
  .wave-header {
    text-align: center;
    margin-bottom: var(--space-4);
  }
  
  .wave-header h2 {
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
  
  .badge.replay {
    background: var(--ui-gold-15);
    color: var(--text-gold);
  }
  
  @keyframes pulse-opacity {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
  }
  
  .wave-content {
    flex: 1;
    display: grid;
    grid-template-columns: 1.5fr 1fr;
    gap: var(--space-6);
  }
  
  .chart-container {
    display: flex;
    flex-direction: column;
  }
  
  .wave-chart {
    width: 100%;
    height: auto;
    background: var(--bg-primary);
    border-radius: var(--radius-md);
  }
  
  .grid-line {
    stroke: var(--border-subtle);
    stroke-width: 1;
    stroke-dasharray: 4 4;
  }
  
  .axis-label {
    font-family: var(--font-mono);
    font-size: 10px;
    fill: var(--text-tertiary);
    text-anchor: end;
  }
  
  .current-point {
    fill: var(--radiant-gold);
    transition: cx 0.3s ease-out, cy 0.3s ease-out;
  }
  
  .current-point-ring {
    fill: none;
    stroke: var(--radiant-gold);
    stroke-width: 2;
    opacity: 0.3;
    animation: pulse-ring 1.5s ease-out infinite;
  }
  
  @keyframes pulse-ring {
    0% { r: 8; opacity: 0.4; }
    100% { r: 24; opacity: 0; }
  }
  
  .round-scrubber {
    display: flex;
    justify-content: space-between;
    padding: var(--space-3) var(--space-5);
  }
  
  .round-marker {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    background: none;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: var(--space-1) var(--space-2);
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  
  .round-marker:hover {
    border-color: var(--border-default);
    color: var(--text-secondary);
  }
  
  .round-marker.passed {
    border-color: var(--ui-gold-40);
    color: var(--text-gold);
  }
  
  .round-marker.active {
    background: var(--ui-gold-15);
    border-color: var(--ui-gold);
    color: var(--text-gold);
  }
  
  .details-panel {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }
  
  .score-display {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: var(--space-4);
    background: var(--bg-primary);
    border-radius: var(--radius-md);
    border: 1px solid var(--border-subtle);
  }
  
  .score-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }
  
  .score-value {
    font-family: var(--font-serif);
    font-size: var(--text-4xl);
    font-weight: 700;
    color: var(--text-gold);
  }
  
  .score-max {
    font-size: var(--text-xl);
    color: var(--text-tertiary);
  }
  
  .score-delta {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--success);
    margin-top: var(--space-1);
  }
  
  .improvements-panel {
    flex: 1;
    display: flex;
    flex-direction: column;
    background: var(--bg-primary);
    border-radius: var(--radius-md);
    border: 1px solid var(--border-subtle);
    overflow: hidden;
  }
  
  .improvements-header {
    padding: var(--space-2) var(--space-3);
    background: var(--bg-tertiary);
    border-bottom: 1px solid var(--border-subtle);
  }
  
  .improvements-title {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-secondary);
  }
  
  .improvements-list {
    flex: 1;
    margin: 0;
    padding: var(--space-3);
    list-style: none;
    overflow: auto;
  }
  
  .improvement-item {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) 0;
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-secondary);
  }
  
  .improvement-item.placeholder {
    color: var(--text-tertiary);
    font-style: italic;
  }
  
  .improvement-icon {
    font-size: var(--text-xs);
  }
  
  .improvement-reason {
    margin: 0;
    padding: var(--space-2) var(--space-3);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    background: var(--bg-tertiary);
    border-top: 1px solid var(--border-subtle);
  }
  
  .playback-controls {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  
  .control-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  
  .control-btn {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: var(--text-sm);
    background: var(--bg-primary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  
  .control-btn:hover:not(:disabled) {
    border-color: var(--border-default);
    background: var(--bg-secondary);
  }
  
  .control-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  
  .control-btn.active {
    background: var(--ui-gold-15);
    border-color: var(--ui-gold);
  }
  
  .speed-controls {
    display: flex;
    margin-left: auto;
    gap: var(--space-1);
  }
  
  .speed-btn {
    padding: var(--space-1) var(--space-2);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    background: var(--bg-primary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  
  .speed-btn:hover {
    border-color: var(--border-default);
    color: var(--text-secondary);
  }
  
  .speed-btn.active {
    background: var(--ui-gold-15);
    border-color: var(--ui-gold);
    color: var(--text-gold);
  }
  
  .wave-footer {
    display: flex;
    justify-content: center;
    gap: var(--space-3);
    padding-top: var(--space-4);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .model-badge {
    padding: var(--space-1) var(--space-2);
    background: var(--bg-primary);
    border-radius: var(--radius-sm);
  }
  
  .separator {
    opacity: 0.4;
  }
  
  .improvement {
    color: var(--success);
  }
  
  /* Mobile responsive */
  @media (max-width: 768px) {
    .resonance-wave {
      padding: var(--space-4);
    }
    
    .wave-header h2 {
      font-size: var(--text-lg);
    }
    
    .wave-content {
      grid-template-columns: 1fr;
      gap: var(--space-4);
    }
    
    .round-scrubber {
      padding: var(--space-2) var(--space-3);
      flex-wrap: wrap;
      gap: var(--space-1);
    }
    
    .round-marker {
      font-size: 10px;
      padding: var(--space-1);
    }
    
    .score-value {
      font-size: var(--text-3xl);
    }
    
    .control-row {
      flex-wrap: wrap;
    }
    
    .speed-controls {
      width: 100%;
      justify-content: center;
      margin-left: 0;
      margin-top: var(--space-2);
    }
    
    .wave-footer {
      flex-wrap: wrap;
      gap: var(--space-2);
    }
  }
  
  /* Reduced motion preference */
  @media (prefers-reduced-motion: reduce) {
    .badge.live {
      animation: none;
    }
    
    .current-point-ring {
      animation: none;
      opacity: 0.2;
    }
    
    .round-marker,
    .control-btn,
    .speed-btn {
      transition: none;
    }
  }
</style>
