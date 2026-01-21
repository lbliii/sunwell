<script lang="ts">
  interface Props {
    value: number;    // 0-1
    width?: number;   // character width
  }

  let { value, width = 10 }: Props = $props();

  // Block elements for smooth progress: ░ ▒ ▓ █
  // Or using eighths: ▏▎▍▌▋▊▉█
  const blocks = ['', '▏', '▎', '▍', '▌', '▋', '▊', '▉', '█'];

  let bar = $derived.by(() => {
    const filled = value * width;
    const fullBlocks = Math.floor(filled);
    const partialIndex = Math.round((filled - fullBlocks) * 8);
    const emptyBlocks = width - fullBlocks - (partialIndex > 0 ? 1 : 0);

    return (
      '█'.repeat(fullBlocks) +
      (partialIndex > 0 ? blocks[partialIndex] : '') +
      '░'.repeat(Math.max(0, emptyBlocks))
    );
  });
</script>

<span class="progress" aria-label={`${Math.round(value * 100)}%`}>
  <span class="bar">{bar}</span>
  <span class="pct">{Math.round(value * 100)}%</span>
</span>

<style>
  .progress {
    display: inline-flex;
    gap: 0.5em;
    font-family: monospace;
  }

  .bar {
    color: var(--color-accent, #7c3aed);
  }

  .pct {
    color: var(--color-text-muted, #666);
    font-size: 0.85em;
    min-width: 3ch;
    text-align: right;
  }
</style>
