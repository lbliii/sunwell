<!--
  Chart Primitive (RFC-072, RFC-097)
  
  SVG-based data visualizations with Holy Light colors.
  
  RFC-097 Enhancement:
  - Line, bar, and area chart types
  - Animated data points
  - Tooltips on hover
  - Holy Light color palette
  - Responsive SVG rendering
-->
<script lang="ts">
  import { fade } from 'svelte/transition';
  import type { DataPrimitiveProps } from './types';
  
  interface DataPoint {
    label: string;
    value: number;
    color?: string;
  }
  
  interface Props extends DataPrimitiveProps {
    data?: DataPoint[];
    chartType?: 'line' | 'bar' | 'area' | 'sparkline';
    title?: string;
    showLabels?: boolean;
    showValues?: boolean;
    animated?: boolean;
  }
  
  let { 
    size, 
    data = [],
    chartType = 'bar',
    title = '',
    showLabels = true,
    showValues = true,
    animated = true,
  }: Props = $props();
  
  // Chart dimensions
  const padding = { top: 20, right: 20, bottom: 40, left: 50 };
  let containerWidth = $state(400);
  let containerHeight = $state(200);
  
  // Calculate chart area
  const chartWidth = $derived(containerWidth - padding.left - padding.right);
  const chartHeight = $derived(containerHeight - padding.top - padding.bottom);
  
  // Calculate scales
  const maxValue = $derived(Math.max(...data.map(d => d.value), 1));
  const minValue = $derived(Math.min(...data.map(d => d.value), 0));
  const valueRange = $derived(maxValue - minValue || 1);
  
  // Scale functions
  function scaleX(index: number): number {
    if (data.length <= 1) return chartWidth / 2;
    return (index / (data.length - 1)) * chartWidth;
  }
  
  function scaleY(value: number): number {
    return chartHeight - ((value - minValue) / valueRange) * chartHeight;
  }
  
  // Bar width for bar charts
  const barWidth = $derived(data.length > 0 ? Math.max(8, (chartWidth / data.length) * 0.7) : 20);
  const barGap = $derived(data.length > 0 ? (chartWidth - (barWidth * data.length)) / (data.length + 1) : 10);
  
  // Line path for line/area charts
  const linePath = $derived(() => {
    if (data.length === 0) return '';
    return data.map((d, i) => {
      const x = scaleX(i);
      const y = scaleY(d.value);
      return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
    }).join(' ');
  });
  
  // Area path (line + bottom fill)
  const areaPath = $derived(() => {
    if (data.length === 0) return '';
    const line = linePath();
    const lastX = scaleX(data.length - 1);
    const firstX = scaleX(0);
    return `${line} L ${lastX} ${chartHeight} L ${firstX} ${chartHeight} Z`;
  });
  
  // Holy Light chart colors
  const chartColors = [
    'var(--ui-gold)',
    'var(--ui-gold-soft)',
    'var(--success)',
    'var(--info)',
    'var(--warning)',
    'var(--error)',
  ];
  
  function getColor(index: number, explicit?: string): string {
    return explicit || chartColors[index % chartColors.length];
  }
  
  // Hover state
  let hoveredIndex = $state<number | null>(null);
  
  // Y-axis ticks
  const yTicks = $derived(() => {
    const tickCount = 5;
    const ticks: number[] = [];
    for (let i = 0; i <= tickCount; i++) {
      ticks.push(minValue + (valueRange * i) / tickCount);
    }
    return ticks;
  });
  
  // Format value for display
  function formatValue(value: number): string {
    if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
    if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
    return value.toFixed(value % 1 === 0 ? 0 : 1);
  }
</script>

<div 
  class="chart" 
  data-size={size}
  bind:clientWidth={containerWidth}
  bind:clientHeight={containerHeight}
  in:fade={{ duration: 150 }}
>
  {#if title}
    <div class="chart-header">
      <span class="chart-title">{title}</span>
    </div>
  {/if}
  
  <div class="chart-content">
    {#if data.length === 0}
      <div class="empty-state">
        <span class="empty-icon">📊</span>
        <p class="empty-text">No chart data</p>
      </div>
    {:else}
      <svg 
        class="chart-svg" 
        viewBox="0 0 {containerWidth} {containerHeight}"
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <!-- Gradient for area fill -->
          <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="var(--ui-gold)" stop-opacity="0.3" />
            <stop offset="100%" stop-color="var(--ui-gold)" stop-opacity="0.05" />
          </linearGradient>
          
          <!-- Glow filter for hover -->
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
        </defs>
        
        <g transform="translate({padding.left}, {padding.top})">
          <!-- Y-axis grid lines -->
          {#each yTicks() as tick}
            <line 
              x1="0" 
              y1={scaleY(tick)} 
              x2={chartWidth} 
              y2={scaleY(tick)}
              class="grid-line"
              class:zero={tick === 0}
            />
            <text 
              x="-8" 
              y={scaleY(tick)}
              class="axis-label"
              dominant-baseline="middle"
              text-anchor="end"
            >
              {formatValue(tick)}
            </text>
          {/each}
          
          <!-- Bar chart -->
          {#if chartType === 'bar'}
            {#each data as point, i}
              {@const barHeight = Math.max(2, ((point.value - minValue) / valueRange) * chartHeight)}
              {@const x = barGap + (i * (barWidth + barGap))}
              {@const y = chartHeight - barHeight}
              
              <g 
                class="bar-group"
                class:hovered={hoveredIndex === i}
                role="img"
                aria-label="{point.label}: {formatValue(point.value)}"
                onmouseenter={() => hoveredIndex = i}
                onmouseleave={() => hoveredIndex = null}
              >
                <rect
                  x={x}
                  y={animated ? chartHeight : y}
                  width={barWidth}
                  height={animated ? 0 : barHeight}
                  fill={getColor(i, point.color)}
                  rx="4"
                  class="bar"
                  style:transform={animated ? `scaleY(${barHeight / chartHeight || 0})` : 'none'}
                  style:transform-origin="bottom"
                  style:transition={animated ? `transform 0.5s ease-out ${i * 0.05}s` : 'none'}
                >
                  <!-- Animate on mount -->
                  {#if animated}
                    <animate 
                      attributeName="y" 
                      from={chartHeight} 
                      to={y} 
                      dur="0.5s" 
                      fill="freeze"
                      begin={`${i * 0.05}s`}
                    />
                    <animate 
                      attributeName="height" 
                      from="0" 
                      to={barHeight} 
                      dur="0.5s" 
                      fill="freeze"
                      begin={`${i * 0.05}s`}
                    />
                  {/if}
                </rect>
                
                <!-- Value label on hover -->
                {#if hoveredIndex === i && showValues}
                  <text 
                    x={x + barWidth / 2}
                    y={y - 8}
                    class="value-label"
                    text-anchor="middle"
                  >
                    {formatValue(point.value)}
                  </text>
                {/if}
                
                <!-- X-axis label -->
                {#if showLabels}
                  <text 
                    x={x + barWidth / 2}
                    y={chartHeight + 20}
                    class="x-label"
                    text-anchor="middle"
                  >
                    {point.label}
                  </text>
                {/if}
              </g>
            {/each}
          {/if}
          
          <!-- Line chart -->
          {#if chartType === 'line' || chartType === 'sparkline'}
            <path 
              d={linePath()}
              fill="none"
              stroke="var(--ui-gold)"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              class="line"
            />
            
            <!-- Data points -->
            {#if chartType === 'line'}
              {#each data as point, i}
                <circle
                  cx={scaleX(i)}
                  cy={scaleY(point.value)}
                  r={hoveredIndex === i ? 6 : 4}
                  fill="var(--bg-primary)"
                  stroke={getColor(i, point.color)}
                  stroke-width="2"
                  class="data-point"
                  class:hovered={hoveredIndex === i}
                  role="img"
                  aria-label="{point.label}: {formatValue(point.value)}"
                  onmouseenter={() => hoveredIndex = i}
                  onmouseleave={() => hoveredIndex = null}
                />
                
                {#if hoveredIndex === i && showValues}
                  <text 
                    x={scaleX(i)}
                    y={scaleY(point.value) - 12}
                    class="value-label"
                    text-anchor="middle"
                  >
                    {formatValue(point.value)}
                  </text>
                {/if}
                
                {#if showLabels}
                  <text 
                    x={scaleX(i)}
                    y={chartHeight + 20}
                    class="x-label"
                    text-anchor="middle"
                  >
                    {point.label}
                  </text>
                {/if}
              {/each}
            {/if}
          {/if}
          
          <!-- Area chart -->
          {#if chartType === 'area'}
            <path 
              d={areaPath()}
              fill="url(#areaGradient)"
              class="area"
            />
            <path 
              d={linePath()}
              fill="none"
              stroke="var(--ui-gold)"
              stroke-width="2"
              class="line"
            />
            
            {#each data as point, i}
              <circle
                cx={scaleX(i)}
                cy={scaleY(point.value)}
                r={hoveredIndex === i ? 6 : 4}
                fill="var(--bg-primary)"
                stroke="var(--ui-gold)"
                stroke-width="2"
                class="data-point"
                class:hovered={hoveredIndex === i}
                role="img"
                aria-label="{point.label}: {formatValue(point.value)}"
                onmouseenter={() => hoveredIndex = i}
                onmouseleave={() => hoveredIndex = null}
              />
              
              {#if hoveredIndex === i && showValues}
                <text 
                  x={scaleX(i)}
                  y={scaleY(point.value) - 12}
                  class="value-label"
                  text-anchor="middle"
                >
                  {formatValue(point.value)}
                </text>
              {/if}
              
              {#if showLabels}
                <text 
                  x={scaleX(i)}
                  y={chartHeight + 20}
                  class="x-label"
                  text-anchor="middle"
                >
                  {point.label}
                </text>
              {/if}
            {/each}
          {/if}
        </g>
      </svg>
    {/if}
  </div>
</div>

<style>
  .chart {
    height: 100%;
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  
  .chart-header {
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--border-subtle);
  }
  
  .chart-title {
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--text-primary);
  }
  
  .chart-content {
    flex: 1;
    padding: var(--space-2);
    min-height: 150px;
  }
  
  .chart-svg {
    width: 100%;
    height: 100%;
  }
  
  .empty-state {
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
  }
  
  .empty-icon {
    font-size: 2rem;
    opacity: 0.5;
  }
  
  .empty-text {
    color: var(--text-tertiary);
    font-size: var(--text-sm);
    margin: 0;
  }
  
  /* Grid and axes */
  .grid-line {
    stroke: var(--border-subtle);
    stroke-width: 1;
    stroke-dasharray: 4 4;
  }
  
  .grid-line.zero {
    stroke: var(--border-default);
    stroke-dasharray: none;
  }
  
  .axis-label {
    font-family: var(--font-mono);
    font-size: 10px;
    fill: var(--text-tertiary);
  }
  
  .x-label {
    font-family: var(--font-mono);
    font-size: 10px;
    fill: var(--text-secondary);
  }
  
  /* Bars */
  .bar {
    transition: opacity var(--transition-fast);
  }
  
  .bar-group:hover .bar {
    filter: url(#glow);
  }
  
  /* Line and area */
  .line {
    transition: stroke-width var(--transition-fast);
  }
  
  .area {
    opacity: 0.8;
  }
  
  /* Data points */
  .data-point {
    cursor: pointer;
    transition: r var(--transition-fast);
  }
  
  .data-point.hovered {
    filter: url(#glow);
  }
  
  /* Value labels */
  .value-label {
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 600;
    fill: var(--text-gold);
  }
</style>
