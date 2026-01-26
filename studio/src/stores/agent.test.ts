/**
 * Agent store tests — verify state management and strict contract enforcement
 *
 * Tests that the store properly handles events, prevents sparse arrays,
 * and requires IDs (not indices) for identification.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { agent, handleAgentEvent, resetAgent } from './agent.svelte';
import { createTestEvent } from '../test/utils';

describe('agent store', () => {
  beforeEach(() => {
    // Reset state before each test
    resetAgent();
    vi.restoreAllMocks();
  });

  describe('plan_candidate_generated', () => {
    it('creates dense array using candidate_id', () => {
      // First initialize planning state
      handleAgentEvent(createTestEvent('plan_candidate_start', { total_candidates: 6 }));

      handleAgentEvent(createTestEvent('plan_candidate_generated', {
        candidate_id: 'candidate-5',
        artifact_count: 10,
        progress: 1,
        total_candidates: 6,
        variance_config: { prompt_style: 'default' },
      }));

      expect(agent.planningCandidates).toHaveLength(1);
      expect(agent.planningCandidates[0]).toBeDefined();
      expect(agent.planningCandidates[0]?.id).toBe('candidate-5');
      expect(agent.planningCandidates[0]?.artifact_count).toBe(10);
    });

    it('handles multiple candidates in any order', () => {
      handleAgentEvent(createTestEvent('plan_candidate_start', { total_candidates: 3 }));

      handleAgentEvent(createTestEvent('plan_candidate_generated', {
        candidate_id: 'candidate-2',
        artifact_count: 5,
        progress: 1,
        total_candidates: 3,
        variance_config: {},
      }));

      handleAgentEvent(createTestEvent('plan_candidate_generated', {
        candidate_id: 'candidate-0',
        artifact_count: 3,
        progress: 2,
        total_candidates: 3,
        variance_config: {},
      }));

      expect(agent.planningCandidates).toHaveLength(2);
      expect(agent.planningCandidates.every((c) => c != null)).toBe(true);
      expect(agent.planningCandidates.find((c) => c.id === 'candidate-0')).toBeDefined();
      expect(agent.planningCandidates.find((c) => c.id === 'candidate-2')).toBeDefined();
    });

    it('rejects events without candidate_id', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      handleAgentEvent(createTestEvent('plan_candidate_start', { total_candidates: 1 }));

      handleAgentEvent(createTestEvent('plan_candidate_generated', {
        artifact_count: 5,
        progress: 1,
        total_candidates: 1,
      }));

      expect(agent.planningCandidates).toHaveLength(0);
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('missing required candidate_id')
      );
    });
  });

  describe('plan_candidate_scored', () => {
    it('updates existing candidate by id', () => {
      handleAgentEvent(createTestEvent('plan_candidate_start', { total_candidates: 1 }));

      handleAgentEvent(createTestEvent('plan_candidate_generated', {
        candidate_id: 'candidate-0',
        artifact_count: 5,
        progress: 1,
        total_candidates: 1,
        variance_config: {},
      }));

      handleAgentEvent(createTestEvent('plan_candidate_scored', {
        candidate_id: 'candidate-0',
        score: 8.5,
        total_candidates: 1,
        metrics: {
          depth: 3,
          parallelism_factor: 0.7,
          balance_factor: 0.8,
          estimated_waves: 2,
          file_conflicts: 0,
        },
        progress: 1,
      }));

      expect(agent.planningCandidates).toHaveLength(1);
      expect(agent.planningCandidates[0]?.score).toBe(8.5);
      expect(agent.planningCandidates[0]?.metrics?.depth).toBe(3);
    });

    it('creates candidate if scored before generated (out-of-order)', () => {
      handleAgentEvent(createTestEvent('plan_candidate_start', { total_candidates: 1 }));

      // Score arrives before generate (out of order)
      handleAgentEvent(createTestEvent('plan_candidate_scored', {
        candidate_id: 'candidate-3',
        score: 7.0,
        total_candidates: 1,
        metrics: {
          depth: 2,
          parallelism_factor: 0.6,
          balance_factor: 0.7,
          estimated_waves: 1,
          file_conflicts: 0,
        },
        progress: 1,
      }));

      expect(agent.planningCandidates).toHaveLength(1);
      expect(agent.planningCandidates[0]?.id).toBe('candidate-3');
      expect(agent.planningCandidates[0]?.score).toBe(7.0);
    });
  });

  describe('plan_winner', () => {
    it('selects candidate by selected_candidate_id', () => {
      handleAgentEvent(createTestEvent('plan_candidate_start', { total_candidates: 3 }));

      // Generate multiple candidates
      handleAgentEvent(createTestEvent('plan_candidate_generated', {
        candidate_id: 'candidate-0',
        artifact_count: 3,
        progress: 1,
        total_candidates: 3,
        variance_config: { prompt_style: 'default' },
      }));
      handleAgentEvent(createTestEvent('plan_candidate_generated', {
        candidate_id: 'candidate-1',
        artifact_count: 5,
        progress: 2,
        total_candidates: 3,
        variance_config: { prompt_style: 'parallel_first' },
      }));
      handleAgentEvent(createTestEvent('plan_candidate_generated', {
        candidate_id: 'candidate-2',
        artifact_count: 7,
        progress: 3,
        total_candidates: 3,
        variance_config: { prompt_style: 'thorough' },
      }));

      // Score them (candidate-1 has highest score)
      handleAgentEvent(createTestEvent('plan_candidate_scored', {
        candidate_id: 'candidate-0', score: 70.0, total_candidates: 3, progress: 1,
      }));
      handleAgentEvent(createTestEvent('plan_candidate_scored', {
        candidate_id: 'candidate-1', score: 90.0, total_candidates: 3, progress: 2,
      }));
      handleAgentEvent(createTestEvent('plan_candidate_scored', {
        candidate_id: 'candidate-2', score: 80.0, total_candidates: 3, progress: 3,
      }));

      // Winner is candidate-1 (highest score)
      handleAgentEvent(createTestEvent('plan_winner', {
        tasks: 5,
        artifact_count: 5,
        selected_candidate_id: 'candidate-1',
        total_candidates: 3,
        score: 90.0,
        selection_reason: 'Highest score',
        variance_strategy: 'prompting',
        variance_config: { prompt_style: 'parallel_first' },
      }));

      expect(agent.selectedCandidate).not.toBeNull();
      expect(agent.selectedCandidate?.id).toBe('candidate-1');
      expect(agent.selectedCandidate?.artifact_count).toBe(5);
      expect(agent.selectedCandidate?.score).toBe(90.0);
      expect(agent.selectedCandidate?.variance_config?.prompt_style).toBe('parallel_first');
    });

    it('handles plan_winner when candidate not found (creates synthetic)', () => {
      // Winner event without prior candidate generation
      handleAgentEvent(createTestEvent('plan_winner', {
        tasks: 3,
        artifact_count: 3,
        selected_candidate_id: 'candidate-unknown',
        total_candidates: 1,
        score: 85.0,
        selection_reason: 'Only candidate',
        variance_strategy: 'none',
      }));

      // Should create a synthetic selectedCandidate
      expect(agent.selectedCandidate).not.toBeNull();
      expect(agent.selectedCandidate?.id).toBe('candidate-unknown');
      expect(agent.selectedCandidate?.artifact_count).toBe(3);
      expect(agent.selectedCandidate?.score).toBe(85.0);
    });

    it('preserves generated candidate details in selectedCandidate', () => {
      handleAgentEvent(createTestEvent('plan_candidate_start', { total_candidates: 1 }));

      handleAgentEvent(createTestEvent('plan_candidate_generated', {
        candidate_id: 'candidate-0',
        artifact_count: 10,
        progress: 1,
        total_candidates: 1,
        variance_config: {
          prompt_style: 'parallel_first',
          temperature: 0.7,
          constraint: 'max_depth_3',
        },
      }));

      handleAgentEvent(createTestEvent('plan_candidate_scored', {
        candidate_id: 'candidate-0',
        score: 95.0,
        total_candidates: 1,
        metrics: {
          depth: 2,
          width: 5,
          parallelism_factor: 0.8,
          balance_factor: 1.2,
          estimated_waves: 2,
          file_conflicts: 0,
        },
        progress: 1,
      }));

      handleAgentEvent(createTestEvent('plan_winner', {
        tasks: 10,
        artifact_count: 10,
        selected_candidate_id: 'candidate-0',
        total_candidates: 1,
        score: 95.0,
        selection_reason: 'Only candidate with excellent score',
      }));

      expect(agent.selectedCandidate?.id).toBe('candidate-0');
      // Should preserve the metrics from scoring
      expect(agent.selectedCandidate?.metrics?.depth).toBe(2);
      expect(agent.selectedCandidate?.metrics?.parallelism_factor).toBe(0.8);
      // Should preserve variance_config from generation
      expect(agent.selectedCandidate?.variance_config?.prompt_style).toBe('parallel_first');
    });

    it('rejects events without selected_candidate_id', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      handleAgentEvent(createTestEvent('plan_winner', {
        tasks: 5,
        artifact_count: 5,
        total_candidates: 1,
      }));

      expect(agent.selectedCandidate).toBeNull();
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('missing required selected_candidate_id')
      );
    });
  });

  describe('task_progress', () => {
    it('updates correct task by task_id not currentTaskIndex', () => {
      // Create two tasks
      handleAgentEvent(createTestEvent('task_start', { task_id: 'task-A', description: 'Task A' }));
      handleAgentEvent(createTestEvent('task_start', { task_id: 'task-B', description: 'Task B' }));

      // Update first task while second is "current"
      handleAgentEvent(createTestEvent('task_progress', { task_id: 'task-A', progress: 50 }));

      const taskA = agent.tasks.find((t) => t.id === 'task-A');
      const taskB = agent.tasks.find((t) => t.id === 'task-B');

      // task-A should have progress 50
      expect(taskA?.progress).toBe(50);
      // task-B (current) should have progress 0
      expect(taskB?.progress).toBe(0);
    });

    it('handles progress for task started later in sequence', () => {
      handleAgentEvent(createTestEvent('task_start', { task_id: 'first', description: 'First' }));
      handleAgentEvent(createTestEvent('task_start', { task_id: 'second', description: 'Second' }));

      // Progress event for task 1 (not current)
      handleAgentEvent(createTestEvent('task_progress', { task_id: 'first', progress: 75 }));

      const first = agent.tasks.find((t) => t.id === 'first');
      expect(first?.progress).toBe(75);
    });

    it('rejects task_progress without task_id', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      handleAgentEvent(createTestEvent('task_start', { task_id: 'task-1', description: 'Task 1' }));
      handleAgentEvent(createTestEvent('task_progress', { progress: 50 })); // Missing task_id

      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('task_progress missing required task_id')
      );
    });
  });

  describe('task_complete', () => {
    it('completes correct task by task_id', () => {
      handleAgentEvent(createTestEvent('task_start', { task_id: 'task-1', description: 'Task 1' }));
      handleAgentEvent(createTestEvent('task_start', { task_id: 'task-2', description: 'Task 2' }));

      // Complete first task by ID
      handleAgentEvent(createTestEvent('task_complete', { task_id: 'task-1', duration_ms: 100 }));

      const task1 = agent.tasks.find((t) => t.id === 'task-1');
      const task2 = agent.tasks.find((t) => t.id === 'task-2');

      expect(task1?.status).toBe('complete');
      expect(task2?.status).toBe('running'); // Should NOT be completed
    });

    it('rejects task_complete without task_id', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      handleAgentEvent(createTestEvent('task_start', { task_id: 'task-1', description: 'Task 1' }));
      handleAgentEvent(createTestEvent('task_complete', { duration_ms: 100 })); // Missing task_id

      // Task should still be running (not completed)
      expect(agent.tasks[0]?.status).toBe('running');
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('task_complete missing required task_id')
      );
    });
  });

  describe('task_failed', () => {
    it('fails correct task by task_id', () => {
      handleAgentEvent(createTestEvent('task_start', { task_id: 'success-task', description: 'Will succeed' }));
      handleAgentEvent(createTestEvent('task_start', { task_id: 'fail-task', description: 'Will fail' }));

      // Fail only the second task
      handleAgentEvent(createTestEvent('task_failed', { task_id: 'fail-task', error: 'Something went wrong' }));

      const successTask = agent.tasks.find((t) => t.id === 'success-task');
      const failTask = agent.tasks.find((t) => t.id === 'fail-task');

      expect(successTask?.status).toBe('running'); // Should NOT be failed
      expect(failTask?.status).toBe('failed');
    });

    it('rejects task_failed without task_id', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      handleAgentEvent(createTestEvent('task_start', { task_id: 'task-1', description: 'Task 1' }));
      handleAgentEvent(createTestEvent('task_failed', { error: 'Some error' })); // Missing task_id

      // Task should still be running (not failed)
      expect(agent.tasks[0]?.status).toBe('running');
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('task_failed missing required task_id')
      );
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // COMPLETION AND ERROR EVENTS
  // ═══════════════════════════════════════════════════════════════════════════

  describe('complete event', () => {
    it('sets status to done when all tasks complete', () => {
      handleAgentEvent(createTestEvent('task_start', { task_id: 'task-1', description: 'Task 1' }));
      handleAgentEvent(createTestEvent('task_complete', { task_id: 'task-1', duration_ms: 100 }));
      handleAgentEvent(createTestEvent('complete', { tasks_completed: 1, tasks_failed: 0 }));

      expect(agent.status).toBe('done');
      expect(agent.isDone).toBe(true);
      expect(agent.endTime).not.toBeNull();
    });

    it('handles completion with failed tasks', () => {
      handleAgentEvent(createTestEvent('task_start', { task_id: 'task-1', description: 'Task 1' }));
      handleAgentEvent(createTestEvent('task_complete', { task_id: 'task-1', duration_ms: 100 }));
      handleAgentEvent(createTestEvent('task_start', { task_id: 'task-2', description: 'Task 2' }));
      handleAgentEvent(createTestEvent('task_failed', { task_id: 'task-2', error: 'Failed' }));
      handleAgentEvent(createTestEvent('complete', { tasks_completed: 1, tasks_failed: 1 }));

      expect(agent.isDone).toBe(true);
      expect(agent.completedTasks).toBe(1);
      expect(agent.failedTasks).toBe(1);
    });

    it('creates synthetic tasks if complete event has counts but no task events', () => {
      // Simulate scenario where task_start events were missed
      handleAgentEvent(createTestEvent('complete', { tasks_completed: 3, tasks_failed: 1 }));

      expect(agent.isDone).toBe(true);
      expect(agent.tasks.length).toBe(4);
      expect(agent.completedTasks).toBe(3);
      expect(agent.failedTasks).toBe(1);
    });
  });

  describe('error event', () => {
    it('sets status to error with message', () => {
      handleAgentEvent(createTestEvent('error', { message: 'Something went wrong' }));

      expect(agent.status).toBe('error');
      expect(agent.hasError).toBe(true);
      expect(agent.error).toBe('Something went wrong');
      expect(agent.endTime).not.toBeNull();
    });

    it('sets default error message when none provided', () => {
      handleAgentEvent(createTestEvent('error', {}));

      expect(agent.hasError).toBe(true);
      expect(agent.error).toBe('Unknown error');
    });
  });

  describe('escalate event', () => {
    it('sets error status with escalation reason', () => {
      handleAgentEvent(createTestEvent('escalate', {
        reason: 'unfixable_errors',
        message: 'Could not fix linting errors',
        fixed: 2,
        errors: ['Error 1', 'Error 2', 'Error 3'],
      }));

      expect(agent.status).toBe('error');
      expect(agent.error).toContain('Could not fix linting errors');
      expect(agent.error).toContain('Error 1');
      expect(agent.error).toContain('(2 errors were auto-fixed)');
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // CONVERGENCE LOOP EVENTS
  // ═══════════════════════════════════════════════════════════════════════════

  describe('convergence events', () => {
    it('tracks convergence start', () => {
      handleAgentEvent(createTestEvent('convergence_start', {
        files: ['file1.py', 'file2.py'],
        gates: ['lint', 'test'],
        max_iterations: 5,
      }));

      expect(agent.convergence).not.toBeNull();
      expect(agent.convergence?.status).toBe('running');
      expect(agent.convergence?.max_iterations).toBe(5);
      expect(agent.convergence?.enabled_gates).toEqual(['lint', 'test']);
      expect(agent.isConverging).toBe(true);
    });

    it('tracks convergence iterations', () => {
      handleAgentEvent(createTestEvent('convergence_start', {
        files: ['file1.py'],
        gates: ['lint'],
        max_iterations: 5,
      }));

      handleAgentEvent(createTestEvent('convergence_iteration_start', { iteration: 1 }));
      expect(agent.convergence?.current_iteration).toBe(1);

      handleAgentEvent(createTestEvent('convergence_iteration_complete', {
        iteration: 1,
        all_passed: false,
        total_errors: 3,
        gate_results: [{ gate: 'lint', passed: false, errors: 3 }],
      }));

      expect(agent.convergence?.iterations).toHaveLength(1);
      expect(agent.convergence?.iterations[0]?.all_passed).toBe(false);
      expect(agent.convergence?.iterations[0]?.total_errors).toBe(3);
    });

    it('tracks convergence stable', () => {
      handleAgentEvent(createTestEvent('convergence_start', {
        files: ['file1.py'],
        gates: ['lint'],
        max_iterations: 5,
      }));

      handleAgentEvent(createTestEvent('convergence_stable', {
        iterations: 2,
        duration_ms: 5000,
      }));

      expect(agent.convergence?.status).toBe('stable');
      expect(agent.convergence?.duration_ms).toBe(5000);
      expect(agent.isConverging).toBe(false);
    });

    it('tracks convergence timeout', () => {
      handleAgentEvent(createTestEvent('convergence_start', {
        files: ['file1.py'],
        gates: ['lint'],
        max_iterations: 5,
      }));

      handleAgentEvent(createTestEvent('convergence_timeout', {}));

      expect(agent.convergence?.status).toBe('timeout');
    });

    it('tracks convergence stuck', () => {
      handleAgentEvent(createTestEvent('convergence_start', {
        files: ['file1.py'],
        gates: ['lint'],
        max_iterations: 5,
      }));

      handleAgentEvent(createTestEvent('convergence_stuck', {
        repeated_errors: ['same error repeated 3 times'],
      }));

      expect(agent.convergence?.status).toBe('stuck');
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // MEMORY/LEARNING EVENTS
  // ═══════════════════════════════════════════════════════════════════════════

  describe('memory_learning event', () => {
    it('adds learnings and extracts concepts', () => {
      handleAgentEvent(createTestEvent('memory_learning', {
        fact: 'Using Flask framework with SQLAlchemy ORM',
      }));

      expect(agent.learnings).toContain('Using Flask framework with SQLAlchemy ORM');
      // Should extract Flask and SQLAlchemy as concepts
      expect(agent.concepts.some((c) => c.id === 'flask')).toBe(true);
      expect(agent.concepts.some((c) => c.id === 'sqlalchemy')).toBe(true);
    });

    it('deduplicates concepts', () => {
      handleAgentEvent(createTestEvent('memory_learning', { fact: 'Using Flask for web' }));
      handleAgentEvent(createTestEvent('memory_learning', { fact: 'Flask is great' }));

      // Should only have one Flask concept
      const flaskConcepts = agent.concepts.filter((c) => c.id === 'flask');
      expect(flaskConcepts).toHaveLength(1);
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // COMPUTED PROPERTIES
  // ═══════════════════════════════════════════════════════════════════════════

  describe('computed properties', () => {
    it('calculates progress based on completed/failed tasks', () => {
      handleAgentEvent(createTestEvent('task_start', { task_id: 'task-1', description: 'Task 1' }));
      handleAgentEvent(createTestEvent('task_start', { task_id: 'task-2', description: 'Task 2' }));
      handleAgentEvent(createTestEvent('task_start', { task_id: 'task-3', description: 'Task 3' }));
      handleAgentEvent(createTestEvent('task_start', { task_id: 'task-4', description: 'Task 4' }));

      expect(agent.progress).toBe(0);

      handleAgentEvent(createTestEvent('task_complete', { task_id: 'task-1', duration_ms: 100 }));
      expect(agent.progress).toBe(25);

      handleAgentEvent(createTestEvent('task_complete', { task_id: 'task-2', duration_ms: 100 }));
      expect(agent.progress).toBe(50);

      handleAgentEvent(createTestEvent('task_failed', { task_id: 'task-3', error: 'Failed' }));
      expect(agent.progress).toBe(75);
    });

    it('returns 100% progress when status is done', () => {
      handleAgentEvent(createTestEvent('complete', { tasks_completed: 0, tasks_failed: 0 }));
      expect(agent.progress).toBe(100);
    });

    it('returns frozen arrays to prevent mutation', () => {
      handleAgentEvent(createTestEvent('task_start', { task_id: 'task-1', description: 'Task 1' }));

      const tasks = agent.tasks;
      expect(Object.isFrozen(tasks)).toBe(true);

      // Attempting to push should throw in strict mode
      expect(() => {
        (tasks as unknown[]).push({ id: 'hacked' });
      }).toThrow();
    });
  });
});
