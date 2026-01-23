/**
 * Home route tests — verify navigation and state management
 *
 * Key regression test: Stale homeState.response must be cleared on mount,
 * otherwise projects are hidden when navigating back to Home.
 */

import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest';
import { render, screen, waitFor } from '@testing-library/svelte/svelte5';
import { tick } from 'svelte';
import Home from './Home.svelte';
import { homeState, resetHome } from '../stores/home.svelte';
import type { ProjectStatus } from '$lib/types';

// Mock project store
const mockDiscovered: ProjectStatus[] = [
  {
    id: 'test-1',
    path: '/test/project-1',
    display_path: '~/projects/project-1',
    name: 'project-1',
    status: 'active',
    last_goal: 'Build something cool',
    tasks_completed: 2,
    tasks_total: 5,
    tasks: null,
    last_activity: new Date().toISOString(),
  },
];

vi.mock('../stores/project.svelte', () => ({
  project: {
    get discovered() { return mockDiscovered; },
    get current() { return null; },
    get isScanning() { return false; },
    get error() { return null; },
  },
  scanProjects: vi.fn(),
  openProject: vi.fn(),
  resumeProject: vi.fn(),
  deleteProject: vi.fn(),
  archiveProject: vi.fn(),
  iterateProject: vi.fn(),
  analyzeProject: vi.fn(),
}));

vi.mock('../stores/lens.svelte', () => ({
  lens: {
    selection: { lens: null, autoSelect: true },
    available: [],
    isLoading: false,
  },
  loadLenses: vi.fn(),
  selectLens: vi.fn(),
}));

vi.mock('../stores/agent.svelte', () => ({
  runGoal: vi.fn(),
}));

vi.mock('../stores/app.svelte', () => ({
  goToProject: vi.fn(),
  goToDemo: vi.fn(),
}));

describe('Home', () => {
  beforeEach(() => {
    // Reset home state before each test
    resetHome();
    vi.clearAllMocks();
  });

  describe('navigation state management', () => {
    it('clears stale response on mount so projects are visible', async () => {
      // Simulate stale response from previous interaction
      // (user typed something, got a response, navigated away, came back)
      homeState.response = {
        route: 'conversation',
        response: 'Previous conversation response',
      };

      render(Home);
      await tick();

      // Response should be cleared
      expect(homeState.response).toBeNull();
    });

    it('shows projects when no response is active', async () => {
      // Ensure clean state
      homeState.response = null;

      render(Home);
      await tick();

      // ProjectManager should be rendered (projects visible)
      // The component renders when project.discovered.length > 0 && !homeState.response
      await waitFor(() => {
        // Look for the contextual-blocks section that contains ProjectManager
        const container = document.querySelector('.contextual-blocks');
        expect(container).toBeInTheDocument();
      });
    });

  });

  describe('initialization', () => {
    it('calls scanProjects on mount', async () => {
      const { scanProjects } = await import('../stores/project.svelte');

      render(Home);
      await tick();

      expect(scanProjects).toHaveBeenCalled();
    });

    it('calls loadLenses on mount', async () => {
      const { loadLenses } = await import('../stores/lens.svelte');

      render(Home);
      await tick();

      expect(loadLenses).toHaveBeenCalled();
    });
  });
});
