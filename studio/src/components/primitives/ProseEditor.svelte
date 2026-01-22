<!--
  ProseEditor Primitive (RFC-072)
  
  Long-form writing editor with distraction-free mode.
-->
<script lang="ts">
  import { untrack } from 'svelte';
  import type { WritingPrimitiveProps } from './types';
  import { emitPrimitiveEvent } from '../../stores/surface.svelte';
  
  interface Props extends WritingPrimitiveProps {}
  
  let { size, content: propContent, title, seed }: Props = $props();
  
  // Extract initial value (intentional one-time capture from props)
  const initialValue = untrack(() => propContent ?? seed?.content as string ?? '');
  let content = $state(initialValue);
  let wordCount = $derived(content.split(/\s+/).filter(w => w.length > 0).length);
  
  function handleChange(e: Event) {
    const target = e.target as HTMLTextAreaElement;
    content = target.value;
    emitPrimitiveEvent('ProseEditor', 'file_edit', { content, wordCount });
  }
</script>

<div class="prose-editor" data-size={size}>
  {#if title}
    <h1 class="document-title">{title}</h1>
  {/if}
  <textarea 
    class="prose-content"
    value={content}
    oninput={handleChange}
    placeholder="Begin writing..."
  ></textarea>
  <div class="prose-footer">
    <span class="word-count">{wordCount} words</span>
  </div>
</div>

<style>
  .prose-editor {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: var(--bg-primary);
    padding: var(--spacing-xl);
    overflow: hidden;
  }
  
  .document-title {
    font-family: var(--font-serif, Georgia, serif);
    font-size: 2rem;
    font-weight: 400;
    color: var(--text-primary);
    margin-bottom: var(--spacing-lg);
    border: none;
    outline: none;
  }
  
  .prose-content {
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    resize: none;
    font-family: var(--font-serif, Georgia, serif);
    font-size: 1.125rem;
    line-height: 1.8;
    color: var(--text-primary);
  }
  
  .prose-content::placeholder {
    color: var(--text-tertiary);
  }
  
  .prose-footer {
    padding-top: var(--spacing-md);
    border-top: 1px solid var(--border-subtle);
  }
  
  .word-count {
    font-size: 0.75rem;
    color: var(--text-tertiary);
  }
</style>
