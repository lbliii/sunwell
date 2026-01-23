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
    gap: var(--space-4);
    padding: var(--space-4);
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    color: var(--text-primary);
  }

  .overview-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: var(--space-3);
    border-bottom: 1px solid var(--border-default);
  }

  .type-badge {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .type-emoji {
    font-size: var(--text-xl);
  }

  .type-name {
    font-weight: 600;
    font-size: var(--text-lg);
  }

  .subtype {
    color: var(--text-secondary);
    font-size: var(--text-sm);
  }

  .confidence {
    font-size: var(--text-sm);
    font-weight: 500;
  }

  .signals {
    font-size: var(--text-sm);
    color: var(--text-secondary);
  }

  .signals summary {
    cursor: pointer;
  }

  .signal-list {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
    margin-top: var(--space-2);
  }

  .signal {
    background: var(--bg-tertiary);
    padding: var(--space-px) var(--space-1);
    border-radius: var(--radius-sm);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
  }

  .pipeline-section h3,
  .suggested-action h3 {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin: 0 0 var(--space-2) 0;
    font-size: var(--text-sm);
    font-weight: 600;
  }

  .completion {
    font-weight: 400;
    color: var(--text-secondary);
    font-size: var(--text-sm);
  }

  .pipeline {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    padding: var(--space-2);
    background: var(--bg-tertiary);
    border-radius: var(--radius-md);
  }

  .step {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1) 0;
    font-size: var(--text-sm);
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
    color: var(--text-secondary);
    font-size: var(--text-xs);
    font-style: italic;
  }

  .empty-state {
    text-align: center;
    padding: var(--space-6);
    background: var(--bg-tertiary);
    border-radius: var(--radius-md);
  }

  .empty-title {
    margin: 0 0 var(--space-2) 0;
    font-size: var(--text-base);
  }

  .empty-hint {
    margin: 0;
    color: var(--text-secondary);
    font-size: var(--text-sm);
  }

  .suggested-action {
    background: var(--bg-tertiary);
    padding: var(--space-3);
    border-radius: var(--radius-md);
    border-left: 3px solid var(--success);
  }

  .action-description {
    margin: 0;
    font-size: var(--text-sm);
  }

  .action-command {
    display: block;
    margin-top: var(--space-2);
    padding: var(--space-1) var(--space-2);
    background: var(--bg-primary);
    border-radius: var(--radius-sm);
    font-size: var(--text-sm);
    font-family: var(--font-mono);
  }

  .actions {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .dev-details {
    font-size: var(--text-sm);
    color: var(--text-secondary);
  }

  .dev-details summary {
    cursor: pointer;
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
    padding: var(--space-px) var(--space-1);
    border-radius: var(--radius-sm);
    font-size: var(--text-sm);
    font-family: var(--font-mono);
  }

  .workspace-hint {
    margin: 0;
    font-size: var(--text-xs);
    color: var(--text-secondary);
    text-align: right;
  }
</style>
