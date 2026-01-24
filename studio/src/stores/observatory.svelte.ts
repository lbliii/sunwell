/**
 * Observatory Store — aggregates agent events for cinematic visualizations (RFC-112)
 *
 * Consumes events from agent store and transforms them into visualization-ready data.
 */

import { agent } from './agent.svelte';
import type { RefinementRound, PlanCandidate, Task } from '$lib/types';
import { PlanningPhase } from '$lib/constants';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

/** A single resonance iteration for visualization */
export interface ResonanceIteration {
  round: number;
  score: number;
  delta: number;
  improvements: string[];
  improved: boolean;
  reason?: string;
  timestamp?: number;
}

/** Resonance wave visualization state */
export interface ResonanceWaveState {
  iterations: ResonanceIteration[];
  isActive: boolean;
  finalScore: number;
  initialScore: number;
  totalImprovement: number;
  improvementPct: number;
}

/** Playback state for animations */
export interface PlaybackState {
  isPlaying: boolean;
  isPaused: boolean;
  currentRound: number;
  speed: number; // 0.5x, 1x, 2x
  mode: 'live' | 'replay';
}

// ═══════════════════════════════════════════════════════════════
// PRISM FRACTURE TYPES
// ═══════════════════════════════════════════════════════════════

/** A candidate perspective in the prism visualization */
export interface PrismCandidate {
  id: string;
  index: number;
  artifactCount: number;
  score?: number;
  color: string;
  varianceConfig?: {
    promptStyle?: string;
    temperature?: number;
    constraint?: string;
  };
}

/** Prism fracture visualization state */
export interface PrismFractureState {
  candidates: PrismCandidate[];
  winner: PrismCandidate | null;
  selectionReason: string;
  phase: 'idle' | 'generating' | 'scoring' | 'complete';
  totalCandidates: number;
  currentProgress: number;
}

// ═══════════════════════════════════════════════════════════════
// EXECUTION CINEMA TYPES
// ═══════════════════════════════════════════════════════════════

/** Task status for cinema visualization */
export type CinemaTaskStatus = 'pending' | 'active' | 'complete' | 'failed';

/** A task node for execution cinema */
export interface CinemaTask {
  id: string;
  label: string;
  status: CinemaTaskStatus;
  progress: number;
}

/** Execution cinema visualization state */
export interface ExecutionCinemaState {
  tasks: CinemaTask[];
  currentTaskIndex: number;
  totalTasks: number;
  completedTasks: number;
  failedTasks: number;
  isExecuting: boolean;
}

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

// Playback controls
let _playback = $state<PlaybackState>({
  isPlaying: false,
  isPaused: false,
  currentRound: 0,
  speed: 1,
  mode: 'live',
});

// Event history for replay (stores snapshots)
let _eventHistory = $state<ResonanceIteration[]>([]);

// ═══════════════════════════════════════════════════════════════
// COMPUTED STATE (derives from agent store)
// ═══════════════════════════════════════════════════════════════

// Color palette for prism candidates
const PRISM_COLORS = [
  '#3b82f6', // blue
  '#ef4444', // red
  '#22c55e', // green
  '#a855f7', // purple
  '#f97316', // orange
  '#06b6d4', // cyan
  '#ec4899', // pink
  '#eab308', // yellow
];

/**
 * Transform agent planning candidates into prism visualization
 */
function transformCandidates(candidates: PlanCandidate[]): PrismCandidate[] {
  return candidates.map((c, index) => ({
    id: c.id,
    index,
    artifactCount: c.artifact_count,
    score: c.score,
    color: PRISM_COLORS[index % PRISM_COLORS.length],
    varianceConfig: c.variance_config ? {
      promptStyle: c.variance_config.prompt_style,
      temperature: c.variance_config.temperature,
      constraint: c.variance_config.constraint,
    } : undefined,
  }));
}

/**
 * Transform agent tasks into cinema tasks
 */
function transformTasks(tasks: Task[]): CinemaTask[] {
  return tasks.map(t => ({
    id: t.id,
    label: t.description,
    status: t.status === 'running' ? 'active' : t.status as CinemaTaskStatus,
    progress: t.progress / 100, // normalize to 0-1
  }));
}

/**
 * Transform agent refinement rounds into resonance iterations
 */
function transformRounds(rounds: RefinementRound[]): ResonanceIteration[] {
  if (rounds.length === 0) return [];

  return rounds.map((round, index) => {
    const prevScore = index === 0 ? round.current_score : (rounds[index - 1].new_score ?? rounds[index - 1].current_score);
    const currentScore = round.new_score ?? round.current_score;
    const delta = round.improvement ?? (currentScore - prevScore);

    // Parse improvements from the string format
    const improvements: string[] = [];
    if (round.improvements_identified) {
      // Split by semicolon or newline
      improvements.push(...round.improvements_identified.split(/[;\n]/).map(s => s.trim()).filter(Boolean));
    }
    if (round.improvements_applied) {
      improvements.push(...round.improvements_applied);
    }

    return {
      round: round.round,
      score: currentScore,
      delta,
      improvements: [...new Set(improvements)], // dedupe
      improved: round.improved,
      reason: round.reason,
    };
  });
}

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const observatory = {
  // Playback state
  get playback() {
    return _playback;
  },

  // Event history
  get eventHistory() {
    return _eventHistory;
  },

  // Resonance wave state (derived from agent store)
  get resonanceWave(): ResonanceWaveState {
    const rounds = agent.refinementRounds;
    const iterations = transformRounds(rounds);

    if (iterations.length === 0) {
      return {
        iterations: [],
        isActive: false,
        finalScore: 0,
        initialScore: 0,
        totalImprovement: 0,
        improvementPct: 0,
      };
    }

    const initialScore = iterations[0].score - iterations[0].delta;
    const finalScore = iterations[iterations.length - 1].score;
    const totalImprovement = finalScore - initialScore;
    const improvementPct = initialScore > 0 ? ((finalScore / initialScore) - 1) * 100 : 0;

    return {
      iterations,
      isActive: agent.status === 'planning' && (agent.planningProgress?.phase === 'refining'),
      finalScore,
      initialScore,
      totalImprovement,
      improvementPct,
    };
  },

  // Is resonance currently happening?
  get isRefining() {
    return agent.planningProgress?.phase === 'refining';
  },

  // Current iteration being visualized
  get currentIteration(): ResonanceIteration | null {
    const iterations = this.resonanceWave.iterations;
    if (iterations.length === 0) return null;
    
    if (_playback.mode === 'replay') {
      return iterations[Math.min(_playback.currentRound, iterations.length - 1)] ?? null;
    }
    
    // In live mode, show the latest
    return iterations[iterations.length - 1];
  },
};

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/** Start playback animation */
export function startPlayback(): void {
  _playback = {
    ..._playback,
    isPlaying: true,
    isPaused: false,
    currentRound: 0,
    mode: 'replay',
  };
}

/** Pause playback */
export function pausePlayback(): void {
  _playback = {
    ..._playback,
    isPaused: true,
  };
}

/** Resume playback */
export function resumePlayback(): void {
  _playback = {
    ..._playback,
    isPaused: false,
  };
}

/** Stop playback and return to live mode */
export function stopPlayback(): void {
  _playback = {
    ..._playback,
    isPlaying: false,
    isPaused: false,
    mode: 'live',
  };
}

/** Advance to next round */
export function nextRound(): void {
  const maxRound = observatory.resonanceWave.iterations.length - 1;
  if (_playback.currentRound < maxRound) {
    _playback = {
      ..._playback,
      currentRound: _playback.currentRound + 1,
    };
  } else {
    // End of playback
    _playback = {
      ..._playback,
      isPlaying: false,
    };
  }
}

/** Go to previous round */
export function prevRound(): void {
  if (_playback.currentRound > 0) {
    _playback = {
      ..._playback,
      currentRound: _playback.currentRound - 1,
    };
  }
}

/** Scrub to specific round */
export function scrubToRound(round: number): void {
  const maxRound = observatory.resonanceWave.iterations.length - 1;
  _playback = {
    ..._playback,
    currentRound: Math.max(0, Math.min(round, maxRound)),
    mode: 'replay',
  };
}

/** Set playback speed */
export function setPlaybackSpeed(speed: number): void {
  _playback = {
    ..._playback,
    speed: Math.max(0.25, Math.min(4, speed)),
  };
}

/** Switch to live mode */
export function goLive(): void {
  _playback = {
    ..._playback,
    isPlaying: false,
    isPaused: false,
    mode: 'live',
  };
}

/** Save current event state to history (for replay) */
export function snapshotHistory(): void {
  _eventHistory = [...observatory.resonanceWave.iterations];
}

/** Clear event history */
export function clearHistory(): void {
  _eventHistory = [];
  _playback = {
    isPlaying: false,
    isPaused: false,
    currentRound: 0,
    speed: 1,
    mode: 'live',
  };
}

// ═══════════════════════════════════════════════════════════════
// DEMO DATA (for testing without live agent)
// ═══════════════════════════════════════════════════════════════

/** Demo iterations for testing/preview */
export const DEMO_ITERATIONS: ResonanceIteration[] = [
  { round: 0, score: 1.0, delta: 0, improvements: [], improved: false },
  { round: 1, score: 3.2, delta: 2.2, improvements: ['type hints'], improved: true },
  { round: 2, score: 5.5, delta: 2.3, improvements: ['docstring'], improved: true },
  { round: 3, score: 7.8, delta: 2.3, improvements: ['error handling'], improved: true },
  { round: 4, score: 8.5, delta: 0.7, improvements: ['polish'], improved: true, reason: 'Diminishing returns' },
];

/** Load demo data for preview mode */
export function loadDemoData(): void {
  _eventHistory = DEMO_ITERATIONS;
  _playback = {
    isPlaying: false,
    isPaused: false,
    currentRound: 0,
    speed: 1,
    mode: 'replay',
  };
}
