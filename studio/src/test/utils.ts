/**
 * Test utilities — helpers for testing Svelte components and stores
 */

import { render, type RenderOptions } from '@testing-library/svelte/svelte5';
import { writable } from 'svelte/store';
import { vi } from 'vitest';
import type { ComponentProps, ComponentType } from 'svelte';

/**
 * Render a component with default props and optional overrides
 */
export function renderComponent<T extends ComponentType>(
  component: T,
  props: Partial<ComponentProps<T>> = {},
  options?: RenderOptions
) {
  return render(component, props as ComponentProps<T>, options);
}

/**
 * Create a mock writable store
 */
export function mockStore<T>(initialValue: T) {
  const store = writable(initialValue);
  return {
    ...store,
    set: vi.fn(store.set.bind(store)),
    update: vi.fn(store.update.bind(store)),
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
