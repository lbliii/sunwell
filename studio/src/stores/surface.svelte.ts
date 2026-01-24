/**
 * Surface Store — Generative surface composition (RFC-072)
 * 
 * Manages dynamic surface layouts that adapt to goals and context.
 *
 * RFC-113: Uses HTTP API instead of Tauri for all communication.
 */

import { apiGet, apiPost } from '$lib/socket';
import type { 
  PrimitiveDef, 
  SurfacePrimitive, 
  SurfaceLayout, 
  SurfaceArrangement,
  PrimitiveSize,
} from '$lib/types';

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

interface SurfaceState {
  /** Current layout */
  layout: SurfaceLayout | null;
  
  /** Available primitives from registry */
  registry: PrimitiveDef[];
  
  /** Current goal that generated this layout */
  currentGoal: string | null;
  
  /** Layout start time (for success tracking) */
  layoutStartTime: number | null;
  
  /** Is layout being composed */
  isComposing: boolean;
  
  /** Error state */
  error: string | null;
  
  /** Previous layouts for undo */
  history: SurfaceLayout[];
  
  /** Is registry loaded */
  registryLoaded: boolean;
}

function createInitialState(): SurfaceState {
  return {
    layout: null,
    registry: [],
    currentGoal: null,
    layoutStartTime: null,
    isComposing: false,
    error: null,
    history: [],
    registryLoaded: false,
  };
}

let _state = $state<SurfaceState>(createInitialState());

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const surface = {
  get layout() { return _state.layout; },
  get registry() { return _state.registry; },
  get currentGoal() { return _state.currentGoal; },
  get layoutStartTime() { return _state.layoutStartTime; },
  get isComposing() { return _state.isComposing; },
  get error() { return _state.error; },
  get history() { return _state.history; },
  get registryLoaded() { return _state.registryLoaded; },
  
  // Computed
  get hasLayout() { return _state.layout !== null; },
  get primaryDef(): PrimitiveDef | undefined {
    if (!_state.layout) return undefined;
    return _state.registry.find(p => p.id === _state.layout!.primary.id);
  },
  get activeCategories(): Set<string> {
    if (!_state.layout) return new Set();
    const cats = new Set([_state.layout.primary.category]);
    _state.layout.secondary.forEach(p => cats.add(p.category));
    _state.layout.contextual.forEach(p => cats.add(p.category));
    return cats;
  },
  get canUndo() { return _state.history.length > 0; },
};

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Load the primitive registry from Python.
 * RFC-113: Uses HTTP API instead of Tauri invoke.
 */
export async function loadRegistry(): Promise<void> {
  if (_state.registryLoaded) return;
  
  try {
    const registry = await apiGet<PrimitiveDef[]>('/api/surface/registry');
    _state = { ..._state, registry: registry || [], registryLoaded: true };
  } catch (e) {
    console.error('Failed to load primitive registry:', e);
    _state = { 
      ..._state, 
      error: e instanceof Error ? e.message : String(e),
    };
  }
}

/**
 * Compose a surface layout for the given goal.
 * RFC-113: Uses HTTP API instead of Tauri invoke.
 */
export async function composeSurface(
  goal: string,
  projectPath?: string,
  lens?: string,
  arrangement?: SurfaceArrangement,
): Promise<SurfaceLayout | null> {
  // Record success of previous layout before switching
  if (_state.layout && _state.currentGoal && _state.layoutStartTime) {
    const duration = Math.floor((Date.now() - _state.layoutStartTime) / 1000);
    await recordSuccess(_state.layout, _state.currentGoal, duration, false);
  }
  
  _state = { ..._state, isComposing: true, error: null };
  
  try {
    const layout = await apiPost<SurfaceLayout>('/api/surface/compose', {
      goal,
      projectPath: projectPath ?? null,
      lens: lens ?? null,
      arrangement: arrangement ?? null,
    });
    
    // Save previous layout to history (max 5)
    if (_state.layout) {
      _state = {
        ..._state,
        history: [_state.layout, ..._state.history.slice(0, 4)],
      };
    }
    
    _state = {
      ..._state,
      layout,
      currentGoal: goal,
      layoutStartTime: Date.now(),
      isComposing: false,
    };
    
    return layout;
  } catch (e) {
    _state = {
      ..._state,
      error: e instanceof Error ? e.message : String(e),
      isComposing: false,
    };
    console.error('Failed to compose surface:', e);
    return null;
  }
}

/**
 * Record layout success metrics.
 * RFC-113: Uses HTTP API instead of Tauri invoke.
 */
async function recordSuccess(
  layout: SurfaceLayout,
  goal: string,
  durationSeconds: number,
  completed: boolean,
): Promise<void> {
  try {
    await apiPost('/api/surface/success', {
      layout,
      goal,
      durationSeconds,
      completed,
    });
  } catch (e) {
    console.error('Failed to record layout success:', e);
  }
}

/**
 * Mark current goal as completed (records success with higher weight).
 */
export async function markGoalCompleted(): Promise<void> {
  if (_state.layout && _state.currentGoal && _state.layoutStartTime) {
    const duration = Math.floor((Date.now() - _state.layoutStartTime) / 1000);
    await recordSuccess(_state.layout, _state.currentGoal, duration, true);
  }
}

/**
 * Emit an event from a primitive component.
 * RFC-113: Uses HTTP API instead of Tauri invoke.
 */
export async function emitPrimitiveEvent(
  primitiveId: string,
  eventType: 'file_edit' | 'terminal_output' | 'test_result' | 'user_action',
  data: Record<string, unknown>,
): Promise<void> {
  try {
    await apiPost('/api/surface/event', {
      primitive_id: primitiveId,
      event_type: eventType,
      data,
    });
  } catch (e) {
    console.error('Failed to emit primitive event:', e);
  }
}

/**
 * Manually add a primitive to the current layout.
 */
export function addPrimitive(
  primitiveId: string, 
  slot: 'secondary' | 'contextual',
  size?: PrimitiveSize,
): void {
  if (!_state.layout) return;
  
  const def = _state.registry.find(p => p.id === primitiveId);
  if (!def) return;
  
  const primitive: SurfacePrimitive = {
    id: primitiveId,
    category: def.category,
    size: size ?? def.default_size,
    props: {},
  };
  
  if (slot === 'secondary' && _state.layout.secondary.length < 3) {
    _state = {
      ..._state,
      layout: {
        ..._state.layout,
        secondary: [..._state.layout.secondary, primitive],
      },
    };
  } else if (slot === 'contextual' && _state.layout.contextual.length < 2) {
    _state = {
      ..._state,
      layout: {
        ..._state.layout,
        contextual: [..._state.layout.contextual, primitive],
      },
    };
  }
}

/**
 * Remove a primitive from the current layout.
 */
export function removePrimitive(primitiveId: string): void {
  if (!_state.layout) return;
  
  _state = {
    ..._state,
    layout: {
      ..._state.layout,
      secondary: _state.layout.secondary.filter(p => p.id !== primitiveId),
      contextual: _state.layout.contextual.filter(p => p.id !== primitiveId),
    },
  };
}

/**
 * Change the arrangement of the current layout.
 */
export function setArrangement(arrangement: SurfaceArrangement): void {
  if (!_state.layout) return;
  
  _state = {
    ..._state,
    layout: {
      ..._state.layout,
      arrangement,
    },
  };
}

/**
 * Undo to previous layout.
 */
export function undoLayout(): void {
  if (_state.history.length === 0) return;
  
  const [previous, ...rest] = _state.history;
  _state = {
    ..._state,
    layout: previous,
    history: rest,
  };
}

/**
 * Set a layout directly (for testing or restoring).
 */
export function setLayout(layout: SurfaceLayout): void {
  if (_state.layout) {
    _state = {
      ..._state,
      history: [_state.layout, ..._state.history.slice(0, 4)],
    };
  }
  
  _state = {
    ..._state,
    layout,
    layoutStartTime: Date.now(),
  };
}

/**
 * Clear error state.
 */
export function clearError(): void {
  _state = { ..._state, error: null };
}

/**
 * Reset surface state.
 */
export function resetSurface(): void {
  _state = createInitialState();
}

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

/**
 * Get primitives by category.
 */
export function getPrimitivesByCategory(category: string): PrimitiveDef[] {
  return _state.registry.filter(p => p.category === category);
}

/**
 * Get primitives that can be primary.
 */
export function getPrimaryCapable(): PrimitiveDef[] {
  return _state.registry.filter(p => p.can_be_primary);
}

/**
 * Get primitives that can be secondary.
 */
export function getSecondaryCapable(): PrimitiveDef[] {
  return _state.registry.filter(p => p.can_be_secondary);
}

/**
 * Get primitives that can be contextual.
 */
export function getContextualCapable(): PrimitiveDef[] {
  return _state.registry.filter(p => p.can_be_contextual);
}

/**
 * Get category icon.
 */
export function getCategoryIcon(category: string): string {
  const icons: Record<string, string> = {
    'code': '💻',
    'planning': '📋',
    'writing': '✍️',
    'data': '📊',
    'universal': '🔮',
  };
  return icons[category] || '📦';
}

/**
 * Get arrangement description.
 */
export function getArrangementDescription(arrangement: SurfaceArrangement): string {
  const descriptions: Record<SurfaceArrangement, string> = {
    'standard': 'Primary with sidebar and optional bottom panel',
    'focused': 'Primary only, minimal distractions',
    'split': 'Two panels side by side',
    'dashboard': 'Multiple panels in a grid',
  };
  return descriptions[arrangement];
}
