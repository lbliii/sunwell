<!--
  Home — Launch screen
  
  The minimal, beautiful entry point. Just a logo, input, and recent projects.
  Matches the RFC mockup exactly.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import Logo from '../components/Logo.svelte';
  import InputBar from '../components/InputBar.svelte';
  import RecentProjects from '../components/RecentProjects.svelte';
  import { goToProject } from '../stores/app';
  import { 
    recentProjects, 
    loadRecentProjects, 
    createProject,
    openProject 
  } from '../stores/project';
  import { runGoal } from '../stores/agent';
  import type { RecentProject } from '$lib/types';
  
  let inputValue = '';
  let inputBar: InputBar;
  
  onMount(() => {
    loadRecentProjects();
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
  
  async function handleSelectProject(event: CustomEvent<RecentProject>) {
    const project = event.detail;
    await openProject(project.path);
    goToProject();
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
      projects={$recentProjects}
      on:select={handleSelectProject}
    />
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
