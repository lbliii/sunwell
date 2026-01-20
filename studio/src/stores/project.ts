/**
 * Project Store — manages current project state
 */

import { writable, derived } from 'svelte/store';
import type { Project, RecentProject, ProjectType } from '$lib/types';

// RFC-053: Demo mode - same as agent store
// Set to false to use real project discovery
const DEMO_MODE = false;

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

export const currentProject = writable<Project | null>(null);
export const recentProjects = writable<RecentProject[]>([]);
export const isLoading = writable(false);
export const error = writable<string | null>(null);

// ═══════════════════════════════════════════════════════════════
// DERIVED
// ═══════════════════════════════════════════════════════════════

export const hasProject = derived(currentProject, $p => $p !== null);

export const projectType = derived(
  currentProject,
  $p => $p?.project_type ?? 'general'
);

export const isCodeProject = derived(
  projectType,
  $t => $t.startsWith('code_')
);

export const isCreativeProject = derived(
  projectType,
  $t => ['novel', 'screenplay', 'game_dialogue'].includes($t)
);

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Load recent projects from storage.
 */
export async function loadRecentProjects(): Promise<void> {
  if (DEMO_MODE) {
    // Return demo projects
    recentProjects.set([
      { path: '/demo/flask-api', name: 'flask-api', last_opened: Date.now() - 3600000, project_type: 'code_python' },
      { path: '/demo/react-app', name: 'react-app', last_opened: Date.now() - 86400000, project_type: 'code_web' },
      { path: '/demo/rust-cli', name: 'rust-cli', last_opened: Date.now() - 172800000, project_type: 'code_rust' },
    ]);
    return;
  }

  try {
    isLoading.set(true);
    error.set(null);
    
    const { invoke } = await import('@tauri-apps/api/core');
    const projects = await invoke<RecentProject[]>('get_recent_projects');
    recentProjects.set(projects);
  } catch (e) {
    error.set(e instanceof Error ? e.message : String(e));
  } finally {
    isLoading.set(false);
  }
}

/**
 * Open a project from a path.
 */
export async function openProject(path: string): Promise<Project | null> {
  if (DEMO_MODE) {
    const project: Project = {
      path,
      name: path.split('/').pop() || 'project',
      project_type: 'code_python',
      description: 'Demo project',
      files_count: 42,
    };
    currentProject.set(project);
    return project;
  }

  try {
    isLoading.set(true);
    error.set(null);
    
    const { invoke } = await import('@tauri-apps/api/core');
    const project = await invoke<Project>('open_project', { path });
    currentProject.set(project);
    return project;
  } catch (e) {
    error.set(e instanceof Error ? e.message : String(e));
    return null;
  } finally {
    isLoading.set(false);
  }
}

/**
 * Create a new project with the given goal.
 */
export function createProject(goal: string): Project {
  // Generate a project name from the goal
  const name = goal
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 30) || 'new-project';

  const project: Project = {
    path: `./${name}`,
    name,
    project_type: 'general',
    description: goal,
    files_count: 0,
  };

  currentProject.set(project);
  return project;
}

/**
 * Close the current project.
 */
export function closeProject(): void {
  currentProject.set(null);
}

/**
 * Get emoji for project type.
 */
export function getProjectTypeEmoji(type: ProjectType): string {
  const emojis: Record<ProjectType, string> = {
    code_python: '🐍',
    code_js: '📦',
    code_rust: '🦀',
    code_go: '🐹',
    code_web: '🌐',
    code_cli: '⌨️',
    novel: '📖',
    screenplay: '🎬',
    game_dialogue: '🎮',
    general: '📁',
  };
  return emojis[type] ?? '📁';
}

/**
 * Get display name for project type.
 */
export function getProjectTypeName(type: ProjectType): string {
  const names: Record<ProjectType, string> = {
    code_python: 'Python',
    code_js: 'JavaScript',
    code_rust: 'Rust',
    code_go: 'Go',
    code_web: 'Web App',
    code_cli: 'CLI',
    novel: 'Novel',
    screenplay: 'Screenplay',
    game_dialogue: 'Game Dialogue',
    general: 'Project',
  };
  return names[type] ?? 'Project';
}
