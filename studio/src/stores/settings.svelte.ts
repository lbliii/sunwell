/**
 * Settings Store — manages user preferences including model provider (RFC-Cloud-Model-Parity)
 */

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export type ModelProvider = 'ollama' | 'openai' | 'anthropic';

export interface Settings {
  /** Default model provider for agent execution */
  provider: ModelProvider;
  /** Whether to auto-detect lens based on goal */
  autoLens: boolean;
}

// ═══════════════════════════════════════════════════════════════
// STORAGE
// ═══════════════════════════════════════════════════════════════

const STORAGE_KEY = 'sunwell_settings';

function loadSettings(): Settings {
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        return {
          provider: parsed.provider ?? 'ollama',
          autoLens: parsed.autoLens ?? true,
        };
      }
    }
  } catch (e) {
    console.warn('Failed to load settings:', e);
  }
  return { provider: 'ollama', autoLens: true };
}

function saveSettings(settings: Settings): void {
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    }
  } catch (e) {
    console.warn('Failed to save settings:', e);
  }
}

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

let _settings = $state<Settings>(loadSettings());

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const settings = {
  get provider() { return _settings.provider; },
  get autoLens() { return _settings.autoLens; },
};

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Set the model provider.
 */
export function setProvider(provider: ModelProvider): void {
  _settings = { ..._settings, provider };
  saveSettings(_settings);
}

/**
 * Set auto-lens preference.
 */
export function setAutoLens(enabled: boolean): void {
  _settings = { ..._settings, autoLens: enabled };
  saveSettings(_settings);
}

/**
 * Get provider for a specific run (returns null to use config default).
 */
export function getRunProvider(): string | null {
  // If provider is ollama (default), return null to use config defaults
  // Otherwise return the explicit provider
  return _settings.provider === 'ollama' ? null : _settings.provider;
}
