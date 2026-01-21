<!--
  FileTree — Browse project files while tasks run (Svelte 5)
  
  Simple expandable tree view of project files.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import type { FileEntry } from '$lib/types';
  
  interface Props {
    path?: string;
    files?: FileEntry[];
    onselect?: (detail: { path: string; name: string; isDir: boolean }) => void;
  }
  
  let { path = '', files: externalFiles, onselect }: Props = $props();
  
  let files = $state<FileEntry[]>([]);
  let isLoading = $state(true);
  let _error = $state<string | null>(null);
  let expandedDirs = $state(new Set<string>());
  let selectedFile = $state<string | null>(null);
  let fileContent = $state<string | null>(null);
  let isLoadingFile = $state(false);
  
  onMount(async () => {
    if (externalFiles) {
      files = externalFiles;
      isLoading = false;
    } else {
      await loadFiles();
    }
  });
  
  // Update files when externalFiles prop changes
  $effect(() => {
    if (externalFiles) {
      files = externalFiles;
      isLoading = false;
    }
  });
  
  async function loadFiles() {
    if (!path) {
      isLoading = false;
      return;
    }
    
    try {
      isLoading = true;
      _error = null;
      const { invoke } = await import('@tauri-apps/api/core');
      files = await invoke<FileEntry[]>('list_project_files', { 
        path,
        maxDepth: 2
      });
    } catch (e) {
      _error = e instanceof Error ? e.message : String(e);
      files = getDemoFiles();
    } finally {
      isLoading = false;
    }
  }
  
  function getDemoFiles(): FileEntry[] {
    return [
      { name: 'src', path: '/src', is_dir: true, children: [
        { name: 'app.py', path: '/src/app.py', is_dir: false, children: undefined, size: 1240 },
        { name: 'models.py', path: '/src/models.py', is_dir: false, children: undefined, size: 890 },
        { name: 'routes.py', path: '/src/routes.py', is_dir: false, children: undefined, size: 2100 },
      ], size: undefined },
      { name: 'tests', path: '/tests', is_dir: true, children: [
        { name: 'test_app.py', path: '/tests/test_app.py', is_dir: false, children: undefined, size: 650 },
      ], size: undefined },
      { name: 'requirements.txt', path: '/requirements.txt', is_dir: false, children: undefined, size: 120 },
      { name: 'README.md', path: '/README.md', is_dir: false, children: undefined, size: 450 },
    ];
  }
  
  function toggleDir(dirPath: string) {
    const newSet = new Set(expandedDirs);
    if (newSet.has(dirPath)) {
      newSet.delete(dirPath);
    } else {
      newSet.add(dirPath);
    }
    expandedDirs = newSet;
  }
  
  async function selectFile(file: FileEntry) {
    if (file.is_dir) {
      toggleDir(file.path);
      return;
    }
    
    // Dispatch select event for external handling
    onselect?.({ path: file.path, name: file.name, isDir: file.is_dir });
    
    // Also show inline preview
    selectedFile = file.path;
    
    try {
      isLoadingFile = true;
      const { invoke } = await import('@tauri-apps/api/core');
      fileContent = await invoke<string>('read_file_contents', { 
        path: file.path,
        maxSize: 50000
      });
    } catch (e) {
      fileContent = `// Preview unavailable\n// ${e}`;
    } finally {
      isLoadingFile = false;
    }
  }
  
  function closePreview() {
    selectedFile = null;
    fileContent = null;
  }
  
  function formatSize(bytes: number | undefined): string {
    if (bytes === undefined) return '';
    if (bytes < 1024) return `${bytes}B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
  }
  
  function getFileIcon(name: string, isDir: boolean): string {
    if (isDir) return '[+]';
    const ext = name.split('.').pop()?.toLowerCase();
    switch (ext) {
      case 'py': return '.py';
      case 'js': return '.js';
      case 'ts': return '.ts';
      case 'jsx': case 'tsx': return '.tx';
      case 'rs': return '.rs';
      case 'go': return '.go';
      case 'md': return '.md';
      case 'json': return '{ }';
      case 'yaml': case 'yml': return '.ym';
      case 'html': return '.ht';
      case 'css': return '.cs';
      case 'txt': return '.tx';
      default: return '---';
    }
  }
  
  function flattenFiles(entries: FileEntry[], depth = 0): Array<FileEntry & { depth: number; visible: boolean }> {
    const result: Array<FileEntry & { depth: number; visible: boolean }> = [];
    
    for (const entry of entries) {
      result.push({ ...entry, depth, visible: true });
      
      if (entry.is_dir && entry.children && expandedDirs.has(entry.path)) {
        const children = flattenFiles(entry.children, depth + 1);
        result.push(...children);
      }
    }
    
    return result;
  }
  
  let flatFiles = $derived(flattenFiles(files));
</script>

<div class="file-tree" role="tree" aria-label="Project files">
  {#if isLoading}
    <div class="loading">Loading files...</div>
  {:else if files.length === 0}
    <div class="empty">No files found</div>
  {:else}
    <div class="tree-content">
      <!-- File List -->
      <div class="file-list">
        {#each flatFiles as file (file.path)}
          <button 
            class="file-node"
            class:selected={selectedFile === file.path}
            class:directory={file.is_dir}
            style="padding-left: {file.depth * 16 + 8}px"
            onclick={() => selectFile(file)}
            role="treeitem"
            aria-expanded={file.is_dir ? expandedDirs.has(file.path) : undefined}
            aria-selected={selectedFile === file.path}
            type="button"
          >
            {#if file.is_dir}
              <span class="expand-icon" aria-hidden="true">{expandedDirs.has(file.path) ? '▾' : '▸'}</span>
            {:else}
              <span class="expand-icon"></span>
            {/if}
            <span class="file-icon" aria-hidden="true">{getFileIcon(file.name, file.is_dir)}</span>
            <span class="file-name">{file.name}</span>
            {#if file.size}
              <span class="file-size">{formatSize(file.size)}</span>
            {/if}
          </button>
        {/each}
      </div>
      
      <!-- File Preview -->
      {#if selectedFile && fileContent !== null}
        <div class="file-preview">
          <div class="preview-header">
            <span class="preview-name">{selectedFile.split('/').pop()}</span>
            <button class="preview-close" onclick={closePreview} aria-label="Close preview" type="button">×</button>
          </div>
          <pre class="preview-content">{#if isLoadingFile}Loading...{:else}{fileContent}{/if}</pre>
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .file-tree {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    overflow: hidden;
    max-height: 300px;
    display: flex;
    flex-direction: column;
  }
  
  .loading, .empty {
    padding: var(--space-4);
    color: var(--text-tertiary);
    font-size: var(--text-sm);
    text-align: center;
  }
  
  .tree-content {
    display: flex;
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }
  
  .file-list {
    flex: 1;
    overflow-y: auto;
    padding: var(--space-2) 0;
    min-width: 200px;
  }
  
  .file-node {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    width: 100%;
    padding: var(--space-1) var(--space-2);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-secondary);
    text-align: left;
    transition: background var(--transition-fast);
    background: transparent;
    border: none;
    cursor: pointer;
  }
  
  .file-node:hover {
    background: var(--bg-tertiary);
    color: var(--text-primary);
  }
  
  .file-node.selected {
    background: var(--bg-tertiary);
    color: var(--text-primary);
  }
  
  .file-node:focus-visible {
    outline: 2px solid rgba(201, 162, 39, 0.4);
    outline-offset: -2px;
  }
  
  .expand-icon {
    width: 12px;
    font-size: 10px;
    color: var(--text-tertiary);
    flex-shrink: 0;
  }
  
  .file-icon {
    font-size: var(--text-sm);
    flex-shrink: 0;
  }
  
  .file-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .file-size {
    color: var(--text-tertiary);
    font-size: 10px;
    flex-shrink: 0;
  }
  
  /* File Preview */
  .file-preview {
    width: 50%;
    border-left: 1px solid var(--border-color);
    display: flex;
    flex-direction: column;
    background: var(--bg-primary);
  }
  
  .preview-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-2) var(--space-3);
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border-color);
    flex-shrink: 0;
  }
  
  .preview-name {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-secondary);
  }
  
  .preview-close {
    color: var(--text-tertiary);
    font-size: var(--text-base);
    padding: 0 var(--space-1);
    line-height: 1;
    background: transparent;
    border: none;
    cursor: pointer;
  }
  
  .preview-close:hover {
    color: var(--text-primary);
  }
  
  .preview-content {
    flex: 1;
    margin: 0;
    padding: var(--space-3);
    font-family: var(--font-mono);
    font-size: 11px;
    line-height: 1.5;
    color: var(--text-secondary);
    overflow: auto;
    white-space: pre-wrap;
    word-break: break-all;
  }
  
  /* Scrollbar */
  .file-list::-webkit-scrollbar,
  .preview-content::-webkit-scrollbar {
    width: 6px;
  }
  
  .file-list::-webkit-scrollbar-track,
  .preview-content::-webkit-scrollbar-track {
    background: transparent;
  }
  
  .file-list::-webkit-scrollbar-thumb,
  .preview-content::-webkit-scrollbar-thumb {
    background: var(--border-color);
    border-radius: 3px;
  }
</style>
