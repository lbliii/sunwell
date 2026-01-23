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
    background: var(--bg-primary);
    border-radius: var(--radius-md);
    overflow: hidden;
    font-family: var(--font-mono);
  }
  
  .terminal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-1) var(--space-2);
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border-subtle);
  }
  
  .terminal-title {
    font-size: var(--text-xs);
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
    background: var(--bg-tertiary);
  }
  
  .terminal-output {
    flex: 1;
    padding: var(--space-2);
    overflow-y: auto;
    font-size: var(--text-sm);
    color: var(--success); /* Terminal green */
  }
  
  .output-line {
    white-space: pre-wrap;
    margin-bottom: 2px;
  }
  
  .terminal-input {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-2);
    border-top: 1px solid var(--border-subtle);
  }
  
  .prompt {
    color: var(--success); /* Terminal green */
  }
  
  .terminal-input input {
    flex: 1;
    background: transparent;
    border: none;
    color: var(--success); /* Terminal green */
    font-family: inherit;
    font-size: var(--text-sm);
    outline: none;
  }
  
  .terminal-input input::placeholder {
    color: var(--text-tertiary);
  }
</style>
