<!--
  ModelComparisonBlock.svelte — Model Discovery (RFC-081)
  
  Helps users discover which models work best for their hardware.
  Shows empirical performance data collected during actual usage:
  - Tokens per second
  - Time to first token
  - Gate pass rate (quality proxy)
  - Combined quality/speed score
  
  Users naturally learn which models suit their workflow:
  "gpt-oss:20b gives amazing thinking but 15 tok/s on my M2"
  "gemma3:4b is 80 tok/s but shallow reasoning"
-->
<script lang="ts">
  import { fade, fly } from 'svelte/transition';
  import type { ModelMetrics } from '$lib/inference';

  interface Props {
    models?: ModelMetrics[];
    title?: string;
    showRecommendation?: boolean;
  }

  let {
    models = [],
    title = "Your Model Performance",
    showRecommendation = true
  }: Props = $props();
  
  // Sort models by quality-speed score (best first)
  const sortedModels = $derived([...models].sort((a, b) => {
    const scoreA = getQualitySpeedScore(a);
    const scoreB = getQualitySpeedScore(b);
    return scoreB - scoreA;
  }));
  
  // Get recommended model (highest quality-speed score with enough data)
  const recommendedModel = $derived(sortedModels.find(m => m.taskCount >= 5) || null);
  
  function getQualitySpeedScore(m: ModelMetrics): number {
    const speedNormalized = Math.min(1.0, m.avgTokPerSec / 100);
    const quality = m.gatePassRate ?? 0.5; // Default 50% if no data
    return quality * speedNormalized;
  }
  
  function formatSpeed(tps: number): string {
    return `${tps.toFixed(0)} tok/s`;
  }
  
  function formatTtft(ms: number): string {
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }
  
  function formatQuality(rate: number | null): string {
    if (rate === null) return '--';
    return `${(rate * 100).toFixed(0)}%`;
  }
  
  function getSpeedClass(tps: number): string {
    if (tps >= 60) return 'speed-fast';
    if (tps >= 30) return 'speed-medium';
    return 'speed-slow';
  }
  
  function getQualityClass(rate: number | null): string {
    if (rate === null) return '';
    if (rate >= 0.9) return 'quality-high';
    if (rate >= 0.7) return 'quality-medium';
    return 'quality-low';
  }
</script>

<div class="model-comparison" in:fly={{ y: 20, duration: 300 }}>
  <div class="header">
    <h3>{title}</h3>
    {#if recommendedModel && showRecommendation}
      <div class="recommendation" in:fade>
        <span class="rec-label">Recommended:</span>
        <span class="rec-model">{recommendedModel.name}</span>
      </div>
    {/if}
  </div>
  
  {#if models.length === 0}
    <div class="empty-state">
      <div class="empty-icon">📊</div>
      <p>No model data yet.</p>
      <p class="hint">Performance metrics will appear as you use different models.</p>
    </div>
  {:else}
    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th class="col-model">Model</th>
            <th class="col-speed">Speed</th>
            <th class="col-ttft">TTFT</th>
            <th class="col-tasks">Tasks</th>
            <th class="col-quality">Quality*</th>
          </tr>
        </thead>
        <tbody>
          {#each sortedModels as model, i (model.name)}
            <tr 
              class:recommended={model === recommendedModel}
              in:fly={{ y: 10, delay: i * 50, duration: 200 }}
            >
              <td class="col-model">
                <span class="model-name">{model.name}</span>
                {#if model === recommendedModel}
                  <span class="badge">⭐</span>
                {/if}
              </td>
              <td class="col-speed {getSpeedClass(model.avgTokPerSec)}">
                {formatSpeed(model.avgTokPerSec)}
              </td>
              <td class="col-ttft">
                {formatTtft(model.avgTtft)}
              </td>
              <td class="col-tasks">
                {model.taskCount}
              </td>
              <td class="col-quality {getQualityClass(model.gatePassRate)}">
                {formatQuality(model.gatePassRate)}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    
    <p class="footnote">*Quality = gate pass rate (syntax, lint, type checks)</p>
  {/if}
</div>

<style>
  .model-comparison {
    background: var(--surface-2, #1a1a2e);
    border-radius: 12px;
    padding: 20px;
    border: 1px solid var(--border, #2d2d44);
    font-family: var(--font-sans, system-ui, sans-serif);
  }
  
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
  }
  
  h3 {
    margin: 0;
    font-size: 1em;
    font-weight: 600;
    color: var(--text, #e2e8f0);
  }
  
  .recommendation {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.85em;
  }
  
  .rec-label {
    color: var(--text-muted, #94a3b8);
  }
  
  .rec-model {
    color: var(--success, #10b981);
    font-weight: 600;
  }
  
  .empty-state {
    text-align: center;
    padding: 32px 16px;
    color: var(--text-muted, #94a3b8);
  }
  
  .empty-icon {
    font-size: 2em;
    margin-bottom: 12px;
    opacity: 0.5;
  }
  
  .empty-state p {
    margin: 4px 0;
  }
  
  .hint {
    font-size: 0.85em;
    opacity: 0.7;
  }
  
  .table-container {
    overflow-x: auto;
  }
  
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9em;
  }
  
  th {
    text-align: left;
    padding: 8px 12px;
    font-weight: 600;
    color: var(--text-muted, #94a3b8);
    font-size: 0.8em;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid var(--border, #2d2d44);
  }
  
  td {
    padding: 10px 12px;
    color: var(--text, #e2e8f0);
    border-bottom: 1px solid var(--border, #2d2d44);
    font-variant-numeric: tabular-nums;
  }
  
  tr:last-child td {
    border-bottom: none;
  }
  
  tr.recommended {
    background: rgba(16, 185, 129, 0.1);
  }
  
  .col-model {
    min-width: 120px;
  }
  
  .col-speed,
  .col-ttft,
  .col-tasks,
  .col-quality {
    text-align: right;
    white-space: nowrap;
  }
  
  .model-name {
    font-weight: 500;
  }
  
  .badge {
    margin-left: 6px;
    font-size: 0.9em;
  }
  
  /* Speed indicators */
  .speed-fast {
    color: var(--success, #10b981);
  }
  
  .speed-medium {
    color: var(--warning, #f59e0b);
  }
  
  .speed-slow {
    color: var(--text-muted, #94a3b8);
  }
  
  /* Quality indicators */
  .quality-high {
    color: var(--success, #10b981);
  }
  
  .quality-medium {
    color: var(--warning, #f59e0b);
  }
  
  .quality-low {
    color: var(--error, #ef4444);
  }
  
  .footnote {
    margin-top: 12px;
    font-size: 0.75em;
    color: var(--text-muted, #94a3b8);
    opacity: 0.7;
  }
  
  /* Responsive */
  @media (max-width: 480px) {
    .header {
      flex-direction: column;
      align-items: flex-start;
      gap: 8px;
    }
    
    .col-ttft {
      display: none;
    }
    
    th.col-ttft,
    td.col-ttft {
      display: none;
    }
  }
</style>
