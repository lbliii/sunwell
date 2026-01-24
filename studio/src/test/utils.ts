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
 * Create a mock writable store
 */
export function mockStore<T>(initialValue: T) {
  const store = writable(initialValue);
  return {
    subscribe: store.subscribe,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    set: vi.fn((value: T) => store.set(value)) as any,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    update: vi.fn((updater: (value: T) => T) => store.update(updater)) as any,
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
