//! Generative Interface Module (RFC-075)
//!
//! Provides Tauri commands for the LLM-driven interaction routing system.

use serde::{Deserialize, Serialize};
use std::process::Command;

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

/// Process a user goal through the generative interface.
#[tauri::command]
pub async fn process_goal(
    goal: String,
    data_dir: Option<String>,
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

    let output = Command::new("sunwell")
        .args(&args)
        .output()
        .map_err(|e| format!("Failed to execute sunwell: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Processing failed: {}", stderr));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);

    serde_json::from_str(&stdout).map_err(|e| format!("Failed to parse output: {} - raw: {}", e, stdout))
}

/// List configured providers.
#[tauri::command]
pub async fn list_providers(data_dir: Option<String>) -> Result<Vec<ProviderInfo>, String> {
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

    let output = Command::new("sunwell")
        .args(&args)
        .output()
        .map_err(|e| format!("Failed to execute sunwell: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Demo failed: {}", stderr));
    }

    Ok("Demo data created successfully".to_string())
}
