//! Writer Commands — Universal Writing Environment (RFC-086)
//!
//! Provides Tauri commands for:
//! - Diataxis detection
//! - Document validation
//! - Skill execution

use serde::{Deserialize, Serialize};
use crate::util::sunwell_command;

// =============================================================================
// TYPES
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiataxisSignal {
    pub dtype: String,
    pub weight: f64,
    pub reason: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiataxisDetection {
    #[serde(rename = "detectedType")]
    pub detected_type: Option<String>,
    pub confidence: f64,
    pub signals: Vec<DiataxisSignal>,
    pub scores: std::collections::HashMap<String, f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiataxisWarning {
    pub message: String,
    pub suggestion: Option<String>,
    pub severity: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiataxisResult {
    pub detection: DiataxisDetection,
    pub warnings: Vec<DiataxisWarning>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ValidationWarning {
    pub line: i32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub column: Option<i32>,
    pub message: String,
    pub rule: String,
    pub severity: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub suggestion: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LensSkill {
    pub id: String,
    pub name: String,
    pub shortcut: String,
    pub description: String,
    pub category: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SkillResult {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub content: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub message: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FixResult {
    pub content: String,
    pub fixed: i32,
}

// =============================================================================
// COMMANDS
// =============================================================================

/// Detect Diataxis content type from document.
#[tauri::command]
pub async fn detect_diataxis(
    content: String,
    file_path: Option<String>,
) -> Result<DiataxisResult, String> {
    // Try calling Python backend
    let file_arg = file_path.as_deref().unwrap_or("-");
    
    let output = sunwell_command()
        .args(["surface", "diataxis", "--json", "--content", &content, "--file", file_arg])
        .output()
        .map_err(|e| format!("Failed to detect diataxis: {}", e));
    
    match output {
        Ok(out) if out.status.success() => {
            let json_str = String::from_utf8_lossy(&out.stdout);
            serde_json::from_str(&json_str)
                .map_err(|e| format!("Failed to parse diataxis result: {}", e))
        }
        _ => {
            // Fallback to local detection
            Ok(detect_diataxis_local(&content, file_path.as_deref()))
        }
    }
}

/// Validate document with lens validators.
#[tauri::command]
pub async fn validate_document(
    content: String,
    file_path: Option<String>,
    lens_name: String,
) -> Result<Vec<ValidationWarning>, String> {
    let file_arg = file_path.as_deref().unwrap_or("-");
    
    let output = sunwell_command()
        .args(["lens", "validate", &lens_name, "--json", "--content", &content, "--file", file_arg])
        .output()
        .map_err(|e| format!("Failed to validate: {}", e));
    
    match output {
        Ok(out) if out.status.success() => {
            let json_str = String::from_utf8_lossy(&out.stdout);
            serde_json::from_str(&json_str)
                .map_err(|e| format!("Failed to parse validation: {}", e))
        }
        _ => {
            // Return empty for now
            Ok(vec![])
        }
    }
}

/// Get skills for a lens.
#[tauri::command]
pub async fn get_lens_skills(lens_name: String) -> Result<Vec<LensSkill>, String> {
    let output = sunwell_command()
        .args(["lens", "skills", &lens_name, "--json"])
        .output()
        .map_err(|e| format!("Failed to get skills: {}", e));
    
    match output {
        Ok(out) if out.status.success() => {
            let json_str = String::from_utf8_lossy(&out.stdout);
            serde_json::from_str(&json_str)
                .map_err(|e| format!("Failed to parse skills: {}", e))
        }
        _ => {
            // Return default skills
            Ok(default_skills())
        }
    }
}

/// Execute a lens skill.
#[tauri::command]
pub async fn execute_skill(
    skill_id: String,
    content: String,
    file_path: Option<String>,
    lens_name: String,
) -> Result<SkillResult, String> {
    let file_arg = file_path.as_deref().unwrap_or("-");
    
    let output = sunwell_command()
        .args([
            "skill", "exec", &skill_id,
            "--lens", &lens_name,
            "--json",
            "--content", &content,
            "--file", file_arg,
        ])
        .output()
        .map_err(|e| format!("Failed to execute skill: {}", e))?;
    
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }
    
    let json_str = String::from_utf8_lossy(&output.stdout);
    serde_json::from_str(&json_str)
        .map_err(|e| format!("Failed to parse skill result: {}", e))
}

/// Fix all issues in document.
#[tauri::command]
pub async fn fix_all_issues(
    content: String,
    warnings: Vec<ValidationWarning>,
    lens_name: String,
) -> Result<FixResult, String> {
    // Serialize warnings to pass to the command
    let warnings_json = serde_json::to_string(&warnings)
        .map_err(|e| format!("Failed to serialize warnings: {}", e))?;
    
    let output = sunwell_command()
        .args([
            "lens", "fix-all",
            &lens_name,
            "--json",
            "--content", &content,
            "--warnings", &warnings_json,
        ])
        .output()
        .map_err(|e| format!("Failed to fix issues: {}", e))?;
    
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }
    
    let json_str = String::from_utf8_lossy(&output.stdout);
    serde_json::from_str(&json_str)
        .map_err(|e| format!("Failed to parse fix result: {}", e))
}

// =============================================================================
// HELPERS
// =============================================================================

fn detect_diataxis_local(content: &str, file_path: Option<&str>) -> DiataxisResult {
    let content_lower = content.to_lowercase();
    let filename = file_path
        .and_then(|p| p.split('/').last())
        .unwrap_or("")
        .to_lowercase();
    
    let mut scores: std::collections::HashMap<String, f64> = std::collections::HashMap::new();
    scores.insert("TUTORIAL".to_string(), 0.0);
    scores.insert("HOW_TO".to_string(), 0.0);
    scores.insert("EXPLANATION".to_string(), 0.0);
    scores.insert("REFERENCE".to_string(), 0.0);
    
    let mut signals = Vec::new();
    
    // Tutorial signals
    for kw in ["tutorial", "getting-started", "learn", "quickstart"] {
        if filename.contains(kw) || content_lower[..content_lower.len().min(500)].contains(kw) {
            *scores.get_mut("TUTORIAL").unwrap() += 0.3;
            signals.push(DiataxisSignal {
                dtype: "TUTORIAL".to_string(),
                weight: 0.3,
                reason: format!("'{}' detected", kw),
            });
        }
    }
    
    // How-to signals
    for kw in ["how-to", "guide", "configure", "deploy"] {
        if filename.contains(kw) || content_lower[..content_lower.len().min(500)].contains(kw) {
            *scores.get_mut("HOW_TO").unwrap() += 0.3;
            signals.push(DiataxisSignal {
                dtype: "HOW_TO".to_string(),
                weight: 0.3,
                reason: format!("'{}' detected", kw),
            });
        }
    }
    
    // Explanation signals
    for kw in ["architecture", "concepts", "overview", "understand"] {
        if filename.contains(kw) || content_lower[..content_lower.len().min(500)].contains(kw) {
            *scores.get_mut("EXPLANATION").unwrap() += 0.3;
            signals.push(DiataxisSignal {
                dtype: "EXPLANATION".to_string(),
                weight: 0.3,
                reason: format!("'{}' detected", kw),
            });
        }
    }
    
    // Reference signals
    for kw in ["reference", "api", "parameters", "configuration"] {
        if filename.contains(kw) || content_lower[..content_lower.len().min(500)].contains(kw) {
            *scores.get_mut("REFERENCE").unwrap() += 0.3;
            signals.push(DiataxisSignal {
                dtype: "REFERENCE".to_string(),
                weight: 0.3,
                reason: format!("'{}' detected", kw),
            });
        }
    }
    
    // Find best type
    let total: f64 = scores.values().sum();
    let (detected_type, confidence) = if total > 0.0 {
        let best = scores.iter()
            .max_by(|a, b| a.1.partial_cmp(b.1).unwrap())
            .map(|(k, v)| (k.clone(), *v));
        
        match best {
            Some((dtype, score)) if score / total > 0.4 => (Some(dtype), score / total),
            _ => (None, 0.0),
        }
    } else {
        (None, 0.0)
    };
    
    // Check for mixed content warning
    let mut warnings = Vec::new();
    let mut sorted_scores: Vec<_> = scores.iter().collect();
    sorted_scores.sort_by(|a, b| b.1.partial_cmp(a.1).unwrap());
    
    if sorted_scores.len() >= 2 {
        let (first_type, first_score) = sorted_scores[0];
        let (second_type, second_score) = sorted_scores[1];
        
        if *first_score > 0.0 && *second_score > first_score * 0.3 {
            warnings.push(DiataxisWarning {
                message: format!("Mixed content types detected: {} + {}", first_type, second_type),
                suggestion: Some(format!("Consider splitting into separate {} and {} pages", first_type, second_type)),
                severity: "warning".to_string(),
            });
        }
    }
    
    DiataxisResult {
        detection: DiataxisDetection {
            detected_type,
            confidence,
            signals,
            scores,
        },
        warnings,
    }
}

fn default_skills() -> Vec<LensSkill> {
    vec![
        LensSkill {
            id: "audit".to_string(),
            name: "Quick Audit".to_string(),
            shortcut: "::a".to_string(),
            description: "Validate document against source code".to_string(),
            category: "validation".to_string(),
        },
        LensSkill {
            id: "polish".to_string(),
            name: "Polish".to_string(),
            shortcut: "::p".to_string(),
            description: "Improve clarity and style".to_string(),
            category: "transformation".to_string(),
        },
        LensSkill {
            id: "style-check".to_string(),
            name: "Style Check".to_string(),
            shortcut: "::s".to_string(),
            description: "Check style guide compliance".to_string(),
            category: "validation".to_string(),
        },
        LensSkill {
            id: "simplify".to_string(),
            name: "Simplify".to_string(),
            shortcut: "::sim".to_string(),
            description: "Reduce complexity and word count".to_string(),
            category: "transformation".to_string(),
        },
    ]
}
