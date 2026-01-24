/**
 * Backlog Store — Goal queue management for RFC-114 (Backlog UI)
 *
 * Manages state for the Backlog panel:
 * - Goal CRUD operations
 * - Priority reordering
 * - Status tracking
 * - Real-time updates
 */

import { apiGet, apiPost, apiDelete } from '$lib/socket';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

/**
 * Goal category — matches backend Goal.category
 * See: src/sunwell/backlog/goals.py:78-87
 */
export type GoalCategory =
  | 'fix'         // Something broken
  | 'improve'     // Something suboptimal
  | 'add'         // Something missing
  | 'refactor'    // Structural improvement
  | 'document'    // Documentation gap
  | 'test'        // Test coverage
  | 'security'    // Security-related
  | 'performance'; // Performance-related

/**
 * Complexity levels — matches backend Goal.estimated_complexity
 * See: src/sunwell/backlog/goals.py:73
 */
export type GoalComplexity = 'trivial' | 'simple' | 'moderate' | 'complex';

/**
 * Goal status — UI-specific, derived from Backlog state
 * Backend tracks status via Backlog.in_progress, Backlog.completed, Backlog.blocked
 */
export type GoalStatus =
  | 'pending'      // Waiting to be claimed
  | 'blocked'      // Has unsatisfied dependencies (Backlog.blocked)
  | 'claimed'      // Worker has claimed it (Backlog.in_progress)
  | 'executing'    // Currently being worked on
  | 'completed'    // Successfully finished (Backlog.completed)
  | 'failed'       // Execution failed
  | 'skipped';     // User skipped (Backlog.blocked with "User skipped")

/**
 * Goal type — RFC-115 hierarchy level
 * See: src/sunwell/backlog/goals.py
 */
export type GoalType = 'epic' | 'milestone' | 'task';

/**
 * Goal interface — matches backend Goal dataclass
 * See: src/sunwell/backlog/goals.py:60-103
 */
export interface Goal {
  id: string;
  title: string;
  description: string;
  priority: number;           // 0-1 float (backend), UI displays as percentage
  category: GoalCategory;
  estimated_complexity: GoalComplexity;
  auto_approvable: boolean;
  requires: string[];         // IDs of blocking goals

  // UI-derived fields (computed from Backlog state)
  status: GoalStatus;
  created_at: string | null;
  claimed_by?: number;        // Worker ID if claimed

  // RFC-115: Hierarchy fields
  goal_type?: GoalType;           // 'epic' | 'milestone' | 'task'
  parent_goal_id?: string | null; // Parent epic/milestone ID
  milestone_produces?: string[];  // Artifacts this milestone creates
  milestone_index?: number | null; // Order within parent
}

/**
 * Milestone summary for UI timeline
 * RFC-115: Hierarchical Goal Decomposition
 */
export interface MilestoneSummary {
  id: string;
  title: string;
  description: string;
  produces: string[];
  status: 'pending' | 'active' | 'completed' | 'blocked';
  index: number;
  tasks_completed: number;
  tasks_total: number;
}

/**
 * Epic progress state
 * RFC-115: Hierarchical Goal Decomposition
 */
export interface EpicProgress {
  epic_id: string;
  epic_title: string;
  total_milestones: number;
  completed_milestones: number;
  current_milestone_id: string | null;
  current_milestone_title: string | null;
  current_milestone_tasks_total: number;
  current_milestone_tasks_completed: number;
  percent_complete: number;
  milestones: MilestoneSummary[];
}

export interface BacklogState {
  goals: Goal[];
  is_loading: boolean;
  error: string | null;
  last_refresh: string | null;

  // RFC-115: Epic/Milestone hierarchy
  active_epic: string | null;
  active_milestone: string | null;
  epic_progress: EpicProgress | null;
}

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

const emptyState: BacklogState = {
  goals: [],
  is_loading: false,
  error: null,
  last_refresh: null,
  active_epic: null,
  active_milestone: null,
  epic_progress: null,
};

let _state = $state<BacklogState>(emptyState);
let _projectPath = $state<string | null>(null);
let _pollingInterval = $state<number | null>(null);

// ═══════════════════════════════════════════════════════════════
// COMPUTED
// ═══════════════════════════════════════════════════════════════

function getPendingGoals(): Goal[] {
  return _state.goals.filter((g) => g.status === 'pending');
}

function getBlockedGoals(): Goal[] {
  return _state.goals.filter((g) => g.status === 'blocked');
}

function getExecutingGoals(): Goal[] {
  return _state.goals.filter((g) => g.status === 'executing' || g.status === 'claimed');
}

function getCompletedGoals(): Goal[] {
  return _state.goals.filter((g) => g.status === 'completed');
}

function getGoalById(id: string): Goal | undefined {
  return _state.goals.find((g) => g.id === id);
}

function getTotalCount(): number {
  return _state.goals.length;
}

function getPendingCount(): number {
  return getPendingGoals().length + getBlockedGoals().length;
}

function getCompletedCount(): number {
  return getCompletedGoals().length;
}

// RFC-115: Epic/Milestone helpers
function getEpics(): Goal[] {
  return _state.goals.filter((g) => g.goal_type === 'epic');
}

function getMilestones(epicId?: string): Goal[] {
  const milestones = _state.goals.filter((g) => g.goal_type === 'milestone');
  if (epicId) {
    return milestones.filter((m) => m.parent_goal_id === epicId);
  }
  return milestones;
}

function getTasksForMilestone(milestoneId: string): Goal[] {
  return _state.goals.filter(
    (g) => g.goal_type === 'task' && g.parent_goal_id === milestoneId
  );
}

function getActiveEpic(): Goal | undefined {
  if (!_state.active_epic) return undefined;
  return _state.goals.find((g) => g.id === _state.active_epic);
}

function getActiveMilestone(): Goal | undefined {
  if (!_state.active_milestone) return undefined;
  return _state.goals.find((g) => g.id === _state.active_milestone);
}

function hasActiveEpic(): boolean {
  return _state.active_epic !== null;
}

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const backlogStore = {
  // Raw state
  get state() {
    return _state;
  },
  get isLoading() {
    return _state.is_loading;
  },
  get error() {
    return _state.error;
  },
  get projectPath() {
    return _projectPath;
  },

  // Goals
  get goals() {
    return _state.goals;
  },
  get pendingGoals() {
    return getPendingGoals();
  },
  get blockedGoals() {
    return getBlockedGoals();
  },
  get executingGoals() {
    return getExecutingGoals();
  },
  get completedGoals() {
    return getCompletedGoals();
  },

  // Counts
  get totalCount() {
    return getTotalCount();
  },
  get pendingCount() {
    return getPendingCount();
  },
  get completedCount() {
    return getCompletedCount();
  },

  // RFC-115: Epic/Milestone hierarchy
  get activeEpicId() {
    return _state.active_epic;
  },
  get activeMilestoneId() {
    return _state.active_milestone;
  },
  get activeEpic() {
    return getActiveEpic();
  },
  get activeMilestone() {
    return getActiveMilestone();
  },
  get hasActiveEpic() {
    return hasActiveEpic();
  },
  get epicProgress() {
    return _state.epic_progress;
  },
  get epics() {
    return getEpics();
  },

  // Helpers
  getGoalById,
  getMilestones,
  getTasksForMilestone,
};

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Set the project path for backlog operations.
 */
export function setBacklogProjectPath(path: string): void {
  _projectPath = path;
}

/**
 * Load backlog from the backend.
 */
export async function loadBacklog(): Promise<void> {
  if (!_projectPath) {
    _state.error = 'No project path set';
    return;
  }

  _state.is_loading = true;
  _state.error = null;

  try {
    const data = await apiGet<{ goals: Goal[]; total: number; error?: string }>(
      `/api/backlog?path=${encodeURIComponent(_projectPath)}`
    );

    if (data?.error) {
      _state.error = data.error;
    } else if (data?.goals) {
      _state.goals = data.goals;
      _state.last_refresh = new Date().toISOString();
    }
  } catch (e) {
    _state.error = e instanceof Error ? e.message : String(e);
    console.error('Failed to load backlog:', e);
  } finally {
    _state.is_loading = false;
  }
}

/**
 * Add a new goal to the backlog.
 */
export async function addGoal(
  title: string,
  description?: string,
  category: GoalCategory = 'add',
  priority: number = 0.5
): Promise<void> {
  if (!_projectPath) {
    throw new Error('No project path set');
  }

  try {
    const result = await apiPost<{ status: string; goal_id?: string; error?: string }>(
      '/api/backlog/goals',
      {
        path: _projectPath,
        title,
        description,
        category,
        priority,
      }
    );

    if (result?.error) {
      throw new Error(result.error);
    }

    // Reload backlog to get updated state
    await loadBacklog();
  } catch (e) {
    _state.error = e instanceof Error ? e.message : String(e);
    throw e;
  }
}

/**
 * Remove a goal from the backlog.
 */
export async function removeGoal(goalId: string): Promise<void> {
  if (!_projectPath) {
    throw new Error('No project path set');
  }

  try {
    const result = await apiDelete<{ status: string; error?: string }>(
      `/api/backlog/goals/${goalId}?path=${encodeURIComponent(_projectPath)}`
    );

    if (result?.error) {
      throw new Error(result.error);
    }

    // Optimistic update: remove from local state
    _state.goals = _state.goals.filter((g) => g.id !== goalId);
  } catch (e) {
    _state.error = e instanceof Error ? e.message : String(e);
    // Reload to sync state on error
    await loadBacklog();
    throw e;
  }
}

/**
 * Skip a goal (mark as blocked with "User skipped" reason).
 */
export async function skipGoal(goalId: string): Promise<void> {
  if (!_projectPath) {
    throw new Error('No project path set');
  }

  try {
    const result = await apiPost<{ status: string; error?: string }>(
      `/api/backlog/goals/${goalId}/skip`,
      { path: _projectPath }
    );

    if (result?.error) {
      throw new Error(result.error);
    }

    await loadBacklog();
  } catch (e) {
    _state.error = e instanceof Error ? e.message : String(e);
    throw e;
  }
}

/**
 * Reorder goals by updating their priorities.
 */
export async function reorderGoals(goalIds: string[]): Promise<void> {
  if (!_projectPath) {
    throw new Error('No project path set');
  }

  try {
    // Optimistic update: reorder local state
    const reordered: Goal[] = [];
    for (const id of goalIds) {
      const goal = _state.goals.find((g) => g.id === id);
      if (goal) reordered.push(goal);
    }
    // Add any goals not in the reorder list
    for (const goal of _state.goals) {
      if (!goalIds.includes(goal.id)) {
        reordered.push(goal);
      }
    }
    _state.goals = reordered;

    // Send to backend
    const result = await apiPost<{ status: string; error?: string }>(
      '/api/backlog/reorder',
      {
        path: _projectPath,
        order: goalIds,
      }
    );

    if (result?.error) {
      throw new Error(result.error);
    }
  } catch (e) {
    _state.error = e instanceof Error ? e.message : String(e);
    // Reload to sync state on error
    await loadBacklog();
    throw e;
  }
}

/**
 * Refresh backlog from project signals.
 */
export async function refreshBacklog(): Promise<void> {
  if (!_projectPath) {
    throw new Error('No project path set');
  }

  _state.is_loading = true;

  try {
    const result = await apiPost<{ status: string; goal_count?: number; error?: string }>(
      '/api/backlog/refresh',
      { path: _projectPath }
    );

    if (result?.error) {
      throw new Error(result.error);
    }

    await loadBacklog();
  } catch (e) {
    _state.error = e instanceof Error ? e.message : String(e);
    throw e;
  } finally {
    _state.is_loading = false;
  }
}

/**
 * Start polling for backlog updates.
 */
export function startBacklogPolling(intervalMs: number = 3000): void {
  if (_pollingInterval !== null) {
    stopBacklogPolling();
  }

  _pollingInterval = window.setInterval(() => {
    loadBacklog();
  }, intervalMs);

  // Initial load
  loadBacklog();
}

/**
 * Stop polling for backlog updates.
 */
export function stopBacklogPolling(): void {
  if (_pollingInterval !== null) {
    clearInterval(_pollingInterval);
    _pollingInterval = null;
  }
}

/**
 * Clear backlog state.
 */
export function clearBacklogState(): void {
  stopBacklogPolling();
  _state = emptyState;
  _projectPath = null;
}

/**
 * Update a goal's priority.
 */
export async function updateGoalPriority(goalId: string, priority: number): Promise<void> {
  if (!_projectPath) {
    throw new Error('No project path set');
  }

  // Clamp priority to 0-1
  const clampedPriority = Math.max(0, Math.min(1, priority));

  try {
    // Optimistic update
    _state.goals = _state.goals.map((g) =>
      g.id === goalId ? { ...g, priority: clampedPriority } : g
    );

    const result = await apiPost<{ status: string; error?: string }>(
      `/api/backlog/goals/${goalId}`,
      {
        path: _projectPath,
        priority: clampedPriority,
      }
    );

    if (result?.error) {
      throw new Error(result.error);
    }
  } catch (e) {
    _state.error = e instanceof Error ? e.message : String(e);
    // Reload to sync state on error
    await loadBacklog();
    throw e;
  }
}

// ═══════════════════════════════════════════════════════════════
// EVENT HANDLERS (RFC-114 Phase 3)
// ═══════════════════════════════════════════════════════════════

/**
 * Handle backlog events from WebSocket/agent events.
 * These events come from the agent execution pipeline.
 */
export function handleBacklogEvent(event: { type: string; data: Record<string, unknown> }): void {
  switch (event.type) {
    case 'backlog_goal_added': {
      // A new goal was added to the backlog
      loadBacklog();
      break;
    }
    case 'backlog_goal_started': {
      // A goal execution started
      const goalId = event.data.goal_id as string;
      const workerId = event.data.worker_id as number | undefined;
      _state.goals = _state.goals.map((g) =>
        g.id === goalId
          ? { ...g, status: 'executing' as GoalStatus, claimed_by: workerId }
          : g
      );
      break;
    }
    case 'backlog_goal_completed': {
      // A goal was completed successfully
      const goalId = event.data.goal_id as string;
      _state.goals = _state.goals.map((g) =>
        g.id === goalId ? { ...g, status: 'completed' as GoalStatus } : g
      );
      break;
    }
    case 'backlog_goal_failed': {
      // A goal execution failed
      const goalId = event.data.goal_id as string;
      _state.goals = _state.goals.map((g) =>
        g.id === goalId ? { ...g, status: 'failed' as GoalStatus } : g
      );
      break;
    }
    case 'backlog_refreshed': {
      // Backlog was refreshed (e.g., from signals scan)
      loadBacklog();
      break;
    }
    case 'backlog_goal_claimed': {
      // A worker claimed a goal
      const goalId = event.data.goal_id as string;
      const workerId = event.data.worker_id as number;
      _state.goals = _state.goals.map((g) =>
        g.id === goalId
          ? { ...g, status: 'claimed' as GoalStatus, claimed_by: workerId }
          : g
      );
      break;
    }

    // RFC-115: Epic/Milestone hierarchy events
    case 'epic_decomposed': {
      // An epic was decomposed into milestones
      const epicId = event.data.epic_id as string;
      const epicTitle = event.data.epic_title as string;
      const totalMilestones = event.data.total_milestones as number;
      const milestones = event.data.milestones as MilestoneSummary[] | undefined;

      _state.active_epic = epicId;
      _state.epic_progress = {
        epic_id: epicId,
        epic_title: epicTitle,
        total_milestones: totalMilestones,
        completed_milestones: 0,
        current_milestone_id: null,
        current_milestone_title: null,
        current_milestone_tasks_total: 0,
        current_milestone_tasks_completed: 0,
        percent_complete: 0,
        milestones: milestones || [],
      };
      loadBacklog();
      break;
    }

    case 'milestone_started': {
      // A milestone started execution
      const milestoneId = event.data.milestone_id as string;
      const milestoneTitle = event.data.milestone_title as string;

      _state.active_milestone = milestoneId;
      if (_state.epic_progress) {
        _state.epic_progress = {
          ..._state.epic_progress,
          current_milestone_id: milestoneId,
          current_milestone_title: milestoneTitle,
          current_milestone_tasks_total: 0,
          current_milestone_tasks_completed: 0,
          milestones: _state.epic_progress.milestones.map((m) =>
            m.id === milestoneId ? { ...m, status: 'active' as const } : m
          ),
        };
      }
      break;
    }

    case 'milestone_progress': {
      // Update milestone task progress
      const tasksCompleted = event.data.tasks_completed as number;
      const tasksTotal = event.data.tasks_total as number;

      if (_state.epic_progress) {
        _state.epic_progress = {
          ..._state.epic_progress,
          current_milestone_tasks_completed: tasksCompleted,
          current_milestone_tasks_total: tasksTotal,
        };
      }
      break;
    }

    case 'milestone_completed': {
      // A milestone completed successfully
      const milestoneId = event.data.milestone_id as string;
      const nextMilestoneId = event.data.next_milestone_id as string | null;
      const nextMilestoneTitle = event.data.next_milestone_title as string | null;

      if (_state.epic_progress) {
        const completedCount = _state.epic_progress.completed_milestones + 1;
        const percent = (completedCount / _state.epic_progress.total_milestones) * 100;

        _state.epic_progress = {
          ..._state.epic_progress,
          completed_milestones: completedCount,
          current_milestone_id: nextMilestoneId,
          current_milestone_title: nextMilestoneTitle,
          current_milestone_tasks_total: 0,
          current_milestone_tasks_completed: 0,
          percent_complete: Math.round(percent * 10) / 10,
          milestones: _state.epic_progress.milestones.map((m) =>
            m.id === milestoneId
              ? { ...m, status: 'completed' as const }
              : m.id === nextMilestoneId
                ? { ...m, status: 'active' as const }
                : m
          ),
        };
      }
      _state.active_milestone = nextMilestoneId;
      loadBacklog();
      break;
    }

    case 'milestone_skipped': {
      // A milestone was skipped
      const milestoneId = event.data.milestone_id as string;
      const nextMilestoneId = event.data.next_milestone_id as string | null;

      if (_state.epic_progress) {
        _state.epic_progress = {
          ..._state.epic_progress,
          current_milestone_id: nextMilestoneId,
          milestones: _state.epic_progress.milestones.map((m) =>
            m.id === milestoneId ? { ...m, status: 'blocked' as const } : m
          ),
        };
      }
      _state.active_milestone = nextMilestoneId;
      break;
    }

    case 'epic_completed': {
      // An epic completed all milestones
      const milestonesCompleted = event.data.milestones_completed as number;

      if (_state.epic_progress) {
        _state.epic_progress = {
          ..._state.epic_progress,
          completed_milestones: milestonesCompleted,
          current_milestone_id: null,
          current_milestone_title: null,
          percent_complete: 100,
        };
      }
      _state.active_epic = null;
      _state.active_milestone = null;
      loadBacklog();
      break;
    }

    default:
      // Unknown event type, ignore
      break;
  }
}

/**
 * Subscribe to agent events for backlog updates.
 * Call this when mounting the BacklogPanel.
 */
export function subscribeToBacklogEvents(
  onEvent: (callback: (event: { type: string; data: Record<string, unknown> }) => void) => () => void
): () => void {
  return onEvent((event) => {
    // Filter for backlog-related events and RFC-115 epic/milestone events
    if (
      event.type.startsWith('backlog_') ||
      event.type.startsWith('epic_') ||
      event.type.startsWith('milestone_')
    ) {
      handleBacklogEvent(event);
    }
  });
}

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

/**
 * Get category display info.
 */
export function getCategoryInfo(category: GoalCategory): { emoji: string; label: string; color: string } {
  const categoryMap: Record<GoalCategory, { emoji: string; label: string; color: string }> = {
    fix: { emoji: '🔧', label: 'Fix', color: 'var(--error)' },
    improve: { emoji: '✨', label: 'Improve', color: 'var(--warning)' },
    add: { emoji: '📦', label: 'Add', color: 'var(--success)' },
    refactor: { emoji: '🔄', label: 'Refactor', color: 'var(--text-secondary)' },
    document: { emoji: '📝', label: 'Document', color: 'var(--accent)' },
    test: { emoji: '🧪', label: 'Test', color: 'var(--info)' },
    security: { emoji: '🔒', label: 'Security', color: 'var(--error)' },
    performance: { emoji: '⚡', label: 'Performance', color: 'var(--warning)' },
  };
  return categoryMap[category] || { emoji: '📋', label: category, color: 'var(--text-tertiary)' };
}

/**
 * Get complexity display info.
 */
export function getComplexityInfo(complexity: GoalComplexity): { emoji: string; label: string; color: string } {
  const complexityMap: Record<GoalComplexity, { emoji: string; label: string; color: string }> = {
    trivial: { emoji: '🟢', label: 'Trivial', color: 'var(--success)' },
    simple: { emoji: '🟢', label: 'Simple', color: 'var(--success)' },
    moderate: { emoji: '🔵', label: 'Moderate', color: 'var(--accent)' },
    complex: { emoji: '🟠', label: 'Complex', color: 'var(--warning)' },
  };
  return complexityMap[complexity] || { emoji: '⚪', label: complexity, color: 'var(--text-tertiary)' };
}

/**
 * Get status display info.
 */
export function getStatusInfo(status: GoalStatus): { emoji: string; label: string; color: string } {
  const statusMap: Record<GoalStatus, { emoji: string; label: string; color: string }> = {
    pending: { emoji: '⏳', label: 'Pending', color: 'var(--text-tertiary)' },
    blocked: { emoji: '🚫', label: 'Blocked', color: 'var(--warning)' },
    claimed: { emoji: '🎯', label: 'Claimed', color: 'var(--accent)' },
    executing: { emoji: '🔄', label: 'Executing', color: 'var(--success)' },
    completed: { emoji: '✅', label: 'Completed', color: 'var(--success)' },
    failed: { emoji: '❌', label: 'Failed', color: 'var(--error)' },
    skipped: { emoji: '⏭️', label: 'Skipped', color: 'var(--text-tertiary)' },
  };
  return statusMap[status] || { emoji: '❓', label: status, color: 'var(--text-tertiary)' };
}

/**
 * Format priority as percentage.
 */
export function formatPriority(priority: number): string {
  return `${Math.round(priority * 100)}%`;
}

/**
 * Get priority level (high/medium/low).
 */
export function getPriorityLevel(priority: number): 'high' | 'medium' | 'low' {
  if (priority >= 0.7) return 'high';
  if (priority >= 0.4) return 'medium';
  return 'low';
}
