<!--
  ObservatoryPanel — Main container for AI cognition visualizations (RFC-112)
  
  Five signature visualizations:
  1. ResonanceWave — Quality emergence through resonance iterations
  2. PrismFracture — Multi-perspective synthesis (harmonic candidates)
  3. MemoryLattice — Force-directed knowledge graph
  4. ExecutionCinema — Enhanced DAG with particle effects
  5. ModelParadox — Quality vs. cost comparison
-->
<script lang="ts">
  import { fade, fly } from 'svelte/transition';
  import ResonanceWave from './ResonanceWave.svelte';
  import PrismFracture from './PrismFracture.svelte';
  import MemoryLattice from './MemoryLattice.svelte';
  import ExecutionCinema from './ExecutionCinema.svelte';
  import ModelParadox from './ModelParadox.svelte';
  
  type Viz = 'resonance' | 'prism' | 'lattice' | 'cinema' | 'paradox';
  
  const visualizations = [
    { id: 'resonance' as const, icon: '📈', label: 'Resonance', desc: 'Quality emergence' },
    { id: 'prism' as const, icon: '🔮', label: 'Prism', desc: 'Multi-perspective' },
    { id: 'lattice' as const, icon: '🧠', label: 'Memory', desc: 'Knowledge graph' },
    { id: 'cinema' as const, icon: '🎬', label: 'Execution', desc: 'Live DAG' },
    { id: 'paradox' as const, icon: '⚡', label: 'Paradox', desc: 'Model comparison' },
  ];
  
  let activeViz = $state<Viz>('resonance');
  let isLive = $state(true);
</script>

<div class="observatory" in:fade={{ duration: 200 }}>
  <header class="observatory-header">
    <div class="title-section">
      <h1 class="title">🔭 Observatory</h1>
      <p class="subtitle">Watch AI cognition in real-time</p>
    </div>
    
    <div class="controls">
      <label class="live-toggle">
        <input type="checkbox" bind:checked={isLive} />
        <span class="toggle-label">Live</span>
        <span class="toggle-indicator" class:active={isLive}></span>
      </label>
      <button class="export-btn" title="Export as GIF">📹 Export</button>
    </div>
  </header>
  
  <nav class="viz-tabs">
    {#each visualizations as viz, i}
      <button
        class="viz-tab"
        class:active={activeViz === viz.id}
        onclick={() => activeViz = viz.id}
        in:fly={{ y: 20, delay: i * 50, duration: 200 }}
      >
        <span class="tab-icon">{viz.icon}</span>
        <span class="tab-label">{viz.label}</span>
        <span class="tab-desc">{viz.desc}</span>
      </button>
    {/each}
  </nav>
  
  <main class="viz-canvas">
    {#if activeViz === 'resonance'}
      <ResonanceWave {isLive} />
    {:else if activeViz === 'prism'}
      <PrismFracture {isLive} />
    {:else if activeViz === 'lattice'}
      <MemoryLattice {isLive} />
    {:else if activeViz === 'cinema'}
      <ExecutionCinema {isLive} />
    {:else if activeViz === 'paradox'}
      <ModelParadox />
    {/if}
  </main>
  
  <footer class="observatory-footer">
    <span class="branding">sunwell.ai</span>
  </footer>
</div>

<style>
  .observatory {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    padding: var(--space-6);
    padding-left: calc(var(--space-6) + 80px); /* Account for back button */
  }
  
  .observatory-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: var(--space-6);
  }
  
  .title {
    font-family: var(--font-serif);
    font-size: var(--text-3xl);
    color: var(--text-gold);
    margin: 0;
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  
  .subtitle {
    font-size: var(--text-sm);
    color: var(--text-tertiary);
    margin: var(--space-1) 0 0;
    font-family: var(--font-mono);
  }
  
  .controls {
    display: flex;
    gap: var(--space-3);
    align-items: center;
  }
  
  .live-toggle {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-sm);
    color: var(--text-secondary);
    cursor: pointer;
    padding: var(--space-2) var(--space-3);
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    border: 1px solid var(--border-subtle);
    transition: all var(--transition-fast);
  }
  
  .live-toggle:hover {
    border-color: var(--border-default);
  }
  
  .live-toggle input {
    display: none;
  }
  
  .toggle-label {
    font-family: var(--font-mono);
  }
  
  .toggle-indicator {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--text-tertiary);
    transition: all var(--transition-fast);
  }
  
  .toggle-indicator.active {
    background: var(--success);
    box-shadow: 0 0 8px var(--success);
    animation: pulse-live 2s ease-in-out infinite;
  }
  
  @keyframes pulse-live {
    0%, 100% { opacity: 1; box-shadow: 0 0 8px var(--success); }
    50% { opacity: 0.6; box-shadow: 0 0 4px var(--success); }
  }
  
  .export-btn {
    padding: var(--space-2) var(--space-4);
    background: var(--bg-secondary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    font-size: var(--text-sm);
    font-family: var(--font-mono);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  
  .export-btn:hover {
    background: var(--accent-hover);
    color: var(--text-gold);
    border-color: var(--border-emphasis);
  }
  
  .viz-tabs {
    display: flex;
    gap: var(--space-2);
    margin-bottom: var(--space-6);
  }
  
  .viz-tab {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-4);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  
  .viz-tab:hover {
    background: var(--bg-tertiary);
    border-color: var(--border-default);
  }
  
  .viz-tab.active {
    background: var(--accent-hover);
    border-color: var(--border-emphasis);
    box-shadow: var(--glow-gold-subtle);
  }
  
  .tab-icon {
    font-size: var(--text-2xl);
  }
  
  .tab-label {
    font-weight: 600;
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-primary);
  }
  
  .viz-tab.active .tab-label {
    color: var(--text-gold);
  }
  
  .tab-desc {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    font-family: var(--font-mono);
  }
  
  .viz-canvas {
    flex: 1;
    background: var(--bg-secondary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-lg);
    min-height: 500px;
    overflow: hidden;
    position: relative;
  }
  
  .observatory-footer {
    padding-top: var(--space-4);
    text-align: center;
  }
  
  .branding {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    font-family: var(--font-mono);
  }
</style>
