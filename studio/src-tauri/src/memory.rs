//! Memory Commands — Surface memory/simulacrum state to Studio (RFC-013, RFC-014, RFC-084)
//!
//! Provides commands to:
//! - Get memory statistics for a project
//! - List conversation sessions
//! - View intelligence (decisions, failures)
//! - RFC-084: Get ConceptGraph and ChunkHierarchy for visualization

use serde::{Deserialize, Serialize};
use std::path::PathBuf;

// =============================================================================
// Public Types
// =============================================================================

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MemoryStats {
    pub session_id: Option<String>,
    pub hot_turns: u32,
    pub warm_files: u32,
    pub warm_size_mb: f32,
    pub cold_files: u32,
    pub cold_size_mb: f32,
    pub total_turns: u32,
    pub branches: u32,
    pub dead_ends: u32,
    pub learnings: u32,
    // RFC-084: Concept graph stats
    pub concept_edges: u32,
}

// =============================================================================
// RFC-084: ConceptGraph Types
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RelationType {
    Elaborates,
    Summarizes,
    Exemplifies,
    Contradicts,
    Supports,
    Qualifies,
    DependsOn,
    Supersedes,
    RelatesTo,
    Follows,
    Updates,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ConceptEdge {
    pub source_id: String,
    pub target_id: String,
    pub relation: RelationType,
    pub confidence: f32,
    pub evidence: Option<String>,
    pub auto_extracted: bool,
    pub timestamp: Option<String>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ConceptGraph {
    pub edges: Vec<ConceptEdge>,
}

// =============================================================================
// RFC-084: Chunk Types
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ChunkType {
    Micro,
    Mini,
    Macro,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Chunk {
    pub id: String,
    pub chunk_type: ChunkType,
    pub turn_range: (u32, u32),
    pub summary: Option<String>,
    pub themes: Vec<String>,
    pub key_facts: Vec<String>,
    pub token_count: u32,
    pub timestamp_start: Option<String>,
    pub timestamp_end: Option<String>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ChunkHierarchy {
    pub hot: Vec<Chunk>,
    pub warm: Vec<Chunk>,
    pub cold: Vec<Chunk>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Session {
    pub id: String,
    pub name: Option<String>,
    pub turns: u32,
    pub created: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Learning {
    pub id: String,
    pub fact: String,
    pub category: String,
    pub confidence: f32,
    pub source_file: Option<String>,
    pub created_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DeadEnd {
    pub approach: String,
    pub reason: String,
    pub context: Option<String>,
    pub created_at: Option<String>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct IntelligenceData {
    pub decisions: Vec<Decision>,
    pub failures: Vec<FailedApproach>,
    pub learnings: Vec<Learning>,
    pub dead_ends: Vec<DeadEnd>,
    pub total_decisions: u32,
    pub total_failures: u32,
    pub total_learnings: u32,
    pub total_dead_ends: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Decision {
    pub id: String,
    pub decision: String,
    pub rationale: String,
    pub created_at: Option<String>,
    pub scope: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FailedApproach {
    pub id: String,
    pub approach: String,
    pub reason: String,
    pub created_at: Option<String>,
    pub context: Option<String>,
}

// =============================================================================
// Tauri Commands
// =============================================================================

/// Get memory statistics for a project
#[tauri::command]
pub async fn get_memory_stats(path: String) -> Result<MemoryStats, String> {
    let project_path = PathBuf::from(&path);
    let memory_path = project_path.join(".sunwell/memory");

    if !memory_path.exists() {
        return Ok(MemoryStats::default());
    }

    // Read directly from the filesystem (sunwell sessions stats outputs Rich tables, not JSON)
    let mut stats = MemoryStats::default();

    // Count files in memory directories
    if let Ok(entries) = std::fs::read_dir(&memory_path) {
        for entry in entries.filter_map(|e| e.ok()) {
            let path = entry.path();
            if path.is_file() && path.extension().map_or(false, |e| e == "json") {
                if path.to_string_lossy().contains("hot") || path.to_string_lossy().contains("current") {
                    stats.hot_turns += 1;
                } else if path.to_string_lossy().contains("cold") || path.to_string_lossy().contains("archive") {
                    stats.cold_files += 1;
                } else {
                    stats.warm_files += 1;
                }
            }
        }
    }

    // Try to get total turns from session DAG
    let dag_path = memory_path.join("dag.json");
    if dag_path.exists() {
        if let Ok(content) = std::fs::read_to_string(&dag_path) {
            if let Ok(json) = serde_json::from_str::<serde_json::Value>(&content) {
                if let Some(turns) = json.get("turn_count").and_then(|v| v.as_u64()) {
                    stats.total_turns = turns as u32;
                }
                if let Some(branches) = json.get("branch_count").and_then(|v| v.as_u64()) {
                    stats.branches = branches as u32;
                }
                if let Some(dead_ends) = json.get("dead_end_count").and_then(|v| v.as_u64()) {
                    stats.dead_ends = dead_ends as u32;
                }
            }
        }
    }

    // Count learnings from intelligence
    let decisions_path = project_path.join(".sunwell/intelligence/decisions.jsonl");
    if decisions_path.exists() {
        if let Ok(content) = std::fs::read_to_string(&decisions_path) {
            stats.learnings = content.lines().filter(|l| !l.is_empty()).count() as u32;
        }
    }

    // RFC-084: Count concept graph edges
    let unified_graph_path = project_path.join(".sunwell/memory/unified/graph.json");
    let graph_path = if unified_graph_path.exists() {
        unified_graph_path
    } else {
        project_path.join(".sunwell/memory/graph.json")
    };
    
    if graph_path.exists() {
        if let Ok(content) = std::fs::read_to_string(&graph_path) {
            if let Ok(json) = serde_json::from_str::<serde_json::Value>(&content) {
                if let Some(edges) = json.get("edges").and_then(|e| e.as_array()) {
                    stats.concept_edges = edges.len() as u32;
                }
            }
        }
    }

    Ok(stats)
}

/// List conversation sessions for a project
#[tauri::command]
pub async fn list_sessions(path: String) -> Result<Vec<Session>, String> {
    let project_path = PathBuf::from(&path);
    let memory_path = project_path.join(".sunwell/memory");

    if !memory_path.exists() {
        return Ok(Vec::new());
    }

    let mut sessions = Vec::new();

    // Look for session directories
    if let Ok(entries) = std::fs::read_dir(&memory_path) {
        for entry in entries.filter_map(|e| e.ok()) {
            let path = entry.path();
            if path.is_dir() {
                let session_id = path.file_name()
                    .and_then(|n| n.to_str())
                    .unwrap_or("unknown")
                    .to_string();

                // Try to read session metadata
                let meta_path = path.join("metadata.json");
                let (name, turns, created) = if meta_path.exists() {
                    if let Ok(content) = std::fs::read_to_string(&meta_path) {
                        if let Ok(json) = serde_json::from_str::<serde_json::Value>(&content) {
                            (
                                json.get("name").and_then(|v| v.as_str()).map(String::from),
                                json.get("turn_count").and_then(|v| v.as_u64()).unwrap_or(0) as u32,
                                json.get("created_at").and_then(|v| v.as_str()).map(String::from),
                            )
                        } else {
                            (None, 0, None)
                        }
                    } else {
                        (None, 0, None)
                    }
                } else {
                    // Count .json files as turn estimate
                    let turns = std::fs::read_dir(&path)
                        .map(|entries| entries.filter_map(|e| e.ok())
                            .filter(|e| e.path().extension().map_or(false, |ext| ext == "json"))
                            .count())
                        .unwrap_or(0) as u32;
                    (None, turns, None)
                };

                sessions.push(Session {
                    id: session_id,
                    name,
                    turns,
                    created,
                });
            }
        }
    }

    Ok(sessions)
}

// =============================================================================
// RFC-084: ConceptGraph and ChunkHierarchy Commands
// =============================================================================

/// Get ConceptGraph for visualization (RFC-084)
#[tauri::command]
pub async fn get_concept_graph(path: String) -> Result<ConceptGraph, String> {
    let project_path = PathBuf::from(&path);
    
    // Try unified store first (RFC-014 format)
    let unified_graph_path = project_path.join(".sunwell/memory/unified/graph.json");
    if unified_graph_path.exists() {
        if let Ok(content) = std::fs::read_to_string(&unified_graph_path) {
            if let Ok(graph) = serde_json::from_str::<ConceptGraph>(&content) {
                return Ok(graph);
            }
        }
    }
    
    // Try legacy format
    let graph_path = project_path.join(".sunwell/memory/graph.json");
    if graph_path.exists() {
        if let Ok(content) = std::fs::read_to_string(&graph_path) {
            if let Ok(graph) = serde_json::from_str::<ConceptGraph>(&content) {
                return Ok(graph);
            }
            // Try parsing as nested structure
            if let Ok(json) = serde_json::from_str::<serde_json::Value>(&content) {
                if let Some(edges_arr) = json.get("edges").and_then(|e| e.as_array()) {
                    let edges: Vec<ConceptEdge> = edges_arr
                        .iter()
                        .filter_map(|v| serde_json::from_value(v.clone()).ok())
                        .collect();
                    return Ok(ConceptGraph { edges });
                }
            }
        }
    }
    
    // No graph found - return empty
    Ok(ConceptGraph::default())
}

/// Get ChunkHierarchy for visualization (RFC-084)
#[tauri::command]
pub async fn get_chunk_hierarchy(path: String) -> Result<ChunkHierarchy, String> {
    let project_path = PathBuf::from(&path);
    let chunks_path = project_path.join(".sunwell/memory/chunks");
    
    let mut hierarchy = ChunkHierarchy::default();
    
    // Read each tier
    for tier in ["hot", "warm", "cold"] {
        let tier_path = chunks_path.join(tier);
        if tier_path.exists() {
            if let Ok(entries) = std::fs::read_dir(&tier_path) {
                for entry in entries.filter_map(|e| e.ok()) {
                    let path = entry.path();
                    if path.extension().map_or(false, |e| e == "json") {
                        if let Ok(content) = std::fs::read_to_string(&path) {
                            if let Ok(json) = serde_json::from_str::<serde_json::Value>(&content) {
                                // Parse chunk from JSON
                                let chunk = Chunk {
                                    id: json.get("id")
                                        .and_then(|v| v.as_str())
                                        .unwrap_or("")
                                        .to_string(),
                                    chunk_type: match json.get("chunk_type")
                                        .and_then(|v| v.as_str())
                                        .unwrap_or("micro") 
                                    {
                                        "mini" => ChunkType::Mini,
                                        "macro" => ChunkType::Macro,
                                        _ => ChunkType::Micro,
                                    },
                                    turn_range: {
                                        let range = json.get("turn_range")
                                            .and_then(|v| v.as_array());
                                        if let Some(arr) = range {
                                            let start = arr.get(0)
                                                .and_then(|v| v.as_u64())
                                                .unwrap_or(0) as u32;
                                            let end = arr.get(1)
                                                .and_then(|v| v.as_u64())
                                                .unwrap_or(0) as u32;
                                            (start, end)
                                        } else {
                                            (0, 0)
                                        }
                                    },
                                    summary: json.get("summary")
                                        .and_then(|v| v.as_str())
                                        .map(String::from),
                                    themes: json.get("themes")
                                        .and_then(|v| v.as_array())
                                        .map(|arr| arr.iter()
                                            .filter_map(|v| v.as_str().map(String::from))
                                            .collect())
                                        .unwrap_or_default(),
                                    key_facts: json.get("key_facts")
                                        .and_then(|v| v.as_array())
                                        .map(|arr| arr.iter()
                                            .filter_map(|v| v.as_str().map(String::from))
                                            .collect())
                                        .unwrap_or_default(),
                                    token_count: json.get("token_count")
                                        .and_then(|v| v.as_u64())
                                        .unwrap_or(0) as u32,
                                    timestamp_start: json.get("timestamp_start")
                                        .and_then(|v| v.as_str())
                                        .map(String::from),
                                    timestamp_end: json.get("timestamp_end")
                                        .and_then(|v| v.as_str())
                                        .map(String::from),
                                };
                                
                                match tier {
                                    "hot" => hierarchy.hot.push(chunk),
                                    "warm" => hierarchy.warm.push(chunk),
                                    "cold" => hierarchy.cold.push(chunk),
                                    _ => {}
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    
    // Sort by turn range for consistent ordering
    hierarchy.hot.sort_by_key(|c| c.turn_range.0);
    hierarchy.warm.sort_by_key(|c| c.turn_range.0);
    hierarchy.cold.sort_by_key(|c| c.turn_range.0);
    
    Ok(hierarchy)
}

/// Get intelligence data (decisions and failures)
#[tauri::command]
pub async fn get_intelligence(path: String) -> Result<IntelligenceData, String> {
    let project_path = PathBuf::from(&path);
    let intel_path = project_path.join(".sunwell/intelligence");

    let mut data = IntelligenceData::default();

    // Read decisions
    let decisions_path = intel_path.join("decisions.jsonl");
    if decisions_path.exists() {
        if let Ok(content) = std::fs::read_to_string(&decisions_path) {
            for line in content.lines() {
                if line.is_empty() {
                    continue;
                }
                if let Ok(json) = serde_json::from_str::<serde_json::Value>(line) {
                    data.decisions.push(Decision {
                        id: json.get("id").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        decision: json.get("decision").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        rationale: json.get("rationale").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        created_at: json.get("created_at").and_then(|v| v.as_str()).map(String::from),
                        scope: json.get("scope").and_then(|v| v.as_str()).map(String::from),
                    });
                }
            }
            data.total_decisions = data.decisions.len() as u32;
        }
    }

    // Read failures
    let failures_path = intel_path.join("failures.jsonl");
    if failures_path.exists() {
        if let Ok(content) = std::fs::read_to_string(&failures_path) {
            for line in content.lines() {
                if line.is_empty() {
                    continue;
                }
                if let Ok(json) = serde_json::from_str::<serde_json::Value>(line) {
                    data.failures.push(FailedApproach {
                        id: json.get("id").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        approach: json.get("approach").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        reason: json.get("reason").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        created_at: json.get("created_at").and_then(|v| v.as_str()).map(String::from),
                        context: json.get("context").and_then(|v| v.as_str()).map(String::from),
                    });
                }
            }
            data.total_failures = data.failures.len() as u32;
        }
    }

    // Read learnings (from agent runs)
    // Source 1: .sunwell/intelligence/learnings.jsonl (JSONL format)
    let learnings_path = intel_path.join("learnings.jsonl");
    if learnings_path.exists() {
        if let Ok(content) = std::fs::read_to_string(&learnings_path) {
            for line in content.lines() {
                if line.is_empty() {
                    continue;
                }
                if let Ok(json) = serde_json::from_str::<serde_json::Value>(line) {
                    data.learnings.push(Learning {
                        id: json.get("id").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        fact: json.get("fact").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        category: json.get("category").and_then(|v| v.as_str()).unwrap_or("pattern").to_string(),
                        confidence: json.get("confidence").and_then(|v| v.as_f64()).unwrap_or(0.7) as f32,
                        source_file: json.get("source_file").and_then(|v| v.as_str()).map(String::from),
                        created_at: json.get("created_at").and_then(|v| v.as_str()).map(String::from),
                    });
                }
            }
        }
    }

    // Source 2: .sunwell/learnings/*.json (JSON array format from Naaru)
    let naaru_learnings_dir = project_path.join(".sunwell/learnings");
    if naaru_learnings_dir.exists() {
        if let Ok(entries) = std::fs::read_dir(&naaru_learnings_dir) {
            for entry in entries.filter_map(|e| e.ok()) {
                let path = entry.path();
                if path.extension().map_or(false, |ext| ext == "json") {
                    if let Ok(content) = std::fs::read_to_string(&path) {
                        // Parse as JSON array of learning records
                        if let Ok(json_array) = serde_json::from_str::<serde_json::Value>(&content) {
                            if let Some(arr) = json_array.as_array() {
                                for json in arr {
                                    // Naaru format: type, goal, task_id, task_description, output, timestamp
                                    let task_id = json.get("task_id").and_then(|v| v.as_str()).unwrap_or("");
                                    let description = json.get("task_description").and_then(|v| v.as_str()).unwrap_or("");
                                    let output = json.get("output").and_then(|v| v.as_str()).unwrap_or("");
                                    let timestamp = json.get("timestamp").and_then(|v| v.as_str());

                                    // Convert Naaru learning format to our Learning struct
                                    if !task_id.is_empty() {
                                        data.learnings.push(Learning {
                                            id: task_id.to_string(),
                                            fact: format!("Completed: {}", description),
                                            category: "task_completion".to_string(),
                                            confidence: 1.0,
                                            source_file: Some(task_id.to_string()),
                                            created_at: timestamp.map(String::from),
                                        });
                                    }
                                    
                                    // If output contains useful info, create a learning from it
                                    if output.len() > 20 && output.len() < 200 {
                                        data.learnings.push(Learning {
                                            id: format!("{}-output", task_id),
                                            fact: output.chars().take(150).collect::<String>(),
                                            category: "code".to_string(),
                                            confidence: 0.8,
                                            source_file: Some(task_id.to_string()),
                                            created_at: timestamp.map(String::from),
                                        });
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    data.total_learnings = data.learnings.len() as u32;

    // Read dead ends (approaches that didn't work)
    let dead_ends_path = intel_path.join("dead_ends.jsonl");
    if dead_ends_path.exists() {
        if let Ok(content) = std::fs::read_to_string(&dead_ends_path) {
            for line in content.lines() {
                if line.is_empty() {
                    continue;
                }
                if let Ok(json) = serde_json::from_str::<serde_json::Value>(line) {
                    data.dead_ends.push(DeadEnd {
                        approach: json.get("approach").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        reason: json.get("reason").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        context: json.get("context").and_then(|v| v.as_str()).map(String::from),
                        created_at: json.get("created_at").and_then(|v| v.as_str()).map(String::from),
                    });
                }
            }
            data.total_dead_ends = data.dead_ends.len() as u32;
        }
    }

    Ok(data)
}

// =============================================================================
// Tests
// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[tokio::test]
    async fn test_empty_project_returns_empty_stats() {
        let tmp = TempDir::new().unwrap();
        let result = get_memory_stats(tmp.path().to_string_lossy().to_string()).await;
        assert!(result.is_ok());
        let stats = result.unwrap();
        assert_eq!(stats.hot_turns, 0);
        assert_eq!(stats.total_turns, 0);
    }

    #[tokio::test]
    async fn test_empty_project_returns_no_sessions() {
        let tmp = TempDir::new().unwrap();
        let result = list_sessions(tmp.path().to_string_lossy().to_string()).await;
        assert!(result.is_ok());
        assert_eq!(result.unwrap().len(), 0);
    }

    #[tokio::test]
    async fn test_empty_project_returns_empty_intelligence() {
        let tmp = TempDir::new().unwrap();
        let result = get_intelligence(tmp.path().to_string_lossy().to_string()).await;
        assert!(result.is_ok());
        let data = result.unwrap();
        assert_eq!(data.total_decisions, 0);
        assert_eq!(data.total_failures, 0);
    }

    #[tokio::test]
    async fn test_reads_decisions() {
        let tmp = TempDir::new().unwrap();
        let intel_dir = tmp.path().join(".sunwell/intelligence");
        std::fs::create_dir_all(&intel_dir).unwrap();
        std::fs::write(
            intel_dir.join("decisions.jsonl"),
            r#"{"id": "d1", "decision": "Use async/await", "rationale": "Better for I/O bound work"}
{"id": "d2", "decision": "Add caching", "rationale": "Improve performance"}"#,
        ).unwrap();

        let result = get_intelligence(tmp.path().to_string_lossy().to_string()).await;
        assert!(result.is_ok());
        let data = result.unwrap();
        assert_eq!(data.total_decisions, 2);
        assert_eq!(data.decisions[0].decision, "Use async/await");
    }

    #[tokio::test]
    async fn test_reads_failures() {
        let tmp = TempDir::new().unwrap();
        let intel_dir = tmp.path().join(".sunwell/intelligence");
        std::fs::create_dir_all(&intel_dir).unwrap();
        std::fs::write(
            intel_dir.join("failures.jsonl"),
            r#"{"id": "f1", "approach": "Sync implementation", "reason": "Too slow"}"#,
        ).unwrap();

        let result = get_intelligence(tmp.path().to_string_lossy().to_string()).await;
        assert!(result.is_ok());
        let data = result.unwrap();
        assert_eq!(data.total_failures, 1);
        assert_eq!(data.failures[0].approach, "Sync implementation");
    }
}
