/**
 * Component exports — Holy Light Design System
 */

// ═══════════════════════════════════════════════════════════════
// FORM COMPONENTS — Standardized inputs with Holy Light styling
// ═══════════════════════════════════════════════════════════════
export * from './form';

// ═══════════════════════════════════════════════════════════════
// TYPOGRAPHY — Consistent text components
// ═══════════════════════════════════════════════════════════════
export * from './typography';

// ═══════════════════════════════════════════════════════════════
// CORE COMPONENTS
// ═══════════════════════════════════════════════════════════════
export { default as BriefingPanel } from './BriefingPanel.svelte';
export { default as Button } from './Button.svelte';
export { default as FileTree } from './FileTree.svelte';
export { default as FluidInput } from './FluidInput.svelte';
export { default as InputBar } from './InputBar.svelte';
export { default as LensLibrary } from './LensLibrary.svelte';
export { default as Logo } from './Logo.svelte';
export { default as Modal } from './Modal.svelte';
export { default as ProjectManager } from './ProjectManager.svelte';
export * from './project-manager';
export { default as MemoryView } from './MemoryView.svelte';
export { default as MemoryGraph } from './MemoryGraph.svelte';
export { default as ChunkViewer } from './ChunkViewer.svelte';
export { default as Panel } from './Panel.svelte';
export { default as Progress } from './Progress.svelte';
export { default as RecentProjects } from './RecentProjects.svelte';
export { default as RisingMotes } from './RisingMotes.svelte';
export { default as MouseMotes } from './MouseMotes.svelte';
export { default as ProviderSelector } from './ProviderSelector.svelte';
export { default as RunButton } from './RunButton.svelte';
export { default as RunAnalysisView } from './RunAnalysisView.svelte';
export { default as Tabs } from './Tabs.svelte';

// Surface (RFC-072)
export { default as Surface } from './Surface.svelte';

// Blocks (RFC-080) — Universal surface elements
export { default as BlockSurface } from './BlockSurface.svelte';
export * from './blocks';

// Home-specific components (RFC-080)
export * from './home';

// Fluid Canvas (RFC-082) — Spring physics, gestures, spatial memory
export { default as Canvas } from './Canvas.svelte';
export { default as GestureProvider } from './GestureProvider.svelte';
export { default as MinimizedDock } from './MinimizedDock.svelte';
export { default as SkeletonLayout } from './SkeletonLayout.svelte';
export { default as AmbientSuggestion } from './AmbientSuggestion.svelte';
export { default as FluidCanvasDemo } from './FluidCanvasDemo.svelte';

// UI primitives (Unicode-based)
export { Spinner, Progress as UnicodeProgress } from './ui';
export * from './weakness';
export * from './primitives';

// Writer Environment (RFC-086) — Universal writing surface
export * from './writer';

// Demo (RFC-095) — The Prism Principle demonstration
export * from './demo';