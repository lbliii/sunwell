/**
 * Observatory Store — aggregates agent events for cinematic visualizations (RFC-112)
 *
 * Consumes events from agent store and transforms them into visualization-ready data.
 */

import { agent } from './agent.svelte';
import { evaluation } from './evaluation.svelte';
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
// MEMORY LATTICE TYPES
// ═══════════════════════════════════════════════════════════════

/** Node category in the memory lattice */
export type LatticeNodeCategory = 'fact' | 'decision' | 'dead_end' | 'pattern' | 'concept';

/** A node in the memory lattice */
export interface LatticeNode {
  id: string;
  label: string;
  category: LatticeNodeCategory;
  x: number;
  y: number;
  timestamp?: number;
}

/** An edge in the memory lattice */
export interface LatticeEdge {
  source: string;
  target: string;
  relation: string;
}

/** Memory lattice visualization state */
export interface MemoryLatticeState {
  nodes: LatticeNode[];
  edges: LatticeEdge[];
  factCount: number;
  conceptCount: number;
  totalLearnings: number;
}

// ═══════════════════════════════════════════════════════════════
// MODEL PARADOX TYPES
// ═══════════════════════════════════════════════════════════════

/** A model comparison entry for the paradox visualization */
export interface ParadoxComparison {
  model: string;
  params: string;
  cost: string;
  rawScore: number;
  sunwellScore: number;
  improvement: number;
}

/** Model paradox visualization state */
export interface ModelParadoxState {
  thesis: string;
  comparisons: ParadoxComparison[];
  avgImprovement: number;
  sunwellWins: number;
  totalRuns: number;
}

// ═══════════════════════════════════════════════════════════════
// CONVERGENCE LOOP TYPES (RFC-123)
// ═══════════════════════════════════════════════════════════════

/** Gate result for visualization */
export interface ConvergenceGate {
  name: string;
  passed: boolean;
  errorCount: number;
}

/** Single convergence iteration for visualization */
export interface ConvergenceIterationViz {
  iteration: number;
  allPassed: boolean;
  totalErrors: number;
  gates: ConvergenceGate[];
}

/** Convergence visualization state */
export interface ConvergenceVizState {
  status: 'idle' | 'running' | 'stable' | 'escalated' | 'timeout' | 'stuck';
  iterations: ConvergenceIterationViz[];
  maxIterations: number;
  currentIteration: number;
  enabledGates: string[];
  isActive: boolean;
  tokensUsed?: number;
  durationMs?: number;
}

// ═══════════════════════════════════════════════════════════════
// DEMO DATA
// ═══════════════════════════════════════════════════════════════

/** Demo paradox comparisons when no evaluation data available */
const DEMO_PARADOX_COMPARISONS: ParadoxComparison[] = [
  { model: 'claude-sonnet-4-20250514', params: '~70B', cost: '$$', rawScore: 72, sunwellScore: 89, improvement: 23.6 },
  { model: 'gpt-4o-mini', params: '~8B', cost: '$', rawScore: 58, sunwellScore: 81, improvement: 39.7 },
  { model: 'claude-3-5-haiku-20241022', params: '~20B', cost: '$', rawScore: 64, sunwellScore: 85, improvement: 32.8 },
  { model: 'gemini-2.0-flash', params: '~27B', cost: '$', rawScore: 61, sunwellScore: 82, improvement: 34.4 },
];

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
 * Map concept category to lattice node category
 */
function mapConceptCategory(category: string): LatticeNodeCategory {
  switch (category) {
    case 'framework':
    case 'database':
    case 'tool':
      return 'concept';
    case 'testing':
      return 'pattern';
    case 'pattern':
      return 'pattern';
    case 'language':
      return 'fact';
    default:
      return 'fact';
  }
}

/**
 * Get parameter count string for a model
 */
function getModelParams(model: string): string {
  if (model.includes('3b') || model.includes(':3b')) return '3B';
  if (model.includes('7b') || model.includes(':7b')) return '7B';
  if (model.includes('8b') || model.includes(':8b')) return '8B';
  if (model.includes('13b') || model.includes(':13b')) return '13B';
  if (model.includes('20b') || model.includes(':20b')) return '20B';
  if (model.includes('70b') || model.includes(':70b')) return '70B';
  if (model.includes('gpt-4')) return '~1T';
  if (model.includes('gpt-3.5')) return '~175B';
  if (model.includes('claude-3')) return '~200B';
  return '?';
}

/**
 * Get cost string for a model
 */
function getModelCost(model: string): string {
  if (model.includes('llama') || model.includes('qwen') || model.includes('phi')) return '$0';
  if (model.includes('gpt-4')) return '~$30/1M';
  if (model.includes('gpt-3.5')) return '~$2/1M';
  if (model.includes('claude-3-opus')) return '~$75/1M';
  if (model.includes('claude-3-sonnet')) return '~$15/1M';
  return '$0';
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

  // ═══════════════════════════════════════════════════════════════
  // PRISM FRACTURE STATE
  // ═══════════════════════════════════════════════════════════════

  // Prism fracture state (derived from agent store)
  get prismFracture(): PrismFractureState {
    const candidates = transformCandidates(agent.planningCandidates);
    const selected = agent.selectedCandidate;
    const progress = agent.planningProgress;

    // Determine phase
    let phase: PrismFractureState['phase'] = 'idle';
    if (progress) {
      if (progress.phase === PlanningPhase.GENERATING) phase = 'generating';
      else if (progress.phase === PlanningPhase.SCORING) phase = 'scoring';
      else if (progress.phase === PlanningPhase.COMPLETE || selected) phase = 'complete';
    }

    // Find winner
    let winner: PrismCandidate | null = null;
    if (selected) {
      winner = candidates.find(c => c.id === selected.id) ?? null;
    }

    return {
      candidates,
      winner,
      selectionReason: selected?.selection_reason ?? '',
      phase,
      totalCandidates: progress?.total_candidates ?? 0,
      currentProgress: progress?.current_candidates ?? 0,
    };
  },

  // Is prism generation active?
  get isPrismActive() {
    const phase = agent.planningProgress?.phase;
    return phase === PlanningPhase.GENERATING || phase === PlanningPhase.SCORING;
  },

  // ═══════════════════════════════════════════════════════════════
  // EXECUTION CINEMA STATE
  // ═══════════════════════════════════════════════════════════════

  // Execution cinema state (derived from agent store)
  get executionCinema(): ExecutionCinemaState {
    const tasks = transformTasks(agent.tasks);
    const currentIdx = agent.currentTaskIndex;
    
    return {
      tasks,
      currentTaskIndex: currentIdx,
      totalTasks: agent.totalTasks,
      completedTasks: agent.completedTasks,
      failedTasks: agent.failedTasks,
      isExecuting: agent.isRunning,
    };
  },

  // Is execution active?
  get isExecuting() {
    return agent.isRunning;
  },

  // ═══════════════════════════════════════════════════════════════
  // MEMORY LATTICE STATE
  // ═══════════════════════════════════════════════════════════════

  // Memory lattice state (derived from agent store)
  get memoryLattice(): MemoryLatticeState {
    const learnings = agent.learnings;
    const concepts = agent.concepts;

    // Generate nodes from concepts with simple force-directed layout
    const nodes: LatticeNode[] = concepts.map((c, i) => {
      // Simple circular layout with some randomness
      const angle = (i / Math.max(concepts.length, 1)) * 2 * Math.PI;
      const radius = 150 + Math.random() * 50;
      return {
        id: c.id,
        label: c.label,
        category: mapConceptCategory(c.category),
        x: 350 + Math.cos(angle) * radius,
        y: 225 + Math.sin(angle) * radius,
        timestamp: c.timestamp,
      };
    });

    // Generate simple edges between related concepts
    const edges: LatticeEdge[] = [];
    for (let i = 0; i < concepts.length - 1; i++) {
      // Connect sequential concepts
      if (concepts[i].category === concepts[i + 1].category) {
        edges.push({
          source: concepts[i].id,
          target: concepts[i + 1].id,
          relation: 'relates_to',
        });
      }
    }

    return {
      nodes,
      edges,
      factCount: learnings.length,
      conceptCount: concepts.length,
      totalLearnings: learnings.length,
    };
  },

  // Has memory data?
  get hasMemory() {
    return agent.learnings.length > 0 || agent.concepts.length > 0;
  },

  // ═══════════════════════════════════════════════════════════════
  // MODEL PARADOX STATE
  // ═══════════════════════════════════════════════════════════════

  // Model paradox state (derived from evaluation store)
  get modelParadox(): ModelParadoxState {
    const history = evaluation.history;
    const stats = evaluation.stats;

    // Group runs by model and compute averages
    const modelGroups: Map<string, { raw: number[]; sunwell: number[] }> = new Map();
    
    for (const run of history) {
      if (!modelGroups.has(run.model)) {
        modelGroups.set(run.model, { raw: [], sunwell: [] });
      }
      const group = modelGroups.get(run.model)!;
      if (run.single_shot_score) {
        group.raw.push(run.single_shot_score.total);
      }
      if (run.sunwell_score) {
        group.sunwell.push(run.sunwell_score.total);
      }
    }

    // Build comparisons
    const comparisons: ParadoxComparison[] = [];
    for (const [model, group] of modelGroups) {
      if (group.raw.length > 0 && group.sunwell.length > 0) {
        const avgRaw = group.raw.reduce((a, b) => a + b, 0) / group.raw.length;
        const avgSunwell = group.sunwell.reduce((a, b) => a + b, 0) / group.sunwell.length;
        comparisons.push({
          model,
          params: getModelParams(model),
          cost: getModelCost(model),
          rawScore: avgRaw,
          sunwellScore: avgSunwell,
          improvement: avgRaw > 0 ? ((avgSunwell / avgRaw) - 1) * 100 : 0,
        });
      }
    }

    return {
      thesis: "Small models contain hidden capability. Structured cognition reveals it.",
      comparisons: comparisons.length > 0 ? comparisons : DEMO_PARADOX_COMPARISONS,
      avgImprovement: stats?.avg_improvement ?? 0,
      sunwellWins: stats?.sunwell_wins ?? 0,
      totalRuns: stats?.total_runs ?? 0,
    };
  },

  // Has evaluation data?
  get hasEvaluations() {
    return evaluation.history.length > 0;
  },

  // ═══════════════════════════════════════════════════════════════
  // CONVERGENCE LOOP STATE (RFC-123)
  // ═══════════════════════════════════════════════════════════════

  // Convergence visualization state (derived from agent store)
  get convergence(): ConvergenceVizState {
    const conv = agent.convergence;
    
    if (!conv) {
      return {
        status: 'idle',
        iterations: [],
        maxIterations: 5,
        currentIteration: 0,
        enabledGates: [],
        isActive: false,
      };
    }

    // Transform iterations for visualization
    const iterations: ConvergenceIterationViz[] = conv.iterations.map(iter => ({
      iteration: iter.iteration,
      allPassed: iter.all_passed,
      totalErrors: iter.total_errors,
      gates: iter.gate_results.map(g => ({
        name: g.gate,
        passed: g.passed,
        errorCount: g.errors,
      })),
    }));

    return {
      status: conv.status,
      iterations,
      maxIterations: conv.max_iterations,
      currentIteration: conv.current_iteration,
      enabledGates: conv.enabled_gates,
      isActive: conv.status === 'running',
      tokensUsed: conv.tokens_used,
      durationMs: conv.duration_ms,
    };
  },

  // Is convergence currently running?
  get isConverging() {
    return agent.convergence?.status === 'running';
  },

  // Has convergence data?
  get hasConvergence() {
    return agent.convergence !== null;
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

