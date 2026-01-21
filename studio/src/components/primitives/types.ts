/**
 * Primitive Component Types (RFC-072)
 * 
 * Common interface for all surface primitives.
 */

import type { PrimitiveSize } from '$lib/types';

/** Base props for all primitives. */
export interface PrimitiveProps {
  /** Primitive size mode */
  size: PrimitiveSize;
  
  /** Seed content from composition */
  seed?: Record<string, unknown>;
  
  /** Additional props from composition */
  [key: string]: unknown;
}

/** Props for code-related primitives. */
export interface CodePrimitiveProps extends PrimitiveProps {
  file?: string;
  language?: string;
}

/** Props for writing-related primitives. */
export interface WritingPrimitiveProps extends PrimitiveProps {
  content?: string;
  title?: string;
}

/** Props for planning-related primitives. */
export interface PlanningPrimitiveProps extends PrimitiveProps {
  items?: unknown[];
  filter?: string;
}

/** Props for data-related primitives. */
export interface DataPrimitiveProps extends PrimitiveProps {
  data?: unknown[];
  columns?: string[];
}
