//! Sunwell Studio — Tauri Application Entry Point
//!
//! A minimal, beautiful GUI for AI-native creative work.
//! Communicates with the Sunwell Python agent via subprocess streaming.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod agent;
mod commands;
mod preview;
mod project;

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
            commands::run_goal,
            commands::stop_agent,
            commands::get_recent_projects,
            commands::open_project,
            commands::get_project_info,
            commands::launch_preview,
            commands::stop_preview,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
