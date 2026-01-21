<!--
  WorkingState — Running/working state UI (Svelte 5)
  RFC-064: Shows active lens during execution
-->
<script lang="ts">
  import { invoke } from '@tauri-apps/api/core';
  import Progress from '../Progress.svelte';
  import Button from '../Button.svelte';
  import LearningsPanel from '../LearningsPanel.svelte';
  import FileTree from '../FileTree.svelte';
  import Spinner from '../ui/Spinner.svelte';
  import LensBadge from '../LensBadge.svelte';
  import { PlanningPanel } from '../planning';
  import { project } from '../../stores/project.svelte';
  import { agent, stopAgent } from '../../stores/agent.svelte';
  import { formatDuration } from '$lib/format';
  
  let showFilePanel = $state(false);
  
  function handleStop() { stopAgent(); }
  
  async function handleOpenFiles() {
    if (!project.current?.path) return;
    try { await invoke('open_in_finder', { path: project.current.path }); } catch (e) { console.error('Failed to open files:', e); }
  }
  
  async function handleOpenTerminal() {
    if (!project.current?.path) return;
    try { await invoke('open_terminal', { path: project.current.path }); } catch (e) { console.error('Failed to open terminal:', e); }
  }
  
  async function handleOpenEditor() {
    if (!project.current?.path) return;
    try { await invoke('open_in_editor', { path: project.current.path }); } catch (e) { console.error('Failed to open editor:', e); }
  }
</script>

<div class="working animate-fadeIn">
  <div class="status-header">
    <Spinner style="braille" speed={60} />
    <span class="status-text">{agent.status === 'planning' ? 'Planning' : 'Building'}</span>
    <LensBadge size="sm" />
  </div>
  
  {#if agent.status === 'planning' || agent.planningCandidates.length > 0}
    <PlanningPanel />
  {/if}
  
  <Progress tasks={agent.tasks} currentIndex={agent.currentTaskIndex} totalExpected={agent.totalTasks} />
  
  <div class="working-footer">
    <span class="working-progress">{agent.completedTasks}/{agent.totalTasks} tasks</span>
    <span class="working-time">{formatDuration(agent.duration)}</span>
  </div>
  
  <div class="actions">
    <Button variant="ghost" size="sm" onclick={handleStop}>Stop</Button>
  </div>
  
  <div class="working-actions">
    <button class="action-btn" onclick={handleOpenFiles} aria-label="Open in Finder">
      <span class="action-icon" aria-hidden="true">▤</span><span>Files</span>
    </button>
    <button class="action-btn" onclick={handleOpenTerminal} aria-label="Open Terminal">
      <span class="action-icon" aria-hidden="true">⊳</span><span>Terminal</span>
    </button>
    <button class="action-btn" onclick={handleOpenEditor} aria-label="Open in Editor">
      <span class="action-icon" aria-hidden="true">⊡</span><span>Editor</span>
    </button>
    <button class="action-btn" onclick={() => showFilePanel = !showFilePanel} aria-expanded={showFilePanel}>
      <span class="action-icon" aria-hidden="true">{showFilePanel ? '▾' : '▸'}</span><span>Browse</span>
    </button>
  </div>
  
  {#if showFilePanel}
    <div class="file-panel">
      <FileTree path={project.current?.path ?? ''} />
    </div>
  {/if}
  
  <LearningsPanel learnings={agent.learnings} concepts={agent.concepts} />
</div>

<style>
  .working { display: flex; flex-direction: column; gap: var(--space-4); }
  .status-header { display: flex; align-items: center; gap: var(--space-2); font-size: var(--text-lg); }
  .status-icon { font-size: var(--text-xl); }
  .status-text { font-weight: 500; }
  .working-footer { display: flex; justify-content: space-between; color: var(--text-tertiary); font-size: var(--text-sm); margin-top: var(--space-4); }
  .actions { margin-top: var(--space-4); display: flex; justify-content: center; gap: var(--space-4); }
  .working-actions { display: flex; gap: var(--space-2); margin-top: var(--space-4); padding-top: var(--space-4); border-top: 1px solid var(--border-color); }
  .action-btn { display: flex; flex-direction: column; align-items: center; gap: var(--space-1); padding: var(--space-3) var(--space-4); background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: var(--radius-md); color: var(--text-secondary); font-size: var(--text-xs); cursor: pointer; transition: all var(--transition-fast); min-width: 70px; }
  .action-btn:hover, .action-btn:focus { background: var(--bg-tertiary); border-color: var(--text-tertiary); color: var(--text-primary); }
  .action-btn:focus { outline: 2px solid var(--accent); outline-offset: 2px; }
  .action-icon { font-size: var(--text-lg); }
  .file-panel { margin-top: var(--space-4); animation: slideDown 0.2s ease-out; }
  @keyframes slideDown { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
</style>
