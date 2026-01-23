<!--
  LensSparkline — Usage activity visualization (RFC-100)
  
  A tiny SVG line chart showing lens usage over time.
-->
<script lang="ts">
  interface Props {
    data: number[];
    width?: number;
    height?: number;
  }
  
  let { data, width = 50, height = 16 }: Props = $props();
  
  const points = $derived.by(() => {
    if (!data.length) return '';
    const max = Math.max(...data, 1);
    const step = width / Math.max(data.length - 1, 1);
    return data
      .map((v, i) => `${i * step},${height - (v / max) * (height - 2) - 1}`)
      .join(' ');
  });
  
  const trend = $derived.by(() => {
    if (data.length < 2) return 'neutral';
    const recent = data.slice(-3);
    const earlier = data.slice(0, 3);
    const recentAvg = recent.reduce((a, b) => a + b, 0) / recent.length;
    const earlierAvg = earlier.reduce((a, b) => a + b, 0) / earlier.length;
    if (recentAvg > earlierAvg * 1.2) return 'up';
    if (recentAvg < earlierAvg * 0.8) return 'down';
    return 'neutral';
  });
</script>

{#if data.length > 1}
  <svg 
    class="sparkline"
    class:trend-up={trend === 'up'}
    class:trend-down={trend === 'down'}
    viewBox="0 0 {width} {height}"
    width={width}
    height={height}
    aria-label="Usage trend"
  >
    <polyline
      fill="none"
      stroke="currentColor"
      stroke-width="1.5"
      stroke-linecap="round"
      stroke-linejoin="round"
      points={points}
    />
    <!-- Dot at the end -->
    {#if data.length > 0}
      {@const lastX = (data.length - 1) * (width / Math.max(data.length - 1, 1))}
      {@const lastY = height - (data[data.length - 1] / Math.max(...data, 1)) * (height - 2) - 1}
      <circle
        cx={lastX}
        cy={lastY}
        r="2"
        fill="currentColor"
      />
    {/if}
  </svg>
{:else}
  <span class="no-data">—</span>
{/if}

<style>
  .sparkline {
    display: block;
    color: var(--ui-gold-soft);
  }
  
  .sparkline.trend-up {
    color: var(--success);
  }
  
  .sparkline.trend-down {
    color: var(--text-tertiary);
  }
  
  .no-data {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
</style>
