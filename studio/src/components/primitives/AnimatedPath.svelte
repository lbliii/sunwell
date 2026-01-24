<!--
  AnimatedPath — SVG path that draws itself (RFC-112)
  
  A primitive for the Observatory visualizations that creates
  a path-drawing animation effect using stroke-dashoffset.
  
  Usage:
    <svg viewBox="0 0 100 100">
      <AnimatedPath 
        d="M 0,50 Q 50,0 100,50" 
        duration={1000} 
        color="var(--ui-gold)"
      />
    </svg>
-->
<script lang="ts">
  import { onMount } from 'svelte';
  
  interface Props {
    /** SVG path data (d attribute) */
    d: string;
    /** Animation duration in ms */
    duration?: number;
    /** Delay before animation starts in ms */
    delay?: number;
    /** Stroke color (CSS variable or color) */
    color?: string;
    /** Stroke width */
    strokeWidth?: number;
    /** Whether to add glow effect */
    glow?: boolean;
    /** Glow color (defaults to color with 40% opacity) */
    glowColor?: string;
    /** Glow blur radius */
    glowRadius?: number;
    /** Line cap style */
    linecap?: 'butt' | 'round' | 'square';
    /** Line join style */
    linejoin?: 'miter' | 'round' | 'bevel';
    /** Whether animation should play (for manual control) */
    animate?: boolean;
    /** Whether to reverse the animation (erase instead of draw) */
    reverse?: boolean;
    /** Easing function name */
    easing?: 'linear' | 'ease' | 'ease-in' | 'ease-out' | 'ease-in-out';
    /** Callback when animation completes */
    onComplete?: () => void;
  }
  
  let { 
    d, 
    duration = 1000, 
    delay = 0,
    color = 'var(--ui-gold)',
    strokeWidth = 2,
    glow = false,
    glowColor,
    glowRadius = 4,
    linecap = 'round',
    linejoin = 'round',
    animate = true,
    reverse = false,
    easing = 'ease-out',
    onComplete,
  }: Props = $props();
  
  let pathRef: SVGPathElement | undefined = $state();
  let pathLength = $state(0);
  let isAnimating = $state(false);
  
  // Compute path length when path or d changes
  $effect(() => {
    if (pathRef && d) {
      pathLength = pathRef.getTotalLength();
    }
  });
  
  // Trigger animation
  $effect(() => {
    if (animate && pathLength > 0) {
      isAnimating = true;
      
      // Notify completion after animation
      if (onComplete) {
        const totalTime = delay + duration;
        const timer = setTimeout(() => {
          onComplete();
        }, totalTime);
        
        return () => clearTimeout(timer);
      }
    }
  });
  
  // Generate unique filter ID for this instance
  const filterId = `glow-${Math.random().toString(36).slice(2, 9)}`;
  
  // Compute glow color (default to color with alpha)
  const computedGlowColor = $derived(glowColor || color);
</script>

{#if glow}
  <defs>
    <filter id={filterId} x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur 
        in="SourceGraphic" 
        stdDeviation={glowRadius} 
        result="blur"
      />
      <feMerge>
        <feMergeNode in="blur" />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>
  </defs>
{/if}

<path
  bind:this={pathRef}
  {d}
  fill="none"
  stroke={color}
  stroke-width={strokeWidth}
  stroke-linecap={linecap}
  stroke-linejoin={linejoin}
  filter={glow ? `url(#${filterId})` : undefined}
  class="animated-path"
  class:animating={isAnimating}
  class:reverse
  style:--path-length={pathLength}
  style:--duration={duration}ms
  style:--delay={delay}ms
  style:--easing={easing}
  style:stroke-dasharray={pathLength}
  style:stroke-dashoffset={isAnimating ? (reverse ? 0 : pathLength) : (reverse ? pathLength : pathLength)}
/>

<style>
  .animated-path {
    transition: none;
  }
  
  .animated-path.animating {
    animation: draw-path var(--duration) var(--easing) var(--delay) forwards;
  }
  
  .animated-path.animating.reverse {
    animation: erase-path var(--duration) var(--easing) var(--delay) forwards;
  }
  
  @keyframes draw-path {
    to {
      stroke-dashoffset: 0;
    }
  }
  
  @keyframes erase-path {
    from {
      stroke-dashoffset: 0;
    }
    to {
      stroke-dashoffset: var(--path-length);
    }
  }
</style>
