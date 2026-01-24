/**
 * Test setup — global test configuration
 *
 * Runs before all tests. Sets up mocks, polyfills, and test utilities.
 */

import { expect, afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/svelte/svelte5';
import '@testing-library/jest-dom/vitest';

// Cleanup after each test (removes mounted components)
afterEach(() => {
  cleanup();
});

// Mock socket.ts API (HTTP bridge)
vi.mock('$lib/socket', () => ({
  apiGet: vi.fn(() => Promise.resolve({})),
  apiPost: vi.fn(() => Promise.resolve({})),
  apiDelete: vi.fn(() => Promise.resolve({})),
  onEvent: vi.fn(() => () => {}),
  startRun: vi.fn(() => Promise.resolve({ run_id: 'test-run-id', status: 'pending' })),
  cancelRun: vi.fn(() => Promise.resolve()),
  getRunStatus: vi.fn(() => Promise.resolve({ run_id: 'test-run-id', status: 'pending' })),
  disconnect: vi.fn(),
  stats: { connected: false, reconnects: 0, totalEvents: 0, droppedEvents: 0, lastLatency: 0 },
  getMemory: vi.fn(() => Promise.resolve({ learnings: [], dead_ends: [] })),
  checkpointMemory: vi.fn(() => Promise.resolve({ status: 'saved' })),
  listLenses: vi.fn(() => Promise.resolve([])),
  getLens: vi.fn(() => Promise.resolve(null)),
  getProject: vi.fn(() => Promise.resolve({ path: '/test', name: 'test' })),
  analyzeProject: vi.fn(() => Promise.resolve({})),
  listProjectFiles: vi.fn(() => Promise.resolve({ files: [] })),
  openFinder: vi.fn(() => Promise.resolve({ status: 'opened' })),
  openTerminal: vi.fn(() => Promise.resolve({ status: 'opened' })),
  openEditor: vi.fn(() => Promise.resolve({ status: 'opened' })),
  healthCheck: vi.fn(() => Promise.resolve({ status: 'healthy', active_runs: 0 })),
}));

// Global test utilities
global.expect = expect;
