<!--
  RunButton — Intelligent project run button (RFC-066)
  
  Analyzes project and shows run options in a modal.
  AI-powered detection with user confirmation before execution.
  Auto-opens Preview when server is ready!
-->
<script lang="ts">
  /**
   * RunButton — Intelligent project run button (RFC-066)
   * RFC-113: Uses HTTP API for all communication.
   */
  import { apiPost, onEvent } from '$lib/socket';
  import { onMount } from 'svelte';
  import type { RunAnalysis, RunSession } from '$lib/types';
  import Modal from './Modal.svelte';
  import Button from './Button.svelte';
  import Spinner from './ui/Spinner.svelte';
  import RunAnalysisView from './RunAnalysisView.svelte';
  import { runStore, setActiveSession, clearActiveSession } from '../stores/run.svelte';
  import { goToPreview } from '../stores/app.svelte';
  
  interface Props {
    projectPath: string;
    compact?: boolean;
  }
  
  let { projectPath, compact = false }: Props = $props();
  
  let isAnalyzing = $state(false);
  let analysis = $state<RunAnalysis | null>(null);
  let showModal = $state(false);
  let isRunning = $state(false);
  let error = $state<string | null>(null);
  let editedCommand = $state<string>('');
  
  // Use centralized run store for session
  let activeSession = $derived(runStore.activeSession);
  
  // Watch for port readiness and auto-navigate to Preview
  $effect(() => {
    if (runStore.isPortReady && runStore.previewUrl) {
      console.log('Port ready! Navigating to Preview...');
      goToPreview();
    }
  });
  
  // Listen for session events via WebSocket
  onMount(() => {
    const unsubscribe = onEvent((event) => {
      if (event.type === 'run_session_started') {
        const payload = event.data as unknown as RunSession;
        if (payload.projectPath === projectPath) {
          setActiveSession(payload, analysis?.expectedUrl ?? undefined);
          showModal = false;
        }
      } else if (event.type === 'run_session_stopped') {
        const sessionId = (event.data as { sessionId: string }).sessionId || (event.data as unknown as string);
        if (activeSession?.id === sessionId) {
          clearActiveSession();
        }
      }
    });
    
    return () => {
      unsubscribe();
    };
  });
  
  async function handleClick() {
    if (activeSession) {
      // Stop running session
      try {
        await apiPost('/api/run/stop', { session_id: activeSession.id });
        clearActiveSession();
      } catch (e) {
        error = e instanceof Error ? e.message : String(e);
      }
      return;
    }
    
    // Analyze and show modal
    isAnalyzing = true;
    error = null;
    showModal = true;
    
    try {
      analysis = await apiPost<RunAnalysis>('/api/project/analyze-for-run', { 
        path: projectPath,
        force_refresh: false,
      });
      if (analysis) {
        editedCommand = analysis.command;
      }
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      isAnalyzing = false;
    }
  }
  
  async function handleRun(installFirst: boolean, remember: boolean) {
    if (!analysis || !editedCommand) return;
    isRunning = true;
    error = null;
    
    try {
      await apiPost('/api/project/run', {
        path: projectPath,
        command: editedCommand,
        install_first: installFirst,
        save_command: remember,
      });
      // Modal will close via event listener when session starts
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
      isRunning = false;
    }
  }
  
  async function handleRefresh() {
    isAnalyzing = true;
    error = null;
    
    try {
      analysis = await apiPost<RunAnalysis>('/api/project/analyze-for-run', { 
        path: projectPath,
        force_refresh: true,
      });
      if (analysis) {
        editedCommand = analysis.command;
      }
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      isAnalyzing = false;
    }
  }
  
  function handleClose() {
    showModal = false;
    isRunning = false;
    error = null;
  }
</script>

<button 
  class="run-btn" 
  class:compact 
  class:running={activeSession !== null}
  class:starting={runStore.isCheckingPort}
  onclick={handleClick}
  aria-label={activeSession ? "Stop project" : "Run project"}
>
  {#if activeSession}
    {#if runStore.isCheckingPort}
      <span class="run-icon starting" aria-hidden="true">⟳</span>
      {#if !compact}<span>Starting...</span>{/if}
    {:else}
      <span class="run-icon stop" aria-hidden="true">◼</span>
      {#if !compact}<span>Stop</span>{/if}
    {/if}
  {:else}
    <span class="run-icon" aria-hidden="true">▶</span>
    {#if !compact}<span>Run</span>{/if}
  {/if}
</button>

{#if showModal}
  <Modal 
    isOpen={true} 
    title="Run Project" 
    onClose={handleClose}
  >
    {#if isAnalyzing}
      <div class="analyzing">
        <Spinner />
        <p>Analyzing project...</p>
      </div>
    {:else if error && !analysis}
      <div class="error-state">
        <p class="error-message">{error}</p>
        <div class="error-actions">
          <Button variant="secondary" onclick={handleRefresh}>Retry</Button>
          <Button variant="ghost" onclick={handleClose}>Cancel</Button>
        </div>
      </div>
    {:else if analysis}
      <RunAnalysisView 
        {analysis} 
        {isRunning}
        {error}
        bind:editedCommand
        onrun={handleRun}
        onrefresh={handleRefresh}
      />
    {/if}
  </Modal>
{/if}

<style>
  .run-btn {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-3) var(--space-4);
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    color: var(--text-secondary);
    font-size: var(--text-xs);
    cursor: pointer;
    transition: all var(--transition-fast);
    min-width: 70px;
  }
  
  .run-btn:hover,
  .run-btn:focus {
    background: var(--bg-tertiary);
    border-color: var(--accent);
    color: var(--accent);
  }
  
  .run-btn:focus {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
  
  .run-btn.running {
    background: var(--error-bg);
    border-color: rgba(239, 68, 68, 0.3);
    color: var(--error);
  }
  
  .run-btn.running:hover {
    background: rgba(239, 68, 68, 0.2);
    border-color: var(--error);
  }
  
  .run-btn.compact {
    flex-direction: row;
    min-width: auto;
    padding: var(--space-2) var(--space-3);
  }
  
  .run-icon {
    font-size: var(--text-lg);
    color: var(--success);
    transition: color var(--transition-fast);
  }
  
  .run-btn:hover .run-icon,
  .run-btn:focus .run-icon {
    color: var(--accent);
  }
  
  .run-icon.stop {
    color: var(--error);
    font-size: var(--text-base);
  }
  
  .run-btn.running .run-icon.stop {
    animation: pulse 1s ease-in-out infinite;
  }
  
  .run-btn.starting {
    background: var(--warning-bg);
    border-color: rgba(234, 179, 8, 0.3);
    color: var(--warning);
  }
  
  .run-icon.starting {
    color: var(--warning);
    animation: spin 1s linear infinite;
  }
  
  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
  
  .analyzing {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-4);
    padding: var(--space-8);
    color: var(--text-secondary);
  }
  
  .analyzing p {
    margin: 0;
    font-size: var(--text-sm);
  }
  
  .error-state {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    padding: var(--space-4);
  }
  
  .error-message {
    color: var(--error);
    margin: 0;
    padding: var(--space-3);
    background: rgba(239, 68, 68, 0.1);
    border-radius: var(--radius-md);
    font-size: var(--text-sm);
  }
  
  .error-actions {
    display: flex;
    gap: var(--space-2);
    justify-content: flex-end;
  }
  
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
</style>
