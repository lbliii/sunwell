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

// Mock Tauri API (since we're testing in Node, not Tauri runtime)
vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(),
}));

vi.mock('@tauri-apps/api/event', () => ({
  listen: vi.fn(() => Promise.resolve(() => {})),
}));

// Global test utilities
global.expect = expect;
