/**
 * Store exports — Svelte 5 runes stores with clean API
 */

// App state
export { app, navigate, goHome, goToProject, goToProjects, goToPreview, goToPlanning, goToLibrary, goToInterface, goToWriter, goToEvaluation, setInitialized } from './app.svelte';

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
  updateExecution as updateWeaknessExecution,
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
  backToList,
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

// Home state (RFC-080)
export {
  homeState,
  routeInput,
  executeBlockAction,
  clearResponse,
  clearConversationHistory,
  setHomeDataDir,
  resetHome,
  isViewResponse,
  isActionResponse,
  isConversationResponse,
  isWorkspaceResponse,
  isHybridResponse,
} from './home.svelte';

// Naaru unified state (RFC-083)
export {
  naaruState,
  process,
  subscribeToEvents,
  getConvergenceSlot,
  cancel,
  clearHistory as clearNaaruHistory,
  resetNaaru,
  getResponseText,
  hasComposition,
  getRouteType,
  isConversationRoute,
  isActionRoute,
  isViewRoute,
  isWorkspaceRoute,
  isHybridRoute,
  type ProcessMode,
  type PageType,
  type NaaruEventType,
  type ProcessInput,
  type ProcessOutput,
  type CompositionSpec,
  type RoutingDecision,
  type NaaruEvent,
  type ConvergenceSlot,
} from './naaru.svelte';

// Composition state (RFC-082)
export {
  compositionState,
  predict,
  setComposition,
  clearComposition,
  resetComposition,
  hasHighConfidencePrediction,
  getPanels,
  getInputMode,
  getSuggestedTools,
  analyzePatterns,
  type CompositionSpec as CompositionSpecType,
  type PanelSpec,
  type PageType as CompositionPageType,
  type InputMode,
  type CompositionSource,
} from './composition.svelte';

// Pattern state (RFC-082 Phase 6)
export {
  patternState,
  trackActivity,
  boostProjectAffinity,
  setLayoutPreference,
  predictActivity,
  getTopProjects,
  getRecommendedLayout,
  predictNextActivity,
  isCommonTransition,
  resetPatterns,
  getPatternStats,
  type ActivityType,
  type HourRange,
  type LayoutConfig,
  type StateTransition,
  type UserPattern,
} from './patterns.svelte';

// Suggestion state (RFC-082 Phase 6)
export {
  suggestionState,
  generateSuggestions,
  dismissSuggestion,
  dismissAll,
  acceptSuggestion,
  setSuggestionsEnabled,
  clearDismissed,
  getTopSuggestion,
  type Suggestion,
  type SuggestionType,
  type SuggestionContext,
} from './suggestions.svelte';

// Workflow state (RFC-086)
export {
  workflowState,
  routeIntent,
  startWorkflow,
  stopWorkflow,
  resumeWorkflow,
  skipStep,
  loadChains,
  listActiveWorkflows,
  updateExecution,
  clearWorkflow,
  resetWorkflow,
  type WorkflowTier,
  type IntentCategory,
  type StepStatus,
  type WorkflowStatus,
  type WorkflowStep,
  type WorkflowChain,
  type WorkflowExecution,
  type Intent,
} from './workflow.svelte';

// Writer state (RFC-086)
export {
  writerState,
  toggleView,
  setViewMode as setWriterViewMode,
  loadDocument,
  updateContent,
  saveDocument,
  detectDiataxis,
  validateDocument,
  dismissWarning,
  fixAllIssues,
  setLens,
  executeSkill,
  setSelection,
  hideActionMenu,
  resetWriter,
  clearError as clearWriterError,
  type ViewMode,
  type DiataxisType,
  type DiataxisSignal,
  type DiataxisDetection,
  type DiataxisWarning,
  type ValidationWarning,
  type LensSkill,
  type SelectionContext,
} from './writer.svelte';

// Skill Graph state (RFC-087)
export {
  skillGraphState,
  handleSkillGraphResolved,
  handleSkillWaveStart,
  handleSkillWaveComplete,
  handleSkillCacheHit,
  handleSkillExecuteStart,
  handleSkillExecuteComplete,
  resetSkillGraph,
  getWavesWithSkills,
  getStatusCounts,
  getRiskCounts,
  type RiskLevel,
  type SkillNode,
  type SkillWave,
  type SkillGraphState,
} from './skill-graph.svelte';

// Settings state (RFC-Cloud-Model-Parity)
export {
  settings,
  setProvider,
  setAutoLens,
  getRunProvider,
  type ModelProvider,
  type Settings,
} from './settings.svelte';

// Project Manager state (RFC-096)
export {
  projectManager,
  getFilteredProjects,
  getProjectStats,
  isSelected,
  loadProjects,
  selectProject,
  toggleSelection,
  selectAll,
  clearSelection,
  openProjectAction,
  resumeProjectAction,
  iterateProjectAction,
  archiveProject as archiveProjectFromManager,
  deleteProject as deleteProjectFromManager,
  archiveSelected,
  deleteSelected,
  setFilter as setProjectFilter,
  setSort as setProjectSort,
  toggleSortDirection as toggleProjectSortDirection,
  setSearch as setProjectSearch,
  setSearchImmediate as setProjectSearchImmediate,
  showDetail,
  backToList as backToProjectList,
  setFocusedIndex,
  focusUp,
  focusDown,
  clearError as clearProjectManagerError,
  resetManager,
  type ProjectView,
  type ProjectSort,
  type ProjectFilter,
} from './projectManager.svelte';

// Evaluation state (RFC-098)
export {
  evaluation,
  loadTasks as loadEvalTasks,
  loadHistory as loadEvalHistory,
  loadStats as loadEvalStats,
  setTask as setEvalTask,
  setModel as setEvalModel,
  setLens as setEvalLens,
  runEvaluation,
  reset as resetEvaluation,
  type EvalTask,
  type EvalPhase,
  type EvalStats,
  type EvaluationRun,
  type FullStackScore,
} from './evaluation.svelte';
