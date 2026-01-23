<!--
  LensCardSkeleton — Shimmer loading skeleton for lens cards (RFC-100)
  
  Displays animated placeholder cards while lens library is loading.
-->
<script lang="ts">
  interface Props {
    count?: number;
  }
  
  let { count = 6 }: Props = $props();
</script>

<div class="skeleton-grid">
  {#each Array(count) as _, i}
    <div class="skeleton-card" style="--index: {i}">
      <div class="skeleton-header">
        <div class="skeleton-icon shimmer"></div>
        <div class="skeleton-title-group">
          <div class="skeleton-title shimmer"></div>
          <div class="skeleton-version shimmer"></div>
        </div>
      </div>
      <div class="skeleton-body shimmer"></div>
      <div class="skeleton-meta">
        <div class="skeleton-stat shimmer"></div>
        <div class="skeleton-stat shimmer"></div>
        <div class="skeleton-stat shimmer"></div>
      </div>
      <div class="skeleton-tags">
        <div class="skeleton-tag shimmer"></div>
        <div class="skeleton-tag shimmer"></div>
      </div>
      <div class="skeleton-actions">
        <div class="skeleton-btn shimmer"></div>
        <div class="skeleton-btn shimmer"></div>
      </div>
    </div>
  {/each}
</div>

<style>
  .skeleton-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: var(--space-4);
  }
  
  .skeleton-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: var(--space-4);
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    animation: skeletonPulse 1.5s ease-in-out infinite;
    animation-delay: calc(var(--index) * 100ms);
  }
  
  @keyframes skeletonPulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
  }
  
  .shimmer {
    background: linear-gradient(
      90deg,
      var(--skeleton-base) 0%,
      var(--skeleton-highlight) 50%,
      var(--skeleton-base) 100%
    );
    background-size: 200% 100%;
    animation: shimmerMove 1.5s ease-in-out infinite;
  }
  
  @keyframes shimmerMove {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }
  
  .skeleton-header {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3);
  }
  
  .skeleton-icon {
    width: 36px;
    height: 36px;
    border-radius: var(--radius-md);
    flex-shrink: 0;
  }
  
  .skeleton-title-group {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  
  .skeleton-title {
    height: 20px;
    width: 65%;
    border-radius: var(--radius-sm);
  }
  
  .skeleton-version {
    height: 14px;
    width: 30%;
    border-radius: var(--radius-sm);
  }
  
  .skeleton-body {
    height: 40px;
    width: 100%;
    border-radius: var(--radius-sm);
  }
  
  .skeleton-meta {
    display: flex;
    gap: var(--space-4);
  }
  
  .skeleton-stat {
    height: 16px;
    width: 40px;
    border-radius: var(--radius-sm);
  }
  
  .skeleton-tags {
    display: flex;
    gap: var(--space-2);
  }
  
  .skeleton-tag {
    height: 22px;
    width: 60px;
    border-radius: var(--radius-full);
  }
  
  .skeleton-actions {
    display: flex;
    gap: var(--space-2);
    padding-top: var(--space-3);
    border-top: 1px solid var(--border-subtle);
  }
  
  .skeleton-btn {
    height: 32px;
    width: 64px;
    border-radius: var(--radius-md);
  }
  
  @media (prefers-reduced-motion: reduce) {
    .skeleton-card { animation: none; }
    .shimmer { animation: none; }
  }
</style>
