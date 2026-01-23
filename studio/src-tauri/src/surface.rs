//! Surface Primitives & Layout System (RFC-072)
//!
//! Provides Tauri commands for surface composition and primitive registry.
//! Calls Python CLI for composition logic.

use crate::error::{ErrorCode, SunwellError};
use crate::sunwell_err;
use crate::util::sunwell_command;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// =============================================================================
// TYPES
// =============================================================================

/// Definition of a UI primitive.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PrimitiveDef {
    pub id: String,
    pub category: String,
    pub component: String,
    pub can_be_primary: bool,
    pub can_be_secondary: bool,
    pub can_be_contextual: bool,
    pub default_size: String,
    pub size_options: Vec<String>,
}

/// A primitive instance in a surface layout.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SurfacePrimitive {
    pub id: String,
    pub category: String,
    pub size: String,
    pub props: HashMap<String, serde_json::Value>,
}

/// A composed surface layout.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SurfaceLayout {
    pub primary: SurfacePrimitive,
    pub secondary: Vec<SurfacePrimitive>,
    pub contextual: Vec<SurfacePrimitive>,
    pub arrangement: String,
}

/// Event from a primitive to Python.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PrimitiveEvent {
    pub primitive_id: String,
    pub event_type: String,
    pub data: HashMap<String, serde_json::Value>,
}

// =============================================================================
// TAURI COMMANDS
// =============================================================================

/// Get the primitive registry.
#[tauri::command]
pub fn get_primitive_registry() -> Result<Vec<PrimitiveDef>, String> {
    let output = sunwell_command()
        .args(["surface", "registry", "--json"])
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(sunwell_err!(RuntimeProcessFailed, "Command failed: {}", stderr).to_json());
    }

    serde_json::from_slice(&output.stdout)
        .map_err(|e| sunwell_err!(ConfigInvalid, "Failed to parse registry: {}", e).to_json())
}

/// Compose a surface layout for the given goal.
#[tauri::command]
pub async fn compose_surface(
    goal: String,
    project_path: Option<String>,
    lens: Option<String>,
    arrangement: Option<String>,
) -> Result<SurfaceLayout, String> {
    let mut args = vec![
        "surface".to_string(),
        "compose".to_string(),
        "--goal".to_string(),
        goal,
        "--json".to_string(),
    ];

    if let Some(ref path) = project_path {
        args.push("--project".to_string());
        args.push(path.clone());
    }

    if let Some(ref l) = lens {
        args.push("--lens".to_string());
        args.push(l.clone());
    }

    if let Some(ref arr) = arrangement {
        args.push("--arrangement".to_string());
        args.push(arr.clone());
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
        return Err(sunwell_err!(SkillExecutionFailed, "Composition failed: {}", stderr).to_json());
    }

    serde_json::from_slice(&output.stdout)
        .map_err(|e| sunwell_err!(ConfigInvalid, "Failed to parse surface layout: {}", e).to_json())
}

/// Save a layout as successful for future reference.
#[tauri::command]
pub async fn record_layout_success(
    layout: SurfaceLayout,
    goal: String,
    duration_seconds: u64,
    completed: bool,
) -> Result<(), String> {
    let layout_json = serde_json::to_string(&layout)
        .map_err(|e| sunwell_err!(ConfigInvalid, "Failed to serialize layout: {}", e).to_json())?;

    let output = sunwell_command()
        .args([
            "surface",
            "record",
            "--goal",
            &goal,
            "--layout",
            &layout_json,
            "--duration",
            &duration_seconds.to_string(),
            "--completed",
            &completed.to_string(),
        ])
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(sunwell_err!(SkillExecutionFailed, "Recording failed: {}", stderr).to_json());
    }

    Ok(())
}

/// Emit an event from a primitive.
#[tauri::command]
pub async fn emit_primitive_event(event: PrimitiveEvent) -> Result<(), String> {
    // Route to appropriate handler based on event type
    // For now, we just acknowledge the event. Future: route to Python for processing.
    match event.event_type.as_str() {
        "file_edit" | "terminal_output" | "test_result" | "user_action" => {
            // Event acknowledged - can be extended to trigger Python handlers
        }
        _ => {
            return Err(format!("Unknown primitive event type: {}", event.event_type));
        }
    }
    Ok(())
}
