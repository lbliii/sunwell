<!--
  Preview — Preview screen (Svelte 5)
  
  Shows the running application/content in an embedded view.
  Can use URL from active run session OR launch_preview for content.
-->
<script lang="ts">
  import { untrack } from 'svelte';
  import Button from '../components/Button.svelte';
  import { goToProject } from '../stores/app.svelte';
  import { project } from '../stores/project.svelte';
  import { runStore, clearActiveSession } from '../stores/run.svelte';
  import { invoke } from '@tauri-apps/api/core';
  import type { PreviewSession } from '$lib/types';
  
  let session = $state<PreviewSession | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  
  // Check if we have a URL from an active run session
  let runUrl = $derived(runStore.previewUrl);
  let hasRunSession = $derived(runStore.isRunning && runUrl !== null);
  
  $effect(() => {
    // If we have an active run session with URL, use that immediately
    if (hasRunSession && runUrl) {
      untrack(() => {
        session = {
          url: runUrl,
          content: undefined,
          view_type: 'web_view',
          command: runStore.activeSession?.command ?? undefined,
          port: runStore.activeSession?.port ?? undefined,
        };
        loading = false;
      });
    } else {
      // Otherwise, try legacy launch_preview
      untrack(() => { launchPreview(); });
    }
    
    return () => { 
      // Only stop preview if not from run session
      if (!hasRunSession) {
        stopPreview(); 
      }
    };
  });
  
  async function launchPreview() {
    try {
      loading = true;
      error = null;
      session = await invoke<PreviewSession>('launch_preview');
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }
  
  async function stopPreview() {
    try { await invoke('stop_preview'); } catch (e) { console.error('Failed to stop preview:', e); }
  }
  
  async function handleStopRun() {
    if (runStore.activeSession) {
      try {
        await invoke('stop_project_run', { sessionId: runStore.activeSession.id });
        clearActiveSession();
      } catch (e) {
        console.error('Failed to stop run:', e);
      }
    }
  }
  
  function handleBack() {
    // Don't stop the run session, just navigate back
    if (!hasRunSession) {
      stopPreview();
    }
    goToProject();
  }
  
  function openInBrowser() {
    const url = session?.url ?? runUrl;
    if (url) window.open(url, '_blank');
  }
</script>

<div class="preview">
  <header class="header">
    <button class="back-btn" onclick={handleBack}>
      ← {project.current?.name ?? 'Project'} › preview
    </button>
  </header>
  
  <main class="content">
    {#if loading}
      <div class="loading">
        <span class="spinner">⟳</span>
        <span>Starting preview...</span>
      </div>
    {:else if error}
      <div class="error">
        <span class="error-icon">✗</span>
        <p class="error-message">{error}</p>
        <Button variant="secondary" onclick={launchPreview}>Try Again</Button>
      </div>
    {:else if session}
      {#if session.view_type === 'web_view' && session.url}
        <div class="webview-container">
          <iframe src={session.url} title="Preview" class="webview" sandbox="allow-scripts allow-forms allow-same-origin"></iframe>
        </div>
      {:else if session.view_type === 'terminal' && session.command}
        <div class="terminal-container">
          <div class="terminal-header">Terminal</div>
          <div class="terminal-content">
            <span class="terminal-prompt">$</span>
            <span class="terminal-command">{session.command}</span>
          </div>
        </div>
      {:else if session.view_type === 'prose' && session.content}
        <div class="prose-container">
          <article class="prose">{@html session.content}</article>
        </div>
      {:else if session.view_type === 'fountain' && session.content}
        <div class="screenplay-container">
          <div class="screenplay">{@html session.content}</div>
        </div>
      {:else if session.view_type === 'dialogue' && session.content}
        <div class="dialogue-container">
          <div class="dialogue"><p>{session.content}</p></div>
        </div>
      {:else}
        <div class="generic-container">
          <pre>{session.content ?? 'No content available'}</pre>
        </div>
      {/if}
    {:else}
      <div class="empty"><p>No preview available</p></div>
    {/if}
  </main>
  
  <footer class="footer">
    <nav class="footer-nav">
      <button class="nav-link" onclick={handleBack}>← back</button>
      {#if session?.url || runUrl}
        <span class="nav-sep">·</span>
        <button class="nav-link" onclick={openInBrowser}>open in browser</button>
      {/if}
      <span class="nav-sep">·</span>
      {#if hasRunSession}
        <button class="nav-link stop" onclick={handleStopRun}>■ stop server</button>
      {:else}
        <button class="nav-link" onclick={stopPreview}>stop</button>
      {/if}
    </nav>
  </footer>
</div>

<style>
  .preview { display: flex; flex-direction: column; height: 100vh; padding: var(--space-6); gap: var(--space-4); }
  .header { flex-shrink: 0; }
  .back-btn { color: var(--text-secondary); font-family: var(--font-mono); font-size: var(--text-sm); padding: var(--space-1) 0; transition: color var(--transition-fast); }
  .back-btn:hover { color: var(--text-primary); }
  .content { flex: 1; display: flex; flex-direction: column; border: var(--border-width) solid var(--border-color); border-radius: var(--radius-md); overflow: hidden; background: var(--bg-secondary); }
  .loading { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--space-3); color: var(--text-secondary); }
  .spinner { font-size: var(--text-2xl); animation: spin 1s linear infinite; }
  @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
  .error { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--space-4); }
  .error-icon { color: var(--error); font-size: var(--text-2xl); }
  .error-message { color: var(--text-secondary); text-align: center; max-width: 400px; }
  .webview-container { flex: 1; display: flex; }
  .webview { flex: 1; border: none; background: white; }
  .terminal-container { flex: 1; display: flex; flex-direction: column; }
  .terminal-header { padding: var(--space-2) var(--space-4); background: var(--bg-tertiary); font-size: var(--text-xs); color: var(--text-tertiary); border-bottom: var(--border-width) solid var(--border-color); }
  .terminal-content { flex: 1; padding: var(--space-4); font-family: var(--font-mono); font-size: var(--text-sm); background: var(--bg-primary); }
  .terminal-prompt { color: var(--success); margin-right: var(--space-2); }
  .terminal-command { color: var(--text-primary); }
  .prose-container { flex: 1; overflow-y: auto; display: flex; justify-content: center; padding: var(--space-8); }
  .screenplay-container { flex: 1; overflow-y: auto; padding: var(--space-8); }
  .screenplay { max-width: 600px; margin: 0 auto; font-family: 'Courier New', monospace; }
  .dialogue-container { flex: 1; display: flex; align-items: center; justify-content: center; padding: var(--space-8); }
  .dialogue { max-width: 500px; text-align: center; }
  .generic-container { flex: 1; overflow: auto; padding: var(--space-4); }
  .generic-container pre { background: transparent; padding: 0; }
  .empty { flex: 1; display: flex; align-items: center; justify-content: center; color: var(--text-tertiary); }
  .footer { flex-shrink: 0; }
  .footer-nav { display: flex; justify-content: center; gap: var(--space-2); color: var(--text-tertiary); font-size: var(--text-sm); }
  .nav-link { color: var(--text-secondary); transition: color var(--transition-fast); }
  .nav-link:hover { color: var(--text-primary); }
  .nav-link.stop { color: var(--error); }
  .nav-link.stop:hover { color: var(--error-muted); }
  .nav-sep { color: var(--text-tertiary); }
</style>
