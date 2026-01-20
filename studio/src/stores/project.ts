/**
 * Project Store — manages current project state
 */

import { writable, derived } from 'svelte/store';
import type { Project, RecentProject, ProjectType, ProjectStatus } from '$lib/types';

// RFC-053: Demo mode - same as agent store
// Set to false to use real project discovery
const DEMO_MODE = false;

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

export const currentProject = writable<Project | null>(null);
export const recentProjects = writable<RecentProject[]>([]);
export const discoveredProjects = writable<ProjectStatus[]>([]);
export const isLoading = writable(false);
export const isScanning = writable(false);
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
      { path: '/demo/flask-api', name: 'flask-api', last_opened: Date.now() - 3600000, project_type: 'code_python', description: '' },
      { path: '/demo/react-app', name: 'react-app', last_opened: Date.now() - 86400000, project_type: 'code_web', description: '' },
      { path: '/demo/rust-cli', name: 'rust-cli', last_opened: Date.now() - 172800000, project_type: 'code_rust', description: '' },
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
 * Scan ~/Sunwell/projects/ for all projects with status.
 */
export async function scanProjects(): Promise<void> {
  if (DEMO_MODE) {
    // Return demo projects with various states
    discoveredProjects.set([
      { 
        path: '/demo/forum-app', 
        display_path: '~/Sunwell/projects/forum-app',
        name: 'forum-app', 
        status: 'interrupted',
        last_goal: 'create a forum app with posts and comments',
        tasks_completed: 4,
        tasks_total: 7,
        tasks: [
          { id: '1', description: 'Set up Flask application structure', completed: true },
          { id: '2', description: 'Create database models for posts', completed: true },
          { id: '3', description: 'Create database models for comments', completed: true },
          { id: '4', description: 'Implement CRUD routes for posts', completed: true },
          { id: '5', description: 'Implement CRUD routes for comments', completed: false },
          { id: '6', description: 'Add user authentication', completed: false },
          { id: '7', description: 'Write tests', completed: false },
        ],
        last_activity: new Date(Date.now() - 300000).toISOString(),
      },
      { 
        path: '/demo/blog-api', 
        display_path: '~/Sunwell/projects/blog-api',
        name: 'blog-api', 
        status: 'complete',
        last_goal: 'build a blog API',
        tasks_completed: 5,
        tasks_total: 5,
        tasks: [
          { id: '1', description: 'Initialize FastAPI project', completed: true },
          { id: '2', description: 'Create post models', completed: true },
          { id: '3', description: 'Implement REST endpoints', completed: true },
          { id: '4', description: 'Add SQLite database', completed: true },
          { id: '5', description: 'Write unit tests', completed: true },
        ],
        last_activity: new Date(Date.now() - 3600000).toISOString(),
      },
      { 
        path: '/demo/cli-tool', 
        display_path: '~/Sunwell/projects/cli-tool',
        name: 'cli-tool', 
        status: 'none',
        last_goal: null,
        tasks_completed: null,
        tasks_total: null,
        tasks: null,
        last_activity: new Date(Date.now() - 86400000).toISOString(),
      },
    ]);
    return;
  }

  try {
    isScanning.set(true);
    error.set(null);
    
    const { invoke } = await import('@tauri-apps/api/core');
    const projects = await invoke<ProjectStatus[]>('scan_projects');
    discoveredProjects.set(projects);
  } catch (e) {
    error.set(e instanceof Error ? e.message : String(e));
  } finally {
    isScanning.set(false);
  }
}

/**
 * Resume an interrupted project.
 */
export async function resumeProject(path: string): Promise<boolean> {
  if (DEMO_MODE) {
    console.log('Demo: Resuming project at', path);
    return true;
  }

  try {
    isLoading.set(true);
    error.set(null);
    
    const { invoke } = await import('@tauri-apps/api/core');
    const result = await invoke<{ success: boolean; message: string }>('resume_project', { path });
    return result.success;
  } catch (e) {
    error.set(e instanceof Error ? e.message : String(e));
    return false;
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
  const icons: Record<ProjectType, string> = {
    code_python: '.py',
    code_js: '.js',
    code_rust: '.rs',
    code_go: '.go',
    code_web: 'web',
    code_cli: 'cli',
    novel: 'txt',
    screenplay: 'scr',
    game_dialogue: 'dlg',
    general: '---',
  };
  return icons[type] ?? '---';
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
