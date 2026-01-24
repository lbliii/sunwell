/**
 * Project Store — manages current project state (Svelte 5 runes)
 * 
 * Extended in RFC-079 with universal project analysis support.
 * Extended in RFC-108 with automatic codebase indexing.
 * RFC-113: Migrated from Tauri invoke to HTTP API.
 */

import type { 
  Project, RecentProject, ProjectType, ProjectStatus, ProjectManageResult, ProjectLearnings,
  ProjectAnalysis, MonorepoAnalysis, AnalysisProjectType,
} from '$lib/types';
import { apiGet, apiPost } from '$lib/socket';
import { initIndexing, stopIndexing } from './indexing.svelte';

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

let _current = $state<Project | null>(null);
let _recent = $state<RecentProject[]>([]);
let _discovered = $state<ProjectStatus[]>([]);
let _isLoading = $state(false);
let _isScanning = $state(false);
let _error = $state<string | null>(null);

// RFC-079: Project analysis state
let _analysis = $state<ProjectAnalysis | null>(null);
let _isAnalyzing = $state(false);
let _analysisError = $state<string | null>(null);

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const project = {
  get current() { return _current; },
  get recent() { return _recent; },
  get discovered() { return _discovered; },
  get isLoading() { return _isLoading; },
  get isScanning() { return _isScanning; },
  get error() { return _error; },
  // Computed
  get hasProject() { return _current !== null; },
  get projectType(): ProjectType { return _current?.project_type ?? 'general'; },
  get isCodeProject() { return (_current?.project_type ?? '').startsWith('code_'); },
  get isCreativeProject() { return ['novel', 'screenplay', 'game_dialogue'].includes(_current?.project_type ?? ''); },
  // RFC-079: Analysis state
  get analysis() { return _analysis; },
  get isAnalyzing() { return _isAnalyzing; },
  get analysisError() { return _analysisError; },
  get hasAnalysis() { return _analysis !== null; },
  get analysisProjectType(): AnalysisProjectType | null { return _analysis?.project_type ?? null; },
  get suggestedWorkspace() { return _analysis?.suggested_workspace_primary ?? 'CodeEditor'; },
  get confidence() { return _analysis?.confidence ?? 0; },
  get confidenceLevel() { return _analysis?.confidence_level ?? 'low'; },
};

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

export async function loadRecentProjects(): Promise<void> {
  // Prevent concurrent loads
  if (_isLoading) return;

  try {
    _isLoading = true;
    _error = null;
    const result = await apiGet<{ recent: RecentProject[] }>('/api/project/recent');
    _recent = result.recent || [];
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
  } finally {
    _isLoading = false;
  }
}

export async function scanProjects(): Promise<void> {
  // Prevent concurrent scans
  if (_isScanning) return;

  try {
    _isScanning = true;
    _error = null;
    const result = await apiGet<{ projects: ProjectStatus[] }>('/api/project/scan');
    _discovered = result.projects || [];
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
  } finally {
    _isScanning = false;
  }
}

export async function resumeProject(path: string): Promise<boolean> {
  try {
    _isLoading = true;
    _error = null;
    const result = await apiPost<{ success: boolean; message: string }>('/api/project/resume', { path });
    return result.success;
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    return false;
  } finally {
    _isLoading = false;
  }
}

export async function openProject(path: string): Promise<Project | null> {
  try {
    _isLoading = true;
    _error = null;
    const proj = await apiPost<Project>('/api/project/open', { path });
    _current = proj;
    
    // RFC-108: Start background codebase indexing
    initIndexing(path);
    
    return proj;
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    return null;
  } finally {
    _isLoading = false;
  }
}

export function createProject(goal: string): Project {
  const name = goal.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 30) || 'new-project';
  const proj: Project = { id: `temp-${Date.now()}`, path: `./${name}`, name, project_type: 'general', description: goal, files_count: 0 };
  _current = proj;
  return proj;
}

export function setCurrentProject(proj: Project | null): void {
  _current = proj;
}

export function closeProject(): void {
  _current = null;
  // RFC-108: Stop codebase indexing when project is closed
  stopIndexing();
}

export async function deleteProject(path: string): Promise<ProjectManageResult> {
  try {
    _isLoading = true;
    _error = null;
    const result = await apiPost<ProjectManageResult>('/api/project/delete', { path });
    if (result.success) await scanProjects();
    return result;
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    _error = msg;
    return { success: false, message: msg, new_path: null };
  } finally {
    _isLoading = false;
  }
}

export async function archiveProject(path: string): Promise<ProjectManageResult> {
  try {
    _isLoading = true;
    _error = null;
    const result = await apiPost<ProjectManageResult>('/api/project/archive', { path });
    if (result.success) await scanProjects();
    return result;
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    _error = msg;
    return { success: false, message: msg, new_path: null };
  } finally {
    _isLoading = false;
  }
}

export async function iterateProject(path: string, newGoal?: string): Promise<ProjectManageResult> {
  try {
    _isLoading = true;
    _error = null;
    const result = await apiPost<ProjectManageResult>('/api/project/iterate', { path, new_goal: newGoal ?? null });
    if (result.success) await scanProjects();
    return result;
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    _error = msg;
    return { success: false, message: msg, new_path: null };
  } finally {
    _isLoading = false;
  }
}

export async function getProjectLearnings(path: string): Promise<ProjectLearnings | null> {
  try {
    return await apiGet<ProjectLearnings>(`/api/project/learnings?path=${encodeURIComponent(path)}`);
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    return null;
  }
}

export function getProjectTypeEmoji(type: ProjectType): string {
  const icons: Record<ProjectType, string> = {
    code_python: '.py', code_js: '.js', code_rust: '.rs', code_go: '.go',
    code_web: 'web', code_cli: 'cli', novel: 'txt', screenplay: 'scr',
    game_dialogue: 'dlg', general: '---',
  };
  return icons[type] ?? '---';
}

export function getProjectTypeName(type: ProjectType): string {
  const names: Record<ProjectType, string> = {
    code_python: 'Python', code_js: 'JavaScript', code_rust: 'Rust', code_go: 'Go',
    code_web: 'Web App', code_cli: 'CLI', novel: 'Novel', screenplay: 'Screenplay',
    game_dialogue: 'Game Dialogue', general: 'Project',
  };
  return names[type] ?? 'Project';
}

// ═══════════════════════════════════════════════════════════════
// RFC-079: PROJECT ANALYSIS ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Analyze a project to understand its intent and state (RFC-079).
 * 
 * This provides universal project understanding including:
 * - Project type classification (code, docs, data, planning, creative)
 * - Goal inference and pipeline state
 * - Suggested next actions
 * - Workspace recommendations
 */
export async function analyzeProject(path: string, fresh = false): Promise<ProjectAnalysis | null> {
  if (_isAnalyzing) return _analysis;

  try {
    _isAnalyzing = true;
    _analysisError = null;
    _analysis = await apiPost<ProjectAnalysis>('/api/project/analyze', { path, fresh });
    return _analysis;
  } catch (e) {
    _analysisError = e instanceof Error ? e.message : String(e);
    return null;
  } finally {
    _isAnalyzing = false;
  }
}

/**
 * Check if a path is a monorepo and get sub-projects (RFC-079).
 */
export async function checkMonorepo(path: string): Promise<MonorepoAnalysis | null> {
  try {
    return await apiPost<MonorepoAnalysis>('/api/project/monorepo', { path });
  } catch (e) {
    _analysisError = e instanceof Error ? e.message : String(e);
    return null;
  }
}

/**
 * Clear the current analysis state.
 */
export function clearAnalysis(): void {
  _analysis = null;
  _analysisError = null;
}

/**
 * Get the emoji for an RFC-079 analysis project type.
 */
export function getAnalysisTypeEmoji(type: AnalysisProjectType): string {
  const emojis: Record<AnalysisProjectType, string> = {
    code: '💻',
    documentation: '📚',
    data: '📊',
    planning: '📋',
    creative: '✍️',
    mixed: '🔀',
  };
  return emojis[type] ?? '📁';
}

/**
 * Get the display name for an RFC-079 analysis project type.
 */
export function getAnalysisTypeName(type: AnalysisProjectType): string {
  const names: Record<AnalysisProjectType, string> = {
    code: 'Code',
    documentation: 'Documentation',
    data: 'Data',
    planning: 'Planning',
    creative: 'Creative',
    mixed: 'Mixed',
  };
  return names[type] ?? 'Project';
}
