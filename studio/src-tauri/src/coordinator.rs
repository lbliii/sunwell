//! Coordinator bridge for multi-agent orchestration (RFC-100 Phase 4).
//!
//! This module provides Tauri commands for the ATC (Air Traffic Control) view
//! in Studio, enabling visualization and control of parallel agent execution.

use serde::{Deserialize, Serialize};
use std::process::Command;

/// Status of a single worker process.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkerStatus {
    pub id: u32,
    pub goal: String,
    pub status: String,
    pub progress: f32,
    pub current_file: Option<String>,
    pub branch: String,
    pub goals_completed: u32,
    pub goals_failed: u32,
    pub last_heartbeat: String,
}

/// A file conflict between two workers.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileConflict {
    pub path: String,
    pub worker_a: u32,
    pub worker_b: u32,
    pub conflict_type: String,
    pub resolution: Option<String>,
    pub detected_at: String,
}

/// Complete coordinator state for UI rendering.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CoordinatorState {
    pub workers: Vec<WorkerStatus>,
    pub conflicts: Vec<FileConflict>,
    pub total_progress: f32,
    pub merged_branches: Vec<String>,
    pub pending_merges: Vec<String>,
    pub is_running: bool,
    pub started_at: Option<String>,
    pub last_update: String,
}

impl Default for CoordinatorState {
    fn default() -> Self {
        Self {
            workers: Vec::new(),
            conflicts: Vec::new(),
            total_progress: 0.0,
            merged_branches: Vec::new(),
            pending_merges: Vec::new(),
            is_running: false,
            started_at: None,
            last_update: chrono::Utc::now().to_rfc3339(),
        }
    }
}

/// Get the current coordinator state for a project.
///
/// Calls `sunwell workers ui-state --project <path>` and parses the JSON output.
#[tauri::command]
pub async fn get_coordinator_state(project_path: String) -> Result<CoordinatorState, String> {
    let output = Command::new("sunwell")
        .args(["workers", "ui-state", "--project", &project_path])
        .output()
        .map_err(|e| format!("Failed to run sunwell: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Command failed: {}", stderr));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    serde_json::from_str(&stdout).map_err(|e| format!("Failed to parse JSON: {}", e))
}

/// Pause a specific worker.
#[tauri::command]
pub async fn pause_worker(project_path: String, worker_id: u32) -> Result<(), String> {
    let output = Command::new("sunwell")
        .current_dir(&project_path)
        .args(["workers", "pause", &worker_id.to_string()])
        .output()
        .map_err(|e| format!("Failed to run sunwell: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Command failed: {}", stderr));
    }

    Ok(())
}

/// Resume a paused worker.
#[tauri::command]
pub async fn resume_worker(project_path: String, worker_id: u32) -> Result<(), String> {
    let output = Command::new("sunwell")
        .current_dir(&project_path)
        .args(["workers", "resume", &worker_id.to_string()])
        .output()
        .map_err(|e| format!("Failed to run sunwell: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Command failed: {}", stderr));
    }

    Ok(())
}

/// Start parallel execution with multiple workers.
#[tauri::command]
pub async fn start_workers(
    project_path: String,
    num_workers: u32,
    dry_run: bool,
) -> Result<(), String> {
    let num_workers_str = num_workers.to_string();
    let mut args = vec!["workers", "start", "-n", &num_workers_str];
    if dry_run {
        args.push("--dry-run");
    }

    let output = Command::new("sunwell")
        .current_dir(&project_path)
        .args(&args)
        .output()
        .map_err(|e| format!("Failed to run sunwell: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Command failed: {}", stderr));
    }

    Ok(())
}

/// Get the scan/state DAG for a project (RFC-100 Phase 0).
#[tauri::command]
pub async fn get_state_dag(project_path: String) -> Result<serde_json::Value, String> {
    let output = Command::new("sunwell")
        .args(["scan", &project_path, "--json"])
        .output()
        .map_err(|e| format!("Failed to run sunwell: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Command failed: {}", stderr));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    serde_json::from_str(&stdout).map_err(|e| format!("Failed to parse JSON: {}", e))
}
