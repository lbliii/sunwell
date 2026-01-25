/**
 * Skill Graph Store (RFC-087)
 *
 * Manages skill DAG state for visualization and execution tracking.
 * Populated by skill_* events from the Python agent.
 */

import type {
  SkillGraphResolvedData,
  SkillWaveStartData,
  SkillWaveCompleteData,
  SkillCacheHitData,
  SkillExecuteStartData,
  SkillExecuteCompleteData,
} from '$lib/agent-events';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical' | null;

export interface SkillNode {
  name: string;
  status: 'pending' | 'running' | 'complete' | 'cached' | 'failed';
  waveIndex: number;
  durationMs?: number;
  error?: string;
  cached: boolean;
  // RFC-089: Security metadata
  riskLevel: RiskLevel;
  hasPermissions: boolean;
  violationsDetected: number;
}

export interface SkillWave {
  index: number;
  skills: string[];
  status: 'pending' | 'running' | 'complete';
  durationMs?: number;
  succeeded: string[];
  failed: string[];
}

export interface SkillGraphState {
  lensName: string | null;
  contentHash: string | null;
  skillCount: number;
  waveCount: number;
  skills: Map<string, SkillNode>;
  waves: SkillWave[];
  currentWave: number;
  isExecuting: boolean;
  cacheHits: number;
  cacheSavedMs: number;
  // RFC-089: Security tracking
  totalViolations: number;
  highRiskSkills: number;
}

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

const initialState: SkillGraphState = {
  lensName: null,
  contentHash: null,
  skillCount: 0,
  waveCount: 0,
  skills: new Map(),
  waves: [],
  currentWave: -1,
  isExecuting: false,
  cacheHits: 0,
  cacheSavedMs: 0,
  totalViolations: 0,
  highRiskSkills: 0,
};

let _state = $state<SkillGraphState>({ ...initialState });

// ═══════════════════════════════════════════════════════════════
// EXPORTED STATE (Read-Only)
// ═══════════════════════════════════════════════════════════════

export const skillGraphState = {
  get lensName() { return _state.lensName; },
  get contentHash() { return _state.contentHash; },
  get skillCount() { return _state.skillCount; },
  get waveCount() { return _state.waveCount; },
  get skills() { return _state.skills; },
  get waves() { return _state.waves; },
  get currentWave() { return _state.currentWave; },
  get isExecuting() { return _state.isExecuting; },
  get cacheHits() { return _state.cacheHits; },
  get cacheSavedMs() { return _state.cacheSavedMs; },
  get totalViolations() { return _state.totalViolations; },
  get highRiskSkills() { return _state.highRiskSkills; },

  /** Progress as percentage (0-100). */
  get progress(): number {
    if (_state.skillCount === 0) return 0;
    let completed = 0;
    const skills = _state.skills;
    // Defensive: ensure skills is a Map before iterating
    if (!(skills instanceof Map)) return 0;
    for (const skill of skills.values()) {
      if (skill.status === 'complete' || skill.status === 'cached') {
        completed++;
      }
    }
    return Math.round((completed / _state.skillCount) * 100);
  },

  /** Cache hit rate (0-100). */
  get cacheHitRate(): number {
    if (_state.skillCount === 0) return 0;
    return Math.round((_state.cacheHits / _state.skillCount) * 100);
  },

  /** Whether there are security concerns. */
  get hasSecurityConcerns(): boolean {
    return _state.totalViolations > 0 || _state.highRiskSkills > 0;
  },
};

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

export function handleSkillGraphResolved(data: SkillGraphResolvedData): void {
  _state = {
    ...initialState,
    lensName: data.lens_name,
    contentHash: data.content_hash,
    skillCount: data.skill_count,
    waveCount: data.wave_count,
    isExecuting: true,
  };
}

export function handleSkillWaveStart(data: SkillWaveStartData): void {
  const skills = Array.isArray(data.skills) ? data.skills : [];
  const wave: SkillWave = {
    index: data.wave_index,
    skills: [...skills],
    status: 'running',
    succeeded: [],
    failed: [],
  };

  // Initialize skill nodes for this wave
  const newSkills = new Map(_state.skills);
  for (const skillName of skills) {
    newSkills.set(skillName, {
      name: skillName,
      status: 'running',
      waveIndex: data.wave_index,
      cached: false,
      riskLevel: null,
      hasPermissions: false,
      violationsDetected: 0,
    });
  }

  const waves = _state.waves;
  const newWaves = Array.isArray(waves) ? [...waves, wave] : [wave];

  _state = {
    ..._state,
    skills: newSkills,
    waves: newWaves,
    currentWave: data.wave_index,
  };
}

export function handleSkillWaveComplete(data: SkillWaveCompleteData): void {
  const waves = _state.waves;
  if (!Array.isArray(waves)) return;
  
  const newWaves = waves.map(w =>
    w.index === data.wave_index
      ? {
          ...w,
          status: 'complete' as const,
          durationMs: data.duration_ms,
          succeeded: [...data.succeeded],  // Convert readonly to mutable
          failed: [...data.failed],        // Convert readonly to mutable
        }
      : w
  );

  _state = {
    ..._state,
    waves: newWaves,
    isExecuting: data.wave_index < _state.waveCount - 1,
  };
}

export function handleSkillCacheHit(data: SkillCacheHitData): void {
  const newSkills = new Map(_state.skills);
  const existing = newSkills.get(data.skill_name);
  if (existing) {
    newSkills.set(data.skill_name, {
      ...existing,
      status: 'cached',
      cached: true,
      durationMs: data.saved_ms,
      // Cached skills retain their risk info
    });
  }

  _state = {
    ..._state,
    skills: newSkills,
    cacheHits: _state.cacheHits + 1,
    cacheSavedMs: _state.cacheSavedMs + data.saved_ms,
  };
}

export function handleSkillExecuteStart(data: SkillExecuteStartData): void {
  const riskLevel = (data.risk_level ?? null) as RiskLevel;
  const isHighRisk = riskLevel === 'high' || riskLevel === 'critical';

  const newSkills = new Map(_state.skills);
  newSkills.set(data.skill_name, {
    name: data.skill_name,
    status: 'running',
    waveIndex: data.wave_index,
    cached: false,
    riskLevel,
    hasPermissions: data.has_permissions ?? false,
    violationsDetected: 0,
  });

  _state = {
    ..._state,
    skills: newSkills,
    highRiskSkills: isHighRisk ? _state.highRiskSkills + 1 : _state.highRiskSkills,
  };
}

export function handleSkillExecuteComplete(data: SkillExecuteCompleteData): void {
  const newSkills = new Map(_state.skills);
  const existing = newSkills.get(data.skill_name);
  const riskLevel = (data.risk_level ?? existing?.riskLevel ?? null) as RiskLevel;
  const violations = data.violations_detected ?? 0;

  newSkills.set(data.skill_name, {
    name: data.skill_name,
    status: data.success ? (data.cached ? 'cached' : 'complete') : 'failed',
    waveIndex: existing?.waveIndex ?? 0,
    durationMs: data.duration_ms,
    error: data.error ?? undefined,
    cached: data.cached,
    riskLevel,
    hasPermissions: existing?.hasPermissions ?? false,
    violationsDetected: violations,
  });

  _state = {
    ..._state,
    skills: newSkills,
    totalViolations: _state.totalViolations + violations,
  };
}

export function resetSkillGraph(): void {
  _state = { ...initialState };
}

// ═══════════════════════════════════════════════════════════════
// DERIVED HELPERS
// ═══════════════════════════════════════════════════════════════

/**
 * Get skill nodes grouped by wave for visualization.
 */
export function getWavesWithSkills(): Array<{
  wave: SkillWave;
  skills: SkillNode[];
}> {
  const waves = _state.waves;
  const skills = _state.skills;
  if (!Array.isArray(waves)) return [];
  if (!(skills instanceof Map)) {
    return waves.map(wave => ({ wave, skills: [] }));
  }
  return waves.map(wave => ({
    wave,
    skills: (Array.isArray(wave.skills) ? wave.skills : [])
      .map(name => skills.get(name))
      .filter((s): s is SkillNode => s !== undefined),
  }));
}

/**
 * Get count of skills by status.
 */
export function getStatusCounts(): Record<SkillNode['status'], number> {
  const counts: Record<SkillNode['status'], number> = {
    pending: 0,
    running: 0,
    complete: 0,
    cached: 0,
    failed: 0,
  };

  const skills = _state.skills;
  if (!(skills instanceof Map)) return counts;

  for (const skill of skills.values()) {
    counts[skill.status]++;
  }

  return counts;
}

/**
 * Get count of skills by risk level.
 */
export function getRiskCounts(): Record<'low' | 'medium' | 'high' | 'critical' | 'none', number> {
  const counts: Record<'low' | 'medium' | 'high' | 'critical' | 'none', number> = {
    low: 0,
    medium: 0,
    high: 0,
    critical: 0,
    none: 0,
  };

  const skills = _state.skills;
  if (!(skills instanceof Map)) return counts;

  for (const skill of skills.values()) {
    counts[skill.riskLevel ?? 'none']++;
  }

  return counts;
}
