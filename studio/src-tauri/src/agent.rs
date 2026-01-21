//! Agent bridge — communicates with Sunwell Python agent via subprocess.
//!
//! The agent outputs NDJSON events that we parse and forward to the frontend.

use serde::{Deserialize, Serialize};
use std::io::{BufRead, BufReader};
use std::path::Path;
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use tauri::{AppHandle, Emitter};

/// Agent event types matching Python's EventType enum.
#[allow(dead_code)]
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EventType {
    // Memory events
    MemoryLoad,
    MemoryLoaded,
    MemoryNew,
    MemoryLearning,
    MemoryDeadEnd,
    MemoryCheckpoint,
    MemorySaved,
    // Signal events
    Signal,
    SignalRoute,
    // Planning events
    PlanStart,
    PlanCandidate,
    PlanWinner,
    PlanExpanded,
    PlanAssess,
    // Gate events
    GateStart,
    GateStep,
    GatePass,
    GateFail,
    // Execution events
    TaskStart,
    TaskProgress,
    TaskComplete,
    TaskFailed,
    // Validation events
    ValidateStart,
    ValidateLevel,
    ValidateError,
    ValidatePass,
    // Fix events
    FixStart,
    FixProgress,
    FixAttempt,
    FixComplete,
    FixFailed,
    // Completion events
    Complete,
    Error,
    Escalate,
    // RFC-067: Integration verification events
    IntegrationCheckStart,
    IntegrationCheckPass,
    IntegrationCheckFail,
    StubDetected,
    OrphanDetected,
    WireTaskGenerated,
}

/// Agent event from the Python agent (NDJSON line).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentEvent {
    #[serde(rename = "type")]
    pub event_type: String,
    pub data: serde_json::Value,
    pub timestamp: f64,
}

/// Manages the agent subprocess.
pub struct AgentBridge {
    process: Option<Child>,
    running: Arc<AtomicBool>,
}

impl AgentBridge {
    pub fn new() -> Self {
        Self {
            process: None,
            running: Arc::new(AtomicBool::new(false)),
        }
    }

    /// Run a goal and stream events to the frontend.
    ///
    /// RFC-064: Supports optional lens selection.
    /// - `lens`: Explicit lens name (e.g., "coder", "tech-writer")
    /// - `auto_lens`: Whether to auto-detect lens based on goal (default: true)
    pub fn run_goal(
        &mut self,
        app: AppHandle,
        goal: &str,
        project_path: &Path,
        lens: Option<&str>,
        auto_lens: bool,
    ) -> Result<(), String> {
        if self.running.load(Ordering::SeqCst) {
            return Err("Agent already running".to_string());
        }

        // Build args with optional lens parameters (RFC-064)
        let mut args = vec!["agent", "run", "--json", "--strategy", "harmonic"];

        // Add lens flag if explicitly specified
        let lens_owned: String;
        if let Some(lens_name) = lens {
            args.push("--lens");
            lens_owned = lens_name.to_string();
            args.push(&lens_owned);
        }

        // Disable auto-lens if requested
        if !auto_lens {
            args.push("--no-auto-lens");
        }

        args.push(goal);

        // Start the Sunwell agent with JSON output
        // Use harmonic planning for better high-level plans, then artifact-first for execution
        // HarmonicPlanner generates multiple candidates and selects best, then uses ArtifactPlanner
        // for execution (which supports automatic incremental builds)
        let mut child = Command::new("sunwell")
            .args(&args)
            .current_dir(project_path)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("Failed to start agent: {}", e))?;

        let stdout = child.stdout.take().ok_or("Failed to capture stdout")?;
        let stderr = child.stderr.take();
        self.process = Some(child);
        self.running.store(true, Ordering::SeqCst);

        let running = self.running.clone();

        // Spawn thread to drain stderr (prevents blocking if buffer fills)
        if let Some(stderr) = stderr {
            std::thread::spawn(move || {
                let reader = BufReader::new(stderr);
                for line in reader.lines() {
                    match line {
                        Ok(err_line) if !err_line.is_empty() => {
                            eprintln!("[sunwell stderr] {}", err_line);
                        }
                        Err(_) => break,
                        _ => {}
                    }
                }
            });
        }

        // Spawn thread to read NDJSON events from stdout
        std::thread::spawn(move || {
            let reader = BufReader::new(stdout);

            for line in reader.lines() {
                if !running.load(Ordering::SeqCst) {
                    break;
                }

                match line {
                    Ok(json_line) => {
                        if json_line.is_empty() {
                            continue;
                        }

                        match serde_json::from_str::<AgentEvent>(&json_line) {
                            Ok(event) => {
                                // Emit event to frontend
                                let _ = app.emit("agent-event", &event);

                                // Check if this is a terminal event
                                if event.event_type == "complete" || event.event_type == "error" {
                                    running.store(false, Ordering::SeqCst);
                                    break;
                                }
                            }
                            Err(e) => {
                                eprintln!("Failed to parse event: {} - {}", e, json_line);
                            }
                        }
                    }
                    Err(e) => {
                        eprintln!("Failed to read line: {}", e);
                        break;
                    }
                }
            }

            running.store(false, Ordering::SeqCst);
            let _ = app.emit("agent-stopped", ());
        });

        Ok(())
    }

    /// Resume an interrupted goal and stream events to the frontend.
    pub fn resume_goal(
        &mut self,
        app: AppHandle,
        project_path: &Path,
    ) -> Result<(), String> {
        if self.running.load(Ordering::SeqCst) {
            return Err("Agent already running".to_string());
        }

        // Start the Sunwell agent in resume mode with JSON output
        let mut child = Command::new("sunwell")
            .args(["agent", "resume", "--json"])
            .current_dir(project_path)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("Failed to start agent: {}", e))?;

        let stdout = child.stdout.take().ok_or("Failed to capture stdout")?;
        let stderr = child.stderr.take();
        self.process = Some(child);
        self.running.store(true, Ordering::SeqCst);

        let running = self.running.clone();

        // Spawn thread to drain stderr (prevents blocking if buffer fills)
        if let Some(stderr) = stderr {
            std::thread::spawn(move || {
                let reader = BufReader::new(stderr);
                for line in reader.lines() {
                    match line {
                        Ok(err_line) if !err_line.is_empty() => {
                            eprintln!("[sunwell stderr] {}", err_line);
                        }
                        Err(_) => break,
                        _ => {}
                    }
                }
            });
        }

        // Spawn thread to read NDJSON events from stdout
        std::thread::spawn(move || {
            let reader = BufReader::new(stdout);

            for line in reader.lines() {
                if !running.load(Ordering::SeqCst) {
                    break;
                }

                match line {
                    Ok(json_line) => {
                        if json_line.is_empty() {
                            continue;
                        }

                        match serde_json::from_str::<AgentEvent>(&json_line) {
                            Ok(event) => {
                                let _ = app.emit("agent-event", &event);

                                if event.event_type == "complete" || event.event_type == "error" {
                                    running.store(false, Ordering::SeqCst);
                                    break;
                                }
                            }
                            Err(e) => {
                                eprintln!("Failed to parse event: {} - {}", e, json_line);
                            }
                        }
                    }
                    Err(e) => {
                        eprintln!("Failed to read line: {}", e);
                        break;
                    }
                }
            }

            running.store(false, Ordering::SeqCst);
            let _ = app.emit("agent-stopped", ());
        });

        Ok(())
    }

    /// Run a specific backlog goal by ID (RFC-056).
    pub fn run_backlog_goal(
        &mut self,
        app: AppHandle,
        goal_id: &str,
        project_path: &Path,
    ) -> Result<(), String> {
        if self.running.load(Ordering::SeqCst) {
            return Err("Agent already running".to_string());
        }

        // Start the Sunwell agent with backlog run command
        let mut child = Command::new("sunwell")
            .args(["backlog", "run", goal_id, "--json"])
            .current_dir(project_path)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("Failed to start agent: {}", e))?;

        let stdout = child.stdout.take().ok_or("Failed to capture stdout")?;
        let stderr = child.stderr.take();
        self.process = Some(child);
        self.running.store(true, Ordering::SeqCst);

        let running = self.running.clone();

        // Spawn thread to drain stderr (prevents blocking if buffer fills)
        if let Some(stderr) = stderr {
            std::thread::spawn(move || {
                let reader = BufReader::new(stderr);
                for line in reader.lines() {
                    match line {
                        Ok(err_line) if !err_line.is_empty() => {
                            eprintln!("[sunwell stderr] {}", err_line);
                        }
                        Err(_) => break,
                        _ => {}
                    }
                }
            });
        }

        // Spawn thread to read NDJSON events from stdout
        std::thread::spawn(move || {
            let reader = BufReader::new(stdout);

            for line in reader.lines() {
                if !running.load(Ordering::SeqCst) {
                    break;
                }

                match line {
                    Ok(json_line) => {
                        if json_line.is_empty() {
                            continue;
                        }

                        match serde_json::from_str::<AgentEvent>(&json_line) {
                            Ok(event) => {
                                // Emit event to frontend
                                let _ = app.emit("agent-event", &event);

                                // Check if this is a terminal event
                                if event.event_type == "complete" || event.event_type == "error" {
                                    running.store(false, Ordering::SeqCst);
                                    break;
                                }
                            }
                            Err(e) => {
                                eprintln!("Failed to parse event: {} - {}", e, json_line);
                            }
                        }
                    }
                    Err(e) => {
                        eprintln!("Failed to read line: {}", e);
                        break;
                    }
                }
            }

            running.store(false, Ordering::SeqCst);
            let _ = app.emit("agent-stopped", ());
        });

        Ok(())
    }

    /// Stop the running agent.
    pub fn stop(&mut self) -> Result<(), String> {
        self.running.store(false, Ordering::SeqCst);

        if let Some(mut process) = self.process.take() {
            process.kill().map_err(|e| format!("Failed to kill agent: {}", e))?;
        }

        Ok(())
    }

    /// Check if agent is running.
    #[allow(dead_code)]
    pub fn is_running(&self) -> bool {
        self.running.load(Ordering::SeqCst)
    }
}

impl Default for AgentBridge {
    fn default() -> Self {
        Self::new()
    }
}
