/**
 * Workflow Store — Autonomous workflow execution state (RFC-086)
 *
 * RFC-113: Migrated from Tauri invoke to HTTP API.
 *
 * Manages workflow chains, execution state, and progress updates.
 */

import { apiGet, apiPost } from '$lib/socket';
import { onEvent } from '$lib/socket';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export type WorkflowTier = 'fast' | 'light' | 'full';
export type IntentCategory = 'creation' | 'validation' | 'transformation' | 'refinement' | 'information';
export type StepStatus = 'pending' | 'running' | 'success' | 'warning' | 'error' | 'skipped';
export type WorkflowStatus = 'idle' | 'running' | 'paused' | 'completed' | 'error' | 'cancelled';

export interface WorkflowStep {
  skill: string;
  purpose: string;
  status: StepStatus;
  duration_s?: number;
  error?: string;
  output?: Record<string, unknown>;
}

export interface WorkflowChain {
  name: string;
  description: string;
  steps: string[];
  checkpoint_after: number[];
  tier: WorkflowTier;
}

export interface WorkflowExecution {
  id: string;
  chain_name: string;
  description: string;
  current_step: number;
  total_steps: number;
  steps: WorkflowStep[];
  status: WorkflowStatus;
  started_at: string;
  updated_at: string;
  context: {
    lens?: string;
    target_file?: string;
    working_dir: string;
  };
}

export interface Intent {
  category: IntentCategory;
  confidence: number;
  signals: string[];
  suggested_workflow?: string;
  tier: WorkflowTier;
}

interface WorkflowState {
  // Current execution
  execution: WorkflowExecution | null;
  status: WorkflowStatus;

  // Available chains
  chains: WorkflowChain[];

  // Intent routing
  lastIntent: Intent | null;

  // Loading states
  isLoading: boolean;
  isRouting: boolean;

  // Errors
  error: string | null;
}

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

const initialState: WorkflowState = {
  execution: null,
  status: 'idle',
  chains: [],
  lastIntent: null,
  isLoading: false,
  isRouting: false,
  error: null,
};

let _state = $state<WorkflowState>({ ...initialState });

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const workflowState = {
  get execution() {
    return _state.execution;
  },
  get status() {
    return _state.status;
  },
  get chains() {
    return _state.chains;
  },
  get lastIntent() {
    return _state.lastIntent;
  },
  get isLoading() {
    return _state.isLoading;
  },
  get isRouting() {
    return _state.isRouting;
  },
  get error() {
    return _state.error;
  },

  // Computed
  get isRunning() {
    return _state.status === 'running';
  },
  get isPaused() {
    return _state.status === 'paused';
  },
  get isComplete() {
    return _state.status === 'completed';
  },
  get hasError() {
    return _state.status === 'error';
  },
  get progress() {
    if (!_state.execution) return 0;
    return (_state.execution.current_step / _state.execution.total_steps) * 100;
  },
  get currentStep() {
    if (!_state.execution) return null;
    return _state.execution.steps[_state.execution.current_step] ?? null;
  },
};

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Route natural language input to a workflow.
 */
export async function routeIntent(userInput: string): Promise<Intent | null> {
  _state = { ..._state, isRouting: true, error: null };

  try {
    const intent = await apiPost<Intent>('/api/workflow/route', { user_input: userInput });
    _state = { ..._state, lastIntent: intent, isRouting: false };
    return intent;
  } catch (e) {
    _state = {
      ..._state,
      isRouting: false,
      error: e instanceof Error ? e.message : String(e),
    };
    return null;
  }
}

/**
 * Start a workflow chain.
 */
export async function startWorkflow(
  chainName: string,
  targetFile?: string,
): Promise<WorkflowExecution | null> {
  _state = { ..._state, isLoading: true, error: null, status: 'running' };

  try {
    const execution = await apiPost<WorkflowExecution>('/api/workflow/start', {
      chain_name: chainName,
      target_file: targetFile,
    });

    _state = {
      ..._state,
      execution,
      status: 'running',
      isLoading: false,
    };

    // Set up event listeners for progress updates
    setupWorkflowListeners();

    return execution;
  } catch (e) {
    _state = {
      ..._state,
      isLoading: false,
      status: 'error',
      error: e instanceof Error ? e.message : String(e),
    };
    return null;
  }
}

/**
 * Stop the current workflow.
 */
export async function stopWorkflow(): Promise<void> {
  if (!_state.execution) return;

  try {
    await apiPost('/api/workflow/stop', { execution_id: _state.execution.id });
    _state = { ..._state, status: 'paused' };
  } catch (e) {
    _state = {
      ..._state,
      error: e instanceof Error ? e.message : String(e),
    };
  }
}

/**
 * Resume a paused workflow.
 */
export async function resumeWorkflow(executionId?: string): Promise<void> {
  const id = executionId ?? _state.execution?.id;
  if (!id) return;

  _state = { ..._state, isLoading: true, status: 'running' };

  try {
    const execution = await apiPost<WorkflowExecution>('/api/workflow/resume', {
      execution_id: id,
    });

    _state = { ..._state, execution, isLoading: false };
    setupWorkflowListeners();
  } catch (e) {
    _state = {
      ..._state,
      isLoading: false,
      status: 'error',
      error: e instanceof Error ? e.message : String(e),
    };
  }
}

/**
 * Skip the current step.
 */
export async function skipStep(): Promise<void> {
  if (!_state.execution) return;

  try {
    await apiPost('/api/workflow/skip-step', { execution_id: _state.execution.id });
  } catch (e) {
    _state = {
      ..._state,
      error: e instanceof Error ? e.message : String(e),
    };
  }
}

/**
 * Load available workflow chains.
 */
export async function loadChains(): Promise<void> {
  try {
    const result = await apiGet<{ chains: WorkflowChain[] }>('/api/workflow/chains');
    _state = { ..._state, chains: result.chains || [] };
  } catch {
    // Fallback to hardcoded chains
    _state = {
      ..._state,
      chains: DEFAULT_CHAINS,
    };
  }
}

/**
 * List active workflows.
 */
export async function listActiveWorkflows(): Promise<WorkflowExecution[]> {
  try {
    const result = await apiGet<{ workflows: WorkflowExecution[] }>('/api/workflow/active');
    return result.workflows || [];
  } catch {
    return [];
  }
}

/**
 * Update execution state from event.
 */
export function updateExecution(update: Partial<WorkflowExecution>): void {
  if (!_state.execution) return;

  _state = {
    ..._state,
    execution: { ..._state.execution, ...update },
    status: update.status ?? _state.status,
  };
}

/**
 * Clear workflow state.
 */
export function clearWorkflow(): void {
  _state = { ...initialState };
}

/**
 * Reset workflow store.
 */
export function resetWorkflow(): void {
  _state = { ...initialState };
}

// ═══════════════════════════════════════════════════════════════
// INTERNAL
// ═══════════════════════════════════════════════════════════════

let unlistenFn: (() => void) | null = null;

function setupWorkflowListeners(): void {
  // Clean up existing listeners
  if (unlistenFn) {
    unlistenFn();
    unlistenFn = null;
  }

  // Use HTTP API event system
  unlistenFn = onEvent((event) => {
    if (event.type.startsWith('workflow_')) {
      handleWorkflowEvent({
        type: event.type as WorkflowEvent['type'],
        execution_id: event.data?.execution_id as string,
        step_index: event.data?.step_index as number | undefined,
        step_result: event.data?.step_result as WorkflowStep | undefined,
        error: event.data?.error as string | undefined,
      });
    }
  });
}

interface WorkflowEvent {
  type: 'workflow_step_started' | 'workflow_step_completed' | 'workflow_step_error' | 'workflow_paused' | 'workflow_completed';
  execution_id: string;
  step_index?: number;
  step_result?: WorkflowStep;
  error?: string;
}

function handleWorkflowEvent(event: WorkflowEvent): void {
  if (!_state.execution || _state.execution.id !== event.execution_id) return;

  switch (event.type) {
    case 'workflow_step_started':
      if (event.step_index !== undefined) {
        const steps = [..._state.execution.steps];
        if (steps[event.step_index]) {
          steps[event.step_index] = { ...steps[event.step_index], status: 'running' };
        }
        _state = {
          ..._state,
          execution: { ..._state.execution, steps, current_step: event.step_index },
        };
      }
      break;

    case 'workflow_step_completed':
      if (event.step_index !== undefined && event.step_result) {
        const steps = [..._state.execution.steps];
        steps[event.step_index] = event.step_result;
        _state = {
          ..._state,
          execution: {
            ..._state.execution,
            steps,
            current_step: event.step_index + 1,
          },
        };
      }
      break;

    case 'workflow_step_error':
      _state = {
        ..._state,
        status: 'error',
        error: event.error ?? 'Step execution failed',
      };
      break;

    case 'workflow_paused':
      _state = { ..._state, status: 'paused' };
      break;

    case 'workflow_completed':
      _state = { ..._state, status: 'completed' };
      break;
  }
}

// ═══════════════════════════════════════════════════════════════
// DEFAULT CHAINS
// ═══════════════════════════════════════════════════════════════

const DEFAULT_CHAINS: WorkflowChain[] = [
  {
    name: 'feature-docs',
    description: 'Document a new feature end-to-end',
    steps: ['context-analyze', 'draft-claims', 'write-structure', 'audit-enhanced', 'apply-style'],
    checkpoint_after: [1, 3],
    tier: 'full',
  },
  {
    name: 'health-check',
    description: 'Comprehensive validation of existing docs',
    steps: ['context-analyze', 'audit-enhanced', 'style-check', 'code-example-audit', 'confidence-score'],
    checkpoint_after: [],
    tier: 'light',
  },
  {
    name: 'quick-fix',
    description: 'Fast issue resolution',
    steps: ['context-analyze', 'auto-select-fixer', 'audit'],
    checkpoint_after: [],
    tier: 'fast',
  },
  {
    name: 'modernize',
    description: 'Update legacy documentation',
    steps: ['audit-enhanced', 'draft-updates', 'modularize-content', 'apply-style', 'reflexion-loop'],
    checkpoint_after: [0, 3],
    tier: 'full',
  },
];
