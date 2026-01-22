<!--
  ProviderSelector — Model provider dropdown (RFC-Cloud-Model-Parity)
  
  Simple UI for selecting the model provider (ollama, openai, anthropic).
  Persists preference to localStorage via settings store.
-->
<script lang="ts">
  import { settings, setProvider, type ModelProvider } from '../stores/settings.svelte';
  
  // Provider metadata
  const providers: { id: ModelProvider; name: string; icon: string }[] = [
    { id: 'ollama', name: 'Ollama (Local)', icon: '◎' },
    { id: 'openai', name: 'OpenAI', icon: '◈' },
    { id: 'anthropic', name: 'Anthropic', icon: '◇' },
  ];
  
  function handleChange(e: Event) {
    const target = e.target as HTMLSelectElement;
    setProvider(target.value as ModelProvider);
  }
</script>

<div class="provider-selector">
  <label class="selector-label" for="provider-select">
    <span class="label-icon" aria-hidden="true">⚙</span>
    <span>Model</span>
  </label>
  <select 
    id="provider-select"
    value={settings.provider}
    onchange={handleChange}
    class="selector"
    aria-label="Select model provider"
  >
    {#each providers as p (p.id)}
      <option value={p.id}>{p.icon} {p.name}</option>
    {/each}
  </select>
</div>

<style>
  .provider-selector {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  
  .selector-label {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    white-space: nowrap;
  }
  
  .label-icon {
    font-size: var(--text-sm);
  }
  
  .selector {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-size: var(--text-xs);
    font-family: var(--font-mono);
    padding: var(--space-1) var(--space-2);
    cursor: pointer;
    transition: 
      border-color var(--transition-fast),
      color var(--transition-fast);
    min-width: 140px;
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23999' d='M3 4.5L6 7.5L9 4.5'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 6px center;
    padding-right: 24px;
  }
  
  .selector:hover,
  .selector:focus {
    border-color: var(--border-emphasis);
    color: var(--text-primary);
    outline: none;
  }
  
  .selector:focus-visible {
    outline: 2px solid var(--border-emphasis);
    outline-offset: 2px;
  }
  
  .selector option {
    background: var(--bg-primary);
    color: var(--text-primary);
    padding: var(--space-2);
  }
</style>
