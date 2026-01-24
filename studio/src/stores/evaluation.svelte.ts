/**
 * Evaluation Store — Full-Stack Metrics (RFC-098)
 *
 * Manages evaluation state and communicates with the Python backend via HTTP REST
 * for comparing single-shot generation against the full Sunwell cognitive architecture.
 */

import { apiGet, apiPost, onEvent } from '$lib/socket';

// ═══════════════════════════════════════════════════════════════
// TYPES — Match Python `sunwell eval` output
// ═══════════════════════════════════════════════════════════════

export interface EvalTask {
  id: string;
  name: string;
  prompt: string;
  available_tools?: string[];
  expected_patterns?: string[];
}

export interface FullStackScore {
  structure: number;
  runnable: number;
  features: number;
  quality: number;
  total: number;
}

export interface SingleShotResult {
  files: string[];
  time_seconds: number;
  turns: number;
  input_tokens: number;
  output_tokens: number;
}

export interface SunwellResult {
  files: string[];
  time_seconds: number;
  turns: number;
  input_tokens: number;
  output_tokens: number;
  lens_used?: string;
  judge_scores: number[];
  resonance_iterations: number;
}

export interface EvaluationRun {
  id: string;
  timestamp: string;
  model: string;
  task_id: string;
  task_prompt: string;
  single_shot?: SingleShotResult;
  sunwell?: SunwellResult;
  single_shot_score?: FullStackScore;
  sunwell_score?: FullStackScore;
  improvement_percent: number;
}

export interface EvalInput {
  task?: string;
  model?: string;
  provider?: string;
  lens?: string;
}

export interface TaskStats {
  runs: number;
  avg_improvement: number;
  sunwell_avg_score: number;
  single_shot_avg_score: number;
}

export interface EvalStats {
  total_runs: number;
  avg_improvement: number;
  sunwell_wins: number;
  single_shot_wins: number;
  ties: number;
  by_task: Record<string, TaskStats>;
}

export type EvalPhase =
  | 'ready'
  | 'running_single'
  | 'running_sunwell'
  | 'scoring'
  | 'complete'
  | 'error';

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

let _phase = $state<EvalPhase>('ready');
let _progress = $state(0);
let _message = $state('');
let _error = $state<string | null>(null);
let _currentRun = $state<EvaluationRun | null>(null);
let _history = $state<EvaluationRun[]>([]);
let _stats = $state<EvalStats | null>(null);
let _availableTasks = $state<EvalTask[]>([]);

// Track files created in real-time
let _singleShotFiles = $state<string[]>([]);
let _sunwellFiles = $state<string[]>([]);

// Current configuration
let _currentTask = $state<EvalTask | null>(null);
let _currentModel = $state('ollama:llama3.2:3b');
let _currentLens = $state<string | null>(null);

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const evaluation = {
  // State getters
  get phase() { return _phase; },
  get progress() { return _progress; },
  get message() { return _message; },
  get error() { return _error; },
  get currentRun() { return _currentRun; },
  get history() { return _history; },
  get stats() { return _stats; },
  get availableTasks() { return _availableTasks; },
  get currentTask() { return _currentTask; },
  get currentModel() { return _currentModel; },
  get currentLens() { return _currentLens; },

  // Real-time tracking
  get singleShotFiles() { return _singleShotFiles; },
  get sunwellFiles() { return _sunwellFiles; },

  // Computed
  get isRunning() {
    return _phase !== 'ready' && _phase !== 'complete' && _phase !== 'error';
  },

  // Score accessors
  get singleShotScore() { return _currentRun?.single_shot_score ?? null; },
  get sunwellScore() { return _currentRun?.sunwell_score ?? null; },
  get improvementPercent() { return _currentRun?.improvement_percent ?? 0; },

  // Result comparison
  get sunwellWins() {
    if (!_currentRun?.single_shot_score || !_currentRun?.sunwell_score) return false;
    return _currentRun.sunwell_score.total > _currentRun.single_shot_score.total;
  },
};

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Load available evaluation tasks from backend.
 */
export async function loadTasks(): Promise<void> {
  try {
    const tasks = await apiGet<EvalTask[]>('/api/eval/tasks');
    _availableTasks = tasks;
    if (tasks.length > 0 && !_currentTask) {
      _currentTask = tasks[0];
    }
  } catch (e) {
    console.error('Failed to load eval tasks:', e);
    _availableTasks = [];
  }
}

/**
 * Load evaluation history.
 */
export async function loadHistory(limit = 20): Promise<void> {
  try {
    const history = await apiGet<EvaluationRun[]>(`/api/eval/history?limit=${limit}`);
    _history = history;
  } catch (e) {
    console.error('Failed to load eval history:', e);
    _history = [];
  }
}

/**
 * Load evaluation statistics.
 */
export async function loadStats(): Promise<void> {
  try {
    const stats = await apiGet<EvalStats>('/api/eval/stats');
    _stats = stats;
  } catch (e) {
    console.error('Failed to load eval stats:', e);
    _stats = null;
  }
}

/**
 * Set the current evaluation task.
 */
export function setTask(task: EvalTask): void {
  _currentTask = task;
}

/**
 * Set the current model.
 */
export function setModel(model: string): void {
  _currentModel = model;
}

/**
 * Set the lens to use (or null for auto-detection).
 */
export function setLens(lens: string | null): void {
  _currentLens = lens;
}

/**
 * Run evaluation with streaming progress.
 *
 * Compares single-shot generation against Sunwell full-stack
 * with real-time file creation updates.
 */
export async function runEvaluation(): Promise<void> {
  if (!_currentTask) {
    _error = 'No task selected';
    _phase = 'error';
    return;
  }

  _phase = 'running_single';
  _progress = 0;
  _message = 'Starting evaluation...';
  _error = null;
  _currentRun = null;
  _singleShotFiles = [];
  _sunwellFiles = [];

  // Parse model string (e.g., "ollama:llama3.2:3b" -> provider: "ollama", model: "llama3.2:3b")
  const [provider, ...modelParts] = _currentModel.split(':');
  const model = modelParts.join(':');

  const input: EvalInput = {
    task: _currentTask.id,
    model: model || undefined,
    provider: provider || undefined,
    lens: _currentLens ?? undefined,
  };

  try {
    // Subscribe to eval events via WebSocket
    const unsubscribe = onEvent((event) => {
      if (event.type === 'eval_start') {
        _message = `Evaluating on ${event.data?.model ?? 'model'}...`;
        _progress = 5;
      } else if (event.type === 'eval_phase') {
        const { method, phase, message } = event.data as {
          method: string;
          phase: string;
          message: string;
        };
        if (method === 'single_shot') {
          _phase = 'running_single';
          _progress = 10 + Math.min(30, _singleShotFiles.length * 5);
        } else if (method === 'sunwell') {
          _phase = 'running_sunwell';
          _progress = 50 + Math.min(30, _sunwellFiles.length * 5);
        }
        if (phase === 'scoring') {
          _phase = 'scoring';
          _progress = 90;
        }
        _message = message;
      } else if (event.type === 'eval_file_created') {
        const { method, path } = event.data as { method: string; path: string };
        if (method === 'single_shot') {
          _singleShotFiles = [..._singleShotFiles, path];
        } else if (method === 'sunwell') {
          _sunwellFiles = [..._sunwellFiles, path];
        }
      } else if (event.type === 'eval_complete') {
        _currentRun = event.data as EvaluationRun;
        _phase = 'complete';
        _progress = 100;
        _message = 'Evaluation complete!';
        loadHistory();
        loadStats();
        unsubscribe();
      } else if (event.type === 'eval_error') {
        _error = (event.data as { message: string }).message;
        _phase = 'error';
        _message = 'Evaluation failed';
        unsubscribe();
      }
    });

    // Start evaluation via REST API
    const result = await apiPost<EvaluationRun>('/api/eval/run', input);

    // Final state update (in case events didn't fire)
    if (_phase !== 'complete' && _phase !== 'error') {
      _currentRun = result;
      _phase = 'complete';
      _progress = 100;
      _message = 'Evaluation complete!';
    }
  } catch (e) {
    _phase = 'error';
    _error = e instanceof Error ? e.message : String(e);
    _message = 'Evaluation failed';
    console.error('Evaluation failed:', e);
  }
}

/**
 * Reset the evaluation to ready state.
 */
export function reset(): void {
  _phase = 'ready';
  _progress = 0;
  _message = '';
  _error = null;
  _currentRun = null;
  _singleShotFiles = [];
  _sunwellFiles = [];
}

// ═══════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════

// Load tasks on import
loadTasks();
