/**
 * Store exports — Svelte 5 runes stores with clean API
 */

// App state
export { app, navigate, goHome, goToProject, goToPreview, goToPlanning, goToLibrary, goToInterface, setInitialized } from './app.svelte';

// Agent state
export { agent, runGoal, stopAgent, resetAgent, handleAgentEvent } from './agent.svelte';

// Project state
export {
  project,
  loadRecentProjects,
  scanProjects,
  resumeProject,
  openProject,
  createProject,
  setCurrentProject,
  closeProject,
  deleteProject,
  archiveProject,
  iterateProject,
  getProjectLearnings,
  getProjectTypeEmoji,
  getProjectTypeName,
} from './project.svelte';

// Layout state
export { layout, setMode, toggleSidebar } from './layout.svelte';

// DAG state
export {
  dag,
  setGraph,
  updateNode,
  completeNode,
  selectNode,
  hoverNode,
  setViewMode,
  setZoom,
  setPan,
  toggleShowCompleted,
  resetView,
  loadDemoGraph,
  clearGraph,
} from './dag.svelte';

// Prompts state
export { prompts, loadPrompts, savePrompt, removePrompt } from './prompts.svelte';

// Weakness state (RFC-063)
export {
  weakness,
  scanWeaknesses,
  selectWeakness,
  startExecution,
  executeQuickFix,
  clearSelection as clearWeaknessSelection,
  clearError as clearWeaknessError,
  clearAll as clearAllWeakness,
  updateExecution,
} from './weakness.svelte';

// Lens state (RFC-064)
export {
  lens,
  loadLenses,
  loadLensDetail,
  clearLensPreview,
  selectLens,
  setActiveLens,
  loadProjectLensConfig,
  saveProjectLensConfig,
  getLensByDomain,
  resetLensState,
  getLensesByDomain,
  getDomainIcon,
} from './lens.svelte';

// Run state (RFC-066)
export {
  runStore,
  setActiveSession,
  clearActiveSession,
  setPreviewUrl,
  markPortReady,
} from './run.svelte';

// Lens Library state (RFC-070)
export {
  lensLibrary,
  getFilteredEntries,
  getAvailableDomains,
  getDefaultLens,
  loadLibrary,
  selectLens as selectLibraryLens,
  openEditor,
  forkLens,
  deleteLens,
  setFilter,
  setDefaultLens,
  goToLibrary,
  loadVersions,
  rollbackLens,
  saveLens,
  clearError as clearLensLibraryError,
  resetLibrary,
} from './lensLibrary.svelte';

// Briefing state (RFC-071)
export {
  briefing,
  loadBriefing,
  hasBriefing,
  clearBriefing,
  resetBriefing,
  getStatusColor,
  getStatusEmoji,
  getStatusLabel,
  formatRelativeTime,
} from './briefing.svelte';

// Surface state (RFC-072)
export {
  surface,
  loadRegistry,
  composeSurface,
  markGoalCompleted,
  emitPrimitiveEvent,
  addPrimitive,
  removePrimitive,
  setArrangement,
  undoLayout,
  setLayout,
  clearError as clearSurfaceError,
  resetSurface,
  getPrimitivesByCategory,
  getPrimaryCapable,
  getSecondaryCapable,
  getContextualCapable,
  getCategoryIcon,
  getArrangementDescription,
} from './surface.svelte';

// Interface state (RFC-075)
export {
  interfaceState,
  processInput,
  setDataDir,
  clearHistory,
  resetInterface,
  getRecentMessages,
  hasActiveWorkspace,
  getCurrentWorkspace,
} from './interface.svelte';
