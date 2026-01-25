<!--
  Timeline Primitive (RFC-072, RFC-078 Phase 2)
  
  Horizontal timeline view with multiple tracks, zoom levels, and time scale.
  Can display calendar events, git commits, file modifications, etc.
-->
<script lang="ts">
  import { untrack } from 'svelte';
  import type { PrimitiveProps } from './types';
  
  interface TimelineEvent {
    id: string;
    title: string;
    start: Date;
    end?: Date;
    track: string;
    color?: string;
    icon?: string;
  }
  
  interface Props extends PrimitiveProps {
    events?: TimelineEvent[];
    startDate?: Date;
    endDate?: Date;
    tracks?: string[];
    zoomLevel?: 'hour' | 'day' | 'week' | 'month';
  }
  
  let { 
    size, 
    events = [],
    startDate,
    endDate,
    tracks,
    zoomLevel = 'day',
  }: Props = $props();
  
  // Zoom configuration
  const ZOOM_CONFIG = {
    hour: { unit: 'hour', labelFormat: 'HH:mm', cellWidth: 60, majorInterval: 6 },
    day: { unit: 'day', labelFormat: 'MMM D', cellWidth: 80, majorInterval: 7 },
    week: { unit: 'week', labelFormat: 'MMM D', cellWidth: 100, majorInterval: 4 },
    month: { unit: 'month', labelFormat: 'MMM YYYY', cellWidth: 120, majorInterval: 3 },
  };
  
  // Initialize zoom from prop (intentional one-time capture)
  let currentZoom: 'hour' | 'day' | 'week' | 'month' = $state(untrack(() => zoomLevel));
  let hoveredEvent: TimelineEvent | null = $state(null);
  let tooltipPosition = $state({ x: 0, y: 0 });
  
  // Compute date range from events if not provided
  const dateRange = $derived.by(() => {
    if (startDate && endDate) {
      return { start: startDate, end: endDate };
    }
    
    if (events.length === 0) {
      const now = new Date();
      return {
        start: new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000),
        end: new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000),
      };
    }
    
    const dates = events.flatMap(e => [e.start, e.end].filter(Boolean)) as Date[];
    const minDate = new Date(Math.min(...dates.map(d => d.getTime())));
    const maxDate = new Date(Math.max(...dates.map(d => d.getTime())));
    
    // Add padding
    const padding = (maxDate.getTime() - minDate.getTime()) * 0.1;
    return {
      start: new Date(minDate.getTime() - padding),
      end: new Date(maxDate.getTime() + padding),
    };
  });
  
  // Compute tracks from events if not provided
  const computedTracks = $derived.by(() => {
    if (tracks && tracks.length > 0) return tracks;
    const trackSet = new Set(events.map(e => e.track));
    return Array.from(trackSet).sort();
  });
  
  // Index events by track for O(1) lookup in template (avoids O(n) filter per track)
  const eventsByTrack = $derived.by(() => {
    const map = new Map<string, TimelineEvent[]>();
    for (const e of events) {
      const arr = map.get(e.track) ?? [];
      arr.push(e);
      map.set(e.track, arr);
    }
    return map;
  });
  
  // Generate time labels based on zoom level
  const timeLabels = $derived.by(() => {
    const { start, end } = dateRange;
    const config = ZOOM_CONFIG[currentZoom];
    const labels: { date: Date; label: string; isMajor: boolean }[] = [];
    
    let current = new Date(start);
    let index = 0;
    
    while (current <= end) {
      const isMajor = index % config.majorInterval === 0;
      labels.push({
        date: new Date(current),
        label: formatDate(current, config.labelFormat),
        isMajor,
      });
      
      // Advance to next unit
      switch (currentZoom) {
        case 'hour':
          current = new Date(current.getTime() + 60 * 60 * 1000);
          break;
        case 'day':
          current.setDate(current.getDate() + 1);
          break;
        case 'week':
          current.setDate(current.getDate() + 7);
          break;
        case 'month':
          current.setMonth(current.getMonth() + 1);
          break;
      }
      index++;
    }
    
    return labels;
  });
  
  // Calculate event position and width
  function getEventStyle(event: TimelineEvent): string {
    const { start, end } = dateRange;
    const totalDuration = end.getTime() - start.getTime();
    
    const eventStart = event.start.getTime();
    const eventEnd = event.end?.getTime() ?? eventStart + 60 * 60 * 1000; // Default 1 hour
    
    const left = ((eventStart - start.getTime()) / totalDuration) * 100;
    const width = ((eventEnd - eventStart) / totalDuration) * 100;
    
    return `left: ${Math.max(0, left)}%; width: ${Math.min(100 - left, width)}%;`;
  }
  
  // Simple date formatting
  function formatDate(date: Date, format: string): string {
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    
    return format
      .replace('YYYY', String(date.getFullYear()))
      .replace('MMM', months[date.getMonth()])
      .replace('DD', String(date.getDate()).padStart(2, '0'))
      .replace('D', String(date.getDate()))
      .replace('HH', String(date.getHours()).padStart(2, '0'))
      .replace('mm', String(date.getMinutes()).padStart(2, '0'));
  }
  
  // Format duration
  function formatDuration(start: Date, end?: Date): string {
    if (!end) return 'Point event';
    
    const diffMs = end.getTime() - start.getTime();
    const hours = Math.floor(diffMs / (1000 * 60 * 60));
    const minutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
    
    if (hours === 0) return `${minutes}m`;
    if (minutes === 0) return `${hours}h`;
    return `${hours}h ${minutes}m`;
  }
  
  // Track colors
  const TRACK_COLORS: Record<string, string> = {
    calendar: 'var(--accent-primary)',
    git: 'var(--success)',
    files: 'var(--warning)',
    default: 'var(--text-secondary)',
  };
  
  function getTrackColor(track: string): string {
    return TRACK_COLORS[track.toLowerCase()] ?? TRACK_COLORS.default;
  }
  
  function handleEventHover(event: TimelineEvent, e: MouseEvent) {
    hoveredEvent = event;
    tooltipPosition = { x: e.clientX, y: e.clientY };
  }
  
  function handleEventLeave() {
    hoveredEvent = null;
  }
</script>

<div class="timeline" data-size={size}>
  <div class="timeline-header">
    <span>📅 Timeline</span>
    <div class="timeline-controls">
      <div class="zoom-controls">
        <button 
          class="zoom-btn"
          class:active={currentZoom === 'hour'}
          onclick={() => currentZoom = 'hour'}
        >
          Hour
        </button>
        <button 
          class="zoom-btn"
          class:active={currentZoom === 'day'}
          onclick={() => currentZoom = 'day'}
        >
          Day
        </button>
        <button 
          class="zoom-btn"
          class:active={currentZoom === 'week'}
          onclick={() => currentZoom = 'week'}
        >
          Week
        </button>
        <button 
          class="zoom-btn"
          class:active={currentZoom === 'month'}
          onclick={() => currentZoom = 'month'}
        >
          Month
        </button>
      </div>
      <span class="event-count">{events.length} events</span>
    </div>
  </div>
  
  <div class="timeline-content">
    {#if events.length === 0}
    <p class="placeholder">No timeline data</p>
    {:else}
      <!-- Time scale header -->
      <div class="time-scale">
        <div class="track-label-spacer"></div>
        <div class="time-labels">
          {#each timeLabels as label (label.date.getTime())}
            <div 
              class="time-label" 
              class:major={label.isMajor}
              style="width: {ZOOM_CONFIG[currentZoom].cellWidth}px;"
            >
              {label.label}
            </div>
          {/each}
        </div>
      </div>
      
      <!-- Tracks -->
      <div class="tracks-container">
        {#each computedTracks as track (track)}
          <div class="track">
            <div class="track-label" style="--track-color: {getTrackColor(track)}">
              <span class="track-name">{track}</span>
            </div>
            <div class="track-content">
              <!-- Grid lines -->
              <div class="grid-lines">
                {#each timeLabels as label (label.date.getTime())}
                  <div 
                    class="grid-line" 
                    class:major={label.isMajor}
                    style="width: {ZOOM_CONFIG[currentZoom].cellWidth}px;"
                  ></div>
                {/each}
              </div>
              
              <!-- Events -->
              {#each eventsByTrack.get(track) ?? [] as event (event.id)}
                <div 
                  class="event"
                  style="{getEventStyle(event)} background: {event.color || getTrackColor(track)};"
                  onmouseenter={(e) => handleEventHover(event, e)}
                  onmouseleave={handleEventLeave}
                  role="button"
                  tabindex="0"
                >
                  <span class="event-title">{event.title}</span>
                </div>
              {/each}
            </div>
          </div>
        {/each}
      </div>
      
      <!-- Today marker -->
      {#if (() => {
        const now = new Date();
        const { start, end } = dateRange;
        return now >= start && now <= end;
      })()}
        <div 
          class="today-marker"
          style="left: calc(100px + {
            ((new Date().getTime() - dateRange.start.getTime()) / 
            (dateRange.end.getTime() - dateRange.start.getTime())) * 
            (timeLabels.length * ZOOM_CONFIG[currentZoom].cellWidth)
          }px);"
        >
          <div class="today-line"></div>
          <span class="today-label">Today</span>
        </div>
      {/if}
    {/if}
  </div>
  
  <!-- Tooltip -->
  {#if hoveredEvent}
    <div 
      class="event-tooltip"
      style="left: {tooltipPosition.x + 10}px; top: {tooltipPosition.y + 10}px;"
    >
      <div class="tooltip-title">{hoveredEvent.title}</div>
      <div class="tooltip-track">{hoveredEvent.track}</div>
      <div class="tooltip-time">
        {formatDate(hoveredEvent.start, 'MMM D, HH:mm')}
        {#if hoveredEvent.end}
          → {formatDate(hoveredEvent.end, 'HH:mm')}
        {/if}
      </div>
      <div class="tooltip-duration">{formatDuration(hoveredEvent.start, hoveredEvent.end)}</div>
    </div>
  {/if}
</div>

<style>
  .timeline {
    height: 100%;
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    position: relative;
  }
  
  .timeline-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-sm) var(--spacing-md);
    border-bottom: 1px solid var(--border-subtle);
    color: var(--text-primary);
  }
  
  .timeline-controls {
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
  }
  
  .zoom-controls {
    display: flex;
    gap: 2px;
    background: var(--bg-tertiary);
    border-radius: var(--radius-sm);
    padding: 2px;
  }
  
  .zoom-btn {
    background: none;
    border: none;
    padding: 4px 8px;
    font-size: 0.6875rem;
    color: var(--text-secondary);
    cursor: pointer;
    border-radius: var(--radius-sm);
  }
  
  .zoom-btn:hover {
    color: var(--text-primary);
  }
  
  .zoom-btn.active {
    background: var(--bg-primary);
    color: var(--text-primary);
  }
  
  .event-count {
    font-size: 0.75rem;
    color: var(--text-secondary);
  }
  
  .timeline-content {
    flex: 1;
    overflow: auto;
    position: relative;
  }
  
  .placeholder {
    color: var(--text-tertiary);
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
  }
  
  /* Time scale */
  .time-scale {
    display: flex;
    position: sticky;
    top: 0;
    background: var(--bg-secondary);
    z-index: 10;
    border-bottom: 1px solid var(--border-subtle);
  }
  
  .track-label-spacer {
    width: 100px;
    flex-shrink: 0;
  }
  
  .time-labels {
    display: flex;
    overflow: hidden;
  }
  
  .time-label {
    flex-shrink: 0;
    padding: 4px 8px;
    font-size: 0.6875rem;
    color: var(--text-tertiary);
    text-align: center;
    border-left: 1px solid var(--border-subtle);
  }
  
  .time-label.major {
    color: var(--text-secondary);
    font-weight: 600;
  }
  
  /* Tracks */
  .tracks-container {
    position: relative;
  }
  
  .track {
    display: flex;
    min-height: 48px;
    border-bottom: 1px solid var(--border-subtle);
  }
  
  .track-label {
    width: 100px;
    flex-shrink: 0;
    padding: 8px 12px;
    display: flex;
    align-items: center;
    gap: 8px;
    background: var(--bg-tertiary);
    border-right: 3px solid var(--track-color);
  }
  
  .track-name {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--text-primary);
    text-transform: capitalize;
  }
  
  .track-content {
    flex: 1;
    position: relative;
    min-height: 40px;
  }
  
  /* Grid lines */
  .grid-lines {
    position: absolute;
    inset: 0;
    display: flex;
    pointer-events: none;
  }
  
  .grid-line {
    flex-shrink: 0;
    border-left: 1px solid var(--border-subtle);
    height: 100%;
  }
  
  .grid-line.major {
    border-color: var(--border-default);
  }
  
  /* Events */
  .event {
    position: absolute;
    top: 6px;
    bottom: 6px;
    min-width: 20px;
    border-radius: var(--radius-sm);
    padding: 4px 8px;
    cursor: pointer;
    overflow: hidden;
    transition: transform 0.1s, box-shadow 0.1s;
    z-index: 5;
  }
  
  .event:hover {
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    z-index: 6;
  }
  
  .event-title {
    font-size: 0.6875rem;
    font-weight: 500;
    color: white;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  /* Today marker */
  .today-marker {
    position: absolute;
    top: 0;
    bottom: 0;
    z-index: 20;
    pointer-events: none;
  }
  
  .today-line {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 2px;
    background: var(--error);
  }
  
  .today-label {
    position: absolute;
    top: 4px;
    left: 4px;
    font-size: 0.5625rem;
    font-weight: 600;
    color: var(--error);
    text-transform: uppercase;
  }
  
  /* Tooltip */
  .event-tooltip {
    position: fixed;
    background: var(--bg-primary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    padding: var(--spacing-sm) var(--spacing-md);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    z-index: 100;
    pointer-events: none;
    min-width: 150px;
  }
  
  .tooltip-title {
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 4px;
  }
  
  .tooltip-track {
    font-size: 0.75rem;
    color: var(--text-secondary);
    text-transform: capitalize;
  }
  
  .tooltip-time {
    font-size: 0.75rem;
    color: var(--text-secondary);
    font-family: var(--font-mono);
    margin-top: 4px;
  }
  
  .tooltip-duration {
    font-size: 0.6875rem;
    color: var(--text-tertiary);
    margin-top: 2px;
  }
</style>
