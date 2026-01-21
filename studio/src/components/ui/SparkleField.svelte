<script lang="ts">
  /**
   * SparkleField — Rising particle animation using Unicode characters
   * 
   * Creates the effect from RFC-061:
   *     ·  ✦        ← particles fade as they rise
   *       ·    ✦
   *    ✦     ·
   *      ·  ✦  ·    ← staggered timing
   *    ·    ✦
   *   ✦  ·    ✦
   *     ·  ✦  ·     ← particles born at bottom
   *   ━━━━━━━━━━━    (source element)
   */
  import { onMount } from 'svelte';

  interface Props {
    width?: number;      // character width
    height?: number;     // character height  
    density?: number;    // particles per row (0-1)
    speed?: number;      // ms per rise tick
    chars?: string[];    // particle characters
  }

  let { 
    width = 12, 
    height = 8, 
    density = 0.25,
    speed = 200,
    chars = ['·', '✧', '✦', '⋆']
  }: Props = $props();

  interface Particle {
    x: number;
    y: number;
    char: string;
    opacity: number;
    age: number;
  }

  let particles = $state<Particle[]>([]);

  // Build display grid
  let grid = $derived.by(() => {
    const rows: string[][] = Array.from({ length: height }, () => 
      Array.from({ length: width }, () => ' ')
    );
    
    for (const p of particles) {
      const row = Math.floor(p.y);
      const col = Math.floor(p.x);
      if (row >= 0 && row < height && col >= 0 && col < width) {
        rows[row][col] = p.char;
      }
    }
    
    return rows;
  });

  // Get opacity class based on height (fade as rising)
  function getOpacityClass(y: number): string {
    const ratio = y / height;
    if (ratio < 0.25) return 'bright';
    if (ratio < 0.5) return 'medium';
    if (ratio < 0.75) return 'dim';
    return 'faint';
  }

  onMount(() => {
    // Spawn new particles
    const spawnInterval = setInterval(() => {
      const newParticles: Particle[] = [];
      
      for (let x = 0; x < width; x++) {
        if (Math.random() < density) {
          newParticles.push({
            x: x + Math.random() * 0.5,
            y: height - 1,
            char: chars[Math.floor(Math.random() * chars.length)],
            opacity: 1,
            age: 0,
          });
        }
      }
      
      particles = [...particles, ...newParticles];
    }, speed * 2);

    // Rise and age particles
    const riseInterval = setInterval(() => {
      particles = particles
        .map(p => ({
          ...p,
          y: p.y - 0.5 - Math.random() * 0.3,
          x: p.x + (Math.random() - 0.5) * 0.3, // slight horizontal drift
          age: p.age + 1,
          // Transition through characters as they rise
          char: p.age > 3 ? '·' : p.age > 1 ? '✧' : p.char,
        }))
        .filter(p => p.y > -1); // Remove particles that rose off screen
    }, speed);

    return () => {
      clearInterval(spawnInterval);
      clearInterval(riseInterval);
    };
  });
</script>

<div class="sparkle-field" style="--width: {width}ch; --height: {height}lh;">
  {#each grid as row, y}
    <div class="row">
      {#each row as char, x}
        <span class="cell {char !== ' ' ? getOpacityClass(y) : ''}">{char}</span>
      {/each}
    </div>
  {/each}
</div>

<style>
  .sparkle-field {
    font-family: monospace;
    line-height: 1.2;
    width: var(--width);
    height: var(--height);
    overflow: hidden;
    user-select: none;
    pointer-events: none;
  }

  .row {
    display: flex;
    height: 1lh;
  }

  .cell {
    width: 1ch;
    text-align: center;
    color: var(--sparkle-color, #d4af37);
    transition: opacity 0.15s ease;
  }

  .bright { opacity: 1; }
  .medium { opacity: 0.7; }
  .dim { opacity: 0.4; }
  .faint { opacity: 0.15; }
</style>
