<!--
  PrismFracture — Multi-perspective synthesis visualization (RFC-112)
  
  Shows a single prompt refracting into multiple perspectives (harmonic candidates),
  then converging into the final output. Wired to real plan_candidate events.
  
  Data contract:
  - Consumes real events via observatory.prismFracture
  - Shows empty state when no data
  - Supports animation playback
-->
<script lang="ts">
  import { onDestroy } from 'svelte';
  import { fade, fly, scale } from 'svelte/transition';
  import { AnimatedPath } from '../primitives';
  import EmptyState from './EmptyState.svelte';
  import {
    observatory,
    type PrismCandidate,
  } from '../../stores';
  
  interface Props {
    isLive?: boolean;
  }
  
  let { isLive = true }: Props = $props();
  
  // Use real data only
  const prismState = $derived(observatory.prismFracture);
  const candidates = $derived(prismState.candidates);
  const winner = $derived(prismState.winner);
  const isPrismActive = $derived(observatory.isPrismActive);
  const hasData = $derived(candidates.length > 0);
  
  // Animation state
  type AnimPhase = 'ready' | 'refracting' | 'scoring' | 'converging' | 'complete';
  let phase = $state<AnimPhase>('ready');
  let visibleCandidates = $state<number[]>([]);
  let scoredCandidates = $state<number[]>([]);
  
  // O(1) lookup sets for template (avoids .includes() in each iteration)
  const visibleCandidatesSet = $derived(new Set(visibleCandidates));
  const scoredCandidatesSet = $derived(new Set(scoredCandidates));
  
  // Track animation timeouts for cleanup
  let animationTimeouts: ReturnType<typeof setTimeout>[] = [];
  
  // Sync phase with live data
  $effect(() => {
    if (isPrismActive) {
      if (prismState.phase === 'generating') {
        phase = 'refracting';
        // Show candidates as they arrive
        visibleCandidates = candidates.map((_, i) => i);
      } else if (prismState.phase === 'scoring') {
        phase = 'scoring';
        scoredCandidates = candidates.filter(c => c.score !== undefined).map((_, i) => i);
      } else if (prismState.phase === 'complete') {
        phase = 'complete';
        visibleCandidates = candidates.map((_, i) => i);
        scoredCandidates = candidates.map((_, i) => i);
      }
    }
  });
  
  function clearAnimationTimeouts() {
    animationTimeouts.forEach(clearTimeout);
    animationTimeouts = [];
  }

  function playAnimation() {
    clearAnimationTimeouts();
    phase = 'ready';
    visibleCandidates = [];
    scoredCandidates = [];
    
    animationTimeouts.push(setTimeout(() => {
      phase = 'refracting';
      // Stagger candidate appearances
      candidates.forEach((_, i) => {
        animationTimeouts.push(setTimeout(() => {
          visibleCandidates = [...visibleCandidates, i];
        }, i * 300));
      });
    }, 500));
    
    animationTimeouts.push(setTimeout(() => {
      phase = 'scoring';
      // Stagger score reveals
      candidates.forEach((_, i) => {
        animationTimeouts.push(setTimeout(() => {
          scoredCandidates = [...scoredCandidates, i];
        }, i * 200));
      });
    }, 2500));
    
    animationTimeouts.push(setTimeout(() => {
      phase = 'converging';
    }, 4000));
    
    animationTimeouts.push(setTimeout(() => {
      phase = 'complete';
    }, 5000));
  }
  
  function reset() {
    clearAnimationTimeouts();
    phase = 'ready';
    visibleCandidates = [];
    scoredCandidates = [];
  }
  
  // Cleanup on destroy
  onDestroy(clearAnimationTimeouts);
  
  // Get persona label from variance config
  function getPersona(candidate: PrismCandidate): string {
    return candidate.varianceConfig?.promptStyle ?? `variant-${candidate.index}`;
  }
  
  // Prism geometry
  const svgWidth = 700;
  const svgHeight = 400;
  const prismPath = "M 250 80 L 350 200 L 150 200 Z";
</script>

{#if !hasData}
  <EmptyState
    icon="🔮"
    title="No planning data"
    message="Run a goal with harmonic planning to see how Sunwell synthesizes multiple perspectives."
  />
{:else}
<div class="prism-fracture" in:fade={{ duration: 300 }}>
  <div class="prism-header">
    <h2>Prism Fracture</h2>
    <p class="description">Watch one prompt refract into multiple perspectives</p>
    
    <!-- Status badges -->
    <div class="status-badges">
      {#if isPrismActive}
        <span class="badge live">🔴 Live</span>
      {:else}
        <span class="badge idle">Recorded</span>
      {/if}
    </div>
  </div>
  
  <div class="prism-content">
    <svg viewBox="0 0 {svgWidth} {svgHeight}" class="prism-svg">
      <!-- Defs -->
      <defs>
        <linearGradient id="inputBeamGradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="var(--ui-gold)" stop-opacity="0.3" />
          <stop offset="100%" stop-color="var(--ui-gold)" />
        </linearGradient>
        <filter id="prismGlow">
          <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
          <feMerge>
            <feMergeNode in="coloredBlur"/>
            <feMergeNode in="SourceGraphic"/>
          </feMerge>
        </filter>
      </defs>
      
      <!-- Input beam using AnimatedPath -->
      {#if phase !== 'ready'}
        <AnimatedPath
          d="M 0 140 L 180 140"
          duration={800}
          color="var(--ui-gold)"
          strokeWidth={4}
          glow={true}
          active={true}
        />
      {/if}
      
      <!-- Prism -->
      <path 
        d={prismPath} 
        class="prism-shape"
        class:glowing={phase === 'refracting' || phase === 'scoring'}
        filter={phase === 'refracting' || phase === 'scoring' ? 'url(#prismGlow)' : undefined}
      />
      <text x="250" y="160" class="prism-label">🔮</text>
      
      <!-- Input prompt label -->
      {#if phase !== 'ready'}
        <g in:fly={{ x: -50, duration: 500 }}>
          <rect x="10" y="110" width="160" height="60" rx="8" class="prompt-box" />
          <text x="90" y="135" class="prompt-text">Goal Input</text>
          <text x="90" y="155" class="prompt-hint">↳ Single prompt</text>
        </g>
      {/if}
      
      <!-- Refracted beams -->
      {#each candidates as candidate, i (candidate.id)}
        {@const endX = 550 + (i * 8)}
        {@const endY = 60 + (i * 70)}
        
        {#if visibleCandidatesSet.has(i)}
          <g in:fly={{ x: -100, duration: 500 }}>
            <!-- Beam line using AnimatedPath -->
            <AnimatedPath
              d="M 350 140 L {endX} {endY}"
              duration={300}
              delay={i * 100}
              color={candidate.color}
              strokeWidth={3}
              glow={true}
              active={phase !== 'complete' || candidate.id === winner?.id}
            />
            
            <!-- Dim non-winners -->
            {#if phase === 'complete' && candidate.id !== winner?.id}
              <line 
                x1="350" y1="140" x2={endX} y2={endY}
                stroke={candidate.color}
                stroke-width="3"
                opacity="0.2"
              />
            {/if}
            
            <!-- Candidate card -->
            <g transform="translate({endX}, {endY})">
              <rect 
                x="-10" y="-25" width="140" height="50" rx="8" 
                class="candidate-card"
                class:winner={phase === 'complete' && candidate.id === winner?.id}
                style="stroke: {candidate.color}"
              />
              <text x="60" y="-5" class="candidate-persona" style="fill: {candidate.color}">
                {getPersona(candidate)}
              </text>
              <text x="60" y="10" class="candidate-artifacts">
                {candidate.artifactCount} artifacts
              </text>
              
              {#if scoredCandidatesSet.has(i) && candidate.score !== undefined}
                <text x="125" y="-5" class="candidate-score" in:scale={{ duration: 300 }}>
                  {candidate.score.toFixed(0)}
                </text>
              {/if}
            </g>
          </g>
        {/if}
      {/each}
      
      <!-- Winner highlight -->
      {#if phase === 'complete' && winner}
        <g in:fade={{ duration: 500 }}>
          <rect x="200" y="320" width="300" height="60" rx="12" class="winner-box" />
          <text x="350" y="345" class="winner-label">🏆 Winner: {getPersona(winner)}</text>
          <text x="350" y="365" class="winner-score">
            Score: {winner.score?.toFixed(0) ?? '?'} | {winner.artifactCount} artifacts
          </text>
        </g>
      {/if}
    </svg>
  </div>
  
  <div class="prism-controls">
    <button class="play-btn" onclick={playAnimation} disabled={phase !== 'ready' && phase !== 'complete'}>
      {phase === 'ready' || phase === 'complete' ? '▶ Play Animation' : '⏳ Playing...'}
    </button>
    
    {#if phase !== 'ready'}
      <button class="reset-btn" onclick={reset}>
        ↺ Reset
      </button>
    {/if}
    
    <div class="phase-indicator">
      <span class="phase-label">Phase:</span>
      <span class="phase-value">{phase}</span>
    </div>
  </div>
  
  <div class="prism-footer">
    <span class="technique-badge">harmonic_{candidates.length}</span>
    <span class="separator">•</span>
    <span class="candidate-count">{candidates.length} candidates</span>
    {#if winner?.score}
      <span class="separator">•</span>
      <span class="winner-badge">Winner: {winner.score.toFixed(0)}/100</span>
    {/if}
  </div>
</div>
{/if}

<style>
  .prism-fracture {
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: var(--space-6);
  }
  
  .prism-header {
    text-align: center;
    margin-bottom: var(--space-4);
  }
  
  .prism-header h2 {
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
  
  @keyframes pulse-opacity {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
  }
  
  .prism-content {
    flex: 1;
    display: flex;
    justify-content: center;
    align-items: center;
  }
  
  .prism-svg {
    width: 100%;
    max-width: 700px;
    height: auto;
  }
  
  .prism-shape {
    fill: rgba(var(--ui-gold-rgb), 0.1);
    stroke: var(--ui-gold);
    stroke-width: 2;
    transition: all var(--transition-normal);
  }
  
  .prism-shape.glowing {
    fill: rgba(var(--ui-gold-rgb), 0.2);
  }
  
  .prism-label {
    font-size: 24px;
    text-anchor: middle;
  }
  
  .prompt-box {
    fill: var(--bg-primary);
    stroke: var(--ui-gold);
    stroke-width: 1;
  }
  
  .prompt-text {
    font-family: var(--font-serif);
    font-size: 12px;
    fill: var(--text-primary);
    text-anchor: middle;
  }
  
  .prompt-hint {
    font-family: var(--font-mono);
    font-size: 9px;
    fill: var(--text-tertiary);
    text-anchor: middle;
  }
  
  .candidate-card {
    fill: var(--bg-primary);
    stroke-width: 2;
    transition: all var(--transition-fast);
  }
  
  .candidate-card.winner {
    fill: rgba(var(--success-rgb), 0.1);
    stroke: var(--success) !important;
    filter: drop-shadow(0 0 12px var(--success));
  }
  
  .candidate-persona {
    font-family: var(--font-mono);
    font-size: 12px;
    font-weight: 600;
    text-anchor: middle;
  }
  
  .candidate-artifacts {
    font-family: var(--font-mono);
    font-size: 9px;
    fill: var(--text-tertiary);
    text-anchor: middle;
  }
  
  .candidate-score {
    font-family: var(--font-mono);
    font-size: 14px;
    font-weight: 700;
    fill: var(--text-gold);
    text-anchor: end;
  }
  
  .winner-box {
    fill: rgba(var(--success-rgb), 0.15);
    stroke: var(--success);
    stroke-width: 2;
  }
  
  .winner-label {
    font-family: var(--font-mono);
    font-size: 14px;
    font-weight: 600;
    fill: var(--success);
    text-anchor: middle;
  }
  
  .winner-score {
    font-family: var(--font-mono);
    font-size: 12px;
    fill: var(--text-secondary);
    text-anchor: middle;
  }
  
  .prism-controls {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: var(--space-4);
    margin-top: var(--space-4);
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
    opacity: 0.6;
    cursor: not-allowed;
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
  
  .phase-indicator {
    display: flex;
    gap: var(--space-2);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
  }
  
  .phase-label {
    color: var(--text-tertiary);
  }
  
  .phase-value {
    color: var(--text-gold);
    text-transform: capitalize;
  }
  
  .prism-footer {
    display: flex;
    justify-content: center;
    gap: var(--space-3);
    padding-top: var(--space-4);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .technique-badge {
    padding: var(--space-1) var(--space-2);
    background: var(--bg-primary);
    border-radius: var(--radius-sm);
    color: var(--text-gold);
  }
  
  .winner-badge {
    color: var(--success);
  }
  
  .separator {
    opacity: 0.4;
  }
</style>
