<script lang="ts">
  import { onMount } from 'svelte';

  type SpinnerStyle = 'moon' | 'dots' | 'arrows' | 'braille' | 'box' | 'star';

  interface Props {
    style?: SpinnerStyle;
    speed?: number; // ms per frame
  }

  let { style = 'moon', speed = 100 }: Props = $props();

  // Unicode animation frames
  const frames: Record<SpinnerStyle, string[]> = {
    moon: ['◐', '◓', '◑', '◒'],
    dots: ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'],
    arrows: ['←', '↖', '↑', '↗', '→', '↘', '↓', '↙'],
    braille: ['⣾', '⣽', '⣻', '⢿', '⡿', '⣟', '⣯', '⣷'],
    box: ['▁', '▂', '▃', '▄', '▅', '▆', '▇', '█', '▇', '▆', '▅', '▄', '▃', '▂'],
    star: ['⋆', '✧', '✦', '★', '✦', '✧'],
  };

  let frameIndex = $state(0);
  let currentFrame = $derived(frames[style][frameIndex]);

  onMount(() => {
    const interval = setInterval(() => {
      frameIndex = (frameIndex + 1) % frames[style].length;
    }, speed);

    return () => clearInterval(interval);
  });
</script>

<span class="spinner" aria-label="Loading">{currentFrame}</span>

<style>
  .spinner {
    display: inline-block;
    font-family: monospace;
    width: 1em;
    text-align: center;
  }
</style>
