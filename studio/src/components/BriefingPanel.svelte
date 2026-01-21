<!--
  BriefingPanel — Rolling Handoff Notes Display (RFC-071)
  
  Shows the current briefing for instant project orientation:
  - Mission (what we're trying to accomplish)
  - Status (where we are)
  - Progress + momentum (last/next action)
  - Hazards (what to avoid)
  - Focus files (where to look)
  - Dispatch hints (skill/lens suggestions)
-->

<script lang="ts">
  import {
    briefing,
    getStatusColor,
    getStatusEmoji,
    getStatusLabel,
    formatRelativeTime,
  } from '../stores/briefing.svelte';

  // Animation state for hazards
  let hazardPulse = $state(false);

  $effect(() => {
    if (briefing.hasHazards) {
      hazardPulse = true;
      const timer = setTimeout(() => { hazardPulse = false; }, 500);
      return () => clearTimeout(timer);
    }
  });
</script>

{#if briefing.current}
  <div class="briefing-panel">
    <header class="briefing-header">
      <h2>Briefing</h2>
      <span
        class="status-badge"
        style="--status-color: {getStatusColor(briefing.current.status)}"
      >
        <span class="status-emoji">{getStatusEmoji(briefing.current.status)}</span>
        {getStatusLabel(briefing.current.status)}
      </span>
    </header>

    <section class="mission">
      <h3>Mission</h3>
      <p>{briefing.current.mission}</p>
    </section>

    <section class="progress">
      <h3>Progress</h3>
      <p>{briefing.current.progress}</p>
    </section>

    <section class="momentum">
      <div class="action last">
        <span class="label">Last:</span>
        <span class="value">{briefing.current.lastAction}</span>
      </div>
      {#if briefing.current.nextAction}
        <div class="action next">
          <span class="label">Next:</span>
          <span class="value">{briefing.current.nextAction}</span>
        </div>
      {/if}
    </section>

    {#if briefing.hasHazards}
      <section class="hazards" class:pulse={hazardPulse}>
        <h3>⚠️ Hazards</h3>
        <ul>
          {#each briefing.current.hazards as hazard}
            <li>{hazard}</li>
          {/each}
        </ul>
      </section>
    {/if}

    {#if briefing.hasBlockers}
      <section class="blockers">
        <h3>🚫 Blockers</h3>
        <ul>
          {#each briefing.current.blockers as blocker}
            <li>{blocker}</li>
          {/each}
        </ul>
      </section>
    {/if}

    {#if briefing.current.hotFiles.length > 0}
      <section class="hot-files">
        <h3>Focus Files</h3>
        <div class="file-list">
          {#each briefing.current.hotFiles as file}
            <code class="file">{file}</code>
          {/each}
        </div>
      </section>
    {/if}

    {#if briefing.hasDispatchHints}
      <section class="dispatch-hints">
        <h3>🎯 Dispatch Hints</h3>
        {#if briefing.current.suggestedLens}
          <p class="hint">
            <span class="hint-label">Suggested Lens:</span>
            <span class="hint-value">{briefing.current.suggestedLens}</span>
          </p>
        {/if}
        {#if briefing.current.predictedSkills?.length}
          <p class="hint">
            <span class="hint-label">Skills:</span>
            <span class="hint-value">{briefing.current.predictedSkills.join(', ')}</span>
          </p>
        {/if}
        {#if briefing.current.complexityEstimate}
          <p class="hint">
            <span class="hint-label">Complexity:</span>
            <span class="hint-value">{briefing.current.complexityEstimate}</span>
          </p>
        {/if}
      </section>
    {/if}

    <footer class="briefing-footer">
      <span class="updated">
        Updated {formatRelativeTime(briefing.current.updatedAt)}
      </span>
    </footer>
  </div>
{:else if briefing.isLoading}
  <div class="briefing-panel loading">
    <div class="loading-spinner"></div>
    <p>Loading briefing...</p>
  </div>
{:else}
  <div class="briefing-panel empty">
    <p class="no-briefing">No active briefing</p>
    <p class="hint">Start a goal to create one.</p>
  </div>
{/if}

<style>
  .briefing-panel {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    padding: 1rem;
    background: var(--color-bg-secondary, #1a1a1a);
    border-radius: 8px;
    font-size: 0.875rem;
  }

  .briefing-panel.loading,
  .briefing-panel.empty {
    align-items: center;
    justify-content: center;
    min-height: 200px;
    color: var(--color-text-muted, #888);
  }

  .loading-spinner {
    width: 24px;
    height: 24px;
    border: 2px solid var(--color-border, #333);
    border-top-color: var(--color-accent, #00aaff);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .briefing-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--color-border, #333);
  }

  .briefing-header h2 {
    margin: 0;
    font-size: 1rem;
    font-weight: 600;
    color: var(--color-text, #fff);
  }

  .status-badge {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.25rem 0.5rem;
    background: color-mix(in srgb, var(--status-color) 15%, transparent);
    color: var(--status-color);
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .status-emoji {
    font-size: 0.625rem;
  }

  section h3 {
    margin: 0 0 0.25rem;
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--color-text-muted, #888);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  section p {
    margin: 0;
    color: var(--color-text, #fff);
    line-height: 1.4;
  }

  .mission p {
    font-weight: 500;
  }

  .momentum {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding: 0.75rem;
    background: var(--color-bg-tertiary, #222);
    border-radius: 6px;
  }

  .action {
    display: flex;
    gap: 0.5rem;
  }

  .action .label {
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--color-text-muted, #888);
    min-width: 3rem;
  }

  .action .value {
    color: var(--color-text, #fff);
  }

  .action.next .value {
    color: var(--color-accent, #00aaff);
    font-weight: 500;
  }

  .hazards {
    padding: 0.75rem;
    background: color-mix(in srgb, var(--color-warning, #ffaa00) 10%, transparent);
    border: 1px solid color-mix(in srgb, var(--color-warning, #ffaa00) 30%, transparent);
    border-radius: 6px;
    transition: background 0.2s ease;
  }

  .hazards.pulse {
    background: color-mix(in srgb, var(--color-warning, #ffaa00) 20%, transparent);
  }

  .hazards h3 {
    color: var(--color-warning, #ffaa00);
  }

  .hazards ul {
    margin: 0;
    padding-left: 1rem;
    color: var(--color-text, #fff);
  }

  .hazards li {
    margin: 0.25rem 0;
  }

  .blockers {
    padding: 0.75rem;
    background: color-mix(in srgb, var(--color-error, #ff4444) 10%, transparent);
    border: 1px solid color-mix(in srgb, var(--color-error, #ff4444) 30%, transparent);
    border-radius: 6px;
  }

  .blockers h3 {
    color: var(--color-error, #ff4444);
  }

  .blockers ul {
    margin: 0;
    padding-left: 1rem;
    color: var(--color-text, #fff);
  }

  .blockers li {
    margin: 0.25rem 0;
  }

  .hot-files .file-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  .file {
    padding: 0.125rem 0.375rem;
    background: var(--color-bg-tertiary, #222);
    border-radius: 3px;
    font-family: var(--font-mono, monospace);
    font-size: 0.75rem;
    color: var(--color-text-secondary, #aaa);
  }

  .dispatch-hints {
    padding: 0.75rem;
    background: color-mix(in srgb, var(--color-accent, #00aaff) 5%, transparent);
    border: 1px solid color-mix(in srgb, var(--color-accent, #00aaff) 20%, transparent);
    border-radius: 6px;
  }

  .dispatch-hints h3 {
    color: var(--color-accent, #00aaff);
  }

  .hint {
    margin: 0.25rem 0;
    display: flex;
    gap: 0.5rem;
  }

  .hint-label {
    font-weight: 500;
    color: var(--color-text-muted, #888);
  }

  .hint-value {
    color: var(--color-text, #fff);
  }

  .briefing-footer {
    padding-top: 0.5rem;
    border-top: 1px solid var(--color-border, #333);
  }

  .updated {
    font-size: 0.75rem;
    color: var(--color-text-muted, #888);
  }

  .no-briefing {
    font-weight: 500;
    color: var(--color-text-secondary, #aaa);
  }

  .empty .hint {
    font-size: 0.75rem;
    color: var(--color-text-muted, #888);
  }
</style>
