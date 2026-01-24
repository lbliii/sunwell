<!--
  ObservatoryPanel — Main container for AI cognition visualizations (RFC-112)
  
  Five signature visualizations:
  1. ResonanceWave — Quality emergence through resonance iterations
  2. PrismFracture — Multi-perspective synthesis (harmonic candidates)
  3. MemoryLattice — Force-directed knowledge graph
  4. ExecutionCinema — Enhanced DAG with particle effects
  5. ModelParadox — Quality vs. cost comparison
  
  Features:
  - Export to PNG/GIF/JSON
  - Shareable URLs
  - Mobile-responsive layout
-->
<script lang="ts">
  import { fade, fly, scale } from 'svelte/transition';
  import ResonanceWave from './ResonanceWave.svelte';
  import PrismFracture from './PrismFracture.svelte';
  import MemoryLattice from './MemoryLattice.svelte';
  import ExecutionCinema from './ExecutionCinema.svelte';
  import ModelParadox from './ModelParadox.svelte';
  import {
    exportAsPng,
    exportAsGif,
    exportAsJson,
    generateShareUrl,
    copyToClipboard,
    downloadBlob,
    type ExportProgress,
  } from '$lib/export';
  import { observatory } from '../../stores';
  
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
  
  // Export modal state
  let showExportModal = $state(false);
  let exportFormat = $state<'png' | 'gif' | 'json'>('png');
  let isExporting = $state(false);
  let exportProgress = $state<ExportProgress | null>(null);
  let exportError = $state<string | null>(null);
  
  // Share modal state
  let showShareModal = $state(false);
  let shareUrl = $state<string>('');
  let shareCopied = $state(false);
  
  // Canvas reference for export
  let canvasElement: HTMLElement;
  
  // Export functions
  async function handleExport() {
    if (!canvasElement || isExporting) return;
    
    isExporting = true;
    exportError = null;
    exportProgress = null;
    
    try {
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      const filename = `sunwell-${activeViz}-${timestamp}`;
      
      if (exportFormat === 'png') {
        await exportAsPng(canvasElement, `${filename}.png`);
        exportProgress = { phase: 'complete', progress: 100, message: 'PNG saved!' };
      } else if (exportFormat === 'gif') {
        const blob = await exportAsGif(
          canvasElement,
          { duration: 5, fps: 10, width: 720, height: 480 },
          (p) => { exportProgress = p; }
        );
        downloadBlob(blob, `${filename}.gif`);
      } else if (exportFormat === 'json') {
        // Export visualization data
        const data = getVisualizationData();
        exportAsJson(data, `${filename}.json`);
        exportProgress = { phase: 'complete', progress: 100, message: 'JSON saved!' };
      }
      
      // Close modal after success
      setTimeout(() => {
        if (exportProgress?.phase === 'complete') {
          showExportModal = false;
          exportProgress = null;
        }
      }, 1500);
    } catch (err) {
      exportError = err instanceof Error ? err.message : 'Export failed';
      exportProgress = null;
    } finally {
      isExporting = false;
    }
  }
  
  function getVisualizationData(): unknown {
    switch (activeViz) {
      case 'resonance':
        return observatory.resonanceWave;
      case 'prism':
        return observatory.prismFracture;
      case 'cinema':
        return observatory.executionCinema;
      case 'lattice':
        return observatory.memoryLattice;
      case 'paradox':
        return observatory.modelParadox;
      default:
        return {};
    }
  }
  
  // Share functions
  function handleShare() {
    const config = {
      visualization: activeViz,
      data: getVisualizationData(),
    };
    shareUrl = generateShareUrl(config);
    showShareModal = true;
    shareCopied = false;
  }
  
  async function copyShareUrl() {
    const success = await copyToClipboard(shareUrl);
    if (success) {
      shareCopied = true;
      setTimeout(() => shareCopied = false, 2000);
    }
  }
  
  function closeModals() {
    showExportModal = false;
    showShareModal = false;
    exportProgress = null;
    exportError = null;
  }
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
      
      <button class="control-btn share-btn" onclick={handleShare} title="Share visualization">
        🔗 Share
      </button>
      
      <button class="control-btn export-btn" onclick={() => showExportModal = true} title="Export visualization">
        📹 Export
      </button>
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
  
  <main class="viz-canvas" bind:this={canvasElement}>
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

<!-- Export Modal -->
{#if showExportModal}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
  <div class="modal-overlay" onclick={closeModals} in:fade={{ duration: 150 }} role="presentation">
    <div class="modal" onclick={(e) => e.stopPropagation()} in:scale={{ duration: 200, start: 0.95 }} role="dialog" aria-modal="true" aria-labelledby="export-modal-title" tabindex="-1">
      <div class="modal-header">
        <h2 id="export-modal-title">📹 Export Visualization</h2>
        <button class="close-btn" onclick={closeModals}>✕</button>
      </div>
      
      <div class="modal-body">
        <div class="format-selector">
          <label class="format-option">
            <input type="radio" bind:group={exportFormat} value="png" />
            <div class="format-card">
              <span class="format-icon">🖼️</span>
              <span class="format-name">PNG</span>
              <span class="format-desc">Single frame snapshot</span>
            </div>
          </label>
          
          <label class="format-option">
            <input type="radio" bind:group={exportFormat} value="gif" />
            <div class="format-card">
              <span class="format-icon">🎬</span>
              <span class="format-name">GIF</span>
              <span class="format-desc">5s animated capture</span>
            </div>
          </label>
          
          <label class="format-option">
            <input type="radio" bind:group={exportFormat} value="json" />
            <div class="format-card">
              <span class="format-icon">📄</span>
              <span class="format-name">JSON</span>
              <span class="format-desc">Raw data export</span>
            </div>
          </label>
        </div>
        
        {#if exportProgress}
          <div class="export-progress">
            <div class="progress-bar">
              <div class="progress-fill" style="width: {exportProgress.progress}%"></div>
            </div>
            <span class="progress-text">{exportProgress.message}</span>
          </div>
        {/if}
        
        {#if exportError}
          <div class="export-error">
            ❌ {exportError}
          </div>
        {/if}
      </div>
      
      <div class="modal-footer">
        <button class="btn secondary" onclick={closeModals}>Cancel</button>
        <button 
          class="btn primary" 
          onclick={handleExport}
          disabled={isExporting}
        >
          {isExporting ? 'Exporting...' : `Export ${exportFormat.toUpperCase()}`}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Share Modal -->
{#if showShareModal}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
  <div class="modal-overlay" onclick={closeModals} in:fade={{ duration: 150 }} role="presentation">
    <div class="modal" onclick={(e) => e.stopPropagation()} in:scale={{ duration: 200, start: 0.95 }} role="dialog" aria-modal="true" aria-labelledby="share-modal-title" tabindex="-1">
      <div class="modal-header">
        <h2 id="share-modal-title">🔗 Share Visualization</h2>
        <button class="close-btn" onclick={closeModals}>✕</button>
      </div>
      
      <div class="modal-body">
        <p class="share-hint">Copy this link to share the current visualization:</p>
        
        <div class="share-url-container">
          <input 
            type="text" 
            readonly 
            value={shareUrl} 
            class="share-url-input"
            onclick={(e) => (e.target as HTMLInputElement).select()}
          />
          <button class="copy-btn" onclick={copyShareUrl}>
            {shareCopied ? '✓ Copied!' : '📋 Copy'}
          </button>
        </div>
        
        <div class="share-social">
          <span class="social-label">Share on:</span>
          <a 
            href="https://twitter.com/intent/tweet?text=Check%20out%20this%20AI%20cognition%20visualization%20from%20Sunwell!&url={encodeURIComponent(shareUrl)}"
            target="_blank"
            rel="noopener"
            class="social-btn twitter"
          >
            𝕏 Twitter
          </a>
          <a 
            href="https://www.reddit.com/submit?url={encodeURIComponent(shareUrl)}&title=AI%20Cognition%20Visualization%20%5BOC%5D"
            target="_blank"
            rel="noopener"
            class="social-btn reddit"
          >
            🔴 Reddit
          </a>
        </div>
      </div>
      
      <div class="modal-footer">
        <button class="btn secondary" onclick={closeModals}>Close</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .observatory {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    padding: var(--space-6);
    padding-left: calc(var(--space-6) + 80px); /* Account for back button */
  }
  
  /* Mobile responsive */
  @media (max-width: 768px) {
    .observatory {
      padding: var(--space-4);
      padding-left: var(--space-4);
      padding-top: calc(var(--space-4) + 48px); /* Account for back button */
    }
  }
  
  .observatory-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: var(--space-6);
    flex-wrap: wrap;
    gap: var(--space-4);
  }
  
  @media (max-width: 768px) {
    .observatory-header {
      flex-direction: column;
      align-items: stretch;
    }
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
  
  @media (max-width: 768px) {
    .title {
      font-size: var(--text-2xl);
    }
  }
  
  .subtitle {
    font-size: var(--text-sm);
    color: var(--text-tertiary);
    margin: var(--space-1) 0 0;
    font-family: var(--font-mono);
  }
  
  .controls {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    flex-wrap: wrap;
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
  
  .control-btn {
    padding: var(--space-2) var(--space-4);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    font-size: var(--text-sm);
    font-family: var(--font-mono);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  
  .control-btn:hover {
    background: var(--bg-tertiary);
    color: var(--text-primary);
    border-color: var(--border-default);
  }
  
  .export-btn:hover {
    color: var(--text-gold);
    border-color: var(--ui-gold-40);
  }
  
  .share-btn:hover {
    color: var(--info);
    border-color: var(--info);
  }
  
  .viz-tabs {
    display: flex;
    gap: var(--space-2);
    margin-bottom: var(--space-6);
    overflow-x: auto;
    padding-bottom: var(--space-2);
  }
  
  @media (max-width: 768px) {
    .viz-tabs {
      gap: var(--space-1);
    }
  }
  
  .viz-tab {
    flex: 1;
    min-width: 100px;
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
  
  @media (max-width: 768px) {
    .viz-tab {
      padding: var(--space-2) var(--space-3);
      min-width: 70px;
    }
    
    .tab-desc {
      display: none;
    }
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
  
  @media (max-width: 768px) {
    .tab-icon {
      font-size: var(--text-lg);
    }
  }
  
  .tab-label {
    font-weight: 600;
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-primary);
  }
  
  @media (max-width: 768px) {
    .tab-label {
      font-size: var(--text-xs);
    }
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
  
  @media (max-width: 768px) {
    .viz-canvas {
      min-height: 400px;
    }
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
  
  /* Modal Styles */
  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.8);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
    padding: var(--space-4);
  }
  
  .modal {
    background: var(--bg-secondary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-lg);
    width: 100%;
    max-width: 480px;
    overflow: hidden;
  }
  
  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-4);
    border-bottom: 1px solid var(--border-subtle);
  }
  
  .modal-header h2 {
    font-family: var(--font-serif);
    font-size: var(--text-lg);
    color: var(--text-primary);
    margin: 0;
  }
  
  .close-btn {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: none;
    border: none;
    color: var(--text-tertiary);
    cursor: pointer;
    font-size: var(--text-lg);
    transition: color var(--transition-fast);
  }
  
  .close-btn:hover {
    color: var(--text-primary);
  }
  
  .modal-body {
    padding: var(--space-4);
  }
  
  .modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-2);
    padding: var(--space-4);
    border-top: 1px solid var(--border-subtle);
  }
  
  /* Export Format Selector */
  .format-selector {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--space-2);
    margin-bottom: var(--space-4);
  }
  
  .format-option {
    cursor: pointer;
  }
  
  .format-option input {
    display: none;
  }
  
  .format-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-3);
    background: var(--bg-primary);
    border: 2px solid var(--border-subtle);
    border-radius: var(--radius-md);
    transition: all var(--transition-fast);
  }
  
  .format-option input:checked + .format-card {
    border-color: var(--ui-gold);
    background: var(--ui-gold-10);
  }
  
  .format-option:hover .format-card {
    border-color: var(--border-default);
  }
  
  .format-icon {
    font-size: var(--text-2xl);
  }
  
  .format-name {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .format-desc {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    text-align: center;
  }
  
  /* Export Progress */
  .export-progress {
    margin-top: var(--space-4);
  }
  
  .progress-bar {
    height: 8px;
    background: var(--bg-primary);
    border-radius: var(--radius-sm);
    overflow: hidden;
    margin-bottom: var(--space-2);
  }
  
  .progress-fill {
    height: 100%;
    background: var(--gradient-ui-gold);
    transition: width 0.3s ease-out;
  }
  
  .progress-text {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-secondary);
  }
  
  .export-error {
    margin-top: var(--space-4);
    padding: var(--space-3);
    background: rgba(var(--error-rgb), 0.1);
    border: 1px solid var(--error);
    border-radius: var(--radius-md);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--error);
  }
  
  /* Share Modal */
  .share-hint {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-secondary);
    margin: 0 0 var(--space-3);
  }
  
  .share-url-container {
    display: flex;
    gap: var(--space-2);
  }
  
  .share-url-input {
    flex: 1;
    padding: var(--space-2) var(--space-3);
    background: var(--bg-primary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-primary);
  }
  
  .copy-btn {
    padding: var(--space-2) var(--space-3);
    background: var(--ui-gold-15);
    border: 1px solid var(--ui-gold-40);
    border-radius: var(--radius-md);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-gold);
    cursor: pointer;
    transition: all var(--transition-fast);
    white-space: nowrap;
  }
  
  .copy-btn:hover {
    background: var(--ui-gold-40);
  }
  
  .share-social {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-top: var(--space-4);
  }
  
  .social-label {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-tertiary);
  }
  
  .social-btn {
    padding: var(--space-2) var(--space-3);
    background: var(--bg-primary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-secondary);
    text-decoration: none;
    transition: all var(--transition-fast);
  }
  
  .social-btn:hover {
    border-color: var(--border-default);
    color: var(--text-primary);
  }
  
  .social-btn.twitter:hover {
    border-color: #1da1f2;
    color: #1da1f2;
  }
  
  .social-btn.reddit:hover {
    border-color: #ff4500;
    color: #ff4500;
  }
  
  /* Buttons */
  .btn {
    padding: var(--space-2) var(--space-4);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: 600;
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  
  .btn.primary {
    background: var(--gradient-ui-gold);
    border: none;
    color: var(--bg-primary);
  }
  
  .btn.primary:hover:not(:disabled) {
    box-shadow: var(--glow-gold);
    transform: translateY(-1px);
  }
  
  .btn.primary:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  
  .btn.secondary {
    background: var(--bg-primary);
    border: 1px solid var(--border-subtle);
    color: var(--text-secondary);
  }
  
  .btn.secondary:hover {
    border-color: var(--border-default);
    color: var(--text-primary);
  }
</style>
