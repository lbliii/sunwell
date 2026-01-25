<!--
  RisingMotes — Signature radiant particle animation (Svelte 5)
  
  The most distinctive element from the Sunwell logo.
  Uses Unicode stars (✦ ✧ ⋆ ·) for magical effect.
  
  Usage:
    <RisingMotes /> - default 8 particles, normal intensity
    <RisingMotes count={12} intensity="intense" /> - loading states
    <RisingMotes count={5} intensity="subtle" /> - hover decorations
-->
<script lang="ts">
  const STAR_CHARS = ['✦', '✧', '⋆', '·', '✦', '✧', '⋆'];
  
  interface Props {
    count?: number;
    intensity?: 'subtle' | 'normal' | 'intense';
    active?: boolean;
  }
  
  let { count = 8, intensity = 'normal', active = true }: Props = $props();
  
  // Generate varied positions and timings for natural feel
  let particles = $derived(
    Array(count).fill(null).map((_, i) => ({
      id: i,
      left: 5 + (i * (90 / count)) + (Math.sin(i * 1.5) * 5),
      delay: i * 0.4 + (Math.sin(i * 2) * 0.2),
      duration: 3 + (i % 4) * 0.5,
      isAlt: i % 3 !== 0,
      size: 1 + (i % 3) * 0.3,
      char: STAR_CHARS[i % STAR_CHARS.length],
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
    {#each particles as particle (particle.id)}
      <span 
        class="mote"
        class:alt={particle.isAlt}
        style="
          left: {particle.left}%;
          animation-delay: {particle.delay}s;
          animation-duration: {particle.duration}s;
          --size-mult: {particle.size};
        "
      >{particle.char}</span>
    {/each}
  </div>
{/if}

<style>
  .motes-container {
    position: absolute;
    inset: 0;
    overflow: visible; /* Allow motes to float beyond container */
    pointer-events: none;
    z-index: 10; /* Float above input elements */
  }
  
  /* Motes use RADIANT gold stars */
  .mote {
    position: absolute;
    bottom: 0;
    font-size: calc(14px * var(--size-mult, 1));
    line-height: 1;
    color: var(--ui-gold);
    text-shadow: var(--glow-gold-intense);
    opacity: 0; /* Start invisible until animation begins */
    animation: riseMote 3.5s ease-out infinite backwards;
    will-change: transform, opacity;
  }
  
  .mote.alt {
    animation: riseMoteAlt 3.5s ease-out infinite backwards;
  }
  
  /* Subtle intensity - smaller, gentler glow */
  .subtle .mote {
    font-size: calc(10px * var(--size-mult, 1));
    text-shadow: var(--glow-gold-subtle);
  }
  
  /* Intense intensity - larger, stronger glow */
  .intense .mote {
    font-size: calc(18px * var(--size-mult, 1));
    text-shadow: var(--glow-gold-intense);
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
      transform: translateY(-200px) scale(0.4);
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
      transform: translateY(-150px) translateX(15px) scale(0.5);
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
