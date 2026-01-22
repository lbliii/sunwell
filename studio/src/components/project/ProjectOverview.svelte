<script lang="ts">
  /**
   * ProjectOverview — RFC-079 Project Intent Analyzer UI
   * 
   * Displays universal project understanding with:
   * - Project type and confidence
   * - Goal pipeline with current state
   * - Suggested next action
   * - Dev server controls (for code projects)
   */

  import type { ProjectAnalysis, PipelineStep, SuggestedAction } from '$lib/types';
  import { project, getAnalysisTypeEmoji, getAnalysisTypeName } from '$stores/project.svelte';
  import Button from '$components/Button.svelte';

  interface Props {
    analysis: ProjectAnalysis;
    onWorkOnGoal?: (goalId: string) => void;
    onStartServer?: (command: string) => void;
    onAddGoal?: () => void;
    onExplore?: () => void;
  }

  let { analysis, onWorkOnGoal, onStartServer, onAddGoal, onExplore }: Props = $props();

  // Computed
  const typeEmoji = $derived(getAnalysisTypeEmoji(analysis.project_type));
  const typeName = $derived(getAnalysisTypeName(analysis.project_type));
  const confidenceColor = $derived(
    analysis.confidence_level === 'high' ? 'var(--green)' :
    analysis.confidence_level === 'medium' ? 'var(--yellow)' : 'var(--red)'
  );
  const completionPercent = $derived(Math.round(analysis.completion_percent * 100));
  const hasGoals = $derived(analysis.pipeline.length > 0);
  const hasDevServer = $derived(analysis.dev_command !== null);

  function handleSuggestedAction(action: SuggestedAction) {
    switch (action.action_type) {
      case 'execute_goal':
      case 'continue_work':
        if (action.goal_id && onWorkOnGoal) onWorkOnGoal(action.goal_id);
        break;
      case 'start_server':
        if (action.command && onStartServer) onStartServer(action.command);
        break;
      case 'add_goal':
        if (onAddGoal) onAddGoal();
        break;
      case 'review':
        if (onExplore) onExplore();
        break;
    }
  }

  function getStepIcon(step: PipelineStep): string {
    switch (step.status) {
      case 'completed': return '✅';
      case 'in_progress': return '🔄';
      default: return '⏳';
    }
  }
</script>

<div class="project-overview">
  <!-- Header: Type & Confidence -->
  <header class="overview-header">
    <div class="type-badge">
      <span class="type-emoji">{typeEmoji}</span>
      <span class="type-name">{typeName} Project</span>
      {#if analysis.project_subtype}
        <span class="subtype">({analysis.project_subtype})</span>
      {/if}
    </div>
    <div class="confidence" style:color={confidenceColor}>
      {Math.round(analysis.confidence * 100)}% confident
    </div>
  </header>

  <!-- Detection Signals (collapsed by default) -->
  {#if analysis.detection_signals.length > 0}
    <details class="signals">
      <summary>Detection signals ({analysis.detection_signals.length})</summary>
      <div class="signal-list">
        {#each analysis.detection_signals as signal}
          <span class="signal">{signal}</span>
        {/each}
      </div>
    </details>
  {/if}

  <!-- Pipeline Section -->
  {#if hasGoals}
    <section class="pipeline-section">
      <h3>
        📋 Pipeline
        <span class="completion">{completionPercent}% done</span>
      </h3>
      <div class="pipeline">
        {#each analysis.pipeline as step}
          <div 
            class="step"
            class:current={step.id === analysis.current_step}
            class:completed={step.status === 'completed'}
          >
            <span class="step-icon">{getStepIcon(step)}</span>
            <span class="step-title">{step.title}</span>
            {#if step.id === analysis.current_step}
              <span class="current-marker">← current</span>
            {/if}
          </div>
        {/each}
      </div>
    </section>
  {:else}
    <section class="empty-state">
      <p class="empty-title">📋 No goals yet</p>
      <p class="empty-hint">
        This looks like a {typeName.toLowerCase()} project. What would you like to accomplish?
      </p>
    </section>
  {/if}

  <!-- Suggested Action -->
  {#if analysis.suggested_action}
    <section class="suggested-action">
      <h3>💡 Suggested</h3>
      <p class="action-description">{analysis.suggested_action.description}</p>
      {#if analysis.suggested_action.command}
        <code class="action-command">{analysis.suggested_action.command}</code>
      {/if}
    </section>
  {/if}

  <!-- Action Buttons -->
  <footer class="actions">
    {#if analysis.suggested_action}
      <Button 
        variant="primary" 
        onclick={() => analysis.suggested_action && handleSuggestedAction(analysis.suggested_action)}
      >
        ▶ Work on this
      </Button>
    {/if}
    
    {#if hasDevServer}
      <Button 
        variant="secondary"
        onclick={() => analysis.dev_command && onStartServer?.(analysis.dev_command.command)}
      >
        🖥️ Dev Server
      </Button>
    {/if}
    
    <Button variant="ghost" onclick={() => onAddGoal?.()}>
      ➕ Add Goal
    </Button>
  </footer>

  <!-- Dev Command Details -->
  {#if analysis.dev_command}
    <details class="dev-details">
      <summary>🖥️ Development Server</summary>
      <div class="dev-info">
        <p><strong>Command:</strong> <code>{analysis.dev_command.command}</code></p>
        {#if analysis.dev_command.expected_url}
          <p><strong>URL:</strong> {analysis.dev_command.expected_url}</p>
        {/if}
        {#if analysis.dev_command.prerequisites.length > 0}
          <p><strong>Prerequisites:</strong></p>
          <ul>
            {#each analysis.dev_command.prerequisites as prereq}
              <li>{prereq.description} — <code>{prereq.command}</code></li>
            {/each}
          </ul>
        {/if}
      </div>
    </details>
  {/if}

  <!-- Workspace Suggestion -->
  <p class="workspace-hint">
    Suggested workspace: <strong>{analysis.suggested_workspace_primary}</strong>
  </p>
</div>

<style>
  .project-overview {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    padding: 1rem;
    background: var(--bg-secondary, #1a1a2e);
    border-radius: 8px;
    color: var(--text-primary, #eee);
  }

  .overview-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid var(--border, #333);
  }

  .type-badge {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .type-emoji {
    font-size: 1.25rem;
  }

  .type-name {
    font-weight: 600;
    font-size: 1.1rem;
  }

  .subtype {
    color: var(--text-secondary, #888);
    font-size: 0.9rem;
  }

  .confidence {
    font-size: 0.85rem;
    font-weight: 500;
  }

  .signals {
    font-size: 0.8rem;
    color: var(--text-secondary, #888);
  }

  .signals summary {
    cursor: pointer;
  }

  .signal-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
    margin-top: 0.5rem;
  }

  .signal {
    background: var(--bg-tertiary, #252545);
    padding: 0.125rem 0.375rem;
    border-radius: 4px;
    font-family: monospace;
    font-size: 0.75rem;
  }

  .pipeline-section h3,
  .suggested-action h3 {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin: 0 0 0.5rem 0;
    font-size: 0.9rem;
    font-weight: 600;
  }

  .completion {
    font-weight: 400;
    color: var(--text-secondary, #888);
    font-size: 0.8rem;
  }

  .pipeline {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    padding: 0.5rem;
    background: var(--bg-tertiary, #252545);
    border-radius: 6px;
  }

  .step {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.25rem 0;
    font-size: 0.85rem;
  }

  .step.completed {
    opacity: 0.6;
  }

  .step.current {
    font-weight: 500;
  }

  .step-icon {
    flex-shrink: 0;
  }

  .step-title {
    flex: 1;
  }

  .current-marker {
    color: var(--text-secondary, #888);
    font-size: 0.75rem;
    font-style: italic;
  }

  .empty-state {
    text-align: center;
    padding: 1.5rem;
    background: var(--bg-tertiary, #252545);
    border-radius: 6px;
  }

  .empty-title {
    margin: 0 0 0.5rem 0;
    font-size: 1rem;
  }

  .empty-hint {
    margin: 0;
    color: var(--text-secondary, #888);
    font-size: 0.85rem;
  }

  .suggested-action {
    background: var(--bg-tertiary, #252545);
    padding: 0.75rem;
    border-radius: 6px;
    border-left: 3px solid var(--green, #4ade80);
  }

  .action-description {
    margin: 0;
    font-size: 0.9rem;
  }

  .action-command {
    display: block;
    margin-top: 0.5rem;
    padding: 0.25rem 0.5rem;
    background: var(--bg-primary, #0f0f23);
    border-radius: 4px;
    font-size: 0.8rem;
  }

  .actions {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .dev-details {
    font-size: 0.85rem;
    color: var(--text-secondary, #888);
  }

  .dev-details summary {
    cursor: pointer;
  }

  .dev-info {
    margin-top: 0.5rem;
    padding-left: 1rem;
  }

  .dev-info p {
    margin: 0.25rem 0;
  }

  .dev-info ul {
    margin: 0.25rem 0;
    padding-left: 1.25rem;
  }

  .dev-info code {
    background: var(--bg-tertiary, #252545);
    padding: 0.125rem 0.25rem;
    border-radius: 3px;
    font-size: 0.8rem;
  }

  .workspace-hint {
    margin: 0;
    font-size: 0.75rem;
    color: var(--text-secondary, #888);
    text-align: right;
  }
</style>
