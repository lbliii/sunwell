<!--
  Home — Launch screen
  
  The minimal, beautiful entry point. Just a logo, input, and projects list.
  Shows all projects from ~/Sunwell/projects/ with status and resume capability.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import Logo from '../components/Logo.svelte';
  import InputBar from '../components/InputBar.svelte';
  import RecentProjects from '../components/RecentProjects.svelte';
  import { goToProject, goToPlanning } from '../stores/app';
  import { 
    discoveredProjects,
    isScanning,
    scanProjects, 
    createProject,
    openProject,
    resumeProject,
  } from '../stores/project';
  import { runGoal, agentState } from '../stores/agent';
  import type { ProjectStatus } from '$lib/types';
  
  let inputValue = '';
  let inputBar: InputBar;
  
  onMount(() => {
    scanProjects();
    inputBar?.focus();
  });
  
  async function handleSubmit(event: CustomEvent<string>) {
    const goal = event.detail;
    if (!goal) return;
    
    // Create a new project from the goal
    createProject(goal);
    
    // Start the agent
    await runGoal(goal);
    
    // Navigate to project view
    goToProject();
  }
  
  async function handleSelectProject(event: CustomEvent<ProjectStatus>) {
    const project = event.detail;
    await openProject(project.path);
    goToProject();
  }
  
  async function handleResumeProject(event: CustomEvent<ProjectStatus>) {
    const project = event.detail;
    
    // Open the project first
    await openProject(project.path);
    
    // Navigate to project view
    goToProject();
    
    // Resume the agent
    await resumeProject(project.path);
  }
  
  function handleViewDag() {
    goToPlanning();
  }
</script>

<div class="home">
  <div class="hero">
    <Logo size="lg" />
    
    <div class="input-section">
      <InputBar
        bind:this={inputBar}
        bind:value={inputValue}
        placeholder="What would you like to create?"
        autofocus
        on:submit={handleSubmit}
      />
    </div>
    
    <RecentProjects 
      projects={$discoveredProjects}
      loading={$isScanning}
      on:select={handleSelectProject}
      on:resume={handleResumeProject}
    />
    
    <!-- Quick actions -->
    <div class="quick-actions">
      <button class="quick-action" on:click={handleViewDag}>
        <span class="action-icon">⬡</span>
        <span class="action-label">View Pipeline</span>
      </button>
    </div>
  </div>
  
  <footer class="version">
    v0.1.0
  </footer>
</div>

<style>
  .home {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    padding: var(--space-8);
  }
  
  .hero {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-8);
    animation: fadeIn 0.3s ease;
  }
  
  .input-section {
    width: 100%;
    display: flex;
    justify-content: center;
    margin-top: var(--space-8);
  }
  
  .quick-actions {
    display: flex;
    gap: var(--space-3);
    margin-top: var(--space-4);
  }
  
  .quick-action {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-4);
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    color: var(--text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  
  .quick-action:hover {
    background: var(--bg-tertiary);
    border-color: var(--text-tertiary);
    color: var(--text-primary);
  }
  
  .action-icon {
    font-size: var(--text-base);
  }
  
  .version {
    text-align: right;
    color: var(--text-tertiary);
    font-size: var(--text-xs);
  }
  
  @keyframes fadeIn {
    from { 
      opacity: 0;
      transform: translateY(10px);
    }
    to { 
      opacity: 1;
      transform: translateY(0);
    }
  }
</style>
