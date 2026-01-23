<!--
  Projects — Dedicated Project Manager Page (RFC-096)
  
  Full-page project management with all controls:
  - Filtering, sorting, search
  - Bulk operations
  - Keyboard navigation
-->
<script lang="ts">
  import { ProjectManager } from '../components';
  import Button from '../components/Button.svelte';
  import { goHome, goToProject } from '../stores/app.svelte';
  import { openProject, analyzeProject } from '../stores/project.svelte';
  
  async function handleOpenProject(path: string) {
    await openProject(path);
    analyzeProject(path);
    goToProject();
  }
</script>

<div class="projects-page">
  <header class="page-header">
    <Button variant="ghost" onclick={goHome}>
      ← Back to Home
    </Button>
    <h1 class="page-title">Project Manager</h1>
  </header>
  
  <main class="page-content">
    <ProjectManager 
      mode="page"
      onOpenProject={handleOpenProject}
    />
  </main>
</div>

<style>
  .projects-page {
    display: flex;
    flex-direction: column;
    height: 100vh;
    background: var(--bg-primary);
  }
  
  .page-header {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    padding: var(--space-4);
    border-bottom: 1px solid var(--border-subtle);
    background: var(--bg-secondary);
  }
  
  .page-title {
    margin: 0;
    font-size: var(--text-lg);
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .page-content {
    flex: 1;
    overflow-y: auto;
    padding: var(--space-6);
  }
</style>
