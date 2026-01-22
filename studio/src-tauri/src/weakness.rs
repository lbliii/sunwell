//! RFC-063: Weakness Cascade Tauri commands.
//!
//! Bridge between frontend and Python CLI for weakness operations.

use crate::util::{parse_json_safe, sunwell_command};
use std::path::PathBuf;

use tauri::Emitter;

use crate::weakness_types::{
    CascadeExecution, CascadePreview, ExtractedContract, WeaknessReport, WeaknessScore,
};

/// Scan project for weaknesses.
///
/// Calls Python CLI with --json flag for structured output.
#[tauri::command]
pub async fn scan_weaknesses(path: String) -> Result<WeaknessReport, String> {
    let project_path = PathBuf::from(&path);

    let output = sunwell_command()
        .args(["weakness", "scan", "--json"])
        .current_dir(&project_path)
        .output()
        .map_err(|e| format!("Failed to run weakness scan: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Weakness scan failed: {}", stderr));
    }

    let report: WeaknessReport = serde_json::from_slice(&output.stdout)
        .map_err(|e| format!("Failed to parse weakness report: {}", e))?;

    Ok(report)
}

/// Preview cascade for a specific weakness.
#[tauri::command]
pub async fn preview_cascade(path: String, artifact_id: String) -> Result<CascadePreview, String> {
    let project_path = PathBuf::from(&path);

    let output = sunwell_command()
        .args(["weakness", "preview", &artifact_id, "--json"])
        .current_dir(&project_path)
        .output()
        .map_err(|e| format!("Failed to preview cascade: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Cascade preview failed: {}", stderr));
    }

    let preview: CascadePreview = serde_json::from_slice(&output.stdout)
        .map_err(|e| format!("Failed to parse cascade preview: {}", e))?;

    Ok(preview)
}

/// Execute cascade fix through agent with event streaming.
#[tauri::command]
pub async fn execute_cascade_fix(
    app: tauri::AppHandle,
    path: String,
    artifact_id: String,
    auto_approve: bool,
    confidence_threshold: f32,
) -> Result<CascadeExecution, String> {
    use std::io::{BufRead, BufReader};
    use std::process::Stdio;

    let project_path = PathBuf::from(&path);

    // Get preview first for the initial event
    let preview = preview_cascade(path.clone(), artifact_id.clone()).await?;

    // Create goal description for cascade
    let goal = format!(
        "Fix weakness in {} ({}) and update {} dependent files",
        artifact_id,
        preview.weakness_types.join(", "),
        preview.total_impacted - 1,
    );

    // Emit cascade started event to UI
    app.emit(
        "cascade_started",
        &serde_json::json!({
            "artifact_id": artifact_id,
            "goal": goal,
            "total_impacted": preview.total_impacted,
        }),
    )
    .map_err(|e| format!("Failed to emit event: {}", e))?;

    // Build args based on options
    let mut args = vec![
        "weakness".to_string(),
        "fix".to_string(),
        artifact_id.clone(),
        "--json".to_string(),
        format!("--confidence-threshold={}", confidence_threshold),
    ];

    if auto_approve {
        args.push("--yes".to_string());
    }

    // Spawn process and stream events
    let mut child = sunwell_command()
        .args(&args)
        .current_dir(&project_path)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to start cascade: {}", e))?;

    let stdout = child.stdout.take().ok_or("No stdout")?;
    let reader = BufReader::new(stdout);

    let mut last_line = String::new();

    // Stream events to frontend
    for line in reader.lines() {
        if let Ok(line) = line {
            last_line = line.clone();
            if let Ok(event) = parse_json_safe::<serde_json::Value>(&line) {
                // Forward to frontend
                let _ = app.emit("agent-event", &event);
            }
        }
    }

    // Wait for completion
    let status = child
        .wait()
        .map_err(|e| format!("Failed to wait for cascade: {}", e))?;

    if !status.success() {
        return Err(format!("Cascade fix failed with exit code: {:?}", status.code()));
    }

    // Parse final execution state from last JSON line (with sanitization per RFC-091)
    let execution: CascadeExecution = parse_json_safe(&last_line)
        .map_err(|e| format!("Failed to parse execution result: {}", e))?;

    // Emit completion event
    app.emit(
        "cascade_complete",
        &serde_json::json!({
            "artifact_id": artifact_id,
            "completed": execution.completed,
            "overall_confidence": execution.overall_confidence,
        }),
    )
    .map_err(|e| format!("Failed to emit completion event: {}", e))?;

    Ok(execution)
}

/// Start wave-by-wave cascade execution.
#[tauri::command]
pub async fn start_cascade_execution(
    path: String,
    artifact_id: String,
    auto_approve: bool,
    confidence_threshold: f32,
) -> Result<CascadeExecution, String> {
    let project_path = PathBuf::from(&path);

    let mut args = vec![
        "weakness".to_string(),
        "fix".to_string(),
        artifact_id.clone(),
        "--wave-by-wave".to_string(),
        "--json".to_string(),
        format!("--confidence-threshold={}", confidence_threshold),
    ];

    if auto_approve {
        args.push("--yes".to_string());
    }

    let output = sunwell_command()
        .args(&args)
        .current_dir(&project_path)
        .output()
        .map_err(|e| format!("Failed to start cascade: {}", e))?;

    let execution: CascadeExecution = serde_json::from_slice(&output.stdout)
        .map_err(|e| format!("Failed to parse execution state: {}", e))?;

    Ok(execution)
}

/// Get weakness overlay data for DAG visualization.
#[tauri::command]
pub async fn get_weakness_overlay(
    path: String,
) -> Result<std::collections::HashMap<String, WeaknessScore>, String> {
    let report = scan_weaknesses(path).await?;

    let mut overlay = std::collections::HashMap::new();
    for weakness in report.weaknesses {
        overlay.insert(weakness.artifact_id.clone(), weakness);
    }

    Ok(overlay)
}

/// Extract contract for a file.
#[tauri::command]
pub async fn extract_contract(
    path: String,
    artifact_id: String,
) -> Result<ExtractedContract, String> {
    let project_path = PathBuf::from(&path);

    let output = sunwell_command()
        .args(["weakness", "extract-contract", &artifact_id, "--json"])
        .current_dir(&project_path)
        .output()
        .map_err(|e| format!("Failed to extract contract: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Contract extraction failed: {}", stderr));
    }

    let contract: ExtractedContract = serde_json::from_slice(&output.stdout)
        .map_err(|e| format!("Failed to parse contract: {}", e))?;

    Ok(contract)
}
