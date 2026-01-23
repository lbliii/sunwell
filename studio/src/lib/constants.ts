/**
 * Sunwell Studio — Constants
 * 
 * Typed constants for type-safe string literals throughout the application.
 * These replace magic strings and enable IDE autocompletion + refactoring.
 */

// ═══════════════════════════════════════════════════════════════
// AGENT STATUS
// ═══════════════════════════════════════════════════════════════

export const AgentStatus = {
  IDLE: 'idle',
  STARTING: 'starting',
  PLANNING: 'planning',
  RUNNING: 'running',
  DONE: 'done',
  ERROR: 'error',
} as const;

export type AgentStatus = (typeof AgentStatus)[keyof typeof AgentStatus];

// ═══════════════════════════════════════════════════════════════
// PLANNING PHASES
// ═══════════════════════════════════════════════════════════════

export const PlanningPhase = {
  GENERATING: 'generating',
  SCORING: 'scoring',
  REFINING: 'refining',
  COMPLETE: 'complete',
} as const;

export type PlanningPhase = (typeof PlanningPhase)[keyof typeof PlanningPhase];

// ═══════════════════════════════════════════════════════════════
// TASK STATUS
// ═══════════════════════════════════════════════════════════════

export const TaskStatus = {
  PENDING: 'pending',
  RUNNING: 'running',
  COMPLETE: 'complete',
  FAILED: 'failed',
} as const;

export type TaskStatus = (typeof TaskStatus)[keyof typeof TaskStatus];

// ═══════════════════════════════════════════════════════════════
// VIEW TABS
// ═══════════════════════════════════════════════════════════════

export const ViewTab = {
  PROJECT: 'project',  // RFC-106: Unified project surface (was PROGRESS)
  PIPELINE: 'pipeline',
  MEMORY: 'memory',
  WORKERS: 'workers',  // RFC-100: Multi-agent orchestration
  STATE_DAG: 'state_dag',  // RFC-100: Project health visualization
} as const;

export type ViewTab = (typeof ViewTab)[keyof typeof ViewTab];

// ═══════════════════════════════════════════════════════════════
// BUTTON VARIANTS
// ═══════════════════════════════════════════════════════════════

export const ButtonVariant = {
  PRIMARY: 'primary',
  SECONDARY: 'secondary',
  GHOST: 'ghost',
} as const;

export type ButtonVariant = (typeof ButtonVariant)[keyof typeof ButtonVariant];

// ═══════════════════════════════════════════════════════════════
// SIZE SCALE
// ═══════════════════════════════════════════════════════════════

export const Size = {
  SM: 'sm',
  MD: 'md',
  LG: 'lg',
} as const;

export type Size = (typeof Size)[keyof typeof Size];

// ═══════════════════════════════════════════════════════════════
// DAG NODE STATUS
// ═══════════════════════════════════════════════════════════════

export const DagNodeStatus = {
  PENDING: 'pending',
  READY: 'ready',
  RUNNING: 'running',
  COMPLETE: 'complete',
  FAILED: 'failed',
  BLOCKED: 'blocked',
} as const;

export type DagNodeStatus = (typeof DagNodeStatus)[keyof typeof DagNodeStatus];

// ═══════════════════════════════════════════════════════════════
// DAG NODE SOURCE
// ═══════════════════════════════════════════════════════════════

export const DagNodeSource = {
  AI: 'ai',
  HUMAN: 'human',
  EXTERNAL: 'external',
} as const;

export type DagNodeSource = (typeof DagNodeSource)[keyof typeof DagNodeSource];

// ═══════════════════════════════════════════════════════════════
// DAG VIEW MODE
// ═══════════════════════════════════════════════════════════════

export const DagViewMode = {
  DAG: 'dag',
  KANBAN: 'kanban',
  LIST: 'list',
} as const;

export type DagViewMode = (typeof DagViewMode)[keyof typeof DagViewMode];

// ═══════════════════════════════════════════════════════════════
// ROUTES
// ═══════════════════════════════════════════════════════════════

export const Route = {
  HOME: 'home',
  PROJECT: 'project',
  PROJECTS: 'projects',
  PREVIEW: 'preview',
  PLANNING: 'planning',
  LIBRARY: 'library',
  INTERFACE: 'interface',
  WRITER: 'writer',
  DEMO: 'demo',
  GALLERY: 'gallery',  // RFC-097: Component showcase
  EVALUATION: 'evaluation',  // RFC-098: Full-stack evaluation
} as const;

export type Route = (typeof Route)[keyof typeof Route];

// ═══════════════════════════════════════════════════════════════
// LAYOUT TYPE
// ═══════════════════════════════════════════════════════════════

export const LayoutType = {
  CODE: 'code',
  NOVEL: 'novel',
  SCREENPLAY: 'screenplay',
  GAME: 'game',
  GENERAL: 'general',
} as const;

export type LayoutType = (typeof LayoutType)[keyof typeof LayoutType];

// ═══════════════════════════════════════════════════════════════
// EXECUTION STATUS
// ═══════════════════════════════════════════════════════════════

export const ExecutionStatus = {
  NONE: 'none',
  COMPLETE: 'complete',
  INTERRUPTED: 'interrupted',
  FAILED: 'failed',
} as const;

export type ExecutionStatus = (typeof ExecutionStatus)[keyof typeof ExecutionStatus];

// ═══════════════════════════════════════════════════════════════
// RFC-074: INCREMENTAL SKIP REASONS
// ═══════════════════════════════════════════════════════════════

export const SkipReason = {
  UNCHANGED_SUCCESS: 'unchanged_success',
  NO_CACHE: 'no_cache',
  HASH_CHANGED: 'hash_changed',
  PREVIOUS_FAILED: 'previous_failed',
  FORCE_RERUN: 'force_rerun',
  DEPENDENCY_CHANGED: 'dependency_changed',
} as const;

export type SkipReason = (typeof SkipReason)[keyof typeof SkipReason];
