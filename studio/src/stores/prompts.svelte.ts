/**
 * Saved Prompts Store (Svelte 5 runes)
 */

import type { SavedPrompt } from '$lib/types';

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

let _list = $state<SavedPrompt[]>([]);
let _isLoading = $state(false);

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const prompts = {
  get list() { return _list; },
  get isLoading() { return _isLoading; },
};

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

export async function loadPrompts(): Promise<void> {
  // Prevent concurrent loads
  if (_isLoading) return;
  
  _isLoading = true;
  try {
    const { invoke } = await import('@tauri-apps/api/core');
    _list = await invoke<SavedPrompt[]>('get_saved_prompts');
  } catch (e) {
    console.error('Failed to load saved prompts:', e);
    _list = [];
  } finally {
    _isLoading = false;
  }
}

export async function savePrompt(prompt: string): Promise<void> {
  try {
    const { invoke } = await import('@tauri-apps/api/core');
    await invoke('save_prompt', { prompt });
    await loadPrompts();
  } catch (e) {
    console.error('Failed to save prompt:', e);
  }
}

export async function removePrompt(prompt: string): Promise<void> {
  try {
    const { invoke } = await import('@tauri-apps/api/core');
    await invoke('remove_saved_prompt', { prompt });
    await loadPrompts();
  } catch (e) {
    console.error('Failed to remove prompt:', e);
  }
}
