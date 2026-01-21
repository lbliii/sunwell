//! Briefing System — Rolling Handoff Notes for Agent Continuity (RFC-071)
//!
//! Reads the briefing.json file to provide instant project orientation.
//! The briefing is a compressed "where are we now" that provides context
//! at session start without requiring retrieval.

use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use thiserror::Error;

/// Briefing-specific errors
#[derive(Debug, Error)]
pub enum BriefingError {
    #[error("Failed to read briefing: {0}")]
    ReadError(#[from] std::io::Error),

    #[error("Failed to parse briefing: {0}")]
    ParseError(#[from] serde_json::Error),
}

// Implement serialization for Tauri
impl serde::Serialize for BriefingError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        serializer.serialize_str(&self.to_string())
    }
}

/// Briefing status — matches Python BriefingStatus
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum BriefingStatus {
    NotStarted,
    InProgress,
    Blocked,
    Complete,
}

/// Rolling handoff note — read by Studio for project orientation
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Briefing {
    pub mission: String,
    pub status: BriefingStatus,
    pub progress: String,
    pub last_action: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub next_action: Option<String>,
    #[serde(default)]
    pub hazards: Vec<String>,
    #[serde(default)]
    pub blockers: Vec<String>,
    #[serde(default)]
    pub hot_files: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub goal_hash: Option<String>,
    #[serde(default)]
    pub related_learnings: Vec<String>,

    // Dispatch hints (optional)
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub predicted_skills: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub suggested_lens: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub complexity_estimate: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub estimated_files_touched: Option<i32>,

    // Metadata
    pub updated_at: String,
    #[serde(default)]
    pub session_id: String,
}

impl Default for Briefing {
    fn default() -> Self {
        Self {
            mission: String::new(),
            status: BriefingStatus::NotStarted,
            progress: String::new(),
            last_action: String::new(),
            next_action: None,
            hazards: Vec::new(),
            blockers: Vec::new(),
            hot_files: Vec::new(),
            goal_hash: None,
            related_learnings: Vec::new(),
            predicted_skills: Vec::new(),
            suggested_lens: None,
            complexity_estimate: None,
            estimated_files_touched: None,
            updated_at: String::new(),
            session_id: String::new(),
        }
    }
}

// =============================================================================
// Tauri Commands
// =============================================================================

/// Get briefing for a project
#[tauri::command]
pub async fn get_briefing(path: String) -> Result<Option<Briefing>, BriefingError> {
    let project_path = PathBuf::from(&path);
    let briefing_path = project_path.join(".sunwell/memory/briefing.json");

    if !briefing_path.exists() {
        return Ok(None);
    }

    let content = std::fs::read_to_string(&briefing_path)?;
    let briefing: Briefing = serde_json::from_str(&content)?;

    Ok(Some(briefing))
}

/// Check if project has a briefing
#[tauri::command]
pub async fn has_briefing(path: String) -> bool {
    let project_path = PathBuf::from(&path);
    project_path.join(".sunwell/memory/briefing.json").exists()
}

/// Clear/delete the briefing for a project
#[tauri::command]
pub async fn clear_briefing(path: String) -> Result<bool, BriefingError> {
    let project_path = PathBuf::from(&path);
    let briefing_path = project_path.join(".sunwell/memory/briefing.json");

    if briefing_path.exists() {
        std::fs::remove_file(&briefing_path)?;
        Ok(true)
    } else {
        Ok(false)
    }
}
