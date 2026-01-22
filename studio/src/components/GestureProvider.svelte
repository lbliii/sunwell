<!--
  GestureProvider — Touch/trackpad gesture wrapper (RFC-082)
  
  Integrates @use-gesture/vanilla for direct manipulation:
  - Swipe to dismiss/minimize
  - Pinch to collapse/expand
  - Drag to reposition
  - Pan for canvas navigation
-->
<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { spring } from 'svelte/motion';

	type GestureAction =
		| { type: 'swipe'; direction: 'up' | 'down' | 'left' | 'right'; velocity: number }
		| { type: 'pinch'; scale: number }
		| { type: 'drag'; x: number; y: number; velocity: [number, number] }
		| { type: 'pan'; x: number; y: number }
		| { type: 'tap' }
		| { type: 'longpress' };

	interface Props {
		enabled?: boolean;
		enableSwipe?: boolean;
		enablePinch?: boolean;
		enableDrag?: boolean;
		enablePan?: boolean;
		enableLongPress?: boolean;
		swipeThreshold?: number;
		pinchCollapseThreshold?: number;
		pinchExpandThreshold?: number;
		longPressDelay?: number;
		onGesture?: (action: GestureAction) => void;
		children?: import('svelte').Snippet;
	}

	let {
		enabled = true,
		enableSwipe = true,
		enablePinch = true,
		enableDrag = false,
		enablePan = false,
		enableLongPress = true,
		swipeThreshold = 0.5,
		pinchCollapseThreshold = 0.7,
		pinchExpandThreshold = 1.3,
		longPressDelay = 500,
		onGesture,
		children,
	}: Props = $props();

	let containerEl: HTMLDivElement | undefined = $state();

	// Spring-animated transform for drag feedback
	const dragX = spring(0, { stiffness: 0.2, damping: 0.5 });
	const dragY = spring(0, { stiffness: 0.2, damping: 0.5 });
	const gestureScale = spring(1, { stiffness: 0.15, damping: 0.5 });

	// Track gesture state
	let isDragging = $state(false);
	let isPinching = $state(false);
	let longPressTimeout: ReturnType<typeof setTimeout> | null = null;
	let gestureCleanup: (() => void) | null = null;

	onMount(async () => {
		if (!containerEl || !enabled) return;

		try {
			// Dynamically import @use-gesture/vanilla
			const { createGesture } = await import('@use-gesture/vanilla');

			const gesture = createGesture(
				containerEl,
				{
					onDrag: enableDrag || enableSwipe ? handleDrag : undefined,
					onPinch: enablePinch ? handlePinch : undefined,
					onWheel: enablePan ? handleWheel : undefined,
				},
				{
					drag: {
						filterTaps: true,
						threshold: 10,
					},
					pinch: {
						threshold: 0.1,
					},
				}
			);

			gestureCleanup = gesture;

			// Long press handling (manual since @use-gesture doesn't have it)
			if (enableLongPress) {
				containerEl.addEventListener('pointerdown', handlePointerDown);
				containerEl.addEventListener('pointerup', handlePointerUp);
				containerEl.addEventListener('pointercancel', handlePointerUp);
				containerEl.addEventListener('pointermove', handlePointerMove);
			}
		} catch (e) {
			console.warn('Gesture library not available, using fallback');
			// Fallback: basic touch event handling
			if (enableSwipe) {
				containerEl.addEventListener('touchstart', handleTouchStart, { passive: true });
				containerEl.addEventListener('touchend', handleTouchEnd);
			}
		}
	});

	onDestroy(() => {
		gestureCleanup?.();
		if (containerEl && enableLongPress) {
			containerEl.removeEventListener('pointerdown', handlePointerDown);
			containerEl.removeEventListener('pointerup', handlePointerUp);
			containerEl.removeEventListener('pointercancel', handlePointerUp);
			containerEl.removeEventListener('pointermove', handlePointerMove);
		}
		if (longPressTimeout) {
			clearTimeout(longPressTimeout);
		}
	});

	// Drag handler
	function handleDrag(state: {
		active: boolean;
		movement: [number, number];
		velocity: [number, number];
		direction: [number, number];
	}) {
		const { active, movement, velocity, direction } = state;
		const [mx, my] = movement;
		const [vx, vy] = velocity;
		const [dx, dy] = direction;

		if (active) {
			isDragging = true;
			dragX.set(mx);
			dragY.set(my);
		} else {
			isDragging = false;
			dragX.set(0);
			dragY.set(0);

			// Detect swipe on release
			if (enableSwipe) {
				const totalVelocity = Math.sqrt(vx * vx + vy * vy);
				if (totalVelocity > swipeThreshold) {
					let swipeDirection: 'up' | 'down' | 'left' | 'right';
					if (Math.abs(dx) > Math.abs(dy)) {
						swipeDirection = dx > 0 ? 'right' : 'left';
					} else {
						swipeDirection = dy > 0 ? 'down' : 'up';
					}
					onGesture?.({ type: 'swipe', direction: swipeDirection, velocity: totalVelocity });
				}
			}

			// Emit drag end if drag was enabled
			if (enableDrag && (Math.abs(mx) > 10 || Math.abs(my) > 10)) {
				onGesture?.({ type: 'drag', x: mx, y: my, velocity });
			}
		}
	}

	// Pinch handler
	function handlePinch(state: { active: boolean; offset: [number, number] }) {
		const { active, offset } = state;
		const scale = offset[0];

		if (active) {
			isPinching = true;
			gestureScale.set(scale);
		} else {
			isPinching = false;
			gestureScale.set(1);

			// Detect collapse/expand
			if (scale < pinchCollapseThreshold) {
				onGesture?.({ type: 'pinch', scale });
			} else if (scale > pinchExpandThreshold) {
				onGesture?.({ type: 'pinch', scale });
			}
		}
	}

	// Wheel handler (for pan)
	function handleWheel(state: { delta: [number, number] }) {
		if (!enablePan) return;
		const [dx, dy] = state.delta;
		onGesture?.({ type: 'pan', x: dx, y: dy });
	}

	// Long press handlers
	let pointerStartPos = { x: 0, y: 0 };

	function handlePointerDown(e: PointerEvent) {
		pointerStartPos = { x: e.clientX, y: e.clientY };
		longPressTimeout = setTimeout(() => {
			onGesture?.({ type: 'longpress' });
		}, longPressDelay);
	}

	function handlePointerUp() {
		if (longPressTimeout) {
			clearTimeout(longPressTimeout);
			longPressTimeout = null;
		}
	}

	function handlePointerMove(e: PointerEvent) {
		// Cancel long press if moved too far
		const dx = e.clientX - pointerStartPos.x;
		const dy = e.clientY - pointerStartPos.y;
		if (Math.sqrt(dx * dx + dy * dy) > 10 && longPressTimeout) {
			clearTimeout(longPressTimeout);
			longPressTimeout = null;
		}
	}

	// Fallback touch handlers
	let touchStartPos = { x: 0, y: 0, time: 0 };

	function handleTouchStart(e: TouchEvent) {
		const touch = e.touches[0];
		touchStartPos = { x: touch.clientX, y: touch.clientY, time: Date.now() };
	}

	function handleTouchEnd(e: TouchEvent) {
		const touch = e.changedTouches[0];
		const dx = touch.clientX - touchStartPos.x;
		const dy = touch.clientY - touchStartPos.y;
		const dt = Date.now() - touchStartPos.time;

		const velocity = Math.sqrt(dx * dx + dy * dy) / dt;
		if (velocity > swipeThreshold * 0.3) {
			let direction: 'up' | 'down' | 'left' | 'right';
			if (Math.abs(dx) > Math.abs(dy)) {
				direction = dx > 0 ? 'right' : 'left';
			} else {
				direction = dy > 0 ? 'down' : 'up';
			}
			onGesture?.({ type: 'swipe', direction, velocity });
		}
	}
</script>

<div
	bind:this={containerEl}
	class="gesture-provider"
	class:dragging={isDragging}
	class:pinching={isPinching}
	style:transform="translate({$dragX}px, {$dragY}px) scale({$gestureScale})"
	style:touch-action={enablePan ? 'none' : 'auto'}
>
	{@render children?.()}
</div>

<style>
	.gesture-provider {
		position: relative;
		transition: box-shadow 0.2s ease;
	}

	.gesture-provider.dragging {
		cursor: grabbing;
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
	}

	.gesture-provider.pinching {
		transition: none;
	}
</style>
