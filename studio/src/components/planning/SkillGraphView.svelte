<script lang="ts">
  /**
   * SkillGraphView - Visualizes skill DAG execution (RFC-087)
   *
   * Shows:
   * - Waves of parallel skill execution
   * - Individual skill status (pending, running, complete, cached, failed)
   * - Per-skill risk levels (RFC-089)
   * - Cache hit statistics
   * - Overall progress
   */

  import {
    skillGraphState,
    getWavesWithSkills,
    getStatusCounts,
    getRiskCounts,
    type RiskLevel
  } from '../../stores';

  // Reactive derived state
  let waves = $derived(getWavesWithSkills());
  let counts = $derived(getStatusCounts());
  let riskCounts = $derived(getRiskCounts());
  let progress = $derived(skillGraphState.progress);
  let cacheRate = $derived(skillGraphState.cacheHitRate);
  let hasSecurityConcerns = $derived(skillGraphState.hasSecurityConcerns);

  function getStatusColor(status: string): string {
    switch (status) {
      case 'complete': return 'var(--color-success)';
      case 'cached': return 'var(--color-info)';
      case 'running': return 'var(--color-warning)';
      case 'failed': return 'var(--color-error)';
      default: return 'var(--color-muted)';
    }
  }

  function getStatusIcon(status: string): string {
    switch (status) {
      case 'complete': return '✓';
      case 'cached': return '⚡';
      case 'running': return '◐';
      case 'failed': return '✗';
      default: return '○';
    }
  }

  function getRiskIcon(risk: RiskLevel): string {
    switch (risk) {
      case 'critical': return '🔴';
      case 'high': return '🟠';
      case 'medium': return '🟡';
      case 'low': return '🟢';
      default: return '';
    }
  }

  function getRiskLabel(risk: RiskLevel): string {
    switch (risk) {
      case 'critical': return 'Critical Risk';
      case 'high': return 'High Risk';
      case 'medium': return 'Medium Risk';
      case 'low': return 'Low Risk';
      default: return '';
    }
  }
</script>

{#if skillGraphState.lensName}
  <div class="skill-graph">
    <header class="graph-header">
      <h3>Skill Execution</h3>
      <div class="stats">
        <span class="stat">
          <span class="label">Progress</span>
          <span class="value">{progress}%</span>
        </span>
        <span class="stat">
          <span class="label">Cache</span>
          <span class="value">{cacheRate}%</span>
        </span>
        {#if skillGraphState.cacheSavedMs > 0}
          <span class="stat saved">
            <span class="label">Saved</span>
            <span class="value">{(skillGraphState.cacheSavedMs / 1000).toFixed(1)}s</span>
          </span>
        {/if}
      </div>
    </header>

    {#if hasSecurityConcerns}
      <div class="security-alert">
        <span class="alert-icon">⚠️</span>
        <span class="alert-text">
          {#if skillGraphState.highRiskSkills > 0}
            {skillGraphState.highRiskSkills} high-risk skill{skillGraphState.highRiskSkills !== 1 ? 's' : ''}
          {/if}
          {#if skillGraphState.totalViolations > 0}
            {skillGraphState.highRiskSkills > 0 ? ' · ' : ''}{skillGraphState.totalViolations} violation{skillGraphState.totalViolations !== 1 ? 's' : ''} detected
          {/if}
        </span>
      </div>
    {/if}

    <div class="progress-bar">
      <div class="fill" style="width: {progress}%"></div>
    </div>

    <div class="waves">
      {#each waves as { wave, skills } (wave.index)}
        <div class="wave" class:active={skillGraphState.currentWave === wave.index}>
          <div class="wave-header">
            <span class="wave-label">Wave {wave.index + 1}</span>
            {#if wave.durationMs}
              <span class="wave-time">{wave.durationMs}ms</span>
            {/if}
          </div>
          <div class="skills">
            {#each skills as skill (skill.name)}
              <div
                class="skill"
                class:running={skill.status === 'running'}
                class:complete={skill.status === 'complete'}
                class:cached={skill.status === 'cached'}
                class:failed={skill.status === 'failed'}
                class:high-risk={skill.riskLevel === 'high' || skill.riskLevel === 'critical'}
                title={skill.error ?? `${skill.name} - ${skill.status}${skill.riskLevel ? ` (${getRiskLabel(skill.riskLevel)})` : ''}${skill.durationMs ? ` (${skill.durationMs}ms)` : ''}`}
              >
                <span class="icon" style="color: {getStatusColor(skill.status)}">
                  {getStatusIcon(skill.status)}
                </span>
                <span class="name">{skill.name}</span>
                {#if skill.riskLevel}
                  <span class="risk-badge" title={getRiskLabel(skill.riskLevel)}>
                    {getRiskIcon(skill.riskLevel)}
                  </span>
                {/if}
                {#if skill.violationsDetected > 0}
                  <span class="violations-badge" title="{skill.violationsDetected} security violation{skill.violationsDetected !== 1 ? 's' : ''}">
                    ⛔{skill.violationsDetected}
                  </span>
                {/if}
                {#if skill.durationMs && skill.status !== 'pending'}
                  <span class="time">{skill.durationMs}ms</span>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      {/each}
    </div>

    <footer class="graph-footer">
      <div class="footer-left">
        <span class="lens-name">{skillGraphState.lensName}</span>
        {#if riskCounts.high > 0 || riskCounts.critical > 0}
          <span class="risk-summary">
            {#if riskCounts.critical > 0}
              <span class="risk-count critical">🔴 {riskCounts.critical}</span>
            {/if}
            {#if riskCounts.high > 0}
              <span class="risk-count high">🟠 {riskCounts.high}</span>
            {/if}
          </span>
        {/if}
      </div>
      <div class="status-summary">
        {#if counts.complete > 0}
          <span class="count complete">✓ {counts.complete}</span>
        {/if}
        {#if counts.cached > 0}
          <span class="count cached">⚡ {counts.cached}</span>
        {/if}
        {#if counts.running > 0}
          <span class="count running">◐ {counts.running}</span>
        {/if}
        {#if counts.failed > 0}
          <span class="count failed">✗ {counts.failed}</span>
        {/if}
        {#if counts.pending > 0}
          <span class="count pending">○ {counts.pending}</span>
        {/if}
      </div>
    </footer>
  </div>
{/if}

<style>
  .skill-graph {
    background: var(--color-surface);
    border-radius: 8px;
    padding: 1rem;
    font-size: 0.875rem;
  }

  .graph-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.75rem;
  }

  .graph-header h3 {
    margin: 0;
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--color-text);
  }

  .stats {
    display: flex;
    gap: 1rem;
  }

  .stat {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
  }

  .stat .label {
    font-size: 0.625rem;
    color: var(--color-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .stat .value {
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }

  .stat.saved .value {
    color: var(--color-success);
  }

  .progress-bar {
    height: 4px;
    background: var(--color-border);
    border-radius: 2px;
    overflow: hidden;
    margin-bottom: 1rem;
  }

  .progress-bar .fill {
    height: 100%;
    background: var(--color-primary);
    transition: width 0.3s ease;
  }

  .waves {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .wave {
    background: var(--color-background);
    border-radius: 6px;
    padding: 0.5rem;
    border: 1px solid var(--color-border);
    transition: border-color 0.2s;
  }

  .wave.active {
    border-color: var(--color-primary);
  }

  .wave-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
    padding-bottom: 0.25rem;
    border-bottom: 1px solid var(--color-border);
  }

  .wave-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--color-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .wave-time {
    font-size: 0.75rem;
    color: var(--color-muted);
    font-variant-numeric: tabular-nums;
  }

  .skills {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  .skill {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.5rem;
    background: var(--color-surface);
    border-radius: 4px;
    font-size: 0.75rem;
    transition: transform 0.1s, box-shadow 0.1s;
  }

  .skill.running {
    animation: pulse 1.5s infinite;
  }

  .skill.failed {
    background: color-mix(in srgb, var(--color-error) 10%, var(--color-surface));
  }

  .skill.high-risk {
    border: 1px solid color-mix(in srgb, var(--color-warning) 50%, transparent);
  }

  .skill .icon {
    font-size: 0.625rem;
  }

  .skill .name {
    color: var(--color-text);
  }

  .skill .time {
    color: var(--color-muted);
    font-size: 0.625rem;
    font-variant-numeric: tabular-nums;
  }

  .skill .risk-badge {
    font-size: 0.5rem;
    line-height: 1;
  }

  .skill .violations-badge {
    font-size: 0.5rem;
    color: var(--color-error);
    background: color-mix(in srgb, var(--color-error) 15%, transparent);
    padding: 0.125rem 0.25rem;
    border-radius: 2px;
    line-height: 1;
  }

  .security-alert {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    margin-bottom: 0.75rem;
    background: color-mix(in srgb, var(--color-warning) 10%, var(--color-surface));
    border: 1px solid color-mix(in srgb, var(--color-warning) 30%, transparent);
    border-radius: 6px;
    font-size: 0.75rem;
  }

  .security-alert .alert-icon {
    font-size: 0.875rem;
  }

  .security-alert .alert-text {
    color: var(--color-text);
  }

  .graph-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 0.75rem;
    padding-top: 0.5rem;
    border-top: 1px solid var(--color-border);
  }

  .footer-left {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .lens-name {
    font-size: 0.75rem;
    color: var(--color-muted);
  }

  .risk-summary {
    display: flex;
    gap: 0.375rem;
  }

  .risk-count {
    font-size: 0.625rem;
    padding: 0.125rem 0.375rem;
    border-radius: 4px;
    font-variant-numeric: tabular-nums;
  }

  .risk-count.critical {
    background: color-mix(in srgb, var(--color-error) 15%, transparent);
  }

  .risk-count.high {
    background: color-mix(in srgb, var(--color-warning) 15%, transparent);
  }

  .status-summary {
    display: flex;
    gap: 0.5rem;
  }

  .count {
    font-size: 0.75rem;
    font-variant-numeric: tabular-nums;
  }

  .count.complete { color: var(--color-success); }
  .count.cached { color: var(--color-info); }
  .count.running { color: var(--color-warning); }
  .count.failed { color: var(--color-error); }
  .count.pending { color: var(--color-muted); }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
  }
</style>
