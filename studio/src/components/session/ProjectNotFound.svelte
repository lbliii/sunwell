<!--
  ProjectNotFound — Error display when URL slug doesn't resolve (RFC-133 Phase 2)
  
  Shows a friendly error when user navigates to a project slug that doesn't exist,
  with options to pick a different project or go home.
-->
<script lang="ts">
  import Button from '../Button.svelte';
  
  interface Props {
    slug: string;
    onPickProject: () => void;
    onGoHome: () => void;
  }
  
  let { slug, onPickProject, onGoHome }: Props = $props();
</script>

<div class="not-found">
  <div class="icon">📭</div>
  <h2 class="title">Project Not Found</h2>
  <p class="message">
    The project <code>{slug}</code> doesn't exist or has been removed.
  </p>
  <p class="hint">
    This can happen if the project was deleted, renamed, or if you followed a stale link.
  </p>
  <div class="actions">
    <Button variant="secondary" onclick={onGoHome}>
      Go Home
    </Button>
    <Button onclick={onPickProject}>
      Pick a Project
    </Button>
  </div>
</div>

<style>
  .not-found {
    text-align: center;
    padding: var(--space-8) var(--space-6);
    max-width: 400px;
    margin: 0 auto;
  }
  
  .icon {
    font-size: 3rem;
    margin-bottom: var(--space-4);
  }
  
  .title {
    font-size: var(--text-xl);
    font-weight: 600;
    color: var(--text-primary);
    margin: 0 0 var(--space-3) 0;
  }
  
  .message {
    color: var(--text-secondary);
    margin: 0 0 var(--space-2) 0;
  }
  
  .message code {
    background: var(--bg-tertiary);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-primary);
  }
  
  .hint {
    font-size: var(--text-sm);
    color: var(--text-tertiary);
    margin: 0 0 var(--space-6) 0;
  }
  
  .actions {
    display: flex;
    gap: var(--space-3);
    justify-content: center;
  }
</style>
