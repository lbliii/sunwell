/**
 * Agent Store — manages Sunwell agent state and communication (Svelte 5 runes)
 */

import { AgentStatus, TaskStatus, PlanningPhase } from '$lib/constants';
import type { AgentState, AgentEvent, Task, Concept, ConceptCategory, PlanCandidate } from '$lib/types';
import { updateNode, completeNode } from './dag.svelte';
import { setActiveLens } from './lens.svelte';

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
};

let _state = $state<AgentState>({ ...initialState });
let eventUnlisten: (() => void) | null = null;
let stopUnlisten: (() => void) | null = null;

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
// EXPORTS
// ═══════════════════════════════════════════════════════════════

const RUNNING_STATUSES: AgentStatus[] = [AgentStatus.STARTING, AgentStatus.PLANNING, AgentStatus.RUNNING];

export const agent = {
  get status() { return _state.status; },
  get goal() { return _state.goal; },
  get tasks() { return _state.tasks; },
  get currentTaskIndex() { return _state.currentTaskIndex; },
  get totalTasks() { return _state.totalTasks; },
  get startTime() { return _state.startTime; },
  get endTime() { return _state.endTime; },
  get error() { return _state.error; },
  get learnings() { return _state.learnings; },
  get concepts() { return _state.concepts; },
  get planningCandidates() { return _state.planningCandidates; },
  get selectedCandidate() { return _state.selectedCandidate; },
  get refinementRounds() { return _state.refinementRounds; },
  get planningProgress() { return _state.planningProgress; },
  // Computed
  get isRunning() { return RUNNING_STATUSES.includes(_state.status); },
  get isDone() { return _state.status === AgentStatus.DONE; },
  get hasError() { return _state.status === AgentStatus.ERROR; },
  get progress() {
    // Progress based on actual tasks seen, not planned total
    // This handles incremental builds where fewer tasks run
    const completed = _state.tasks.filter(t => t.status === TaskStatus.COMPLETE).length;
    const failed = _state.tasks.filter(t => t.status === TaskStatus.FAILED).length;
    const total = _state.tasks.length;
    if (total === 0) return _state.status === AgentStatus.DONE ? 100 : 0;
    return Math.round(((completed + failed) / total) * 100);
  },
  get duration() {
    return !_state.startTime ? 0 : Math.round(((_state.endTime ?? Date.now()) - _state.startTime) / 1000);
  },
  get completedTasks() { return _state.tasks.filter(t => t.status === TaskStatus.COMPLETE).length; },
  get failedTasks() { return _state.tasks.filter(t => t.status === TaskStatus.FAILED).length; },
  /** Number of planned artifacts that were skipped (incremental builds) */
  get skippedTasks() { return Math.max(0, _state.totalTasks - _state.tasks.length); },
};

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Run a goal with optional lens selection (RFC-064).
 * 
 * @param goal - The goal to execute
 * @param projectPath - Optional project path
 * @param lens - Optional explicit lens name (e.g., "coder", "tech-writer")
 * @param autoLens - Whether to auto-detect lens based on goal (default: true)
 */
export async function runGoal(
  goal: string,
  projectPath?: string,
  lens?: string | null,
  autoLens?: boolean,
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
    const { invoke } = await import('@tauri-apps/api/core');
    _state = { ...initialState, status: AgentStatus.STARTING, goal, startTime: Date.now() };
    await setupEventListeners();
    
    // RFC-064: Pass lens selection to backend
    const result = await invoke<{ success: boolean; message: string; workspace_path: string }>(
      'run_goal',
      {
        goal,
        projectPath,
        lens: lens ?? null,
        autoLens: autoLens ?? true,
      },
    );
    
    if (!result.success) { _state = { ..._state, status: AgentStatus.ERROR, error: result.message }; return null; }
    _state = { ..._state, status: AgentStatus.PLANNING };
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
    _state = { ..._state, tasks: _state.tasks.map((t, idx) => idx === i ? { ...t, status: TaskStatus.RUNNING, progress: 0 } : t), currentTaskIndex: i };
    for (let p = 0; p <= 100; p += 25) { await sleep(100 + Math.random() * 150); _state = { ..._state, tasks: _state.tasks.map((t, idx) => idx === i ? { ...t, progress: p } : t) }; }
    _state = { ..._state, tasks: _state.tasks.map((t, idx) => idx === i ? { ...t, status: TaskStatus.COMPLETE, progress: 100 } : t) };
    await sleep(150);
  }
  const demoLearnings = ['Detected Flask web framework', 'Using SQLAlchemy for ORM', 'pytest available for testing'];
  const demoConcepts: Concept[] = demoLearnings.flatMap(extractConcepts);
  _state = { ..._state, status: AgentStatus.DONE, endTime: Date.now(), learnings: demoLearnings, concepts: deduplicateConcepts(demoConcepts) };
  return true;
}

function sleep(ms: number): Promise<void> { return new Promise(resolve => setTimeout(resolve, ms)); }

export async function stopAgent(): Promise<void> {
  if (DEMO_MODE) { cleanup(); _state = { ..._state, status: AgentStatus.IDLE, endTime: Date.now() }; return; }
  try {
    const { invoke } = await import('@tauri-apps/api/core');
    await invoke('stop_agent');
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
    const { listen } = await import('@tauri-apps/api/event');
    eventUnlisten = await listen<AgentEvent>('agent-event', (event) => { handleAgentEvent(event.payload); });
    stopUnlisten = await listen('agent-stopped', () => { if (_state.status !== AgentStatus.ERROR) { _state = { ..._state, status: AgentStatus.DONE, endTime: Date.now() }; } });
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
      for (const candidate of _state.planningCandidates) {
        if (candidate != null) candidateMap.set(candidate.id, candidate);
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
      for (const candidate of _state.planningCandidates) {
        if (candidate != null) candidateMap.set(candidate.id, candidate);
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
      _state = { ..._state, planningProgress: { phase: PlanningPhase.REFINING, current_candidates: round, total_candidates: totalRounds }, refinementRounds: [..._state.refinementRounds, { round, current_score: currentScore, improvements_identified: improvementsIdentified, improved: false }] };
      break;
    }

    case 'plan_refine_attempt': {
      const round = (data.round as number) ?? 0;
      const improvementsApplied = (data.improvements_applied as string[]) ?? [];
      const rounds = [..._state.refinementRounds];
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
      const rounds = [..._state.refinementRounds];
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
      const selected = _state.planningCandidates.find(c => c.id === selectedId) ?? null;
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
      const existingIndex = _state.tasks.findIndex(t => t.id === taskId);
      if (existingIndex >= 0) {
        const tasks = [..._state.tasks]; tasks[existingIndex] = { ...tasks[existingIndex], status: TaskStatus.RUNNING };
        _state = { ..._state, tasks, currentTaskIndex: existingIndex };
      } else {
        const newTask: Task = { id: taskId, description, status: TaskStatus.RUNNING, progress: 0 };
        _state = { ..._state, tasks: [..._state.tasks, newTask], currentTaskIndex: _state.tasks.length };
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
      const taskIndex = _state.tasks.findIndex(t => t.id === taskId);
      if (taskIndex >= 0) {
        const tasks = [..._state.tasks]; tasks[taskIndex] = { ...tasks[taskIndex], progress: progressVal };
        _state = { ..._state, tasks };
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
      const tasks = _state.tasks.map(t => t.id === taskId ? { ...t, status: TaskStatus.COMPLETE, progress: 100, duration_ms: durationMs } : t);
      _state = { ..._state, tasks };
      completeNode(taskId);
      break;
    }

    case 'task_failed': {
      const taskId = data.task_id as string;
      if (!taskId) {
        console.error('[Sunwell] task_failed missing required task_id');
        break;
      }
      const tasks = _state.tasks.map(t => t.id === taskId ? { ...t, status: TaskStatus.FAILED } : t);
      _state = { ..._state, tasks };
      updateNode(taskId, { status: 'failed' });
      break;
    }

    case 'memory_learning': {
      const fact = (data.fact as string) ?? '';
      if (fact) {
        const newConcepts = extractConcepts(fact);
        _state = { ..._state, learnings: [..._state.learnings, fact], concepts: deduplicateConcepts([..._state.concepts, ...newConcepts]) };
      }
      break;
    }

    case 'complete': {
      const tasksCompleted = (data.tasks_completed as number) ?? (data.completed as number) ?? 0;
      const tasksFailed = (data.tasks_failed as number) ?? (data.failed as number) ?? 0;
      const hasAnomaly = _state.tasks.length === 0 && tasksCompleted > 0;
      if (hasAnomaly) {
        console.warn(`[Sunwell] Agent completed with ${tasksCompleted} artifacts but no task_start events`);
        const syntheticTasks: Task[] = [];
        for (let i = 0; i < tasksCompleted; i++) syntheticTasks.push({ id: `completed-${i}`, description: `Completed artifact ${i + 1}`, status: TaskStatus.COMPLETE, progress: 100 });
        for (let i = 0; i < tasksFailed; i++) syntheticTasks.push({ id: `failed-${i}`, description: `Failed artifact ${i + 1}`, status: TaskStatus.FAILED, progress: 0 });
        _state = { ..._state, status: AgentStatus.DONE, endTime: Date.now(), tasks: syntheticTasks.length > 0 ? syntheticTasks : _state.tasks, totalTasks: _state.totalTasks > 0 ? _state.totalTasks : tasksCompleted + tasksFailed };
      } else {
        _state = { ..._state, status: AgentStatus.DONE, endTime: Date.now() };
      }
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
      _state = { ..._state, status: AgentStatus.ERROR, error: `Escalated: ${reason}${message ? ` - ${message}` : ''}` };
      break;
    }

    // RFC-064: Lens events
    case 'lens_selected': {
      const name = (data.name as string) ?? '';
      const reason = (data.reason as string) ?? '';
      setActiveLens(name);
      _state = {
        ..._state,
        learnings: [..._state.learnings, `Using lens: ${name} (${reason})`],
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
        learnings: [..._state.learnings, briefingInfo],
      };
      break;
    }

    case 'briefing_saved': {
      const status = (data.status as string) ?? '';
      const tasksCompleted = (data.tasks_completed as number) ?? 0;
      _state = {
        ..._state,
        learnings: [..._state.learnings, `📋 Briefing saved: ${status} (${tasksCompleted} tasks)`],
      };
      break;
    }

    case 'prefetch_start': {
      const briefing = (data.briefing as string) ?? '';
      _state = {
        ..._state,
        learnings: [..._state.learnings, `🔄 Prefetch starting for: ${briefing}`],
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
        learnings: [..._state.learnings, `✅ Prefetch complete: ${filesLoaded} files, ${learningsLoaded} learnings.${skills}`],
      };
      break;
    }

    case 'prefetch_timeout': {
      const error = (data.error as string) ?? '';
      const msg = error ? `⏱️ Prefetch timed out: ${error}` : '⏱️ Prefetch timed out (proceeding without warm context)';
      _state = {
        ..._state,
        learnings: [..._state.learnings, msg],
      };
      break;
    }

    case 'lens_suggested': {
      const suggested = (data.suggested as string) ?? '';
      const reason = (data.reason as string) ?? '';
      _state = {
        ..._state,
        learnings: [..._state.learnings, `🎯 Lens suggested: ${suggested} (${reason})`],
      };
      break;
    }
  }
}
