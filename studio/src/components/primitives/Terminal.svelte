<!--
  Terminal Primitive (RFC-072)
  
  Terminal emulator for command execution.
-->
<script lang="ts">
  import type { PrimitiveProps } from './types';
  import { emitPrimitiveEvent } from '../../stores/surface.svelte';
  
  interface Props extends PrimitiveProps {}
  
  let { size }: Props = $props();
  
  let output = $state<string[]>(['$ Ready']);
  let input = $state('');
  
  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && input.trim()) {
      output = [...output, `$ ${input}`, 'Command executed...'];
      emitPrimitiveEvent('Terminal', 'terminal_output', { command: input });
      input = '';
    }
  }
</script>

<div class="terminal" data-size={size}>
  <div class="terminal-header">
    <span class="terminal-title">Terminal</span>
    <div class="terminal-controls">
      <span class="control"></span>
      <span class="control"></span>
      <span class="control"></span>
    </div>
  </div>
  <div class="terminal-output">
    {#each output as line}
      <div class="output-line">{line}</div>
    {/each}
  </div>
  <div class="terminal-input">
    <span class="prompt">$</span>
    <input 
      type="text" 
      bind:value={input}
      onkeydown={handleKeydown}
      placeholder="Enter command..."
    />
  </div>
</div>

<style>
  .terminal {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: #1a1a1a;
    border-radius: var(--radius-md);
    overflow: hidden;
    font-family: var(--font-mono);
  }
  
  .terminal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-xs) var(--spacing-sm);
    background: #2a2a2a;
  }
  
  .terminal-title {
    font-size: 0.75rem;
    color: var(--text-secondary);
  }
  
  .terminal-controls {
    display: flex;
    gap: 6px;
  }
  
  .control {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: #444;
  }
  
  .terminal-output {
    flex: 1;
    padding: var(--spacing-sm);
    overflow-y: auto;
    font-size: 0.875rem;
    color: #0f0;
  }
  
  .output-line {
    white-space: pre-wrap;
    margin-bottom: 2px;
  }
  
  .terminal-input {
    display: flex;
    align-items: center;
    gap: var(--spacing-xs);
    padding: var(--spacing-sm);
    border-top: 1px solid #333;
  }
  
  .prompt {
    color: #0f0;
  }
  
  .terminal-input input {
    flex: 1;
    background: transparent;
    border: none;
    color: #0f0;
    font-family: inherit;
    font-size: 0.875rem;
    outline: none;
  }
</style>
