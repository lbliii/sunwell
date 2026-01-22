//! Sunwell Studio — Tauri Application Entry Point
//!
//! A minimal, beautiful GUI for AI-native creative work.
//! Communicates with the Sunwell Python agent via subprocess streaming.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod agent;
mod briefing;
mod commands;
mod dag;
mod error;
mod heuristic_detect;
mod interface;
mod lens;
mod memory;
mod naaru;
mod preview;
mod project;
mod run_analysis;
mod security;
mod self_knowledge;
mod surface;
mod util;
mod weakness;
mod weakness_types;
mod workflow;
mod workspace;
mod writer;

use clap::Parser;
use commands::AppState;
use serde::Serialize;
use tauri::{Emitter, Manager};

/// Sunwell Studio — AI-native writing environment (RFC-086).
#[derive(Parser, Debug, Clone)]
#[command(name = "sunwell-studio", about = "AI-native writing environment")]
struct CliArgs {
    /// Path to project directory to open
    #[arg(short, long)]
    project: Option<String>,

    /// Lens to use (e.g., coder.lens, tech-writer.lens)
    #[arg(short, long)]
    lens: Option<String>,

    /// Workspace mode: writer, code, or planning
    #[arg(short, long)]
    mode: Option<String>,

    /// Path to plan JSON file to load on startup (RFC-090)
    #[arg(long)]
    plan: Option<String>,
}

/// Startup parameters passed via CLI (RFC-086, RFC-090).
#[derive(Debug, Clone, Serialize)]
pub struct StartupParams {
    pub project: Option<String>,
    pub lens: Option<String>,
    pub mode: Option<String>,
    /// RFC-090: Plan file to load on startup
    pub plan: Option<String>,
}

fn main() {
    // RFC-086: Parse CLI args before Tauri starts
    let args = CliArgs::parse();
    let startup = StartupParams {
        project: args.project,
        lens: args.lens,
        mode: args.mode,
        plan: args.plan,  // RFC-090
    };

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(AppState::default())
        .setup(move |app| {
            // Emit startup params to frontend if any were provided (RFC-090: include plan)
            if startup.project.is_some() || startup.lens.is_some() || startup.mode.is_some() || startup.plan.is_some() {
                let handle = app.handle().clone();
                let params = startup.clone();
                // Emit after a short delay to ensure frontend is ready
                std::thread::spawn(move || {
                    std::thread::sleep(std::time::Duration::from_millis(500));
                    let _ = handle.emit("startup-params", params);
                });
            }

            #[cfg(debug_assertions)]
            {
                let window = app.get_webview_window("main").unwrap();
                window.open_devtools();
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            // Goal execution
            commands::run_goal,
            commands::stop_agent,
            // Workspace resolution (RFC-043 addendum)
            commands::resolve_workspace_for_goal,
            commands::get_default_workspace,
            commands::create_project,
            commands::get_workspace_settings,
            commands::generate_project_name,
            commands::check_path_available,
            // Project management
            commands::get_recent_projects,
            commands::remove_recent_project,
            commands::open_project,
            commands::get_project_info,
            // Project discovery & resume
            commands::scan_projects,
            commands::get_project_status,
            commands::resume_project,
            // Preview
            commands::launch_preview,
            commands::stop_preview,
            // Project access (files, terminal, edit)
            commands::open_in_finder,
            commands::open_terminal,
            commands::open_in_editor,
            // File tree
            commands::list_project_files,
            commands::read_file_contents,
            // Project lifecycle (delete, archive, iterate)
            commands::delete_project,
            commands::archive_project,
            commands::iterate_project,
            commands::get_project_learnings,
            // DAG / Pipeline view (RFC-056, RFC-090)
            dag::get_project_dag,
            dag::execute_dag_node,
            dag::refresh_backlog,
            dag::load_plan_file,  // RFC-090: Load plan from CLI
            // Incremental Execution (RFC-074)
            dag::get_incremental_plan,
            dag::get_cache_stats,
            dag::get_artifact_impact,
            dag::clear_cache,
            // Memory / Simulacrum (RFC-013, RFC-014, RFC-084)
            memory::get_memory_stats,
            memory::list_sessions,
            memory::get_intelligence,
            memory::get_concept_graph,
            memory::get_chunk_hierarchy,
            // Saved prompts
            commands::get_saved_prompts,
            commands::save_prompt,
            commands::remove_saved_prompt,
            // Weakness Cascade (RFC-063)
            weakness::scan_weaknesses,
            weakness::preview_cascade,
            weakness::execute_cascade_fix,
            weakness::start_cascade_execution,
            weakness::get_weakness_overlay,
            weakness::extract_contract,
            // Lens Management (RFC-064)
            lens::list_lenses,
            lens::get_lens_detail,
            lens::get_project_lens_config,
            lens::set_project_lens,
            // Lens Library (RFC-070)
            lens::get_lens_library,
            lens::fork_lens,
            lens::save_lens,
            lens::delete_lens,
            lens::get_lens_versions,
            lens::rollback_lens,
            lens::set_default_lens,
            lens::get_lens_content,
            // Run Analysis (RFC-066)
            commands::analyze_project_for_run,
            commands::run_project,
            commands::stop_project_run,
            commands::save_run_command,
            // Project Intent Analysis (RFC-079)
            commands::analyze_project,
            commands::analyze_monorepo,
            commands::get_project_signals,
            // Briefing System (RFC-071)
            briefing::get_briefing,
            briefing::has_briefing,
            briefing::clear_briefing,
            // Surface Primitives & Layout (RFC-072)
            surface::get_primitive_registry,
            surface::compose_surface,
            surface::record_layout_success,
            surface::emit_primitive_event,
            // Generative Interface (RFC-075)
            interface::process_goal,
            interface::list_providers,
            interface::interface_demo,
            // Block Actions (RFC-080)
            interface::execute_block_action,
            // Speculative UI Composition (RFC-082)
            interface::predict_composition,
            // Naaru Unified API (RFC-083)
            naaru::naaru_process,
            naaru::naaru_subscribe,
            naaru::naaru_convergence,
            naaru::naaru_cancel,
            // Self-Knowledge (RFC-085)
            self_knowledge::self_get_module_source,
            self_knowledge::self_find_symbol,
            self_knowledge::self_list_modules,
            self_knowledge::self_search_source,
            self_knowledge::self_get_patterns,
            self_knowledge::self_get_failures,
            self_knowledge::self_list_proposals,
            self_knowledge::self_get_proposal,
            self_knowledge::self_test_proposal,
            self_knowledge::self_approve_proposal,
            self_knowledge::self_apply_proposal,
            self_knowledge::self_rollback_proposal,
            self_knowledge::self_get_summary,
            // Workflow Execution (RFC-086)
            workflow::route_workflow_intent,
            workflow::start_workflow,
            workflow::stop_workflow,
            workflow::resume_workflow,
            workflow::skip_workflow_step,
            workflow::list_workflow_chains,
            workflow::list_active_workflows,
            // Writer Environment (RFC-086)
            writer::detect_diataxis,
            writer::validate_document,
            writer::get_lens_skills,
            writer::execute_skill,
            writer::fix_all_issues,
            // Skill Graph (RFC-087)
            writer::get_skill_graph,
            writer::get_skill_execution_plan,
            writer::get_skill_cache_stats,
            writer::clear_skill_cache,
            // Security-First Execution (RFC-089)
            security::analyze_dag_permissions,
            security::submit_security_approval,
            security::get_audit_log,
            security::verify_audit_integrity,
            security::scan_for_security_issues,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
