<!--
  RunAnalysisView — Display run analysis results (RFC-066)
  
  Shows detected project type, command, and prerequisites.
  Allows editing the command before execution.
-->
<script lang="ts">
  import type { RunAnalysis } from '$lib/types';
  import Button from './Button.svelte';
  
  interface Props {
    analysis: RunAnalysis;
    isRunning: boolean;
    error: string | null;
    editedCommand: string;
    onrun: (installFirst: boolean, remember: boolean) => void;
    onrefresh: () => void;
  }
  
  let { 
    analysis, 
    isRunning, 
    error,
    editedCommand = $bindable(), 
    onrun, 
    onrefresh 
  }: Props = $props();
  
  let rememberCommand = $state(false);
  
  const hasUnmetPrereqs = $derived(
    analysis.prerequisites.some(p => p.required && !p.satisfied)
  );
  
  const confidenceDisplay = $derived({
    high: { dots: '●●●○', label: 'High', class: 'high' },
    medium: { dots: '●●○○', label: 'Medium', class: 'medium' },
    low: { dots: '●○○○', label: 'Low', class: 'low' },
  }[analysis.confidence]);
  
  const sourceLabel = $derived({
    ai: 'AI-powered analysis',
    heuristic: 'Detected from project files',
    cache: 'Using cached analysis',
    user: 'Your saved command',
  }[analysis.source]);
</script>

<div class="analysis">
  {#if analysis.confidence === 'low'}
    <div class="warning-banner" role="alert">
      <span class="warning-icon" aria-hidden="true">⚠️</span>
      <span>Low confidence detection — please verify the command</span>
    </div>
  {/if}
  
  <div class="detection-info">
    <div class="info-row">
      <span class="label">Detected:</span>
      <span class="value">{analysis.projectType}</span>
    </div>
    
    {#if analysis.framework}
      <div class="info-row">
        <span class="label">Framework:</span>
        <span class="value">{analysis.framework}</span>
      </div>
    {/if}
    
    <div class="info-row">
      <span class="label">Language:</span>
      <span class="value">{analysis.language}</span>
    </div>
    
    <div class="info-row confidence {confidenceDisplay.class}">
      <span class="dots" aria-hidden="true">{confidenceDisplay.dots}</span>
      <span>{confidenceDisplay.label} confidence</span>
    </div>
  </div>
  
  <div class="source-notice" class:saved={analysis.userSaved}>
    {#if analysis.userSaved}
      <span class="source-icon" aria-hidden="true">★</span>
    {:else if analysis.source === 'heuristic'}
      <span class="source-icon" aria-hidden="true">⚡</span>
    {:else if analysis.fromCache}
      <span class="source-icon" aria-hidden="true">↺</span>
    {:else}
      <span class="source-icon" aria-hidden="true">✨</span>
    {/if}
    <span>{sourceLabel}</span>
    {#if analysis.source !== 'user'}
      <button class="refresh-btn" onclick={onrefresh} aria-label="Refresh analysis">
        ↻
      </button>
    {/if}
  </div>
  
  <div class="command-section">
    <label for="run-command" class="command-label">Command:</label>
    <div class="command-input-wrapper">
      <input 
        id="run-command"
        type="text" 
        bind:value={editedCommand}
        class="command-input"
        spellcheck="false"
        autocomplete="off"
      />
    </div>
    <p class="command-description">{analysis.commandDescription}</p>
  </div>
  
  {#if analysis.prerequisites.length > 0}
    <div class="prerequisites">
      <h4 class="prereq-title">Prerequisites</h4>
      <ul class="prereq-list">
        {#each analysis.prerequisites as prereq}
          <li class="prereq-item" class:satisfied={prereq.satisfied} class:required={prereq.required}>
            <span class="prereq-status" aria-hidden="true">
              {prereq.satisfied ? '✓' : '⚠️'}
            </span>
            <span class="prereq-text">
              {prereq.description}
              {#if !prereq.satisfied}
                <code class="prereq-command">{prereq.command}</code>
              {/if}
            </span>
          </li>
        {/each}
      </ul>
    </div>
  {/if}
  
  {#if error}
    <div class="error-banner" role="alert">
      {error}
    </div>
  {/if}
  
  <div class="remember-option">
    <label class="remember-label">
      <input type="checkbox" bind:checked={rememberCommand} />
      <span>Remember this command for this project</span>
    </label>
  </div>
  
  <div class="actions">
    {#if hasUnmetPrereqs}
      <Button variant="primary" onclick={() => onrun(true, rememberCommand)} loading={isRunning}>
        Install & Run
      </Button>
      <Button variant="secondary" onclick={() => onrun(false, rememberCommand)} loading={isRunning}>
        Run Only
      </Button>
    {:else}
      <Button variant="primary" onclick={() => onrun(false, rememberCommand)} loading={isRunning}>
        Run
      </Button>
    {/if}
  </div>
  
  {#if analysis.expectedUrl}
    <p class="expected-url">
      Will be available at: 
      <a href={analysis.expectedUrl} target="_blank" rel="noopener noreferrer">
        {analysis.expectedUrl}
      </a>
    </p>
  {/if}
</div>

<style>
  .analysis {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }
  
  .warning-banner {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-3);
    background: rgba(245, 158, 11, 0.1);
    border: 1px solid rgba(245, 158, 11, 0.3);
    border-radius: var(--radius-md);
    color: #f59e0b;
    font-size: var(--text-sm);
  }
  
  .warning-icon {
    flex-shrink: 0;
  }
  
  .detection-info {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  
  .info-row {
    display: flex;
    gap: var(--space-2);
    font-size: var(--text-sm);
  }
  
  .label {
    color: var(--text-tertiary);
    min-width: 80px;
  }
  
  .value {
    color: var(--text-primary);
    font-weight: 500;
  }
  
  .confidence {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  
  .confidence.high { color: var(--success); }
  .confidence.medium { color: #f59e0b; }
  .confidence.low { color: var(--error); }
  
  .dots {
    letter-spacing: 2px;
  }
  
  .source-notice {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    padding: var(--space-2);
    background: var(--bg-secondary);
    border-radius: var(--radius-sm);
  }
  
  .source-notice.saved {
    color: var(--accent);
    background: rgba(201, 162, 39, 0.1);
  }
  
  .source-icon {
    font-size: var(--text-sm);
  }
  
  .refresh-btn {
    margin-left: auto;
    background: none;
    border: none;
    color: var(--text-tertiary);
    cursor: pointer;
    font-size: var(--text-base);
    padding: var(--space-1);
    line-height: 1;
    border-radius: var(--radius-sm);
    transition: all var(--transition-fast);
  }
  
  .refresh-btn:hover {
    color: var(--accent);
    background: rgba(201, 162, 39, 0.1);
  }
  
  .command-section {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  
  .command-label {
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--text-secondary);
  }
  
  .command-input-wrapper {
    position: relative;
  }
  
  .command-input {
    width: 100%;
    padding: var(--space-3);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    color: var(--text-primary);
    transition: border-color var(--transition-fast);
  }
  
  .command-input:focus {
    outline: none;
    border-color: var(--accent);
  }
  
  .command-description {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    margin: 0;
  }
  
  .prerequisites {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  
  .prereq-title {
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--text-secondary);
    margin: 0;
  }
  
  .prereq-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  
  .prereq-item {
    display: flex;
    align-items: flex-start;
    gap: var(--space-2);
    font-size: var(--text-sm);
    padding: var(--space-2);
    background: var(--bg-secondary);
    border-radius: var(--radius-sm);
  }
  
  .prereq-item.satisfied {
    color: var(--text-tertiary);
  }
  
  .prereq-item.required:not(.satisfied) {
    background: rgba(245, 158, 11, 0.08);
    border: 1px solid rgba(245, 158, 11, 0.2);
  }
  
  .prereq-status {
    flex-shrink: 0;
  }
  
  .prereq-text {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  
  .prereq-command {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    background: var(--bg-tertiary);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    color: var(--accent);
  }
  
  .error-banner {
    padding: var(--space-3);
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    border-radius: var(--radius-md);
    color: var(--error);
    font-size: var(--text-sm);
  }
  
  .remember-option {
    padding-top: var(--space-2);
  }
  
  .remember-label {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-sm);
    color: var(--text-secondary);
    cursor: pointer;
  }
  
  .remember-label input {
    width: 16px;
    height: 16px;
    cursor: pointer;
    accent-color: var(--accent);
  }
  
  .actions {
    display: flex;
    gap: var(--space-3);
    padding-top: var(--space-2);
  }
  
  .expected-url {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    margin: 0;
  }
  
  .expected-url a {
    color: var(--accent);
    text-decoration: none;
  }
  
  .expected-url a:hover {
    text-decoration: underline;
  }
</style>
