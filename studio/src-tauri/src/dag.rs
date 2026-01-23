//! DAG Commands — Hierarchical DAG Architecture (RFC-056, RFC-105)
//!
//! RFC-105: Three-level hierarchy (Project → Workspace → Environment)
//! with indexed storage for fast loading and cumulative goal history.
//!
//! Provides commands to:
//! - Load the full DAG from `.sunwell/backlog/` and `.sunwell/plans/`
//! - Load fast index for quick project switching (<10ms target)
//! - Lazy load goal details on demand
//! - Append goals to cumulative history
//! - Execute a specific node from the DAG

use crate::sunwell_err;
use crate::util::{parse_json_safe, sunwell_command};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::fs;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::time::SystemTime;

// =============================================================================
// Public Types (match TypeScript DagGraph)
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DagNode {
    pub id: String,
    pub title: String,
    pub description: String,
    pub status: String, // pending, ready, running, complete, failed, blocked
    pub source: String, // ai, human, external
    pub progress: u8,
    pub priority: f32,
    pub effort: String,
    pub depends_on: Vec<String>,
    pub category: Option<String>,
    pub current_action: Option<String>,
    
    // RFC-067: Task type discrimination
    #[serde(default = "default_task_type")]
    pub task_type: String, // "create", "wire", "verify", "refactor"
    
    // RFC-067: What this node produces (for edge labeling)
    #[serde(default)]
    pub produces: Vec<String>,
}

fn default_task_type() -> String {
    "create".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DagEdge {
    pub id: String,
    pub source: String,
    pub target: String,
    pub artifact: Option<String>,
    
    // RFC-067: Edge type (dependency vs integration)
    #[serde(default = "default_edge_type")]
    pub edge_type: String, // "dependency", "integration"
    
    // RFC-067: Verification status for integration edges
    pub verification_status: Option<String>, // "verified", "missing", "pending"
    
    // RFC-067: What integration this edge represents
    pub integration_type: Option<String>, // "import", "call", "route", etc.
}

fn default_edge_type() -> String {
    "dependency".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DagGraph {
    pub nodes: Vec<DagNode>,
    pub edges: Vec<DagEdge>,
    pub goal: Option<String>,
    pub total_progress: u8,
}

// =============================================================================
// RFC-105: Hierarchical DAG Types
// =============================================================================

/// Index file for fast DAG loading (RFC-105)
/// Stored at <project>/.sunwell/dag/index.json
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct DagIndex {
    /// Schema version for migrations
    pub version: u32,
    /// Project identifier
    pub project_id: String,
    /// Last update timestamp (ISO 8601)
    pub last_updated: String,
    /// Summary statistics
    pub summary: DagSummary,
    /// Goal summaries for quick overview
    pub goals: Vec<GoalSummary>,
    /// Recent artifacts for quick reference
    pub recent_artifacts: Vec<ArtifactSummary>,
}

/// Summary statistics for the index
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct DagSummary {
    pub total_goals: u32,
    pub completed_goals: u32,
    pub total_artifacts: u32,
    pub total_edges: u32,
}

/// Goal summary for index (minimal data for fast load)
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GoalSummary {
    pub id: String,
    pub title: String,
    pub status: String,
    pub completed_at: Option<String>,
    pub created_at: String,
    pub task_count: u32,
}

/// Artifact summary for index
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ArtifactSummary {
    pub id: String,
    pub path: Option<String>,
    pub goal_id: String,
}

/// Full goal node with all details (RFC-105)
/// Stored at <project>/.sunwell/dag/goals/<hash>.json
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GoalNode {
    pub id: String,
    pub title: String,
    pub description: String,
    pub status: String,
    pub created_at: String,
    pub completed_at: Option<String>,
    /// Tasks within this goal
    pub tasks: Vec<TaskNode>,
    /// Learnings from this goal execution
    #[serde(default)]
    pub learnings: Vec<String>,
    /// Execution metrics
    pub metrics: Option<GoalMetrics>,
}

/// Task within a goal
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TaskNode {
    pub id: String,
    pub description: String,
    pub status: String,
    #[serde(default)]
    pub produces: Vec<String>,
    #[serde(default)]
    pub requires: Vec<String>,
    #[serde(default)]
    pub depends_on: Vec<String>,
    pub content_hash: Option<String>,
}

/// Metrics for goal execution
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GoalMetrics {
    pub duration_seconds: Option<u64>,
    pub tasks_completed: u32,
    pub tasks_skipped: u32,
}

/// Edge log entry (RFC-105)
/// Stored in <project>/.sunwell/dag/edges.jsonl (append-only)
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct EdgeLogEntry {
    pub id: String,
    pub source: String,
    pub target: String,
    #[serde(rename = "type")]
    pub edge_type: String,
    pub ts: String,
    /// Integration kind for integration edges
    pub kind: Option<String>,
}

/// Workspace DAG index (RFC-105)
/// Stored at <workspace>/.sunwell/dag/workspace-index.json
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct WorkspaceDagIndex {
    pub workspace_id: String,
    pub last_updated: String,
    pub projects: Vec<ProjectSummary>,
    #[serde(default)]
    pub cross_project_dependencies: Vec<CrossProjectEdge>,
    #[serde(default)]
    pub shared_patterns: Vec<String>,
}

/// Project summary for workspace index
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ProjectSummary {
    pub id: String,
    pub name: String,
    pub path: String,
    pub summary: DagSummary,
    #[serde(default)]
    pub tech_stack: Vec<String>,
    pub last_activity: Option<String>,
}

/// Cross-project dependency edge
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CrossProjectEdge {
    pub source_project: String,
    pub target_project: String,
    pub source_artifact: String,
    pub target_artifact: String,
    pub edge_type: String,
}

/// Environment DAG overview (RFC-105)
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct EnvironmentDag {
    pub user_id: String,
    pub last_updated: String,
    pub workspaces: Vec<WorkspaceSummary>,
    #[serde(default)]
    pub tech_stack_fingerprint: Vec<String>,
    #[serde(default)]
    pub global_patterns: Vec<String>,
}

/// Workspace summary for environment view
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkspaceSummary {
    pub id: String,
    pub path: String,
    pub project_count: u32,
    pub total_goals: u32,
    pub completion_rate: f32,
}

// =============================================================================
// Internal Types (for parsing .sunwell/ files)
// =============================================================================

/// Goal from backlog/current.json
#[derive(Debug, Clone, Deserialize)]
struct BacklogGoal {
    #[allow(dead_code)]
    #[serde(default)]
    id: Option<String>,
    #[serde(default)]
    title: String,
    #[serde(default)]
    description: String,
    #[serde(default)]
    priority: f32,
    #[serde(default)]
    requires: Vec<String>,
    #[serde(default)]
    category: String,
    #[serde(default)]
    source_signals: Vec<String>,
    #[serde(default)]
    estimated_complexity: String,
}

/// Backlog state from backlog/current.json
#[derive(Debug, Default, Deserialize)]
struct Backlog {
    #[serde(default)]
    goals: HashMap<String, BacklogGoal>,
    #[serde(default)]
    completed: HashSet<String>,
    #[serde(default)]
    in_progress: Option<String>,
    #[serde(default)]
    blocked: HashMap<String, String>,
}

/// Task from plans/<hash>.json (current agent output format)
#[derive(Debug, Clone, Deserialize)]
struct PlanTask {
    #[serde(default)]
    id: String,
    #[serde(default)]
    description: String,
    #[serde(default)]
    depends_on: Vec<String>,
    #[serde(default)]
    priority: Option<f32>,
    #[serde(default)]
    category: Option<String>,
    #[serde(default)]
    status: Option<String>, // "completed", "failed", "pending", etc.
    #[serde(default)]
    estimated_effort: Option<String>,
    // produces/requires for DAG edge computation (RFC-034)
    #[serde(default)]
    produces: Vec<String>,
    #[serde(default)]
    requires: Vec<String>,
    // RFC-067: Task type discrimination
    #[serde(default)]
    task_type: Option<String>, // "create", "wire", "verify", "refactor"
}

/// Artifact from plans/<hash>.json (legacy format with graph.artifacts)
#[derive(Debug, Clone, Deserialize)]
struct Artifact {
    #[serde(default)]
    id: String,
    #[serde(default)]
    description: String,
    #[serde(default)]
    depends_on: Vec<String>,
    #[serde(default)]
    priority: Option<f32>,
    #[serde(default)]
    category: Option<String>,
}

/// Graph from plans/<hash>.json (legacy format)
#[derive(Debug, Default, Deserialize)]
struct ArtifactGraph {
    #[serde(default)]
    artifacts: Vec<Artifact>,
}

/// Completion record (legacy format)
#[derive(Debug, Deserialize)]
#[allow(dead_code)]
struct ArtifactCompletion {
    #[serde(default)]
    content_hash: String,
    #[serde(default)]
    verified: bool,
}

/// Saved execution state from plans/<hash>.json
/// Supports both current format (tasks at root) and legacy format (graph.artifacts)
#[derive(Debug, Default, Deserialize)]
struct SavedExecution {
    #[serde(default)]
    goal: String,
    // Legacy format: nested under graph.artifacts
    #[serde(default)]
    graph: ArtifactGraph,
    // Current format: tasks at root level
    #[serde(default)]
    tasks: Vec<PlanTask>,
    // Legacy format: separate completed map
    #[serde(default)]
    completed: HashMap<String, ArtifactCompletion>,
    #[serde(default)]
    failed: HashMap<String, String>,
    #[serde(default)]
    current_artifact: Option<String>,
}

// =============================================================================
// Tauri Commands
// =============================================================================

/// Get the project's DAG by reading .sunwell/backlog/ and .sunwell/plans/
#[tauri::command]
pub async fn get_project_dag(path: String) -> Result<DagGraph, String> {
    let project_path = PathBuf::from(&path);

    // 1. Read backlog (goals)
    let backlog_path = project_path.join(".sunwell/backlog/current.json");
    let backlog = read_backlog(&backlog_path);

    // 2. Read latest execution state (tasks within goals)
    let plans_dir = project_path.join(".sunwell/plans");
    let execution = read_latest_execution(&plans_dir);

    // 3. Merge into DagGraph
    let graph = merge_to_dag(backlog, execution);

    Ok(graph)
}

// =============================================================================
// RFC-105: Hierarchical DAG Commands
// =============================================================================

/// Get the project's DAG index for fast loading (RFC-105)
/// 
/// Returns only the index data (~1KB) for quick project switching.
/// Target: <10ms cold load.
#[tauri::command]
pub async fn get_project_dag_index(path: String) -> Result<DagIndex, String> {
    let project_path = PathBuf::from(&path);
    let index_path = project_path.join(".sunwell/dag/index.json");
    
    // If index exists, read it directly
    if index_path.exists() {
        match fs::read_to_string(&index_path) {
            Ok(content) => {
                return parse_json_safe(&content)
                    .map_err(|e| format!("Failed to parse DAG index: {}", e));
            }
            Err(e) => {
                eprintln!("Failed to read DAG index, will rebuild: {}", e);
            }
        }
    }
    
    // Index doesn't exist or failed to read - build from existing data
    build_dag_index(&project_path).await
}

/// Get full details for a specific goal (RFC-105)
/// 
/// Lazy loads the complete goal data from dag/goals/<hash>.json
#[tauri::command]
pub async fn get_goal_details(path: String, goal_id: String) -> Result<GoalNode, String> {
    let project_path = PathBuf::from(&path);
    let goal_path = project_path.join(format!(".sunwell/dag/goals/{}.json", goal_id));
    
    if goal_path.exists() {
        let content = fs::read_to_string(&goal_path)
            .map_err(|e| format!("Failed to read goal file: {}", e))?;
        return parse_json_safe(&content)
            .map_err(|e| format!("Failed to parse goal file: {}", e));
    }
    
    // Fall back to building from plans/ (migration path)
    build_goal_from_plans(&project_path, &goal_id).await
}

/// Append a completed goal to the DAG (RFC-105)
/// 
/// Called after goal completion to:
/// 1. Write goal file to dag/goals/<hash>.json
/// 2. Append edges to dag/edges.jsonl
/// 3. Update dag/index.json
#[tauri::command]
pub async fn append_goal_to_dag(path: String, goal: GoalNode) -> Result<(), String> {
    let project_path = PathBuf::from(&path);
    let dag_dir = project_path.join(".sunwell/dag");
    let goals_dir = dag_dir.join("goals");
    
    // Ensure directories exist
    fs::create_dir_all(&goals_dir)
        .map_err(|e| format!("Failed to create dag/goals directory: {}", e))?;
    
    // 1. Write goal file
    let goal_path = goals_dir.join(format!("{}.json", goal.id));
    let goal_json = serde_json::to_string_pretty(&goal)
        .map_err(|e| format!("Failed to serialize goal: {}", e))?;
    fs::write(&goal_path, goal_json)
        .map_err(|e| format!("Failed to write goal file: {}", e))?;
    
    // 2. Append edges to edges.jsonl
    let edges_path = dag_dir.join("edges.jsonl");
    append_goal_edges(&edges_path, &goal)?;
    
    // 3. Update index
    update_dag_index(&project_path, &goal).await?;
    
    Ok(())
}

/// Get workspace DAG index (RFC-105 Phase 3)
/// 
/// Aggregates project indexes from all projects in the workspace.
#[tauri::command]
pub async fn get_workspace_dag(path: String) -> Result<WorkspaceDagIndex, String> {
    let workspace_path = PathBuf::from(&path);
    let index_path = workspace_path.join(".sunwell/dag/workspace-index.json");
    
    // If index exists and is recent, return it
    if index_path.exists() {
        match fs::read_to_string(&index_path) {
            Ok(content) => {
                return parse_json_safe(&content)
                    .map_err(|e| format!("Failed to parse workspace index: {}", e));
            }
            Err(e) => {
                eprintln!("Failed to read workspace index, will rebuild: {}", e);
            }
        }
    }
    
    // Build workspace index by scanning project directories
    build_workspace_index(&workspace_path).await
}

/// Refresh workspace index by re-scanning all projects (RFC-105)
#[tauri::command]
pub async fn refresh_workspace_index(path: String) -> Result<WorkspaceDagIndex, String> {
    let workspace_path = PathBuf::from(&path);
    build_workspace_index(&workspace_path).await
}

/// Get environment-level DAG overview (RFC-105 Phase 4)
#[tauri::command]
pub async fn get_environment_dag() -> Result<EnvironmentDag, String> {
    let home = dirs::home_dir()
        .ok_or_else(|| "Could not determine home directory".to_string())?;
    let env_path = home.join(".sunwell/environment-dag.json");
    
    if env_path.exists() {
        let content = fs::read_to_string(&env_path)
            .map_err(|e| format!("Failed to read environment DAG: {}", e))?;
        return parse_json_safe(&content)
            .map_err(|e| format!("Failed to parse environment DAG: {}", e));
    }
    
    // Return empty environment DAG if not configured
    Ok(EnvironmentDag::default())
}

// =============================================================================
// RFC-105: Index Building and Management
// =============================================================================

/// Build DAG index from existing plans/ directory (migration path)
async fn build_dag_index(project_path: &Path) -> Result<DagIndex, String> {
    let plans_dir = project_path.join(".sunwell/plans");
    let backlog_path = project_path.join(".sunwell/backlog/current.json");
    
    let mut index = DagIndex {
        version: 1,
        project_id: generate_project_id(project_path),
        last_updated: iso_now(),
        summary: DagSummary::default(),
        goals: Vec::new(),
        recent_artifacts: Vec::new(),
    };
    
    // Read backlog for goal metadata
    let backlog = read_backlog(&backlog_path);
    
    // Scan plans directory for execution files
    if plans_dir.exists() {
        let mut plan_files: Vec<_> = fs::read_dir(&plans_dir)
            .map_err(|e| format!("Failed to read plans directory: {}", e))?
            .filter_map(|e| e.ok())
            .filter(|e| {
                let path = e.path();
                path.extension().map_or(false, |ext| ext == "json")
                    && !path.to_string_lossy().contains(".trace")
            })
            .collect();
        
        // Sort by modification time (oldest first for chronological order)
        plan_files.sort_by_key(|e| e.metadata().ok().and_then(|m| m.modified().ok()));
        
        for entry in plan_files {
            if let Ok(content) = fs::read_to_string(entry.path()) {
                if let Ok(execution) = parse_json_safe::<SavedExecution>(&content) {
                    // Create goal summary from execution
                    let goal_id = generate_hash(&execution.goal);
                    let task_count = if !execution.tasks.is_empty() {
                        execution.tasks.len() as u32
                    } else {
                        execution.graph.artifacts.len() as u32
                    };
                    
                    let completed_count = if !execution.tasks.is_empty() {
                        execution.tasks.iter()
                            .filter(|t| t.status.as_deref() == Some("completed") || t.status.as_deref() == Some("complete"))
                            .count() as u32
                    } else {
                        execution.completed.len() as u32
                    };
                    
                    let status = if completed_count == task_count && task_count > 0 {
                        "complete".to_string()
                    } else if completed_count > 0 {
                        "in_progress".to_string()
                    } else {
                        "pending".to_string()
                    };
                    
                    // Get file modification time for timestamps
                    let file_time = entry.metadata()
                        .ok()
                        .and_then(|m| m.modified().ok())
                        .map(|t| format_system_time(t))
                        .unwrap_or_else(iso_now);
                    
                    let goal_summary = GoalSummary {
                        id: goal_id.clone(),
                        title: truncate_title(&execution.goal),
                        status,
                        completed_at: if completed_count == task_count && task_count > 0 {
                            Some(file_time.clone())
                        } else {
                            None
                        },
                        created_at: file_time,
                        task_count,
                    };
                    
                    // Check for duplicate goal (same title)
                    if !index.goals.iter().any(|g| g.title == goal_summary.title) {
                        index.goals.push(goal_summary);
                        index.summary.total_goals += 1;
                        if completed_count == task_count && task_count > 0 {
                            index.summary.completed_goals += 1;
                        }
                        index.summary.total_artifacts += task_count;
                    }
                    
                    // Add recent artifacts (last 10)
                    let artifacts: Vec<String> = if !execution.tasks.is_empty() {
                        execution.tasks.iter().flat_map(|t| t.produces.clone()).collect()
                    } else {
                        execution.graph.artifacts.iter().map(|a| a.id.clone()).collect()
                    };
                    
                    for artifact_id in artifacts.iter().take(10) {
                        if index.recent_artifacts.len() < 10 {
                            index.recent_artifacts.push(ArtifactSummary {
                                id: artifact_id.clone(),
                                path: None,
                                goal_id: goal_id.clone(),
                            });
                        }
                    }
                }
            }
        }
    }
    
    // Also include backlog goals not yet executed
    for (goal_id, goal) in &backlog.goals {
        if !index.goals.iter().any(|g| g.id == *goal_id || g.title == goal.title) {
            let status = if backlog.completed.contains(goal_id) {
                "complete".to_string()
            } else if backlog.in_progress.as_ref() == Some(goal_id) {
                "running".to_string()
            } else {
                "pending".to_string()
            };
            
            index.goals.push(GoalSummary {
                id: goal_id.clone(),
                title: if goal.title.is_empty() { truncate_title(&goal.description) } else { truncate_title(&goal.title) },
                status,
                completed_at: None,
                created_at: iso_now(),
                task_count: 0,
            });
            index.summary.total_goals += 1;
        }
    }
    
    // Save index for future fast loads
    let dag_dir = project_path.join(".sunwell/dag");
    if let Err(e) = fs::create_dir_all(&dag_dir) {
        eprintln!("Warning: Could not create dag directory: {}", e);
    } else {
        let index_path = dag_dir.join("index.json");
        if let Ok(json) = serde_json::to_string_pretty(&index) {
            let _ = fs::write(index_path, json);
        }
    }
    
    Ok(index)
}

/// Build goal details from plans/ (migration path)
async fn build_goal_from_plans(project_path: &Path, goal_id: &str) -> Result<GoalNode, String> {
    let plans_dir = project_path.join(".sunwell/plans");
    
    if !plans_dir.exists() {
        return Err(format!("Goal {} not found", goal_id));
    }
    
    // Find the plan file that matches this goal
    let entries: Vec<_> = fs::read_dir(&plans_dir)
        .map_err(|e| format!("Failed to read plans directory: {}", e))?
        .filter_map(|e| e.ok())
        .filter(|e| {
            let path = e.path();
            path.extension().map_or(false, |ext| ext == "json")
                && !path.to_string_lossy().contains(".trace")
        })
        .collect();
    
    for entry in entries {
        if let Ok(content) = fs::read_to_string(entry.path()) {
            if let Ok(execution) = parse_json_safe::<SavedExecution>(&content) {
                let computed_id = generate_hash(&execution.goal);
                if computed_id == goal_id || entry.path().file_stem().map_or(false, |s| s.to_string_lossy() == goal_id) {
                    return execution_to_goal_node(execution, entry.path());
                }
            }
        }
    }
    
    Err(format!("Goal {} not found", goal_id))
}

/// Convert SavedExecution to GoalNode
fn execution_to_goal_node(exec: SavedExecution, file_path: PathBuf) -> Result<GoalNode, String> {
    let file_time = fs::metadata(&file_path)
        .ok()
        .and_then(|m| m.modified().ok())
        .map(|t| format_system_time(t))
        .unwrap_or_else(iso_now);
    
    let tasks: Vec<TaskNode> = if !exec.tasks.is_empty() {
        exec.tasks.iter().map(|t| TaskNode {
            id: t.id.clone(),
            description: t.description.clone(),
            status: t.status.clone().unwrap_or_else(|| "pending".to_string()),
            produces: t.produces.clone(),
            requires: t.requires.clone(),
            depends_on: t.depends_on.clone(),
            content_hash: None,
        }).collect()
    } else {
        exec.graph.artifacts.iter().map(|a| TaskNode {
            id: a.id.clone(),
            description: a.description.clone(),
            status: if exec.completed.contains_key(&a.id) {
                "complete".to_string()
            } else if exec.failed.contains_key(&a.id) {
                "failed".to_string()
            } else {
                "pending".to_string()
            },
            produces: vec![a.id.clone()],
            requires: vec![],
            depends_on: a.depends_on.clone(),
            content_hash: exec.completed.get(&a.id).map(|c| c.content_hash.clone()),
        }).collect()
    };
    
    let completed_count = tasks.iter().filter(|t| t.status == "complete" || t.status == "completed").count() as u32;
    let total_count = tasks.len() as u32;
    
    let status = if completed_count == total_count && total_count > 0 {
        "complete"
    } else if completed_count > 0 {
        "in_progress"
    } else {
        "pending"
    };
    
    Ok(GoalNode {
        id: generate_hash(&exec.goal),
        title: truncate_title(&exec.goal),
        description: exec.goal.clone(),
        status: status.to_string(),
        created_at: file_time.clone(),
        completed_at: if status == "complete" { Some(file_time) } else { None },
        tasks,
        learnings: vec![],
        metrics: Some(GoalMetrics {
            duration_seconds: None,
            tasks_completed: completed_count,
            tasks_skipped: 0,
        }),
    })
}

/// Append edges from a goal to the edge log
fn append_goal_edges(edges_path: &Path, goal: &GoalNode) -> Result<(), String> {
    let mut file = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(edges_path)
        .map_err(|e| format!("Failed to open edges file: {}", e))?;
    
    let ts = iso_now();
    
    // Build edges from task dependencies
    for task in &goal.tasks {
        for dep in &task.depends_on {
            let edge = EdgeLogEntry {
                id: format!("{}->{}", dep, task.id),
                source: dep.clone(),
                target: task.id.clone(),
                edge_type: "dependency".to_string(),
                ts: ts.clone(),
                kind: None,
            };
            let line = serde_json::to_string(&edge)
                .map_err(|e| format!("Failed to serialize edge: {}", e))?;
            writeln!(file, "{}", line)
                .map_err(|e| format!("Failed to write edge: {}", e))?;
        }
        
        // Add produces edges
        for artifact in &task.produces {
            let edge = EdgeLogEntry {
                id: format!("{}->{}", task.id, artifact),
                source: task.id.clone(),
                target: artifact.clone(),
                edge_type: "produces".to_string(),
                ts: ts.clone(),
                kind: None,
            };
            let line = serde_json::to_string(&edge)
                .map_err(|e| format!("Failed to serialize edge: {}", e))?;
            writeln!(file, "{}", line)
                .map_err(|e| format!("Failed to write edge: {}", e))?;
        }
    }
    
    Ok(())
}

/// Update the DAG index with a new goal
async fn update_dag_index(project_path: &Path, goal: &GoalNode) -> Result<(), String> {
    let dag_dir = project_path.join(".sunwell/dag");
    let index_path = dag_dir.join("index.json");
    
    // Read existing index or create new
    let mut index = if index_path.exists() {
        let content = fs::read_to_string(&index_path)
            .map_err(|e| format!("Failed to read index: {}", e))?;
        parse_json_safe::<DagIndex>(&content)
            .unwrap_or_else(|_| build_empty_index(project_path))
    } else {
        build_empty_index(project_path)
    };
    
    // Update with new goal
    let goal_summary = GoalSummary {
        id: goal.id.clone(),
        title: goal.title.clone(),
        status: goal.status.clone(),
        completed_at: goal.completed_at.clone(),
        created_at: goal.created_at.clone(),
        task_count: goal.tasks.len() as u32,
    };
    
    // Remove existing entry if present (update case)
    index.goals.retain(|g| g.id != goal.id);
    index.goals.push(goal_summary);
    
    // Update summary
    index.summary.total_goals = index.goals.len() as u32;
    index.summary.completed_goals = index.goals.iter()
        .filter(|g| g.status == "complete")
        .count() as u32;
    index.summary.total_artifacts = index.goals.iter()
        .map(|g| g.task_count)
        .sum();
    
    index.last_updated = iso_now();
    
    // Write updated index
    fs::create_dir_all(&dag_dir)
        .map_err(|e| format!("Failed to create dag directory: {}", e))?;
    let json = serde_json::to_string_pretty(&index)
        .map_err(|e| format!("Failed to serialize index: {}", e))?;
    fs::write(&index_path, json)
        .map_err(|e| format!("Failed to write index: {}", e))?;
    
    Ok(())
}

/// Build an empty index for a project
fn build_empty_index(project_path: &Path) -> DagIndex {
    DagIndex {
        version: 1,
        project_id: generate_project_id(project_path),
        last_updated: iso_now(),
        summary: DagSummary::default(),
        goals: Vec::new(),
        recent_artifacts: Vec::new(),
    }
}

/// Build workspace index from project directories
async fn build_workspace_index(workspace_path: &Path) -> Result<WorkspaceDagIndex, String> {
    let mut index = WorkspaceDagIndex {
        workspace_id: generate_project_id(workspace_path),
        last_updated: iso_now(),
        projects: Vec::new(),
        cross_project_dependencies: Vec::new(),
        shared_patterns: Vec::new(),
    };
    
    // Scan for projects (directories with .sunwell/)
    if let Ok(entries) = fs::read_dir(workspace_path) {
        for entry in entries.filter_map(|e| e.ok()) {
            let path = entry.path();
            if path.is_dir() && path.join(".sunwell").exists() {
                // Get project index
                if let Ok(project_index) = get_project_dag_index(path.to_string_lossy().to_string()).await {
                    let project_name = path.file_name()
                        .map(|n| n.to_string_lossy().to_string())
                        .unwrap_or_default();
                    
                    index.projects.push(ProjectSummary {
                        id: project_index.project_id,
                        name: project_name,
                        path: path.strip_prefix(workspace_path)
                            .map(|p| p.to_string_lossy().to_string())
                            .unwrap_or_else(|_| path.to_string_lossy().to_string()),
                        summary: project_index.summary,
                        tech_stack: detect_tech_stack(&path),
                        last_activity: project_index.goals.iter()
                            .filter_map(|g| g.completed_at.as_ref())
                            .max()
                            .cloned(),
                    });
                }
            }
        }
    }
    
    // Save workspace index
    let dag_dir = workspace_path.join(".sunwell/dag");
    if let Err(e) = fs::create_dir_all(&dag_dir) {
        eprintln!("Warning: Could not create workspace dag directory: {}", e);
    } else {
        let index_path = dag_dir.join("workspace-index.json");
        if let Ok(json) = serde_json::to_string_pretty(&index) {
            let _ = fs::write(index_path, json);
        }
    }
    
    Ok(index)
}

/// Detect tech stack from project files
fn detect_tech_stack(project_path: &Path) -> Vec<String> {
    let mut stack = Vec::new();
    
    if project_path.join("pyproject.toml").exists() || project_path.join("setup.py").exists() {
        stack.push("python".to_string());
    }
    if project_path.join("package.json").exists() {
        stack.push("javascript".to_string());
    }
    if project_path.join("Cargo.toml").exists() {
        stack.push("rust".to_string());
    }
    if project_path.join("go.mod").exists() {
        stack.push("go".to_string());
    }
    if project_path.join("requirements.txt").exists() {
        // Check for common frameworks
        if let Ok(content) = fs::read_to_string(project_path.join("requirements.txt")) {
            if content.contains("flask") || content.contains("Flask") {
                stack.push("flask".to_string());
            }
            if content.contains("django") || content.contains("Django") {
                stack.push("django".to_string());
            }
            if content.contains("fastapi") || content.contains("FastAPI") {
                stack.push("fastapi".to_string());
            }
        }
    }
    
    stack
}

/// Read edges from the edge log
#[allow(dead_code)]
fn read_edge_log(edges_path: &Path) -> Vec<EdgeLogEntry> {
    if !edges_path.exists() {
        return Vec::new();
    }
    
    let file = match fs::File::open(edges_path) {
        Ok(f) => f,
        Err(_) => return Vec::new(),
    };
    
    let reader = BufReader::new(file);
    reader.lines()
        .filter_map(|line| line.ok())
        .filter_map(|line| serde_json::from_str(&line).ok())
        .collect()
}

// =============================================================================
// Utility Functions
// =============================================================================

/// Generate a stable project ID from path
fn generate_project_id(path: &Path) -> String {
    use std::collections::hash_map::DefaultHasher;
    use std::hash::{Hash, Hasher};
    
    let mut hasher = DefaultHasher::new();
    path.to_string_lossy().hash(&mut hasher);
    format!("{:016x}", hasher.finish())
}

/// Generate a hash for a goal title
fn generate_hash(s: &str) -> String {
    use std::collections::hash_map::DefaultHasher;
    use std::hash::{Hash, Hasher};
    
    let mut hasher = DefaultHasher::new();
    s.hash(&mut hasher);
    format!("{:016x}", hasher.finish())
}

/// Get current time as ISO 8601 string
fn iso_now() -> String {
    chrono::Utc::now().to_rfc3339()
}

/// Format SystemTime as ISO 8601
fn format_system_time(time: SystemTime) -> String {
    let datetime: chrono::DateTime<chrono::Utc> = time.into();
    datetime.to_rfc3339()
}

/// Execute a specific node from the DAG (RFC-056)
/// 
/// For backlog goals, uses `sunwell backlog run <id>` to preserve goal metadata.
/// For execution artifacts, uses `sunwell agent run <description>`.
#[tauri::command]
pub async fn execute_dag_node(
    app: tauri::AppHandle,
    state: tauri::State<'_, crate::commands::AppState>,
    path: String,
    node_id: String,
) -> Result<crate::commands::RunGoalResult, String> {
    let project_path = std::path::PathBuf::from(&path);
    
    // Check if this is a backlog goal
    let backlog_path = project_path.join(".sunwell/backlog/current.json");
    let is_backlog_goal = if backlog_path.exists() {
        match std::fs::read_to_string(&backlog_path) {
            Ok(content) => {
                // Check if node_id exists in the backlog goals
                content.contains(&format!("\"{}\"", node_id)) || 
                content.contains(&format!("\"{}", node_id))
            }
            Err(_) => false,
        }
    } else {
        false
    };

    if is_backlog_goal {
        // Use backlog run command for backlog goals
        let mut agent = state.agent.lock()
            .map_err(|e| sunwell_err!(RuntimeStateInvalid, "Failed to acquire agent lock: {}", e).to_json())?;
        agent.run_backlog_goal(app, &node_id, &project_path, None)
            .map_err(|e| e.to_json())?;
        
        Ok(crate::commands::RunGoalResult {
            success: true,
            message: format!("Backlog goal {} started", node_id),
            workspace_path: crate::workspace::shorten_path(&project_path),
        })
    } else {
        // Fall back to regular agent run for execution artifacts
        let dag = get_project_dag(path.clone()).await?;
        let node = dag
            .nodes
            .iter()
            .find(|n| n.id == node_id)
            .ok_or_else(|| format!("Node {} not found", node_id))?;

        // DAG nodes use auto-lens detection (no explicit lens), default provider
        crate::commands::run_goal(app, state, node.description.clone(), Some(path), None, None, None).await
    }
}

/// Refresh the backlog by scanning for signals (RFC-046)
#[tauri::command]
pub async fn refresh_backlog(path: String) -> Result<DagGraph, String> {
    let project_path = PathBuf::from(&path);
    
    // Run sunwell backlog refresh to scan for signals and update backlog
    let output = sunwell_command()
        .args(["backlog", "refresh"])
        .current_dir(&project_path)
        .output()
        .map_err(|e| format!("Failed to run backlog refresh: {}", e))?;
    
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        // Don't fail on warning-level messages, just log them
        if !stderr.is_empty() {
            eprintln!("backlog refresh stderr: {}", stderr);
        }
    }
    
    // Return the updated DAG
    get_project_dag(path).await
}

// =============================================================================
// RFC-090: Load Plan File
// =============================================================================

/// Plan file format from `sunwell --plan --json` (RFC-090)
/// Used via serde deserialization in `load_plan_file`
#[allow(dead_code)] // Constructed by serde, not directly
#[derive(Debug, Clone, Deserialize)]
struct CliPlanFile {
    #[serde(default)]
    goal: Option<String>,
    #[serde(default)]
    tasks: i64,
    #[serde(default)]
    gates: i64,
    #[serde(default)]
    technique: Option<String>,
    #[serde(default)]
    task_list: Vec<CliTaskSummary>,
    #[serde(default)]
    gate_list: Vec<CliGateSummary>,
    #[serde(default)]
    created_at: Option<String>,
}

/// Task summary from plan file (RFC-090)
/// Used via serde deserialization in `load_plan_file`
#[allow(dead_code)] // Constructed by serde, not directly
#[derive(Debug, Clone, Deserialize)]
struct CliTaskSummary {
    #[serde(default)]
    id: String,
    #[serde(default)]
    description: String,
    #[serde(default)]
    depends_on: Vec<String>,
    #[serde(default)]
    produces: Vec<String>,
    #[serde(default)]
    category: Option<String>,
}

/// Gate summary from plan file (RFC-090)
/// Used via serde deserialization in `load_plan_file`
#[allow(dead_code)] // Constructed by serde, not directly
#[derive(Debug, Clone, Deserialize)]
struct CliGateSummary {
    #[serde(default)]
    id: String,
    #[serde(rename = "type", default)]
    gate_type: String,
    #[serde(default)]
    after_tasks: Vec<String>,
}

/// Load a plan file and convert to DagGraph (RFC-090)
/// 
/// Used when Studio is launched with `--plan <path>` to display
/// a pre-generated plan from `sunwell --plan --json`.
#[tauri::command]
pub async fn load_plan_file(plan_path: String) -> Result<DagGraph, String> {
    let path = PathBuf::from(&plan_path);
    
    if !path.exists() {
        return Err(format!("Plan file not found: {}", plan_path));
    }
    
    let content = std::fs::read_to_string(&path)
        .map_err(|e| format!("Failed to read plan file: {}", e))?;
    
    let plan: CliPlanFile = parse_json_safe(&content)
        .map_err(|e| format!("Failed to parse plan file: {}", e))?;
    
    // Convert plan to DagGraph
    let graph = cli_plan_to_dag_graph(plan)?;
    Ok(graph)
}

/// Convert a CliPlanFile to DagGraph format (RFC-090)
fn cli_plan_to_dag_graph(plan: CliPlanFile) -> Result<DagGraph, String> {
    let mut nodes: Vec<DagNode> = Vec::new();
    let mut edges: Vec<DagEdge> = Vec::new();
    
    // Convert tasks to nodes
    for task in &plan.task_list {
        nodes.push(DagNode {
            id: task.id.clone(),
            title: truncate_title(&task.description),
            description: task.description.clone(),
            status: "pending".to_string(),
            source: "ai".to_string(),
            progress: 0,
            priority: 0.5,
            effort: "medium".to_string(),
            depends_on: task.depends_on.clone(),
            category: task.category.clone(),
            current_action: None,
            task_type: "create".to_string(),
            produces: task.produces.clone(),
        });
        
        // Build edges from dependencies
        for dep in &task.depends_on {
            edges.push(DagEdge {
                id: format!("{}->{}", dep, task.id),
                source: dep.clone(),
                target: task.id.clone(),
                artifact: None,
                edge_type: "dependency".to_string(),
                verification_status: None,
                integration_type: None,
            });
        }
    }
    
    Ok(DagGraph {
        nodes,
        edges,
        goal: plan.goal,
        total_progress: 0,
    })
}

// =============================================================================
// RFC-074: Incremental Execution Commands
// =============================================================================

/// Incremental execution plan response
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct IncrementalPlan {
    pub to_execute: Vec<String>,
    pub to_skip: Vec<String>,
    pub skip_percentage: f32,
    pub decisions: Vec<SkipDecision>,
}

/// Skip decision for a single artifact
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SkipDecision {
    pub artifact_id: String,
    pub can_skip: bool,
    pub reason: String,
    pub current_hash: String,
    pub previous_hash: Option<String>,
    pub last_executed_at: Option<String>,
}

/// Cache statistics response
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CacheStats {
    pub by_status: HashMap<String, i64>,
    pub total_skips: i64,
    pub avg_execution_time_ms: f64,
    pub total_artifacts: i64,
    pub cache_path: String,
}

/// Get the incremental execution plan (RFC-074)
/// 
/// Calls `sunwell dag plan --json` to get which artifacts will skip vs execute.
#[tauri::command]
pub async fn get_incremental_plan(path: String) -> Result<IncrementalPlan, String> {
    let project_path = PathBuf::from(&path);
    
    let output = sunwell_command()
        .args(["dag", "plan", "--json"])
        .current_dir(&project_path)
        .output()
        .map_err(|e| format!("Failed to run sunwell dag plan: {}", e))?;
    
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("dag plan failed: {}", stderr));
    }
    
    let stdout = String::from_utf8_lossy(&output.stdout);
    parse_json_safe(&stdout)
        .map_err(|e| format!("Failed to parse plan output: {} (output: {})", e, stdout))
}

/// Get cache statistics (RFC-074)
/// 
/// Calls `sunwell dag cache stats --json` to get cache metrics.
#[tauri::command]
pub async fn get_cache_stats(path: String) -> Result<CacheStats, String> {
    let project_path = PathBuf::from(&path);
    
    let output = sunwell_command()
        .args(["dag", "cache", "stats", "--json"])
        .current_dir(&project_path)
        .output()
        .map_err(|e| format!("Failed to run sunwell dag cache stats: {}", e))?;
    
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("cache stats failed: {}", stderr));
    }
    
    let stdout = String::from_utf8_lossy(&output.stdout);
    parse_json_safe(&stdout)
        .map_err(|e| format!("Failed to parse cache stats: {} (output: {})", e, stdout))
}

/// Analyze impact of changing an artifact (RFC-074)
/// 
/// Calls `sunwell dag impact <artifact_id> --json` to find affected downstream.
#[tauri::command]
pub async fn get_artifact_impact(path: String, artifact_id: String) -> Result<Vec<String>, String> {
    let project_path = PathBuf::from(&path);
    
    let output = sunwell_command()
        .args(["dag", "impact", &artifact_id, "--json"])
        .current_dir(&project_path)
        .output()
        .map_err(|e| format!("Failed to run sunwell dag impact: {}", e))?;
    
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("impact analysis failed: {}", stderr));
    }
    
    let stdout = String::from_utf8_lossy(&output.stdout);
    parse_json_safe(&stdout)
        .map_err(|e| format!("Failed to parse impact output: {} (output: {})", e, stdout))
}

/// Clear the execution cache (RFC-074)
#[tauri::command]
pub async fn clear_cache(path: String, artifact_id: Option<String>) -> Result<String, String> {
    let project_path = PathBuf::from(&path);
    
    let mut args = vec!["dag", "cache", "clear", "--force"];
    if let Some(ref id) = artifact_id {
        args.push("--artifact");
        args.push(id);
    }
    
    let output = sunwell_command()
        .args(&args)
        .current_dir(&project_path)
        .output()
        .map_err(|e| format!("Failed to run sunwell dag cache clear: {}", e))?;
    
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("cache clear failed: {}", stderr));
    }
    
    Ok("Cache cleared".to_string())
}

// =============================================================================
// File Reading
// =============================================================================

fn read_backlog(path: &Path) -> Backlog {
    if !path.exists() {
        return Backlog::default();
    }

    match std::fs::read_to_string(path) {
        Ok(content) => parse_json_safe(&content).unwrap_or_default(),
        Err(_) => Backlog::default(),
    }
}

fn read_latest_execution(plans_dir: &Path) -> Option<SavedExecution> {
    if !plans_dir.exists() {
        return None;
    }

    // Find most recent .json file (excluding .trace files)
    let mut entries: Vec<_> = match std::fs::read_dir(plans_dir) {
        Ok(entries) => entries
            .filter_map(|e| e.ok())
            .filter(|e| {
                let path = e.path();
                path.extension().map_or(false, |ext| ext == "json")
                    && !path.to_string_lossy().contains(".trace")
            })
            .collect(),
        Err(_) => return None,
    };

    // Sort by modification time (newest last)
    entries.sort_by_key(|e| e.metadata().ok().and_then(|m| m.modified().ok()));

    // Read the latest file
    if let Some(latest) = entries.last() {
        match std::fs::read_to_string(latest.path()) {
            Ok(content) => {
                return parse_json_safe(&content).ok();
            }
            Err(_) => return None,
        }
    }

    None
}

// =============================================================================
// Merge Logic
// =============================================================================

fn merge_to_dag(backlog: Backlog, execution: Option<SavedExecution>) -> DagGraph {
    let mut nodes = Vec::new();
    let mut edges = Vec::new();
    let mut seen_ids: HashSet<String> = HashSet::new();
    let mut completed_count = 0;

    // If we have execution state, use tasks from there
    if let Some(ref exec) = execution {
        // Current format: tasks at root level with embedded status
        if !exec.tasks.is_empty() {
            // Build produces -> task_id map for dependency resolution
            let mut producers: HashMap<String, String> = HashMap::new();
            for task in &exec.tasks {
                for artifact in &task.produces {
                    producers.insert(artifact.clone(), task.id.clone());
                }
            }

            for task in &exec.tasks {
                let status_str = task.status.as_deref().unwrap_or("pending");
                let is_completed = status_str == "completed" || status_str == "complete";
                let is_failed = status_str == "failed";
                let is_running = status_str == "running" || status_str == "in_progress";

                // Compute effective dependencies: use depends_on if set, else resolve from requires
                let effective_deps: Vec<String> = if !task.depends_on.is_empty() {
                    task.depends_on.clone()
                } else {
                    // Resolve requires -> produces to find dependency task IDs
                    task.requires
                        .iter()
                        .filter_map(|req| producers.get(req).cloned())
                        .collect()
                };

                let status = if is_completed {
                    completed_count += 1;
                    "complete"
                } else if is_failed {
                    "failed"
                } else if is_running {
                    "running"
                } else if effective_deps.is_empty()
                    || effective_deps.iter().all(|dep| {
                        exec.tasks
                            .iter()
                            .find(|t| &t.id == dep)
                            .and_then(|t| t.status.as_deref())
                            .map_or(false, |s| s == "completed" || s == "complete")
                    })
                {
                    "ready"
                } else {
                    "blocked"
                };

                // RFC-067: Determine task type
                let task_type = task.task_type.clone().unwrap_or_else(|| "create".to_string());

                nodes.push(DagNode {
                    id: task.id.clone(),
                    title: truncate_title(&task.description),
                    description: task.description.clone(),
                    status: status.to_string(),
                    source: "ai".to_string(),
                    progress: if is_completed { 100 } else { 0 },
                    priority: task.priority.unwrap_or(0.5),
                    effort: task
                        .estimated_effort
                        .clone()
                        .unwrap_or_else(|| "medium".to_string()),
                    depends_on: effective_deps.clone(),
                    category: task.category.clone(),
                    current_action: None,
                    // RFC-067 fields
                    task_type,
                    produces: task.produces.clone(),
                });

                seen_ids.insert(task.id.clone());

                // Create edges for dependencies (using effective deps)
                // RFC-067: Wire tasks get integration edge type
                let is_wire_task = task.task_type.as_deref() == Some("wire");
                for dep in &effective_deps {
                    edges.push(DagEdge {
                        id: format!("{}->{}", dep, task.id),
                        source: dep.clone(),
                        target: task.id.clone(),
                        artifact: None,
                        // RFC-067: Set edge type based on task type
                        edge_type: if is_wire_task { "integration".to_string() } else { "dependency".to_string() },
                        verification_status: if is_wire_task { Some("pending".to_string()) } else { None },
                        integration_type: if is_wire_task { Some("import".to_string()) } else { None },
                    });
                }
            }
        }
        // Legacy format: graph.artifacts with separate completed map
        else {
            for artifact in &exec.graph.artifacts {
                let is_completed = exec.completed.contains_key(&artifact.id);
                let is_failed = exec.failed.contains_key(&artifact.id);
                let is_current = exec
                    .current_artifact
                    .as_ref()
                    .map_or(false, |c| c == &artifact.id);

                let status = if is_completed {
                    completed_count += 1;
                    "complete"
                } else if is_failed {
                    "failed"
                } else if is_current {
                    "running"
                } else if is_ready(&artifact.id, &artifact.depends_on, &exec.completed) {
                    "ready"
                } else {
                    "blocked"
                };

                nodes.push(DagNode {
                    id: artifact.id.clone(),
                    title: truncate_title(&artifact.description),
                    description: artifact.description.clone(),
                    status: status.to_string(),
                    source: "ai".to_string(),
                    progress: if is_completed { 100 } else { 0 },
                    priority: artifact.priority.unwrap_or(0.5),
                    effort: "medium".to_string(),
                    depends_on: artifact.depends_on.clone(),
                    category: artifact.category.clone(),
                    current_action: None,
                    // RFC-067 fields (default for legacy format)
                    task_type: "create".to_string(),
                    produces: vec![artifact.id.clone()],
                });

                seen_ids.insert(artifact.id.clone());

                // Create edges for dependencies
                for dep in &artifact.depends_on {
                    edges.push(DagEdge {
                        id: format!("{}->{}", dep, artifact.id),
                        source: dep.clone(),
                        target: artifact.id.clone(),
                        artifact: None,
                        // RFC-067 fields (default for legacy format)
                        edge_type: "dependency".to_string(),
                        verification_status: None,
                        integration_type: None,
                    });
                }
            }
        }
    }

    // Also include goals from backlog that aren't in current execution
    for (goal_id, goal) in &backlog.goals {
        if seen_ids.contains(goal_id) {
            continue;
        }

        let is_completed = backlog.completed.contains(goal_id);
        let is_blocked = backlog.blocked.contains_key(goal_id);
        let is_in_progress = backlog.in_progress.as_ref().map_or(false, |ip| ip == goal_id);

        let status = if is_completed {
            completed_count += 1;
            "complete"
        } else if is_blocked {
            "blocked"
        } else if is_in_progress {
            "running"
        } else if is_goal_ready(goal_id, &goal.requires, &backlog.completed) {
            "ready"
        } else {
            "pending"
        };

        let source = if goal.source_signals.is_empty() {
            "human"
        } else {
            "ai"
        };

        nodes.push(DagNode {
            id: goal_id.clone(),
            title: if goal.title.is_empty() {
                truncate_title(&goal.description)
            } else {
                truncate_title(&goal.title)
            },
            description: goal.description.clone(),
            status: status.to_string(),
            source: source.to_string(),
            progress: if status == "complete" { 100 } else { 0 },
            priority: goal.priority,
            effort: if goal.estimated_complexity.is_empty() {
                "medium".to_string()
            } else {
                goal.estimated_complexity.clone()
            },
            depends_on: goal.requires.clone(),
            category: if goal.category.is_empty() {
                None
            } else {
                Some(goal.category.clone())
            },
            current_action: None,
            // RFC-067 fields (goals are typically "create" type)
            task_type: "create".to_string(),
            produces: vec![],
        });

        // Create edges for goal dependencies
        for dep in &goal.requires {
            edges.push(DagEdge {
                id: format!("{}->{}", dep, goal_id),
                source: dep.clone(),
                target: goal_id.clone(),
                artifact: None,
                // RFC-067 fields
                edge_type: "dependency".to_string(),
                verification_status: None,
                integration_type: None,
            });
        }
    }

    // Calculate total progress
    let total = nodes.len();
    let progress = if total > 0 {
        ((completed_count as f32 / total as f32) * 100.0) as u8
    } else {
        0
    };

    DagGraph {
        nodes,
        edges,
        goal: execution.map(|e| e.goal),
        total_progress: progress,
    }
}

fn is_ready(
    _id: &str,
    deps: &[String],
    completed: &HashMap<String, ArtifactCompletion>,
) -> bool {
    deps.iter().all(|d| completed.contains_key(d))
}

fn is_goal_ready(_id: &str, deps: &[String], completed: &HashSet<String>) -> bool {
    deps.iter().all(|d| completed.contains(d))
}

fn truncate_title(s: &str) -> String {
    let s = s.trim();
    if s.len() <= 40 {
        s.to_string()
    } else {
        format!("{}...", &s[..37])
    }
}

// =============================================================================
// Tests
// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[tokio::test]
    async fn test_empty_project_returns_empty_dag() {
        let tmp = TempDir::new().unwrap();
        let result = get_project_dag(tmp.path().to_string_lossy().to_string()).await;
        assert!(result.is_ok());
        let dag = result.unwrap();
        assert_eq!(dag.nodes.len(), 0);
        assert_eq!(dag.edges.len(), 0);
        assert_eq!(dag.total_progress, 0);
    }

    // ==========================================================================
    // RFC-105: Hierarchical DAG Tests
    // ==========================================================================

    #[tokio::test]
    async fn test_project_dag_index_builds_from_plans() {
        let tmp = TempDir::new().unwrap();
        let plans_dir = tmp.path().join(".sunwell/plans");
        std::fs::create_dir_all(&plans_dir).unwrap();
        std::fs::write(
            plans_dir.join("abc123.json"),
            r#"{
                "goal": "Build test app",
                "tasks": [
                    {"id": "task-1", "description": "First task", "status": "completed", "depends_on": [], "produces": ["TaskOne"], "requires": []},
                    {"id": "task-2", "description": "Second task", "status": "pending", "depends_on": ["task-1"], "produces": ["TaskTwo"], "requires": ["TaskOne"]}
                ]
            }"#,
        )
        .unwrap();

        let result = get_project_dag_index(tmp.path().to_string_lossy().to_string()).await;
        assert!(result.is_ok());
        let index = result.unwrap();
        assert_eq!(index.version, 1);
        assert_eq!(index.summary.total_goals, 1);
        assert_eq!(index.goals.len(), 1);
        assert!(index.goals[0].title.contains("Build test app"));
    }

    #[tokio::test]
    async fn test_project_dag_index_caches_to_file() {
        let tmp = TempDir::new().unwrap();
        let plans_dir = tmp.path().join(".sunwell/plans");
        std::fs::create_dir_all(&plans_dir).unwrap();
        std::fs::write(
            plans_dir.join("abc123.json"),
            r#"{
                "goal": "Cached goal test",
                "tasks": [
                    {"id": "task-1", "description": "Task", "status": "completed", "depends_on": [], "produces": [], "requires": []}
                ]
            }"#,
        )
        .unwrap();

        // First call builds and caches
        let result = get_project_dag_index(tmp.path().to_string_lossy().to_string()).await;
        assert!(result.is_ok());

        // Verify cache file was created
        let index_path = tmp.path().join(".sunwell/dag/index.json");
        assert!(index_path.exists());

        // Second call should read from cache
        let result2 = get_project_dag_index(tmp.path().to_string_lossy().to_string()).await;
        assert!(result2.is_ok());
        let index = result2.unwrap();
        assert!(index.goals[0].title.contains("Cached goal test"));
    }

    #[tokio::test]
    async fn test_append_goal_creates_files() {
        let tmp = TempDir::new().unwrap();
        
        let goal = GoalNode {
            id: "test-goal-123".to_string(),
            title: "Test Goal".to_string(),
            description: "A test goal".to_string(),
            status: "complete".to_string(),
            created_at: iso_now(),
            completed_at: Some(iso_now()),
            tasks: vec![
                TaskNode {
                    id: "task-1".to_string(),
                    description: "Task 1".to_string(),
                    status: "complete".to_string(),
                    produces: vec!["Artifact1".to_string()],
                    requires: vec![],
                    depends_on: vec![],
                    content_hash: None,
                },
                TaskNode {
                    id: "task-2".to_string(),
                    description: "Task 2".to_string(),
                    status: "complete".to_string(),
                    produces: vec!["Artifact2".to_string()],
                    requires: vec!["Artifact1".to_string()],
                    depends_on: vec!["task-1".to_string()],
                    content_hash: None,
                },
            ],
            learnings: vec!["Learned something".to_string()],
            metrics: Some(GoalMetrics {
                duration_seconds: Some(120),
                tasks_completed: 2,
                tasks_skipped: 0,
            }),
        };

        let result = append_goal_to_dag(tmp.path().to_string_lossy().to_string(), goal).await;
        assert!(result.is_ok());

        // Verify goal file was created
        let goal_path = tmp.path().join(".sunwell/dag/goals/test-goal-123.json");
        assert!(goal_path.exists());

        // Verify edges file was created
        let edges_path = tmp.path().join(".sunwell/dag/edges.jsonl");
        assert!(edges_path.exists());
        let edges_content = std::fs::read_to_string(&edges_path).unwrap();
        assert!(edges_content.contains("task-1"));
        assert!(edges_content.contains("task-2"));
        assert!(edges_content.contains("dependency"));
        assert!(edges_content.contains("produces"));

        // Verify index was updated
        let index_path = tmp.path().join(".sunwell/dag/index.json");
        assert!(index_path.exists());
        let index_content = std::fs::read_to_string(&index_path).unwrap();
        assert!(index_content.contains("Test Goal"));
    }

    #[tokio::test]
    async fn test_get_goal_details_from_goal_file() {
        let tmp = TempDir::new().unwrap();
        let goals_dir = tmp.path().join(".sunwell/dag/goals");
        std::fs::create_dir_all(&goals_dir).unwrap();
        
        let goal = GoalNode {
            id: "existing-goal".to_string(),
            title: "Existing Goal".to_string(),
            description: "An existing goal".to_string(),
            status: "complete".to_string(),
            created_at: iso_now(),
            completed_at: Some(iso_now()),
            tasks: vec![],
            learnings: vec![],
            metrics: None,
        };
        
        let goal_json = serde_json::to_string_pretty(&goal).unwrap();
        std::fs::write(goals_dir.join("existing-goal.json"), goal_json).unwrap();

        let result = get_goal_details(
            tmp.path().to_string_lossy().to_string(),
            "existing-goal".to_string()
        ).await;
        assert!(result.is_ok());
        let loaded = result.unwrap();
        assert_eq!(loaded.title, "Existing Goal");
        assert_eq!(loaded.status, "complete");
    }

    #[tokio::test]
    async fn test_workspace_index_aggregates_projects() {
        let tmp = TempDir::new().unwrap();
        
        // Create two project directories with .sunwell
        let project1 = tmp.path().join("project-alpha");
        let project2 = tmp.path().join("project-beta");
        
        std::fs::create_dir_all(project1.join(".sunwell/plans")).unwrap();
        std::fs::create_dir_all(project2.join(".sunwell/plans")).unwrap();
        
        // Add a plan to project1
        std::fs::write(
            project1.join(".sunwell/plans/plan1.json"),
            r#"{"goal": "Alpha goal", "tasks": [{"id": "t1", "description": "Task", "status": "completed", "depends_on": [], "produces": [], "requires": []}]}"#,
        ).unwrap();
        
        // Add pyproject.toml to detect Python stack
        std::fs::write(project1.join("pyproject.toml"), "[project]\nname = \"alpha\"\n").unwrap();

        let result = get_workspace_dag(tmp.path().to_string_lossy().to_string()).await;
        assert!(result.is_ok());
        let workspace = result.unwrap();
        assert_eq!(workspace.projects.len(), 2);
        
        // Verify tech stack detection
        let alpha = workspace.projects.iter().find(|p| p.name == "project-alpha");
        assert!(alpha.is_some());
        assert!(alpha.unwrap().tech_stack.contains(&"python".to_string()));
    }

    #[tokio::test]
    async fn test_backlog_creates_goal_nodes() {
        let tmp = TempDir::new().unwrap();
        let backlog_dir = tmp.path().join(".sunwell/backlog");
        std::fs::create_dir_all(&backlog_dir).unwrap();
        std::fs::write(
            backlog_dir.join("current.json"),
            r#"{
                "goals": {
                    "test-goal": {
                        "title": "Test Goal",
                        "description": "Test goal description",
                        "priority": 0.9,
                        "requires": [],
                        "category": "test"
                    }
                },
                "completed": [],
                "in_progress": null,
                "blocked": {}
            }"#,
        )
        .unwrap();

        let result = get_project_dag(tmp.path().to_string_lossy().to_string()).await;
        assert!(result.is_ok());
        let dag = result.unwrap();
        assert_eq!(dag.nodes.len(), 1);
        assert_eq!(dag.nodes[0].title, "Test Goal");
        assert_eq!(dag.nodes[0].status, "ready");
        assert_eq!(dag.nodes[0].source, "human");
    }

    #[tokio::test]
    async fn test_execution_state_marks_completed() {
        let tmp = TempDir::new().unwrap();
        let plans_dir = tmp.path().join(".sunwell/plans");
        std::fs::create_dir_all(&plans_dir).unwrap();
        std::fs::write(
            plans_dir.join("abc123.json"),
            r#"{
                "goal": "Build test app",
                "graph": {
                    "artifacts": [
                        {"id": "task-1", "description": "First task", "depends_on": []},
                        {"id": "task-2", "description": "Second task", "depends_on": ["task-1"]}
                    ]
                },
                "completed": {
                    "task-1": {"content_hash": "abc", "verified": true}
                },
                "failed": {}
            }"#,
        )
        .unwrap();

        let result = get_project_dag(tmp.path().to_string_lossy().to_string()).await;
        assert!(result.is_ok());
        let dag = result.unwrap();
        assert_eq!(dag.nodes.len(), 2);

        let task1 = dag.nodes.iter().find(|n| n.id == "task-1").unwrap();
        assert_eq!(task1.status, "complete");
        assert_eq!(task1.progress, 100);

        let task2 = dag.nodes.iter().find(|n| n.id == "task-2").unwrap();
        assert_eq!(task2.status, "ready"); // task-1 is complete, so task-2 is ready

        assert_eq!(dag.total_progress, 50); // 1 of 2 complete
    }

    #[tokio::test]
    async fn test_blocked_status() {
        let tmp = TempDir::new().unwrap();
        let plans_dir = tmp.path().join(".sunwell/plans");
        std::fs::create_dir_all(&plans_dir).unwrap();
        std::fs::write(
            plans_dir.join("abc123.json"),
            r#"{
                "goal": "Build test app",
                "graph": {
                    "artifacts": [
                        {"id": "task-1", "description": "First task", "depends_on": []},
                        {"id": "task-2", "description": "Second task", "depends_on": ["task-1"]}
                    ]
                },
                "completed": {},
                "failed": {}
            }"#,
        )
        .unwrap();

        let result = get_project_dag(tmp.path().to_string_lossy().to_string()).await;
        assert!(result.is_ok());
        let dag = result.unwrap();

        let task1 = dag.nodes.iter().find(|n| n.id == "task-1").unwrap();
        assert_eq!(task1.status, "ready"); // no deps

        let task2 = dag.nodes.iter().find(|n| n.id == "task-2").unwrap();
        assert_eq!(task2.status, "blocked"); // task-1 not complete
    }
}
