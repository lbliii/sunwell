/**
 * Primitive Components Index (RFC-072)
 * 
 * Export all primitive components for dynamic rendering.
 */

// Code primitives
export { default as CodeEditor } from './CodeEditor.svelte';
export { default as Terminal } from './Terminal.svelte';
export { default as TestRunner } from './TestRunner.svelte';
export { default as DiffView } from './DiffView.svelte';
export { default as Preview } from './Preview.svelte';
export { default as Dependencies } from './Dependencies.svelte';

// Planning primitives
export { default as KanbanBoard } from './KanbanBoard.svelte';
export { default as Timeline } from './Timeline.svelte';
export { default as GoalTree } from './GoalTree.svelte';
export { default as TaskList } from './TaskList.svelte';
export { default as Calendar } from './Calendar.svelte';
export { default as Metrics } from './Metrics.svelte';

// Writing primitives
export { default as ProseEditor } from './ProseEditor.svelte';
export { default as Outline } from './Outline.svelte';
export { default as References } from './References.svelte';
export { default as WordCount } from './WordCount.svelte';

// Data primitives
export { default as DataTable } from './DataTable.svelte';
export { default as Chart } from './Chart.svelte';
export { default as QueryBuilder } from './QueryBuilder.svelte';
export { default as Summary } from './Summary.svelte';

// Universal primitives
export { default as MemoryPane } from './MemoryPane.svelte';
export { default as DAGView } from './DAGView.svelte';
export { default as BriefingCard } from './BriefingCard.svelte';

// Types
export type { PrimitiveProps, CodePrimitiveProps, WritingPrimitiveProps, PlanningPrimitiveProps, DataPrimitiveProps } from './types';

// Component map for dynamic rendering
export const componentMap: Record<string, any> = {
  // Code
  CodeEditor: () => import('./CodeEditor.svelte'),
  FileTree: () => import('../FileTree.svelte'),
  Terminal: () => import('./Terminal.svelte'),
  TestRunner: () => import('./TestRunner.svelte'),
  DiffView: () => import('./DiffView.svelte'),
  Preview: () => import('./Preview.svelte'),
  Dependencies: () => import('./Dependencies.svelte'),
  
  // Planning
  KanbanBoard: () => import('./KanbanBoard.svelte'),
  Timeline: () => import('./Timeline.svelte'),
  GoalTree: () => import('./GoalTree.svelte'),
  TaskList: () => import('./TaskList.svelte'),
  Calendar: () => import('./Calendar.svelte'),
  Metrics: () => import('./Metrics.svelte'),
  
  // Writing
  ProseEditor: () => import('./ProseEditor.svelte'),
  Outline: () => import('./Outline.svelte'),
  References: () => import('./References.svelte'),
  WordCount: () => import('./WordCount.svelte'),
  
  // Data
  DataTable: () => import('./DataTable.svelte'),
  Chart: () => import('./Chart.svelte'),
  QueryBuilder: () => import('./QueryBuilder.svelte'),
  Summary: () => import('./Summary.svelte'),
  
  // Universal
  MemoryPane: () => import('./MemoryPane.svelte'),
  InputBar: () => import('../InputBar.svelte'),
  DAGView: () => import('./DAGView.svelte'),
  BriefingCard: () => import('./BriefingCard.svelte'),
};
