<!--
  RisingMotes — Signature radiant particle animation (Svelte 5)
  
  The most distinctive element from the Sunwell logo.
  Uses RADIANT gold (bright) for magical effect — this is where
  the bright gold belongs, not on UI elements.
  
  Usage:
    <RisingMotes /> - default 8 particles, normal intensity
    <RisingMotes count={12} intensity="intense" /> - loading states
    <RisingMotes count={5} intensity="subtle" /> - hover decorations
-->
<script lang="ts">
  interface Props {
    count?: number;
    intensity?: 'subtle' | 'normal' | 'intense';
    active?: boolean;
  }
  
  let { count = 8, intensity = 'normal', active = true }: Props = $props();
  
  // Generate varied positions and timings for natural feel
  let particles = $derived(
    Array(count).fill(null).map((_, i) => ({
      left: 5 + (i * (90 / count)) + (Math.sin(i * 1.5) * 5),
      delay: i * 0.4 + (Math.sin(i * 2) * 0.2),
      duration: 3 + (i % 4) * 0.5,
      isAlt: i % 3 !== 0,
      size: 1 + (i % 3) * 0.3, // Vary sizes slightly
    }))
  );
</script>

{#if active}
  <div 
    class="motes-container"
    class:subtle={intensity === 'subtle'}
    class:intense={intensity === 'intense'}
    aria-hidden="true"
  >
    {#each particles as particle}
      <span 
        class="mote"
        class:alt={particle.isAlt}
        style="
          left: {particle.left}%;
          animation-delay: {particle.delay}s;
          animation-duration: {particle.duration}s;
          --size-mult: {particle.size};
        "
      ></span>
    {/each}
  </div>
{/if}

<style>
  .motes-container {
    position: absolute;
    inset: 0;
    overflow: hidden;
    pointer-events: none;
    z-index: 1;
  }
  
  /* Motes use RADIANT gold - the bright magical light */
  .mote {
    position: absolute;
    bottom: 0;
    width: calc(5px * var(--size-mult, 1));
    height: calc(5px * var(--size-mult, 1));
    background: radial-gradient(
      circle,
      #fff9e6 0%,
      #ffd700 40%,
      rgba(255, 215, 0, 0.6) 70%,
      transparent 100%
    );
    border-radius: 50%;
    box-shadow: 
      0 0 8px rgba(255, 215, 0, 0.8),
      0 0 16px rgba(255, 215, 0, 0.5),
      0 0 24px rgba(255, 215, 0, 0.2);
    animation: riseMote 3.5s ease-out infinite;
    will-change: transform, opacity;
  }
  
  .mote.alt {
    animation-name: riseMoteAlt;
  }
  
  /* Subtle intensity - smaller, gentler glow */
  .subtle .mote {
    width: calc(3px * var(--size-mult, 1));
    height: calc(3px * var(--size-mult, 1));
    box-shadow: 
      0 0 4px rgba(255, 215, 0, 0.6),
      0 0 8px rgba(255, 215, 0, 0.3);
  }
  
  /* Intense intensity - larger, stronger glow */
  .intense .mote {
    width: calc(7px * var(--size-mult, 1));
    height: calc(7px * var(--size-mult, 1));
    box-shadow: 
      0 0 10px rgba(255, 215, 0, 1),
      0 0 20px rgba(255, 215, 0, 0.6),
      0 0 40px rgba(255, 215, 0, 0.3);
  }
  
  @keyframes riseMote {
    0% {
      transform: translateY(0) scale(1);
      opacity: 0;
    }
    5% { 
      opacity: 1; 
    }
    70% { 
      opacity: 0.7;
    }
    100% {
      transform: translateY(-200px) scale(0.2);
      opacity: 0;
    }
  }
  
  @keyframes riseMoteAlt {
    0% {
      transform: translateY(0) translateX(0) scale(1);
      opacity: 0;
    }
    5% { 
      opacity: 0.9;
    }
    100% {
      transform: translateY(-150px) translateX(15px) scale(0.3);
      opacity: 0;
    }
  }
  
  /* Reduced motion: hide particles */
  @media (prefers-reduced-motion: reduce) {
    .mote {
      animation: none;
      opacity: 0;
    }
  }
</style>
