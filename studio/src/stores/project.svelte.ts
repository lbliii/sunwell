/**
 * Project Store — manages current project state (Svelte 5 runes)
 * 
 * Extended in RFC-079 with universal project analysis support.
 * Extended in RFC-108 with automatic codebase indexing.
 */

import type { 
  Project, RecentProject, ProjectType, ProjectStatus, ProjectManageResult, ProjectLearnings,
  ProjectAnalysis, MonorepoAnalysis, AnalysisProjectType,
} from '$lib/types';
import { initIndexing, stopIndexing } from './indexing.svelte';

const DEMO_MODE = false;

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
  
  if (DEMO_MODE) {
    _recent = [
      { path: '/demo/flask-api', name: 'flask-api', last_opened: Date.now() - 3600000, project_type: 'code_python', description: '' },
      { path: '/demo/react-app', name: 'react-app', last_opened: Date.now() - 86400000, project_type: 'code_web', description: '' },
    ];
    return;
  }

  try {
    _isLoading = true;
    _error = null;
    const { invoke } = await import('@tauri-apps/api/core');
    _recent = await invoke<RecentProject[]>('get_recent_projects');
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
  } finally {
    _isLoading = false;
  }
}

export async function scanProjects(): Promise<void> {
  // Prevent concurrent scans
  if (_isScanning) return;
  
  if (DEMO_MODE) {
    _discovered = [
      { 
        id: 'demo-forum-app', path: '/demo/forum-app', display_path: '~/Sunwell/projects/forum-app',
        name: 'forum-app', status: 'interrupted', last_goal: 'create a forum app',
        tasks_completed: 4, tasks_total: 7, tasks: null,
        last_activity: new Date(Date.now() - 300000).toISOString(),
      },
      { 
        id: 'demo-blog-api', path: '/demo/blog-api', display_path: '~/Sunwell/projects/blog-api',
        name: 'blog-api', status: 'complete', last_goal: 'build a blog API',
        tasks_completed: 5, tasks_total: 5, tasks: null,
        last_activity: new Date(Date.now() - 3600000).toISOString(),
      },
    ];
    return;
  }

  try {
    _isScanning = true;
    _error = null;
    const { invoke } = await import('@tauri-apps/api/core');
    _discovered = await invoke<ProjectStatus[]>('scan_projects');
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
  } finally {
    _isScanning = false;
  }
}

export async function resumeProject(path: string): Promise<boolean> {
  if (DEMO_MODE) return true;

  try {
    _isLoading = true;
    _error = null;
    const { invoke } = await import('@tauri-apps/api/core');
    const result = await invoke<{ success: boolean; message: string }>('resume_project', { path });
    return result.success;
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    return false;
  } finally {
    _isLoading = false;
  }
}

export async function openProject(path: string): Promise<Project | null> {
  if (DEMO_MODE) {
    const proj: Project = {
      id: `demo-${path.replace(/\//g, '-')}`,
      path,
      name: path.split('/').pop() || 'project',
      project_type: 'code_python',
      description: 'Demo project',
      files_count: 42,
    };
    _current = proj;
    return proj;
  }

  try {
    _isLoading = true;
    _error = null;
    const { invoke } = await import('@tauri-apps/api/core');
    const proj = await invoke<Project>('open_project', { path });
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
  if (DEMO_MODE) {
    _discovered = _discovered.filter(p => p.path !== path);
    return { success: true, message: 'Deleted project', new_path: null };
  }

  try {
    _isLoading = true;
    _error = null;
    const { invoke } = await import('@tauri-apps/api/core');
    const result = await invoke<ProjectManageResult>('delete_project', { path });
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
  if (DEMO_MODE) {
    _discovered = _discovered.filter(p => p.path !== path);
    return { success: true, message: 'Archived project', new_path: '~/Sunwell/archived/demo' };
  }

  try {
    _isLoading = true;
    _error = null;
    const { invoke } = await import('@tauri-apps/api/core');
    const result = await invoke<ProjectManageResult>('archive_project', { path });
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
  if (DEMO_MODE) {
    const baseName = path.split('/').pop() || 'project';
    return { success: true, message: `Created ${baseName}-v2`, new_path: `/demo/${baseName}-v2` };
  }

  try {
    _isLoading = true;
    _error = null;
    const { invoke } = await import('@tauri-apps/api/core');
    const result = await invoke<ProjectManageResult>('iterate_project', { path, newGoal: newGoal ?? null });
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
  if (DEMO_MODE) {
    return {
      original_goal: 'create a forum app',
      decisions: ['Used Flask', 'SQLite for dev'],
      failures: ['Redis was overkill'],
      completed_tasks: ['Set up Flask', 'Create models'],
      pending_tasks: ['User auth', 'Tests'],
    };
  }

  try {
    const { invoke } = await import('@tauri-apps/api/core');
    return await invoke<ProjectLearnings>('get_project_learnings', { path });
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

  if (DEMO_MODE) {
    _analysis = {
      name: path.split('/').pop() || 'project',
      path,
      project_type: 'code',
      project_subtype: 'svelte-app',
      goals: [
        { id: 'goal-1', title: 'Implement core features', description: '', priority: 'high', status: 'inferred', confidence: 0.8 },
        { id: 'goal-2', title: 'Add tests', description: '', priority: 'medium', status: 'inferred', confidence: 0.7 },
      ],
      pipeline: [
        { id: 'goal-1', title: 'Implement core features', status: 'in_progress', description: '' },
        { id: 'goal-2', title: 'Add tests', status: 'pending', description: '' },
      ],
      current_step: 'goal-1',
      completion_percent: 0.3,
      suggested_action: { action_type: 'continue_work', description: 'Continue: Implement core features', goal_id: 'goal-1', command: null, confidence: 0.85 },
      suggested_workspace_primary: 'CodeEditor',
      dev_command: { command: 'npm run dev', description: 'Start Vite dev server', prerequisites: [], expected_url: 'http://localhost:5173' },
      confidence: 0.85,
      confidence_level: 'high',
      detection_signals: ['has_package_json', 'svelte_dependency'],
      analyzed_at: new Date().toISOString(),
      classification_source: 'heuristic',
    };
    return _analysis;
  }

  try {
    _isAnalyzing = true;
    _analysisError = null;
    const { invoke } = await import('@tauri-apps/api/core');
    _analysis = await invoke<ProjectAnalysis>('analyze_project', { path, fresh });
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
  if (DEMO_MODE) {
    return { is_monorepo: false, sub_projects: [] };
  }

  try {
    const { invoke } = await import('@tauri-apps/api/core');
    return await invoke<MonorepoAnalysis>('analyze_monorepo', { path });
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
