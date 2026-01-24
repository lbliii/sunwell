<script lang="ts">
  /**
   * EpicProgress — Visual progress tracker for hierarchical goals (RFC-115)
   *
   * Shows:
   * - Epic title and overall progress
   * - Milestone timeline with status indicators
   * - Current milestone task progress
   * - Produces/artifacts for each milestone
   */
  import { backlogStore, type MilestoneSummary } from '../../stores/backlog.svelte';

  // ═══════════════════════════════════════════════════════════════
  // DERIVED STATE
  // ═══════════════════════════════════════════════════════════════

  let epicProgress = $derived(backlogStore.epicProgress);
  let hasEpic = $derived(epicProgress !== null);
  let milestones = $derived(epicProgress?.milestones ?? []);
  let currentMilestone = $derived(
    milestones.find((m) => m.id === epicProgress?.current_milestone_id)
  );

  // Calculate overall progress bar width
  let progressPercent = $derived(epicProgress?.percent_complete ?? 0);

  // ═══════════════════════════════════════════════════════════════
  // HELPERS
  // ═══════════════════════════════════════════════════════════════

  function getMilestoneIcon(status: MilestoneSummary['status']): string {
    switch (status) {
      case 'completed':
        return '✅';
      case 'active':
        return '🔄';
      case 'blocked':
        return '⏭';
      case 'pending':
      default:
        return '⏳';
    }
  }

  function getMilestoneStatusClass(status: MilestoneSummary['status']): string {
    switch (status) {
      case 'completed':
        return 'completed';
      case 'active':
        return 'active';
      case 'blocked':
        return 'blocked';
      case 'pending':
      default:
        return 'pending';
    }
  }
</script>

{#if hasEpic && epicProgress}
  <div class="epic-progress">
    <!-- Header with epic title and overall progress -->
    <header class="epic-header">
      <div class="epic-title">
        <span class="epic-icon">🎯</span>
        <h2>{epicProgress.epic_title}</h2>
      </div>
      <div class="epic-stats">
        <span class="milestone-count">
          {epicProgress.completed_milestones}/{epicProgress.total_milestones} milestones
        </span>
        <span class="percent">{progressPercent.toFixed(0)}%</span>
      </div>
    </header>

    <!-- Overall progress bar -->
    <div class="progress-bar-container">
      <div class="progress-bar" style="width: {progressPercent}%"></div>
    </div>

    <!-- Current milestone details (if any) -->
    {#if currentMilestone}
      <div class="current-milestone">
        <div class="current-header">
          <span class="current-label">Current:</span>
          <span class="current-title">{currentMilestone.title}</span>
        </div>
        {#if epicProgress.current_milestone_tasks_total > 0}
          <div class="task-progress">
            <div class="task-bar-container">
              <div
                class="task-bar"
                style="width: {(epicProgress.current_milestone_tasks_completed / epicProgress.current_milestone_tasks_total) * 100}%"
              ></div>
            </div>
            <span class="task-count">
              {epicProgress.current_milestone_tasks_completed}/{epicProgress.current_milestone_tasks_total} tasks
            </span>
          </div>
        {/if}
        {#if currentMilestone.produces.length > 0}
          <div class="produces">
            <span class="produces-label">Produces:</span>
            <span class="produces-list">{currentMilestone.produces.join(', ')}</span>
          </div>
        {/if}
      </div>
    {/if}

    <!-- Milestone timeline -->
    <div class="milestone-timeline" role="list" aria-label="Milestone timeline">
      {#each milestones as milestone, index (milestone.id)}
        <div
          class="milestone-item {getMilestoneStatusClass(milestone.status)}"
          role="listitem"
          aria-current={milestone.id === epicProgress.current_milestone_id ? 'step' : undefined}
        >
          <div class="milestone-connector">
            {#if index > 0}
              <div class="connector-line"></div>
            {/if}
            <div class="milestone-dot">
              <span class="milestone-icon">{getMilestoneIcon(milestone.status)}</span>
            </div>
          </div>
          <div class="milestone-content">
            <div class="milestone-header">
              <span class="milestone-index">M{(milestone.index ?? index) + 1}</span>
              <span class="milestone-title">{milestone.title}</span>
            </div>
            {#if milestone.status === 'active' && milestone.tasks_total > 0}
              <div class="milestone-tasks">
                {milestone.tasks_completed}/{milestone.tasks_total} tasks
              </div>
            {/if}
            {#if milestone.produces.length > 0}
              <div class="milestone-produces">
                {milestone.produces.slice(0, 3).join(', ')}
                {#if milestone.produces.length > 3}
                  <span class="more">+{milestone.produces.length - 3} more</span>
                {/if}
              </div>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  </div>
{/if}

<style>
  .epic-progress {
    background: var(--bg-secondary, #1a1a2e);
    border: 1px solid var(--border, #333);
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 16px;
  }

  /* Header */
  .epic-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }

  .epic-title {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .epic-icon {
    font-size: 1.25rem;
  }

  .epic-title h2 {
    margin: 0;
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-primary, #fff);
  }

  .epic-stats {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .milestone-count {
    font-size: 0.85rem;
    color: var(--text-secondary, #888);
  }

  .percent {
    font-size: 1rem;
    font-weight: 600;
    color: var(--accent, #7c3aed);
  }

  /* Progress bar */
  .progress-bar-container {
    height: 6px;
    background: var(--bg-tertiary, #262640);
    border-radius: 3px;
    overflow: hidden;
    margin-bottom: 16px;
  }

  .progress-bar {
    height: 100%;
    background: linear-gradient(90deg, var(--accent, #7c3aed), var(--success, #10b981));
    border-radius: 3px;
    transition: width 0.3s ease;
  }

  /* Current milestone */
  .current-milestone {
    background: var(--bg-tertiary, #262640);
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 16px;
  }

  .current-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
  }

  .current-label {
    font-size: 0.75rem;
    color: var(--text-secondary, #888);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .current-title {
    font-weight: 500;
    color: var(--text-primary, #fff);
  }

  .task-progress {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 8px;
  }

  .task-bar-container {
    flex: 1;
    height: 4px;
    background: var(--bg-secondary, #1a1a2e);
    border-radius: 2px;
    overflow: hidden;
  }

  .task-bar {
    height: 100%;
    background: var(--success, #10b981);
    border-radius: 2px;
    transition: width 0.3s ease;
  }

  .task-count {
    font-size: 0.8rem;
    color: var(--text-secondary, #888);
    white-space: nowrap;
  }

  .produces {
    font-size: 0.8rem;
    color: var(--text-secondary, #888);
  }

  .produces-label {
    opacity: 0.7;
  }

  .produces-list {
    color: var(--text-primary, #fff);
    opacity: 0.9;
  }

  /* Timeline */
  .milestone-timeline {
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  .milestone-item {
    display: flex;
    gap: 12px;
    padding: 8px 0;
  }

  .milestone-connector {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 24px;
    flex-shrink: 0;
  }

  .connector-line {
    width: 2px;
    height: 16px;
    background: var(--border, #333);
    margin-bottom: -4px;
  }

  .milestone-item.completed .connector-line {
    background: var(--success, #10b981);
  }

  .milestone-item.active .connector-line {
    background: linear-gradient(to bottom, var(--success, #10b981), var(--accent, #7c3aed));
  }

  .milestone-dot {
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg-tertiary, #262640);
    border: 2px solid var(--border, #333);
    border-radius: 50%;
    font-size: 0.75rem;
  }

  .milestone-item.completed .milestone-dot {
    border-color: var(--success, #10b981);
    background: rgba(16, 185, 129, 0.1);
  }

  .milestone-item.active .milestone-dot {
    border-color: var(--accent, #7c3aed);
    background: rgba(124, 58, 237, 0.1);
    animation: pulse 2s ease-in-out infinite;
  }

  .milestone-item.blocked .milestone-dot {
    border-color: var(--text-secondary, #888);
    opacity: 0.5;
  }

  @keyframes pulse {
    0%,
    100% {
      box-shadow: 0 0 0 0 rgba(124, 58, 237, 0.4);
    }
    50% {
      box-shadow: 0 0 0 6px rgba(124, 58, 237, 0);
    }
  }

  .milestone-content {
    flex: 1;
    min-width: 0;
  }

  .milestone-header {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .milestone-index {
    font-size: 0.7rem;
    font-weight: 600;
    color: var(--text-secondary, #888);
    background: var(--bg-tertiary, #262640);
    padding: 2px 6px;
    border-radius: 4px;
  }

  .milestone-item.completed .milestone-index {
    color: var(--success, #10b981);
  }

  .milestone-item.active .milestone-index {
    color: var(--accent, #7c3aed);
  }

  .milestone-title {
    font-size: 0.9rem;
    font-weight: 500;
    color: var(--text-primary, #fff);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .milestone-item.pending .milestone-title,
  .milestone-item.blocked .milestone-title {
    opacity: 0.6;
  }

  .milestone-tasks {
    font-size: 0.75rem;
    color: var(--accent, #7c3aed);
    margin-top: 2px;
  }

  .milestone-produces {
    font-size: 0.75rem;
    color: var(--text-secondary, #888);
    margin-top: 2px;
  }

  .milestone-produces .more {
    opacity: 0.6;
  }
</style>
