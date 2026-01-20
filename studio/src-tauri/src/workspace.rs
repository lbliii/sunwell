//! Workspace resolution with sensible defaults (RFC-043 addendum).
//!
//! Provides unified workspace resolution logic for the Desktop app:
//! - Sensible defaults (~/.sunwell/projects/)
//! - Explicit path override
//! - Detection from cwd
//! - Project name derivation from goals

use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

/// How the workspace was resolved.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ResolutionSource {
    /// User provided explicit path
    Explicit,
    /// Found project markers in directory
    Detected,
    /// Using default ~/Sunwell/projects/
    Default,
}

/// Result of workspace resolution.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkspaceResult {
    /// Resolved workspace path
    pub path: PathBuf,
    /// How the workspace was found
    pub source: ResolutionSource,
    /// Confidence in the resolution (0.0-1.0)
    pub confidence: f64,
    /// Derived project name (for new projects)
    pub project_name: Option<String>,
    /// Whether the path already exists
    pub exists: bool,
}

impl WorkspaceResult {
    /// Whether this resolution should be confirmed with user.
    pub fn needs_confirmation(&self) -> bool {
        self.confidence < 0.9
    }
}

/// Project markers that indicate a valid project root.
const PROJECT_MARKERS: &[&str] = &[
    ".sunwell",       // Explicit Sunwell project
    "pyproject.toml", // Python
    "package.json",   // Node
    "Cargo.toml",     // Rust
    "go.mod",         // Go
    ".git",           // Git repository
    "setup.py",       // Legacy Python
    "Makefile",       // C/C++ or general
];

/// Get platform-appropriate default workspace root.
///
/// Returns ~/Sunwell/projects/ on all platforms
pub fn default_workspace_root() -> PathBuf {
    dirs::home_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("Sunwell")
        .join("projects")
}

/// Get platform-appropriate config root.
///
/// Returns ~/Sunwell/.sunwell/ for global config
pub fn default_config_root() -> PathBuf {
    dirs::home_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("Sunwell")
        .join(".sunwell")
}

/// Get path for recent projects file.
pub fn recent_projects_path() -> PathBuf {
    default_config_root().join("recent.json")
}

/// Walk up from start looking for project markers.
fn find_project_root(start: &Path) -> Option<PathBuf> {
    let mut current = start.to_path_buf();

    // Don't walk above home directory
    let home = dirs::home_dir();

    loop {
        // Stop at home directory
        if let Some(ref h) = home {
            if &current == h {
                break;
            }
        }

        // Skip Sunwell Studio's own directories to prevent creating projects inside the app
        let dir_name = current.file_name().and_then(|n| n.to_str()).unwrap_or("");
        if dir_name == "src-tauri" || dir_name == "studio" || dir_name == "sunwell" {
            if !current.pop() {
                break;
            }
            continue;
        }

        // Check for project markers
        for marker in PROJECT_MARKERS {
            if current.join(marker).exists() {
                return Some(current);
            }
        }

        // Move up
        if !current.pop() {
            break;
        }
    }

    None
}

/// Check if path looks like a random/temporary location.
fn is_random_location(path: &Path) -> bool {
    let path_str = path.to_string_lossy().to_lowercase();

    let random_indicators = ["/tmp", "/var/tmp", "/temp", "downloads", "/private/tmp"];

    random_indicators.iter().any(|ind| path_str.contains(ind))
}

/// Resolve workspace with full context about how it was found.
///
/// Resolution precedence:
/// 1. Explicit path (if provided)
/// 2. Current directory if it has project markers
/// 3. Walk up to find nearest project root
/// 4. Default ~/Sunwell/projects/
pub fn resolve_workspace(explicit: Option<&Path>, project_name: Option<&str>) -> WorkspaceResult {
    // 1. Explicit always wins
    if let Some(path) = explicit {
        return WorkspaceResult {
            path: path.to_path_buf(),
            source: ResolutionSource::Explicit,
            confidence: 1.0,
            project_name: project_name.map(String::from),
            exists: path.exists(),
        };
    }

    // 2. Detect from cwd or walk up
    let start = std::env::current_dir().unwrap_or_default();

    if let Some(found) = find_project_root(&start) {
        return WorkspaceResult {
            path: found,
            source: ResolutionSource::Detected,
            confidence: 0.95,
            project_name: None,
            exists: true,
        };
    }

    // 3. Check if cwd looks random/temporary
    let mut default_path = default_workspace_root();
    if let Some(name) = project_name {
        default_path = default_path.join(slugify(name));
    }

    let confidence = if is_random_location(&start) {
        0.3 // Very low - definitely confirm
    } else {
        0.5 // Low - should confirm
    };

    WorkspaceResult {
        path: default_path.clone(),
        source: ResolutionSource::Default,
        confidence,
        project_name: project_name.map(String::from),
        exists: default_path.exists(),
    }
}

/// Convert project name to directory-safe slug.
///
/// Examples:
///     "Forum App" → "forum-app"
///     "My REST API" → "my-rest-api"
pub fn slugify(name: &str) -> String {
    let mut slug: String = name
        .to_lowercase()
        .chars()
        .map(|c| {
            if c.is_alphanumeric() {
                c
            } else if c.is_whitespace() || c == '_' {
                '-'
            } else {
                ' ' // Will be filtered out
            }
        })
        .filter(|c| *c != ' ')
        .collect();

    // Collapse multiple hyphens
    while slug.contains("--") {
        slug = slug.replace("--", "-");
    }

    // Strip leading/trailing hyphens
    slug.trim_matches('-').to_string()
}

/// Ensure the workspace directory exists.
pub fn ensure_workspace_exists(path: &Path) -> std::io::Result<()> {
    std::fs::create_dir_all(path)?;

    // Create .sunwell subdirectory for project config
    let sunwell_dir = path.join(".sunwell");
    std::fs::create_dir_all(sunwell_dir)?;

    Ok(())
}

/// Format a path for display by replacing home with ~.
pub fn shorten_path(path: &Path) -> String {
    let path_str = path.to_string_lossy();

    if let Some(home) = dirs::home_dir() {
        let home_str = home.to_string_lossy();
        if path_str.starts_with(home_str.as_ref()) {
            return format!("~{}", &path_str[home_str.len()..]);
        }
    }

    path_str.to_string()
}

// =============================================================================
// Recent Projects Persistence
// =============================================================================

use crate::project::{ProjectType, RecentProject};

/// Maximum number of recent projects to store.
const MAX_RECENT_PROJECTS: usize = 20;

/// Recent projects storage.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct RecentProjectsStore {
    pub projects: Vec<RecentProject>,
}

impl RecentProjectsStore {
    /// Load recent projects from disk.
    pub fn load() -> Self {
        let path = recent_projects_path();

        if !path.exists() {
            return Self::default();
        }

        match std::fs::read_to_string(&path) {
            Ok(content) => serde_json::from_str(&content).unwrap_or_default(),
            Err(_) => Self::default(),
        }
    }

    /// Save recent projects to disk.
    pub fn save(&self) -> std::io::Result<()> {
        let path = recent_projects_path();

        // Ensure parent directory exists
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }

        let content = serde_json::to_string_pretty(self)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;

        std::fs::write(path, content)
    }

    /// Add or update a project in recent list.
    pub fn add(&mut self, project: RecentProject) {
        // Remove existing entry with same path
        self.projects
            .retain(|p| p.path != project.path);

        // Add to front
        self.projects.insert(0, project);

        // Trim to max size
        self.projects.truncate(MAX_RECENT_PROJECTS);
    }

    /// Get all recent projects.
    pub fn get_all(&self) -> &[RecentProject] {
        &self.projects
    }

    /// Remove a project from recent list.
    pub fn remove(&mut self, path: &Path) {
        self.projects.retain(|p| p.path != path);
    }
}

/// Create a RecentProject from a path and detected info.
pub fn create_recent_project(
    path: &Path,
    name: &str,
    project_type: ProjectType,
    description: Option<&str>,
) -> RecentProject {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);

    RecentProject {
        path: path.to_path_buf(),
        name: name.to_string(),
        project_type,
        description: description.unwrap_or("").to_string(),
        last_opened: now,
    }
}

// =============================================================================
// Project Name Extraction
// =============================================================================

/// Extract a project name hint from a goal.
///
/// Simple heuristic extraction - looks for common patterns like
/// "build a X app" or "create X".
pub fn extract_project_name(goal: &str) -> Option<String> {
    let goal_lower = goal.to_lowercase();

    // Pattern: "build/create/make a X app/api/tool/site"
    let patterns = [
        // Pattern with suffix
        (
            &["build", "create", "make", "write"][..],
            &["app", "api", "tool", "site", "website", "service"][..],
        ),
    ];

    for (verbs, suffixes) in &patterns {
        for verb in *verbs {
            if let Some(start) = goal_lower.find(verb) {
                let after_verb = &goal_lower[start + verb.len()..];

                // Skip "a " or "an " if present
                let after_article = after_verb
                    .trim_start()
                    .strip_prefix("a ")
                    .or_else(|| after_verb.trim_start().strip_prefix("an "))
                    .unwrap_or(after_verb.trim_start());

                // Look for suffix
                for suffix in *suffixes {
                    if let Some(end) = after_article.find(suffix) {
                        let name = after_article[..end].trim();
                        if name.len() > 2
                            && !["a", "an", "the", "new", "simple"].contains(&name)
                        {
                            return Some(name.to_string());
                        }
                    }
                }

                // No suffix found, try to extract until "with" or end
                let name = after_article
                    .split(" with ")
                    .next()
                    .and_then(|s| s.split(" using ").next())
                    .map(|s| s.trim())
                    .filter(|s| s.len() > 2 && s.len() < 50)
                    .map(String::from);

                if name.is_some() {
                    return name;
                }
            }
        }
    }

    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_slugify() {
        assert_eq!(slugify("Forum App"), "forum-app");
        assert_eq!(slugify("My REST API"), "my-rest-api");
        assert_eq!(slugify("The Lighthouse Keeper"), "the-lighthouse-keeper");
        assert_eq!(slugify("test__name"), "test-name");
        assert_eq!(slugify("  spaces  "), "spaces");
    }

    #[test]
    fn test_default_workspace_root() {
        let root = default_workspace_root();
        assert!(root.ends_with("Sunwell/projects"));
    }
}
