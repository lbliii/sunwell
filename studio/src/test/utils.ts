/**
 * Test utilities — helpers for testing Svelte components and stores
 */

import { render, type RenderOptions } from '@testing-library/svelte/svelte5';
import { writable } from 'svelte/store';
import { vi } from 'vitest';
import type { Component } from 'svelte';
import type { AgentEventType, AgentEvent } from '$lib/agent-events';

/**
 * Render a component with default props and optional overrides
 * 
 * Note: The `any` cast is required due to Svelte 5's Component type not being
 * directly assignable to testing-library's expected SvelteComponent type.
 * This is a known limitation of @testing-library/svelte's Svelte 5 support.
 */
export function renderComponent<Props extends Record<string, unknown>>(
  component: Component<Props>,
  props: Partial<Props> = {},
  options?: RenderOptions
) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return render(component as any, { props: props as Props, ...options });
}

/**
 * Mock store interface with proper types
 */
interface MockStore<T> {
  subscribe: (run: (value: T) => void) => () => void;
  set: ReturnType<typeof vi.fn<[T], void>> & ((value: T) => void);
  update: ReturnType<typeof vi.fn<[(value: T) => T], void>> & ((updater: (value: T) => T) => void);
}

/**
 * Create a mock writable store with spy methods
 */
export function mockStore<T>(initialValue: T): MockStore<T> {
  const store = writable(initialValue);

  const setFn = vi.fn((value: T) => store.set(value));
  const updateFn = vi.fn((updater: (value: T) => T) => store.update(updater));

  return {
    subscribe: store.subscribe,
    set: setFn as MockStore<T>['set'],
    update: updateFn as MockStore<T>['update'],
  };
}

/**
 * Wait for reactive updates to complete
 */
export async function waitForReactive() {
  await new Promise((resolve) => setTimeout(resolve, 0));
}

/**
 * Create a sparse array (for testing sparse array handling)
 */
export function createSparseArray<T>(length: number, values: Record<number, T>): (T | undefined)[] {
  const arr: (T | undefined)[] = new Array(length);
  for (const [index, value] of Object.entries(values)) {
    arr[Number(index)] = value;
  }
  return arr;
}

/**
 * Create a test agent event with automatic timestamp
 */
export function createTestEvent(
  type: AgentEventType,
  data: Record<string, unknown> = {}
): AgentEvent {
  return {
    type,
    data,
    timestamp: Date.now(),
  };
}
