<!--
  Switch — Holy Light styled toggle switch (Svelte 5)
  
  Features:
  - Animated toggle with gold accent
  - Label support (left or right)
  - Disabled state
-->
<script lang="ts">
  import { uniqueId } from '$lib/a11y';
  
  interface Props {
    checked?: boolean;
    label?: string;
    labelPosition?: 'left' | 'right';
    size?: 'sm' | 'md';
    disabled?: boolean;
    onchange?: (checked: boolean) => void;
  }
  
  let {
    checked = $bindable(false),
    label,
    labelPosition = 'right',
    size = 'md',
    disabled = false,
    onchange,
  }: Props = $props();
  
  const switchId = uniqueId('switch');
  
  function handleClick() {
    if (!disabled) {
      checked = !checked;
      onchange?.(checked);
    }
  }
</script>

<div class="switch-wrapper {size}" class:disabled class:label-left={labelPosition === 'left'}>
  {#if label && labelPosition === 'left'}
    <span class="switch-label">{label}</span>
  {/if}
  
  <button
    type="button"
    role="switch"
    id={switchId}
    aria-checked={checked}
    aria-label={label}
    class="switch-track"
    class:checked
    {disabled}
    onclick={handleClick}
  >
    <span class="switch-thumb"></span>
  </button>
  
  {#if label && labelPosition === 'right'}
    <span class="switch-label">{label}</span>
  {/if}
</div>

<style>
  .switch-wrapper {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
  }
  
  .switch-wrapper.disabled {
    opacity: 0.5;
  }
  
  /* ═══════════════════════════════════════════════════════════════
     TRACK
     ═══════════════════════════════════════════════════════════════ */
  .switch-track {
    position: relative;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-full);
    cursor: pointer;
    transition: 
      background var(--transition-fast),
      border-color var(--transition-fast);
  }
  
  /* Size variants */
  .md .switch-track {
    width: 44px;
    height: 24px;
  }
  
  .sm .switch-track {
    width: 36px;
    height: 20px;
  }
  
  .switch-track:hover:not(:disabled) {
    border-color: var(--border-default);
  }
  
  .switch-track:focus-visible {
    outline: 2px solid var(--border-emphasis);
    outline-offset: 2px;
  }
  
  .switch-track.checked {
    background: var(--ui-gold);
    border-color: var(--ui-gold);
  }
  
  .switch-track:disabled {
    cursor: not-allowed;
  }
  
  /* ═══════════════════════════════════════════════════════════════
     THUMB
     ═══════════════════════════════════════════════════════════════ */
  .switch-thumb {
    position: absolute;
    top: 2px;
    left: 2px;
    background: var(--text-secondary);
    border-radius: var(--radius-full);
    transition: 
      transform var(--transition-fast),
      background var(--transition-fast);
  }
  
  .md .switch-thumb {
    width: 18px;
    height: 18px;
  }
  
  .sm .switch-thumb {
    width: 14px;
    height: 14px;
  }
  
  .switch-track.checked .switch-thumb {
    background: var(--bg-primary);
  }
  
  .md .switch-track.checked .switch-thumb {
    transform: translateX(20px);
  }
  
  .sm .switch-track.checked .switch-thumb {
    transform: translateX(16px);
  }
  
  /* ═══════════════════════════════════════════════════════════════
     LABEL
     ═══════════════════════════════════════════════════════════════ */
  .switch-label {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-primary);
    cursor: pointer;
    user-select: none;
  }
  
  .disabled .switch-label {
    cursor: not-allowed;
  }
</style>
