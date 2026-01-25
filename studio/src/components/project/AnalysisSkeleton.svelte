<!--
  AnalysisSkeleton — RFC-106 loading state for project analysis
  
  Shows skeleton UI while project analysis is in progress.
  Pure presentational component with no props.
-->
<div class="analysis-skeleton" aria-busy="true" aria-label="Analyzing project...">
  <!-- Type badge skeleton -->
  <header class="skeleton-header">
    <div class="skeleton-badge">
      <span class="skeleton-emoji"></span>
      <span class="skeleton-text" style="width: 140px;"></span>
    </div>
    <span class="skeleton-text" style="width: 80px;"></span>
  </header>
  
  <!-- Pipeline skeleton -->
  <section class="skeleton-pipeline">
    <div class="skeleton-title" style="width: 100px;"></div>
    <div class="skeleton-steps">
      {#each Array(3) as _, i (i)}
        <div class="skeleton-step">
          <span class="skeleton-icon"></span>
          <span class="skeleton-text" style="width: 180px;"></span>
        </div>
      {/each}
    </div>
  </section>
</div>

<style>
  .analysis-skeleton {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    padding: var(--space-4);
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    animation: pulse 1.5s ease-in-out infinite;
  }
  
  .skeleton-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: var(--space-3);
    border-bottom: 1px solid var(--border-color);
  }
  
  .skeleton-badge {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  
  .skeleton-emoji,
  .skeleton-icon {
    width: 20px;
    height: 20px;
    background: var(--bg-tertiary);
    border-radius: var(--radius-sm);
  }
  
  .skeleton-text,
  .skeleton-title {
    height: 16px;
    background: var(--bg-tertiary);
    border-radius: var(--radius-sm);
  }
  
  .skeleton-title {
    margin-bottom: var(--space-2);
  }
  
  .skeleton-steps {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding: var(--space-2);
    background: var(--bg-tertiary);
    border-radius: var(--radius-md);
  }
  
  .skeleton-step {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1) 0;
  }
  
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
</style>
