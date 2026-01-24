<!--
  ParticleStream — Particles flowing along a path (RFC-112)
  
  A primitive for Observatory visualizations that creates
  flowing particles along an SVG path, useful for showing
  data flow between nodes.
  
  Usage:
    <svg viewBox="0 0 500 300">
      <ParticleStream 
        path="M 0,50 L 100,50" 
        count={10}
        speed={2000}
        active={true}
      />
    </svg>
  
  Note: Must be used inside an <svg> element.
-->
<script lang="ts">
  interface Props {
    /** SVG path data for particles to follow */
    path: string;
    /** Number of particles */
    count?: number;
    /** Time for one particle to traverse path (ms) */
    speed?: number;
    /** Whether particles are flowing */
    active?: boolean;
    /** Particle color */
    color?: string;
    /** Min particle radius */
    minSize?: number;
    /** Max particle radius */
    maxSize?: number;
    /** Whether to add glow effect */
    glow?: boolean;
    /** Glow blur radius */
    glowRadius?: number;
    /** Opacity range [min, max] */
    opacity?: [number, number];
    /** Whether particles should fade in/out */
    fade?: boolean;
    /** Whether to reverse direction */
    reverse?: boolean;
  }
  
  let { 
    path, 
    count = 10, 
    speed = 2000,
    active = true,
    color = 'var(--ui-gold)',
    minSize = 2,
    maxSize = 4,
    glow = true,
    glowRadius = 3,
    opacity = [0.6, 1.0],
    fade = true,
    reverse = false,
  }: Props = $props();
  
  // Generate unique ID for this stream
  const streamId = `stream-${Math.random().toString(36).slice(2, 9)}`;
  const pathId = `${streamId}-path`;
  const filterId = `${streamId}-glow`;
  
  // Generate particles with staggered timing and varied sizes
  const particles = $derived(
    Array(count).fill(null).map((_, i) => ({
      id: `${streamId}-p${i}`,
      delay: (i / count) * speed,
      size: minSize + Math.random() * (maxSize - minSize),
      opacity: opacity[0] + Math.random() * (opacity[1] - opacity[0]),
    }))
  );
</script>

{#if active}
  <g class="particle-stream" class:reverse>
    <defs>
      <!-- Invisible path for motion reference -->
      <path id={pathId} d={path} fill="none" stroke="none" />
      
      <!-- Glow filter -->
      {#if glow}
        <filter id={filterId} x="-100%" y="-100%" width="300%" height="300%">
          <feGaussianBlur in="SourceGraphic" stdDeviation={glowRadius} result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      {/if}
    </defs>
    
    {#each particles as particle (particle.id)}
      <circle
        r={particle.size}
        fill={color}
        class="particle"
        class:fade
        filter={glow ? `url(#${filterId})` : undefined}
        style:--delay="{particle.delay}ms"
        style:--duration="{speed}ms"
        style:--opacity={particle.opacity}
      >
        <animateMotion
          dur="{speed}ms"
          repeatCount="indefinite"
          begin="{particle.delay}ms"
          keyPoints={reverse ? "1;0" : "0;1"}
          keyTimes="0;1"
          calcMode="linear"
        >
          <mpath href="#{pathId}" />
        </animateMotion>
      </circle>
    {/each}
  </g>
{/if}

<style>
  .particle-stream {
    pointer-events: none;
  }
  
  .particle {
    opacity: var(--opacity, 1);
  }
  
  .particle.fade {
    animation: particle-fade var(--duration) ease-in-out var(--delay) infinite;
  }
  
  @keyframes particle-fade {
    0%, 100% { 
      opacity: 0; 
    }
    15%, 85% { 
      opacity: var(--opacity, 1); 
    }
  }
</style>
