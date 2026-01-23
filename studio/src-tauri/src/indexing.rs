//! Codebase indexing Tauri commands (RFC-108)
//!
//! Provides commands for the IndexStatus component and semantic search.

use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::sync::Arc;
use tauri::{AppHandle, Emitter, Manager, State};
use tokio::sync::RwLock;

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "snake_case")]
pub enum IndexState {
    #[default]
    NoIndex,
    Checking,
    Loading,
    Building,
    Verifying,
    Ready,
    Updating,
    Degraded,
    Error,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct IndexStatus {
    pub state: IndexState,
    pub project_type: Option<String>,
    pub progress: Option<u32>,
    pub current_file: Option<String>,
    pub chunk_count: Option<u32>,
    pub file_count: Option<u32>,
    pub last_updated: Option<String>,
    pub error: Option<String>,
    pub fallback_reason: Option<String>,
    pub priority_complete: Option<bool>,
    pub estimated_time_ms: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct IndexQuery {
    pub text: String,
    pub top_k: Option<u32>,
    pub threshold: Option<f32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct IndexChunk {
    pub id: String,
    pub file_path: String,
    pub start_line: u32,
    pub end_line: u32,
    pub content: String,
    pub chunk_type: String,
    pub name: Option<String>,
    pub score: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct IndexResult {
    pub chunks: Vec<IndexChunk>,
    pub fallback_used: bool,
    pub query_time_ms: u32,
    pub total_chunks_searched: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct IndexSettings {
    pub auto_index: bool,
    pub watch_files: bool,
    pub embedding_model: String,
    pub max_file_size: u32,
    pub exclude_patterns: Vec<String>,
}

impl Default for IndexSettings {
    fn default() -> Self {
        Self {
            auto_index: true,
            watch_files: true,
            embedding_model: "all-minilm".to_string(),
            max_file_size: 100_000,
            exclude_patterns: vec![],
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct IndexMetrics {
    pub build_time_ms: u32,
    pub chunk_count: u32,
    pub file_count: u32,
    pub embedding_time_ms: u32,
    pub cache_hit_rate: f32,
    pub avg_query_latency_ms: f32,
    pub is_healthy: bool,
}

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

#[derive(Default)]
pub struct IndexingState {
    pub status: Arc<RwLock<IndexStatus>>,
    pub settings: Arc<RwLock<IndexSettings>>,
    pub workspace_root: Arc<RwLock<Option<PathBuf>>>,
    pub child_process: Arc<RwLock<Option<tokio::process::Child>>>,
}

// ═══════════════════════════════════════════════════════════════
// COMMANDS
// ═══════════════════════════════════════════════════════════════

#[tauri::command]
pub async fn start_indexing_service(
    app: AppHandle,
    state: State<'_, IndexingState>,
    workspace_path: String,
) -> Result<(), String> {
    let path = PathBuf::from(&workspace_path);
    *state.workspace_root.write().await = Some(path.clone());

    let app_clone = app.clone();
    let status = state.status.clone();
    let child_holder = state.child_process.clone();

    // Spawn background indexing task
    tokio::spawn(async move {
        use tokio::io::{AsyncBufReadExt, BufReader};

        // Start sunwell index build process
        let child_result = tokio::process::Command::new("sunwell")
            .args(["index", "build", "--json", "--progress"])
            .current_dir(&path)
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped())
            .spawn();

        let mut child = match child_result {
            Ok(c) => c,
            Err(e) => {
                let mut s = status.write().await;
                s.state = IndexState::Error;
                s.error = Some(format!("Failed to start sunwell: {}", e));
                let _ = app_clone.emit("index-status", s.clone());
                return;
            }
        };

        // Read stdout for status updates
        if let Some(stdout) = child.stdout.take() {
            let reader = BufReader::new(stdout);
            let mut lines = reader.lines();

            while let Ok(Some(line)) = lines.next_line().await {
                if let Ok(update) = serde_json::from_str::<IndexStatus>(&line) {
                    *status.write().await = update.clone();
                    let _ = app_clone.emit("index-status", update);
                }
            }
        }

        // Wait for process to complete
        let exit_status = child.wait().await;

        // Check exit status
        if let Ok(status_code) = exit_status {
            if !status_code.success() {
                let mut s = status.write().await;
                s.state = IndexState::Error;
                s.error = Some(format!("Indexing exited with code {:?}", status_code.code()));
                let _ = app_clone.emit("index-status", s.clone());
            }
        }
    });

    Ok(())
}

#[tauri::command]
pub async fn stop_indexing_service(state: State<'_, IndexingState>) -> Result<(), String> {
    if let Some(mut child) = state.child_process.write().await.take() {
        let _ = child.kill().await;
    }

    let mut status = state.status.write().await;
    *status = IndexStatus::default();

    Ok(())
}

#[tauri::command]
pub async fn query_index(
    query: IndexQuery,
    state: State<'_, IndexingState>,
) -> Result<IndexResult, String> {
    let workspace_root = state.workspace_root.read().await;
    let Some(root) = workspace_root.as_ref() else {
        return Ok(IndexResult {
            chunks: vec![],
            fallback_used: true,
            query_time_ms: 0,
            total_chunks_searched: 0,
        });
    };

    let top_k = query.top_k.unwrap_or(10);

    let output = std::process::Command::new("sunwell")
        .args([
            "index",
            "query",
            "--json",
            "--top-k",
            &top_k.to_string(),
            &query.text,
        ])
        .current_dir(root)
        .output()
        .map_err(|e| e.to_string())?;

    if output.status.success() {
        serde_json::from_slice(&output.stdout).map_err(|e| e.to_string())
    } else {
        Ok(IndexResult {
            chunks: vec![],
            fallback_used: true,
            query_time_ms: 0,
            total_chunks_searched: 0,
        })
    }
}

#[tauri::command]
pub async fn get_index_status(state: State<'_, IndexingState>) -> Result<IndexStatus, String> {
    Ok(state.status.read().await.clone())
}

#[tauri::command]
pub async fn rebuild_index(
    app: AppHandle,
    state: State<'_, IndexingState>,
) -> Result<(), String> {
    let workspace_root = state.workspace_root.read().await;
    let Some(root) = workspace_root.as_ref() else {
        return Err("No workspace opened".into());
    };

    // Clear cache
    let cache_dir = root.join(".sunwell").join("index");
    if cache_dir.exists() {
        let _ = std::fs::remove_dir_all(&cache_dir);
    }

    let root_str = root.to_string_lossy().to_string();

    // Restart indexing
    drop(workspace_root);
    start_indexing_service(app, state, root_str).await
}

#[tauri::command]
pub async fn set_index_settings(
    settings: IndexSettings,
    state: State<'_, IndexingState>,
) -> Result<(), String> {
    *state.settings.write().await = settings;
    Ok(())
}

#[tauri::command]
pub async fn get_index_metrics(state: State<'_, IndexingState>) -> Result<IndexMetrics, String> {
    let workspace_root = state.workspace_root.read().await;
    let Some(root) = workspace_root.as_ref() else {
        return Err("No workspace opened".into());
    };

    let output = std::process::Command::new("sunwell")
        .args(["index", "metrics", "--json"])
        .current_dir(root)
        .output()
        .map_err(|e| e.to_string())?;

    if output.status.success() {
        serde_json::from_slice(&output.stdout).map_err(|e| e.to_string())
    } else {
        Err("Failed to get metrics".into())
    }
}
