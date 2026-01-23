<!--
  MouseMotes — Tinkerbell-style mouse trail particles (Svelte 5)
  
  Spawns gentle golden star characters that follow cursor movement.
  Uses Unicode stars (✦ ✧ ⋆ ·) instead of gradient bubbles.
  
  Usage:
    <MouseMotes /> - adds mouse trail to parent container
    <MouseMotes spawnRate={80} /> - spawn every 80ms (default: 60)
    <MouseMotes maxParticles={20} /> - limit active particles
-->
<script lang="ts">
  import type { Snippet } from 'svelte';
  import { onMount } from 'svelte';
  
  const STAR_CHARS = ['✦', '✧', '⋆', '·', '✦', '✧'];
  
  interface Props {
    spawnRate?: number;
    maxParticles?: number;
    active?: boolean;
    children?: Snippet;
  }
  
  let { 
    spawnRate = 60, 
    maxParticles = 25, 
    active = true,
    children,
  }: Props = $props();
  
  interface Particle {
    id: number;
    x: number;
    y: number;
    char: string;
    size: number;
    duration: number;
    drift: number;
  }
  
  let particles = $state<Particle[]>([]);
  let container: HTMLDivElement;
  let lastSpawn = 0;
  let idCounter = 0;
  let lastX = 0;
  let lastY = 0;
  
  // Check for reduced motion preference
  let prefersReducedMotion = $state(false);
  
  onMount(() => {
    prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });
  
  function handleMouseMove(e: MouseEvent) {
    if (!active || !container) return;
    
    const now = Date.now();
    if (now - lastSpawn < spawnRate) return;
    
    // Get position relative to container
    const rect = container.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    // Only spawn if mouse has moved enough
    const dist = Math.sqrt((x - lastX) ** 2 + (y - lastY) ** 2);
    if (dist < 5) return;
    
    lastX = x;
    lastY = y;
    lastSpawn = now;
    
    // Create new particle with slight randomness
    const particle: Particle = {
      id: idCounter++,
      x: x + (Math.random() - 0.5) * 10,
      y: y + (Math.random() - 0.5) * 10,
      char: STAR_CHARS[Math.floor(Math.random() * STAR_CHARS.length)],
      size: 10 + Math.random() * 6,
      duration: 1.2 + Math.random() * 0.6,
      drift: (Math.random() - 0.5) * 20,
    };
    
    particles = [...particles.slice(-(maxParticles - 1)), particle];
    
    // Remove particle after animation
    setTimeout(() => {
      particles = particles.filter(p => p.id !== particle.id);
    }, particle.duration * 1000);
  }
</script>

<div 
  class="mouse-motes-container" 
  bind:this={container}
  onmousemove={handleMouseMove}
  role="presentation"
>
  {#if children}
    {@render children()}
  {/if}
  
  {#if active && !prefersReducedMotion}
    {#each particles as particle (particle.id)}
      <span 
        class="mouse-mote"
        style="
          left: {particle.x}px;
          top: {particle.y}px;
          --size: {particle.size}px;
          --duration: {particle.duration}s;
          --drift: {particle.drift}px;
        "
      >{particle.char}</span>
    {/each}
  {/if}
</div>

<style>
  .mouse-motes-container {
    position: relative;
    width: 100%;
    height: 100%;
  }
  
  .mouse-mote {
    position: absolute;
    pointer-events: none;
    z-index: 100;
    font-size: var(--size);
    line-height: 1;
    color: var(--ui-gold);
    text-shadow: var(--glow-gold-intense);
    animation: mouseMoteFade var(--duration) ease-out forwards;
    transform: translate(-50%, -50%);
  }
  
  @keyframes mouseMoteFade {
    0% {
      opacity: 0.9;
      transform: translate(-50%, -50%) scale(1);
    }
    30% {
      opacity: 0.7;
    }
    100% {
      opacity: 0;
      transform: translate(
        calc(-50% + var(--drift)), 
        calc(-50% - 40px)
      ) scale(0.5);
    }
  }
</style>
