/**
 * Weakness Store — manages code health analysis and cascade execution (Svelte 5 runes)
 *
 * RFC-063: Weakness Cascade
 */

import { apiPost } from '$lib/socket';
import type {
  WeaknessReport,
  WeaknessScore,
  CascadePreview,
  CascadeExecution,
  WaveConfidence,
} from '$lib/types/weakness';

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

let _report = $state<WeaknessReport | null>(null);
let _selectedWeakness = $state<WeaknessScore | null>(null);
let _cascadePreview = $state<CascadePreview | null>(null);
let _execution = $state<CascadeExecution | null>(null);
let _isScanning = $state<boolean>(false);
let _isPreviewing = $state<boolean>(false);
let _isExecuting = $state<boolean>(false);
let _error = $state<string | null>(null);

// ═══════════════════════════════════════════════════════════════
// COMPUTED HELPERS
// ═══════════════════════════════════════════════════════════════

function getWeaknessMap(): Map<string, WeaknessScore> {
  const map = new Map<string, WeaknessScore>();
  if (_report) {
    const weaknesses = _report.weaknesses;
    if (Array.isArray(weaknesses)) {
      for (const w of weaknesses) {
        map.set(w.artifact_id, w);
      }
    }
  }
  return map;
}

function getTopWeaknesses(limit: number = 5): WeaknessScore[] {
  if (!_report) return [];
  return _report.weaknesses.slice(0, limit);
}

function getCriticalWeaknesses(): WeaknessScore[] {
  if (!_report) return [];
  return _report.weaknesses.filter((w) => w.cascade_risk === 'critical');
}

function getCurrentWaveConfidence(): WaveConfidence | null {
  if (!_execution || _execution.wave_confidences.length === 0) return null;
  return _execution.wave_confidences[_execution.wave_confidences.length - 1];
}

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const weakness = {
  // Report data
  get report() {
    return _report;
  },
  get selectedWeakness() {
    return _selectedWeakness;
  },
  get cascadePreview() {
    return _cascadePreview;
  },
  get execution() {
    return _execution;
  },

  // Loading states
  get isScanning() {
    return _isScanning;
  },
  get isPreviewing() {
    return _isPreviewing;
  },
  get isExecuting() {
    return _isExecuting;
  },
  get error() {
    return _error;
  },

  // Computed
  get weaknessMap() {
    return getWeaknessMap();
  },
  get topWeaknesses() {
    return getTopWeaknesses();
  },
  get criticalWeaknesses() {
    return getCriticalWeaknesses();
  },
  get currentWaveConfidence() {
    return getCurrentWaveConfidence();
  },

  // Summary stats
  get totalFilesScanned() {
    return _report?.total_files_scanned ?? 0;
  },
  get criticalCount() {
    return _report?.critical_count ?? 0;
  },
  get highCount() {
    return _report?.high_count ?? 0;
  },
  get mediumCount() {
    return _report?.medium_count ?? 0;
  },
  get lowCount() {
    return _report?.low_count ?? 0;
  },
  get hasWeaknesses() {
    return (_report?.weaknesses?.length ?? 0) > 0;
  },
};

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

export async function scanWeaknesses(projectPath: string): Promise<void> {
  // Prevent concurrent scans
  if (_isScanning) return;
  
  _isScanning = true;
  _error = null;

  try {
    // RFC-113: Uses HTTP API instead of Tauri invoke
    const report = await apiPost<WeaknessReport>('/api/weakness/scan', {
      path: projectPath,
    });
    _report = report;
  } catch (e) {
    _error = String(e);
    console.error('Weakness scan failed:', e);
  } finally {
    _isScanning = false;
  }
}

export async function selectWeakness(
  weakness: WeaknessScore | null,
  projectPath: string
): Promise<void> {
  _selectedWeakness = weakness;
  _cascadePreview = null;

  if (weakness) {
    _isPreviewing = true;
    try {
      // RFC-113: Uses HTTP API instead of Tauri invoke
      const preview = await apiPost<CascadePreview>('/api/weakness/preview', {
        path: projectPath,
        artifact_id: weakness.artifact_id,
      });
      _cascadePreview = preview;
    } catch (e) {
      _error = String(e);
      console.error('Cascade preview failed:', e);
    } finally {
      _isPreviewing = false;
    }
  }
}

export async function startExecution(
  projectPath: string,
  artifactId: string,
  autoApprove: boolean = false,
  confidenceThreshold: number = 0.7
): Promise<void> {
  _isExecuting = true;
  _error = null;

  try {
    // RFC-113: Uses HTTP API instead of Tauri invoke
    const execution = await apiPost<CascadeExecution>('/api/weakness/execute', {
      path: projectPath,
      artifact_id: artifactId,
      auto_approve: autoApprove,
      confidence_threshold: confidenceThreshold,
    });
    _execution = execution;
  } catch (e) {
    _error = String(e);
    console.error('Cascade execution failed:', e);
  } finally {
    _isExecuting = false;
  }
}

export async function executeQuickFix(
  projectPath: string,
  artifactId: string,
  autoApprove: boolean = true,
  confidenceThreshold: number = 0.7
): Promise<void> {
  _isExecuting = true;
  _error = null;

  try {
    // RFC-113: Uses HTTP API instead of Tauri invoke
    // Start execution - events will stream via WebSocket
    const execution = await apiPost<CascadeExecution>('/api/weakness/fix', {
      path: projectPath,
      artifact_id: artifactId,
      auto_approve: autoApprove,
      confidence_threshold: confidenceThreshold,
    });

    _execution = execution;

    // Refresh weakness report after completion
    if (execution.completed) {
      await scanWeaknesses(projectPath);
    }
  } catch (e) {
    _error = String(e);
    console.error('Cascade fix failed:', e);
  } finally {
    _isExecuting = false;
  }
}

export function clearSelection(): void {
  _selectedWeakness = null;
  _cascadePreview = null;
  _execution = null;
}

export function clearError(): void {
  _error = null;
}

export function clearAll(): void {
  _report = null;
  _selectedWeakness = null;
  _cascadePreview = null;
  _execution = null;
  _isScanning = false;
  _isPreviewing = false;
  _isExecuting = false;
  _error = null;
}

// Update execution state (called from event listener)
export function updateExecution(execution: CascadeExecution): void {
  _execution = execution;
}
