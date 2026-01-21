<!--
  CodeLayout — Layout for code projects (Svelte 5)
-->
<script lang="ts">
  import type { Snippet } from 'svelte';
  import BaseLayout from './BaseLayout.svelte';
  import Panel from '../components/Panel.svelte';
  
  interface Props {
    children: Snippet;
  }
  
  let { children }: Props = $props();
  
  let files = [
    { name: 'app.py', icon: '🐍' },
    { name: 'models.py', icon: '🐍' },
    { name: 'routes.py', icon: '🐍' },
    { name: 'config.py', icon: '🐍' },
    { name: 'requirements.txt', icon: '📄' },
  ];
</script>

<BaseLayout>
  {#snippet sidebarHeader()}
    <span class="sidebar-title">📁 Files</span>
  {/snippet}
  
  {#snippet sidebar()}
    <div class="file-list">
      {#each files as file}
        <button class="file-item">
          <span class="file-icon">{file.icon}</span>
          <span class="file-name">{file.name}</span>
        </button>
      {/each}
    </div>
  {/snippet}
  
  {#snippet children()}
    <div class="code-content">
      {@render children()}
    </div>
  {/snippet}
  
  {#snippet panel()}
    <aside class="right-panel">
      <Panel title="Tests" icon="🧪" collapsible collapsed>
        <p class="placeholder">No tests found</p>
      </Panel>
      <Panel title="Coverage" icon="📊" collapsible collapsed>
        <p class="placeholder">Run tests to see coverage</p>
      </Panel>
    </aside>
  {/snippet}
</BaseLayout>

<style>
  .sidebar-title { font-size: var(--text-sm); font-weight: 500; }
  .file-list { padding: var(--space-2); }
  .file-item { display: flex; align-items: center; gap: var(--space-2); width: 100%; padding: var(--space-2) var(--space-3); text-align: left; font-family: var(--font-mono); font-size: var(--text-sm); color: var(--text-secondary); border-radius: var(--radius-sm); transition: background var(--transition-fast), color var(--transition-fast); }
  .file-item:hover { background: var(--bg-tertiary); color: var(--text-primary); }
  .file-icon { font-size: var(--text-base); }
  .file-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .code-content { flex: 1; padding: var(--space-4); overflow: auto; }
  .right-panel { width: 280px; flex-shrink: 0; border-left: var(--border-width) solid var(--border-color); overflow-y: auto; display: flex; flex-direction: column; gap: var(--space-2); padding: var(--space-2); }
  .placeholder { color: var(--text-tertiary); font-size: var(--text-sm); }
</style>
