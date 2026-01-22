/**
 * Type declarations for @use-gesture/vanilla
 * 
 * This module is dynamically imported at runtime.
 * These declarations provide type safety for development.
 */

declare module '@use-gesture/vanilla' {
	export interface GestureState {
		active: boolean;
		movement: [number, number];
		velocity: [number, number];
		direction: [number, number];
		offset: [number, number];
		delta: [number, number];
	}

	export interface GestureHandlers {
		onDrag?: (state: GestureState) => void;
		onPinch?: (state: GestureState) => void;
		onWheel?: (state: GestureState) => void;
		onScroll?: (state: GestureState) => void;
		onMove?: (state: GestureState) => void;
		onHover?: (state: GestureState) => void;
	}

	export interface GestureConfig {
		drag?: {
			filterTaps?: boolean;
			threshold?: number;
		};
		pinch?: {
			threshold?: number;
		};
	}

	export function createGesture(
		element: Element,
		handlers: GestureHandlers,
		config?: GestureConfig
	): () => void;
}
