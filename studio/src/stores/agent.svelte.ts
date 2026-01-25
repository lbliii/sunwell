/**
 * Agent Store — manages Sunwell agent state and communication (Svelte 5 runes)
 */

import { AgentStatus, TaskStatus, PlanningPhase } from '$lib/constants';
import type { AgentState, AgentEvent, Task, Concept, ConceptCategory, PlanCandidate, RefinementRound } from '$lib/types';
import { updateNode, completeNode, reloadDag, loadProjectDagIndex } from './dag.svelte';
import { reloadFiles } from './files.svelte';
import { runGoal as apiRunGoal, stopAgent as apiStopAgent, onAgentEvent } from '$lib/api';
import { apiPost } from '$lib/socket';
import type { GoalNode, TaskNodeDetail } from '$lib/types';
import { setActiveLens } from './lens.svelte';
import {
  handleSkillGraphResolved,
  handleSkillWaveStart,
  handleSkillWaveComplete,
  handleSkillCacheHit,
  handleSkillExecuteStart,
  handleSkillExecuteComplete,
} from './skill-graph.svelte';
import { handleSecurityEvent } from './security.svelte';

const DEMO_MODE = false;

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

const initialState: AgentState = {
  status: AgentStatus.IDLE,
  goal: null,
  tasks: [],
  currentTaskIndex: -1,
  totalTasks: 0,
  startTime: null,
  endTime: null,
  error: null,
  learnings: [],
  concepts: [],
  planningCandidates: [],
  selectedCandidate: null,
  refinementRounds: [],
  planningProgress: null,
  convergence: null,
};

let _state = $state<AgentState>({ ...initialState });
let eventUnlisten: (() => void) | null = null;
let stopUnlisten: (() => void) | null = null;

// RFC-105: Track current project path for DAG updates
let _currentProjectPath: string | null = null;

// ═══════════════════════════════════════════════════════════════
// CONCEPT EXTRACTION
// ═══════════════════════════════════════════════════════════════

const CONCEPT_PATTERNS: Record<ConceptCategory, RegExp[]> = {
  framework: [/\bflask\b/i, /\bfastapi\b/i, /\bdjango\b/i, /\bexpress\b/i, /\bsvelte\b/i, /\breact\b/i, /\bvue\b/i, /\bnext\.?js\b/i],
  database: [/\bsqlite\b/i, /\bpostgres(?:ql)?\b/i, /\bmysql\b/i, /\bsqlalchemy\b/i, /\bprisma\b/i, /\bmongodb\b/i, /\bredis\b/i],
  testing: [/\bpytest\b/i, /\bjest\b/i, /\bunittest\b/i, /\bvitest\b/i, /\bmocha\b/i],
  pattern: [/\brest\s?api\b/i, /\bgraphql\b/i, /\bmvc\b/i, /\bcrud\b/i, /\borm\b/i],
  tool: [/\bdocker\b/i, /\bgit\b/i, /\bnpm\b/i, /\bpip\b/i, /\bcargo\b/i, /\buv\b/i],
  language: [/\bpython\b/i, /\btypescript\b/i, /\bjavascript\b/i, /\brust\b/i, /\bgo\b/i],
};

function extractConcepts(learning: string): Concept[] {
  const concepts: Concept[] = [];
  const seen = new Set<string>();
  for (const [category, patterns] of Object.entries(CONCEPT_PATTERNS)) {
    for (const pattern of patterns) {
      const match = learning.match(pattern);
      if (match) {
        const id = match[0].toLowerCase().replace(/\s+/g, '');
        if (!seen.has(id)) {
          seen.add(id);
          concepts.push({ id, label: match[0], category: category as ConceptCategory, timestamp: Date.now() });
        }
      }
    }
  }
  return concepts;
}

function deduplicateConcepts(concepts: Concept[]): Concept[] {
  const seen = new Set<string>();
  return concepts.filter(c => { if (seen.has(c.id)) return false; seen.add(c.id); return true; });
}

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

/** Safely get learnings array, returns empty array if not initialized */
function getLearnings(): string[] {
  const learnings = _state.learnings;
  return Array.isArray(learnings) ? learnings : [];
}

/** Safely get refinement rounds array, returns empty array if not initialized */
function getRefinementRounds(): RefinementRound[] {
  const rounds = _state.refinementRounds;
  return Array.isArray(rounds) ? rounds : [];
}

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

const RUNNING_STATUSES: AgentStatus[] = [AgentStatus.STARTING, AgentStatus.PLANNING, AgentStatus.RUNNING];

// Pre-compute task counts once for O(n) total instead of O(4n) per access
function getTaskCounts(): { complete: number; failed: number; total: number } {
  let complete = 0;
  let failed = 0;
  const tasks = _state.tasks;
  if (!Array.isArray(tasks)) return { complete: 0, failed: 0, total: 0 };
  for (const t of tasks) {
    if (t.status === TaskStatus.COMPLETE) complete++;
    else if (t.status === TaskStatus.FAILED) failed++;
  }
  return { complete, failed, total: tasks.length };
}

export const agent = {
  get status() { return _state.status; },
  get goal() { return _state.goal; },
  /** Tasks array (frozen to prevent external mutation) */
  get tasks(): readonly Task[] { 
    const tasks = _state.tasks;
    return Object.freeze(Array.isArray(tasks) ? [...tasks] : []); 
  },
  get currentTaskIndex() { return _state.currentTaskIndex; },
  get totalTasks() { return _state.totalTasks; },
  get startTime() { return _state.startTime; },
  get endTime() { return _state.endTime; },
  get error() { return _state.error; },
  /** Learnings array (frozen to prevent external mutation) */
  get learnings(): readonly string[] { 
    const learnings = _state.learnings;
    return Object.freeze(Array.isArray(learnings) ? [...learnings] : []); 
  },
  /** Concepts array (frozen to prevent external mutation) */
  get concepts(): readonly Concept[] { 
    const concepts = _state.concepts;
    return Object.freeze(Array.isArray(concepts) ? [...concepts] : []); 
  },
  /** Planning candidates array (frozen to prevent external mutation) */
  get planningCandidates(): readonly PlanCandidate[] { 
    const candidates = _state.planningCandidates;
    return Object.freeze(Array.isArray(candidates) ? [...candidates] : []); 
  },
  get selectedCandidate() { return _state.selectedCandidate; },
  /** Refinement rounds array (frozen to prevent external mutation) */
  get refinementRounds(): readonly RefinementRound[] { 
    const rounds = _state.refinementRounds;
    return Object.freeze(Array.isArray(rounds) ? [...rounds] : []); 
  },
  get planningProgress() { return _state.planningProgress; },
  get convergence() { return _state.convergence; },
  // Computed
  get isRunning() { return RUNNING_STATUSES.includes(_state.status); },
  get isConverging() { return _state.convergence?.status === 'running'; },
  get isDone() { return _state.status === AgentStatus.DONE; },
  get hasError() { return _state.status === AgentStatus.ERROR; },
  get progress() {
    // Progress based on actual tasks seen, not planned total
    // This handles incremental builds where fewer tasks run
    const counts = getTaskCounts();
    if (counts.total === 0) return _state.status === AgentStatus.DONE ? 100 : 0;
    return Math.round(((counts.complete + counts.failed) / counts.total) * 100);
  },
  get duration() {
    return !_state.startTime ? 0 : Math.round(((_state.endTime ?? Date.now()) - _state.startTime) / 1000);
  },
  get completedTasks() { return getTaskCounts().complete; },
  get failedTasks() { return getTaskCounts().failed; },
  /** Number of planned artifacts that were skipped (incremental builds) */
  get skippedTasks() { 
    const tasks = _state.tasks;
    return Math.max(0, _state.totalTasks - (Array.isArray(tasks) ? tasks.length : 0)); 
  },
};

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Run a goal with optional lens and provider selection (RFC-064, RFC-Cloud-Model-Parity).
 * 
 * @param goal - The goal to execute
 * @param projectPath - Optional project path
 * @param projectId - Optional project ID from registry (RFC-117)
 * @param lens - Optional explicit lens name (e.g., "coder", "tech-writer")
 * @param autoLens - Whether to auto-detect lens based on goal (default: true)
 * @param provider - Optional model provider (e.g., "openai", "anthropic", "ollama")
 */
export async function runGoal(
  goal: string,
  projectPath?: string,
  projectId?: string,
  lens?: string | null,
  autoLens?: boolean,
  provider?: string | null,
): Promise<string | null> {
  // Prevent concurrent runs
  if (RUNNING_STATUSES.includes(_state.status)) {
    console.warn('Agent already running, ignoring runGoal call');
    return null;
  }

  if (DEMO_MODE) {
    const success = await runDemoGoal(goal);
    return success ? `/demo/${goal.slice(0, 20).replace(/\s+/g, '-')}` : null;
  }

  try {
    _state = { ...initialState, status: AgentStatus.STARTING, goal, startTime: Date.now() };
    await setupEventListeners();

    // RFC-113: Use unified API layer (works with both Tauri and HTTP)
    // RFC-117: Pass project_id if provided
    const result = await apiRunGoal({
      goal,
      projectPath,
      projectId,
      lens: lens ?? null,
      autoLens: autoLens ?? true,
      provider: provider ?? null,
    });

    if (!result.success) { _state = { ..._state, status: AgentStatus.ERROR, error: result.message }; return null; }
    _state = { ..._state, status: AgentStatus.PLANNING };

    // RFC-105: Track project path for DAG updates
    _currentProjectPath = result.workspace_path;

    return result.workspace_path;
  } catch (e) {
    _state = { ..._state, status: AgentStatus.ERROR, error: e instanceof Error ? e.message : String(e) };
    return null;
  }
}

async function runDemoGoal(goal: string): Promise<boolean> {
  const demoTasks: Task[] = [
    { id: '1', description: 'Analyzing goal...', status: TaskStatus.PENDING, progress: 0 },
    { id: '2', description: 'Creating project structure', status: TaskStatus.PENDING, progress: 0 },
    { id: '3', description: 'Setting up models', status: TaskStatus.PENDING, progress: 0 },
    { id: '4', description: 'Implementing routes', status: TaskStatus.PENDING, progress: 0 },
    { id: '5', description: 'Writing tests', status: TaskStatus.PENDING, progress: 0 },
  ];
  _state = { ...initialState, status: AgentStatus.PLANNING, goal, startTime: Date.now(), tasks: demoTasks, totalTasks: demoTasks.length };
  await sleep(800);
  _state = { ..._state, status: AgentStatus.RUNNING };
  for (let i = 0; i < demoTasks.length; i++) {
    const tasks1 = _state.tasks;
    if (Array.isArray(tasks1)) {
      _state = { ..._state, tasks: tasks1.map((t, idx) => idx === i ? { ...t, status: TaskStatus.RUNNING, progress: 0 } : t), currentTaskIndex: i };
    }
    for (let p = 0; p <= 100; p += 25) { 
      await sleep(100 + Math.random() * 150); 
      const tasks2 = _state.tasks;
      if (Array.isArray(tasks2)) {
        _state = { ..._state, tasks: tasks2.map((t, idx) => idx === i ? { ...t, progress: p } : t) }; 
      }
    }
    const tasks3 = _state.tasks;
    if (Array.isArray(tasks3)) {
      _state = { ..._state, tasks: tasks3.map((t, idx) => idx === i ? { ...t, status: TaskStatus.COMPLETE, progress: 100 } : t) };
    }
    await sleep(150);
  }
  const demoLearnings = ['Detected Flask web framework', 'Using SQLAlchemy for ORM', 'pytest available for testing'];
  const demoConcepts: Concept[] = demoLearnings.flatMap(extractConcepts);
  _state = { ..._state, status: AgentStatus.DONE, endTime: Date.now(), learnings: demoLearnings, concepts: deduplicateConcepts(demoConcepts) };
  return true;
}

function sleep(ms: number): Promise<void> { return new Promise(resolve => setTimeout(resolve, ms)); }

// RFC-105: Helper to append completed goal to hierarchical DAG
async function appendCompletedGoalToDag(
  goalId: string,
  goalTitle: string,
  _artifacts: string[], // Available for future use
  _failed: string[],    // Available for future use  
  partial: boolean
): Promise<void> {
  if (!_currentProjectPath) return;

  try {
    // Build task nodes from current agent state
    const stateTasks = _state.tasks;
    const tasks: TaskNodeDetail[] = Array.isArray(stateTasks) ? stateTasks.map(t => ({
      id: t.id,
      description: t.description,
      status: t.status === 'complete' ? 'complete' : t.status === 'failed' ? 'failed' : 'pending',
      produces: [], // TODO: Extract from task data when available
      requires: [],
      dependsOn: [],
      contentHash: undefined,
    })) : [];

    // Construct the GoalNode
    const now = new Date().toISOString();
    const stateLearnings = _state.learnings;
    const goalNode: GoalNode = {
      id: goalId || `goal-${Date.now()}`,
      title: goalTitle,
      description: _state.goal ?? goalTitle,
      status: partial ? 'partial' : 'complete',
      createdAt: _state.startTime ? new Date(_state.startTime).toISOString() : now,
      completedAt: now,
      tasks,
      learnings: Array.isArray(stateLearnings) ? stateLearnings.filter(l => !l.startsWith('🚀') && !l.startsWith('✅') && !l.startsWith('❌') && !l.startsWith('⚠️')) : [],
      metrics: {
        durationSeconds: _state.startTime ? Math.round((Date.now() - _state.startTime) / 1000) : undefined,
        tasksCompleted: Array.isArray(stateTasks) ? stateTasks.filter(t => t.status === 'complete').length : 0,
        tasksSkipped: Math.max(0, _state.totalTasks - (Array.isArray(stateTasks) ? stateTasks.length : 0)),
      },
    };

    // RFC-113: Use HTTP API
    await apiPost('/api/dag/append', {
      path: _currentProjectPath,
      goal: goalNode,
    });

    // Reload the project DAG index to reflect changes
    await loadProjectDagIndex(_currentProjectPath);

    console.log(`RFC-105: Goal ${goalId} appended to DAG`);
  } catch (e) {
    console.error('RFC-105: Failed to append goal to DAG:', e);
    // Don't fail the goal completion, just log the error
  }
}

export async function stopAgent(): Promise<void> {
  if (DEMO_MODE) { cleanup(); _state = { ..._state, status: AgentStatus.IDLE, endTime: Date.now() }; return; }
  try {
    // RFC-113: Use unified API layer
    await apiStopAgent();
    cleanup();
    _state = { ..._state, status: AgentStatus.IDLE, endTime: Date.now() };
  } catch (e) { console.error('Failed to stop agent:', e); }
}

export function resetAgent(): void {
  cleanup();
  _state = { ...initialState };
}

// ═══════════════════════════════════════════════════════════════
// EVENT HANDLING
// ═══════════════════════════════════════════════════════════════

async function setupEventListeners(): Promise<void> {
  if (DEMO_MODE) return;
  cleanup();
  try {
    // RFC-113: Use unified API layer for events (works with both Tauri and HTTP)
    eventUnlisten = onAgentEvent((event) => { handleAgentEvent(event); });
    // Note: 'agent-stopped' event is now sent as a 'complete' event type
  } catch (e) { console.error('Failed to setup event listeners:', e); }
}

function cleanup(): void {
  if (eventUnlisten) { eventUnlisten(); eventUnlisten = null; }
  if (stopUnlisten) { stopUnlisten(); stopUnlisten = null; }
}

function validatePlanningState(eventType: string, currentState: AgentState): string | null {
  const requiresProgress = ['plan_candidate_generated', 'plan_candidate_scored', 'plan_candidates_complete', 'plan_scoring_complete'];
  if (requiresProgress.includes(eventType) && !currentState.planningProgress) {
    return `Event ${eventType} received before plan_candidate_start.`;
  }
  return null;
}

export function handleAgentEvent(event: AgentEvent): void {
  const { type, data } = event;
  if (type.startsWith('plan_')) console.debug(`[Sunwell] Planning event: ${type}`, data);
  const validationError = validatePlanningState(type, _state);
  if (validationError) console.warn(`[Sunwell] State validation warning: ${validationError}`);

  switch (type) {
    case 'plan_start':
      _state = { ..._state, status: AgentStatus.PLANNING, planningCandidates: [], selectedCandidate: null, refinementRounds: [], planningProgress: null };
      break;

    case 'plan_candidate_start': {
      const totalCandidates = (data.total_candidates as number) ?? 0;
      _state = { ..._state, planningProgress: { phase: PlanningPhase.GENERATING, current_candidates: 0, total_candidates: totalCandidates }, planningCandidates: [] };
      break;
    }

    case 'plan_candidate_generated': {
      const candidateId = data.candidate_id as string;
      if (!candidateId) {
        console.error('[Sunwell] plan_candidate_generated missing required candidate_id');
        break;
      }
      const artifactCount = (data.artifact_count as number) ?? 0;
      const progressVal = (data.progress as number) ?? 0;
      const totalCandidates = (data.total_candidates as number) ?? 0;
      const varianceConfig = (data.variance_config as Record<string, unknown>) ?? {};
      // Store by ID (no index fallback)
      const candidateMap = new Map<string, PlanCandidate>();
      const planningCandidates = _state.planningCandidates;
      if (Array.isArray(planningCandidates)) {
        for (const candidate of planningCandidates) {
          if (candidate != null) candidateMap.set(candidate.id, candidate);
        }
      }
      candidateMap.set(candidateId, {
        id: candidateId,
        artifact_count: artifactCount,
        variance_config: varianceConfig as PlanCandidate['variance_config'],
      });
      const candidates = Array.from(candidateMap.values());
      const currentProgress = _state.planningProgress ?? {
        phase: PlanningPhase.GENERATING,
        current_candidates: 0,
        total_candidates: totalCandidates || 1,
      };
      _state = {
        ..._state,
        planningCandidates: candidates,
        planningProgress: {
          ...currentProgress,
          current_candidates: Math.max(progressVal, currentProgress.current_candidates),
          total_candidates: totalCandidates || currentProgress.total_candidates,
        },
      };
      break;
    }

    case 'plan_candidates_complete':
      _state = { ..._state, planningProgress: _state.planningProgress ? { ..._state.planningProgress, phase: PlanningPhase.SCORING, current_candidates: 0 } : null };
      break;

    case 'plan_candidate_scored': {
      const candidateId = data.candidate_id as string;
      if (!candidateId) {
        console.error('[Sunwell] plan_candidate_scored missing required candidate_id');
        break;
      }
      const score = (data.score as number) ?? 0;
      const metrics = (data.metrics as PlanCandidate['metrics']) ?? undefined;
      const progressVal = (data.progress as number) ?? 0;
      // Match by ID (no index fallback)
      const candidateMap = new Map<string, PlanCandidate>();
      const planningCandidates = _state.planningCandidates;
      if (Array.isArray(planningCandidates)) {
        for (const candidate of planningCandidates) {
          if (candidate != null) candidateMap.set(candidate.id, candidate);
        }
      }
      const existing = candidateMap.get(candidateId);
      if (existing) {
        candidateMap.set(candidateId, { ...existing, score, metrics });
      } else {
        // Create new candidate - this shouldn't happen but handle gracefully
        console.warn(`[Sunwell] plan_candidate_scored for unknown candidate: ${candidateId}`);
        candidateMap.set(candidateId, {
          id: candidateId,
          artifact_count: 0,
          score,
          metrics,
        });
      }
      const candidates = Array.from(candidateMap.values());
      _state = {
        ..._state,
        planningCandidates: candidates,
        planningProgress: _state.planningProgress
          ? { ..._state.planningProgress, current_candidates: progressVal }
          : null,
      };
      break;
    }

    case 'plan_scoring_complete':
      _state = { ..._state, planningProgress: _state.planningProgress ? { ..._state.planningProgress, phase: PlanningPhase.COMPLETE } : null };
      break;

    case 'plan_refine_start': {
      const round = (data.round as number) ?? 0;
      const currentScore = (data.current_score as number) ?? 0;
      const rawImprovements = data.improvements_identified;
      const improvementsIdentified = Array.isArray(rawImprovements) ? rawImprovements.join('; ') : (rawImprovements as string) ?? '';
      const totalRounds = (data.total_rounds as number) ?? 0;
      _state = { ..._state, planningProgress: { phase: PlanningPhase.REFINING, current_candidates: round, total_candidates: totalRounds }, refinementRounds: [...getRefinementRounds(), { round, current_score: currentScore, improvements_identified: improvementsIdentified, improved: false }] };
      break;
    }

    case 'plan_refine_attempt': {
      const round = (data.round as number) ?? 0;
      const improvementsApplied = (data.improvements_applied as string[]) ?? [];
      const rounds = [...getRefinementRounds()];
      const roundIndex = rounds.findIndex(r => r.round === round);
      if (roundIndex >= 0) rounds[roundIndex] = { ...rounds[roundIndex], improvements_applied: improvementsApplied };
      else rounds.push({ round, current_score: 0, improvements_identified: '', improved: false, improvements_applied: improvementsApplied });
      _state = { ..._state, refinementRounds: rounds };
      break;
    }

    case 'plan_refine_complete': {
      const round = (data.round as number) ?? 0;
      const improved = (data.improved as boolean) ?? false;
      const oldScore = (data.old_score as number) ?? undefined;
      const newScore = (data.new_score as number) ?? undefined;
      const improvement = (data.improvement as number) ?? undefined;
      const reason = (data.reason as string) ?? undefined;
      const rounds = [...getRefinementRounds()];
      const roundIndex = rounds.findIndex(r => r.round === round);
      if (roundIndex >= 0) rounds[roundIndex] = { ...rounds[roundIndex], improved, old_score: oldScore, new_score: newScore, improvement, reason };
      _state = { ..._state, refinementRounds: rounds };
      break;
    }

    case 'plan_refine_final':
      _state = { ..._state, planningProgress: _state.planningProgress ? { ..._state.planningProgress, phase: PlanningPhase.COMPLETE } : null };
      break;

    case 'plan_winner': {
      const selectedId = data.selected_candidate_id as string;
      if (!selectedId) {
        console.error('[Sunwell] plan_winner missing required selected_candidate_id');
        break;
      }
      const selectionReason = (data.selection_reason as string) ?? '';
      const metrics = (data.metrics as PlanCandidate['metrics']) ?? undefined;
      const score = (data.score as number) ?? undefined;
      const varianceConfig = (data.variance_config as PlanCandidate['variance_config']) ?? undefined;
      // Match by ID (no index fallback)
      const planningCandidates = _state.planningCandidates;
      const selected = Array.isArray(planningCandidates) ? planningCandidates.find(c => c.id === selectedId) ?? null : null;
      _state = {
        ..._state,
        status: AgentStatus.RUNNING,
        totalTasks: (data.tasks as number) ?? (data.artifact_count as number) ?? 0,
        selectedCandidate: selected
          ? {
            ...selected,
            selection_reason: selectionReason,
            score: score ?? selected.score,
            metrics: metrics ?? selected.metrics,
            variance_config: varianceConfig ?? selected.variance_config,
          }
          : {
            // Candidate wasn't tracked (shouldn't happen) - create minimal entry
            id: selectedId,
            artifact_count: (data.artifact_count as number) ?? 0,
            score,
            metrics,
            selection_reason: selectionReason,
            variance_config: varianceConfig,
          },
      };
      break;
    }

    case 'task_start': {
      const taskId = data.task_id as string;
      if (!taskId) {
        console.error('[Sunwell] task_start missing required task_id');
        break;
      }
      const description = (data.description as string) ?? 'Working...';
      const stateTasks = _state.tasks;
      if (!Array.isArray(stateTasks)) {
        const newTask: Task = { id: taskId, description, status: TaskStatus.RUNNING, progress: 0 };
        _state = { ..._state, tasks: [newTask], currentTaskIndex: 0 };
      } else {
        const existingIndex = stateTasks.findIndex(t => t.id === taskId);
        if (existingIndex >= 0) {
          const tasks = [...stateTasks]; tasks[existingIndex] = { ...tasks[existingIndex], status: TaskStatus.RUNNING };
          _state = { ..._state, tasks, currentTaskIndex: existingIndex };
        } else {
          const newTask: Task = { id: taskId, description, status: TaskStatus.RUNNING, progress: 0 };
          _state = { ..._state, tasks: [...stateTasks, newTask], currentTaskIndex: stateTasks.length };
        }
      }
      updateNode(taskId, { status: 'running', currentAction: description });
      break;
    }

    case 'task_progress': {
      const taskId = data.task_id as string;
      if (!taskId) {
        console.error('[Sunwell] task_progress missing required task_id');
        break;
      }
      const progressVal = (data.progress as number) ?? 0;
      const stateTasks = _state.tasks;
      if (Array.isArray(stateTasks)) {
        const taskIndex = stateTasks.findIndex(t => t.id === taskId);
        if (taskIndex >= 0) {
          const tasks = [...stateTasks]; tasks[taskIndex] = { ...tasks[taskIndex], progress: progressVal };
          _state = { ..._state, tasks };
        }
      }
      updateNode(taskId, { progress: progressVal });
      break;
    }

    case 'task_complete': {
      const taskId = data.task_id as string;
      if (!taskId) {
        console.error('[Sunwell] task_complete missing required task_id');
        break;
      }
      const durationMs = (data.duration_ms as number) ?? 0;
      const stateTasks = _state.tasks;
      if (Array.isArray(stateTasks)) {
        const tasks = stateTasks.map(t => t.id === taskId ? { ...t, status: TaskStatus.COMPLETE, progress: 100, duration_ms: durationMs } : t);
        _state = { ..._state, tasks };
      }
      completeNode(taskId);
      reloadFiles(); // Refresh file tree when task completes
      break;
    }

    case 'task_failed': {
      const taskId = data.task_id as string;
      if (!taskId) {
        console.error('[Sunwell] task_failed missing required task_id');
        break;
      }
      const stateTasks = _state.tasks;
      if (Array.isArray(stateTasks)) {
        const tasks = stateTasks.map(t => t.id === taskId ? { ...t, status: TaskStatus.FAILED } : t);
        _state = { ..._state, tasks };
      }
      updateNode(taskId, { status: 'failed' });
      break;
    }

    case 'tool_complete': {
      // Track tool invocations, especially self-corrections
      const toolName = data.tool_name as string;
      const selfCorrected = data.self_corrected as boolean;
      const success = data.success as boolean;

      if (selfCorrected) {
        console.info(`[Sunwell] Self-corrected: ${toolName}`);
        // Store self-correction for display in Observatory
        const selfCorrections = _state.selfCorrections ?? [];
        _state = {
          ..._state,
          selfCorrections: [...selfCorrections, {
            tool: toolName,
            output: (data.output as string) ?? '',
            timestamp: Date.now(),
            invocationSummary: data.invocation_summary as Record<string, unknown> | undefined,
          }],
        };
      } else if (!success) {
        console.warn(`[Sunwell] Tool failed: ${toolName}`, data.error);
      }
      break;
    }

    case 'memory_learning': {
      const fact = (data.fact as string) ?? '';
      if (fact) {
        const newConcepts = extractConcepts(fact);
        const stateLearnings = _state.learnings;
        const stateConcepts = _state.concepts;
        _state = { 
          ..._state, 
          learnings: Array.isArray(stateLearnings) ? [...stateLearnings, fact] : [fact], 
          concepts: deduplicateConcepts(Array.isArray(stateConcepts) ? [...stateConcepts, ...newConcepts] : newConcepts) 
        };
      }
      break;
    }

    case 'complete': {
      const tasksCompleted = (data.tasks_completed as number) ?? (data.completed as number) ?? 0;
      const tasksFailed = (data.tasks_failed as number) ?? (data.failed as number) ?? 0;
      const stateTasks = _state.tasks;
      const tasksLen = Array.isArray(stateTasks) ? stateTasks.length : 0;
      const hasAnomaly = tasksLen === 0 && tasksCompleted > 0;
      if (hasAnomaly) {
        console.warn(`[Sunwell] Agent completed with ${tasksCompleted} artifacts but no task_start events`);
        const syntheticTasks: Task[] = [];
        for (let i = 0; i < tasksCompleted; i++) syntheticTasks.push({ id: `completed-${i}`, description: `Completed artifact ${i + 1}`, status: TaskStatus.COMPLETE, progress: 100 });
        for (let i = 0; i < tasksFailed; i++) syntheticTasks.push({ id: `failed-${i}`, description: `Failed artifact ${i + 1}`, status: TaskStatus.FAILED, progress: 0 });
        _state = { ..._state, status: AgentStatus.DONE, endTime: Date.now(), tasks: syntheticTasks.length > 0 ? syntheticTasks : (Array.isArray(stateTasks) ? stateTasks : []), totalTasks: _state.totalTasks > 0 ? _state.totalTasks : tasksCompleted + tasksFailed };
      } else {
        _state = { ..._state, status: AgentStatus.DONE, endTime: Date.now() };
      }
      reloadFiles(); // Refresh file tree on completion
      cleanup();
      break;
    }

    case 'error': {
      const message = (data.message as string) ?? 'Unknown error';
      _state = { ..._state, status: AgentStatus.ERROR, error: message, endTime: Date.now() };
      cleanup();
      break;
    }

    case 'escalate': {
      const reason = (data.reason as string) ?? 'Unknown';
      const message = (data.message as string) ?? '';
      const fixed = (data.fixed as number) ?? 0;
      const errors = (data.errors as string[]) ?? [];

      // Build a user-friendly error with context
      let errorMsg = message || `Escalated: ${reason}`;
      if (errors.length > 0) {
        errorMsg += `\n\nErrors:\n${errors.map(e => `• ${e}`).join('\n')}`;
      }
      if (fixed > 0) {
        errorMsg += `\n\n(${fixed} errors were auto-fixed)`;
      }

      _state = { ..._state, status: AgentStatus.ERROR, error: errorMsg };
      break;
    }

    // RFC-064: Lens events
    case 'lens_selected': {
      const name = (data.name as string) ?? '';
      const reason = (data.reason as string) ?? '';
      setActiveLens(name);
      _state = {
        ..._state,
        learnings: [...getLearnings(), `Using lens: ${name} (${reason})`],
      };
      break;
    }

    case 'lens_changed': {
      const name = (data.name as string) ?? '';
      setActiveLens(name);
      break;
    }

    // RFC-071: Briefing events
    case 'briefing_loaded': {
      const mission = (data.mission as string) ?? '';
      const status = (data.status as string) ?? '';
      const hasHazards = (data.has_hazards as boolean) ?? false;
      const hasDispatchHints = (data.has_dispatch_hints as boolean) ?? false;
      // Store briefing info in learnings for visibility
      let briefingInfo = `📋 Briefing loaded: ${mission} [${status}]`;
      if (hasHazards) briefingInfo += ' ⚠️ Has hazards';
      if (hasDispatchHints) briefingInfo += ' 🎯 Has dispatch hints';
      _state = {
        ..._state,
        learnings: [...getLearnings(), briefingInfo],
      };
      break;
    }

    case 'briefing_saved': {
      const status = (data.status as string) ?? '';
      const tasksCompleted = (data.tasks_completed as number) ?? 0;
      _state = {
        ..._state,
        learnings: [...getLearnings(), `📋 Briefing saved: ${status} (${tasksCompleted} tasks)`],
      };
      break;
    }

    case 'prefetch_start': {
      const briefing = (data.briefing as string) ?? '';
      _state = {
        ..._state,
        learnings: [...getLearnings(), `🔄 Prefetch starting for: ${briefing}`],
      };
      break;
    }

    case 'prefetch_complete': {
      const filesLoaded = (data.files_loaded as number) ?? 0;
      const learningsLoaded = (data.learnings_loaded as number) ?? 0;
      const skillsActivated = (data.skills_activated as string[]) ?? [];
      const skills = skillsActivated.length > 0 ? ` Skills: ${skillsActivated.join(', ')}` : '';
      _state = {
        ..._state,
        learnings: [...getLearnings(), `✅ Prefetch complete: ${filesLoaded} files, ${learningsLoaded} learnings.${skills}`],
      };
      break;
    }

    case 'prefetch_timeout': {
      const error = (data.error as string) ?? '';
      const msg = error ? `⏱️ Prefetch timed out: ${error}` : '⏱️ Prefetch timed out (proceeding without warm context)';
      _state = {
        ..._state,
        learnings: [...getLearnings(), msg],
      };
      break;
    }

    case 'lens_suggested': {
      const suggested = (data.suggested as string) ?? '';
      const reason = (data.reason as string) ?? '';
      _state = {
        ..._state,
        learnings: [...getLearnings(), `🎯 Lens suggested: ${suggested} (${reason})`],
      };
      break;
    }

    // RFC-087: Skill graph execution events
    case 'skill_graph_resolved': {
      handleSkillGraphResolved({
        lens_name: (data.lens_name as string) ?? '',
        skill_count: (data.skill_count as number) ?? 0,
        wave_count: (data.wave_count as number) ?? 0,
        content_hash: (data.content_hash as string) ?? '',
      });
      const skillCount = (data.skill_count as number) ?? 0;
      const waveCount = (data.wave_count as number) ?? 0;
      const lensName = (data.lens_name as string) ?? '';
      _state = {
        ..._state,
        learnings: [...getLearnings(), `🔧 Skill graph: ${skillCount} skills in ${waveCount} waves (${lensName})`],
      };
      break;
    }

    case 'skill_wave_start': {
      handleSkillWaveStart({
        wave_index: (data.wave_index as number) ?? 0,
        total_waves: (data.total_waves as number) ?? 1,
        skills: (data.skills as string[]) ?? [],
        parallel: (data.parallel as boolean) ?? true,
      });
      const waveIndex = (data.wave_index as number) ?? 0;
      const totalWaves = (data.total_waves as number) ?? 1;
      const skills = (data.skills as string[]) ?? [];
      _state = {
        ..._state,
        learnings: [...getLearnings(), `⚡ Wave ${waveIndex + 1}/${totalWaves}: ${skills.join(', ')}`],
      };
      break;
    }

    case 'skill_wave_complete': {
      handleSkillWaveComplete({
        wave_index: (data.wave_index as number) ?? 0,
        duration_ms: (data.duration_ms as number) ?? 0,
        succeeded: (data.succeeded as string[]) ?? [],
        failed: (data.failed as string[]) ?? [],
      });
      const waveIndex = (data.wave_index as number) ?? 0;
      const durationMs = (data.duration_ms as number) ?? 0;
      const succeeded = (data.succeeded as string[]) ?? [];
      const failed = (data.failed as string[]) ?? [];
      const status = failed.length > 0 ? `⚠️ ${failed.length} failed` : `✅ ${succeeded.length} complete`;
      _state = {
        ..._state,
        learnings: [...getLearnings(), `Wave ${waveIndex + 1} done: ${status} (${durationMs}ms)`],
      };
      break;
    }

    case 'skill_cache_hit': {
      handleSkillCacheHit({
        skill_name: (data.skill_name as string) ?? '',
        cache_key: (data.cache_key as string) ?? '',
        saved_ms: (data.saved_ms as number) ?? 0,
      });
      const skillName = (data.skill_name as string) ?? '';
      const savedMs = (data.saved_ms as number) ?? 0;
      _state = {
        ..._state,
        learnings: [...getLearnings(), `💨 Cache hit: ${skillName} (saved ~${savedMs}ms)`],
      };
      break;
    }

    case 'skill_execute_start': {
      handleSkillExecuteStart({
        skill_name: (data.skill_name as string) ?? '',
        wave_index: (data.wave_index as number) ?? 0,
        requires: (data.requires as string[]) ?? [],
        context_keys_available: (data.context_keys_available as string[]) ?? [],
      });
      // Don't flood learnings with every skill start, just update store
      break;
    }

    case 'skill_execute_complete': {
      handleSkillExecuteComplete({
        skill_name: (data.skill_name as string) ?? '',
        duration_ms: (data.duration_ms as number) ?? 0,
        produces: (data.produces as string[]) ?? [],
        cached: (data.cached as boolean) ?? false,
        success: (data.success as boolean) ?? true,
        error: data.error as string | undefined,
      });
      const skillName = (data.skill_name as string) ?? '';
      const success = (data.success as boolean) ?? true;
      const error = data.error as string | undefined;
      if (!success) {
        _state = {
          ..._state,
          learnings: [...getLearnings(), `❌ Skill ${skillName}: ${error ?? 'failed'}`],
        };
      }
      break;
    }

    // RFC-089: Security events
    case 'security_approval_requested':
    case 'security_approval_received':
    case 'security_violation':
    case 'security_scan_complete':
    case 'audit_log_entry': {
      const learning = handleSecurityEvent(type, data);
      if (learning) {
        _state = {
          ..._state,
          learnings: [...getLearnings(), learning],
        };
      }
      break;
    }

    // RFC-094: Backlog lifecycle events — trigger DAG reload
    case 'backlog_goal_added': {
      const goalId = (data.goal_id as string) ?? '';
      const title = (data.title as string) ?? '';
      _state = {
        ..._state,
        learnings: [...getLearnings(), `📋 Goal added: ${title || goalId}`],
      };
      reloadDag();
      break;
    }

    case 'backlog_goal_started': {
      const goalId = (data.goal_id as string) ?? '';
      const title = (data.title as string) ?? '';
      _state = {
        ..._state,
        learnings: [...getLearnings(), `🚀 Goal started: ${title || goalId}`],
      };
      reloadDag();
      break;
    }

    case 'backlog_goal_completed': {
      const goalId = (data.goal_id as string) ?? '';
      const goalTitle = (data.title as string) ?? _state.goal ?? 'Unknown goal';
      const artifacts = (data.artifacts as string[]) ?? [];
      const failed = (data.failed as string[]) ?? [];
      const partial = (data.partial as boolean) ?? false;
      const statusMsg = partial
        ? `⚠️ Goal completed (partial): ${artifacts.length} created, ${failed.length} failed`
        : `✅ Goal completed: ${artifacts.length} artifacts created`;
      _state = {
        ..._state,
        learnings: [...getLearnings(), statusMsg],
      };

      // RFC-105: Append completed goal to hierarchical DAG
      if (_currentProjectPath) {
        // Fire-and-forget but log errors (don't block event handling)
        appendCompletedGoalToDag(goalId, goalTitle, artifacts, failed, partial).catch(
          (e) => console.error('Failed to append goal to DAG:', e)
        );
      }

      reloadDag();
      reloadFiles(); // Refresh file tree when goal completes
      break;
    }

    case 'backlog_goal_failed': {
      const error = (data.error as string) ?? 'Unknown error';
      _state = {
        ..._state,
        learnings: [...getLearnings(), `❌ Goal failed: ${error}`],
      };
      reloadDag();
      break;
    }

    case 'backlog_refreshed': {
      _state = {
        ..._state,
        learnings: [...getLearnings(), '🔄 Backlog refreshed'],
      };
      reloadDag();
      break;
    }

    // Gate validation events
    case 'gate_start': {
      const gateId = (data.gate_id as string) ?? '';
      const gateType = (data.gate_type as string) ?? '';
      _state = { ..._state, learnings: [...getLearnings(), `🔒 Gate ${gateId}: ${gateType} starting`] };
      break;
    }
    case 'gate_step': {
      const step = (data.step as string) ?? '';
      const passed = (data.passed as boolean) ?? false;
      _state = { ..._state, learnings: [...getLearnings(), `  ${passed ? '✓' : '✗'} ${step}`] };
      break;
    }
    case 'gate_pass': {
      const gateId = (data.gate_id as string) ?? '';
      _state = { ..._state, learnings: [...getLearnings(), `✅ Gate ${gateId} passed`] };
      break;
    }
    case 'gate_fail': {
      const gateId = (data.gate_id as string) ?? '';
      _state = { ..._state, learnings: [...getLearnings(), `❌ Gate ${gateId} failed`] };
      break;
    }

    // Fix/auto-repair events
    case 'fix_start': {
      _state = { ..._state, learnings: [...getLearnings(), '🔧 Auto-fix starting...'] };
      break;
    }
    case 'fix_attempt': {
      const errorType = (data.error_type as string) ?? '';
      _state = { ..._state, learnings: [...getLearnings(), `  Attempting fix: ${errorType}`] };
      break;
    }
    case 'fix_complete': {
      const totalFixed = (data.total_fixed as number) ?? 0;
      _state = { ..._state, learnings: [...getLearnings(), `✅ Auto-fix complete: ${totalFixed} fixed`] };
      break;
    }
    case 'fix_failed':
    case 'fix_progress': {
      // Absorb silently - fix_complete/escalate will provide summary
      break;
    }

    // Validation cascade events
    case 'validate_start': {
      _state = { ..._state, learnings: [...getLearnings(), '🔍 Validating...'] };
      break;
    }
    case 'validate_error': {
      const file = (data.file as string) ?? '';
      const message = (data.message as string) ?? '';
      _state = { ..._state, learnings: [...getLearnings(), `  ⚠️ ${file}: ${message}`] };
      break;
    }
    case 'validate_pass': {
      _state = { ..._state, learnings: [...getLearnings(), '✅ Validation passed'] };
      break;
    }
    case 'validate_level': {
      // Absorb - too granular for user display
      break;
    }

    // Model/inference events
    case 'model_start': {
      _state = { ..._state, learnings: [...getLearnings(), '🤖 Model thinking...'] };
      break;
    }
    case 'model_complete': {
      const tokensUsed = (data.tokens_used as number) ?? 0;
      if (tokensUsed > 0) {
        _state = { ..._state, learnings: [...getLearnings(), `  ${tokensUsed} tokens`] };
      }
      break;
    }
    case 'model_tokens':
    case 'model_thinking':
    case 'model_heartbeat': {
      // Absorb - too frequent for learnings
      break;
    }

    // Memory lifecycle events
    case 'memory_load':
    case 'memory_loaded':
    case 'memory_new': {
      // Absorb - session start events
      break;
    }
    case 'memory_dead_end': {
      const approach = (data.approach as string) ?? '';
      _state = { ..._state, learnings: [...getLearnings(), `⛔ Dead end: ${approach}`] };
      break;
    }
    case 'memory_checkpoint': {
      _state = { ..._state, learnings: [...getLearnings(), '💾 Memory checkpoint saved'] };
      break;
    }
    case 'memory_saved': {
      _state = { ..._state, learnings: [...getLearnings(), '💾 Memory saved'] };
      break;
    }

    // Informational events
    case 'info': {
      const message = (data.message as string) ?? '';
      if (message) {
        console.debug(`[Sunwell] Info: ${message}`);
      }
      // Absorb - informational message from backend
      break;
    }

    // OODA loop / knowledge events
    case 'orient': {
      const learningsCount = (data.learnings as number) ?? 0;
      const constraintsCount = (data.constraints as number) ?? 0;
      const deadEndsCount = (data.dead_ends as number) ?? 0;
      // Only log if there's meaningful context
      if (learningsCount > 0 || constraintsCount > 0 || deadEndsCount > 0) {
        console.debug(`[Sunwell] Orient: ${learningsCount} learnings, ${constraintsCount} constraints, ${deadEndsCount} dead ends`);
      }
      // Absorb - internal OODA cycle event
      break;
    }

    case 'knowledge_retrieved': {
      const factsCount = (data.facts_count as number) ?? 0;
      const constraintsCount = (data.constraints_count as number) ?? 0;
      const deadEndsCount = (data.dead_ends_count as number) ?? 0;
      const templatesCount = (data.templates_count as number) ?? 0;
      const heuristicsCount = (data.heuristics_count as number) ?? 0;
      const patternsCount = (data.patterns_count as number) ?? 0;
      const totalKnowledge = factsCount + constraintsCount + deadEndsCount + templatesCount + heuristicsCount + patternsCount;
      // Only log if knowledge was retrieved
      if (totalKnowledge > 0) {
        console.debug(`[Sunwell] Knowledge retrieved: ${totalKnowledge} items (${factsCount} facts, ${patternsCount} patterns, ${templatesCount} templates)`);
      }
      // Absorb - internal knowledge retrieval event
      break;
    }

    // Signal events
    case 'signal': {
      const status = (data.status as string) ?? '';
      if (status === 'complete' && data.signals) {
        const signals = data.signals as Record<string, unknown>;
        const route = (signals.planning_route as string) ?? '';
        _state = { ..._state, learnings: [...getLearnings(), `📡 Route: ${route}`] };
      }
      break;
    }
    case 'signal_route': {
      const route = (data.route as string) ?? '';
      _state = { ..._state, learnings: [...getLearnings(), `📡 Routed to: ${route}`] };
      break;
    }

    // Integration verification events
    case 'integration_check_start':
    case 'integration_check_pass':
    case 'integration_check_fail':
    case 'stub_detected':
    case 'orphan_detected':
    case 'wire_task_generated': {
      // Absorb - internal planning events
      break;
    }

    // Planning progress events
    case 'plan_candidate':
    case 'plan_assess':
    case 'plan_expanded':
    case 'plan_discovery_progress': {
      // Absorb - covered by RFC-058 events
      break;
    }

    // Skill compilation events
    case 'skill_compile_start':
    case 'skill_compile_complete':
    case 'skill_compile_cache_hit':
    case 'skill_subgraph_extracted': {
      // Absorb - internal skill system events
      break;
    }

    // ═══════════════════════════════════════════════════════════════
    // RFC-123: CONVERGENCE LOOP EVENTS
    // ═══════════════════════════════════════════════════════════════

    case 'convergence_start': {
      const files = (data.files as string[]) ?? [];
      const gates = (data.gates as string[]) ?? [];
      const maxIterations = (data.max_iterations as number) ?? 5;
      _state = {
        ..._state,
        convergence: {
          status: 'running',
          iterations: [],
          max_iterations: maxIterations,
          enabled_gates: gates,
          current_iteration: 0,
        },
      };
      console.debug(`[Sunwell] Convergence started: ${files.length} files, gates: ${gates.join(', ')}`);
      break;
    }

    case 'convergence_iteration_start': {
      const iteration = (data.iteration as number) ?? 1;
      if (_state.convergence) {
        _state = {
          ..._state,
          convergence: {
            ..._state.convergence,
            current_iteration: iteration,
          },
        };
      }
      break;
    }

    case 'convergence_iteration_complete': {
      const iteration = (data.iteration as number) ?? 1;
      const allPassed = (data.all_passed as boolean) ?? false;
      const totalErrors = (data.total_errors as number) ?? 0;
      const gateResults = (data.gate_results as Array<{ gate: string; passed: boolean; errors: number }>) ?? [];
      if (_state.convergence) {
        const newIteration = {
          iteration,
          all_passed: allPassed,
          total_errors: totalErrors,
          gate_results: gateResults,
        };
        _state = {
          ..._state,
          convergence: {
            ..._state.convergence,
            iterations: [..._state.convergence.iterations, newIteration],
          },
        };
      }
      break;
    }

    case 'convergence_fixing': {
      // Track that we're in fixing phase - no state change needed
      const errorCount = (data.error_count as number) ?? 0;
      console.debug(`[Sunwell] Convergence fixing ${errorCount} errors`);
      break;
    }

    case 'convergence_stable': {
      const iterations = (data.iterations as number) ?? 0;
      const durationMs = (data.duration_ms as number) ?? 0;
      if (_state.convergence) {
        _state = {
          ..._state,
          convergence: {
            ..._state.convergence,
            status: 'stable',
            duration_ms: durationMs,
          },
        };
      }
      console.debug(`[Sunwell] Convergence stable after ${iterations} iteration(s)`);
      break;
    }

    case 'convergence_timeout': {
      if (_state.convergence) {
        _state = {
          ..._state,
          convergence: {
            ..._state.convergence,
            status: 'timeout',
          },
        };
      }
      break;
    }

    case 'convergence_stuck': {
      const repeatedErrors = (data.repeated_errors as string[]) ?? [];
      if (_state.convergence) {
        _state = {
          ..._state,
          convergence: {
            ..._state.convergence,
            status: 'stuck',
          },
        };
      }
      console.warn(`[Sunwell] Convergence stuck on: ${repeatedErrors.join(', ')}`);
      break;
    }

    case 'convergence_max_iterations': {
      if (_state.convergence) {
        _state = {
          ..._state,
          convergence: {
            ..._state.convergence,
            status: 'escalated',
          },
        };
      }
      break;
    }

    case 'convergence_budget_exceeded': {
      const tokensUsed = (data.tokens_used as number) ?? 0;
      if (_state.convergence) {
        _state = {
          ..._state,
          convergence: {
            ..._state.convergence,
            status: 'escalated',
            tokens_used: tokensUsed,
          },
        };
      }
      break;
    }

    // ═══════════════════════════════════════════════════════════════
    // RFC-130: AGENT CONSTELLATION (AUTONOMOUS) EVENTS
    // ═══════════════════════════════════════════════════════════════

    // Dynamic Agent Spawning
    case 'specialist_spawned': {
      const specialistId = (data.specialist_id as string) ?? '';
      const role = (data.role as string) ?? '';
      const goal = (data.goal as string) ?? '';
      _state = {
        ..._state,
        learnings: [...getLearnings(), `🌟 Spawned specialist: ${role} → "${goal.slice(0, 50)}..."`],
      };
      console.debug(`[Sunwell] Specialist spawned: ${specialistId} (${role})`);
      break;
    }

    case 'specialist_completed': {
      const specialistId = (data.specialist_id as string) ?? '';
      const status = (data.status as string) ?? '';
      const statusIcon = status === 'completed' ? '✅' : status === 'failed' ? '❌' : '⚠️';
      _state = {
        ..._state,
        learnings: [...getLearnings(), `${statusIcon} Specialist ${specialistId} ${status}`],
      };
      break;
    }

    // Semantic Checkpoints
    case 'checkpoint_found': {
      const phase = (data.phase as string) ?? '';
      _state = {
        ..._state,
        learnings: [...getLearnings(), `📍 Found checkpoint at phase: ${phase}`],
      };
      break;
    }

    case 'checkpoint_saved': {
      const phase = (data.phase as string) ?? '';
      _state = {
        ..._state,
        learnings: [...getLearnings(), `💾 Checkpoint saved: ${phase}`],
      };
      break;
    }

    case 'checkpoint_restored': {
      const phase = (data.phase as string) ?? '';
      _state = {
        ..._state,
        learnings: [...getLearnings(), `🔄 Resumed from checkpoint: ${phase}`],
      };
      break;
    }

    case 'phase_complete': {
      const phase = (data.phase as string) ?? '';
      const summary = (data.summary as string) ?? '';
      _state = {
        ..._state,
        learnings: [...getLearnings(), `✅ Phase ${phase} complete${summary ? `: ${summary}` : ''}`],
      };
      break;
    }

    // Adaptive Guardrails
    case 'autonomous_action_blocked': {
      const action = (data.action_type as string) ?? '';
      const reason = (data.reason as string) ?? '';
      _state = {
        ..._state,
        learnings: [...getLearnings(), `🛡️ Blocked: ${action} — ${reason}`],
      };
      break;
    }

    case 'guard_evolution_suggested': {
      const ruleId = (data.rule_id as string) ?? '';
      const description = (data.description as string) ?? '';
      _state = {
        ..._state,
        learnings: [...getLearnings(), `💡 Guard evolution: ${ruleId} — ${description}`],
      };
      break;
    }

    // Autonomous Session Lifecycle
    case 'autonomous_session_start': {
      const sessionId = (data.session_id as string) ?? '';
      const goal = (data.goal as string) ?? '';
      _state = {
        ..._state,
        learnings: [...getLearnings(), `🚀 Autonomous session: ${goal.slice(0, 60)}...`],
      };
      console.debug(`[Sunwell] Autonomous session started: ${sessionId}`);
      break;
    }

    case 'autonomous_session_complete': {
      const success = (data.success as boolean) ?? false;
      const durationS = (data.duration_s as number) ?? 0;
      const icon = success ? '✅' : '⚠️';
      _state = {
        ..._state,
        learnings: [...getLearnings(), `${icon} Autonomous session complete (${durationS.toFixed(1)}s)`],
      };
      break;
    }

    default: {
      // Log unhandled events so we catch future drift
      console.warn(`[Sunwell] Unhandled event type: ${type}`, data);
    }
  }
}
