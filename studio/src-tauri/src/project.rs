//! Project detection and management.
//!
//! Detects project type from files and structure to enable
//! adaptive UI layouts.

use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};

/// Type of project being worked on.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ProjectType {
    /// Python code project
    CodePython,
    /// JavaScript/TypeScript project
    CodeJs,
    /// Rust project
    CodeRust,
    /// Go project
    CodeGo,
    /// Web application (Flask, FastAPI, Express, etc.)
    CodeWeb,
    /// CLI tool
    CodeCli,
    /// Novel or long-form fiction
    Novel,
    /// Screenplay in Fountain format
    Screenplay,
    /// Game dialogue/narrative
    GameDialogue,
    /// General/unknown project type
    General,
}

/// A project being worked on.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Project {
    pub id: String,
    pub path: PathBuf,
    pub name: String,
    pub project_type: ProjectType,
    pub description: Option<String>,
    pub files_count: usize,
    pub last_modified: Option<u64>,
}

/// A recently opened project for the home screen.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecentProject {
    pub path: PathBuf,
    pub name: String,
    pub project_type: ProjectType,
    pub description: String,
    pub last_opened: u64,
}

/// Detects project type from files and structure.
pub struct ProjectDetector {
    // Could hold configuration or caches
}

impl ProjectDetector {
    pub fn new() -> Self {
        Self {}
    }

    /// Detect project type and create Project struct.
    pub fn detect(&self, path: &Path) -> Result<Project, String> {
        if !path.exists() {
            return Err(format!("Path does not exist: {}", path.display()));
        }

        let name = path
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("Untitled")
            .to_string();

        let project_type = self.detect_type(path);
        let files_count = self.count_files(path);

        // Generate stable ID from path
        let id = generate_project_id(path);

        Ok(Project {
            id,
            path: path.to_path_buf(),
            name,
            project_type,
            description: None,
            files_count,
            last_modified: None,
        })
    }

    /// Detect project type from files.
    fn detect_type(&self, path: &Path) -> ProjectType {
        // Check for specific file markers
        if path.join("pyproject.toml").exists() || path.join("setup.py").exists() {
            return self.detect_python_type(path);
        }

        if path.join("package.json").exists() {
            return self.detect_js_type(path);
        }

        if path.join("Cargo.toml").exists() {
            return ProjectType::CodeRust;
        }

        if path.join("go.mod").exists() {
            return ProjectType::CodeGo;
        }

        // Check for creative writing projects
        if self.has_extension(path, "fountain") {
            return ProjectType::Screenplay;
        }

        if self.has_extension(path, "md") && self.looks_like_novel(path) {
            return ProjectType::Novel;
        }

        // Check for dialogue files (yarn, ink, etc.)
        if self.has_extension(path, "yarn") || self.has_extension(path, "ink") {
            return ProjectType::GameDialogue;
        }

        ProjectType::General
    }

    /// Detect Python project subtype.
    fn detect_python_type(&self, path: &Path) -> ProjectType {
        // Check for web frameworks
        let app_patterns = ["app.py", "main.py", "wsgi.py", "asgi.py"];
        for pattern in &app_patterns {
            let file = path.join(pattern);
            if file.exists() {
                if let Ok(content) = std::fs::read_to_string(&file) {
                    if content.contains("Flask")
                        || content.contains("FastAPI")
                        || content.contains("Django")
                    {
                        return ProjectType::CodeWeb;
                    }
                }
            }
        }

        // Check for CLI indicators
        if path.join("cli.py").exists() || path.join("__main__.py").exists() {
            return ProjectType::CodeCli;
        }

        ProjectType::CodePython
    }

    /// Detect JavaScript/TypeScript project subtype.
    fn detect_js_type(&self, path: &Path) -> ProjectType {
        let package_json = path.join("package.json");
        if let Ok(content) = std::fs::read_to_string(&package_json) {
            if content.contains("express")
                || content.contains("fastify")
                || content.contains("next")
                || content.contains("nuxt")
            {
                return ProjectType::CodeWeb;
            }
        }

        ProjectType::CodeJs
    }

    /// Check if directory has files with given extension.
    fn has_extension(&self, path: &Path, ext: &str) -> bool {
        if let Ok(entries) = std::fs::read_dir(path) {
            for entry in entries.flatten() {
                if let Some(entry_ext) = entry.path().extension() {
                    if entry_ext == ext {
                        return true;
                    }
                }
            }
        }
        false
    }

    /// Check if markdown files look like a novel structure.
    fn looks_like_novel(&self, path: &Path) -> bool {
        let chapter_patterns = ["chapter", "ch_", "ch-"];

        if let Ok(entries) = std::fs::read_dir(path) {
            let md_files: Vec<_> = entries
                .flatten()
                .filter(|e| {
                    e.path()
                        .extension()
                        .map(|ext| ext == "md")
                        .unwrap_or(false)
                })
                .collect();

            // If we have multiple markdown files with chapter-like names
            let chapter_count = md_files
                .iter()
                .filter(|e| {
                    let name = e.file_name().to_string_lossy().to_lowercase();
                    chapter_patterns.iter().any(|p| name.contains(p))
                })
                .count();

            return chapter_count >= 2;
        }

        false
    }

    /// Count files in directory (shallow).
    fn count_files(&self, path: &Path) -> usize {
        std::fs::read_dir(path)
            .map(|entries| entries.count())
            .unwrap_or(0)
    }
}

impl Default for ProjectDetector {
    fn default() -> Self {
        Self::new()
    }
}

/// Generate a stable project ID from the path.
/// Uses a hash of the absolute path for consistency.
fn generate_project_id(path: &Path) -> String {
    let canonical = path.canonicalize().unwrap_or_else(|_| path.to_path_buf());
    let path_str = canonical.to_string_lossy();
    
    let mut hasher = DefaultHasher::new();
    path_str.hash(&mut hasher);
    let hash = hasher.finish();
    
    // Use first 12 characters of hex hash for readability
    format!("{:012x}", hash)
}
