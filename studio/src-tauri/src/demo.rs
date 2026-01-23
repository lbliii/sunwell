//! Demo execution — The Prism Principle (RFC-095)
//!
//! Tauri commands for running the real demo comparison.
//! Calls `sunwell demo --json` and streams results to frontend.

use crate::error::{ErrorCode, SunwellError};
use serde::{Deserialize, Serialize};
use std::process::Stdio;
use tauri::{Emitter, Window};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES — Match Python `sunwell demo --json` output exactly
// ═══════════════════════════════════════════════════════════════════════════════

/// Demo task configuration (from Python).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DemoTask {
    pub name: String,
    pub prompt: String,
    /// Optional in JSON output, but we include it for list_demo_tasks
    #[serde(default)]
    pub expected_features: Vec<String>,
}

/// Token usage statistics.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct TokenUsage {
    #[serde(default)]
    pub prompt: u32,
    #[serde(default)]
    pub completion: u32,
    #[serde(default)]
    pub total: u32,
}

// ═══════════════════════════════════════════════════════════════════════════════
// BREAKDOWN TYPES — Show what each Sunwell component contributed
// ═══════════════════════════════════════════════════════════════════════════════

/// Lens contribution info.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct LensBreakdown {
    pub name: String,
    pub detected: bool,
    #[serde(default)]
    pub heuristics_applied: Vec<String>,
}

/// Prompt enhancement info.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct PromptBreakdown {
    #[serde(rename = "type")]
    pub prompt_type: String,
    #[serde(default)]
    pub requirements_added: Vec<String>,
}

/// Judge evaluation info.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct JudgeBreakdown {
    pub score: f64,
    #[serde(default)]
    pub issues: Vec<String>,
    pub passed: bool,
}

/// Resonance refinement info.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ResonanceBreakdown {
    pub triggered: bool,
    /// Did refinement actually improve the code?
    #[serde(default)]
    pub succeeded: bool,
    #[serde(default)]
    pub iterations: u32,
    #[serde(default)]
    pub improvements: Vec<String>,
}

/// Final result summary.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ResultBreakdown {
    pub final_score: f64,
    #[serde(default)]
    pub features_achieved: Vec<String>,
    #[serde(default)]
    pub features_missing: Vec<String>,
}

/// Complete component breakdown — shows what each Sunwell feature contributed.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ComponentBreakdown {
    pub lens: LensBreakdown,
    pub prompt: PromptBreakdown,
    pub judge: JudgeBreakdown,
    pub resonance: ResonanceBreakdown,
    pub result: ResultBreakdown,
}

/// Result from a single method — Python flattens score + result into one object.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DemoMethodOutput {
    pub score: f64,
    pub lines: u32,
    pub time_ms: u64,
    pub features: std::collections::HashMap<String, bool>,
    #[serde(default)]
    pub iterations: Option<u32>,
    /// Code is only present in verbose mode
    #[serde(default)]
    pub code: Option<String>,
    /// Token usage statistics
    #[serde(default)]
    pub tokens: Option<TokenUsage>,
}

/// Complete demo comparison result (matches Python output).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DemoComparison {
    pub model: String,
    pub task: DemoTask,
    pub single_shot: DemoMethodOutput,
    pub sunwell: DemoMethodOutput,
    pub improvement_percent: f64,
    /// Component breakdown showing what each Sunwell feature contributed.
    #[serde(default)]
    pub breakdown: Option<ComponentBreakdown>,
}

/// Progress event during demo execution.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DemoProgress {
    pub phase: String,
    pub message: String,
    pub progress: f64,
}

/// Streaming event from `sunwell demo --stream`.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum DemoStreamEvent {
    #[serde(rename = "start")]
    Start {
        model: String,
        task: DemoTask,
    },
    #[serde(rename = "chunk")]
    Chunk {
        method: String,  // "single_shot" or "sunwell"
        content: String,
    },
    #[serde(rename = "phase")]
    Phase {
        method: String,
        phase: String,  // "generating", "judging", "refining"
    },
    #[serde(rename = "complete")]
    Complete(Box<DemoComparison>),
    #[serde(rename = "error")]
    Error {
        message: String,
    },
}

/// Demo input parameters.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DemoInput {
    pub task: Option<String>,
    pub model: Option<String>,
    pub provider: Option<String>,
    /// Request verbose output (includes actual code)
    #[serde(default = "default_verbose")]
    pub verbose: bool,
}

fn default_verbose() -> bool {
    true // Always request code by default
}

// ═══════════════════════════════════════════════════════════════════════════════
// COMMANDS
// ═══════════════════════════════════════════════════════════════════════════════

/// Run demo with streaming progress events.
///
/// Uses `sunwell demo --stream` for parallel execution with real-time updates.
/// Emits events to frontend as NDJSON lines arrive.
#[tauri::command]
pub async fn run_demo_streaming(
    window: Window,
    input: DemoInput,
) -> Result<DemoComparison, SunwellError> {
    // Build command arguments - use --stream for NDJSON output
    let mut args = vec!["demo".to_string(), "--stream".to_string()];
    
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
    
    // Start subprocess with streaming
    let mut child = Command::new("sunwell")
        .args(&args)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e))?;
    
    // Emit starting progress
    let _ = window.emit("demo-progress", DemoProgress {
        phase: "starting".to_string(),
        message: "Starting parallel demo...".to_string(),
        progress: 0.0,
    });
    
    let mut final_result: Option<DemoComparison> = None;
    
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
            match serde_json::from_str::<DemoStreamEvent>(&line) {
                Ok(event) => {
                    match &event {
                        DemoStreamEvent::Start { model, task } => {
                            let _ = window.emit("demo-start", serde_json::json!({
                                "model": model,
                                "task": task,
                            }));
                        }
                        DemoStreamEvent::Chunk { method, content } => {
                            let _ = window.emit("demo-chunk", serde_json::json!({
                                "method": method,
                                "content": content,
                            }));
                        }
                        DemoStreamEvent::Phase { method, phase } => {
                            let _ = window.emit("demo-phase", serde_json::json!({
                                "method": method,
                                "phase": phase,
                            }));
                        }
                        DemoStreamEvent::Complete(comparison) => {
                            final_result = Some(*comparison.clone());
                            let _ = window.emit("demo-complete", comparison.as_ref());
                        }
                        DemoStreamEvent::Error { message } => {
                            let _ = window.emit("demo-error", serde_json::json!({
                                "message": message,
                            }));
                        }
                    }
                }
                Err(e) => {
                    // Log parse error but continue
                    eprintln!("Failed to parse NDJSON line: {} - {}", e, line);
                }
            }
        }
    }
    
    // Wait for completion
    let status = child.wait().await
        .map_err(|e| SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e))?;
    
    if !status.success() {
        return Err(SunwellError::new(
            ErrorCode::RuntimeProcessFailed,
            "Demo execution failed",
        ));
    }
    
    // Return final result
    final_result.ok_or_else(|| SunwellError::new(
        ErrorCode::ConfigInvalid,
        "No complete event received from demo stream",
    ))
}

/// List available demo tasks.
#[tauri::command]
pub async fn list_demo_tasks() -> Result<Vec<DemoTask>, SunwellError> {
    // Call sunwell demo --list-tasks --json (if supported) or return built-in list
    // For now, return the known built-in tasks
    Ok(vec![
        DemoTask {
            name: "divide".to_string(),
            prompt: "Write a Python function to divide two numbers".to_string(),
            expected_features: vec![
                "type_hints".to_string(),
                "docstring".to_string(),
                "zero_division_handling".to_string(),
                "type_validation".to_string(),
            ],
        },
        DemoTask {
            name: "add".to_string(),
            prompt: "Write a Python function to add two numbers".to_string(),
            expected_features: vec![
                "type_hints".to_string(),
                "docstring".to_string(),
                "type_validation".to_string(),
            ],
        },
        DemoTask {
            name: "sort".to_string(),
            prompt: "Write a Python function to sort a list".to_string(),
            expected_features: vec![
                "type_hints".to_string(),
                "docstring".to_string(),
                "empty_list_handling".to_string(),
                "edge_case_handling".to_string(),
            ],
        },
        DemoTask {
            name: "fibonacci".to_string(),
            prompt: "Write a Python function to compute the nth Fibonacci number".to_string(),
            expected_features: vec![
                "type_hints".to_string(),
                "docstring".to_string(),
                "negative_input_handling".to_string(),
                "memoization_or_iteration".to_string(),
            ],
        },
        DemoTask {
            name: "validate_email".to_string(),
            prompt: "Write a Python function to validate an email address".to_string(),
            expected_features: vec![
                "type_hints".to_string(),
                "docstring".to_string(),
                "regex_pattern".to_string(),
                "edge_case_handling".to_string(),
            ],
        },
    ])
}
