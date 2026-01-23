//! Evaluation Framework — Real Metrics, Real Transparency (RFC-098)
//!
//! Tauri commands for running full-stack evaluations comparing
//! single-shot generation vs Sunwell cognitive architecture.
//! Calls `sunwell eval --stream` for NDJSON streaming.

use crate::error::{ErrorCode, SunwellError};
use serde::{Deserialize, Serialize};
use std::process::Stdio;
use tauri::{Emitter, Window};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES — Match Python `sunwell eval --stream` output
// ═══════════════════════════════════════════════════════════════════════════════

/// An evaluation task.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvalTask {
    pub id: String,
    pub name: String,
    pub prompt: String,
    #[serde(default)]
    pub available_tools: Vec<String>,
    #[serde(default)]
    pub expected_patterns: Vec<String>,
}

/// Score breakdown for a generated project.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct FullStackScore {
    /// Files in correct places (0-1)
    pub structure: f64,
    /// Passes smoke test (0-1)
    pub runnable: f64,
    /// Expected features present (0-1)
    pub features: f64,
    /// Code quality metrics (0-1)
    pub quality: f64,
    /// Weighted total (0-100)
    pub total: f64,
}

/// Result from single-shot execution.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SingleShotResult {
    pub files: Vec<String>,
    pub time_seconds: f64,
    pub turns: u32,
    pub input_tokens: u32,
    pub output_tokens: u32,
}

/// Result from Sunwell full-stack execution.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SunwellResult {
    pub files: Vec<String>,
    pub time_seconds: f64,
    pub turns: u32,
    pub input_tokens: u32,
    pub output_tokens: u32,
    pub lens_used: Option<String>,
    #[serde(default)]
    pub judge_scores: Vec<f64>,
    pub resonance_iterations: u32,
}

/// Complete evaluation run comparing both methods.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvaluationRun {
    pub id: String,
    pub timestamp: String,
    pub model: String,
    pub task_id: String,
    pub task_prompt: String,
    pub single_shot: Option<SingleShotResult>,
    pub sunwell: Option<SunwellResult>,
    pub single_shot_score: Option<FullStackScore>,
    pub sunwell_score: Option<FullStackScore>,
    #[serde(default)]
    pub improvement_percent: f64,
}

/// Progress event during evaluation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvalProgress {
    pub phase: String,
    pub message: String,
    pub progress: f64,
}

/// Streaming event from `sunwell eval --stream`.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum EvalStreamEvent {
    #[serde(rename = "start")]
    Start { model: String, task: EvalTask },
    #[serde(rename = "progress")]
    Progress {
        method: String,
        phase: String,
        message: String,
    },
    #[serde(rename = "file_created")]
    FileCreated { method: String, path: String },
    #[serde(rename = "complete")]
    Complete(Box<EvaluationRun>),
    #[serde(rename = "error")]
    Error { message: String },
}

/// Evaluation input parameters.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvalInput {
    pub task: Option<String>,
    pub model: Option<String>,
    pub provider: Option<String>,
    pub lens: Option<String>,
}

/// Statistics from historical evaluations.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvalStats {
    pub total_runs: u32,
    pub avg_improvement: f64,
    pub sunwell_wins: u32,
    pub single_shot_wins: u32,
    pub ties: u32,
    #[serde(default)]
    pub by_task: std::collections::HashMap<String, TaskStats>,
}

/// Per-task statistics.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct TaskStats {
    pub runs: u32,
    pub avg_improvement: f64,
    pub sunwell_avg_score: f64,
    pub single_shot_avg_score: f64,
}

// ═══════════════════════════════════════════════════════════════════════════════
// COMMANDS
// ═══════════════════════════════════════════════════════════════════════════════

/// Run evaluation with streaming progress events.
///
/// Uses `sunwell eval --stream` for real-time updates.
/// Emits events to frontend as NDJSON lines arrive.
#[tauri::command]
pub async fn run_eval_streaming(
    window: Window,
    input: EvalInput,
) -> Result<EvaluationRun, SunwellError> {
    // Build command arguments
    let mut args = vec!["eval".to_string(), "--stream".to_string()];

    if let Some(task) = &input.task {
        args.push("--task".to_string());
        args.push(task.clone());
    }

    if let Some(model) = &input.model {
        args.push("--model".to_string());
        args.push(model.clone());
    }

    if let Some(provider) = &input.provider {
        args.push("--provider".to_string());
        args.push(provider.clone());
    }

    if let Some(lens) = &input.lens {
        args.push("--lens".to_string());
        args.push(lens.clone());
    }

    // Start subprocess with streaming
    let mut child = Command::new("sunwell")
        .args(&args)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e))?;

    // Emit starting progress
    let _ = window.emit(
        "eval-progress",
        EvalProgress {
            phase: "starting".to_string(),
            message: "Starting evaluation...".to_string(),
            progress: 0.0,
        },
    );

    let mut final_result: Option<EvaluationRun> = None;

    // Read stdout line by line (NDJSON)
    if let Some(stdout) = child.stdout.take() {
        let reader = BufReader::new(stdout);
        let mut lines = reader.lines();

        while let Ok(Some(line)) = lines.next_line().await {
            // Skip empty lines
            if line.trim().is_empty() {
                continue;
            }

            // Parse NDJSON event
            match serde_json::from_str::<EvalStreamEvent>(&line) {
                Ok(event) => match &event {
                    EvalStreamEvent::Start { model, task } => {
                        let _ = window.emit(
                            "eval-start",
                            serde_json::json!({
                                "model": model,
                                "task": task,
                            }),
                        );
                    }
                    EvalStreamEvent::Progress {
                        method,
                        phase,
                        message,
                    } => {
                        let _ = window.emit(
                            "eval-phase",
                            serde_json::json!({
                                "method": method,
                                "phase": phase,
                                "message": message,
                            }),
                        );
                    }
                    EvalStreamEvent::FileCreated { method, path } => {
                        let _ = window.emit(
                            "eval-file-created",
                            serde_json::json!({
                                "method": method,
                                "path": path,
                            }),
                        );
                    }
                    EvalStreamEvent::Complete(run) => {
                        final_result = Some(*run.clone());
                        let _ = window.emit("eval-complete", run.as_ref());
                    }
                    EvalStreamEvent::Error { message } => {
                        let _ = window.emit(
                            "eval-error",
                            serde_json::json!({
                                "message": message,
                            }),
                        );
                    }
                },
                Err(e) => {
                    eprintln!("Failed to parse NDJSON line: {} - {}", e, line);
                }
            }
        }
    }

    // Wait for completion
    let status = child
        .wait()
        .await
        .map_err(|e| SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e))?;

    if !status.success() {
        return Err(SunwellError::new(
            ErrorCode::RuntimeProcessFailed,
            "Evaluation execution failed",
        ));
    }

    // Return final result
    final_result.ok_or_else(|| {
        SunwellError::new(
            ErrorCode::ConfigInvalid,
            "No complete event received from eval stream",
        )
    })
}

/// List available evaluation tasks.
#[tauri::command]
pub async fn list_eval_tasks() -> Result<Vec<EvalTask>, SunwellError> {
    // Call sunwell eval --list-tasks
    let output = Command::new("sunwell")
        .args(["eval", "--list-tasks", "--json"])
        .output()
        .await
        .map_err(|e| SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e))?;

    if output.status.success() {
        let stdout = String::from_utf8_lossy(&output.stdout);
        match serde_json::from_str::<Vec<EvalTask>>(&stdout) {
            Ok(tasks) => return Ok(tasks),
            Err(_) => {} // Fall through to built-in
        }
    }

    // Return built-in tasks
    Ok(vec![
        EvalTask {
            id: "forum_app".to_string(),
            name: "Forum Application".to_string(),
            prompt: "Create a Python forum application with Flask".to_string(),
            available_tools: vec![
                "create_file".to_string(),
                "read_file".to_string(),
                "list_dir".to_string(),
                "run_command".to_string(),
            ],
            expected_patterns: vec!["app.py".to_string(), "models.py".to_string()],
        },
        EvalTask {
            id: "cli_tool".to_string(),
            name: "CLI Tool".to_string(),
            prompt: "Create a command-line tool with Click".to_string(),
            available_tools: vec![
                "create_file".to_string(),
                "read_file".to_string(),
                "list_dir".to_string(),
                "run_command".to_string(),
            ],
            expected_patterns: vec!["cli.py".to_string(), "pyproject.toml".to_string()],
        },
        EvalTask {
            id: "rest_api".to_string(),
            name: "REST API".to_string(),
            prompt: "Create a REST API with FastAPI".to_string(),
            available_tools: vec![
                "create_file".to_string(),
                "read_file".to_string(),
                "list_dir".to_string(),
                "run_command".to_string(),
            ],
            expected_patterns: vec!["main.py".to_string(), "routes/".to_string()],
        },
    ])
}

/// Get evaluation history.
#[tauri::command]
pub async fn get_eval_history(limit: Option<u32>) -> Result<Vec<EvaluationRun>, SunwellError> {
    let mut args = vec!["eval".to_string(), "--history".to_string(), "--json".to_string()];
    if let Some(n) = limit {
        args.push("--limit".to_string());
        args.push(n.to_string());
    }

    let output = Command::new("sunwell")
        .args(&args)
        .output()
        .await
        .map_err(|e| SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e))?;

    if !output.status.success() {
        return Ok(vec![]);
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    Ok(serde_json::from_str(&stdout).unwrap_or_default())
}

/// Get evaluation statistics.
#[tauri::command]
pub async fn get_eval_stats() -> Result<EvalStats, SunwellError> {
    let output = Command::new("sunwell")
        .args(["eval", "--stats", "--json"])
        .output()
        .await
        .map_err(|e| SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e))?;

    if !output.status.success() {
        // Return empty stats
        return Ok(EvalStats {
            total_runs: 0,
            avg_improvement: 0.0,
            sunwell_wins: 0,
            single_shot_wins: 0,
            ties: 0,
            by_task: std::collections::HashMap::new(),
        });
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    Ok(serde_json::from_str(&stdout).unwrap_or_else(|_| EvalStats {
        total_runs: 0,
        avg_improvement: 0.0,
        sunwell_wins: 0,
        single_shot_wins: 0,
        ties: 0,
        by_task: std::collections::HashMap::new(),
    }))
}
