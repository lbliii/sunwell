//! Agent bridge — communicates with Sunwell Python agent via subprocess.
//!
//! The agent outputs NDJSON events that we parse and forward to the frontend.

use crate::error::{ErrorCode, SunwellError};
use crate::sunwell_err;
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
    /// RFC-097: Optional UI hints from Python
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ui_hints: Option<serde_json::Value>,
}

/// RFC-097: UI rendering hints for frontend.
///
/// These hints help the frontend render events more richly with
/// appropriate icons, colors, and animations.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UIHints {
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub icon: Option<String>,
    #[serde(default = "default_severity")]
    pub severity: String,
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub animation: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub progress: Option<f64>,
}

fn default_severity() -> String {
    "info".into()
}

impl UIHints {
    /// Create UI hints based on event type.
    ///
    /// If the Python event already includes ui_hints, those are used.
    /// Otherwise, Rust provides sensible defaults based on event_type.
    pub fn from_event(event: &AgentEvent) -> Self {
        // If Python already provided hints, use them
        if let Some(hints) = &event.ui_hints {
            if let Ok(parsed) = serde_json::from_value::<UIHints>(hints.clone()) {
                return parsed;
            }
        }

        // Otherwise, provide Rust-side defaults
        match event.event_type.as_str() {
            "task_start" => UIHints {
                icon: Some("⚡".into()),
                severity: "info".into(),
                animation: Some("pulse".into()),
                progress: None,
            },
            "task_complete" => UIHints {
                icon: Some("✓".into()),
                severity: "success".into(),
                animation: Some("fade-in".into()),
                progress: Some(1.0),
            },
            "task_failed" | "error" => UIHints {
                icon: Some("✗".into()),
                severity: "error".into(),
                animation: Some("shake".into()),
                progress: None,
            },
            "model_start" | "model_tokens" | "model_thinking" | "model_heartbeat" => UIHints {
                icon: Some("🧠".into()),
                severity: "info".into(),
                animation: Some("pulse".into()),
                progress: None,
            },
            "model_complete" => UIHints {
                icon: Some("🧠".into()),
                severity: "success".into(),
                animation: Some("fade-in".into()),
                progress: Some(1.0),
            },
            "gate_pass" | "validate_pass" => UIHints {
                icon: Some("✓".into()),
                severity: "success".into(),
                animation: None,
                progress: None,
            },
            "gate_fail" | "validate_error" => UIHints {
                icon: Some("✗".into()),
                severity: "error".into(),
                animation: Some("shake".into()),
                progress: None,
            },
            "fix_start" => UIHints {
                icon: Some("🔧".into()),
                severity: "warning".into(),
                animation: Some("pulse".into()),
                progress: None,
            },
            "fix_complete" => UIHints {
                icon: Some("✓".into()),
                severity: "success".into(),
                animation: Some("fade-in".into()),
                progress: None,
            },
            "complete" => UIHints {
                icon: Some("✨".into()),
                severity: "success".into(),
                animation: Some("fade-in".into()),
                progress: Some(1.0),
            },
            "security_violation" => UIHints {
                icon: Some("🛡️".into()),
                severity: "error".into(),
                animation: Some("shake".into()),
                progress: None,
            },
            "security_approval_requested" => UIHints {
                icon: Some("🔐".into()),
                severity: "warning".into(),
                animation: None,
                progress: None,
            },
            "plan_winner" | "plan_expanded" => UIHints {
                icon: Some("📋".into()),
                severity: "info".into(),
                animation: Some("fade-in".into()),
                progress: None,
            },
            "memory_learning" => UIHints {
                icon: Some("💡".into()),
                severity: "info".into(),
                animation: Some("pulse".into()),
                progress: None,
            },
            _ => UIHints::default(),
        }
    }
}

impl Default for UIHints {
    fn default() -> Self {
        Self {
            icon: None,
            severity: default_severity(),
            animation: None,
            progress: None,
        }
    }
}

/// RFC-097: UI-enriched event for frontend.
///
/// Wraps the raw AgentEvent with computed UI hints for richer rendering.
#[derive(Debug, Clone, Serialize)]
pub struct UIEvent {
    /// The original event data
    #[serde(flatten)]
    pub event: AgentEvent,
    /// Computed UI hints (from Python or Rust defaults)
    pub ui: UIHints,
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
    ) -> Result<(), SunwellError> {
        if self.running.load(Ordering::SeqCst) {
            return Err(sunwell_err!(RuntimeConcurrentLimit, "Agent already running")
                .with_hints(vec!["Wait for the current operation to complete", "Or stop the agent first"]));
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
            .map_err(|e| SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec![
                    "Check if sunwell CLI is installed",
                    "Try running 'sunwell --help' to verify",
                    "Check your PATH includes sunwell",
                ]))?;

        let stdout = child.stdout.take().ok_or_else(|| 
            sunwell_err!(RuntimeProcessFailed, "Failed to capture agent stdout"))?;
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
                                // RFC-097: Wrap event with UI hints for richer frontend rendering
                                let ui_event = UIEvent {
                                    ui: UIHints::from_event(&event),
                                    event: event.clone(),
                                };
                                // Emit enriched event to frontend
                                let _ = app.emit("agent-event", &ui_event);

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
    ) -> Result<(), SunwellError> {
        if self.running.load(Ordering::SeqCst) {
            return Err(sunwell_err!(RuntimeConcurrentLimit, "Agent already running")
                .with_hints(vec!["Wait for the current operation to complete", "Or stop the agent first"]));
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
            .map_err(|e| SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec![
                    "Check if sunwell CLI is installed",
                    "Try running 'sunwell --help' to verify",
                ]))?;

        let stdout = child.stdout.take().ok_or_else(|| 
            sunwell_err!(RuntimeProcessFailed, "Failed to capture agent stdout"))?;
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
                                // RFC-097: Wrap event with UI hints
                                let ui_event = UIEvent {
                                    ui: UIHints::from_event(&event),
                                    event: event.clone(),
                                };
                                let _ = app.emit("agent-event", &ui_event);

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
    ) -> Result<(), SunwellError> {
        if self.running.load(Ordering::SeqCst) {
            return Err(sunwell_err!(RuntimeConcurrentLimit, "Agent already running")
                .with_hints(vec!["Wait for the current operation to complete", "Or stop the agent first"]));
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
            .map_err(|e| SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec![
                    "Check if sunwell CLI is installed",
                    "Try running 'sunwell --help' to verify",
                ]))?;

        let stdout = child.stdout.take().ok_or_else(|| 
            sunwell_err!(RuntimeProcessFailed, "Failed to capture agent stdout"))?;
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
                                // RFC-097: Wrap event with UI hints
                                let ui_event = UIEvent {
                                    ui: UIHints::from_event(&event),
                                    event: event.clone(),
                                };
                                // Emit enriched event to frontend
                                let _ = app.emit("agent-event", &ui_event);

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
    pub fn stop(&mut self) -> Result<(), SunwellError> {
        self.running.store(false, Ordering::SeqCst);

        if let Some(mut process) = self.process.take() {
            process.kill().map_err(|e| SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["The agent process may have already terminated"]))?;
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
