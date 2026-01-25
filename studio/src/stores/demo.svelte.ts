/**
 * Demo Store — Real backend integration for Prism Principle demo (RFC-095)
 *
 * Manages demo state and communicates with the Python backend via HTTP REST + WebSocket
 * for PARALLEL LLM execution with real-time streaming to both code panes.
 */

import { apiGet, apiPost, onEvent } from '$lib/socket';

// ═══════════════════════════════════════════════════════════════
// TYPES — Match Python `sunwell demo --json` output exactly
// ═══════════════════════════════════════════════════════════════

export interface DemoTask {
  name: string;
  prompt: string;
  /** Only present when listing tasks, not in comparison result */
  expected_features?: string[];
}

/** Token usage statistics */
export interface TokenUsage {
  prompt: number;
  completion: number;
  total: number;
}

/** Python flattens score + result into one object */
export interface DemoMethodOutput {
  score: number;
  lines: number;
  time_ms: number;
  features: Record<string, boolean>;
  iterations?: number;
  /** Code only present in verbose mode */
  code?: string;
  /** Token usage statistics */
  tokens?: TokenUsage;
}

// ═══════════════════════════════════════════════════════════════
// BREAKDOWN TYPES — Show what each Sunwell component contributed
// ═══════════════════════════════════════════════════════════════

export interface LensBreakdown {
  name: string;
  detected: boolean;
  heuristics_applied: string[];
}

export interface PromptBreakdown {
  type: string;
  requirements_added: string[];
}

export interface JudgeBreakdown {
  score: number;
  issues: string[];
  passed: boolean;
}

export interface ResonanceBreakdown {
  triggered: boolean;
  /** Did refinement actually improve the code? */
  succeeded: boolean;
  iterations: number;
  improvements: string[];
}

export interface ResultBreakdown {
  final_score: number;
  features_achieved: string[];
  features_missing: string[];
}

/** Complete component breakdown — shows what each Sunwell feature contributed */
export interface ComponentBreakdown {
  lens: LensBreakdown;
  prompt: PromptBreakdown;
  judge: JudgeBreakdown;
  resonance: ResonanceBreakdown;
  result: ResultBreakdown;
}

export interface DemoComparison {
  model: string;
  task: DemoTask;
  single_shot: DemoMethodOutput;
  sunwell: DemoMethodOutput;
  improvement_percent: number;
  /** Unique ID to fetch code files */
  run_id?: string;
  /** Component breakdown showing what each Sunwell feature contributed */
  breakdown?: ComponentBreakdown;
}

export interface DemoProgress {
  phase: string;
  message: string;
  progress: number;
}

export interface DemoInput {
  task?: string;
  model?: string;
  provider?: string;
}

export type DemoPhase = 'ready' | 'generating' | 'judging' | 'refining' | 'revealed' | 'error';

// ═══════════════════════════════════════════════════════════════
// TYPE GUARDS
// ═══════════════════════════════════════════════════════════════

function isDemoComparison(data: unknown): data is DemoComparison {
  if (typeof data !== 'object' || data === null) return false;
  const d = data as Record<string, unknown>;
  return typeof d.model === 'string' &&
    typeof d.task === 'object' &&
    typeof d.single_shot === 'object' &&
    typeof d.sunwell === 'object' &&
    typeof d.improvement_percent === 'number';
}

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

let _phase = $state<DemoPhase>('ready');
let _progress = $state(0);
let _message = $state('');
let _error = $state<string | null>(null);
let _comparison = $state<DemoComparison | null>(null);
let _availableTasks = $state<DemoTask[]>([]);

// Streaming code buffers (updated in real-time)
let _singleShotCodeStream = $state('');
let _sunwellCodeStream = $state('');
let _sunwellPhase = $state<'generating' | 'judging' | 'refining'>('generating');

// Final code loaded from files (clean, no escaping issues)
let _singleShotCodeFile = $state('');
let _sunwellCodeFile = $state('');

// Default task if none loaded
const DEFAULT_TASK: DemoTask = {
  name: 'divide',
  prompt: 'Write a Python function to divide two numbers',
  expected_features: ['type_hints', 'docstring', 'zero_division_handling', 'type_validation'],
};

let _currentTask = $state<DemoTask>(DEFAULT_TASK);
let _currentModel = $state('ollama:llama3.2:3b');

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const demo = {
  // State getters
  get phase() { return _phase; },
  get progress() { return _progress; },
  get message() { return _message; },
  get error() { return _error; },
  get comparison() { return _comparison; },
  get availableTasks() { return _availableTasks; },
  get currentTask() { return _currentTask; },
  get currentModel() { return _currentModel; },

  // Streaming state
  get sunwellPhase() { return _sunwellPhase; },
  
  // Computed
  get isRunning() { return _phase !== 'ready' && _phase !== 'revealed' && _phase !== 'error'; },
  /** The actual model used (from backend response) */
  get actualModel() { return _comparison?.model ?? _currentModel; },
  
  /** 
   * Code for display — uses file-loaded code when available (clean, no escaping),
   * falls back to streaming buffer during generation.
   */
  get singleShotCode() { 
    // Prefer file-loaded code (no escaping issues)
    if (_phase === 'revealed' && _singleShotCodeFile) {
      return _singleShotCodeFile;
    }
    return _singleShotCodeStream || '';
  },
  get sunwellCode() { 
    // Prefer file-loaded code (no escaping issues)
    if (_phase === 'revealed' && _sunwellCodeFile) {
      return _sunwellCodeFile;
    }
    return _sunwellCodeStream || '';
  },
  
  /** Score is embedded in the method output (flattened structure) */
  get singleShotScore() { return _comparison?.single_shot ?? null; },
  get sunwellScore() { return _comparison?.sunwell ?? null; },
  get improvementPercent() { return _comparison?.improvement_percent ?? 0; },
  
  /** Component breakdown — what each Sunwell feature contributed */
  get breakdown() { return _comparison?.breakdown ?? null; },
};

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Load available demo tasks from backend.
 */
export async function loadTasks(): Promise<void> {
  try {
    const tasks = await apiGet<DemoTask[]>('/api/demo/tasks');
    _availableTasks = tasks;
    if (_availableTasks.length > 0 && !_currentTask) {
      _currentTask = _availableTasks[0];
    }
  } catch (e) {
    console.error('Failed to load demo tasks:', e);
    // Use default task
    _availableTasks = [DEFAULT_TASK];
  }
}

/**
 * Set the current demo task.
 */
export function setTask(task: DemoTask): void {
  _currentTask = task;
}

/**
 * Set the current model.
 */
export function setModel(model: string): void {
  _currentModel = model;
}

/**
 * Run the demo — PARALLEL execution with real-time streaming.
 *
 * Uses the Python backend for:
 * - Parallel execution of single-shot and Sunwell (2x faster)
 * - Real-time code streaming to both panes
 * - Phase updates as Sunwell progresses through judge/refine
 */
export async function runDemo(): Promise<void> {
  _phase = 'generating';
  _progress = 0;
  _message = 'Starting parallel demo...';
  _error = null;
  _comparison = null;
  _singleShotCodeStream = '';
  _sunwellCodeStream = '';
  _sunwellPhase = 'generating';

  // Parse model string (e.g., "ollama:llama3.2:3b" -> provider: "ollama", model: "llama3.2:3b")
  const [provider, ...modelParts] = _currentModel.split(':');
  const model = modelParts.join(':');

  const input: DemoInput = {
    task: _currentTask.name,
    model: model || undefined,
    provider: provider || undefined,
  };

  try {
    // Subscribe to demo events via WebSocket
    const unsubscribe = onEvent((event) => {
      if (event.type === 'demo_start') {
        _message = `Running on ${event.data?.model ?? 'model'}...`;
        _progress = 5;
      } else if (event.type === 'demo_chunk') {
        const { method, content } = event.data as { method: string; content: string };
        if (method === 'single_shot') {
          _singleShotCodeStream += content;
        } else if (method === 'sunwell') {
          _sunwellCodeStream += content;
        }
        const totalChars = _singleShotCodeStream.length + _sunwellCodeStream.length;
        _progress = Math.min(80, 10 + totalChars / 20);
      } else if (event.type === 'demo_phase') {
        const { phase } = event.data as { phase: string };
        if (phase === 'generating') {
          _sunwellPhase = 'generating';
          _message = 'Generating initial code...';
        } else if (phase === 'judging') {
          _sunwellPhase = 'judging';
          _phase = 'judging';
          _message = 'Judge evaluating quality...';
          _progress = 60;
        } else if (phase === 'refining') {
          _sunwellPhase = 'refining';
          _phase = 'refining';
          _message = 'Resonance refining...';
          _progress = 75;
        }
      } else if (event.type === 'demo_complete') {
        if (isDemoComparison(event.data)) {
          _comparison = event.data;
        } else {
          console.error('Invalid demo_complete data:', event.data);
          _error = 'Invalid response format';
          _phase = 'error';
          unsubscribe();
          return;
        }
        _progress = 95;
        _message = 'Loading code...';
        // Load code from files BEFORE revealing
        if (_comparison.run_id) {
          loadCodeFiles(_comparison.run_id).then(() => {
            _phase = 'revealed';
            _progress = 100;
            _message = 'Demo complete!';
          });
        } else {
          _phase = 'revealed';
          _progress = 100;
          _message = 'Demo complete!';
        }
        unsubscribe();
      } else if (event.type === 'demo_error') {
        _error = (event.data as { message: string }).message;
        _phase = 'error';
        _message = 'Demo failed';
        unsubscribe();
      }
    });

    // Start demo via REST API
    const result = await apiPost<DemoComparison>('/api/demo/run', input);
    
    // Final state update (in case events didn't fire)
    const phase = _phase as DemoPhase; // Re-read phase after async
    if (phase !== 'revealed' && phase !== 'error') {
      _comparison = result;
      _progress = 95;
      _message = 'Loading code...';
      
      // Load code from files BEFORE setting phase to revealed
      // This avoids a race condition where the UI renders with empty code
      if (result.run_id) {
        await loadCodeFiles(result.run_id);
      }
      
      // Now reveal with code loaded
      _phase = 'revealed';
      _progress = 100;
      _message = 'Demo complete!';
    }
  } catch (e) {
    _phase = 'error';
    _error = e instanceof Error ? e.message : String(e);
    _message = 'Demo failed';
    console.error('Demo failed:', e);
  }
}

/**
 * Load code from files (avoids JSON escaping issues).
 */
async function loadCodeFiles(runId: string): Promise<void> {
  // Use the same API base as other calls (Python server on :8080 in dev)
  const API_BASE = import.meta.env.VITE_API_BASE || (import.meta.env.DEV ? 'http://127.0.0.1:8080' : '');
  
  try {
    const [singleShotRes, sunwellRes] = await Promise.all([
      fetch(`${API_BASE}/api/demo/code/${runId}/single_shot`),
      fetch(`${API_BASE}/api/demo/code/${runId}/sunwell`),
    ]);

    if (singleShotRes.ok) {
      _singleShotCodeFile = await singleShotRes.text();
    }
    if (sunwellRes.ok) {
      _sunwellCodeFile = await sunwellRes.text();
    }
  } catch (e) {
    console.error('Failed to load code files:', e);
    // Fall back to streaming buffers (already in state)
  }
}

/**
 * Reset the demo to ready state.
 */
export function reset(): void {
  _phase = 'ready';
  _progress = 0;
  _message = '';
  _error = null;
  _comparison = null;
  _singleShotCodeStream = '';
  _sunwellCodeStream = '';
  _singleShotCodeFile = '';
  _sunwellCodeFile = '';
  _sunwellPhase = 'generating';
}

// ═══════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════

// Load tasks on import
loadTasks();
