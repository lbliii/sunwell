<!--
  LensCardMotes — Hover sparkle effect for lens cards (RFC-100)
  
  Subtle golden sparkles that appear on hover for magical delight.
-->
<script lang="ts">
  interface Mote {
    id: number;
    x: number;
    y: number;
    delay: number;
    char: string;
  }
  
  let motes = $state<Mote[]>([]);
  let moteId = 0;
  
  const chars = ['✦', '✧', '⋆', '·'];
  
  export function spawnMotes(e: MouseEvent) {
    // Respect reduced motion
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    // Spawn 3-5 motes around cursor
    const count = 3 + Math.floor(Math.random() * 3);
    const newMotes: Mote[] = Array.from({ length: count }, (_, i) => ({
      id: moteId++,
      x: x + (Math.random() - 0.5) * 40,
      y: y + (Math.random() - 0.5) * 20,
      delay: i * 50,
      char: chars[Math.floor(Math.random() * chars.length)],
    }));
    
    motes = [...motes, ...newMotes];
    
    // Clean up after animation
    setTimeout(() => {
      motes = motes.filter(m => !newMotes.some(nm => nm.id === m.id));
    }, 1000);
  }
</script>

<div class="mote-container">
  {#each motes as mote (mote.id)}
    <span 
      class="micro-mote"
      style="--x: {mote.x}px; --y: {mote.y}px; --delay: {mote.delay}ms"
    >{mote.char}</span>
  {/each}
</div>

<style>
  .mote-container {
    position: absolute;
    inset: 0;
    pointer-events: none;
    overflow: hidden;
    border-radius: inherit;
  }
  
  .micro-mote {
    position: absolute;
    left: var(--x);
    top: var(--y);
    font-size: 10px;
    color: var(--radiant-gold);
    text-shadow: var(--glow-gold-subtle);
    opacity: 0;
    animation: moteRise var(--mote-duration) ease-out forwards;
    animation-delay: var(--delay);
  }
  
  @keyframes moteRise {
    0% { 
      opacity: 0; 
      transform: translateY(0) scale(0.5); 
    }
    20% { 
      opacity: 0.9; 
    }
    100% { 
      opacity: 0; 
      transform: translateY(-25px) scale(0); 
    }
  }
  
  @media (prefers-reduced-motion: reduce) {
    .micro-mote { 
      animation: none; 
      display: none;
    }
  }
</style>
