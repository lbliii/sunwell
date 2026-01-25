<!--
  SuggestedAction — RFC-106 suggested action with CTAs
  
  Shows the suggested next action with "Work on this" and "Dev Server" buttons.
  Extracted from ProjectOverview.svelte action section.
-->
<script lang="ts">
  import type { SuggestedAction as SuggestedActionType, DevCommand } from '$lib/types';
  import Button from '../Button.svelte';
  
  interface Props {
    action: SuggestedActionType;
    devCommand: DevCommand | null;
    onWorkOnGoal: (goalId: string) => void;
    onStartServer: (command: string) => void;
    onAddGoal: () => void;
  }
  
  let { action, devCommand, onWorkOnGoal, onStartServer, onAddGoal }: Props = $props();
  
  function handleAction() {
    switch (action.action_type) {
      case 'execute_goal':
      case 'continue_work':
        if (action.goal_id) onWorkOnGoal(action.goal_id);
        break;
      case 'start_server':
        if (action.command) onStartServer(action.command);
        break;
      case 'add_goal':
      case 'review':
        onAddGoal();
        break;
    }
  }
</script>

<section class="suggested-action">
  <h3 class="action-header">💡 Suggested</h3>
  <p class="action-description">{action.description}</p>
  {#if action.command}
    <code class="action-command">{action.command}</code>
  {/if}
  
  <div class="action-buttons">
    <Button variant="primary" onclick={handleAction}>
      ▶ Work on this
    </Button>
    
    {#if devCommand}
      <Button variant="secondary" onclick={() => onStartServer(devCommand.command)}>
        🖥️ Dev Server
      </Button>
    {/if}
    
    <Button variant="ghost" onclick={onAddGoal}>
      ➕ Add Goal
    </Button>
  </div>
</section>

<!-- Dev Command Details (collapsed) -->
{#if devCommand}
  <details class="dev-details">
    <summary>🖥️ Development Server</summary>
    <div class="dev-info">
      <p><strong>Command:</strong> <code>{devCommand.command}</code></p>
      {#if devCommand.expected_url}
        <p><strong>URL:</strong> {devCommand.expected_url}</p>
      {/if}
      {#if devCommand.prerequisites.length > 0}
        <p><strong>Prerequisites:</strong></p>
        <ul>
          {#each devCommand.prerequisites as prereq (prereq.command)}
            <li>{prereq.description} — <code>{prereq.command}</code></li>
          {/each}
        </ul>
      {/if}
    </div>
  </details>
{/if}

<style>
  .suggested-action {
    background: var(--bg-secondary);
    padding: var(--space-3);
    border-radius: var(--radius-md);
    border-left: 3px solid var(--success);
  }
  
  .action-header {
    margin: 0 0 var(--space-2) 0;
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .action-description {
    margin: 0;
    font-size: var(--text-sm);
    color: var(--text-secondary);
  }
  
  .action-command {
    display: block;
    margin-top: var(--space-2);
    padding: var(--space-1) var(--space-2);
    background: var(--bg-tertiary);
    border-radius: var(--radius-sm);
    font-size: var(--text-sm);
    font-family: var(--font-mono);
    color: var(--text-primary);
  }
  
  .action-buttons {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
    margin-top: var(--space-3);
  }
  
  .dev-details {
    font-size: var(--text-sm);
    color: var(--text-secondary);
    margin-top: var(--space-2);
  }
  
  .dev-details summary {
    cursor: pointer;
    padding: var(--space-1) 0;
  }
  
  .dev-info {
    margin-top: var(--space-2);
    padding-left: var(--space-4);
  }
  
  .dev-info p {
    margin: var(--space-1) 0;
  }
  
  .dev-info ul {
    margin: var(--space-1) 0;
    padding-left: var(--space-5);
  }
  
  .dev-info code {
    background: var(--bg-tertiary);
    padding: 1px 4px;
    border-radius: var(--radius-sm);
    font-size: var(--text-sm);
    font-family: var(--font-mono);
  }
</style>
