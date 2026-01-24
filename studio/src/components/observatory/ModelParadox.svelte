<!--
  ModelParadox — Quality vs. cost/parameters visualization (RFC-112)
  
  Proves that small models + Sunwell beats big models raw.
  The paradox: 3B + architecture > 20B raw.
  
  Data contract:
  - comparisons: Array<{ model, params, cost_per_run, conditions: { technique, score, improvement_pct }[] }>
  - thesis_claim: string
-->
<script lang="ts">
  import { fade, fly } from 'svelte/transition';
  import { spring } from 'svelte/motion';
  
  // Demo data showing the paradox
  const demoData = {
    thesis: "Small models contain hidden capability. Structured cognition reveals it.",
    comparisons: [
      {
        model: 'llama3.2:3b',
        params: '3.2B',
        cost: '$0',
        raw: 1.0,
        sunwell: 8.5,
      },
      {
        model: 'llama3.2:20b', 
        params: '20.9B',
        cost: '$0',
        raw: 6.0,
        sunwell: 9.5,
      },
    ],
  };
  
  let showSunwell = $state(false);
  const smallRawSpring = spring(0, { stiffness: 0.03, damping: 0.3 });
  const smallSunwellSpring = spring(0, { stiffness: 0.03, damping: 0.3 });
  const bigRawSpring = spring(0, { stiffness: 0.03, damping: 0.3 });
  const bigSunwellSpring = spring(0, { stiffness: 0.03, damping: 0.3 });
  
  function playAnimation() {
    showSunwell = false;
    smallRawSpring.set(0, { hard: true });
    smallSunwellSpring.set(0, { hard: true });
    bigRawSpring.set(0, { hard: true });
    bigSunwellSpring.set(0, { hard: true });
    
    // Animate raw scores first
    setTimeout(() => {
      smallRawSpring.set(demoData.comparisons[0].raw);
      bigRawSpring.set(demoData.comparisons[1].raw);
    }, 500);
    
    // Then show Sunwell activation
    setTimeout(() => {
      showSunwell = true;
    }, 2000);
    
    // Animate Sunwell scores
    setTimeout(() => {
      smallSunwellSpring.set(demoData.comparisons[0].sunwell);
      bigSunwellSpring.set(demoData.comparisons[1].sunwell);
    }, 2500);
  }
  
  // SVG dimensions
  const width = 600;
  const height = 300;
  const padding = { top: 40, right: 80, bottom: 60, left: 60 };
  
  function scoreToY(score: number): number {
    return height - padding.bottom - ((score / 10) * (height - padding.top - padding.bottom));
  }
</script>

<div class="model-paradox" in:fade={{ duration: 300 }}>
  <div class="paradox-header">
    <h2>Model Paradox</h2>
    <p class="thesis">"{demoData.thesis}"</p>
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
      
      <!-- 3B raw line (flat, disappointing) -->
      <line
        x1={padding.left + 50}
        y1={scoreToY($smallRawSpring)}
        x2={width - padding.right - 50}
        y2={scoreToY($smallRawSpring)}
        class="data-line raw small"
      />
      <circle 
        cx={padding.left + 50} 
        cy={scoreToY($smallRawSpring)} 
        r="6" 
        class="data-point raw"
      />
      <text 
        x={width - padding.right - 40} 
        y={scoreToY($smallRawSpring) + 4} 
        class="line-label raw"
      >
        3B (raw): {$smallRawSpring.toFixed(1)}
      </text>
      
      <!-- 20B raw line (mediocre) -->
      <line
        x1={padding.left + 50}
        y1={scoreToY($bigRawSpring)}
        x2={width - padding.right - 50}
        y2={scoreToY($bigRawSpring)}
        class="data-line raw big"
      />
      <circle 
        cx={padding.left + 50} 
        cy={scoreToY($bigRawSpring)} 
        r="6" 
        class="data-point raw"
      />
      <text 
        x={width - padding.right - 40} 
        y={scoreToY($bigRawSpring) + 4} 
        class="line-label raw"
      >
        20B (raw): {$bigRawSpring.toFixed(1)}
      </text>
      
      <!-- Sunwell activation flash -->
      {#if showSunwell}
        <g in:fade={{ duration: 300 }}>
          <rect 
            x={padding.left} 
            y={padding.top} 
            width={width - padding.left - padding.right}
            height={height - padding.top - padding.bottom}
            class="activation-flash"
          />
          
          <!-- 3B + Sunwell line (rockets up!) -->
          <line
            x1={padding.left + 50}
            y1={scoreToY(demoData.comparisons[0].raw)}
            x2={width - padding.right - 50}
            y2={scoreToY($smallSunwellSpring)}
            class="data-line sunwell small"
          />
          <circle 
            cx={width - padding.right - 50} 
            cy={scoreToY($smallSunwellSpring)} 
            r="8" 
            class="data-point sunwell"
          />
          <text 
            x={width - padding.right + 10} 
            y={scoreToY($smallSunwellSpring) + 4} 
            class="line-label sunwell"
          >
            3B + Sunwell: {$smallSunwellSpring.toFixed(1)}
          </text>
          
          <!-- 20B + Sunwell line -->
          <line
            x1={padding.left + 50}
            y1={scoreToY(demoData.comparisons[1].raw)}
            x2={width - padding.right - 50}
            y2={scoreToY($bigSunwellSpring)}
            class="data-line sunwell big"
          />
          <circle 
            cx={width - padding.right - 50} 
            cy={scoreToY($bigSunwellSpring)} 
            r="8" 
            class="data-point sunwell"
          />
          <text 
            x={width - padding.right + 10} 
            y={scoreToY($bigSunwellSpring) + 4} 
            class="line-label sunwell"
          >
            20B + Sunwell: {$bigSunwellSpring.toFixed(1)}
          </text>
        </g>
      {/if}
    </svg>
    
    <!-- Stats cards -->
    <div class="stats-row">
      {#each demoData.comparisons as comp, i}
        <div class="stat-card" in:fly={{ y: 20, delay: i * 100, duration: 300 }}>
          <div class="stat-header">
            <span class="stat-model">{comp.model}</span>
            <span class="stat-params">{comp.params}</span>
          </div>
          <div class="stat-comparison">
            <div class="stat-value raw">
              <span class="value-label">Raw</span>
              <span class="value-number">{comp.raw.toFixed(1)}</span>
            </div>
            <span class="stat-arrow">→</span>
            <div class="stat-value sunwell">
              <span class="value-label">+Sunwell</span>
              <span class="value-number">{comp.sunwell.toFixed(1)}</span>
            </div>
            <span class="stat-improvement">+{(((comp.sunwell / comp.raw) - 1) * 100).toFixed(0)}%</span>
          </div>
        </div>
      {/each}
    </div>
  </div>
  
  <div class="paradox-controls">
    <button class="play-btn" onclick={playAnimation}>
      ▶ Reveal the Paradox
    </button>
  </div>
  
  <div class="paradox-footer">
    <span class="punchline">💡 $0 beats $50 with the right architecture.</span>
  </div>
</div>

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
    margin: 0;
  }
  
  .paradox-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-6);
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
  
  .y-label {
    font-family: var(--font-mono);
    font-size: 10px;
    fill: var(--text-tertiary);
    text-anchor: end;
  }
  
  .axis-title {
    font-family: var(--font-mono);
    font-size: 11px;
    fill: var(--text-tertiary);
    text-anchor: middle;
  }
  
  .data-line {
    stroke-width: 3;
    stroke-linecap: round;
    transition: all 0.5s ease;
  }
  
  .data-line.raw {
    stroke: var(--text-tertiary);
  }
  
  .data-line.sunwell {
    stroke: var(--ui-gold);
    filter: drop-shadow(0 0 8px var(--ui-gold));
  }
  
  .data-point {
    transition: all 0.5s ease;
  }
  
  .data-point.raw {
    fill: var(--text-tertiary);
  }
  
  .data-point.sunwell {
    fill: var(--radiant-gold);
    filter: drop-shadow(0 0 8px var(--radiant-gold));
  }
  
  .line-label {
    font-family: var(--font-mono);
    font-size: 10px;
  }
  
  .line-label.raw {
    fill: var(--text-tertiary);
  }
  
  .line-label.sunwell {
    fill: var(--text-gold);
    font-weight: 600;
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
  
  .paradox-controls {
    display: flex;
    justify-content: center;
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
  
  .play-btn:hover {
    transform: translateY(-2px);
    box-shadow: var(--glow-gold);
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
