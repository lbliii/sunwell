//! Sunwell Studio — Tauri Application Entry Point
//!
//! A minimal, beautiful GUI for AI-native creative work.
//! Communicates with the Sunwell Python agent via subprocess streaming.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod agent;
mod commands;
mod dag;
mod memory;
mod preview;
mod project;
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
            // Memory / Simulacrum (RFC-013, RFC-014)
            memory::get_memory_stats,
            memory::list_sessions,
            memory::get_intelligence,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
