//! Heuristic-based project run detection (RFC-066).
//!
//! This module provides fast, deterministic run detection without AI.
//! Used as a fallback when AI is unavailable or times out.

use std::fs;
use std::path::Path;

use crate::run_analysis::{Confidence, Prerequisite, RunAnalysis, Source};

/// Detect how to run a project using heuristics (no AI).
///
/// Checks common patterns in order:
/// 1. package.json scripts (dev > start > serve)
/// 2. Makefile targets (run, dev, start)
/// 3. Cargo.toml (cargo run)
/// 4. pyproject.toml / requirements.txt
/// 5. docker-compose.yml
pub fn heuristic_detect(path: &Path) -> Option<RunAnalysis> {
    // Try each detection strategy in order
    if let Some(analysis) = detect_nodejs(path) {
        return Some(analysis);
    }
    
    if let Some(analysis) = detect_rust(path) {
        return Some(analysis);
    }
    
    if let Some(analysis) = detect_python(path) {
        return Some(analysis);
    }
    
    if let Some(analysis) = detect_makefile(path) {
        return Some(analysis);
    }
    
    if let Some(analysis) = detect_docker(path) {
        return Some(analysis);
    }
    
    None
}

/// Detect Node.js projects via package.json.
fn detect_nodejs(path: &Path) -> Option<RunAnalysis> {
    let package_json_path = path.join("package.json");
    if !package_json_path.exists() {
        return None;
    }
    
    let content = fs::read_to_string(&package_json_path).ok()?;
    let json: serde_json::Value = serde_json::from_str(&content).ok()?;
    
    let scripts = json.get("scripts")?.as_object()?;
    
    // Determine package manager
    let package_manager = if path.join("pnpm-lock.yaml").exists() {
        "pnpm"
    } else if path.join("yarn.lock").exists() {
        "yarn"
    } else if path.join("bun.lockb").exists() {
        "bun"
    } else {
        "npm"
    };
    
    // Check for common dev scripts in order of preference
    let (script_name, description) = if scripts.contains_key("dev") {
        ("dev", "Start development server")
    } else if scripts.contains_key("start") {
        ("start", "Start server")
    } else if scripts.contains_key("serve") {
        ("serve", "Start server")
    } else {
        return None;
    };
    
    let command = format!("{} run {}", package_manager, script_name);
    
    // Detect framework from dependencies
    let dependencies = json.get("dependencies").and_then(|d| d.as_object());
    let dev_dependencies = json.get("devDependencies").and_then(|d| d.as_object());
    
    let framework = detect_nodejs_framework(dependencies, dev_dependencies);
    let (expected_port, expected_url) = detect_nodejs_port(&framework, scripts.get(script_name));
    
    // Check prerequisites
    let has_node_modules = path.join("node_modules").exists();
    let prerequisites = if has_node_modules {
        vec![]
    } else {
        vec![Prerequisite {
            description: "Install dependencies".to_string(),
            command: format!("{} install", package_manager),
            satisfied: false,
            required: true,
        }]
    };
    
    let _project_name = json.get("name")
        .and_then(|n| n.as_str())
        .unwrap_or("Node.js project");
    
    Some(RunAnalysis {
        project_type: format!("{} application", framework.as_deref().unwrap_or("Node.js")),
        framework,
        language: detect_nodejs_language(path),
        command,
        command_description: description.to_string(),
        working_dir: None,
        alternatives: vec![],
        prerequisites,
        expected_port,
        expected_url,
        confidence: Confidence::High,
        source: Source::Heuristic,
        from_cache: false,
        user_saved: false,
    })
}

/// Detect Node.js framework from dependencies.
fn detect_nodejs_framework(
    deps: Option<&serde_json::Map<String, serde_json::Value>>,
    dev_deps: Option<&serde_json::Map<String, serde_json::Value>>,
) -> Option<String> {
    let all_deps: Vec<&str> = deps.iter()
        .chain(dev_deps.iter())
        .flat_map(|d| d.keys().map(|k| k.as_str()))
        .collect();
    
    // Check for frameworks in order of specificity
    if all_deps.contains(&"next") {
        Some("Next.js".to_string())
    } else if all_deps.contains(&"nuxt") {
        Some("Nuxt".to_string())
    } else if all_deps.contains(&"@sveltejs/kit") {
        Some("SvelteKit".to_string())
    } else if all_deps.contains(&"svelte") {
        Some("Svelte".to_string())
    } else if all_deps.contains(&"vite") && all_deps.contains(&"react") {
        Some("Vite + React".to_string())
    } else if all_deps.contains(&"vite") && all_deps.contains(&"vue") {
        Some("Vite + Vue".to_string())
    } else if all_deps.contains(&"vite") {
        Some("Vite".to_string())
    } else if all_deps.contains(&"react") {
        Some("React".to_string())
    } else if all_deps.contains(&"vue") {
        Some("Vue".to_string())
    } else if all_deps.contains(&"express") {
        Some("Express".to_string())
    } else if all_deps.contains(&"fastify") {
        Some("Fastify".to_string())
    } else if all_deps.contains(&"koa") {
        Some("Koa".to_string())
    } else if all_deps.contains(&"hono") {
        Some("Hono".to_string())
    } else {
        None
    }
}

/// Detect typical port for Node.js framework.
fn detect_nodejs_port(
    framework: &Option<String>,
    script_value: Option<&serde_json::Value>,
) -> (Option<u16>, Option<String>) {
    // Try to parse port from script
    if let Some(script) = script_value.and_then(|v| v.as_str()) {
        // Look for --port or -p flags
        if let Some(port_str) = script.split_whitespace()
            .skip_while(|&w| w != "--port" && w != "-p")
            .nth(1)
        {
            if let Ok(port) = port_str.parse::<u16>() {
                return (Some(port), Some(format!("http://localhost:{}", port)));
            }
        }
    }
    
    // Default ports by framework
    match framework.as_deref() {
        Some("Next.js") => (Some(3000), Some("http://localhost:3000".to_string())),
        Some("Nuxt") => (Some(3000), Some("http://localhost:3000".to_string())),
        Some("SvelteKit") => (Some(5173), Some("http://localhost:5173".to_string())),
        Some(f) if f.contains("Vite") => (Some(5173), Some("http://localhost:5173".to_string())),
        Some("Express") | Some("Fastify") | Some("Koa") | Some("Hono") => {
            (Some(3000), Some("http://localhost:3000".to_string()))
        }
        _ => (None, None),
    }
}

/// Detect if project uses TypeScript.
fn detect_nodejs_language(path: &Path) -> String {
    if path.join("tsconfig.json").exists() {
        "TypeScript".to_string()
    } else {
        "JavaScript".to_string()
    }
}

/// Detect Rust projects via Cargo.toml.
fn detect_rust(path: &Path) -> Option<RunAnalysis> {
    let cargo_toml_path = path.join("Cargo.toml");
    if !cargo_toml_path.exists() {
        return None;
    }
    
    let content = fs::read_to_string(&cargo_toml_path).ok()?;
    
    // Check if it's a binary crate (has [[bin]] or [package] without library-only markers)
    let is_binary = content.contains("[[bin]]") || 
        (content.contains("[package]") && !content.contains("lib.rs"));
    
    // Detect framework from dependencies
    let framework = if content.contains("actix-web") {
        Some("Actix Web".to_string())
    } else if content.contains("axum") {
        Some("Axum".to_string())
    } else if content.contains("rocket") {
        Some("Rocket".to_string())
    } else if content.contains("warp") {
        Some("Warp".to_string())
    } else if content.contains("tauri") {
        Some("Tauri".to_string())
    } else {
        None
    };
    
    // Check prerequisites
    let has_target = path.join("target").exists();
    let prerequisites = if has_target {
        vec![]
    } else {
        vec![Prerequisite {
            description: "Build dependencies".to_string(),
            command: "cargo build".to_string(),
            satisfied: false,
            required: false, // cargo run will build automatically
        }]
    };
    
    let (expected_port, expected_url) = match framework.as_deref() {
        Some("Actix Web") | Some("Axum") | Some("Rocket") | Some("Warp") => {
            (Some(8080), Some("http://localhost:8080".to_string()))
        }
        _ => (None, None),
    };
    
    Some(RunAnalysis {
        project_type: format!("{} application", framework.as_deref().unwrap_or("Rust")),
        framework,
        language: "Rust".to_string(),
        command: "cargo run".to_string(),
        command_description: if is_binary {
            "Run the binary crate".to_string()
        } else {
            "Build and run".to_string()
        },
        working_dir: None,
        alternatives: vec![],
        prerequisites,
        expected_port,
        expected_url,
        confidence: Confidence::High,
        source: Source::Heuristic,
        from_cache: false,
        user_saved: false,
    })
}

/// Detect Python projects.
fn detect_python(path: &Path) -> Option<RunAnalysis> {
    let has_pyproject = path.join("pyproject.toml").exists();
    let has_requirements = path.join("requirements.txt").exists();
    let has_main_py = path.join("main.py").exists();
    let has_app_py = path.join("app.py").exists();
    let has_manage_py = path.join("manage.py").exists();
    
    if !has_pyproject && !has_requirements && !has_main_py && !has_app_py && !has_manage_py {
        return None;
    }
    
    // Detect framework and determine command
    let (command, description, framework, expected_port, expected_url) = if has_manage_py {
        // Django
        (
            "python manage.py runserver".to_string(),
            "Start Django development server".to_string(),
            Some("Django".to_string()),
            Some(8000),
            Some("http://localhost:8000".to_string()),
        )
    } else if let Some(content) = read_python_deps(path) {
        if content.contains("fastapi") || content.contains("FastAPI") {
            (
                "python -m uvicorn app:app --reload".to_string(),
                "Start FastAPI with uvicorn".to_string(),
                Some("FastAPI".to_string()),
                Some(8000),
                Some("http://localhost:8000".to_string()),
            )
        } else if content.contains("flask") || content.contains("Flask") {
            (
                "python -m flask run".to_string(),
                "Start Flask development server".to_string(),
                Some("Flask".to_string()),
                Some(5000),
                Some("http://localhost:5000".to_string()),
            )
        } else if content.contains("streamlit") {
            (
                "streamlit run app.py".to_string(),
                "Start Streamlit app".to_string(),
                Some("Streamlit".to_string()),
                Some(8501),
                Some("http://localhost:8501".to_string()),
            )
        } else if has_app_py {
            (
                "python app.py".to_string(),
                "Run app.py".to_string(),
                None,
                None,
                None,
            )
        } else if has_main_py {
            (
                "python main.py".to_string(),
                "Run main.py".to_string(),
                None,
                None,
                None,
            )
        } else {
            return None;
        }
    } else if has_app_py {
        (
            "python app.py".to_string(),
            "Run app.py".to_string(),
            None,
            None,
            None,
        )
    } else if has_main_py {
        (
            "python main.py".to_string(),
            "Run main.py".to_string(),
            None,
            None,
            None,
        )
    } else {
        return None;
    };
    
    // Check prerequisites
    let has_venv = path.join("venv").exists() || path.join(".venv").exists();
    let prerequisites = if has_venv {
        vec![]
    } else {
        vec![Prerequisite {
            description: "Install dependencies".to_string(),
            command: if has_pyproject {
                "pip install -e .".to_string()
            } else {
                "pip install -r requirements.txt".to_string()
            },
            satisfied: false,
            required: true,
        }]
    };
    
    Some(RunAnalysis {
        project_type: format!("{} application", framework.as_deref().unwrap_or("Python")),
        framework,
        language: "Python".to_string(),
        command,
        command_description: description,
        working_dir: None,
        alternatives: vec![],
        prerequisites,
        expected_port,
        expected_url,
        confidence: Confidence::Medium,
        source: Source::Heuristic,
        from_cache: false,
        user_saved: false,
    })
}

/// Read Python dependencies from pyproject.toml or requirements.txt.
fn read_python_deps(path: &Path) -> Option<String> {
    // Try pyproject.toml first
    if let Ok(content) = fs::read_to_string(path.join("pyproject.toml")) {
        return Some(content);
    }
    
    // Fall back to requirements.txt
    fs::read_to_string(path.join("requirements.txt")).ok()
}

/// Detect Makefile-based projects.
fn detect_makefile(path: &Path) -> Option<RunAnalysis> {
    let makefile_path = path.join("Makefile");
    if !makefile_path.exists() {
        return None;
    }
    
    let content = fs::read_to_string(&makefile_path).ok()?;
    
    // Check for common targets
    let (target, description) = if content.contains("\ndev:") || content.contains("\ndev ") {
        ("dev", "Run development mode")
    } else if content.contains("\nrun:") || content.contains("\nrun ") {
        ("run", "Run the project")
    } else if content.contains("\nstart:") || content.contains("\nstart ") {
        ("start", "Start the project")
    } else if content.contains("\nserve:") || content.contains("\nserve ") {
        ("serve", "Start server")
    } else {
        return None;
    };
    
    Some(RunAnalysis {
        project_type: "Makefile project".to_string(),
        framework: None,
        language: "unknown".to_string(),
        command: format!("make {}", target),
        command_description: description.to_string(),
        working_dir: None,
        alternatives: vec![],
        prerequisites: vec![],
        expected_port: None,
        expected_url: None,
        confidence: Confidence::Medium,
        source: Source::Heuristic,
        from_cache: false,
        user_saved: false,
    })
}

/// Detect Docker Compose projects.
fn detect_docker(path: &Path) -> Option<RunAnalysis> {
    let compose_yml = path.join("docker-compose.yml");
    let compose_yaml = path.join("docker-compose.yaml");
    
    if !compose_yml.exists() && !compose_yaml.exists() {
        return None;
    }
    
    Some(RunAnalysis {
        project_type: "Docker Compose application".to_string(),
        framework: Some("Docker Compose".to_string()),
        language: "containerized".to_string(),
        command: "docker-compose up".to_string(),
        command_description: "Start containers".to_string(),
        working_dir: None,
        alternatives: vec![],
        prerequisites: vec![Prerequisite {
            description: "Docker daemon running".to_string(),
            command: "docker info".to_string(),
            satisfied: is_docker_running(),
            required: true,
        }],
        expected_port: None,
        expected_url: None,
        confidence: Confidence::High,
        source: Source::Heuristic,
        from_cache: false,
        user_saved: false,
    })
}

/// Check if Docker daemon is running.
fn is_docker_running() -> bool {
    std::process::Command::new("docker")
        .args(["info"])
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use tempfile::tempdir;
    
    #[test]
    fn test_detect_nodejs_npm() {
        let dir = tempdir().unwrap();
        let path = dir.path();
        
        let package_json = r#"{
            "name": "test-app",
            "scripts": {
                "dev": "vite",
                "build": "vite build"
            },
            "dependencies": {
                "react": "^18.0.0"
            },
            "devDependencies": {
                "vite": "^5.0.0"
            }
        }"#;
        fs::write(path.join("package.json"), package_json).unwrap();
        
        let analysis = heuristic_detect(path).unwrap();
        
        assert_eq!(analysis.command, "npm run dev");
        assert_eq!(analysis.language, "JavaScript");
        assert_eq!(analysis.framework, Some("Vite + React".to_string()));
        assert_eq!(analysis.source, Source::Heuristic);
    }
    
    #[test]
    fn test_detect_nodejs_with_pnpm() {
        let dir = tempdir().unwrap();
        let path = dir.path();
        
        fs::write(path.join("package.json"), r#"{"scripts": {"dev": "vite"}}"#).unwrap();
        fs::write(path.join("pnpm-lock.yaml"), "").unwrap();
        
        let analysis = heuristic_detect(path).unwrap();
        
        assert_eq!(analysis.command, "pnpm run dev");
    }
    
    #[test]
    fn test_detect_rust() {
        let dir = tempdir().unwrap();
        let path = dir.path();
        
        let cargo_toml = r#"
[package]
name = "test-app"
version = "0.1.0"

[dependencies]
actix-web = "4"
"#;
        fs::write(path.join("Cargo.toml"), cargo_toml).unwrap();
        
        let analysis = heuristic_detect(path).unwrap();
        
        assert_eq!(analysis.command, "cargo run");
        assert_eq!(analysis.language, "Rust");
        assert_eq!(analysis.framework, Some("Actix Web".to_string()));
    }
    
    #[test]
    fn test_detect_python_fastapi() {
        let dir = tempdir().unwrap();
        let path = dir.path();
        
        fs::write(path.join("requirements.txt"), "fastapi\nuvicorn\n").unwrap();
        fs::write(path.join("app.py"), "from fastapi import FastAPI\napp = FastAPI()").unwrap();
        
        let analysis = heuristic_detect(path).unwrap();
        
        assert!(analysis.command.contains("uvicorn"));
        assert_eq!(analysis.framework, Some("FastAPI".to_string()));
    }
    
    #[test]
    fn test_detect_makefile() {
        let dir = tempdir().unwrap();
        let path = dir.path();
        
        let makefile = "
.PHONY: dev run

dev:
\t@echo 'Starting dev'

run:
\t@echo 'Running'
";
        fs::write(path.join("Makefile"), makefile).unwrap();
        
        let analysis = heuristic_detect(path).unwrap();
        
        assert_eq!(analysis.command, "make dev");
    }
    
    #[test]
    fn test_no_detection() {
        let dir = tempdir().unwrap();
        let path = dir.path();
        
        // Empty directory
        let analysis = heuristic_detect(path);
        
        assert!(analysis.is_none());
    }
}
