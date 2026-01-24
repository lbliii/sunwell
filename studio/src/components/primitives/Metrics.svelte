<!--
  Metrics Primitive (RFC-072, RFC-097)
  
  Progress/velocity widget with animated counters and visual indicators.
  
  RFC-097 Enhancement:
  - Animated number counters with spring physics
  - Multiple metric cards
  - Trend indicators (up/down/stable)
  - Progress bars for bounded metrics
  - Holy Light design tokens
-->
<script lang="ts">
  import { spring } from 'svelte/motion';
  import { fade, fly } from 'svelte/transition';
  import type { PrimitiveProps } from './types';
  
  interface Metric {
    id: string;
    label: string;
    value: number;
    format?: 'number' | 'percent' | 'duration' | 'bytes';
    max?: number;           // For progress bar display
    trend?: 'up' | 'down' | 'stable';
    trendValue?: number;    // e.g., +15% or -3
    icon?: string;
  }
  
  interface Props extends PrimitiveProps {
    metrics?: Metric[];
    layout?: 'grid' | 'row' | 'stack';
  }
  
  let { 
    size, 
    metrics = [
      { id: 'tasks', label: 'Tasks Complete', value: 0, icon: '✓' },
    ],
    layout = 'grid',
  }: Props = $props();
  
  // Reactive state for animated values (keyed by metric id)
  let animatedState: Record<string, number> = $state({});
  
  // Spring stores (created once, updated reactively)
  const springs = new Map<string, ReturnType<typeof spring<number>>>();
  
  // Update springs when metrics change
  $effect(() => {
    for (const metric of metrics) {
      if (!springs.has(metric.id)) {
        const s = spring(metric.value, { stiffness: 0.08, damping: 0.5 });
        springs.set(metric.id, s);
        // Subscribe to update state
        s.subscribe((v) => {
          animatedState[metric.id] = v;
        });
      } else {
        springs.get(metric.id)!.set(metric.value);
      }
    }
  });
  
  // Get animated value for a metric (reads from reactive state)
  function getAnimatedValue(metricId: string, fallback: number): number {
    return animatedState[metricId] ?? fallback;
  }
  
  // Format value based on format type
  function formatValue(value: number, format?: Metric['format']): string {
    switch (format) {
      case 'percent':
        return `${Math.round(value)}%`;
      case 'duration':
        if (value < 60) return `${value.toFixed(1)}s`;
        const mins = Math.floor(value / 60);
        const secs = Math.round(value % 60);
        return `${mins}m ${secs}s`;
      case 'bytes':
        if (value < 1024) return `${value}B`;
        if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)}KB`;
        return `${(value / (1024 * 1024)).toFixed(1)}MB`;
      default:
        if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
        if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
        return Math.round(value).toLocaleString();
    }
  }
  
  // Get trend icon
  function getTrendIcon(trend?: Metric['trend']): string {
    switch (trend) {
      case 'up': return '↑';
      case 'down': return '↓';
      default: return '→';
    }
  }
  
  // Get trend color
  function getTrendColor(trend?: Metric['trend']): string {
    switch (trend) {
      case 'up': return 'var(--success)';
      case 'down': return 'var(--error)';
      default: return 'var(--text-tertiary)';
    }
  }
</script>

<div class="metrics" data-size={size} data-layout={layout} in:fade={{ duration: 150 }}>
  {#each metrics as metric, i (metric.id)}
    {@const animatedValue = getAnimatedValue(metric.id, metric.value)}
    <div 
      class="metric-card" 
      in:fly={{ y: 20, delay: i * 50, duration: 200 }}
    >
      <div class="metric-header">
        {#if metric.icon}
          <span class="metric-icon">{metric.icon}</span>
        {/if}
        <span class="metric-label">{metric.label}</span>
      </div>
      
      <div class="metric-value">
        <span class="value">{formatValue(animatedValue, metric.format)}</span>
        {#if metric.trend}
          <span class="trend" style:color={getTrendColor(metric.trend)}>
            <span class="trend-icon">{getTrendIcon(metric.trend)}</span>
            {#if metric.trendValue !== undefined}
              <span class="trend-value">
                {metric.trend === 'up' ? '+' : ''}{metric.trendValue}
                {metric.format === 'percent' ? 'pp' : ''}
              </span>
            {/if}
          </span>
        {/if}
      </div>
      
      {#if metric.max}
        <div class="metric-progress">
          <div class="progress-track">
            <div 
              class="progress-fill"
              style:width="{Math.min(100, (animatedValue / metric.max) * 100)}%"
            ></div>
          </div>
          <span class="progress-label">
            {formatValue(animatedValue, metric.format)} / {formatValue(metric.max, metric.format)}
          </span>
        </div>
      {/if}
    </div>
  {/each}
</div>

<style>
  .metrics {
    height: 100%;
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    padding: var(--space-4);
    display: grid;
    gap: var(--space-4);
  }
  
  /* Layout variants */
  .metrics[data-layout="grid"] {
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    align-content: start;
  }
  
  .metrics[data-layout="row"] {
    grid-auto-flow: column;
    grid-auto-columns: 1fr;
    align-items: center;
  }
  
  .metrics[data-layout="stack"] {
    grid-template-columns: 1fr;
  }
  
  .metric-card {
    background: var(--bg-primary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: var(--space-4);
    transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
  }
  
  .metric-card:hover {
    border-color: var(--border-default);
    box-shadow: var(--glow-gold-subtle);
  }
  
  .metric-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-2);
  }
  
  .metric-icon {
    font-size: var(--text-base);
    opacity: 0.8;
  }
  
  .metric-label {
    font-size: var(--text-xs);
    font-weight: 500;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  
  .metric-value {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
  }
  
  .value {
    font-family: var(--font-mono);
    font-size: var(--text-2xl);
    font-weight: 600;
    color: var(--text-gold);
    font-variant-numeric: tabular-nums;
  }
  
  .trend {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    font-size: var(--text-xs);
    font-weight: 500;
  }
  
  .trend-icon {
    font-size: var(--text-sm);
  }
  
  .trend-value {
    font-family: var(--font-mono);
  }
  
  .metric-progress {
    margin-top: var(--space-3);
  }
  
  .progress-track {
    height: 4px;
    background: var(--bg-tertiary);
    border-radius: var(--radius-full);
    overflow: hidden;
  }
  
  .progress-fill {
    height: 100%;
    background: var(--gradient-progress);
    border-radius: var(--radius-full);
    transition: width 0.3s ease-out;
    position: relative;
  }
  
  /* Shimmer effect on progress */
  .progress-fill::after {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(
      90deg,
      transparent,
      rgba(255, 255, 255, 0.15),
      transparent
    );
    animation: shimmer 2s infinite;
  }
  
  .progress-label {
    display: block;
    margin-top: var(--space-1);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    font-family: var(--font-mono);
    text-align: right;
  }
  
  /* Size variants */
  .metrics[data-size="sm"] .value {
    font-size: var(--text-xl);
  }
  
  .metrics[data-size="sm"] .metric-card {
    padding: var(--space-3);
  }
  
  .metrics[data-size="lg"] .value {
    font-size: var(--text-3xl);
  }
</style>
