<!--
  DemoPanel — The Prism Principle demonstration (Svelte 5, RFC-095)
  
  Single-surface progressive reveal: READY → GENERATING → REVEALED
  Now uses REAL backend execution via `sunwell demo --json`.
-->
<script lang="ts">
  import { fade, fly, scale } from 'svelte/transition';
  import { spring } from 'svelte/motion';
  import Sparkle from '../ui/Sparkle.svelte';
  import { demo, runDemo, reset, setTask, loadTasks } from '../../stores/demo.svelte';
  import type { DemoTask, DemoMethodOutput, ComponentBreakdown } from '../../stores/demo.svelte';
  
  interface Props {
    onRunTask?: (goal: string) => void;
  }
  
  let { onRunTask }: Props = $props();
  
  // Animated improvement counter
  const improvementDisplay = spring(0, { stiffness: 0.05, damping: 0.5 });
  
  // Update improvement animation when comparison arrives
  $effect(() => {
    if (demo.phase === 'revealed' && demo.comparison) {
      improvementDisplay.set(demo.improvementPercent);
    }
  });
  
  // Reset animation on reset
  $effect(() => {
    if (demo.phase === 'ready') {
      improvementDisplay.set(0, { hard: true });
    }
  });
  
  async function startDemo() {
    await runDemo();
  }
  
  function handleRunOwn() {
    onRunTask?.(demo.currentTask.prompt);
  }
  
  function formatFeature(feature: string): string {
    return feature
      .replace(/_/g, ' ')
      .replace(/\b\w/g, c => c.toUpperCase());
  }
  
  // View mode toggle: 'code' shows actual code, 'eval' shows features, 'breakdown' shows components
  type ViewMode = 'code' | 'eval' | 'breakdown';
  let viewMode = $state<ViewMode>('code');
  
  // Reactive values from store
  const phase = $derived(demo.phase);
  const progress = $derived(demo.progress);
  const message = $derived(demo.message);
  const task = $derived(demo.currentTask);
  const model = $derived(demo.currentModel);
  const actualModel = $derived(demo.actualModel);
  const singleShotCode = $derived(demo.singleShotCode);
  const sunwellCode = $derived(demo.sunwellCode);
  const singleShotScore = $derived(demo.singleShotScore);
  const sunwellScore = $derived(demo.sunwellScore);
  const error = $derived(demo.error);
  const breakdown = $derived(demo.breakdown);
  
  // Check if actual code is available
  const hasCode = $derived(
    demo.comparison?.single_shot?.code && demo.comparison?.sunwell?.code
  );
</script>

<div class="demo-panel" data-phase={phase}>
  <!-- Ready State: Hero CTA -->
  {#if phase === 'ready'}
    <div class="demo-hero" in:fade={{ duration: 300 }}>
      <div class="prism-glow" aria-hidden="true"></div>
      
      <h1>
        <span class="prism-icon">🔮</span>
        The Prism Principle
      </h1>
      
      <blockquote class="task-prompt">
        "{task.prompt}"
      </blockquote>
      
      <button class="run-cta" onclick={startDemo}>
        <Sparkle style="star" speed={200} />
        <span>Run Demo</span>
      </button>
      
      <div class="context-meta">
        <span>Using: {model}</span>
        <span class="dot">•</span>
        <span>Task: {task.name}</span>
        <span class="dot">•</span>
        <span class="real-badge">🔴 LIVE</span>
      </div>
    </div>
  {/if}
  
  <!-- Error State -->
  {#if phase === 'error'}
    <div class="demo-error" in:fade={{ duration: 300 }}>
      <div class="error-icon">⚠️</div>
      <h2>Demo Failed</h2>
      <p class="error-message">{error}</p>
      <button class="action-secondary" onclick={reset}>
        Try Again ↻
      </button>
    </div>
  {/if}
  
  <!-- Generating State: Side-by-Side Race with REAL STREAMING -->
  {#if phase === 'generating' || phase === 'judging' || phase === 'refining'}
    <div class="demo-race" in:fade={{ duration: 300 }}>
      <p class="task-prompt-compact">"{task.prompt}"</p>
      
      <div class="race-grid">
        <!-- Single-shot pane: Shows streaming code in real-time -->
        <div class="code-pane baseline" class:dimmed={phase !== 'generating' && !singleShotCode}>
          <div class="pane-header">
            <span class="pane-icon">⚫</span>
            <span class="pane-title">Single-shot</span>
            {#if singleShotCode}
              <span class="phase-badge done">Streaming...</span>
            {:else}
              <span class="phase-badge">Waiting...</span>
            {/if}
          </div>
          <pre class="code-content">
            <code>{singleShotCode}</code>{#if !singleShotCode || phase !== 'revealed'}<span class="cursor"></span>{/if}
          </pre>
        </div>
        
        <!-- Sunwell pane: Shows streaming code + phase updates -->
        <div class="code-pane prism">
          <div class="pane-header">
            <span class="pane-icon">🔮</span>
            <span class="pane-title">Sunwell + Resonance</span>
            {#if phase === 'generating' || demo.sunwellPhase === 'generating'}
              <span class="phase-badge">{sunwellCode ? 'Streaming...' : 'Generating...'}</span>
            {:else if phase === 'judging' || demo.sunwellPhase === 'judging'}
              <span class="phase-badge">Judging...</span>
            {:else if phase === 'refining'}
              <span class="phase-badge">Refining...</span>
            {/if}
          </div>
          <pre class="code-content">
            <code>{sunwellCode}</code>{#if !sunwellCode || phase !== 'revealed'}<span class="cursor"></span>{/if}
          </pre>
        </div>
      </div>
      
      <div class="progress-track">
        <div class="progress-header">
          <Sparkle style="star" speed={120} />
          <span class="progress-label">{message || 'Processing...'}</span>
        </div>
        <div class="progress-bar-container">
          <div class="progress-bar" style="width: {progress}%">
            <div class="progress-shimmer"></div>
          </div>
        </div>
      </div>
    </div>
  {/if}
  
  <!-- Revealed State: The Payoff -->
  {#if phase === 'revealed'}
    {@const sunwellWon = sunwellScore && singleShotScore && sunwellScore.score >= singleShotScore.score}
    <div class="demo-revealed" in:scale={{ start: 0.97, duration: 400 }}>
      <div class="completion-badge" class:loss={!sunwellWon}>
        {sunwellWon ? '✅ Demo Complete' : '⚠️ Demo Complete'}
      </div>
      
      <div class="model-badge">
        <span class="model-icon">🤖</span>
        <span class="model-name">{actualModel}</span>
      </div>
      
      <p class="task-prompt-compact">"{task.prompt}"</p>
      
      <!-- View Mode Toggle -->
      <div class="view-toggle">
        <button 
          class="toggle-btn" 
          class:active={viewMode === 'code'}
          onclick={() => viewMode = 'code'}
        >
          <span class="toggle-icon">📝</span> Code
        </button>
        <button 
          class="toggle-btn" 
          class:active={viewMode === 'eval'}
          onclick={() => viewMode = 'eval'}
        >
          <span class="toggle-icon">📊</span> Evaluation
        </button>
        {#if breakdown}
          <button 
            class="toggle-btn" 
            class:active={viewMode === 'breakdown'}
            onclick={() => viewMode = 'breakdown'}
          >
            <span class="toggle-icon">🔬</span> Breakdown
          </button>
        {/if}
      </div>
      
      <div class="comparison-grid">
        <div class="result-pane baseline" class:winner={singleShotScore && sunwellScore && singleShotScore.score > sunwellScore.score}>
          <div class="pane-header">
            <span class="pane-icon">⚫</span>
            <span class="pane-title">Single-shot</span>
            <span class="score" 
                  class:good={singleShotScore && singleShotScore.score >= 8}
                  class:warning={singleShotScore && singleShotScore.score >= 5 && singleShotScore.score < 8}
                  class:bad={singleShotScore && singleShotScore.score < 5}>
              {singleShotScore?.score.toFixed(1)}/10
            </span>
          </div>
          
          {#if viewMode === 'code'}
            <pre class="code-content"><code>{@html highlightPython(singleShotCode)}</code></pre>
          {:else}
            <div class="eval-content">
              <div class="eval-stats">
                <div class="stat">
                  <span class="stat-label">Lines</span>
                  <span class="stat-value">{singleShotScore?.lines}</span>
                </div>
                <div class="stat">
                  <span class="stat-label">Time</span>
                  <span class="stat-value">{singleShotScore?.time_ms}ms</span>
                </div>
                {#if singleShotScore?.tokens?.total}
                  <div class="stat tokens">
                    <span class="stat-label">Tokens</span>
                    <span class="stat-value">{singleShotScore.tokens.total.toLocaleString()}</span>
                  </div>
                {/if}
              </div>
              <div class="feature-list eval-features">
                {#each Object.entries(singleShotScore?.features ?? {}) as [feature, present], i}
                  <div 
                    class="feature" 
                    class:present 
                    class:missing={!present}
                    in:fade={{ delay: i * 50, duration: 150 }}
                  >
                    <span class="icon">{present ? '✅' : '❌'}</span>
                    <span>{formatFeature(feature)}</span>
                  </div>
                {/each}
              </div>
            </div>
          {/if}
        </div>
        
        <div class="result-pane prism" class:winner={sunwellScore && singleShotScore && sunwellScore.score >= singleShotScore.score} class:loser={sunwellScore && singleShotScore && sunwellScore.score < singleShotScore.score}>
          <div class="pane-header">
            <span class="pane-icon">🔮</span>
            <span class="pane-title">Sunwell + Resonance</span>
            <span class="score"
                  class:good={sunwellScore && sunwellScore.score >= 8}
                  class:warning={sunwellScore && sunwellScore.score >= 5 && sunwellScore.score < 8}
                  class:bad={sunwellScore && sunwellScore.score < 5}>
              {sunwellScore?.score.toFixed(1)}/10
            </span>
          </div>
          
          {#if viewMode === 'code'}
            <pre class="code-content"><code>{@html highlightPython(sunwellCode)}</code></pre>
          {:else}
            <div class="eval-content">
              <div class="eval-stats">
                <div class="stat">
                  <span class="stat-label">Lines</span>
                  <span class="stat-value">{sunwellScore?.lines}</span>
                </div>
                <div class="stat">
                  <span class="stat-label">Time</span>
                  <span class="stat-value">{sunwellScore?.time_ms}ms</span>
                </div>
                {#if sunwellScore?.iterations !== undefined}
                  <div class="stat">
                    <span class="stat-label">Iterations</span>
                    <span class="stat-value">{sunwellScore.iterations}</span>
                  </div>
                {/if}
                {#if sunwellScore?.tokens?.total}
                  <div class="stat tokens">
                    <span class="stat-label">Tokens</span>
                    <span class="stat-value">{sunwellScore.tokens.total.toLocaleString()}</span>
                  </div>
                {/if}
              </div>
              <div class="feature-list eval-features">
                {#each Object.entries(sunwellScore?.features ?? {}) as [feature, present], i}
                  <div 
                    class="feature" 
                    class:present 
                    class:missing={!present}
                    in:fade={{ delay: i * 50, duration: 150 }}
                  >
                    <span class="icon">{present ? '✅' : '❌'}</span>
                    <span>{formatFeature(feature)}</span>
                  </div>
                {/each}
              </div>
            </div>
          {/if}
        </div>
      </div>
      
      <!-- Breakdown View: What each Sunwell component contributed -->
      {#if viewMode === 'breakdown' && breakdown}
        <div class="breakdown-view" in:fade={{ duration: 300 }}>
          <h3 class="breakdown-title">🔬 What Made the Difference</h3>
          <p class="breakdown-subtitle">How each Sunwell component contributed to the result</p>
          
          <div class="breakdown-grid">
            <!-- Lens -->
            <div class="breakdown-card lens">
              <div class="card-header">
                <span class="card-icon">👓</span>
                <span class="card-title">Lens</span>
                <span class="card-status" class:active={breakdown.lens.detected}>
                  {breakdown.lens.detected ? '✓ Active' : '○ Not used'}
                </span>
              </div>
              <div class="card-body">
                <div class="card-field">
                  <span class="field-label">Name</span>
                  <span class="field-value">{breakdown.lens.name}</span>
                </div>
                {#if breakdown.lens.heuristics_applied?.length > 0}
                  <div class="card-field">
                    <span class="field-label">Heuristics</span>
                    <div class="field-tags">
                      {#each breakdown.lens.heuristics_applied.slice(0, 3) as h}
                        <span class="tag">{h}</span>
                      {/each}
                      {#if breakdown.lens.heuristics_applied.length > 3}
                        <span class="tag more">+{breakdown.lens.heuristics_applied.length - 3}</span>
                      {/if}
                    </div>
                  </div>
                {/if}
              </div>
            </div>
            
            <!-- Structured Prompting -->
            <div class="breakdown-card prompt">
              <div class="card-header">
                <span class="card-icon">📝</span>
                <span class="card-title">Prompt</span>
                <span class="card-status active">{breakdown.prompt.type}</span>
              </div>
              <div class="card-body">
                <div class="card-field">
                  <span class="field-label">Requirements Added</span>
                  <div class="field-list">
                    {#each breakdown.prompt.requirements_added.slice(0, 4) as req}
                      <div class="list-item">• {req}</div>
                    {/each}
                    {#if breakdown.prompt.requirements_added.length > 4}
                      <div class="list-item more">+{breakdown.prompt.requirements_added.length - 4} more</div>
                    {/if}
                  </div>
                </div>
              </div>
            </div>
            
            <!-- Judge -->
            <div class="breakdown-card judge">
              <div class="card-header">
                <span class="card-icon">⚖️</span>
                <span class="card-title">Judge</span>
                <span class="card-status" class:passed={breakdown.judge.passed} class:failed={!breakdown.judge.passed}>
                  {breakdown.judge.passed ? '✓ Passed' : '✗ Failed'}
                </span>
              </div>
              <div class="card-body">
                <div class="card-field">
                  <span class="field-label">Initial Score</span>
                  <span class="field-value score" class:good={breakdown.judge.score >= 8} class:bad={breakdown.judge.score < 8}>
                    {breakdown.judge.score.toFixed(1)}/10
                  </span>
                </div>
                {#if breakdown.judge.issues?.length > 0}
                  <div class="card-field">
                    <span class="field-label">Issues Found</span>
                    <div class="field-list issues">
                      {#each breakdown.judge.issues.slice(0, 3) as issue}
                        <div class="list-item issue">⚠️ {issue}</div>
                      {/each}
                    </div>
                  </div>
                {/if}
              </div>
            </div>
            
            <!-- Resonance -->
            <div class="breakdown-card resonance" class:triggered={breakdown.resonance.triggered} class:failed={breakdown.resonance.triggered && !breakdown.resonance.succeeded}>
              <div class="card-header">
                <span class="card-icon">🔮</span>
                <span class="card-title">Resonance</span>
                <span class="card-status" 
                      class:active={breakdown.resonance.triggered && breakdown.resonance.succeeded}
                      class:failed={breakdown.resonance.triggered && !breakdown.resonance.succeeded}>
                  {#if !breakdown.resonance.triggered}
                    ○ Not needed
                  {:else if breakdown.resonance.succeeded}
                    ✓ {breakdown.resonance.iterations} iteration(s)
                  {:else}
                    ✗ Failed to improve
                  {/if}
                </span>
              </div>
              <div class="card-body">
                {#if breakdown.resonance.triggered && breakdown.resonance.succeeded}
                  <div class="card-field">
                    <span class="field-label">Improvements Made</span>
                    <div class="field-tags improvements">
                      {#each breakdown.resonance.improvements as imp}
                        <span class="tag success">{formatFeature(imp)}</span>
                      {/each}
                    </div>
                  </div>
                {:else if breakdown.resonance.triggered && !breakdown.resonance.succeeded}
                  <div class="card-field">
                    <span class="field-label">Status</span>
                    <span class="field-value warning">Refinement attempted but could not improve quality</span>
                  </div>
                {:else}
                  <div class="card-field">
                    <span class="field-label">Status</span>
                    <span class="field-value">Code passed judge on first attempt</span>
                  </div>
                {/if}
              </div>
            </div>
          </div>
          
          <!-- Final Result Summary -->
          <div class="breakdown-summary">
            <div class="summary-item">
              <span class="summary-icon">🎯</span>
              <span class="summary-label">Final Score</span>
              <span class="summary-value" class:good={breakdown.result.final_score >= 8} class:warning={breakdown.result.final_score >= 5 && breakdown.result.final_score < 8} class:bad={breakdown.result.final_score < 5}>{breakdown.result.final_score.toFixed(1)}/10</span>
            </div>
            <div class="summary-item">
              <span class="summary-icon">✅</span>
              <span class="summary-label">Features Achieved</span>
              <span class="summary-value">{breakdown.result.features_achieved.length}</span>
            </div>
            {#if breakdown.result.features_missing?.length > 0}
              <div class="summary-item">
                <span class="summary-icon">⚠️</span>
                <span class="summary-label">Still Missing</span>
                <span class="summary-value warning">{breakdown.result.features_missing.length}</span>
              </div>
            {/if}
          </div>
        </div>
      {/if}
      
      <div class="improvement-reveal" in:fade={{ delay: 800, duration: 400 }}>
        <div class="improvement-number" class:negative={!sunwellWon}>
          {sunwellWon ? '🔮' : '⚫'} {$improvementDisplay >= 0 ? '+' : ''}{$improvementDisplay.toFixed(0)}%
        </div>
        <p class="tagline" class:loss={!sunwellWon}>
          {sunwellWon ? 'Same model. Same prompt. Different architecture.' : 'Single-shot won this round.'}
        </p>
        <p class="subtagline">
          {#if sunwellWon}
            The capability was already there. Sunwell revealed it.
          {:else}
            Architecture overhead doesn't always pay off. This is honest variance.
          {/if}
        </p>
        
        {#if singleShotScore?.tokens?.total && sunwellScore?.tokens?.total}
          {@const singleTokens = singleShotScore.tokens.total}
          {@const sunwellTokens = sunwellScore.tokens.total}
          {@const tokenDiff = sunwellTokens - singleTokens}
          {@const tokenPercent = ((tokenDiff / singleTokens) * 100).toFixed(0)}
          <div class="token-comparison" in:fade={{ delay: 1000, duration: 300 }}>
            <span class="token-icon">🪙</span>
            <span class="token-stats">
              {singleTokens.toLocaleString()} → {sunwellTokens.toLocaleString()} tokens
              <span class="token-delta" class:positive={tokenDiff > 0} class:negative={tokenDiff < 0}>
                ({tokenDiff > 0 ? '+' : ''}{tokenPercent}%)
              </span>
            </span>
          </div>
        {/if}
      </div>
      
      <div class="action-buttons" in:fade={{ delay: 1200, duration: 300 }}>
        <button class="action-primary" onclick={handleRunOwn}>
          Run Your Own Task →
        </button>
        <button class="action-secondary" onclick={reset}>
          Run Again ↻
        </button>
      </div>
    </div>
  {/if}
</div>

<script module lang="ts">
  // Basic Python syntax highlighting (will be replaced with Shiki in RFC-097)
  function highlightPython(code: string): string {
    if (!code) return '';
    
    // Escape HTML first
    let html = code
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    
    // Keywords
    html = html.replace(
      /\b(def|return|if|else|elif|for|while|try|except|finally|raise|import|from|as|class|with|not|and|or|in|is|None|True|False)\b/g,
      '<span class="syntax-keyword">$1</span>'
    );
    
    // Function names (after def)
    html = html.replace(
      /\b(def)\s+(\w+)/g,
      '<span class="syntax-keyword">$1</span> <span class="syntax-function">$2</span>'
    );
    
    // Strings (triple-quoted and single-quoted)
    html = html.replace(
      /("""[\s\S]*?"""|'''[\s\S]*?'''|"[^"]*"|'[^']*')/g,
      '<span class="syntax-string">$1</span>'
    );
    
    // Numbers
    html = html.replace(
      /\b(\d+\.?\d*)\b/g,
      '<span class="syntax-number">$1</span>'
    );
    
    // Types (common Python types and after colons in annotations)
    html = html.replace(
      /:\s*(float|int|str|bool|list|dict|tuple|set|None)\b/g,
      ': <span class="syntax-type">$1</span>'
    );
    
    // Return type annotation
    html = html.replace(
      /-&gt;\s*(float|int|str|bool|list|dict|tuple|set|None)\b/g,
      '-&gt; <span class="syntax-type">$1</span>'
    );
    
    // Builtins
    html = html.replace(
      /\b(isinstance|type|print|len|range|enumerate|zip|map|filter|sorted|TypeError|ZeroDivisionError|ValueError|Exception)\b/g,
      '<span class="syntax-builtin">$1</span>'
    );
    
    // Comments (must come last to not interfere with other patterns)
    html = html.replace(
      /(#.*)$/gm,
      '<span class="syntax-comment">$1</span>'
    );
    
    return html;
  }
</script>

<style>
  .demo-panel {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 100%;
    padding: var(--space-8);
    position: relative;
    /* Removed overflow:hidden - clips dropdown menus */
  }
  
  /* ═══════════════════════════════════════════════════════════
     READY STATE: Hero CTA
     ═══════════════════════════════════════════════════════════ */
  
  .demo-hero {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    max-width: 600px;
    position: relative;
  }
  
  .prism-glow {
    position: absolute;
    top: -100px;
    width: 400px;
    height: 400px;
    background: var(--gradient-aura);
    pointer-events: none;
    animation: pulse-glow 4s ease-in-out infinite;
  }
  
  @keyframes pulse-glow {
    0%, 100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.1); opacity: 0.7; }
  }
  
  .demo-hero h1 {
    font-family: var(--font-serif);
    font-size: var(--text-3xl);
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: var(--space-6);
    display: flex;
    align-items: center;
    gap: var(--space-3);
    position: relative;
    z-index: 1;
  }
  
  .prism-icon {
    font-size: 1.5em;
  }
  
  .task-prompt {
    font-family: var(--font-serif);
    font-size: var(--text-xl);
    font-style: italic;
    color: var(--text-secondary);
    margin: 0 0 var(--space-8);
    padding: var(--space-4) var(--space-6);
    border-left: 3px solid var(--ui-gold);
    background: rgba(201, 162, 39, 0.05);
    border-radius: 0 var(--radius-md) var(--radius-md) 0;
    position: relative;
    z-index: 1;
  }
  
  .run-cta {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-4) var(--space-8);
    font-size: var(--text-lg);
    font-weight: 600;
    font-family: var(--font-mono);
    color: var(--bg-primary);
    background: var(--gradient-ui-gold);
    border: none;
    border-radius: var(--radius-lg);
    cursor: pointer;
    box-shadow: var(--glow-gold-subtle), 0 4px 12px rgba(0, 0, 0, 0.2);
    transition: transform var(--transition-fast), box-shadow var(--transition-fast);
    position: relative;
    z-index: 1;
  }
  
  .run-cta:hover {
    transform: translateY(-2px);
    box-shadow: var(--glow-gold), 0 8px 24px rgba(0, 0, 0, 0.3);
  }
  
  .run-cta:active {
    transform: translateY(0);
  }
  
  .context-meta {
    margin-top: var(--space-6);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-tertiary);
    display: flex;
    gap: var(--space-3);
    position: relative;
    z-index: 1;
  }
  
  .dot { opacity: 0.4; }
  
  .real-badge {
    color: var(--error);
    font-weight: 600;
    animation: pulse-badge 2s ease-in-out infinite;
  }
  
  /* ═══════════════════════════════════════════════════════════
     ERROR STATE
     ═══════════════════════════════════════════════════════════ */
  
  .demo-error {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    max-width: 500px;
  }
  
  .error-icon {
    font-size: 3rem;
    margin-bottom: var(--space-4);
  }
  
  .demo-error h2 {
    font-family: var(--font-serif);
    font-size: var(--text-2xl);
    color: var(--text-primary);
    margin: 0 0 var(--space-4);
  }
  
  .error-message {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--error);
    background: rgba(var(--error-rgb), 0.1);
    padding: var(--space-4);
    border-radius: var(--radius-md);
    margin-bottom: var(--space-6);
    max-width: 100%;
    overflow-x: auto;
  }
  
  /* ═══════════════════════════════════════════════════════════
     GENERATING STATE: Side-by-Side Race
     ═══════════════════════════════════════════════════════════ */
  
  .demo-race {
    width: 100%;
    max-width: 1000px;
  }
  
  .task-prompt-compact {
    font-family: var(--font-serif);
    font-size: var(--text-base);
    font-style: italic;
    color: var(--text-secondary);
    text-align: center;
    margin-bottom: var(--space-6);
  }
  
  .race-grid,
  .comparison-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-4);
    margin-bottom: var(--space-6);
  }
  
  .code-pane,
  .result-pane {
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    overflow: hidden;
    border: 1px solid var(--border-default);
    transition: opacity var(--transition-normal), border-color var(--transition-normal);
  }
  
  .code-pane.baseline {
    border-color: var(--border-default);
  }
  
  .code-pane.baseline.dimmed {
    opacity: 0.6;
  }
  
  .code-pane.prism,
  .result-pane.prism.winner {
    border-color: var(--border-emphasis);
    box-shadow: var(--glow-gold-subtle);
  }
  
  .result-pane.prism.loser {
    border-color: var(--border-default);
    box-shadow: none;
    opacity: 0.85;
  }
  
  .result-pane.baseline.winner {
    border-color: var(--success);
    box-shadow: 0 0 12px rgba(var(--success-rgb), 0.3);
  }
  
  .pane-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-3) var(--space-4);
    background: var(--bg-tertiary);
    border-bottom: 1px solid var(--border-subtle);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
  }
  
  .pane-title {
    font-weight: 500;
    color: var(--text-primary);
  }
  
  .phase-badge {
    margin-left: auto;
    padding: var(--space-1) var(--space-2);
    background: rgba(201, 162, 39, 0.15);
    border-radius: var(--radius-sm);
    font-size: var(--text-xs);
    color: var(--text-gold);
    animation: pulse-badge 2s ease-in-out infinite;
  }
  
  .phase-badge.done {
    background: rgba(var(--success-rgb), 0.15);
    color: var(--success);
    animation: none;
  }
  
  @keyframes pulse-badge {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
  }
  
  
  .code-content {
    padding: var(--space-4);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    line-height: 1.6;
    min-height: 200px;
    max-height: 300px;
    overflow-y: auto;
    margin: 0;
    white-space: pre-wrap;
    color: var(--text-secondary);
  }
  
  .cursor {
    display: inline-block;
    width: 8px;
    height: 1.2em;
    background: var(--ui-gold);
    animation: blink 1s step-end infinite;
    vertical-align: text-bottom;
    margin-left: 2px;
  }
  
  @keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
  }
  
  .progress-track {
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    padding: var(--space-4);
  }
  
  .progress-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-2);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-primary);
  }
  
  .progress-bar-container {
    height: 4px;
    background: rgba(201, 162, 39, 0.15);
    border-radius: 2px;
    overflow: hidden;
  }
  
  .progress-bar {
    height: 100%;
    background: var(--gradient-progress);
    transition: width 0.3s ease;
    position: relative;
    box-shadow: var(--glow-gold-subtle);
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
  
  /* ═══════════════════════════════════════════════════════════
     REVEALED STATE: The Payoff
     ═══════════════════════════════════════════════════════════ */
  
  .demo-revealed {
    width: 100%;
    max-width: 1000px;
  }
  
  .completion-badge {
    text-align: center;
    font-family: var(--font-mono);
    font-size: var(--text-lg);
    font-weight: 500;
    color: var(--success);
    margin-bottom: var(--space-2);
  }
  
  .completion-badge.loss {
    color: var(--warning);
  }
  
  .model-badge {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    margin-bottom: var(--space-4);
    padding: var(--space-2) var(--space-4);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-full);
    width: fit-content;
    margin-left: auto;
    margin-right: auto;
  }
  
  .model-icon {
    font-size: 1em;
  }
  
  .model-name {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-secondary);
  }
  
  /* View Toggle */
  .view-toggle {
    display: flex;
    justify-content: center;
    gap: var(--space-2);
    margin-bottom: var(--space-6);
  }
  
  .toggle-btn {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-4);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--text-secondary);
    background: var(--bg-secondary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  
  .toggle-btn:hover {
    color: var(--text-primary);
    border-color: var(--border-emphasis);
  }
  
  .toggle-btn.active {
    color: var(--text-gold);
    background: rgba(201, 162, 39, 0.1);
    border-color: var(--ui-gold);
  }
  
  .toggle-icon {
    font-size: 1.1em;
  }
  
  /* Evaluation Content */
  .eval-content {
    padding: var(--space-4);
    min-height: 200px;
  }
  
  .eval-stats {
    display: flex;
    gap: var(--space-6);
    margin-bottom: var(--space-4);
    padding-bottom: var(--space-4);
    border-bottom: 1px solid var(--border-subtle);
  }
  
  .stat {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  
  .stat-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  
  .stat-value {
    font-family: var(--font-mono);
    font-size: var(--text-lg);
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .eval-features {
    border-top: none;
    padding-top: 0;
  }
  
  .score {
    margin-left: auto;
    font-weight: 600;
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
  }
  
  .score.bad {
    background: rgba(var(--error-rgb), 0.15);
    color: var(--error);
  }
  
  .score.warning {
    background: rgba(var(--warning-rgb), 0.15);
    color: var(--warning);
  }
  
  .score.good {
    background: rgba(var(--success-rgb), 0.15);
    color: var(--success);
  }
  
  .feature-list {
    padding: var(--space-3) var(--space-4);
    border-top: 1px solid var(--border-subtle);
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }
  
  .feature {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
  }
  
  .feature.missing {
    background: rgba(var(--error-rgb), 0.1);
    color: var(--error);
  }
  
  .feature.present {
    background: rgba(var(--success-rgb), 0.1);
    color: var(--success);
  }
  
  /* The Big Number */
  .improvement-reveal {
    text-align: center;
    padding: var(--space-8) 0;
    border-top: 1px solid var(--border-subtle);
    border-bottom: 1px solid var(--border-subtle);
    margin-bottom: var(--space-6);
  }
  
  .improvement-number {
    font-family: var(--font-serif);
    font-size: 4rem;
    font-weight: 700;
    background: linear-gradient(135deg, var(--ui-gold) 0%, var(--radiant-gold) 50%, var(--ui-gold) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: var(--space-4);
  }
  
  .improvement-number.negative {
    background: linear-gradient(135deg, var(--text-tertiary) 0%, var(--text-secondary) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  
  .tagline {
    font-family: var(--font-mono);
    font-size: var(--text-lg);
    font-weight: 500;
    color: var(--text-primary);
    margin: 0 0 var(--space-2);
  }
  
  .tagline.loss {
    color: var(--text-secondary);
  }
  
  .subtagline {
    font-family: var(--font-serif);
    font-size: var(--text-base);
    font-style: italic;
    color: var(--text-tertiary);
    margin: 0;
  }
  
  /* Token Comparison */
  .token-comparison {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    margin-top: var(--space-4);
    padding: var(--space-3) var(--space-4);
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
  }
  
  .token-icon {
    font-size: 1.2em;
  }
  
  .token-stats {
    color: var(--text-secondary);
  }
  
  .token-delta {
    font-weight: 600;
    margin-left: var(--space-1);
  }
  
  .token-delta.positive {
    color: var(--warning);
  }
  
  .token-delta.negative {
    color: var(--success);
  }
  
  /* Tokens stat in eval view */
  .stat.tokens .stat-value {
    color: var(--text-gold);
  }
  
  /* CTAs */
  .action-buttons {
    display: flex;
    justify-content: center;
    gap: var(--space-4);
  }
  
  .action-primary {
    padding: var(--space-3) var(--space-6);
    font-family: var(--font-mono);
    font-weight: 600;
    color: var(--bg-primary);
    background: var(--gradient-ui-gold);
    border: none;
    border-radius: var(--radius-md);
    cursor: pointer;
    box-shadow: var(--glow-gold-subtle);
    transition: transform var(--transition-fast), box-shadow var(--transition-fast);
  }
  
  .action-primary:hover {
    transform: translateY(-2px);
    box-shadow: var(--glow-gold);
  }
  
  .action-secondary {
    padding: var(--space-3) var(--space-6);
    font-family: var(--font-mono);
    font-weight: 500;
    color: var(--text-secondary);
    background: var(--bg-secondary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: background var(--transition-fast), color var(--transition-fast);
  }
  
  .action-secondary:hover {
    background: var(--bg-tertiary);
    color: var(--text-primary);
  }
  
  /* ═══════════════════════════════════════════════════════════
     SYNTAX HIGHLIGHTING — Holy Light Theme
     ═══════════════════════════════════════════════════════════ */
  
  .code-content :global(.syntax-keyword) {
    color: var(--ui-gold);
  }
  
  .code-content :global(.syntax-function) {
    color: var(--syntax-function);
  }
  
  .code-content :global(.syntax-string) {
    color: var(--syntax-string);
  }
  
  .code-content :global(.syntax-number) {
    color: var(--syntax-number);
  }
  
  .code-content :global(.syntax-comment) {
    color: var(--syntax-comment);
    font-style: italic;
  }
  
  .code-content :global(.syntax-type) {
    color: var(--syntax-type);
  }
  
  .code-content :global(.syntax-builtin) {
    color: var(--syntax-builtin);
  }
  
  /* ═══════════════════════════════════════════════════════════
     BREAKDOWN VIEW: Component Contributions
     ═══════════════════════════════════════════════════════════ */
  
  .breakdown-view {
    margin-bottom: var(--space-6);
    padding: var(--space-6);
    background: var(--bg-secondary);
    border-radius: var(--radius-lg);
    border: 1px solid var(--border-default);
  }
  
  .breakdown-title {
    font-family: var(--font-serif);
    font-size: var(--text-xl);
    font-weight: 600;
    color: var(--text-primary);
    margin: 0 0 var(--space-2);
    text-align: center;
  }
  
  .breakdown-subtitle {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-tertiary);
    text-align: center;
    margin: 0 0 var(--space-6);
  }
  
  .breakdown-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-4);
    margin-bottom: var(--space-6);
  }
  
  .breakdown-card {
    background: var(--bg-primary);
    border-radius: var(--radius-md);
    border: 1px solid var(--border-subtle);
    overflow: hidden;
    transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
  }
  
  .breakdown-card:hover {
    border-color: var(--border-default);
  }
  
  .breakdown-card.triggered {
    border-color: var(--ui-gold);
    box-shadow: var(--glow-gold-subtle);
  }
  
  .card-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-3) var(--space-4);
    background: var(--bg-tertiary);
    border-bottom: 1px solid var(--border-subtle);
  }
  
  .card-icon {
    font-size: 1.2em;
  }
  
  .card-title {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .card-status {
    margin-left: auto;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    background: var(--bg-secondary);
    color: var(--text-tertiary);
  }
  
  .card-status.active {
    background: rgba(201, 162, 39, 0.15);
    color: var(--text-gold);
  }
  
  .card-status.passed {
    background: rgba(var(--success-rgb), 0.15);
    color: var(--success);
  }
  
  .card-status.failed {
    background: rgba(var(--error-rgb), 0.15);
    color: var(--error);
  }
  
  .card-body {
    padding: var(--space-4);
  }
  
  .card-field {
    margin-bottom: var(--space-3);
  }
  
  .card-field:last-child {
    margin-bottom: 0;
  }
  
  .field-label {
    display: block;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: var(--space-1);
  }
  
  .field-value {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-primary);
  }
  
  .field-value.score.good {
    color: var(--success);
  }
  
  .field-value.score.bad {
    color: var(--error);
  }
  
  .field-value.warning {
    color: var(--warning);
  }

  .field-tags {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
  }
  
  .tag {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    padding: var(--space-1) var(--space-2);
    background: var(--bg-secondary);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
  }
  
  .tag.more {
    background: transparent;
    color: var(--text-tertiary);
  }
  
  .tag.success {
    background: rgba(var(--success-rgb), 0.15);
    color: var(--success);
  }
  
  .field-list {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-secondary);
  }
  
  .list-item {
    padding: var(--space-1) 0;
    line-height: 1.4;
  }
  
  .list-item.more {
    color: var(--text-tertiary);
    font-style: italic;
  }
  
  .list-item.issue {
    color: var(--warning);
  }
  
  .breakdown-summary {
    display: flex;
    justify-content: center;
    gap: var(--space-8);
    padding: var(--space-4);
    background: var(--bg-tertiary);
    border-radius: var(--radius-md);
  }
  
  .summary-item {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  
  .summary-icon {
    font-size: 1.1em;
  }
  
  .summary-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  
  .summary-value {
    font-family: var(--font-mono);
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .summary-value.good {
    color: var(--success);
  }
  
  .summary-value.warning {
    color: var(--warning);
  }
  
  .summary-value.bad {
    color: var(--error);
  }
</style>
