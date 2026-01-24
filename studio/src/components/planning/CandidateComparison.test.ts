/**
 * CandidateComparison tests — verify sparse array handling
 * 
 * Tests the fix for sparse arrays created by indexed assignment.
 */

import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte/svelte5';
import CandidateComparison from './CandidateComparison.svelte';
import type { PlanCandidate } from '$lib/types';
import { createSparseArray } from '../../test/utils';

describe('CandidateComparison', () => {
  const mockCandidate: PlanCandidate = {
    id: 'candidate-0',
    artifact_count: 5,
    score: 8.5,
    metrics: {
      depth: 3,
      width: 4,
      leaf_count: 2,
      artifact_count: 5,
      parallelism_factor: 0.7,
      balance_factor: 0.8,
      estimated_waves: 2,
      file_conflicts: 0,
    },
    variance_config: {
      prompt_style: 'default',
    },
  };

  it('renders candidates correctly', () => {
    const candidates: PlanCandidate[] = [mockCandidate];
    const { getByText } = render(CandidateComparison, {
      candidates,
      selected: null,
    });

    expect(getByText('Plan Candidates (1 generated)')).toBeInTheDocument();
    expect(getByText('5')).toBeInTheDocument(); // artifact_count
  });

  it('filters out undefined entries from sparse arrays', () => {
    // Simulate sparse array created by indexed assignment
    // e.g., candidates[5] = {...} when array length is 1
    const sparseArray = createSparseArray(6, {
      0: mockCandidate,
      5: { ...mockCandidate, id: 'candidate-5', artifact_count: 10 },
    });

    const { getByText } = render(CandidateComparison, {
      candidates: sparseArray as PlanCandidate[],
      selected: null,
    });

    // Should only show 2 valid candidates, not 6
    expect(getByText('Plan Candidates (2 generated)')).toBeInTheDocument();
    expect(getByText('5')).toBeInTheDocument(); // First candidate
    expect(getByText('10')).toBeInTheDocument(); // Fifth candidate
  });

  it('highlights selected candidate by id', () => {
    const candidates: PlanCandidate[] = [
      mockCandidate,
      { ...mockCandidate, id: 'candidate-1', artifact_count: 8 },
    ];
    const selected = candidates[1];

    const { container } = render(CandidateComparison, {
      candidates,
      selected,
    });

    const rows = container.querySelectorAll('tbody tr');
    expect(rows[1]).toHaveClass('selected');
    expect(rows[0]).not.toHaveClass('selected');
  });

  it('handles empty candidates array', () => {
    const { container } = render(CandidateComparison, {
      candidates: [],
      selected: null,
    });

    expect(container.querySelector('.candidate-comparison')).not.toBeInTheDocument();
  });

  it('handles all undefined entries gracefully', () => {
    const sparseArray = createSparseArray(3, {});

    const { container } = render(CandidateComparison, {
      candidates: sparseArray as PlanCandidate[],
      selected: null,
    });

    // Should not render anything if all entries are undefined
    expect(container.querySelector('.candidate-comparison')).not.toBeInTheDocument();
  });
});
