//! Naaru Unified API - Tauri commands (RFC-083)
//!
//! THE Tauri interface to Naaru. All UI interaction goes through here.
//!
//! This replaces fragmented command files:
//! - interface.rs → naaru_process()
//! - commands.rs → naaru_process()
//! - dag.rs → naaru_convergence()

use crate::error::{ErrorCode, SunwellError};
use crate::sunwell_err;
use crate::util::parse_json_safe;
use serde::{Deserialize, Serialize};
use std::process::Stdio;
use tauri::{Emitter, Window};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES (match Python exactly)
// ═══════════════════════════════════════════════════════════════════════════════

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ProcessMode {
    Auto,
    Chat,
    Agent,
    Interface,
}

impl Default for ProcessMode {
    fn default() -> Self {
        ProcessMode::Auto
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConversationMessage {
    pub role: String,
    pub content: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessInput {
    pub content: String,
    #[serde(default)]
    pub mode: ProcessMode,
    #[serde(default = "default_page_type")]
    pub page_type: String,
    #[serde(default)]
    pub conversation_history: Vec<ConversationMessage>,
    #[serde(default)]
    pub workspace: Option<String>,
    #[serde(default = "default_stream")]
    pub stream: bool,
    #[serde(default = "default_timeout")]
    pub timeout: f64,
    #[serde(default)]
    pub context: serde_json::Value,
}

fn default_page_type() -> String {
    "home".to_string()
}

fn default_stream() -> bool {
    true
}

fn default_timeout() -> f64 {
    300.0
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompositionSpec {
    pub page_type: String,
    pub panels: Vec<serde_json::Value>,
    pub input_mode: String,
    pub suggested_tools: Vec<String>,
    pub confidence: f64,
    pub source: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RoutingDecision {
    pub interaction_type: String,
    pub confidence: f64,
    pub tier: i32,
    pub lens: Option<String>,
    pub page_type: String,
    pub tools: Vec<String>,
    pub mood: Option<String>,
    pub reasoning: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NaaruEvent {
    #[serde(rename = "type")]
    pub event_type: String,
    pub timestamp: String,
    pub data: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessOutput {
    pub response: String,
    pub route_type: String,
    pub confidence: f64,
    pub composition: Option<CompositionSpec>,
    pub tasks_completed: i32,
    pub artifacts: Vec<String>,
    pub events: Vec<NaaruEvent>,
    pub routing: Option<RoutingDecision>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConvergenceSlot {
    pub id: String,
    pub content: serde_json::Value,
    pub relevance: f64,
    pub source: String,
    pub ready: bool,
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAURI COMMANDS
// ═══════════════════════════════════════════════════════════════════════════════

/// Process any input through unified Naaru (RFC-083).
///
/// THE entry point. All UI interaction goes through here.
///
/// # Arguments
/// * `input` - ProcessInput with content and options
///
/// # Returns
/// ProcessOutput with response, routing, and composition
#[tauri::command]
pub async fn naaru_process(input: ProcessInput) -> Result<ProcessOutput, String> {
    // Build CLI command
    let mode_str = match input.mode {
        ProcessMode::Auto => "auto",
        ProcessMode::Chat => "chat",
        ProcessMode::Agent => "agent",
        ProcessMode::Interface => "interface",
    };

    // Call sunwell naaru process
    let output = Command::new("sunwell")
        .args([
            "naaru",
            "process",
            &input.content,
            "--mode",
            mode_str,
            "--page-type",
            &input.page_type,
            "--json",
        ])
        .output()
        .await
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(sunwell_err!(SkillExecutionFailed, "Naaru process failed: {}", stderr)
            .with_hints(vec!["Check the input content", "Verify model availability"])
            .to_json());
    }

    let stdout = String::from_utf8_lossy(&output.stdout);

    // Try to parse the last JSON object (the final output)
    // The output may contain multiple JSON lines if streaming
    let lines: Vec<&str> = stdout.lines().collect();

    // Find the last valid JSON that looks like a ProcessOutput
    let mut response = String::new();
    let mut route_type = "conversation".to_string();
    let mut confidence = 0.0;
    let mut events: Vec<NaaruEvent> = Vec::new();
    let mut composition: Option<CompositionSpec> = None;
    let mut routing: Option<RoutingDecision> = None;
    let mut tasks_completed = 0;
    let mut artifacts: Vec<String> = Vec::new();

    for line in lines {
        if let Ok(event) = parse_json_safe::<NaaruEvent>(line) {
            events.push(event.clone());

            // Extract data from events
            match event.event_type.as_str() {
                "model_tokens" => {
                    if let Some(content) = event.data.get("content").and_then(|v| v.as_str()) {
                        response.push_str(content);
                    }
                }
                "route_decision" => {
                    if let Some(it) = event.data.get("interaction_type").and_then(|v| v.as_str()) {
                        route_type = it.to_string();
                    }
                    if let Some(c) = event.data.get("confidence").and_then(|v| v.as_f64()) {
                        confidence = c;
                    }
                    routing = serde_json::from_value(event.data.clone()).ok();
                }
                "composition_ready" => {
                    composition = serde_json::from_value(event.data.clone()).ok();
                }
                "task_complete" => {
                    tasks_completed += 1;
                    if let Some(artifact) = event.data.get("artifact").and_then(|v| v.as_str()) {
                        artifacts.push(artifact.to_string());
                    }
                }
                _ => {}
            }
        } else if let Ok(output) = parse_json_safe::<ProcessOutput>(line) {
            // Found a complete ProcessOutput - use it directly
            return Ok(output);
        }
    }

    // Build response from accumulated events
    Ok(ProcessOutput {
        response: if response.is_empty() {
            "I'm here to help.".to_string()
        } else {
            response
        },
        route_type,
        confidence,
        composition,
        tasks_completed,
        artifacts,
        events,
        routing,
    })
}

/// Subscribe to real-time Naaru events.
///
/// Opens event stream and emits to window.
#[tauri::command]
pub async fn naaru_subscribe(window: Window) -> Result<(), String> {
    // Start sunwell in streaming mode
    let mut child = Command::new("sunwell")
        .args(["naaru", "process", "--stream", "--json", ""])
        .stdout(Stdio::piped())
        .spawn()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| sunwell_err!(RuntimeProcessFailed, "Failed to capture stdout").to_json())?;
    let reader = BufReader::new(stdout);
    let mut lines = reader.lines();

    // Spawn task to read and emit events
    tokio::spawn(async move {
        while let Ok(Some(line)) = lines.next_line().await {
            if let Ok(event) = parse_json_safe::<NaaruEvent>(&line) {
                let _ = window.emit("naaru_event", event);
            }
        }
    });

    Ok(())
}

/// Read a Convergence slot.
///
/// # Arguments
/// * `slot` - Slot ID like "routing:current" or "composition:current"
///
/// # Returns
/// ConvergenceSlot or null if not found
#[tauri::command]
pub async fn naaru_convergence(slot: String) -> Result<Option<ConvergenceSlot>, String> {
    let output = Command::new("sunwell")
        .args(["naaru", "convergence", "--slot", &slot, "--json"])
        .output()
        .await
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if !output.status.success() {
        return Ok(None);
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    parse_json_safe(&stdout)
        .map_err(|e| sunwell_err!(ConfigInvalid, "Failed to parse convergence: {}", e).to_json())
}

/// Cancel current processing.
#[tauri::command]
pub async fn naaru_cancel() -> Result<(), String> {
    // Send SIGINT to any running sunwell processes
    // For now, this is a no-op - proper cancellation requires process management
    Ok(())
}

// ═══════════════════════════════════════════════════════════════════════════════
// TESTS
// ═══════════════════════════════════════════════════════════════════════════════

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_process_input_defaults() {
        let input: ProcessInput = serde_json::from_str(r#"{"content": "hello"}"#).unwrap();
        assert_eq!(input.content, "hello");
        assert_eq!(input.page_type, "home");
        assert!(input.stream);
        assert_eq!(input.timeout, 300.0);
    }

    #[test]
    fn test_process_mode_serialization() {
        assert_eq!(
            serde_json::to_string(&ProcessMode::Auto).unwrap(),
            "\"auto\""
        );
        assert_eq!(
            serde_json::to_string(&ProcessMode::Chat).unwrap(),
            "\"chat\""
        );
    }
}
