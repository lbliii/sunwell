/**
 * Layout Store — manages adaptive UI layout based on project type
 */

import { writable, derived } from 'svelte/store';
import { projectType } from './project';
import type { ProjectType } from '$lib/types';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export type LayoutType = 'code' | 'novel' | 'screenplay' | 'game' | 'general';

export interface Panel {
  id: string;
  title: string;
  icon: string;
  component: string;
  visible: boolean;
  position: 'left' | 'right' | 'bottom';
  width?: number;
  height?: number;
}

export interface LayoutConfig {
  type: LayoutType;
  panels: Panel[];
  primaryPanel: string;
  showSidebar: boolean;
}

// ═══════════════════════════════════════════════════════════════
// PANEL DEFINITIONS
// ═══════════════════════════════════════════════════════════════

const codePanels: Panel[] = [
  { id: 'files', title: 'Files', icon: '📁', component: 'FileTree', visible: true, position: 'left', width: 250 },
  { id: 'code', title: 'Code', icon: '📝', component: 'CodeEditor', visible: true, position: 'right' },
  { id: 'tests', title: 'Tests', icon: '🧪', component: 'TestRunner', visible: false, position: 'right' },
  { id: 'terminal', title: 'Terminal', icon: '⌨️', component: 'Terminal', visible: false, position: 'bottom', height: 200 },
];

const novelPanels: Panel[] = [
  { id: 'chapters', title: 'Chapters', icon: '📑', component: 'ChapterList', visible: true, position: 'left', width: 250 },
  { id: 'writing', title: 'Writing', icon: '✍️', component: 'ProseEditor', visible: true, position: 'right' },
  { id: 'characters', title: 'Characters', icon: '👥', component: 'CharacterList', visible: true, position: 'right', width: 250 },
  { id: 'threads', title: 'Plot Threads', icon: '🧵', component: 'PlotThreads', visible: false, position: 'right' },
  { id: 'wordcount', title: 'Word Count', icon: '📊', component: 'WordCount', visible: true, position: 'bottom', height: 60 },
];

const screenplayPanels: Panel[] = [
  { id: 'scenes', title: 'Scenes', icon: '🎬', component: 'SceneList', visible: true, position: 'left', width: 250 },
  { id: 'script', title: 'Script', icon: '✍️', component: 'FountainEditor', visible: true, position: 'right' },
  { id: 'beatsheet', title: 'Beat Sheet', icon: '🎭', component: 'BeatSheet', visible: false, position: 'right' },
  { id: 'timeline', title: 'Timeline', icon: '⏱', component: 'Timeline', visible: false, position: 'bottom', height: 150 },
];

const gamePanels: Panel[] = [
  { id: 'npcs', title: 'NPCs', icon: '👥', component: 'NPCList', visible: true, position: 'left', width: 250 },
  { id: 'dialogue', title: 'Dialogue Tree', icon: '🌳', component: 'DialogueTree', visible: true, position: 'right' },
  { id: 'quests', title: 'Quest Info', icon: '📋', component: 'QuestInfo', visible: false, position: 'right' },
  { id: 'variables', title: 'Variables', icon: '🔗', component: 'GameVariables', visible: false, position: 'bottom', height: 150 },
];

const generalPanels: Panel[] = [
  { id: 'files', title: 'Files', icon: '📁', component: 'FileTree', visible: true, position: 'left', width: 250 },
  { id: 'content', title: 'Content', icon: '📝', component: 'ContentViewer', visible: true, position: 'right' },
];

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

export const showSidebar = writable(true);
export const activePanels = writable<string[]>([]);

// ═══════════════════════════════════════════════════════════════
// DERIVED
// ═══════════════════════════════════════════════════════════════

/**
 * Get layout type from project type.
 */
export const layoutType = derived(projectType, ($projectType): LayoutType => {
  switch ($projectType) {
    case 'code_python':
    case 'code_js':
    case 'code_rust':
    case 'code_go':
    case 'code_web':
    case 'code_cli':
      return 'code';
    case 'novel':
      return 'novel';
    case 'screenplay':
      return 'screenplay';
    case 'game_dialogue':
      return 'game';
    default:
      return 'general';
  }
});

/**
 * Get panels for current layout type.
 */
export const panels = derived(layoutType, ($layoutType): Panel[] => {
  switch ($layoutType) {
    case 'code':
      return codePanels;
    case 'novel':
      return novelPanels;
    case 'screenplay':
      return screenplayPanels;
    case 'game':
      return gamePanels;
    default:
      return generalPanels;
  }
});

/**
 * Get current layout configuration.
 */
export const layoutConfig = derived(
  [layoutType, panels, showSidebar],
  ([$layoutType, $panels, $showSidebar]): LayoutConfig => ({
    type: $layoutType,
    panels: $panels,
    primaryPanel: $panels.find(p => p.position === 'right')?.id ?? 'content',
    showSidebar: $showSidebar,
  })
);

/**
 * Get visible panels for a position.
 */
export function getVisiblePanels(allPanels: Panel[], position: 'left' | 'right' | 'bottom'): Panel[] {
  return allPanels.filter(p => p.visible && p.position === position);
}

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Toggle sidebar visibility.
 */
export function toggleSidebar(): void {
  showSidebar.update(v => !v);
}

/**
 * Toggle a panel's visibility.
 */
export function togglePanel(panels: Panel[], panelId: string): Panel[] {
  return panels.map(p =>
    p.id === panelId ? { ...p, visible: !p.visible } : p
  );
}

/**
 * Show a specific panel.
 */
export function showPanel(panels: Panel[], panelId: string): Panel[] {
  return panels.map(p =>
    p.id === panelId ? { ...p, visible: true } : p
  );
}

/**
 * Hide a specific panel.
 */
export function hidePanel(panels: Panel[], panelId: string): Panel[] {
  return panels.map(p =>
    p.id === panelId ? { ...p, visible: false } : p
  );
}
