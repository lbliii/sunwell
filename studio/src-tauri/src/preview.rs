//! Preview system — launches and manages project previews.
//!
//! Supports different preview modes based on project type:
//! - Web apps: Start server, open embedded browser
//! - CLI tools: Pre-filled terminal command
//! - Prose: Formatted reader view
//! - Dialogues: Interactive dialogue player

use crate::error::{ErrorCode, SunwellError};
use crate::project::{Project, ProjectType};
use serde::{Deserialize, Serialize};
use std::net::TcpListener;
use std::process::{Child, Command, Stdio};

/// Type of preview view.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ViewType {
    /// Embedded web browser
    WebView,
    /// Terminal/CLI view
    Terminal,
    /// Formatted prose reader
    Prose,
    /// Screenplay viewer
    Fountain,
    /// Interactive dialogue player
    Dialogue,
    /// Generic file viewer
    Generic,
}

/// An active preview session.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PreviewSession {
    /// URL to open (for web views)
    pub url: Option<String>,
    /// Content to display (for prose/dialogue)
    pub content: Option<String>,
    /// Type of view to use
    pub view_type: ViewType,
    /// Command that was run (for terminals)
    pub command: Option<String>,
    /// Port being used
    pub port: Option<u16>,
}

/// Web framework detection.
#[derive(Debug, Clone)]
pub enum Framework {
    Flask,
    FastAPI,
    Django,
    Express,
    Unknown,
}

/// Manages preview sessions.
pub struct PreviewManager {
    /// Currently running server process
    server_process: Option<Child>,
    /// Current session info
    current_session: Option<PreviewSession>,
}

impl PreviewManager {
    pub fn new() -> Self {
        Self {
            server_process: None,
            current_session: None,
        }
    }

    /// Launch a preview for the given project.
    pub fn launch(&mut self, project: &Project) -> Result<PreviewSession, String> {
        // Stop any existing preview
        self.stop()?;

        let session = match project.project_type {
            ProjectType::CodeWeb | ProjectType::CodePython => self.launch_web_app(project)?,
            ProjectType::CodeCli => self.launch_cli(project)?,
            ProjectType::Novel => self.launch_prose_reader(project)?,
            ProjectType::Screenplay => self.launch_fountain_viewer(project)?,
            ProjectType::GameDialogue => self.launch_dialogue_player(project)?,
            _ => self.launch_generic(project)?,
        };

        self.current_session = Some(session.clone());
        Ok(session)
    }

    /// Stop the current preview.
    pub fn stop(&mut self) -> Result<(), String> {
        if let Some(mut process) = self.server_process.take() {
            process.kill().map_err(|e| {
                SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                    .with_hints(vec!["Process may have already exited"])
                    .to_json()
            })?;
        }
        self.current_session = None;
        Ok(())
    }

    /// Launch a web application preview.
    fn launch_web_app(&mut self, project: &Project) -> Result<PreviewSession, String> {
        let framework = self.detect_framework(&project.path);
        let port = find_free_port()?;

        let process = match framework {
            Framework::Flask => Command::new("python")
                .args(["-m", "flask", "run", "--port", &port.to_string()])
                .current_dir(&project.path)
                .env("FLASK_APP", "app.py")
                .stdout(Stdio::piped())
                .stderr(Stdio::piped())
                .spawn()
                .map_err(|e| {
                    SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                        .with_hints(vec!["Check if Flask is installed", "Run 'pip install flask'"])
                        .to_json()
                })?,
            Framework::FastAPI => Command::new("uvicorn")
                .args(["main:app", "--port", &port.to_string()])
                .current_dir(&project.path)
                .stdout(Stdio::piped())
                .stderr(Stdio::piped())
                .spawn()
                .map_err(|e| {
                    SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                        .with_hints(vec!["Check if uvicorn is installed", "Run 'pip install uvicorn'"])
                        .to_json()
                })?,
            Framework::Django => Command::new("python")
                .args(["manage.py", "runserver", &format!("127.0.0.1:{}", port)])
                .current_dir(&project.path)
                .stdout(Stdio::piped())
                .stderr(Stdio::piped())
                .spawn()
                .map_err(|e| {
                    SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                        .with_hints(vec!["Check if Django is configured", "Run 'python manage.py check'"])
                        .to_json()
                })?,
            Framework::Express => Command::new("npm")
                .args(["start"])
                .current_dir(&project.path)
                .env("PORT", port.to_string())
                .stdout(Stdio::piped())
                .stderr(Stdio::piped())
                .spawn()
                .map_err(|e| {
                    SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                        .with_hints(vec!["Check if npm is installed", "Run 'npm install' first"])
                        .to_json()
                })?,
            Framework::Unknown => {
                // Try generic Python approach
                Command::new("python")
                    .args(["app.py"])
                    .current_dir(&project.path)
                    .stdout(Stdio::piped())
                    .stderr(Stdio::piped())
                    .spawn()
                    .map_err(|e| {
                        SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                            .with_hints(vec!["Check if app.py exists", "Check Python is installed"])
                            .to_json()
                    })?
            }
        };

        self.server_process = Some(process);

        Ok(PreviewSession {
            url: Some(format!("http://localhost:{}", port)),
            content: None,
            view_type: ViewType::WebView,
            command: None,
            port: Some(port),
        })
    }

    /// Launch CLI preview.
    fn launch_cli(&self, project: &Project) -> Result<PreviewSession, String> {
        let cmd = if project.path.join("__main__.py").exists() {
            format!("python -m {}", project.name)
        } else if project.path.join("cli.py").exists() {
            "python cli.py --help".to_string()
        } else {
            "python -h".to_string()
        };

        Ok(PreviewSession {
            url: None,
            content: None,
            view_type: ViewType::Terminal,
            command: Some(cmd),
            port: None,
        })
    }

    /// Launch prose reader preview.
    fn launch_prose_reader(&self, project: &Project) -> Result<PreviewSession, String> {
        // Find first chapter/content file
        let content = self.find_prose_content(&project.path)?;

        Ok(PreviewSession {
            url: None,
            content: Some(content),
            view_type: ViewType::Prose,
            command: None,
            port: None,
        })
    }

    /// Launch Fountain screenplay viewer.
    fn launch_fountain_viewer(&self, project: &Project) -> Result<PreviewSession, String> {
        let content = self.find_fountain_content(&project.path)?;

        Ok(PreviewSession {
            url: None,
            content: Some(content),
            view_type: ViewType::Fountain,
            command: None,
            port: None,
        })
    }

    /// Launch dialogue player.
    fn launch_dialogue_player(&self, project: &Project) -> Result<PreviewSession, String> {
        let content = self.find_dialogue_content(&project.path)?;

        Ok(PreviewSession {
            url: None,
            content: Some(content),
            view_type: ViewType::Dialogue,
            command: None,
            port: None,
        })
    }

    /// Launch generic preview.
    fn launch_generic(&self, project: &Project) -> Result<PreviewSession, String> {
        Ok(PreviewSession {
            url: None,
            content: Some(format!("Project: {}\nPath: {}", project.name, project.path.display())),
            view_type: ViewType::Generic,
            command: None,
            port: None,
        })
    }

    /// Detect web framework from project files.
    fn detect_framework(&self, path: &std::path::Path) -> Framework {
        // Check Python files
        for file in ["app.py", "main.py", "wsgi.py"] {
            let filepath = path.join(file);
            if let Ok(content) = std::fs::read_to_string(&filepath) {
                if content.contains("Flask") {
                    return Framework::Flask;
                }
                if content.contains("FastAPI") {
                    return Framework::FastAPI;
                }
            }
        }

        // Check for Django
        if path.join("manage.py").exists() {
            return Framework::Django;
        }

        // Check package.json for Node frameworks
        if let Ok(content) = std::fs::read_to_string(path.join("package.json")) {
            if content.contains("express") {
                return Framework::Express;
            }
        }

        Framework::Unknown
    }

    /// Find prose content to display.
    fn find_prose_content(&self, path: &std::path::Path) -> Result<String, String> {
        // Look for chapter files
        if let Ok(entries) = std::fs::read_dir(path) {
            for entry in entries.flatten() {
                let entry_path = entry.path();
                if entry_path.extension().map(|e| e == "md").unwrap_or(false) {
                    if let Ok(content) = std::fs::read_to_string(&entry_path) {
                        return Ok(content);
                    }
                }
            }
        }
        Err("No prose content found".to_string())
    }

    /// Find Fountain screenplay content.
    fn find_fountain_content(&self, path: &std::path::Path) -> Result<String, String> {
        if let Ok(entries) = std::fs::read_dir(path) {
            for entry in entries.flatten() {
                let entry_path = entry.path();
                if entry_path.extension().map(|e| e == "fountain").unwrap_or(false) {
                    if let Ok(content) = std::fs::read_to_string(&entry_path) {
                        return Ok(content);
                    }
                }
            }
        }
        Err("No Fountain screenplay found".to_string())
    }

    /// Find dialogue content.
    fn find_dialogue_content(&self, path: &std::path::Path) -> Result<String, String> {
        for ext in ["yarn", "ink", "json"] {
            if let Ok(entries) = std::fs::read_dir(path) {
                for entry in entries.flatten() {
                    let entry_path = entry.path();
                    if entry_path.extension().map(|e| e == ext).unwrap_or(false) {
                        if let Ok(content) = std::fs::read_to_string(&entry_path) {
                            return Ok(content);
                        }
                    }
                }
            }
        }
        Err("No dialogue content found".to_string())
    }
}

impl Default for PreviewManager {
    fn default() -> Self {
        Self::new()
    }
}

/// Find a free TCP port.
fn find_free_port() -> Result<u16, String> {
    let listener = TcpListener::bind("127.0.0.1:0").map_err(|e| {
        SunwellError::from_error(ErrorCode::NetworkUnreachable, e)
            .with_hints(vec!["Check if the port range is available"])
            .to_json()
    })?;
    let port = listener.local_addr().map_err(|e| {
        SunwellError::from_error(ErrorCode::NetworkUnreachable, e)
            .with_hints(vec!["Network configuration issue"])
            .to_json()
    })?.port();
    Ok(port)
}
