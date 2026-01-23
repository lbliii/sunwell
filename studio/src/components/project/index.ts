/**
 * Project-related components (Svelte 5)
 * 
 * RFC-106: Unified Project Surface
 * - ProjectOverview.svelte removed (merged into IdleState)
 * - New components: AnalysisSkeleton, EmptyPipelineState, CollapsibleSection,
 *   ProjectIdentity, PipelineSection, SuggestedAction, LastRunStatus
 */

// Main project state components
export { default as ProjectHeader } from './ProjectHeader.svelte';
export { default as WorkingState } from './WorkingState.svelte';
export { default as DoneState } from './DoneState.svelte';
export { default as ErrorState } from './ErrorState.svelte';
export { default as IdleState } from './IdleState.svelte';

// RFC-106: Unified project surface sub-components
export { default as AnalysisSkeleton } from './AnalysisSkeleton.svelte';
export { default as EmptyPipelineState } from './EmptyPipelineState.svelte';
export { default as CollapsibleSection } from './CollapsibleSection.svelte';
export { default as ProjectIdentity } from './ProjectIdentity.svelte';
export { default as PipelineSection } from './PipelineSection.svelte';
export { default as SuggestedAction } from './SuggestedAction.svelte';
export { default as LastRunStatus } from './LastRunStatus.svelte';