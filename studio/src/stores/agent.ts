/**
 * Agent Store — manages Sunwell agent state and communication
 * 
 * Includes a DEMO_MODE for testing without the full Sunwell CLI.
 */

import { writable, derived, get } from 'svelte/store';
import type { 
  AgentState, 
  AgentEvent, 
  AgentEventType, 
  AgentStatus,
  Task,
  Concept,
  ConceptCategory
} from '$lib/types';
import { updateNode, completeNode } from './dag';

// RFC-053: Set to false to use real Sunwell agent
// Set to true to use mock data for testing without the CLI
const DEMO_MODE = false;

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
  concepts: [],
};

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
          concepts.push({
            id,
            label: match[0],
            category: category as ConceptCategory,
            timestamp: Date.now(),
          });
        }
      }
    }
  }
  return concepts;
}

function deduplicateConcepts(concepts: Concept[]): Concept[] {
  const seen = new Set<string>();
  return concepts.filter(c => {
    if (seen.has(c.id)) return false;
    seen.add(c.id);
    return true;
  });
}

export const agentState = writable<AgentState>(initialState);

// Event listener cleanup
let eventUnlisten: (() => void) | null = null;
let stopUnlisten: (() => void) | null = null;

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
  // Demo mode - simulate agent execution
  if (DEMO_MODE) {
    return runDemoGoal(goal);
  }

  try {
    const { invoke } = await import('@tauri-apps/api/core');
    
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
 * Demo mode - simulate agent execution with mock tasks.
 */
async function runDemoGoal(goal: string): Promise<boolean> {
  // Generate demo tasks based on goal
  const demoTasks: Task[] = [
    { id: '1', description: 'Analyzing goal...', status: 'pending', progress: 0 },
    { id: '2', description: 'Creating project structure', status: 'pending', progress: 0 },
    { id: '3', description: 'Setting up models', status: 'pending', progress: 0 },
    { id: '4', description: 'Implementing routes', status: 'pending', progress: 0 },
    { id: '5', description: 'Adding authentication', status: 'pending', progress: 0 },
    { id: '6', description: 'Writing tests', status: 'pending', progress: 0 },
    { id: '7', description: 'Final verification', status: 'pending', progress: 0 },
  ];

  agentState.set({
    ...initialState,
    status: 'planning',
    goal,
    startTime: Date.now(),
    tasks: demoTasks,
    totalTasks: demoTasks.length,
  });

  // Simulate planning phase
  await sleep(800);
  
  agentState.update(s => ({ ...s, status: 'running' }));

  // Simulate each task
  for (let i = 0; i < demoTasks.length; i++) {
    // Start task
    agentState.update(s => {
      const tasks = [...s.tasks];
      tasks[i] = { ...tasks[i], status: 'running', progress: 0 };
      return { ...s, tasks, currentTaskIndex: i };
    });

    // Simulate progress
    for (let p = 0; p <= 100; p += 20) {
      await sleep(150 + Math.random() * 200);
      agentState.update(s => {
        const tasks = [...s.tasks];
        tasks[i] = { ...tasks[i], progress: p };
        return { ...s, tasks };
      });
    }

    // Complete task
    agentState.update(s => {
      const tasks = [...s.tasks];
      tasks[i] = { ...tasks[i], status: 'complete', progress: 100 };
      return { ...s, tasks };
    });

    await sleep(200);
  }

  // Done!
  const demoLearnings = [
    'Detected Flask web framework',
    'Using SQLAlchemy for ORM',
    'pytest available for testing',
    'SQLite database detected',
  ];
  
  const demoConcepts: Concept[] = demoLearnings.flatMap(extractConcepts);
  
  agentState.update(s => ({
    ...s,
    status: 'done',
    endTime: Date.now(),
    learnings: demoLearnings,
    concepts: deduplicateConcepts(demoConcepts),
  }));

  return true;
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Stop the running agent.
 */
export async function stopAgent(): Promise<void> {
  if (DEMO_MODE) {
    cleanup();
    agentState.update(s => ({
      ...s,
      status: 'idle',
      endTime: Date.now(),
    }));
    return;
  }

  try {
    const { invoke } = await import('@tauri-apps/api/core');
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
  if (DEMO_MODE) return;

  // Clean up existing listeners
  cleanup();

  try {
    const { listen } = await import('@tauri-apps/api/event');

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
  } catch (e) {
    console.error('Failed to setup event listeners:', e);
  }
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
      
      // RFC-056: Also update DAG store
      updateNode(taskId, { 
        status: 'running',
        currentAction: description,
      });
      break;
    }

    case 'task_progress': {
      const taskId = (data.task_id as string) ?? '';
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
      
      // RFC-056: Also update DAG store
      if (taskId) {
        updateNode(taskId, { progress });
      }
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
      
      // RFC-056: Also update DAG store - this updates dependent nodes to 'ready'
      if (taskId) {
        completeNode(taskId);
      }
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
      
      // RFC-056: Also update DAG store
      if (taskId) {
        updateNode(taskId, { status: 'failed' });
      }
      break;
    }

    // Memory events
    case 'memory_learning': {
      const fact = (data.fact as string) ?? '';
      if (fact) {
        const newConcepts = extractConcepts(fact);
        agentState.update(s => ({
          ...s,
          learnings: [...s.learnings, fact],
          concepts: deduplicateConcepts([...s.concepts, ...newConcepts]),
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
