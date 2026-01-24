<!--
  EmptyState — Shown when a visualization has no data (RFC-112)
  
  Prompts users to run a goal to generate real data.
-->
<script lang="ts">
  import { fade, fly } from 'svelte/transition';
  import { goToDemo } from '../../stores/app.svelte';
  
  interface Props {
    icon?: string;
    title?: string;
    message?: string;
    actionLabel?: string;
    onAction?: () => void;
  }
  
  let {
    icon = '🔭',
    title = 'No data yet',
    message = 'Run a goal to see this visualization come to life.',
    actionLabel = '🚀 Run a Goal',
    onAction = goToDemo,
  }: Props = $props();
</script>

<div class="empty-state" in:fade={{ duration: 300 }}>
  <div class="empty-content" in:fly={{ y: 20, duration: 400 }}>
    <span class="empty-icon">{icon}</span>
    <h3 class="empty-title">{title}</h3>
    <p class="empty-message">{message}</p>
    
    <button class="action-btn" onclick={onAction}>
      {actionLabel}
    </button>
    
    <p class="empty-hint">
      The Observatory visualizes real AI cognition — start a goal to generate data.
    </p>
  </div>
  
  <!-- Decorative background pattern -->
  <div class="bg-pattern">
    <svg viewBox="0 0 400 300" class="pattern-svg">
      <defs>
        <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
          <path d="M 40 0 L 0 0 0 40" fill="none" stroke="var(--border-subtle)" stroke-width="0.5" opacity="0.3"/>
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#grid)"/>
      
      <!-- Decorative nodes suggesting the visualization -->
      <circle cx="100" cy="100" r="6" fill="var(--ui-gold)" opacity="0.2"/>
      <circle cx="200" cy="150" r="8" fill="var(--ui-gold)" opacity="0.15"/>
      <circle cx="300" cy="100" r="5" fill="var(--ui-gold)" opacity="0.2"/>
      <circle cx="150" cy="200" r="7" fill="var(--ui-gold)" opacity="0.1"/>
      <circle cx="280" cy="220" r="6" fill="var(--ui-gold)" opacity="0.15"/>
      
      <!-- Connecting lines -->
      <path d="M 100 100 Q 150 125 200 150" fill="none" stroke="var(--ui-gold)" stroke-width="1" opacity="0.1"/>
      <path d="M 200 150 Q 250 125 300 100" fill="none" stroke="var(--ui-gold)" stroke-width="1" opacity="0.1"/>
      <path d="M 150 200 Q 200 200 280 220" fill="none" stroke="var(--ui-gold)" stroke-width="1" opacity="0.1"/>
    </svg>
  </div>
</div>

<style>
  .empty-state {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    min-height: 400px;
    position: relative;
    overflow: hidden;
  }
  
  .empty-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    max-width: 400px;
    padding: var(--space-8);
    position: relative;
    z-index: 1;
  }
  
  .empty-icon {
    font-size: 4rem;
    margin-bottom: var(--space-4);
    filter: grayscale(0.5);
    opacity: 0.8;
  }
  
  .empty-title {
    font-family: var(--font-serif);
    font-size: var(--text-xl);
    color: var(--text-primary);
    margin: 0 0 var(--space-2);
  }
  
  .empty-message {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-secondary);
    margin: 0 0 var(--space-6);
    line-height: 1.6;
  }
  
  .action-btn {
    padding: var(--space-3) var(--space-6);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--bg-primary);
    background: var(--gradient-ui-gold);
    border: none;
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  
  .action-btn:hover {
    transform: translateY(-2px);
    box-shadow: var(--glow-gold);
  }
  
  .empty-hint {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    margin: var(--space-4) 0 0;
    max-width: 300px;
  }
  
  .bg-pattern {
    position: absolute;
    inset: 0;
    pointer-events: none;
    opacity: 0.5;
  }
  
  .pattern-svg {
    width: 100%;
    height: 100%;
  }
</style>
