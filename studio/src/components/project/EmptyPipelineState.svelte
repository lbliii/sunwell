<!--
  EmptyPipelineState — RFC-106 state for projects without goals
  
  Shows contextual prompt for projects that don't have any goals yet.
-->
<script lang="ts">
  import type { AnalysisProjectType } from '$lib/types';
  import { getAnalysisTypeName } from '../../stores/project.svelte';
  
  interface Props {
    projectType: AnalysisProjectType;
  }
  
  let { projectType }: Props = $props();
  
  const typeName = $derived(getAnalysisTypeName(projectType).toLowerCase());
</script>

<section class="empty-pipeline">
  <p class="empty-title">📋 No goals yet</p>
  <p class="empty-hint">
    This looks like a {typeName} project. Describe what you'd like to accomplish below.
  </p>
</section>

<style>
  .empty-pipeline {
    text-align: center;
    padding: var(--space-6);
    background: var(--bg-tertiary);
    border-radius: var(--radius-md);
  }
  
  .empty-title {
    margin: 0 0 var(--space-2) 0;
    font-size: var(--text-base);
    color: var(--text-primary);
  }
  
  .empty-hint {
    margin: 0;
    color: var(--text-secondary);
    font-size: var(--text-sm);
  }
</style>
