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
    background: var(--bg-secondary);
    border-radius: var(--radius-lg);
    padding: var(--space-5);
    border: 1px solid var(--border-default);
    font-family: var(--font-sans);
  }
  
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-4);
  }
  
  h3 {
    margin: 0;
    font-size: 1em;
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .recommendation {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    font-size: 0.85em;
  }
  
  .rec-label {
    color: var(--text-secondary);
  }
  
  .rec-model {
    color: var(--success);
    font-weight: 600;
  }
  
  .empty-state {
    text-align: center;
    padding: var(--space-8) var(--space-4);
    color: var(--text-secondary);
  }
  
  .empty-icon {
    font-size: 2em;
    margin-bottom: var(--space-3);
    opacity: 0.5;
  }
  
  .empty-state p {
    margin: var(--space-1) 0;
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
    padding: var(--space-2) var(--space-3);
    font-weight: 600;
    color: var(--text-secondary);
    font-size: 0.8em;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid var(--border-default);
  }
  
  td {
    padding: var(--space-2) var(--space-3);
    color: var(--text-primary);
    border-bottom: 1px solid var(--border-subtle);
    font-variant-numeric: tabular-nums;
  }
  
  tr:last-child td {
    border-bottom: none;
  }
  
  tr.recommended {
    background: var(--success-bg);
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
    margin-left: var(--space-1);
    font-size: 0.9em;
  }
  
  /* Speed indicators */
  .speed-fast {
    color: var(--success);
  }
  
  .speed-medium {
    color: var(--warning);
  }
  
  .speed-slow {
    color: var(--text-secondary);
  }

  /* Quality indicators */
  .quality-high {
    color: var(--success);
  }
  
  .quality-medium {
    color: var(--warning);
  }
  
  .quality-low {
    color: var(--error);
  }
  
  .footnote {
    margin-top: var(--space-3);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  /* Responsive */
  @media (max-width: 480px) {
    .header {
      flex-direction: column;
      align-items: flex-start;
      gap: var(--space-2);
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
