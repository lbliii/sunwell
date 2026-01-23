//! Lens types and commands for Sunwell Studio (RFC-064, RFC-070).
//!
//! Provides lens discovery, selection, library management, and project configuration.

use crate::error::{ErrorCode, SunwellError};
use crate::sunwell_err;
use crate::util::{parse_json_safe, sunwell_command};
use serde::{Deserialize, Serialize};
use std::path::Path;

/// Lens summary for UI display.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LensSummary {
    pub name: String,
    pub domain: Option<String>,
    pub version: String,
    pub description: Option<String>,
    pub path: String,
    pub heuristics_count: usize,
    pub skills_count: usize,
}

// =============================================================================
// RFC-070: Lens Library Types
// =============================================================================

/// Lens library entry for UI display.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LensLibraryEntry {
    pub name: String,
    pub domain: Option<String>,
    pub version: String,
    pub description: Option<String>,
    pub source: String, // "builtin", "user"
    pub path: String,
    pub is_default: bool,
    pub is_editable: bool,
    pub version_count: usize,
    pub last_modified: Option<String>,
    pub heuristics_count: usize,
    pub skills_count: usize,
    pub use_cases: Vec<String>,
    pub tags: Vec<String>,
    
    // RFC-100: Discovery features
    /// Top 3 heuristics for hover preview (pre-computed)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub top_heuristics: Option<Vec<HeuristicSummary>>,
    /// Last time this lens was activated (ISO 8601)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub last_used: Option<String>,
    /// Usage counts for last 7 days (for sparkline)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub usage_history: Option<Vec<u32>>,
}

/// Version info for a lens.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LensVersionInfo {
    pub version: String,
    pub created_at: String,
    pub message: Option<String>,
    pub checksum: String,
}

/// Result of lens fork operation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ForkResult {
    pub success: bool,
    pub path: String,
    pub message: String,
}

/// Result of lens save operation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SaveResult {
    pub success: bool,
    pub new_version: String,
    pub message: String,
}

/// Heuristic summary for preview.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HeuristicSummary {
    pub name: String,
    pub rule: String,
    pub priority: f32,
}

/// Lens detail for preview.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LensDetail {
    pub name: String,
    pub domain: Option<String>,
    pub version: String,
    pub description: Option<String>,
    pub author: Option<String>,
    pub heuristics: Vec<HeuristicSummary>,
    pub communication_style: Option<String>,
    pub skills: Vec<String>,
}

/// Project lens configuration.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ProjectLensConfig {
    pub default_lens: Option<String>,
    pub auto_select: bool,
}

impl ProjectLensConfig {
    /// Load lens configuration from a project's .sunwell/config.yaml.
    pub fn load(project_path: &Path) -> Self {
        let config_path = project_path.join(".sunwell/config.yaml");
        if config_path.exists() {
            if let Ok(content) = std::fs::read_to_string(&config_path) {
                if let Ok(config) = serde_yaml::from_str::<serde_yaml::Value>(&content) {
                    return Self {
                        default_lens: config
                            .get("default_lens")
                            .and_then(|v| v.as_str())
                            .map(String::from),
                        auto_select: config
                            .get("auto_lens")
                            .and_then(|v| v.as_bool())
                            .unwrap_or(true),
                    };
                }
            }
        }
        Self::default()
    }

    /// Save lens configuration to a project's .sunwell/config.yaml.
    pub fn save(&self, project_path: &Path) -> Result<(), String> {
        let config_path = project_path.join(".sunwell/config.yaml");

        // Load existing config or create new
        let mut config: serde_yaml::Value = if config_path.exists() {
            let content =
                std::fs::read_to_string(&config_path).map_err(|e| e.to_string())?;
            serde_yaml::from_str(&content)
                .unwrap_or(serde_yaml::Value::Mapping(Default::default()))
        } else {
            serde_yaml::Value::Mapping(Default::default())
        };

        // Update lens fields
        if let serde_yaml::Value::Mapping(ref mut map) = config {
            if let Some(lens) = &self.default_lens {
                map.insert(
                    serde_yaml::Value::String("default_lens".into()),
                    serde_yaml::Value::String(lens.clone()),
                );
            } else {
                map.remove(&serde_yaml::Value::String("default_lens".into()));
            }
            map.insert(
                serde_yaml::Value::String("auto_lens".into()),
                serde_yaml::Value::Bool(self.auto_select),
            );
        }

        // Ensure directory exists
        if let Some(parent) = config_path.parent() {
            std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }

        let yaml = serde_yaml::to_string(&config).map_err(|e| e.to_string())?;
        std::fs::write(&config_path, yaml).map_err(|e| e.to_string())?;

        Ok(())
    }
}

/// List all available lenses by calling the Python CLI.
#[tauri::command]
pub async fn list_lenses() -> Result<Vec<LensSummary>, String> {
    let output = sunwell_command()
        .args(["lens", "list", "--json"])
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(sunwell_err!(LensNotFound, "Failed to list lenses: {}", stderr).to_json());
    }

    let json_str = String::from_utf8_lossy(&output.stdout);
    parse_json_safe(&json_str)
        .map_err(|e| sunwell_err!(ConfigInvalid, "Failed to parse lens list: {}", e).to_json())
}

/// Get details of a specific lens.
#[tauri::command]
pub async fn get_lens_detail(name: String) -> Result<LensDetail, String> {
    let output = sunwell_command()
        .args(["lens", "show", &name, "--json"])
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(sunwell_err!(LensNotFound, "Lens '{}' not found: {}", name, stderr)
            .with_hints(vec!["Run 'sunwell lens list' to see available lenses"])
            .to_json());
    }

    let json_str = String::from_utf8_lossy(&output.stdout);
    parse_json_safe(&json_str)
        .map_err(|e| sunwell_err!(ConfigInvalid, "Failed to parse lens detail: {}", e).to_json())
}

/// Get project lens configuration.
#[tauri::command]
pub async fn get_project_lens_config(path: String) -> Result<ProjectLensConfig, String> {
    let project_path = std::path::PathBuf::from(&path);
    Ok(ProjectLensConfig::load(&project_path))
}

/// Set project default lens.
#[tauri::command]
pub async fn set_project_lens(
    path: String,
    lens_name: Option<String>,
    auto_select: bool,
) -> Result<(), String> {
    let project_path = std::path::PathBuf::from(&path);
    let config = ProjectLensConfig {
        default_lens: lens_name,
        auto_select,
    };
    config.save(&project_path)
}

// =============================================================================
// RFC-070: Lens Library Commands
// =============================================================================

/// Get lens library with full metadata.
#[tauri::command]
pub async fn get_lens_library(filter: Option<String>) -> Result<Vec<LensLibraryEntry>, String> {
    let mut args = vec!["lens", "library", "--json"];

    let filter_owned: String;
    if let Some(ref f) = filter {
        filter_owned = f.clone();
        args.push("--filter");
        args.push(&filter_owned);
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
        return Err(sunwell_err!(LensNotFound, "Failed to get lens library: {}", stderr).to_json());
    }

    let json_str = String::from_utf8_lossy(&output.stdout);
    parse_json_safe(&json_str)
        .map_err(|e| sunwell_err!(ConfigInvalid, "Failed to parse lens library: {}", e).to_json())
}

/// Fork a lens to create an editable copy.
#[tauri::command]
pub async fn fork_lens(
    source_name: String,
    new_name: String,
    message: Option<String>,
) -> Result<ForkResult, String> {
    let mut args = vec!["lens", "fork", &source_name, &new_name];

    let msg_owned: String;
    if let Some(ref m) = message {
        msg_owned = format!("-m={}", m);
        args.push(&msg_owned);
    }

    let output = sunwell_command()
        .args(&args)
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    let success = output.status.success();
    let out_message = if success {
        String::from_utf8_lossy(&output.stdout).to_string()
    } else {
        String::from_utf8_lossy(&output.stderr).to_string()
    };

    Ok(ForkResult {
        success,
        path: format!(
            "~/.sunwell/lenses/{}.lens",
            new_name.to_lowercase().replace(' ', "-")
        ),
        message: out_message,
    })
}

/// Save changes to a lens with version tracking.
#[tauri::command]
pub async fn save_lens(
    name: String,
    content: String,
    message: Option<String>,
    bump: Option<String>,
) -> Result<SaveResult, String> {
    // Write content to temp file
    let temp_path = std::env::temp_dir().join(format!("{}-edit.lens", name));
    std::fs::write(&temp_path, &content).map_err(|e| {
        SunwellError::from_error(ErrorCode::FileWriteFailed, e)
            .with_hints(vec!["Check disk space and permissions"])
            .to_json()
    })?;

    // Call Python CLI with the content
    let temp_str = temp_path.to_string_lossy().to_string();
    let mut args = vec!["lens", "save", &name, "--file", &temp_str];

    let msg_owned: String;
    if let Some(ref m) = message {
        msg_owned = format!("-m={}", m);
        args.push(&msg_owned);
    }

    let bump_owned: String;
    if let Some(ref b) = bump {
        bump_owned = format!("--bump={}", b);
        args.push(&bump_owned);
    }

    let output = sunwell_command()
        .args(&args)
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    // Clean up temp file
    let _ = std::fs::remove_file(&temp_path);

    let success = output.status.success();
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();

    Ok(SaveResult {
        success,
        new_version: if success {
            // Parse version from output
            stdout
                .lines()
                .find(|l| l.contains('v'))
                .unwrap_or("")
                .to_string()
        } else {
            String::new()
        },
        message: if success {
            stdout
        } else {
            String::from_utf8_lossy(&output.stderr).to_string()
        },
    })
}

/// Delete a user lens.
#[tauri::command]
pub async fn delete_lens(name: String) -> Result<(), String> {
    let output = sunwell_command()
        .args(["lens", "delete", &name, "--yes"])
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(sunwell_err!(LensNotFound, "Failed to delete lens '{}': {}", name, stderr)
            .with_hints(vec!["Check if the lens exists", "Builtin lenses cannot be deleted"])
            .to_json());
    }

    Ok(())
}

/// Get version history for a lens.
#[tauri::command]
pub async fn get_lens_versions(name: String) -> Result<Vec<LensVersionInfo>, String> {
    let output = sunwell_command()
        .args(["lens", "versions", &name, "--json"])
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(sunwell_err!(LensNotFound, "Failed to get versions for '{}': {}", name, stderr).to_json());
    }

    let json_str = String::from_utf8_lossy(&output.stdout);
    parse_json_safe(&json_str)
        .map_err(|e| sunwell_err!(ConfigInvalid, "Failed to parse lens versions: {}", e).to_json())
}

/// Rollback a lens to a previous version.
#[tauri::command]
pub async fn rollback_lens(name: String, version: String) -> Result<(), String> {
    let output = sunwell_command()
        .args(["lens", "rollback", &name, &version])
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(sunwell_err!(LensVersionConflict, "Failed to rollback '{}' to {}: {}", name, version, stderr)
            .with_hints(vec!["Check if the version exists"])
            .to_json());
    }

    Ok(())
}

/// Set the global default lens.
#[tauri::command]
pub async fn set_default_lens(name: Option<String>) -> Result<(), String> {
    let args: Vec<&str> = if let Some(ref n) = name {
        vec!["lens", "set-default", n]
    } else {
        vec!["lens", "set-default", "--clear"]
    };

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
        return Err(sunwell_err!(LensNotFound, "Failed to set default lens: {}", stderr)
            .with_hints(vec!["Check if the lens exists"])
            .to_json());
    }

    Ok(())
}

/// Get raw lens content for editing.
#[tauri::command]
pub async fn get_lens_content(name: String) -> Result<String, String> {
    // Find lens path - check user lenses first
    let user_path = dirs::home_dir()
        .ok_or_else(|| sunwell_err!(ConfigMissing, "Could not find home directory").to_json())?
        .join(".sunwell")
        .join("lenses")
        .join(format!("{}.lens", name));

    if user_path.exists() {
        return std::fs::read_to_string(&user_path).map_err(|e| {
            SunwellError::from_error(ErrorCode::FileNotFound, e)
                .with_hints(vec!["Check file permissions"])
                .to_json()
        });
    }

    // Try builtin path (cwd/lenses)
    let builtin_path = std::env::current_dir()
        .map_err(|e| sunwell_err!(RuntimeStateInvalid, "Failed to get current dir: {}", e).to_json())?
        .join("lenses")
        .join(format!("{}.lens", name));

    if builtin_path.exists() {
        return std::fs::read_to_string(&builtin_path).map_err(|e| {
            SunwellError::from_error(ErrorCode::FileNotFound, e)
                .with_hints(vec!["Check file permissions"])
                .to_json()
        });
    }

    Err(sunwell_err!(LensNotFound, "Lens not found: {}", name)
        .with_hints(vec!["Run 'sunwell lens list' to see available lenses"])
        .to_json())
}

/// Export a lens to a file (RFC-100).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExportResult {
    pub success: bool,
    pub path: String,
    pub message: String,
}

#[tauri::command]
pub async fn export_lens(
    name: String,
    output_path: Option<String>,
    format: Option<String>,
) -> Result<ExportResult, String> {
    let fmt = format.unwrap_or_else(|| "yaml".to_string());
    
    let mut args = vec!["lens", "export", &name];
    
    let output_owned: String;
    if let Some(ref path) = output_path {
        output_owned = format!("-o={}", path);
        args.push(&output_owned);
    }
    
    let fmt_owned = format!("--format={}", fmt);
    args.push(&fmt_owned);
    
    let output = sunwell_command()
        .args(&args)
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;
    
    let success = output.status.success();
    let message = if success {
        String::from_utf8_lossy(&output.stdout).to_string()
    } else {
        String::from_utf8_lossy(&output.stderr).to_string()
    };
    
    // Determine the actual output path
    let actual_path = if let Some(p) = output_path {
        p
    } else {
        format!("{}.lens", name.to_lowercase().replace(' ', "-"))
    };
    
    Ok(ExportResult {
        success,
        path: actual_path,
        message,
    })
}

/// Record lens activation for usage tracking (RFC-100).
#[tauri::command]
pub async fn record_lens_usage(name: String) -> Result<(), String> {
    let output = sunwell_command()
        .args(["lens", "record-usage", &name])
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;
    
    // Non-critical - don't fail if usage tracking fails
    if !output.status.success() {
        eprintln!("Warning: Failed to record lens usage: {}", 
            String::from_utf8_lossy(&output.stderr));
    }
    
    Ok(())
}
