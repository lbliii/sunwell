<!--
  ThinkingBlock.svelte — Inference Visibility (RFC-081, RFC-097)
  
  Shows real-time feedback during model generation:
  - Token counter with animated progress
  - Tokens per second display
  - Thinking phase preview
  - Completion indicator
  
  Auto-appears when model is generating, providing "beep boop bop" visibility.
  
  RFC-097: Updated to use Holy Light design tokens (no hardcoded colors).
-->
<script lang="ts">
  import { spring } from 'svelte/motion';
  import { fade, fly } from 'svelte/transition';

  interface Props {
    model?: string;
    tokens?: number;
    tokensPerSecond?: number | null;
    elapsed?: number;
    thinking?: string;
    phase?: string;
    isComplete?: boolean;
    ttft?: number | null;
  }

  let {
    model = "",
    tokens = 0,
    tokensPerSecond = null,
    elapsed = 0,
    thinking = "",
    phase = "",
    isComplete = false,
    ttft = null
  }: Props = $props();
  
  // Animated token counter with spring physics
  const displayTokens = spring(0, { stiffness: 0.1, damping: 0.5 });
  $effect(() => {
    displayTokens.set(tokens);
  });
  
  // Pulse animation while generating
  const pulse = $derived(!isComplete);
  
  // Format elapsed time
  function formatElapsed(seconds: number): string {
    if (seconds < 60) {
      return `${seconds.toFixed(1)}s`;
    }
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs.toFixed(0)}s`;
  }
  
  // Progress bar width (based on typical generation ~500 tokens)
  const progressWidth = $derived(Math.min(100, (tokens / 500) * 100));
</script>

<div 
  class="thinking-block"
  class:complete={isComplete}
  in:fly={{ y: 20, duration: 300 }}
  out:fade={{ duration: 200 }}
>
  <div class="header">
    <div class="model-indicator" class:pulse>
      <span class="brain">🧠</span>
      <span class="model-name">{model}</span>
    </div>
    <div class="metrics">
      <span class="elapsed">{formatElapsed(elapsed)}</span>
    </div>
  </div>
  
  <div class="progress-bar">
    <div class="fill" style:width="{progressWidth}%"></div>
    <div class="stats">
      <span class="token-count">{Math.round($displayTokens)} tokens</span>
      {#if tokensPerSecond}
        <span class="tps">{tokensPerSecond.toFixed(1)} tok/s</span>
      {/if}
    </div>
  </div>
  
  {#if thinking}
    <div class="thinking-preview" transition:fade>
      <div class="phase-label">💭 {phase}</div>
      <div class="content">{thinking.slice(0, 200)}{thinking.length > 200 ? '...' : ''}</div>
    </div>
  {/if}
  
  {#if isComplete}
    <div class="complete-indicator" in:fly={{ y: 10, duration: 200 }}>
      <span class="check">✓</span>
      <span class="complete-text">Complete</span>
      {#if ttft}
        <span class="ttft">TTFT: {ttft}ms</span>
      {/if}
    </div>
  {/if}
</div>

<style>
  .thinking-block {
    background: var(--bg-secondary);
    border-radius: var(--radius-lg);
    padding: var(--space-4);
    border: 1px solid var(--border-default);
    transition: border-color var(--transition-normal), box-shadow var(--transition-normal);
    font-family: var(--font-sans);
  }
  
  .thinking-block:not(.complete) {
    box-shadow: var(--glow-gold-subtle);
    animation: goldPulse 2s ease-in-out infinite;
  }
  
  .thinking-block.complete {
    border-color: var(--success);
    box-shadow: 0 0 12px rgba(var(--success-rgb), 0.15);
  }
  
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-3);
  }
  
  .model-indicator {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .brain {
    font-size: 1.2em;
    display: inline-block;
  }
  
  .pulse .brain {
    animation: pulse 1.5s ease-in-out infinite;
  }
  
  @keyframes pulse {
    0%, 100% { 
      opacity: 1; 
      transform: scale(1); 
    }
    50% { 
      opacity: 0.7; 
      transform: scale(1.1); 
    }
  }
  
  .model-name {
    font-size: var(--text-sm);
    color: var(--text-secondary);
  }
  
  .elapsed {
    font-variant-numeric: tabular-nums;
    font-size: var(--text-sm);
    color: var(--text-secondary);
  }
  
  .progress-bar {
    height: var(--space-6);
    background: var(--bg-tertiary);
    border-radius: var(--radius-md);
    overflow: hidden;
    position: relative;
  }
  
  .fill {
    height: 100%;
    background: var(--gradient-progress);
    transition: width 0.3s ease-out;
    border-radius: var(--radius-md);
    position: relative;
  }
  
  /* Shimmer effect on progress bar */
  .fill::after {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(
      90deg,
      transparent,
      rgba(255, 255, 255, 0.1),
      transparent
    );
    animation: shimmer 2s infinite;
  }
  
  .stats {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 var(--space-3);
    font-size: var(--text-sm);
    font-variant-numeric: tabular-nums;
    color: var(--text-primary);
    font-weight: 500;
  }
  
  .tps {
    color: var(--text-secondary);
  }
  
  .thinking-preview {
    margin-top: var(--space-3);
    padding: var(--space-3);
    background: var(--bg-primary);
    border-radius: var(--radius-md);
    border: 1px solid var(--border-subtle);
  }
  
  .phase-label {
    font-size: var(--text-xs);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-tertiary);
    margin-bottom: var(--space-2);
    font-weight: 600;
  }
  
  .content {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-secondary);
    white-space: pre-wrap;
    word-break: break-word;
    line-height: var(--leading-relaxed);
    max-height: 80px;
    overflow: hidden;
  }
  
  .complete-indicator {
    margin-top: var(--space-3);
    display: flex;
    align-items: center;
    gap: var(--space-2);
    color: var(--success);
    font-weight: 600;
  }
  
  .check {
    font-size: 1.1em;
  }
  
  .complete-text {
    flex: 1;
  }
  
  .ttft {
    font-size: var(--text-xs);
    color: var(--text-secondary);
    font-weight: normal;
    font-variant-numeric: tabular-nums;
  }
</style>
