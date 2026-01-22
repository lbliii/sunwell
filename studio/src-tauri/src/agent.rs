//! Agent bridge — communicates with Sunwell Python agent via subprocess.
//!
//! The agent outputs NDJSON events that we parse and forward to the frontend.

use crate::util::{parse_json_safe, sunwell_command};
use serde::{Deserialize, Serialize};
use std::io::{BufRead, BufReader};
use std::path::Path;
use std::process::{Child, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use tauri::{AppHandle, Emitter};

/// Agent event types matching Python's EventType enum (sunwell.adaptive.events).
///
/// KEEP IN SYNC WITH: src/sunwell/adaptive/events.py
#[allow(dead_code)]
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EventType {
    // Memory events (Simulacrum integration)
    MemoryLoad,
    MemoryLoaded,
    MemoryNew,
    MemoryLearning,
    MemoryDeadEnd,
    MemoryCheckpoint,
    MemorySaved,

    // Signal events (adaptive routing)
    Signal,
    SignalRoute,

    // Planning events
    PlanStart,
    PlanCandidate,
    PlanWinner,
    PlanExpanded,
    PlanAssess,

    // RFC-058: Planning visibility events
    PlanCandidateStart,
    PlanCandidateGenerated,
    PlanCandidatesComplete,
    PlanCandidateScored,
    PlanScoringComplete,
    PlanRefineStart,
    PlanRefineAttempt,
    PlanRefineComplete,
    PlanRefineFinal,
    PlanDiscoveryProgress,

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

    // Lens events (RFC-064)
    LensSelected,
    LensChanged,

    // Integration verification events (RFC-067)
    IntegrationCheckStart,
    IntegrationCheckPass,
    IntegrationCheckFail,
    StubDetected,
    OrphanDetected,
    WireTaskGenerated,

    // Briefing events (RFC-071)
    BriefingLoaded,
    BriefingSaved,

    // Prefetch events (RFC-071)
    PrefetchStart,
    PrefetchComplete,
    PrefetchTimeout,
    LensSuggested,

    // Inference visibility events (RFC-081)
    ModelStart,
    ModelTokens,
    ModelThinking,
    ModelComplete,
    ModelHeartbeat,

    // Skill graph execution events (RFC-087)
    SkillGraphResolved,
    SkillWaveStart,
    SkillWaveComplete,
    SkillCacheHit,
    SkillExecuteStart,
    SkillExecuteComplete,

    // Security events (RFC-089)
    SecurityApprovalRequested,
    SecurityApprovalReceived,
    SecurityViolation,
    SecurityScanComplete,
    AuditLogEntry,

    // Backlog lifecycle events (RFC-094)
    BacklogGoalAdded,
    BacklogGoalStarted,
    BacklogGoalCompleted,
    BacklogGoalFailed,
    BacklogRefreshed,
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
    /// RFC-Cloud-Model-Parity: Supports optional provider selection.
    /// - `lens`: Explicit lens name (e.g., "coder", "tech-writer")
    /// - `auto_lens`: Whether to auto-detect lens based on goal (default: true)
    /// - `provider`: Model provider (e.g., "openai", "anthropic", "ollama")
    pub fn run_goal(
        &mut self,
        app: AppHandle,
        goal: &str,
        project_path: &Path,
        lens: Option<&str>,
        auto_lens: bool,
        provider: Option<&str>,
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

        // Add provider flag if explicitly specified (RFC-Cloud-Model-Parity)
        let provider_owned: String;
        if let Some(provider_name) = provider {
            args.push("--provider");
            provider_owned = provider_name.to_string();
            args.push(&provider_owned);
        }

        args.push(goal);

        // Start the Sunwell agent with JSON output
        // Use harmonic planning for better high-level plans, then artifact-first for execution
        // HarmonicPlanner generates multiple candidates and selects best, then uses ArtifactPlanner
        // for execution (which supports automatic incremental builds)
        let mut child = sunwell_command()
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

                        match parse_json_safe::<AgentEvent>(&json_line) {
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
    ///
    /// RFC-Cloud-Model-Parity: Supports optional provider selection.
    pub fn resume_goal(
        &mut self,
        app: AppHandle,
        project_path: &Path,
        provider: Option<&str>,
    ) -> Result<(), String> {
        if self.running.load(Ordering::SeqCst) {
            return Err("Agent already running".to_string());
        }

        // Build args with optional provider (RFC-Cloud-Model-Parity)
        let mut args = vec!["agent", "resume", "--json"];
        let provider_owned: String;
        if let Some(provider_name) = provider {
            args.push("--provider");
            provider_owned = provider_name.to_string();
            args.push(&provider_owned);
        }

        // Start the Sunwell agent in resume mode with JSON output
        let mut child = sunwell_command()
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

                        match parse_json_safe::<AgentEvent>(&json_line) {
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
    ///
    /// RFC-Cloud-Model-Parity: Supports optional provider selection.
    pub fn run_backlog_goal(
        &mut self,
        app: AppHandle,
        goal_id: &str,
        project_path: &Path,
        provider: Option<&str>,
    ) -> Result<(), String> {
        if self.running.load(Ordering::SeqCst) {
            return Err("Agent already running".to_string());
        }

        // Build args with optional provider (RFC-Cloud-Model-Parity)
        let mut args = vec!["backlog", "run", goal_id, "--json"];
        let provider_owned: String;
        if let Some(provider_name) = provider {
            args.push("--provider");
            provider_owned = provider_name.to_string();
            args.push(&provider_owned);
        }

        // Start the Sunwell agent with backlog run command
        let mut child = sunwell_command()
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

                        match parse_json_safe::<AgentEvent>(&json_line) {
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
