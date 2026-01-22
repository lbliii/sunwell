//! Workflow Commands — Autonomous workflow execution (RFC-086)
//!
//! Provides Tauri commands for:
//! - Intent routing (natural language → workflow)
//! - Workflow execution (start, stop, resume, skip)
//! - State persistence queries

use serde::{Deserialize, Serialize};
use crate::util::{parse_json_safe, sunwell_command};

// =============================================================================
// TYPES
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Intent {
    pub category: String,
    pub confidence: f64,
    pub signals: Vec<String>,
    pub suggested_workflow: Option<String>,
    pub tier: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkflowChain {
    pub name: String,
    pub description: String,
    pub steps: Vec<String>,
    pub checkpoint_after: Vec<usize>,
    pub tier: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkflowStep {
    pub skill: String,
    pub purpose: String,
    pub status: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub duration_s: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkflowContext {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub lens: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub target_file: Option<String>,
    pub working_dir: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkflowExecution {
    pub id: String,
    pub chain_name: String,
    pub description: String,
    pub current_step: usize,
    pub total_steps: usize,
    pub steps: Vec<WorkflowStep>,
    pub status: String,
    pub started_at: String,
    pub updated_at: String,
    pub context: WorkflowContext,
}

// =============================================================================
// COMMANDS
// =============================================================================

/// Route natural language input to a workflow intent.
#[tauri::command]
pub async fn route_workflow_intent(user_input: String) -> Result<Intent, String> {
    let output = sunwell_command()
        .args(["workflow", "auto", "--json", &user_input])
        .output()
        .map_err(|e| format!("Failed to route intent: {}", e))?;

    if !output.status.success() {
        // Fallback to simple classification
        return Ok(classify_intent_fallback(&user_input));
    }

    let json_str = String::from_utf8_lossy(&output.stdout);
    parse_json_safe(&json_str).map_err(|e| format!("Failed to parse intent: {}", e))
}

/// Start a workflow chain.
#[tauri::command]
pub async fn start_workflow(
    chain_name: String,
    target_file: Option<String>,
) -> Result<WorkflowExecution, String> {
    let mut args = vec!["workflow", "run", &chain_name, "--json"];

    let target_owned: String;
    if let Some(target) = &target_file {
        args.push("--target");
        target_owned = target.clone();
        args.push(&target_owned);
    }

    let output = sunwell_command()
        .args(&args)
        .output()
        .map_err(|e| format!("Failed to start workflow: {}", e))?;

    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }

    let json_str = String::from_utf8_lossy(&output.stdout);
    parse_json_safe(&json_str).map_err(|e| format!("Failed to parse execution: {}", e))
}

/// Stop a running workflow.
#[tauri::command]
pub async fn stop_workflow(execution_id: String) -> Result<(), String> {
    let output = sunwell_command()
        .args(["workflow", "stop", &execution_id])
        .output()
        .map_err(|e| format!("Failed to stop workflow: {}", e))?;

    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }

    Ok(())
}

/// Resume a paused workflow.
#[tauri::command]
pub async fn resume_workflow(execution_id: String) -> Result<WorkflowExecution, String> {
    let output = sunwell_command()
        .args(["workflow", "resume", "--id", &execution_id, "--json"])
        .output()
        .map_err(|e| format!("Failed to resume workflow: {}", e))?;

    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }

    let json_str = String::from_utf8_lossy(&output.stdout);
    parse_json_safe(&json_str).map_err(|e| format!("Failed to parse execution: {}", e))
}

/// Skip the current workflow step.
#[tauri::command]
pub async fn skip_workflow_step(execution_id: String) -> Result<(), String> {
    let output = sunwell_command()
        .args(["workflow", "skip", &execution_id])
        .output()
        .map_err(|e| format!("Failed to skip step: {}", e))?;

    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }

    Ok(())
}

/// List available workflow chains.
#[tauri::command]
pub async fn list_workflow_chains() -> Result<Vec<WorkflowChain>, String> {
    let output = sunwell_command()
        .args(["workflow", "chains", "--json"])
        .output()
        .map_err(|e| format!("Failed to list chains: {}", e))?;

    if !output.status.success() {
        // Return default chains
        return Ok(default_chains());
    }

    let json_str = String::from_utf8_lossy(&output.stdout);
    parse_json_safe(&json_str).unwrap_or_else(|_| default_chains())
        .pipe(Ok)
}

/// List active workflows.
#[tauri::command]
pub async fn list_active_workflows() -> Result<Vec<WorkflowExecution>, String> {
    let output = sunwell_command()
        .args(["workflow", "list", "--json"])
        .output()
        .map_err(|e| format!("Failed to list workflows: {}", e))?;

    if !output.status.success() {
        return Ok(vec![]);
    }

    let json_str = String::from_utf8_lossy(&output.stdout);
    parse_json_safe(&json_str).unwrap_or_else(|_| vec![])
        .pipe(Ok)
}

// =============================================================================
// HELPERS
// =============================================================================

fn classify_intent_fallback(input: &str) -> Intent {
    let input_lower = input.to_lowercase();

    let (category, workflow) = if input_lower.contains("audit") || input_lower.contains("check") {
        ("validation", Some("health-check"))
    } else if input_lower.contains("document") || input_lower.contains("write") {
        ("creation", Some("feature-docs"))
    } else if input_lower.contains("fix") || input_lower.contains("improve") {
        ("transformation", Some("quick-fix"))
    } else if input_lower.contains("modernize") || input_lower.contains("update") {
        ("transformation", Some("modernize"))
    } else {
        ("information", None)
    };

    Intent {
        category: category.to_string(),
        confidence: 0.6,
        signals: vec![],
        suggested_workflow: workflow.map(String::from),
        tier: "light".to_string(),
    }
}

fn default_chains() -> Vec<WorkflowChain> {
    vec![
        WorkflowChain {
            name: "feature-docs".to_string(),
            description: "Document a new feature end-to-end".to_string(),
            steps: vec![
                "context-analyze".to_string(),
                "draft-claims".to_string(),
                "write-structure".to_string(),
                "audit-enhanced".to_string(),
                "apply-style".to_string(),
            ],
            checkpoint_after: vec![1, 3],
            tier: "full".to_string(),
        },
        WorkflowChain {
            name: "health-check".to_string(),
            description: "Comprehensive validation of existing docs".to_string(),
            steps: vec![
                "context-analyze".to_string(),
                "audit-enhanced".to_string(),
                "style-check".to_string(),
                "code-example-audit".to_string(),
                "confidence-score".to_string(),
            ],
            checkpoint_after: vec![],
            tier: "light".to_string(),
        },
        WorkflowChain {
            name: "quick-fix".to_string(),
            description: "Fast issue resolution".to_string(),
            steps: vec![
                "context-analyze".to_string(),
                "auto-select-fixer".to_string(),
                "audit".to_string(),
            ],
            checkpoint_after: vec![],
            tier: "fast".to_string(),
        },
        WorkflowChain {
            name: "modernize".to_string(),
            description: "Update legacy documentation".to_string(),
            steps: vec![
                "audit-enhanced".to_string(),
                "draft-updates".to_string(),
                "modularize-content".to_string(),
                "apply-style".to_string(),
                "reflexion-loop".to_string(),
            ],
            checkpoint_after: vec![0, 3],
            tier: "full".to_string(),
        },
    ]
}

// Pipe trait for cleaner code
trait Pipe: Sized {
    fn pipe<R>(self, f: impl FnOnce(Self) -> R) -> R {
        f(self)
    }
}

impl<T> Pipe for T {}
