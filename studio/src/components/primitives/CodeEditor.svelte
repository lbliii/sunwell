<!--
  CodeEditor Primitive (RFC-072)
  
  Primary code editing primitive with syntax highlighting.
-->
<script lang="ts">
  import type { CodePrimitiveProps } from './types';
  import { emitPrimitiveEvent } from '../../stores/surface.svelte';
  
  interface Props extends CodePrimitiveProps {}
  
  let { size, file, language, seed }: Props = $props();
  
  let content = $state(seed?.content as string ?? '// Start coding...');
  
  function handleChange(e: Event) {
    const target = e.target as HTMLTextAreaElement;
    content = target.value;
    emitPrimitiveEvent('CodeEditor', 'file_edit', { file, content });
  }
</script>

<div class="code-editor" data-size={size}>
  <div class="editor-header">
    <span class="file-name">{file ?? 'Untitled'}</span>
    <span class="language">{language ?? 'text'}</span>
  </div>
  <textarea 
    class="editor-content"
    value={content}
    oninput={handleChange}
    spellcheck="false"
  ></textarea>
</div>

<style>
  .code-editor {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: var(--bg-primary);
    border-radius: var(--radius-md);
    overflow: hidden;
  }
  
  .editor-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-sm) var(--spacing-md);
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border-subtle);
  }
  
  .file-name {
    font-family: var(--font-mono);
    font-size: 0.875rem;
    color: var(--text-primary);
  }
  
  .language {
    font-size: 0.75rem;
    color: var(--text-secondary);
    text-transform: uppercase;
  }
  
  .editor-content {
    flex: 1;
    padding: var(--spacing-md);
    background: var(--bg-primary);
    color: var(--text-primary);
    font-family: var(--font-mono);
    font-size: 0.875rem;
    line-height: 1.6;
    border: none;
    resize: none;
    outline: none;
  }
  
  .editor-content:focus {
    outline: none;
  }
</style>
