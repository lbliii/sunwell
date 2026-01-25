<!--
  ProjectIdentity — RFC-106 project type badge and confidence display
  
  Shows project type with emoji, subtype, and confidence indicator.
  Extracted from ProjectOverview.svelte header section.
-->
<script lang="ts">
  import type { ProjectAnalysis } from '$lib/types';
  import { getAnalysisTypeEmoji, getAnalysisTypeName } from '../../stores/project.svelte';
  
  interface Props {
    analysis: ProjectAnalysis;
  }
  
  let { analysis }: Props = $props();
  
  const typeEmoji = $derived(getAnalysisTypeEmoji(analysis.project_type));
  const typeName = $derived(getAnalysisTypeName(analysis.project_type));
  const confidenceColor = $derived(
    analysis.confidence_level === 'high' ? 'var(--success)' :
    analysis.confidence_level === 'medium' ? 'var(--warning)' : 'var(--error)'
  );
</script>

<header class="project-identity">
  <div class="type-badge">
    <span class="type-emoji">{typeEmoji}</span>
    <span class="type-name">{typeName} Project</span>
    {#if analysis.project_subtype}
      <span class="subtype">({analysis.project_subtype})</span>
    {/if}
  </div>
  <span class="confidence" style:color={confidenceColor}>
    {Math.round(analysis.confidence * 100)}% confident
  </span>
</header>

{#if analysis.detection_signals.length > 0}
  <details class="signals">
    <summary>Detection signals ({analysis.detection_signals.length})</summary>
    <div class="signal-tags">
      {#each analysis.detection_signals as signal (signal)}
        <span class="signal">{signal}</span>
      {/each}
    </div>
  </details>
{/if}

<style>
  .project-identity {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-3);
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
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
    font-size: var(--text-base);
    color: var(--text-primary);
  }
  
  .subtype {
    color: var(--text-secondary);
    font-size: var(--text-sm);
  }
  
  .confidence {
    font-size: var(--text-sm);
    font-weight: 500;
    font-family: var(--font-mono);
  }
  
  .signals {
    font-size: var(--text-sm);
    color: var(--text-secondary);
    margin-top: var(--space-2);
  }
  
  .signals summary {
    cursor: pointer;
    padding: var(--space-1) 0;
  }
  
  .signal-tags {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
    margin-top: var(--space-2);
  }
  
  .signal {
    background: var(--bg-tertiary);
    padding: 2px 6px;
    border-radius: var(--radius-sm);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-secondary);
  }
</style>
