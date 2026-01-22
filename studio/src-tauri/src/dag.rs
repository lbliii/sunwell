//! DAG Commands — Read backlog and execution state for Pipeline view (RFC-056)
//!
//! Provides commands to:
//! - Load the full DAG from `.sunwell/backlog/` and `.sunwell/plans/`
//! - Execute a specific node from the DAG

use crate::util::sunwell_command;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};

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
        let mut agent = state.agent.lock().map_err(|e| e.to_string())?;
        agent.run_backlog_goal(app, &node_id, &project_path)?;
        
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

        // DAG nodes use auto-lens detection (no explicit lens)
        crate::commands::run_goal(app, state, node.description.clone(), Some(path), None, None).await
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
    serde_json::from_str(&stdout)
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
    serde_json::from_str(&stdout)
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
    serde_json::from_str(&stdout)
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
        Ok(content) => serde_json::from_str(&content).unwrap_or_default(),
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
                return serde_json::from_str(&content).ok();
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
