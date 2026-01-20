//! Tauri IPC commands — interface between frontend and Rust backend.

use crate::agent::AgentBridge;
use crate::preview::PreviewManager;
use crate::project::{Project, ProjectDetector, RecentProject};
use crate::workspace::{
    create_recent_project, default_workspace_root, ensure_workspace_exists,
    extract_project_name, resolve_workspace, shorten_path, slugify,
    RecentProjectsStore, ResolutionSource, WorkspaceResult,
};
use chrono::{DateTime, Utc};
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

// =============================================================================
// Project Discovery & Status (Per-Project Resume)
// =============================================================================

/// Status of a project's agent execution.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ExecutionStatus {
    /// No execution history
    None,
    /// Execution completed successfully
    Complete,
    /// Execution was interrupted (has checkpoint)
    Interrupted,
    /// Execution failed with error
    Failed,
}

/// Task from a checkpoint (for display).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CheckpointTask {
    pub id: String,
    pub description: String,
    pub completed: bool,
}

/// Detailed status of a discovered project.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectStatus {
    pub path: String,
    pub display_path: String,
    pub name: String,
    pub status: ExecutionStatus,
    pub last_goal: Option<String>,
    pub tasks_completed: Option<u32>,
    pub tasks_total: Option<u32>,
    pub tasks: Option<Vec<CheckpointTask>>,
    pub last_activity: Option<String>,
}

/// Scan ~/Sunwell/projects/ for all projects.
#[tauri::command]
pub async fn scan_projects() -> Result<Vec<ProjectStatus>, String> {
    let projects_root = default_workspace_root();
    
    if !projects_root.exists() {
        return Ok(vec![]);
    }

    let mut projects = Vec::new();

    let entries = std::fs::read_dir(&projects_root)
        .map_err(|e| format!("Failed to read projects directory: {}", e))?;

    for entry in entries.flatten() {
        let path = entry.path();
        
        // Skip non-directories
        if !path.is_dir() {
            continue;
        }

        // Skip hidden directories
        if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
            if name.starts_with('.') {
                continue;
            }
        }

        // Get project status
        if let Ok(status) = get_project_status_internal(&path) {
            projects.push(status);
        }
    }

    // Sort by last activity (most recent first)
    projects.sort_by(|a, b| {
        let a_time = a.last_activity.as_ref().map(|s| s.as_str()).unwrap_or("");
        let b_time = b.last_activity.as_ref().map(|s| s.as_str()).unwrap_or("");
        b_time.cmp(a_time)
    });

    Ok(projects)
}

/// Get status for a specific project.
#[tauri::command]
pub async fn get_project_status(path: String) -> Result<ProjectStatus, String> {
    let path = PathBuf::from(path);
    get_project_status_internal(&path)
}

/// Internal function to get project status.
fn get_project_status_internal(path: &PathBuf) -> Result<ProjectStatus, String> {
    let name = path
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("unknown")
        .to_string();

    let sunwell_dir = path.join(".sunwell");
    let checkpoints_dir = sunwell_dir.join("checkpoints");

    // Check for checkpoints (interrupted execution)
    let checkpoint_info = find_latest_checkpoint(&checkpoints_dir);

    let (status, last_goal, tasks_completed, tasks_total, tasks, last_activity) = 
        if let Some(info) = checkpoint_info {
            (
                if info.is_complete {
                    ExecutionStatus::Complete
                } else {
                    ExecutionStatus::Interrupted
                },
                Some(info.goal),
                Some(info.completed),
                Some(info.total),
                Some(info.tasks),
                Some(info.timestamp),
            )
        } else {
            (ExecutionStatus::None, None, None, None, None, get_dir_mtime(path))
        };

    Ok(ProjectStatus {
        path: path.to_string_lossy().to_string(),
        display_path: shorten_path(path),
        name,
        status,
        last_goal,
        tasks_completed,
        tasks_total,
        tasks,
        last_activity,
    })
}

/// Checkpoint summary info.
struct CheckpointInfo {
    goal: String,
    completed: u32,
    total: u32,
    is_complete: bool,
    timestamp: String,
    tasks: Vec<CheckpointTask>,
}

/// Find and parse the latest checkpoint file.
fn find_latest_checkpoint(checkpoints_dir: &PathBuf) -> Option<CheckpointInfo> {
    if !checkpoints_dir.exists() {
        return None;
    }

    let entries = std::fs::read_dir(checkpoints_dir).ok()?;
    
    let mut latest: Option<(PathBuf, std::time::SystemTime)> = None;

    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) == Some("json") {
            if let Ok(meta) = path.metadata() {
                if let Ok(mtime) = meta.modified() {
                    if latest.is_none() || mtime > latest.as_ref().unwrap().1 {
                        latest = Some((path, mtime));
                    }
                }
            }
        }
    }

    let (checkpoint_path, mtime) = latest?;
    
    // Parse checkpoint JSON
    let content = std::fs::read_to_string(&checkpoint_path).ok()?;
    let json: serde_json::Value = serde_json::from_str(&content).ok()?;

    let goal = json.get("goal")?.as_str()?.to_string();
    let tasks_json = json.get("tasks")?.as_array()?;
    let completed_ids: std::collections::HashSet<String> = json
        .get("completed_ids")?
        .as_array()?
        .iter()
        .filter_map(|v| v.as_str().map(|s| s.to_string()))
        .collect();
    
    // Parse task details
    let tasks: Vec<CheckpointTask> = tasks_json
        .iter()
        .filter_map(|t| {
            let id = t.get("id")?.as_str()?.to_string();
            // Try different possible field names for description
            let description = t.get("description")
                .or_else(|| t.get("title"))
                .or_else(|| t.get("name"))
                .and_then(|v| v.as_str())
                .unwrap_or("Task")
                .to_string();
            let completed = completed_ids.contains(&id);
            Some(CheckpointTask { id, description, completed })
        })
        .collect();
    
    let total = tasks.len() as u32;
    let completed = tasks.iter().filter(|t| t.completed).count() as u32;
    let is_complete = completed >= total && total > 0;

    // Format timestamp
    let timestamp = mtime
        .duration_since(std::time::UNIX_EPOCH)
        .ok()
        .map(|d| {
            DateTime::<Utc>::from_timestamp(d.as_secs() as i64, 0)
                .map(|dt| dt.format("%Y-%m-%dT%H:%M:%SZ").to_string())
                .unwrap_or_default()
        })
        .unwrap_or_default();

    Some(CheckpointInfo {
        goal,
        completed,
        total,
        is_complete,
        timestamp,
        tasks,
    })
}

/// Get directory modification time as ISO string.
fn get_dir_mtime(path: &PathBuf) -> Option<String> {
    let meta = std::fs::metadata(path).ok()?;
    let mtime = meta.modified().ok()?;
    let duration = mtime.duration_since(std::time::UNIX_EPOCH).ok()?;
    DateTime::<Utc>::from_timestamp(duration.as_secs() as i64, 0)
        .map(|dt| dt.format("%Y-%m-%dT%H:%M:%SZ").to_string())
}

/// Resume an interrupted project.
#[tauri::command]
pub async fn resume_project(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    path: String,
) -> Result<RunGoalResult, String> {
    let project_path = PathBuf::from(&path);

    if !project_path.exists() {
        return Err(format!("Project path does not exist: {}", path));
    }

    // Check if there's something to resume
    let status = get_project_status_internal(&project_path)?;
    if status.status != ExecutionStatus::Interrupted {
        return Err("No interrupted execution to resume".to_string());
    }

    // Start agent in resume mode
    let mut agent = state.agent.lock().map_err(|e| e.to_string())?;
    agent.resume_goal(app, &project_path)?;

    Ok(RunGoalResult {
        success: true,
        message: "Agent resumed".to_string(),
        workspace_path: shorten_path(&project_path),
    })
}

// =============================================================================
// Project Access Commands (files, terminal, edit)
// =============================================================================

/// Open project folder in system file manager (Finder/Explorer).
#[tauri::command]
pub async fn open_in_finder(path: String) -> Result<(), String> {
    let path = PathBuf::from(&path);
    
    if !path.exists() {
        return Err(format!("Path does not exist: {}", path.display()));
    }

    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open")
            .arg(&path)
            .spawn()
            .map_err(|e| format!("Failed to open Finder: {}", e))?;
    }

    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("explorer")
            .arg(&path)
            .spawn()
            .map_err(|e| format!("Failed to open Explorer: {}", e))?;
    }

    #[cfg(target_os = "linux")]
    {
        std::process::Command::new("xdg-open")
            .arg(&path)
            .spawn()
            .map_err(|e| format!("Failed to open file manager: {}", e))?;
    }

    Ok(())
}

/// Open terminal at project directory.
#[tauri::command]
pub async fn open_terminal(path: String) -> Result<(), String> {
    let path = PathBuf::from(&path);
    
    if !path.exists() {
        return Err(format!("Path does not exist: {}", path.display()));
    }

    #[cfg(target_os = "macos")]
    {
        // Try iTerm first, fall back to Terminal.app
        let iterm_script = format!(
            r#"tell application "iTerm"
                create window with default profile
                tell current session of current window
                    write text "cd '{}'"
                end tell
            end tell"#,
            path.display()
        );

        let result = std::process::Command::new("osascript")
            .args(["-e", &iterm_script])
            .output();

        if result.is_err() || !result.as_ref().unwrap().status.success() {
            // Fall back to Terminal.app
            let terminal_script = format!(
                r#"tell application "Terminal"
                    do script "cd '{}'"
                    activate
                end tell"#,
                path.display()
            );
            std::process::Command::new("osascript")
                .args(["-e", &terminal_script])
                .spawn()
                .map_err(|e| format!("Failed to open Terminal: {}", e))?;
        }
    }

    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("cmd")
            .args(["/c", "start", "cmd", "/k", &format!("cd /d {}", path.display())])
            .spawn()
            .map_err(|e| format!("Failed to open terminal: {}", e))?;
    }

    #[cfg(target_os = "linux")]
    {
        // Try common terminal emulators
        let terminals = ["gnome-terminal", "konsole", "xfce4-terminal", "xterm"];
        let mut success = false;
        
        for term in &terminals {
            let result = std::process::Command::new(term)
                .arg("--working-directory")
                .arg(&path)
                .spawn();
            
            if result.is_ok() {
                success = true;
                break;
            }
        }
        
        if !success {
            return Err("No supported terminal emulator found".to_string());
        }
    }

    Ok(())
}

/// File entry for the file tree.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileEntry {
    pub name: String,
    pub path: String,
    pub is_dir: bool,
    pub children: Option<Vec<FileEntry>>,
    pub size: Option<u64>,
}

/// List files in a project directory (for file tree display).
#[tauri::command]
pub async fn list_project_files(path: String, max_depth: Option<u32>) -> Result<Vec<FileEntry>, String> {
    let path = PathBuf::from(&path);
    
    if !path.exists() {
        return Err(format!("Path does not exist: {}", path.display()));
    }

    let max_depth = max_depth.unwrap_or(3);
    let entries = list_dir_recursive(&path, 0, max_depth)?;
    Ok(entries)
}

/// Recursively list directory contents.
fn list_dir_recursive(dir: &PathBuf, depth: u32, max_depth: u32) -> Result<Vec<FileEntry>, String> {
    let mut entries = Vec::new();
    
    let read_dir = std::fs::read_dir(dir)
        .map_err(|e| format!("Failed to read directory: {}", e))?;

    for entry in read_dir.flatten() {
        let path = entry.path();
        let name = entry.file_name().to_string_lossy().to_string();
        
        // Skip hidden files and common ignored directories
        if name.starts_with('.') 
            || name == "node_modules" 
            || name == "__pycache__"
            || name == "target"
            || name == "venv"
            || name == ".venv"
            || name == "dist"
            || name == "build"
        {
            continue;
        }

        let is_dir = path.is_dir();
        let size = if !is_dir {
            std::fs::metadata(&path).ok().map(|m| m.len())
        } else {
            None
        };

        let children = if is_dir && depth < max_depth {
            Some(list_dir_recursive(&path, depth + 1, max_depth).unwrap_or_default())
        } else if is_dir {
            Some(vec![]) // Indicate it's expandable but not loaded
        } else {
            None
        };

        entries.push(FileEntry {
            name,
            path: path.to_string_lossy().to_string(),
            is_dir,
            children,
            size,
        });
    }

    // Sort: directories first, then alphabetically
    entries.sort_by(|a, b| {
        match (a.is_dir, b.is_dir) {
            (true, false) => std::cmp::Ordering::Less,
            (false, true) => std::cmp::Ordering::Greater,
            _ => a.name.to_lowercase().cmp(&b.name.to_lowercase()),
        }
    });

    Ok(entries)
}

/// Read file contents (for preview).
#[tauri::command]
pub async fn read_file_contents(path: String, max_size: Option<u64>) -> Result<String, String> {
    let path = PathBuf::from(&path);
    let max_size = max_size.unwrap_or(100_000); // 100KB default
    
    if !path.exists() {
        return Err("File does not exist".to_string());
    }
    
    if !path.is_file() {
        return Err("Path is not a file".to_string());
    }

    let metadata = std::fs::metadata(&path)
        .map_err(|e| format!("Failed to read metadata: {}", e))?;
    
    if metadata.len() > max_size {
        return Err(format!("File too large ({} bytes)", metadata.len()));
    }

    std::fs::read_to_string(&path)
        .map_err(|e| format!("Failed to read file: {}", e))
}

/// Open project in code editor (VS Code, Cursor, etc.).
#[tauri::command]
pub async fn open_in_editor(path: String) -> Result<(), String> {
    let path = PathBuf::from(&path);
    
    if !path.exists() {
        return Err(format!("Path does not exist: {}", path.display()));
    }

    // Try editors in order of preference
    let editors = ["cursor", "code", "codium", "subl", "atom"];
    
    for editor in &editors {
        let result = std::process::Command::new(editor)
            .arg(&path)
            .spawn();
        
        if result.is_ok() {
            return Ok(());
        }
    }

    // Fallback: try to open with system default
    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open")
            .args(["-a", "TextEdit", path.to_str().unwrap_or("")])
            .spawn()
            .map_err(|e| format!("Failed to open editor: {}", e))?;
        return Ok(());
    }

    #[cfg(not(target_os = "macos"))]
    Err("No supported code editor found. Install VS Code or Cursor.".to_string())
}

// =============================================================================
// Project Management (Delete, Archive, Iterate)
// =============================================================================

/// Result of a project management operation.
#[derive(Debug, Serialize, Deserialize)]
pub struct ProjectManageResult {
    pub success: bool,
    pub message: String,
    pub new_path: Option<String>,
}

/// Delete a project permanently.
#[tauri::command]
pub async fn delete_project(
    state: State<'_, AppState>,
    path: String,
) -> Result<ProjectManageResult, String> {
    let path = PathBuf::from(&path);
    
    if !path.exists() {
        return Err(format!("Project does not exist: {}", path.display()));
    }

    let name = path.file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("project")
        .to_string();

    // Remove from recent projects
    let mut recent_store = state.recent_projects.lock().map_err(|e| e.to_string())?;
    recent_store.remove(&path);
    let _ = recent_store.save();
    drop(recent_store);

    // Delete the directory
    std::fs::remove_dir_all(&path)
        .map_err(|e| format!("Failed to delete project: {}", e))?;

    Ok(ProjectManageResult {
        success: true,
        message: format!("Deleted project '{}'", name),
        new_path: None,
    })
}

/// Archive a project (move to ~/Sunwell/archived/).
#[tauri::command]
pub async fn archive_project(
    state: State<'_, AppState>,
    path: String,
) -> Result<ProjectManageResult, String> {
    let path = PathBuf::from(&path);
    
    if !path.exists() {
        return Err(format!("Project does not exist: {}", path.display()));
    }

    let name = path.file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("project")
        .to_string();

    // Create archive directory
    let archive_root = default_workspace_root().parent()
        .map(|p| p.to_path_buf())
        .unwrap_or_else(|| dirs::home_dir().unwrap_or_default().join("Sunwell"))
        .join("archived");
    
    std::fs::create_dir_all(&archive_root)
        .map_err(|e| format!("Failed to create archive directory: {}", e))?;

    // Generate unique archive name with timestamp
    let timestamp = chrono::Utc::now().format("%Y%m%d_%H%M%S");
    let archive_name = format!("{}_{}", name, timestamp);
    let archive_path = archive_root.join(&archive_name);

    // Move the project
    std::fs::rename(&path, &archive_path)
        .map_err(|e| format!("Failed to archive project: {}", e))?;

    // Remove from recent projects
    let mut recent_store = state.recent_projects.lock().map_err(|e| e.to_string())?;
    recent_store.remove(&path);
    let _ = recent_store.save();

    Ok(ProjectManageResult {
        success: true,
        message: format!("Archived '{}' to ~/Sunwell/archived/", name),
        new_path: Some(shorten_path(&archive_path)),
    })
}

/// Learnings extracted from a project for iteration.
#[derive(Debug, Serialize, Deserialize)]
pub struct ProjectLearnings {
    pub original_goal: Option<String>,
    pub decisions: Vec<String>,
    pub failures: Vec<String>,
    pub completed_tasks: Vec<String>,
    pub pending_tasks: Vec<String>,
}

/// Extract learnings from a project's .sunwell directory.
fn extract_project_learnings(path: &PathBuf) -> ProjectLearnings {
    let sunwell_dir = path.join(".sunwell");
    let mut learnings = ProjectLearnings {
        original_goal: None,
        decisions: Vec::new(),
        failures: Vec::new(),
        completed_tasks: Vec::new(),
        pending_tasks: Vec::new(),
    };

    // Extract goal and tasks from checkpoint
    if let Some(checkpoint_info) = find_latest_checkpoint(&sunwell_dir.join("checkpoints")) {
        learnings.original_goal = Some(checkpoint_info.goal);
        for task in checkpoint_info.tasks {
            if task.completed {
                learnings.completed_tasks.push(task.description);
            } else {
                learnings.pending_tasks.push(task.description);
            }
        }
    }

    // Extract decisions from intelligence
    let decisions_path = sunwell_dir.join("intelligence").join("decisions.jsonl");
    if decisions_path.exists() {
        if let Ok(content) = std::fs::read_to_string(&decisions_path) {
            for line in content.lines() {
                if let Ok(json) = serde_json::from_str::<serde_json::Value>(line) {
                    if let Some(decision) = json.get("decision").and_then(|d| d.as_str()) {
                        learnings.decisions.push(decision.to_string());
                    }
                }
            }
        }
    }

    // Extract failures from intelligence
    let failures_path = sunwell_dir.join("intelligence").join("failures.jsonl");
    if failures_path.exists() {
        if let Ok(content) = std::fs::read_to_string(&failures_path) {
            for line in content.lines() {
                if let Ok(json) = serde_json::from_str::<serde_json::Value>(line) {
                    if let Some(approach) = json.get("approach").and_then(|a| a.as_str()) {
                        let reason = json.get("reason").and_then(|r| r.as_str()).unwrap_or("failed");
                        learnings.failures.push(format!("{} ({})", approach, reason));
                    }
                }
            }
        }
    }

    learnings
}

/// Iterate on a project - create a new version informed by learnings.
#[tauri::command]
pub async fn iterate_project(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    path: String,
    new_goal: Option<String>,
) -> Result<ProjectManageResult, String> {
    let path = PathBuf::from(&path);
    
    if !path.exists() {
        return Err(format!("Project does not exist: {}", path.display()));
    }

    let name = path.file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("project")
        .to_string();

    // Extract learnings from original project
    let learnings = extract_project_learnings(&path);

    // Generate new project name (increment version)
    let new_name = generate_iteration_name(&name);
    let new_path = path.parent()
        .map(|p| p.join(&new_name))
        .ok_or("Failed to determine new project path")?;

    // Create new project directory
    ensure_workspace_exists(&new_path)
        .map_err(|e| format!("Failed to create iteration directory: {}", e))?;

    // Create .sunwell directory with inherited learnings
    let new_sunwell = new_path.join(".sunwell");
    std::fs::create_dir_all(&new_sunwell)
        .map_err(|e| format!("Failed to create .sunwell directory: {}", e))?;

    // Write learnings context for the agent to consume
    let context_path = new_sunwell.join("iteration_context.json");
    let context_json = serde_json::json!({
        "iteration_of": path.to_string_lossy(),
        "original_goal": learnings.original_goal,
        "learned_decisions": learnings.decisions,
        "failed_approaches": learnings.failures,
        "completed_in_previous": learnings.completed_tasks,
        "pending_from_previous": learnings.pending_tasks,
    });
    std::fs::write(&context_path, serde_json::to_string_pretty(&context_json).unwrap_or_default())
        .map_err(|e| format!("Failed to write iteration context: {}", e))?;

    // Formulate the iteration goal
    let iteration_goal = if let Some(goal) = new_goal {
        goal
    } else if let Some(original) = &learnings.original_goal {
        format!(
            "Iterate on: {} — Build an improved version using learnings from the previous attempt. Avoid: {:?}",
            original,
            learnings.failures.iter().take(3).collect::<Vec<_>>()
        )
    } else {
        format!("Continue developing {} with improvements", name)
    };

    // Start agent with the new goal
    let mut agent = state.agent.lock().map_err(|e| e.to_string())?;
    agent.run_goal(app, &iteration_goal, &new_path)?;

    Ok(ProjectManageResult {
        success: true,
        message: format!("Created iteration '{}' from '{}'", new_name, name),
        new_path: Some(shorten_path(&new_path)),
    })
}

/// Generate the next iteration name (e.g., "myproject" -> "myproject-v2").
fn generate_iteration_name(name: &str) -> String {
    // Check if name already has version suffix
    let version_re = regex::Regex::new(r"-v(\d+)$").ok();
    
    if let Some(re) = version_re {
        if let Some(caps) = re.captures(name) {
            if let Some(v) = caps.get(1) {
                if let Ok(num) = v.as_str().parse::<u32>() {
                    let base = &name[..name.len() - caps.get(0).unwrap().len()];
                    return format!("{}-v{}", base, num + 1);
                }
            }
        }
    }
    
    format!("{}-v2", name)
}

/// Get learnings for a project (for display in UI).
#[tauri::command]
pub async fn get_project_learnings(path: String) -> Result<ProjectLearnings, String> {
    let path = PathBuf::from(&path);
    
    if !path.exists() {
        return Err(format!("Project does not exist: {}", path.display()));
    }

    Ok(extract_project_learnings(&path))
}
