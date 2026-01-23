//! Generative Interface Module (RFC-075)
//!
//! Provides Tauri commands for the LLM-driven interaction routing system.

use crate::error::{ErrorCode, SunwellError};
use crate::sunwell_err;
use crate::util::{parse_json_safe, sunwell_command};
use serde::{Deserialize, Serialize};

/// Output from the generative interface.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InterfaceOutput {
    #[serde(rename = "type")]
    pub output_type: String,
    pub response: Option<String>,
    pub data: Option<serde_json::Value>,
    pub action_type: Option<String>,
    pub success: Option<bool>,
    pub view_type: Option<String>,
    pub workspace_spec: Option<WorkspaceSpec>,
}

/// Workspace specification.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkspaceSpec {
    pub primary: String,
    pub secondary: Vec<String>,
    pub contextual: Vec<String>,
    pub arrangement: String,
    pub seed_content: Option<serde_json::Value>,
}

/// Message in conversation history.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConversationMessage {
    pub role: String,
    pub content: String,
}

/// Process a user goal through the generative interface.
#[tauri::command]
pub async fn process_goal(
    goal: String,
    data_dir: Option<String>,
    history: Option<Vec<ConversationMessage>>,
) -> Result<InterfaceOutput, String> {
    let mut args = vec![
        "interface".to_string(),
        "process".to_string(),
        "-g".to_string(),
        goal,
        "--json".to_string(),
    ];

    if let Some(dir) = data_dir {
        args.push("-d".to_string());
        args.push(dir);
    }

    // Pass conversation history if available
    if let Some(hist) = history {
        if !hist.is_empty() {
            let history_json = serde_json::to_string(&hist)
                .map_err(|e| sunwell_err!(ConfigInvalid, "Failed to serialize history: {}", e).to_json())?;
            args.push("--history".to_string());
            args.push(history_json);
        }
    }

    let output = sunwell_command()
        .args(&args)
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(sunwell_err!(SkillExecutionFailed, "Processing failed: {}", stderr)
            .with_hints(vec!["Check the input goal", "Verify model availability"])
            .to_json());
    }

    let stdout = String::from_utf8_lossy(&output.stdout);

    parse_json_safe(&stdout)
        .map_err(|e| sunwell_err!(ConfigInvalid, "Failed to parse output: {}", e).to_json())
}

/// List configured providers.
#[tauri::command]
pub async fn list_providers(_data_dir: Option<String>) -> Result<Vec<ProviderInfo>, String> {
    // For now, return static info since all providers are always available
    Ok(vec![
        ProviderInfo {
            name: "Calendar".to_string(),
            provider_type: "SunwellCalendar".to_string(),
            status: "active".to_string(),
        },
        ProviderInfo {
            name: "Lists".to_string(),
            provider_type: "SunwellLists".to_string(),
            status: "active".to_string(),
        },
        ProviderInfo {
            name: "Notes".to_string(),
            provider_type: "SunwellNotes".to_string(),
            status: "active".to_string(),
        },
    ])
}

/// Provider information.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProviderInfo {
    pub name: String,
    pub provider_type: String,
    pub status: String,
}

/// Run the interface demo to set up sample data.
#[tauri::command]
pub async fn interface_demo(data_dir: Option<String>) -> Result<String, String> {
    let mut args = vec!["interface".to_string(), "demo".to_string()];

    if let Some(dir) = data_dir {
        args.push("-d".to_string());
        args.push(dir);
    }

    let output = sunwell_command()
        .args(&args)
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(sunwell_err!(SkillExecutionFailed, "Demo failed: {}", stderr).to_json());
    }

    Ok("Demo data created successfully".to_string())
}

/// Result from executing a block action.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlockActionResult {
    pub success: bool,
    pub message: String,
    pub data: Option<serde_json::Value>,
}

/// Speculative UI composition (RFC-082).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompositionSpec {
    pub page_type: String,
    pub panels: Vec<PanelSpec>,
    pub input_mode: String,
    pub suggested_tools: Vec<String>,
    pub confidence: f64,
    pub source: String,
}

/// Panel specification for composition.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PanelSpec {
    pub panel_type: String,
    pub title: Option<String>,
    pub data: Option<serde_json::Value>,
}

/// Predict UI composition (RFC-082 Tier 0/1).
///
/// Fast speculative composition prediction:
/// - Tier 0: Regex pattern matching (~0ms)
/// - Tier 1: Fast model if available (~100-200ms)
///
/// Returns composition spec before full content is ready,
/// enabling skeleton rendering while content streams in.
#[tauri::command]
pub async fn predict_composition(
    input: String,
    current_page: Option<String>,
) -> Result<Option<CompositionSpec>, String> {
    let mut args = vec![
        "interface".to_string(),
        "compose".to_string(),
        "-i".to_string(),
        input,
        "--json".to_string(),
    ];

    if let Some(page) = current_page {
        args.push("--page".to_string());
        args.push(page);
    }

    let output = sunwell_command()
        .args(&args)
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if !output.status.success() {
        // Non-fatal for composition - return None and let full pipeline handle it
        return Ok(None);
    }

    let stdout = String::from_utf8_lossy(&output.stdout);

    parse_json_safe(&stdout)
        .map_err(|e| sunwell_err!(ConfigInvalid, "Failed to parse composition: {}", e).to_json())
}

/// Execute a block action (RFC-080).
///
/// Block actions are quick operations embedded in Home blocks,
/// like completing a habit, checking a list item, etc.
#[tauri::command]
pub async fn execute_block_action(
    action_id: String,
    item_id: Option<String>,
    data_dir: Option<String>,
) -> Result<BlockActionResult, String> {
    let mut args = vec![
        "interface".to_string(),
        "action".to_string(),
        "-a".to_string(),
        action_id.clone(),
        "--json".to_string(),
    ];

    if let Some(id) = item_id {
        args.push("-i".to_string());
        args.push(id);
    }

    if let Some(dir) = data_dir {
        args.push("-d".to_string());
        args.push(dir);
    }

    let output = sunwell_command()
        .args(&args)
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(sunwell_err!(SkillExecutionFailed, "Action '{}' failed: {}", action_id, stderr)
            .with_hints(vec!["Check the action parameters"])
            .to_json());
    }

    let stdout = String::from_utf8_lossy(&output.stdout);

    parse_json_safe(&stdout)
        .map_err(|e| sunwell_err!(ConfigInvalid, "Failed to parse action result: {}", e).to_json())
}
