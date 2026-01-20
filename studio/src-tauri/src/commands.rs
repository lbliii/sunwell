//! Tauri IPC commands — interface between frontend and Rust backend.

use crate::agent::AgentBridge;
use crate::preview::PreviewManager;
use crate::project::{Project, ProjectDetector, RecentProject};
use crate::workspace::{
    create_recent_project, default_workspace_root, ensure_workspace_exists,
    extract_project_name, resolve_workspace, shorten_path, slugify,
    RecentProjectsStore, ResolutionSource, WorkspaceResult,
};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::sync::Mutex;
use tauri::State;

/// Application state shared across commands.
pub struct AppState {
    pub agent: Mutex<AgentBridge>,
    pub preview: Mutex<PreviewManager>,
    pub detector: ProjectDetector,
    pub current_project: Mutex<Option<Project>>,
    pub recent_projects: Mutex<RecentProjectsStore>,
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            agent: Mutex::new(AgentBridge::new()),
            preview: Mutex::new(PreviewManager::new()),
            detector: ProjectDetector::new(),
            current_project: Mutex::new(None),
            recent_projects: Mutex::new(RecentProjectsStore::load()),
        }
    }
}

/// Result of running a goal.
#[derive(Debug, Serialize, Deserialize)]
pub struct RunGoalResult {
    pub success: bool,
    pub message: String,
    pub workspace_path: String,
}

/// Workspace resolution info for frontend.
#[derive(Debug, Serialize, Deserialize)]
pub struct WorkspaceInfo {
    pub path: String,
    pub display_path: String,
    pub source: String,
    pub confidence: f64,
    pub needs_confirmation: bool,
    pub exists: bool,
    pub project_name: Option<String>,
}

impl From<WorkspaceResult> for WorkspaceInfo {
    fn from(result: WorkspaceResult) -> Self {
        Self {
            path: result.path.to_string_lossy().to_string(),
            display_path: shorten_path(&result.path),
            source: match result.source {
                ResolutionSource::Explicit => "explicit".to_string(),
                ResolutionSource::Detected => "detected".to_string(),
                ResolutionSource::Default => "default".to_string(),
            },
            confidence: result.confidence,
            needs_confirmation: result.needs_confirmation(),
            exists: result.exists,
            project_name: result.project_name,
        }
    }
}

/// Resolve workspace for a goal (used by frontend before running).
#[tauri::command]
pub async fn resolve_workspace_for_goal(
    goal: String,
    explicit_path: Option<String>,
) -> Result<WorkspaceInfo, String> {
    let explicit = explicit_path.map(PathBuf::from);
    let project_name = extract_project_name(&goal);

    let result = resolve_workspace(
        explicit.as_deref(),
        project_name.as_deref(),
    );

    Ok(result.into())
}

/// Get the default workspace location.
#[tauri::command]
pub async fn get_default_workspace() -> Result<String, String> {
    let root = default_workspace_root();
    Ok(shorten_path(&root))
}

/// Create a new project directory.
#[tauri::command]
pub async fn create_project(
    state: State<'_, AppState>,
    path: String,
    name: String,
) -> Result<Project, String> {
    let path = PathBuf::from(&path);

    // Ensure directory exists
    ensure_workspace_exists(&path)
        .map_err(|e| format!("Failed to create project directory: {}", e))?;

    // Detect project type
    let project = state.detector.detect(&path)?;

    // Update current project
    let mut current = state.current_project.lock().map_err(|e| e.to_string())?;
    *current = Some(project.clone());

    // Add to recent projects
    let recent = create_recent_project(
        &path,
        &name,
        project.project_type.clone(),
        project.description.as_deref(),
    );

    let mut recent_store = state.recent_projects.lock().map_err(|e| e.to_string())?;
    recent_store.add(recent);
    let _ = recent_store.save(); // Best effort save

    Ok(project)
}

/// Run a goal using the Sunwell agent.
#[tauri::command]
pub async fn run_goal(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    goal: String,
    project_path: Option<String>,
) -> Result<RunGoalResult, String> {
    // Resolve workspace
    let explicit = project_path.map(PathBuf::from);
    let project_name = extract_project_name(&goal);

    let resolution = resolve_workspace(
        explicit.as_deref(),
        project_name.as_deref(),
    );

    let workspace_path = resolution.path.clone();

    // Ensure workspace exists if creating new project
    if !resolution.exists {
        ensure_workspace_exists(&workspace_path)
            .map_err(|e| format!("Failed to create workspace: {}", e))?;
    }

    // Start agent
    let mut agent = state.agent.lock().map_err(|e| e.to_string())?;
    agent.run_goal(app, &goal, &workspace_path)?;

    // Update recent projects
    if let Ok(project) = state.detector.detect(&workspace_path) {
        let recent = create_recent_project(
            &workspace_path,
            &project.name,
            project.project_type,
            project.description.as_deref(),
        );

        let mut recent_store = state.recent_projects.lock().map_err(|e| e.to_string())?;
        recent_store.add(recent);
        let _ = recent_store.save();
    }

    Ok(RunGoalResult {
        success: true,
        message: "Agent started".to_string(),
        workspace_path: shorten_path(&workspace_path),
    })
}

/// Stop the running agent.
#[tauri::command]
pub async fn stop_agent(state: State<'_, AppState>) -> Result<(), String> {
    let mut agent = state.agent.lock().map_err(|e| e.to_string())?;
    agent.stop()
}

/// Get list of recent projects.
#[tauri::command]
pub async fn get_recent_projects(
    state: State<'_, AppState>,
) -> Result<Vec<RecentProject>, String> {
    let recent_store = state.recent_projects.lock().map_err(|e| e.to_string())?;
    Ok(recent_store.get_all().to_vec())
}

/// Remove a project from recent list.
#[tauri::command]
pub async fn remove_recent_project(
    state: State<'_, AppState>,
    path: String,
) -> Result<(), String> {
    let mut recent_store = state.recent_projects.lock().map_err(|e| e.to_string())?;
    recent_store.remove(&PathBuf::from(path));
    recent_store.save().map_err(|e| e.to_string())
}

/// Open a project from a path.
#[tauri::command]
pub async fn open_project(
    state: State<'_, AppState>,
    path: String,
) -> Result<Project, String> {
    let path = PathBuf::from(&path);

    if !path.exists() {
        return Err(format!("Path does not exist: {}", path.display()));
    }

    let project = state.detector.detect(&path)?;

    // Update current project
    let mut current = state.current_project.lock().map_err(|e| e.to_string())?;
    *current = Some(project.clone());

    // Add to recent projects
    let recent = create_recent_project(
        &path,
        &project.name,
        project.project_type.clone(),
        project.description.as_deref(),
    );

    let mut recent_store = state.recent_projects.lock().map_err(|e| e.to_string())?;
    recent_store.add(recent);
    let _ = recent_store.save();

    Ok(project)
}

/// Get information about the current project.
#[tauri::command]
pub async fn get_project_info(state: State<'_, AppState>) -> Result<Option<Project>, String> {
    let current = state.current_project.lock().map_err(|e| e.to_string())?;
    Ok(current.clone())
}

/// Launch preview for the current project.
#[tauri::command]
pub async fn launch_preview(
    state: State<'_, AppState>,
) -> Result<crate::preview::PreviewSession, String> {
    let current = state.current_project.lock().map_err(|e| e.to_string())?;

    let project = current
        .as_ref()
        .ok_or("No project open")?;

    let mut preview = state.preview.lock().map_err(|e| e.to_string())?;
    preview.launch(project)
}

/// Stop the running preview.
#[tauri::command]
pub async fn stop_preview(state: State<'_, AppState>) -> Result<(), String> {
    let mut preview = state.preview.lock().map_err(|e| e.to_string())?;
    preview.stop()
}

/// Get workspace settings.
#[tauri::command]
pub async fn get_workspace_settings() -> Result<WorkspaceSettings, String> {
    Ok(WorkspaceSettings {
        default_location: shorten_path(&default_workspace_root()),
        confirm_new_projects: true,
        derive_names_from_goal: true,
    })
}

/// Workspace settings for the settings panel.
#[derive(Debug, Serialize, Deserialize)]
pub struct WorkspaceSettings {
    pub default_location: String,
    pub confirm_new_projects: bool,
    pub derive_names_from_goal: bool,
}

/// Generate a safe project directory name.
#[tauri::command]
pub async fn generate_project_name(name: String) -> Result<String, String> {
    Ok(slugify(&name))
}

/// Check if a project path is available (doesn't exist or is empty).
#[tauri::command]
pub async fn check_path_available(path: String) -> Result<bool, String> {
    let path = PathBuf::from(path);

    if !path.exists() {
        return Ok(true);
    }

    // Check if empty
    match std::fs::read_dir(&path) {
        Ok(mut entries) => Ok(entries.next().is_none()),
        Err(_) => Ok(false),
    }
}
