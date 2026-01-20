//! Tauri IPC commands — interface between frontend and Rust backend.

use crate::agent::AgentBridge;
use crate::preview::PreviewManager;
use crate::project::{Project, ProjectDetector, RecentProject};
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
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            agent: Mutex::new(AgentBridge::new()),
            preview: Mutex::new(PreviewManager::new()),
            detector: ProjectDetector::new(),
            current_project: Mutex::new(None),
        }
    }
}

/// Result of running a goal.
#[derive(Debug, Serialize, Deserialize)]
pub struct RunGoalResult {
    pub success: bool,
    pub message: String,
}

/// Run a goal using the Sunwell agent.
#[tauri::command]
pub async fn run_goal(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    goal: String,
    project_path: Option<String>,
) -> Result<RunGoalResult, String> {
    let path = project_path
        .map(PathBuf::from)
        .unwrap_or_else(|| std::env::current_dir().unwrap_or_default());

    let mut agent = state.agent.lock().map_err(|e| e.to_string())?;

    agent.run_goal(app, &goal, &path)?;

    Ok(RunGoalResult {
        success: true,
        message: "Agent started".to_string(),
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
pub async fn get_recent_projects() -> Result<Vec<RecentProject>, String> {
    // TODO: Load from persistent storage
    // For now, return empty list
    Ok(vec![])
}

/// Open a project from a path.
#[tauri::command]
pub async fn open_project(
    state: State<'_, AppState>,
    path: String,
) -> Result<Project, String> {
    let path = PathBuf::from(path);

    if !path.exists() {
        return Err(format!("Path does not exist: {}", path.display()));
    }

    let project = state.detector.detect(&path)?;

    let mut current = state.current_project.lock().map_err(|e| e.to_string())?;
    *current = Some(project.clone());

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
