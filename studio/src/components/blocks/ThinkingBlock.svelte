<!--
  ThinkingBlock.svelte — Inference Visibility (RFC-081)
  
  Shows real-time feedback during model generation:
  - Token counter with animated progress
  - Tokens per second display
  - Thinking phase preview
  - Completion indicator
  
  Auto-appears when model is generating, providing "beep boop bop" visibility.
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
    background: var(--surface-2, #1a1a2e);
    border-radius: 12px;
    padding: 16px;
    border: 1px solid var(--border, #2d2d44);
    transition: border-color 0.2s, box-shadow 0.2s;
    font-family: var(--font-sans, system-ui, sans-serif);
  }
  
  .thinking-block:not(.complete) {
    box-shadow: 0 0 20px rgba(99, 102, 241, 0.1);
  }
  
  .thinking-block.complete {
    border-color: var(--success, #10b981);
  }
  
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }
  
  .model-indicator {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 600;
    color: var(--text, #e2e8f0);
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
    font-size: 0.9em;
    color: var(--text-muted, #94a3b8);
  }
  
  .elapsed {
    font-variant-numeric: tabular-nums;
    font-size: 0.85em;
    color: var(--text-muted, #94a3b8);
  }
  
  .progress-bar {
    height: 28px;
    background: var(--surface-3, #252538);
    border-radius: 8px;
    overflow: hidden;
    position: relative;
  }
  
  .fill {
    height: 100%;
    background: linear-gradient(90deg, 
      var(--primary, #6366f1), 
      var(--accent, #8b5cf6)
    );
    transition: width 0.3s ease-out;
    border-radius: 8px;
  }
  
  .stats {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 12px;
    font-size: 0.85em;
    font-variant-numeric: tabular-nums;
    color: var(--text, #e2e8f0);
    font-weight: 500;
  }
  
  .tps {
    color: var(--text-muted, #94a3b8);
  }
  
  .thinking-preview {
    margin-top: 12px;
    padding: 12px;
    background: var(--surface-1, #0f0f1a);
    border-radius: 8px;
    border: 1px solid var(--border, #2d2d44);
  }
  
  .phase-label {
    font-size: 0.75em;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted, #94a3b8);
    margin-bottom: 6px;
    font-weight: 600;
  }
  
  .content {
    font-family: var(--font-mono, 'JetBrains Mono', monospace);
    font-size: 0.85em;
    color: var(--text-muted, #94a3b8);
    white-space: pre-wrap;
    word-break: break-word;
    line-height: 1.5;
    max-height: 80px;
    overflow: hidden;
  }
  
  .complete-indicator {
    margin-top: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--success, #10b981);
    font-weight: 600;
  }
  
  .check {
    font-size: 1.1em;
  }
  
  .complete-text {
    flex: 1;
  }
  
  .ttft {
    font-size: 0.8em;
    color: var(--text-muted, #94a3b8);
    font-weight: normal;
    font-variant-numeric: tabular-nums;
  }
</style>
