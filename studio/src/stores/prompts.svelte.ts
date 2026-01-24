/**
 * Saved Prompts Store (Svelte 5 runes)
 *
 * RFC-113: Migrated from Tauri invoke to HTTP API.
 */

import type { SavedPrompt } from '$lib/types';
import { apiGet, apiPost } from '$lib/socket';

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
    const result = await apiGet<{ prompts: SavedPrompt[] }>('/api/prompts');
    _list = result.prompts || [];
  } catch (e) {
    console.error('Failed to load saved prompts:', e);
    _list = [];
  } finally {
    _isLoading = false;
  }
}

export async function savePrompt(prompt: string): Promise<void> {
  try {
    await apiPost('/api/prompts', { prompt });
    await loadPrompts();
  } catch (e) {
    console.error('Failed to save prompt:', e);
  }
}

export async function removePrompt(prompt: string): Promise<void> {
  try {
    await apiPost('/api/prompts/remove', { prompt });
    await loadPrompts();
  } catch (e) {
    console.error('Failed to remove prompt:', e);
  }
}
