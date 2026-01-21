<script lang="ts">
  import { onMount } from 'svelte';

  type SparkleStyle = 'twinkle' | 'pulse' | 'star' | 'dots' | 'diamond';

  interface Props {
    style?: SparkleStyle;
    speed?: number;  // ms per frame
    dim?: boolean;   // start dim vs bright
  }

  let { style = 'twinkle', speed = 150, dim = false }: Props = $props();

  // Sparkle frame sequences - designed for twinkling/pulsing effects
  // Note: `dim` is captured at initialization - this is intentional for sparkle staggering
  const frames: Record<SparkleStyle, string[]> = {
    // Classic twinkle: dim → bright → dim → gone
    twinkle: dim 
      ? ['·', '✧', '✦', '✧', '·', ' ']
      : ['✦', '✧', '·', ' ', '·', '✧'],
    
    // Gentle pulse between two states
    pulse: ['✦', '✧'],
    
    // Star intensity cycle
    star: ['⋆', '✧', '✦', '★', '✦', '✧'],
    
    // Diamond pulse
    diamond: ['◇', '◈', '◆', '◈'],
    
    // Dot fade
    dots: ['●', '•', '·', '∘', ' ', '∘', '·', '•'],
  };

  let frameIndex = $state(0);
  let currentFrame = $derived(frames[style][frameIndex]);

  onMount(() => {
    // Random start offset for staggered effect when multiple sparkles
    const startDelay = Math.random() * speed * frames[style].length;
    
    const timeout = setTimeout(() => {
      const interval = setInterval(() => {
        frameIndex = (frameIndex + 1) % frames[style].length;
      }, speed);
      
      return () => clearInterval(interval);
    }, startDelay);

    return () => clearTimeout(timeout);
  });
</script>

<span class="sparkle">{currentFrame}</span>

<style>
  .sparkle {
    display: inline-block;
    width: 1ch;
    text-align: center;
    color: var(--sparkle-color, var(--color-accent, #d4af37));
  }
</style>
