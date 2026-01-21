<!--
  Preview Primitive (RFC-072)
  
  Live preview for web content, docs, etc.
-->
<script lang="ts">
  import type { PrimitiveProps } from './types';
  
  interface Props extends PrimitiveProps {
    url?: string;
  }
  
  let { size, url }: Props = $props();
</script>

<div class="preview" data-size={size}>
  <div class="preview-header">
    <span>👁️ Preview</span>
    {#if url}
      <span class="preview-url">{url}</span>
    {/if}
  </div>
  <div class="preview-content">
    {#if url}
      <iframe src={url} title="Preview"></iframe>
    {:else}
      <p class="placeholder">No preview available</p>
    {/if}
  </div>
</div>

<style>
  .preview {
    height: 100%;
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  
  .preview-header {
    display: flex;
    justify-content: space-between;
    padding: var(--spacing-sm) var(--spacing-md);
    border-bottom: 1px solid var(--border-subtle);
    color: var(--text-primary);
  }
  
  .preview-url {
    font-size: 0.75rem;
    color: var(--text-secondary);
    font-family: var(--font-mono);
  }
  
  .preview-content {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  
  .preview-content iframe {
    width: 100%;
    height: 100%;
    border: none;
  }
  
  .placeholder {
    color: var(--text-tertiary);
  }
</style>
