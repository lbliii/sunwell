<!--
  PrismFracture — Multi-perspective synthesis visualization (RFC-112)
  
  Shows a single prompt refracting into multiple perspectives (harmonic candidates),
  then converging into the final output.
  
  Data contract:
  - input_prompt: string
  - candidates: Array<{ index, persona, score, description }>
  - winner: { index, selection_reason, final_score }
  - technique: string ("harmonic_5", "variance_3", etc.)
-->
<script lang="ts">
  import { fade, fly, scale } from 'svelte/transition';
  
  interface Props {
    isLive?: boolean;
  }
  
  let { isLive = true }: Props = $props();
  
  // Demo data
  const demoData = {
    input_prompt: "Build a REST API with auth",
    candidates: [
      { index: 0, persona: 'architect', score: 85, color: '#3b82f6', description: 'Comprehensive 6-file structure' },
      { index: 1, persona: 'critic', score: 72, color: '#ef4444', description: 'Security-focused review' },
      { index: 2, persona: 'simplifier', score: 91, color: '#22c55e', description: 'Minimal 2-file solution' },
      { index: 3, persona: 'user', score: 78, color: '#a855f7', description: 'UX-optimized endpoints' },
      { index: 4, persona: 'adversary', score: 65, color: '#f97316', description: 'Edge case hardened' },
    ],
    winner: { index: 2, persona: 'simplifier', selection_reason: 'Highest quality score with minimal complexity', final_score: 91 },
    technique: 'harmonic_5',
  };
  
  let phase = $state<'ready' | 'refracting' | 'scoring' | 'converging' | 'complete'>('ready');
  let visibleCandidates = $state<number[]>([]);
  let scoredCandidates = $state<number[]>([]);
  
  function playAnimation() {
    phase = 'ready';
    visibleCandidates = [];
    scoredCandidates = [];
    
    setTimeout(() => {
      phase = 'refracting';
      // Stagger candidate appearances
      demoData.candidates.forEach((_, i) => {
        setTimeout(() => {
          visibleCandidates = [...visibleCandidates, i];
        }, i * 300);
      });
    }, 500);
    
    setTimeout(() => {
      phase = 'scoring';
      // Stagger score reveals
      demoData.candidates.forEach((_, i) => {
        setTimeout(() => {
          scoredCandidates = [...scoredCandidates, i];
        }, i * 200);
      });
    }, 2500);
    
    setTimeout(() => {
      phase = 'converging';
    }, 4000);
    
    setTimeout(() => {
      phase = 'complete';
    }, 5000);
  }
  
  // Prism geometry
  const prismPath = "M 250 80 L 350 200 L 150 200 Z";
</script>

<div class="prism-fracture" in:fade={{ duration: 300 }}>
  <div class="prism-header">
    <h2>Prism Fracture</h2>
    <p class="description">Watch one prompt refract into multiple perspectives</p>
  </div>
  
  <div class="prism-content">
    <svg viewBox="0 0 700 400" class="prism-svg">
      <!-- Input beam -->
      <line 
        x1="0" y1="140" x2="180" y2="140"
        class="input-beam"
        class:active={phase !== 'ready'}
      />
      
      <!-- Prism -->
      <path 
        d={prismPath} 
        class="prism-shape"
        class:glowing={phase === 'refracting' || phase === 'scoring'}
      />
      <text x="250" y="160" class="prism-label">🔮</text>
      
      <!-- Input prompt label -->
      {#if phase !== 'ready'}
        <g in:fly={{ x: -50, duration: 500 }}>
          <rect x="10" y="110" width="160" height="60" rx="8" class="prompt-box" />
          <text x="90" y="135" class="prompt-text">"{demoData.input_prompt}"</text>
          <text x="90" y="155" class="prompt-hint">↳ Single prompt</text>
        </g>
      {/if}
      
      <!-- Refracted beams -->
      {#each demoData.candidates as candidate, i}
        {@const angle = -40 + (i * 20)}
        {@const endX = 550 + (i * 10)}
        {@const endY = 80 + (i * 70)}
        
        {#if visibleCandidates.includes(i)}
          <g in:fly={{ x: -100, duration: 500 }}>
            <!-- Beam line -->
            <line 
              x1="350" y1="140" x2={endX} y2={endY}
              class="refracted-beam"
              style="stroke: {candidate.color}; opacity: {phase === 'complete' && candidate.index !== demoData.winner.index ? 0.3 : 1}"
            />
            
            <!-- Candidate card -->
            <g transform="translate({endX}, {endY})">
              <rect 
                x="-10" y="-25" width="140" height="50" rx="8" 
                class="candidate-card"
                class:winner={phase === 'complete' && candidate.index === demoData.winner.index}
                style="stroke: {candidate.color}"
              />
              <text x="60" y="-5" class="candidate-persona" style="fill: {candidate.color}">
                {candidate.persona}
              </text>
              
              {#if scoredCandidates.includes(i)}
                <text x="60" y="15" class="candidate-score" in:scale={{ duration: 300 }}>
                  {candidate.score}/100
                </text>
              {/if}
            </g>
          </g>
        {/if}
      {/each}
      
      <!-- Winner highlight -->
      {#if phase === 'complete'}
        <g in:fade={{ duration: 500 }}>
          <rect x="200" y="320" width="300" height="60" rx="12" class="winner-box" />
          <text x="350" y="345" class="winner-label">🏆 Winner: {demoData.winner.persona}</text>
          <text x="350" y="365" class="winner-score">Score: {demoData.winner.final_score}/100</text>
        </g>
      {/if}
    </svg>
  </div>
  
  <div class="prism-controls">
    <button class="play-btn" onclick={playAnimation} disabled={phase !== 'ready' && phase !== 'complete'}>
      {phase === 'ready' || phase === 'complete' ? '▶ Play Animation' : '⏳ Playing...'}
    </button>
    
    <div class="phase-indicator">
      <span class="phase-label">Phase:</span>
      <span class="phase-value">{phase}</span>
    </div>
  </div>
  
  <div class="prism-footer">
    <span class="technique-badge">{demoData.technique}</span>
    <span class="separator">•</span>
    <span class="candidate-count">{demoData.candidates.length} candidates</span>
  </div>
</div>

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
    margin: 0;
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
  
  .input-beam {
    stroke: var(--ui-gold);
    stroke-width: 4;
    stroke-dasharray: 400;
    stroke-dashoffset: 400;
    transition: stroke-dashoffset 1s ease-out;
  }
  
  .input-beam.active {
    stroke-dashoffset: 0;
    filter: drop-shadow(0 0 8px var(--ui-gold));
  }
  
  .prism-shape {
    fill: rgba(var(--ui-gold-rgb), 0.1);
    stroke: var(--ui-gold);
    stroke-width: 2;
    transition: all var(--transition-normal);
  }
  
  .prism-shape.glowing {
    fill: rgba(var(--ui-gold-rgb), 0.2);
    filter: drop-shadow(0 0 20px var(--ui-gold));
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
    font-size: 11px;
    fill: var(--text-primary);
    text-anchor: middle;
  }
  
  .prompt-hint {
    font-family: var(--font-mono);
    font-size: 9px;
    fill: var(--text-tertiary);
    text-anchor: middle;
  }
  
  .refracted-beam {
    stroke-width: 3;
    transition: opacity var(--transition-normal);
    filter: drop-shadow(0 0 4px currentColor);
  }
  
  .candidate-card {
    fill: var(--bg-primary);
    stroke-width: 2;
    transition: all var(--transition-fast);
  }
  
  .candidate-card.winner {
    fill: rgba(var(--success-rgb), 0.1);
    stroke: var(--success);
    filter: drop-shadow(0 0 12px var(--success));
  }
  
  .candidate-persona {
    font-family: var(--font-mono);
    font-size: 12px;
    font-weight: 600;
    text-anchor: middle;
  }
  
  .candidate-score {
    font-family: var(--font-mono);
    font-size: 11px;
    fill: var(--text-secondary);
    text-anchor: middle;
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
    gap: var(--space-6);
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
  
  .separator {
    opacity: 0.4;
  }
</style>
