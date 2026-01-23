/**
 * Layout Store — manages adaptive UI layout (Svelte 5 runes)
 */

import { LayoutType } from '$lib/constants';
import type { LayoutType as LayoutTypeValue } from '$lib/constants';
import type { ProjectType } from '$lib/types';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

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
];

const screenplayPanels: Panel[] = [
  { id: 'scenes', title: 'Scenes', icon: '🎬', component: 'SceneList', visible: true, position: 'left', width: 250 },
  { id: 'script', title: 'Script', icon: '✍️', component: 'FountainEditor', visible: true, position: 'right' },
];

const gamePanels: Panel[] = [
  { id: 'npcs', title: 'NPCs', icon: '👥', component: 'NPCList', visible: true, position: 'left', width: 250 },
  { id: 'dialogue', title: 'Dialogue Tree', icon: '🌳', component: 'DialogueTree', visible: true, position: 'right' },
];

const generalPanels: Panel[] = [
  { id: 'files', title: 'Files', icon: '📁', component: 'FileTree', visible: true, position: 'left', width: 250 },
  { id: 'content', title: 'Content', icon: '📝', component: 'ContentViewer', visible: true, position: 'right' },
];

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

let _isSidebarOpen = $state(true);
let _layoutType = $state<LayoutTypeValue>(LayoutType.GENERAL);

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

function getPanelsForLayoutType(type: LayoutTypeValue): Panel[] {
  switch (type) {
    case LayoutType.CODE: return codePanels;
    case LayoutType.NOVEL: return novelPanels;
    case LayoutType.SCREENPLAY: return screenplayPanels;
    case LayoutType.GAME: return gamePanels;
    default: return generalPanels;
  }
}

function getLayoutTypeFromProjectType(projectType: ProjectType): LayoutTypeValue {
  switch (projectType) {
    case 'code_python': case 'code_js': case 'code_rust': case 'code_go': case 'code_web': case 'code_cli':
      return LayoutType.CODE;
    case 'novel': return LayoutType.NOVEL;
    case 'screenplay': return LayoutType.SCREENPLAY;
    case 'game_dialogue': return LayoutType.GAME;
    default: return LayoutType.GENERAL;
  }
}

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const layout = {
  get isSidebarOpen() { return _isSidebarOpen; },
  get type() { return _layoutType; },
  get panels() { return getPanelsForLayoutType(_layoutType); },
};

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

export function toggleSidebar(): void {
  _isSidebarOpen = !_isSidebarOpen;
}

export function setMode(projectType: ProjectType): void {
  _layoutType = getLayoutTypeFromProjectType(projectType);
}

export function getVisiblePanels(panels: Panel[], position: 'left' | 'right' | 'bottom'): Panel[] {
  return panels.filter(p => p.visible && p.position === position);
}
