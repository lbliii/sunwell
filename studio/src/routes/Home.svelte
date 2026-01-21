<!--
  Home — Holy Light styled launch screen (Svelte 5)
  
  The minimal, beautiful entry point approaching the Sunwell.
  Features golden background aura and ambient rising motes.
-->
<script lang="ts">
  import { untrack } from 'svelte';
  import Logo from '../components/Logo.svelte';
  import InputBar from '../components/InputBar.svelte';
  import RecentProjects from '../components/RecentProjects.svelte';
  import RisingMotes from '../components/RisingMotes.svelte';
  import MouseMotes from '../components/MouseMotes.svelte';
  import Modal from '../components/Modal.svelte';
  import Button from '../components/Button.svelte';
  import SavedPrompts from '../components/SavedPrompts.svelte';
  import SparkleField from '../components/ui/SparkleField.svelte';
  import LensPicker from '../components/LensPicker.svelte';
  import LensBadge from '../components/LensBadge.svelte';
  import { goToProject, goToInterface } from '../stores/app.svelte';
  import { 
    project,
    scanProjects,
    openProject,
    resumeProject,
    deleteProject,
    archiveProject,
    iterateProject,
  } from '../stores/project.svelte';
  import { runGoal } from '../stores/agent.svelte';
  import { prompts, loadPrompts, removePrompt } from '../stores/prompts.svelte';
  import { lens, loadLenses, selectLens } from '../stores/lens.svelte';
  import type { ProjectStatus } from '$lib/types';
  
  let inputValue = $state('');
  let inputBar: InputBar;
  
  // RFC-064: Lens picker state
  let showLensPicker = $state(false);
  let pendingGoal = $state<string | null>(null);
  
  // Confirmation modal state
  let confirmModal = $state<{ 
    show: boolean; 
    title: string; 
    message: string; 
    action: 'delete' | 'archive'; 
    project: ProjectStatus | null;
    destructive: boolean;
  }>({ show: false, title: '', message: '', action: 'delete', project: null, destructive: false });
  
  function showConfirm(action: 'delete' | 'archive', proj: ProjectStatus) {
    if (action === 'delete') {
      confirmModal = {
        show: true,
        title: 'Delete Project',
        message: `Delete "${proj.name}" permanently? This cannot be undone.`,
        action: 'delete',
        project: proj,
        destructive: true,
      };
    } else {
      confirmModal = {
        show: true,
        title: 'Archive Project',
        message: `Archive "${proj.name}"? This will move it to ~/Sunwell/archived/`,
        action: 'archive',
        project: proj,
        destructive: false,
      };
    }
  }
  
  async function handleConfirm() {
    if (!confirmModal.project) return;
    
    const proj = confirmModal.project;
    const action = confirmModal.action;
    confirmModal = { ...confirmModal, show: false };
    
    if (action === 'delete') {
      await deleteProject(proj.path);
    } else {
      await archiveProject(proj.path);
    }
  }
  
  function handleCancel() {
    confirmModal = { ...confirmModal, show: false };
  }
  
  // One-time initialization on mount
  $effect(() => {
    untrack(() => {
      scanProjects();
      loadPrompts();
      loadLenses(); // RFC-064: Pre-load lenses
      inputBar?.focus();
    });
  });
  
  // RFC-064: Show lens picker before starting goal
  async function handleSubmit(goal: string) {
    if (!goal) return;
    pendingGoal = goal;
    showLensPicker = true;
  }
  
  // RFC-064: Handle lens selection and run goal
  async function handleLensConfirm(lensName: string | null, autoSelect: boolean) {
    if (!pendingGoal) return;
    
    selectLens(lensName, autoSelect);
    
    // Run goal with lens selection — pass lens info to backend
    const workspacePath = await runGoal(pendingGoal, undefined, lensName, autoSelect);
    if (workspacePath) {
      await openProject(workspacePath);
      goToProject();
    }
    
    pendingGoal = null;
  }
  
  function handleLensPickerClose() {
    showLensPicker = false;
    pendingGoal = null;
  }
  
  async function handleSelectProject(proj: ProjectStatus) {
    await openProject(proj.path);
    goToProject();
  }
  
  async function handleResumeProject(proj: ProjectStatus) {
    await openProject(proj.path);
    goToProject();
    await resumeProject(proj.path);
  }
  
  async function handleIterateProject(proj: ProjectStatus) {
    const result = await iterateProject(proj.path);
    if (result.success && result.new_path) {
      await openProject(result.new_path);
      goToProject();
    }
  }
  
  function handleArchiveProject(proj: ProjectStatus) {
    showConfirm('archive', proj);
  }
  
  function handleDeleteProject(proj: ProjectStatus) {
    showConfirm('delete', proj);
  }
  
  function handleSelectPrompt(text: string) {
    inputValue = text;
    inputBar?.focus();
  }
  
  async function handleRemovePrompt(text: string) {
    await removePrompt(text);
  }
</script>

<MouseMotes spawnRate={50} maxParticles={30}>
  {#snippet children()}
    <div class="home">
      <!-- Background aura centered on logo area -->
      <div class="background-aura"></div>
      
      <!-- Ambient rising motes (always visible, more prominent) -->
      <div class="ambient-motes">
        <RisingMotes count={12} intensity="normal" />
      </div>
      
      <div class="hero">
        <div class="logo-container">
          <div class="logo-sparkles">
            <SparkleField width={16} height={5} density={0.08} speed={250} />
          </div>
          <Logo size="lg" />
        </div>
        
        <div class="input-section">
          <InputBar
            bind:this={inputBar}
            bind:value={inputValue}
            placeholder="What would you like to create?"
            autofocus
            showMotes={true}
            onsubmit={handleSubmit}
          />
          <!-- RFC-064: Show selected lens badge -->
          {#if lens.selection.lens || !lens.selection.autoSelect}
            <div class="lens-indicator">
              <LensBadge size="sm" showAuto={false} />
            </div>
          {/if}
        </div>
        
        <SavedPrompts
          prompts={prompts.list}
          loading={prompts.isLoading}
          onselect={handleSelectPrompt}
          onremove={handleRemovePrompt}
        />
        
        <RecentProjects 
          projects={project.discovered}
          loading={project.isScanning}
          onselect={handleSelectProject}
          onresume={handleResumeProject}
          oniterate={handleIterateProject}
          onarchive={handleArchiveProject}
          ondelete={handleDeleteProject}
        />
      </div>
      
      <footer class="footer-nav">
        <button class="chat-mode-btn" onclick={goToInterface}>
          <span class="chat-icon">💬</span>
          <span class="chat-label">Chat Mode</span>
        </button>
        <span class="version">v0.1.0</span>
      </footer>
    </div>
  {/snippet}
</MouseMotes>

<!-- Confirmation Modal using accessible Modal component -->
<Modal 
  isOpen={confirmModal.show}
  onClose={handleCancel}
  title={confirmModal.title}
  description={confirmModal.message}
>
  <div class="modal-actions">
    <Button variant="ghost" onclick={handleCancel}>
      Cancel
    </Button>
    <Button 
      variant={confirmModal.destructive ? 'secondary' : 'primary'}
      onclick={handleConfirm}
    >
      {confirmModal.action === 'delete' ? 'Delete' : 'Archive'}
    </Button>
  </div>
</Modal>

<!-- RFC-064: Lens Picker Modal -->
<LensPicker
  isOpen={showLensPicker}
  onClose={handleLensPickerClose}
  onConfirm={handleLensConfirm}
/>

<style>
  .home {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    padding: var(--space-8);
    position: relative;
    overflow: hidden;
  }
  
  .background-aura {
    position: absolute;
    top: 0;
    left: 50%;
    transform: translateX(-50%);
    width: 100%;
    height: 60%;
    background: 
      radial-gradient(
        ellipse 60% 50% at 50% 30%,
        rgba(255, 215, 0, 0.06) 0%,
        rgba(218, 165, 32, 0.03) 30%,
        transparent 60%
      );
    pointer-events: none;
    z-index: 0;
  }
  
  .ambient-motes {
    position: absolute;
    top: 15%;
    left: 50%;
    transform: translateX(-50%);
    width: 500px;
    height: 300px;
    pointer-events: none;
    z-index: 1;
  }
  
  .hero {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-8);
    animation: fadeIn 0.3s ease;
    position: relative;
    z-index: 2;
  }
  
  .logo-container {
    position: relative;
  }
  
  .logo-sparkles {
    position: absolute;
    bottom: 100%;
    left: 50%;
    transform: translateX(-50%);
    opacity: 0.6;
    pointer-events: none;
  }
  
  .input-section {
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-2);
    margin-top: var(--space-8);
  }
  
  .lens-indicator {
    animation: fadeIn 0.2s ease;
  }
  
  .footer-nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    position: relative;
    z-index: 2;
  }
  
  .chat-mode-btn {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    color: var(--text-secondary);
    cursor: pointer;
    font-size: var(--text-sm);
    transition: all 0.2s;
  }
  
  .chat-mode-btn:hover {
    background: var(--bg-tertiary);
    border-color: var(--gold);
    color: var(--text-primary);
  }
  
  .chat-icon {
    font-size: var(--text-lg);
  }
  
  .chat-label {
    font-weight: 500;
  }
  
  .version {
    color: var(--text-tertiary);
    font-size: var(--text-xs);
  }
  
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }
  
  .modal-actions {
    display: flex;
    gap: var(--space-3);
    justify-content: flex-end;
    margin-top: var(--space-4);
  }
</style>
