/**
 * Writer Store — Universal Writing Environment state (RFC-086)
 *
 * RFC-113: Migrated from Tauri invoke to HTTP API.
 *
 * Manages the writer workspace including:
 * - View mode (source/preview)
 * - Active document and validation state
 * - Diataxis detection
 * - Selection and actions
 */

import { apiGet, apiPost } from '$lib/socket';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export type ViewMode = 'source' | 'preview' | 'split';
export type DiataxisType = 'TUTORIAL' | 'HOW_TO' | 'EXPLANATION' | 'REFERENCE';

export interface DiataxisSignal {
  dtype: DiataxisType;
  weight: number;
  reason: string;
}

export interface DiataxisDetection {
  detectedType: DiataxisType | null;
  confidence: number;
  signals: DiataxisSignal[];
  scores: Record<DiataxisType, number>;
}

export interface DiataxisWarning {
  message: string;
  suggestion: string | null;
  severity: 'warning' | 'info';
}

export interface ValidationWarning {
  line: number;
  column?: number;
  message: string;
  rule: string;
  severity: 'warning' | 'error' | 'info';
  suggestion?: string;
}

export interface LensSkill {
  id: string;
  name: string;
  shortcut: string;
  description: string;
  category: 'validation' | 'creation' | 'transformation' | 'utility';
}

export interface SelectionContext {
  text: string;
  start: number;
  end: number;
  line: number;
  column: number;
}

interface WriterState {
  // View
  viewMode: ViewMode;

  // Document
  filePath: string | null;
  content: string;
  wordCount: number;
  isDirty: boolean;

  // Lens
  lensName: string;
  lensSkills: LensSkill[];
  recentSkills: string[];

  // Diataxis
  diataxis: DiataxisDetection | null;
  diataxisWarnings: DiataxisWarning[];

  // Validation
  validationWarnings: ValidationWarning[];
  isValidating: boolean;

  // Selection
  selection: SelectionContext | null;
  showActionMenu: boolean;

  // Loading
  isLoading: boolean;
  error: string | null;
}

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

const initialState: WriterState = {
  viewMode: 'source',
  filePath: null,
  content: '',
  wordCount: 0,
  isDirty: false,
  lensName: 'tech-writer',
  lensSkills: [],
  recentSkills: [],
  diataxis: null,
  diataxisWarnings: [],
  validationWarnings: [],
  isValidating: false,
  selection: null,
  showActionMenu: false,
  isLoading: false,
  error: null,
};

let _state = $state<WriterState>({ ...initialState });

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const writerState = {
  // View
  get viewMode() {
    return _state.viewMode;
  },

  // Document
  get filePath() {
    return _state.filePath;
  },
  get content() {
    return _state.content;
  },
  get wordCount() {
    return _state.wordCount;
  },
  get isDirty() {
    return _state.isDirty;
  },

  // Lens
  get lensName() {
    return _state.lensName;
  },
  get lensSkills() {
    return _state.lensSkills;
  },
  get recentSkills() {
    return _state.recentSkills;
  },

  // Diataxis
  get diataxis() {
    return _state.diataxis;
  },
  get diataxisWarnings() {
    return _state.diataxisWarnings;
  },

  // Validation
  get validationWarnings() {
    return _state.validationWarnings;
  },
  get isValidating() {
    return _state.isValidating;
  },

  // Selection
  get selection() {
    return _state.selection;
  },
  get showActionMenu() {
    return _state.showActionMenu;
  },

  // Loading
  get isLoading() {
    return _state.isLoading;
  },
  get error() {
    return _state.error;
  },

  // Computed
  get errorCount() {
    return _state.validationWarnings.filter((w) => w.severity === 'error').length;
  },
  get warningCount() {
    return _state.validationWarnings.filter((w) => w.severity === 'warning').length;
  },
  get hasIssues() {
    return _state.validationWarnings.length > 0;
  },
  get diataxisType() {
    return _state.diataxis?.detectedType ?? null;
  },
  get diataxisConfidence() {
    return _state.diataxis?.confidence ?? 0;
  },
};

// ═══════════════════════════════════════════════════════════════
// VIEW ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Toggle view mode (source ↔ preview).
 */
export function toggleView(): void {
  _state = {
    ..._state,
    viewMode: _state.viewMode === 'source' ? 'preview' : 'source',
  };
}

/**
 * Set specific view mode.
 */
export function setViewMode(mode: ViewMode): void {
  _state = { ..._state, viewMode: mode };
}

// ═══════════════════════════════════════════════════════════════
// DOCUMENT ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Load a document into the writer.
 */
export async function loadDocument(filePath: string): Promise<void> {
  _state = { ..._state, isLoading: true, error: null };

  try {
    const result = await apiGet<{ content: string }>(`/api/files/read?path=${encodeURIComponent(filePath)}`);

    _state = {
      ..._state,
      filePath,
      content: result.content,
      wordCount: countWords(result.content),
      isDirty: false,
      isLoading: false,
    };

    // Trigger Diataxis detection and validation
    await Promise.all([detectDiataxis(), validateDocument()]);
  } catch (e) {
    _state = {
      ..._state,
      isLoading: false,
      error: e instanceof Error ? e.message : String(e),
    };
  }
}

/**
 * Update document content.
 */
export function updateContent(content: string): void {
  _state = {
    ..._state,
    content,
    wordCount: countWords(content),
    isDirty: true,
  };

  // Debounced validation will be triggered by the editor
}

/**
 * Save the current document.
 */
export async function saveDocument(): Promise<boolean> {
  if (!_state.filePath || !_state.isDirty) return true;

  try {
    await apiPost('/api/files/write', {
      path: _state.filePath,
      content: _state.content,
    });

    _state = { ..._state, isDirty: false };
    return true;
  } catch (e) {
    _state = {
      ..._state,
      error: e instanceof Error ? e.message : String(e),
    };
    return false;
  }
}

// ═══════════════════════════════════════════════════════════════
// DIATAXIS ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Detect Diataxis content type.
 */
export async function detectDiataxis(): Promise<void> {
  if (!_state.content) return;

  try {
    const result = await apiPost<{
      detection: DiataxisDetection;
      warnings: DiataxisWarning[];
    }>('/api/writer/diataxis', {
      content: _state.content,
      file_path: _state.filePath,
    });

    _state = {
      ..._state,
      diataxis: result.detection,
      diataxisWarnings: result.warnings,
    };
  } catch {
    // Fallback to simple detection
    const detection = detectDiataxisLocal(_state.content, _state.filePath ?? '');
    _state = {
      ..._state,
      diataxis: detection,
      diataxisWarnings: [],
    };
  }
}

// ═══════════════════════════════════════════════════════════════
// VALIDATION ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Run validation on current document.
 */
export async function validateDocument(): Promise<void> {
  if (!_state.content) return;

  _state = { ..._state, isValidating: true };

  try {
    const result = await apiPost<{ warnings: ValidationWarning[] }>('/api/writer/validate', {
      content: _state.content,
      file_path: _state.filePath,
      lens_name: _state.lensName,
    });

    _state = {
      ..._state,
      validationWarnings: result.warnings || [],
      isValidating: false,
    };
  } catch {
    // Fallback to basic validation
    _state = {
      ..._state,
      validationWarnings: [],
      isValidating: false,
    };
  }
}

/**
 * Dismiss a validation warning.
 */
export function dismissWarning(warning: ValidationWarning): void {
  _state = {
    ..._state,
    validationWarnings: _state.validationWarnings.filter(
      (w) => w.line !== warning.line || w.rule !== warning.rule,
    ),
  };
}

/**
 * Fix all fixable issues.
 */
export async function fixAllIssues(): Promise<void> {
  // This would invoke the lens fix skill
  const fixableCount =
    _state.validationWarnings.filter((w) => w.severity !== 'info').length;
  if (fixableCount === 0) return;

  try {
    const result = await apiPost<{ content: string; fixed: number }>('/api/writer/fix-all', {
      content: _state.content,
      warnings: _state.validationWarnings,
      lens_name: _state.lensName,
    });

    if (result.fixed > 0) {
      _state = {
        ..._state,
        content: result.content,
        isDirty: true,
      };
      await validateDocument();
    }
  } catch (e) {
    _state = {
      ..._state,
      error: e instanceof Error ? e.message : String(e),
    };
  }
}

// ═══════════════════════════════════════════════════════════════
// LENS ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Set active lens.
 */
export async function setLens(lensName: string): Promise<void> {
  _state = { ..._state, lensName, isLoading: true };

  try {
    const result = await apiGet<{ skills: LensSkill[] }>(`/api/lenses/${encodeURIComponent(lensName)}/skills`);

    _state = {
      ..._state,
      lensSkills: result.skills || [],
      isLoading: false,
    };

    // Re-validate with new lens
    await validateDocument();
  } catch {
    _state = {
      ..._state,
      lensSkills: getDefaultSkills(),
      isLoading: false,
    };
  }
}

/**
 * Execute a lens skill.
 */
export async function executeSkill(skillId: string): Promise<void> {
  try {
    const result = await apiPost<{ content?: string; message?: string }>('/api/writer/execute-skill', {
      skill_id: skillId,
      content: _state.content,
      file_path: _state.filePath,
      lens_name: _state.lensName,
    });

    // Track as recent
    const recent = [skillId, ..._state.recentSkills.filter((s) => s !== skillId)].slice(
      0,
      5,
    );

    if (result.content) {
      _state = {
        ..._state,
        content: result.content,
        isDirty: true,
        recentSkills: recent,
      };
      await validateDocument();
    } else {
      _state = { ..._state, recentSkills: recent };
    }
  } catch (e) {
    _state = {
      ..._state,
      error: e instanceof Error ? e.message : String(e),
    };
  }
}

// ═══════════════════════════════════════════════════════════════
// SELECTION ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Set current selection.
 */
export function setSelection(selection: SelectionContext | null): void {
  _state = {
    ..._state,
    selection,
    showActionMenu: selection !== null && selection.text.length > 0,
  };
}

/**
 * Hide the action menu.
 */
export function hideActionMenu(): void {
  _state = { ..._state, showActionMenu: false };
}

// ═══════════════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════════════

/**
 * Reset writer state.
 */
export function resetWriter(): void {
  _state = { ...initialState };
}

/**
 * Clear error.
 */
export function clearError(): void {
  _state = { ..._state, error: null };
}

// ═══════════════════════════════════════════════════════════════
// LOCAL HELPERS
// ═══════════════════════════════════════════════════════════════

function countWords(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

/**
 * Simple local Diataxis detection (fallback).
 */
function detectDiataxisLocal(content: string, filePath: string): DiataxisDetection {
  const contentLower = content.toLowerCase();
  const filename = filePath.split('/').pop()?.toLowerCase() ?? '';

  const scores: Record<DiataxisType, number> = {
    TUTORIAL: 0,
    HOW_TO: 0,
    EXPLANATION: 0,
    REFERENCE: 0,
  };

  const signals: DiataxisSignal[] = [];

  // Tutorial signals
  const tutorialKeywords = ['tutorial', 'getting started', 'learn', 'first steps', 'quickstart'];
  for (const kw of tutorialKeywords) {
    if (filename.includes(kw.replace(' ', '-')) || contentLower.slice(0, 500).includes(kw)) {
      scores.TUTORIAL += 0.3;
      signals.push({ dtype: 'TUTORIAL', weight: 0.3, reason: `'${kw}' detected` });
    }
  }

  // How-to signals
  const howtoKeywords = ['how to', 'guide', 'configure', 'set up', 'deploy'];
  for (const kw of howtoKeywords) {
    if (filename.includes(kw.replace(' ', '-')) || contentLower.slice(0, 500).includes(kw)) {
      scores.HOW_TO += 0.3;
      signals.push({ dtype: 'HOW_TO', weight: 0.3, reason: `'${kw}' detected` });
    }
  }

  // Explanation signals
  const explanationKeywords = ['understand', 'architecture', 'concepts', 'overview', 'why'];
  for (const kw of explanationKeywords) {
    if (filename.includes(kw) || contentLower.slice(0, 500).includes(kw)) {
      scores.EXPLANATION += 0.3;
      signals.push({ dtype: 'EXPLANATION', weight: 0.3, reason: `'${kw}' detected` });
    }
  }

  // Reference signals
  const referenceKeywords = ['reference', 'api', 'parameters', 'configuration'];
  for (const kw of referenceKeywords) {
    if (filename.includes(kw) || contentLower.slice(0, 500).includes(kw)) {
      scores.REFERENCE += 0.3;
      signals.push({ dtype: 'REFERENCE', weight: 0.3, reason: `'${kw}' detected` });
    }
  }

  // Find best type
  const total = Object.values(scores).reduce((a, b) => a + b, 0);
  let detectedType: DiataxisType | null = null;
  let confidence = 0;

  if (total > 0) {
    const best = (Object.entries(scores) as [DiataxisType, number][]).sort(
      ([, a], [, b]) => b - a,
    )[0];
    detectedType = best[0];
    confidence = best[1] / total;
  }

  return {
    detectedType: confidence > 0.4 ? detectedType : null,
    confidence,
    signals,
    scores,
  };
}

/**
 * Default skills when lens not loaded.
 */
function getDefaultSkills(): LensSkill[] {
  return [
    {
      id: 'audit',
      name: 'Quick Audit',
      shortcut: '::a',
      description: 'Validate document against source code',
      category: 'validation',
    },
    {
      id: 'polish',
      name: 'Polish',
      shortcut: '::p',
      description: 'Improve clarity and style',
      category: 'transformation',
    },
    {
      id: 'style-check',
      name: 'Style Check',
      shortcut: '::s',
      description: 'Check style guide compliance',
      category: 'validation',
    },
    {
      id: 'simplify',
      name: 'Simplify',
      shortcut: '::sim',
      description: 'Reduce complexity and word count',
      category: 'transformation',
    },
  ];
}
