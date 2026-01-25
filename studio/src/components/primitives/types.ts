/**
 * Primitive Component Types (RFC-072)
 * 
 * Common interface for all surface primitives.
 * Uses generics to provide type safety for seed/data props.
 */

import type { PrimitiveSize } from '$lib/types';

/** Base props for all primitives with typed seed content. */
export interface PrimitiveProps<TSeed extends Record<string, unknown> = Record<string, unknown>> {
  /** Primitive size mode */
  readonly size: PrimitiveSize;

  /** Seed content from composition (type-safe per primitive) */
  readonly seed?: Readonly<TSeed>;
}

/** Props for code-related primitives. */
export interface CodePrimitiveProps extends PrimitiveProps<CodeSeed> {
  readonly file?: string;
  readonly language?: string;
}

/** Seed data for code primitives */
export interface CodeSeed {
  readonly content?: string;
  readonly highlights?: readonly number[];
}

/** Props for writing-related primitives. */
export interface WritingPrimitiveProps extends PrimitiveProps<WritingSeed> {
  readonly content?: string;
  readonly title?: string;
}

/** Seed data for writing primitives */
export interface WritingSeed {
  readonly template?: string;
  readonly variables?: Readonly<Record<string, string>>;
}

/** Props for planning-related primitives. */
export interface PlanningPrimitiveProps<TItem = unknown> extends PrimitiveProps<PlanningSeed<TItem>> {
  readonly items?: readonly TItem[];
  readonly filter?: string;
}

/** Seed data for planning primitives */
export interface PlanningSeed<TItem = unknown> {
  readonly defaultItems?: readonly TItem[];
  readonly sortBy?: string;
}

/** Props for data-related primitives. */
export interface DataPrimitiveProps<TRow = Record<string, unknown>> extends PrimitiveProps<DataSeed<TRow>> {
  readonly data?: readonly TRow[];
  readonly columns?: readonly string[];
}

/** Seed data for data primitives */
export interface DataSeed<TRow = Record<string, unknown>> {
  readonly defaultData?: readonly TRow[];
  readonly schema?: Readonly<Record<string, 'string' | 'number' | 'boolean' | 'date'>>;
}
