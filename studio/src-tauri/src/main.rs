//! Sunwell Studio — Tauri Application Entry Point
//!
//! A minimal, beautiful GUI for AI-native creative work.
//! Communicates with the Sunwell Python agent via subprocess streaming.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod agent;
mod briefing;
mod commands;
mod dag;
mod heuristic_detect;
mod interface;
mod lens;
mod memory;
mod preview;
mod project;
mod run_analysis;
mod surface;
mod weakness;
mod weakness_types;
mod workspace;

use commands::AppState;
use tauri::Manager;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(AppState::default())
        .setup(|app| {
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
            // DAG / Pipeline view (RFC-056)
            dag::get_project_dag,
            dag::execute_dag_node,
            dag::refresh_backlog,
            // Incremental Execution (RFC-074)
            dag::get_incremental_plan,
            dag::get_cache_stats,
            dag::get_artifact_impact,
            dag::clear_cache,
            // Memory / Simulacrum (RFC-013, RFC-014)
            memory::get_memory_stats,
            memory::list_sessions,
            memory::get_intelligence,
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
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
