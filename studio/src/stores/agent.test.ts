/**
 * Agent store tests — verify state management and strict contract enforcement
 *
 * Tests that the store properly handles events, prevents sparse arrays,
 * and requires IDs (not indices) for identification.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { agent, handleAgentEvent, resetAgent } from './agent.svelte';
import type { AgentEvent } from '$lib/types';

describe('agent store', () => {
  beforeEach(() => {
    // Reset state before each test
    resetAgent();
    vi.restoreAllMocks();
  });

  describe('plan_candidate_generated', () => {
    it('creates dense array using candidate_id', () => {
      // First initialize planning state
      handleAgentEvent({
        type: 'plan_candidate_start',
        data: { total_candidates: 6 },
      });

      handleAgentEvent({
        type: 'plan_candidate_generated',
        data: {
          candidate_id: 'candidate-5',
          artifact_count: 10,
          progress: 1,
          total_candidates: 6,
          variance_config: { prompt_style: 'default' },
        },
      });

      expect(agent.planningCandidates).toHaveLength(1);
      expect(agent.planningCandidates[0]).toBeDefined();
      expect(agent.planningCandidates[0]?.id).toBe('candidate-5');
      expect(agent.planningCandidates[0]?.artifact_count).toBe(10);
    });

    it('handles multiple candidates in any order', () => {
      handleAgentEvent({
        type: 'plan_candidate_start',
        data: { total_candidates: 3 },
      });

      handleAgentEvent({
        type: 'plan_candidate_generated',
        data: {
          candidate_id: 'candidate-2',
          artifact_count: 5,
          progress: 1,
          total_candidates: 3,
          variance_config: {},
        },
      });

      handleAgentEvent({
        type: 'plan_candidate_generated',
        data: {
          candidate_id: 'candidate-0',
          artifact_count: 3,
          progress: 2,
          total_candidates: 3,
          variance_config: {},
        },
      });

      expect(agent.planningCandidates).toHaveLength(2);
      expect(agent.planningCandidates.every((c) => c != null)).toBe(true);
      expect(agent.planningCandidates.find((c) => c.id === 'candidate-0')).toBeDefined();
      expect(agent.planningCandidates.find((c) => c.id === 'candidate-2')).toBeDefined();
    });

    it('rejects events without candidate_id', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      handleAgentEvent({
        type: 'plan_candidate_start',
        data: { total_candidates: 1 },
      });

      handleAgentEvent({
        type: 'plan_candidate_generated',
        data: {
          artifact_count: 5,
          progress: 1,
          total_candidates: 1,
        },
      });

      expect(agent.planningCandidates).toHaveLength(0);
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('missing required candidate_id')
      );
    });
  });

  describe('plan_candidate_scored', () => {
    it('updates existing candidate by id', () => {
      handleAgentEvent({
        type: 'plan_candidate_start',
        data: { total_candidates: 1 },
      });

      handleAgentEvent({
        type: 'plan_candidate_generated',
        data: {
          candidate_id: 'candidate-0',
          artifact_count: 5,
          progress: 1,
          total_candidates: 1,
          variance_config: {},
        },
      });

      handleAgentEvent({
        type: 'plan_candidate_scored',
        data: {
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
        },
      });

      expect(agent.planningCandidates).toHaveLength(1);
      expect(agent.planningCandidates[0]?.score).toBe(8.5);
      expect(agent.planningCandidates[0]?.metrics?.depth).toBe(3);
    });

    it('creates candidate if scored before generated (out-of-order)', () => {
      handleAgentEvent({
        type: 'plan_candidate_start',
        data: { total_candidates: 1 },
      });

      // Score arrives before generate (out of order)
      handleAgentEvent({
        type: 'plan_candidate_scored',
        data: {
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
        },
      });

      expect(agent.planningCandidates).toHaveLength(1);
      expect(agent.planningCandidates[0]?.id).toBe('candidate-3');
      expect(agent.planningCandidates[0]?.score).toBe(7.0);
    });
  });

  describe('plan_winner', () => {
    it('selects candidate by selected_candidate_id', () => {
      handleAgentEvent({
        type: 'plan_candidate_start',
        data: { total_candidates: 3 },
      });

      // Generate multiple candidates
      handleAgentEvent({
        type: 'plan_candidate_generated',
        data: {
          candidate_id: 'candidate-0',
          artifact_count: 3,
          progress: 1,
          total_candidates: 3,
          variance_config: { prompt_style: 'default' },
        },
      });
      handleAgentEvent({
        type: 'plan_candidate_generated',
        data: {
          candidate_id: 'candidate-1',
          artifact_count: 5,
          progress: 2,
          total_candidates: 3,
          variance_config: { prompt_style: 'parallel_first' },
        },
      });
      handleAgentEvent({
        type: 'plan_candidate_generated',
        data: {
          candidate_id: 'candidate-2',
          artifact_count: 7,
          progress: 3,
          total_candidates: 3,
          variance_config: { prompt_style: 'thorough' },
        },
      });

      // Score them (candidate-1 has highest score)
      handleAgentEvent({
        type: 'plan_candidate_scored',
        data: { candidate_id: 'candidate-0', score: 70.0, total_candidates: 3, progress: 1 },
      });
      handleAgentEvent({
        type: 'plan_candidate_scored',
        data: { candidate_id: 'candidate-1', score: 90.0, total_candidates: 3, progress: 2 },
      });
      handleAgentEvent({
        type: 'plan_candidate_scored',
        data: { candidate_id: 'candidate-2', score: 80.0, total_candidates: 3, progress: 3 },
      });

      // Winner is candidate-1 (highest score)
      handleAgentEvent({
        type: 'plan_winner',
        data: {
          tasks: 5,
          artifact_count: 5,
          selected_candidate_id: 'candidate-1',
          total_candidates: 3,
          score: 90.0,
          selection_reason: 'Highest score',
          variance_strategy: 'prompting',
          variance_config: { prompt_style: 'parallel_first' },
        },
      });

      expect(agent.selectedCandidate).not.toBeNull();
      expect(agent.selectedCandidate?.id).toBe('candidate-1');
      expect(agent.selectedCandidate?.artifact_count).toBe(5);
      expect(agent.selectedCandidate?.score).toBe(90.0);
      expect(agent.selectedCandidate?.variance_config?.prompt_style).toBe('parallel_first');
    });

    it('handles plan_winner when candidate not found (creates synthetic)', () => {
      // Winner event without prior candidate generation
      handleAgentEvent({
        type: 'plan_winner',
        data: {
          tasks: 3,
          artifact_count: 3,
          selected_candidate_id: 'candidate-unknown',
          total_candidates: 1,
          score: 85.0,
          selection_reason: 'Only candidate',
          variance_strategy: 'none',
        },
      });

      // Should create a synthetic selectedCandidate
      expect(agent.selectedCandidate).not.toBeNull();
      expect(agent.selectedCandidate?.id).toBe('candidate-unknown');
      expect(agent.selectedCandidate?.artifact_count).toBe(3);
      expect(agent.selectedCandidate?.score).toBe(85.0);
    });

    it('preserves generated candidate details in selectedCandidate', () => {
      handleAgentEvent({
        type: 'plan_candidate_start',
        data: { total_candidates: 1 },
      });

      handleAgentEvent({
        type: 'plan_candidate_generated',
        data: {
          candidate_id: 'candidate-0',
          artifact_count: 10,
          progress: 1,
          total_candidates: 1,
          variance_config: {
            prompt_style: 'parallel_first',
            temperature: 0.7,
            constraint: 'max_depth_3',
          },
        },
      });

      handleAgentEvent({
        type: 'plan_candidate_scored',
        data: {
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
        },
      });

      handleAgentEvent({
        type: 'plan_winner',
        data: {
          tasks: 10,
          artifact_count: 10,
          selected_candidate_id: 'candidate-0',
          total_candidates: 1,
          score: 95.0,
          selection_reason: 'Only candidate with excellent score',
        },
      });

      expect(agent.selectedCandidate?.id).toBe('candidate-0');
      // Should preserve the metrics from scoring
      expect(agent.selectedCandidate?.metrics?.depth).toBe(2);
      expect(agent.selectedCandidate?.metrics?.parallelism_factor).toBe(0.8);
      // Should preserve variance_config from generation
      expect(agent.selectedCandidate?.variance_config?.prompt_style).toBe('parallel_first');
    });

    it('rejects events without selected_candidate_id', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      handleAgentEvent({
        type: 'plan_winner',
        data: {
          tasks: 5,
          artifact_count: 5,
          total_candidates: 1,
        },
      });

      expect(agent.selectedCandidate).toBeNull();
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('missing required selected_candidate_id')
      );
    });
  });

  describe('task_progress', () => {
    it('updates correct task by task_id not currentTaskIndex', () => {
      // Create two tasks
      handleAgentEvent({
        type: 'task_start',
        data: { task_id: 'task-A', description: 'Task A' },
      });
      handleAgentEvent({
        type: 'task_start',
        data: { task_id: 'task-B', description: 'Task B' },
      });

      // Update first task while second is "current"
      handleAgentEvent({
        type: 'task_progress',
        data: { task_id: 'task-A', progress: 50 },
      });

      const taskA = agent.tasks.find((t) => t.id === 'task-A');
      const taskB = agent.tasks.find((t) => t.id === 'task-B');

      // task-A should have progress 50
      expect(taskA?.progress).toBe(50);
      // task-B (current) should have progress 0
      expect(taskB?.progress).toBe(0);
    });

    it('handles progress for task started later in sequence', () => {
      handleAgentEvent({
        type: 'task_start',
        data: { task_id: 'first', description: 'First' },
      });

      handleAgentEvent({
        type: 'task_start',
        data: { task_id: 'second', description: 'Second' },
      });

      // Progress event for task 1 (not current)
      handleAgentEvent({
        type: 'task_progress',
        data: { task_id: 'first', progress: 75 },
      });

      const first = agent.tasks.find((t) => t.id === 'first');
      expect(first?.progress).toBe(75);
    });

    it('rejects task_progress without task_id', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      handleAgentEvent({
        type: 'task_start',
        data: { task_id: 'task-1', description: 'Task 1' },
      });

      handleAgentEvent({
        type: 'task_progress',
        data: { progress: 50 }, // Missing task_id
      });

      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('task_progress missing required task_id')
      );
    });
  });

  describe('task_complete', () => {
    it('completes correct task by task_id', () => {
      handleAgentEvent({
        type: 'task_start',
        data: { task_id: 'task-1', description: 'Task 1' },
      });
      handleAgentEvent({
        type: 'task_start',
        data: { task_id: 'task-2', description: 'Task 2' },
      });

      // Complete first task by ID
      handleAgentEvent({
        type: 'task_complete',
        data: { task_id: 'task-1', duration_ms: 100 },
      });

      const task1 = agent.tasks.find((t) => t.id === 'task-1');
      const task2 = agent.tasks.find((t) => t.id === 'task-2');

      expect(task1?.status).toBe('complete');
      expect(task2?.status).toBe('running'); // Should NOT be completed
    });

    it('rejects task_complete without task_id', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      handleAgentEvent({
        type: 'task_start',
        data: { task_id: 'task-1', description: 'Task 1' },
      });

      handleAgentEvent({
        type: 'task_complete',
        data: { duration_ms: 100 }, // Missing task_id
      });

      // Task should still be running (not completed)
      expect(agent.tasks[0]?.status).toBe('running');
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('task_complete missing required task_id')
      );
    });
  });

  describe('task_failed', () => {
    it('fails correct task by task_id', () => {
      handleAgentEvent({
        type: 'task_start',
        data: { task_id: 'success-task', description: 'Will succeed' },
      });
      handleAgentEvent({
        type: 'task_start',
        data: { task_id: 'fail-task', description: 'Will fail' },
      });

      // Fail only the second task
      handleAgentEvent({
        type: 'task_failed',
        data: { task_id: 'fail-task', error: 'Something went wrong' },
      });

      const successTask = agent.tasks.find((t) => t.id === 'success-task');
      const failTask = agent.tasks.find((t) => t.id === 'fail-task');

      expect(successTask?.status).toBe('running'); // Should NOT be failed
      expect(failTask?.status).toBe('failed');
    });

    it('rejects task_failed without task_id', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      handleAgentEvent({
        type: 'task_start',
        data: { task_id: 'task-1', description: 'Task 1' },
      });

      handleAgentEvent({
        type: 'task_failed',
        data: { error: 'Some error' }, // Missing task_id
      });

      // Task should still be running (not failed)
      expect(agent.tasks[0]?.status).toBe('running');
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('task_failed missing required task_id')
      );
    });
  });
});
