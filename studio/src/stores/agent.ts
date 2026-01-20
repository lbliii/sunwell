/**
 * Agent Store — manages Sunwell agent state and communication
 */

import { writable, derived, get } from 'svelte/store';
import { invoke } from '@tauri-apps/api/core';
import { listen, type UnlistenFn } from '@tauri-apps/api/event';
import type { 
  AgentState, 
  AgentEvent, 
  AgentEventType, 
  AgentStatus,
  Task 
} from '$lib/types';

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

const initialState: AgentState = {
  status: 'idle',
  goal: null,
  tasks: [],
  currentTaskIndex: -1,
  totalTasks: 0,
  startTime: null,
  endTime: null,
  error: null,
  learnings: [],
};

export const agentState = writable<AgentState>(initialState);

// Event listener cleanup
let eventUnlisten: UnlistenFn | null = null;
let stopUnlisten: UnlistenFn | null = null;

// ═══════════════════════════════════════════════════════════════
// DERIVED
// ═══════════════════════════════════════════════════════════════

export const isRunning = derived(
  agentState,
  $s => ['starting', 'planning', 'running'].includes($s.status)
);

export const isDone = derived(
  agentState,
  $s => $s.status === 'done'
);

export const hasError = derived(
  agentState,
  $s => $s.status === 'error'
);

export const progress = derived(agentState, $s => {
  if ($s.totalTasks === 0) return 0;
  const completed = $s.tasks.filter(t => t.status === 'complete').length;
  return Math.round((completed / $s.totalTasks) * 100);
});

export const duration = derived(agentState, $s => {
  if (!$s.startTime) return 0;
  const end = $s.endTime ?? Date.now();
  return Math.round((end - $s.startTime) / 1000);
});

export const completedTasks = derived(
  agentState,
  $s => $s.tasks.filter(t => t.status === 'complete').length
);

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Run a goal using the Sunwell agent.
 */
export async function runGoal(goal: string, projectPath?: string): Promise<boolean> {
  try {
    // Reset state
    agentState.set({
      ...initialState,
      status: 'starting',
      goal,
      startTime: Date.now(),
    });

    // Set up event listeners
    await setupEventListeners();

    // Start the agent
    const result = await invoke<{ success: boolean; message: string }>('run_goal', {
      goal,
      projectPath,
    });

    if (!result.success) {
      agentState.update(s => ({
        ...s,
        status: 'error',
        error: result.message,
      }));
      return false;
    }

    agentState.update(s => ({ ...s, status: 'planning' }));
    return true;
  } catch (e) {
    agentState.update(s => ({
      ...s,
      status: 'error',
      error: e instanceof Error ? e.message : String(e),
    }));
    return false;
  }
}

/**
 * Stop the running agent.
 */
export async function stopAgent(): Promise<void> {
  try {
    await invoke('stop_agent');
    cleanup();
    agentState.update(s => ({
      ...s,
      status: 'idle',
      endTime: Date.now(),
    }));
  } catch (e) {
    console.error('Failed to stop agent:', e);
  }
}

/**
 * Reset agent state.
 */
export function resetAgent(): void {
  cleanup();
  agentState.set(initialState);
}

// ═══════════════════════════════════════════════════════════════
// EVENT HANDLING
// ═══════════════════════════════════════════════════════════════

async function setupEventListeners(): Promise<void> {
  // Clean up existing listeners
  cleanup();

  // Listen for agent events
  eventUnlisten = await listen<AgentEvent>('agent-event', (event) => {
    handleAgentEvent(event.payload);
  });

  // Listen for agent stop
  stopUnlisten = await listen('agent-stopped', () => {
    const state = get(agentState);
    if (state.status !== 'error') {
      agentState.update(s => ({
        ...s,
        status: 'done',
        endTime: Date.now(),
      }));
    }
  });
}

function cleanup(): void {
  if (eventUnlisten) {
    eventUnlisten();
    eventUnlisten = null;
  }
  if (stopUnlisten) {
    stopUnlisten();
    stopUnlisten = null;
  }
}

function handleAgentEvent(event: AgentEvent): void {
  const { type, data } = event;

  switch (type) {
    // Planning events
    case 'plan_start':
      agentState.update(s => ({ ...s, status: 'planning' }));
      break;

    case 'plan_winner':
      agentState.update(s => ({
        ...s,
        status: 'running',
        totalTasks: (data.tasks as number) ?? 0,
      }));
      break;

    // Task events
    case 'task_start': {
      const taskId = (data.task_id as string) ?? `task-${Date.now()}`;
      const description = (data.description as string) ?? 'Working...';
      
      agentState.update(s => {
        const existingIndex = s.tasks.findIndex(t => t.id === taskId);
        if (existingIndex >= 0) {
          // Update existing task
          const tasks = [...s.tasks];
          tasks[existingIndex] = { ...tasks[existingIndex], status: 'running' };
          return { ...s, tasks, currentTaskIndex: existingIndex };
        } else {
          // Add new task
          const newTask: Task = {
            id: taskId,
            description,
            status: 'running',
            progress: 0,
          };
          return {
            ...s,
            tasks: [...s.tasks, newTask],
            currentTaskIndex: s.tasks.length,
          };
        }
      });
      break;
    }

    case 'task_progress': {
      const progress = (data.progress as number) ?? 0;
      agentState.update(s => {
        if (s.currentTaskIndex >= 0 && s.currentTaskIndex < s.tasks.length) {
          const tasks = [...s.tasks];
          tasks[s.currentTaskIndex] = {
            ...tasks[s.currentTaskIndex],
            progress,
          };
          return { ...s, tasks };
        }
        return s;
      });
      break;
    }

    case 'task_complete': {
      const taskId = (data.task_id as string) ?? '';
      const durationMs = (data.duration_ms as number) ?? 0;
      
      agentState.update(s => {
        const tasks = s.tasks.map(t =>
          t.id === taskId || (taskId === '' && t.status === 'running')
            ? { ...t, status: 'complete' as const, progress: 100, duration_ms: durationMs }
            : t
        );
        return { ...s, tasks };
      });
      break;
    }

    case 'task_failed': {
      const taskId = (data.task_id as string) ?? '';
      agentState.update(s => {
        const tasks = s.tasks.map(t =>
          t.id === taskId || (taskId === '' && t.status === 'running')
            ? { ...t, status: 'failed' as const }
            : t
        );
        return { ...s, tasks };
      });
      break;
    }

    // Memory events
    case 'memory_learning': {
      const fact = (data.fact as string) ?? '';
      if (fact) {
        agentState.update(s => ({
          ...s,
          learnings: [...s.learnings, fact],
        }));
      }
      break;
    }

    // Completion events
    case 'complete':
      agentState.update(s => ({
        ...s,
        status: 'done',
        endTime: Date.now(),
      }));
      cleanup();
      break;

    case 'error': {
      const message = (data.message as string) ?? 'Unknown error';
      agentState.update(s => ({
        ...s,
        status: 'error',
        error: message,
        endTime: Date.now(),
      }));
      cleanup();
      break;
    }

    case 'escalate': {
      const reason = (data.reason as string) ?? 'Unknown';
      const message = (data.message as string) ?? '';
      agentState.update(s => ({
        ...s,
        status: 'error',
        error: `Escalated: ${reason}${message ? ` - ${message}` : ''}`,
      }));
      break;
    }
  }
}
