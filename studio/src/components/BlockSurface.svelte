<!--
  BlockSurface — Tetris-style animated surface for blocks (RFC-080)
  
  Universal container for rendering blocks with spring physics animations.
  Blocks can appear anywhere: Home, workspace sidebars, floating overlays.
-->
<script lang="ts">
	import { fly, scale } from 'svelte/transition';
	import { spring } from 'svelte/motion';
	import HabitsBlock from './blocks/HabitsBlock.svelte';
	import ContactsBlock from './blocks/ContactsBlock.svelte';
	import CalendarBlock from './blocks/CalendarBlock.svelte';
	import FilesBlock from './blocks/FilesBlock.svelte';
	import ProjectsBlock from './blocks/ProjectsBlock.svelte';
	import GitBlock from './blocks/GitBlock.svelte';
	import BookmarksBlock from './blocks/BookmarksBlock.svelte';
	import ListBlock from './blocks/ListBlock.svelte';
	import NotesBlock from './blocks/NotesBlock.svelte';
	import SearchBlock from './blocks/SearchBlock.svelte';
	import GenericBlock from './blocks/GenericBlock.svelte';
	import {
		calculateBlockHeight,
		getSpringConfigForBlockType,
		SPRING_CONFIGS,
	} from '../lib/tetris';

	interface Props {
		blockType: string;
		blockData: Record<string, unknown>;
		response?: string;
		onDismiss?: () => void;
		onAction?: (actionId: string, itemId?: string) => void;
	}

	let { blockType, blockData, response, onDismiss, onAction }: Props = $props();

	// Spring animation for height - use $derived so it reacts to blockType changes
	const springConfig = $derived(getSpringConfigForBlockType(blockType));
	let surfaceHeight = spring(0, SPRING_CONFIGS.default);
	
	// Update spring config when blockType changes
	$effect(() => {
		surfaceHeight.stiffness = springConfig.stiffness;
		surfaceHeight.damping = springConfig.damping;
	});

	// Map block types to components
	const blockComponents: Record<string, typeof GenericBlock> = {
		habits: HabitsBlock,
		contacts: ContactsBlock,
		calendar: CalendarBlock,
		files: FilesBlock,
		projects: ProjectsBlock,
		git_status: GitBlock,
		git_log: GitBlock,
		git_branches: GitBlock,
		bookmarks: BookmarksBlock,
		list: ListBlock,
		notes: NotesBlock,
		search: SearchBlock,
	};

	// Calculate content height based on data
	function getItemCount(data: Record<string, unknown>): number {
		const keys = ['habits', 'contacts', 'events', 'files', 'items', 'projects', 'notes', 'results', 'commits', 'bookmarks'];
		for (const key of keys) {
			if (Array.isArray(data[key])) {
				return (data[key] as unknown[]).length;
			}
		}
		return 3; // Default
	}

	$effect(() => {
		// Animate to appropriate height based on content
		const itemCount = getItemCount(blockData);
		const contentHeight = calculateBlockHeight(itemCount);
		surfaceHeight.set(contentHeight);
	});

	function handleAction(actionId: string, itemId?: string) {
		onAction?.(actionId, itemId);
	}

	function handleDismiss() {
		onDismiss?.();
	}
</script>

<div
	class="block-surface"
	style:height="{$surfaceHeight}px"
	in:fly={{ y: 50, duration: 300 }}
	out:scale={{ start: 0.95, duration: 200 }}
>
	{#if response}
		<div class="response-header">
			<p class="response-text">{response}</p>
			<button class="dismiss-btn" onclick={handleDismiss} aria-label="Dismiss">
				<span aria-hidden="true">✕</span>
			</button>
		</div>
	{/if}

	<div class="block-content">
		{#if blockComponents[blockType]}
			{@const BlockComponent = blockComponents[blockType]}
			<BlockComponent data={blockData} {onAction} />
		{:else}
			<GenericBlock type={blockType} data={blockData} />
		{/if}
	</div>
</div>

<style>
	.block-surface {
		position: relative;
		margin-top: var(--space-6, 24px);
		background: linear-gradient(
			180deg,
			rgba(255, 215, 0, 0.03) 0%,
			rgba(10, 10, 10, 0.95) 100%
		);
		border: 1px solid rgba(255, 215, 0, 0.15);
		border-radius: var(--radius-xl, 16px);
		overflow: hidden;
		backdrop-filter: blur(20px);
		width: 100%;
		max-width: 600px;

		/* Golden glow */
		box-shadow:
			0 4px 24px rgba(0, 0, 0, 0.4),
			0 0 60px rgba(255, 215, 0, 0.08),
			inset 0 1px 0 rgba(255, 215, 0, 0.1);
	}

	.response-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		padding: var(--space-4, 16px);
		border-bottom: 1px solid rgba(255, 215, 0, 0.1);
		gap: var(--space-3, 12px);
	}

	.response-text {
		color: var(--text-secondary, #999);
		font-size: var(--text-sm, 14px);
		margin: 0;
		flex: 1;
		line-height: 1.5;
	}

	.dismiss-btn {
		background: none;
		border: none;
		color: var(--text-tertiary, #666);
		cursor: pointer;
		padding: var(--space-1, 4px);
		border-radius: var(--radius-sm, 4px);
		transition: all 0.15s ease;
		flex-shrink: 0;
	}

	.dismiss-btn:hover {
		color: var(--gold, #ffd700);
		background: rgba(255, 215, 0, 0.1);
	}

	.dismiss-btn:focus-visible {
		outline: 2px solid var(--gold, #ffd700);
		outline-offset: 2px;
	}

	.block-content {
		padding: var(--space-4, 16px);
		overflow-y: auto;
		max-height: calc(100% - 60px);
	}

	/* Scrollbar styling */
	.block-content::-webkit-scrollbar {
		width: 6px;
	}

	.block-content::-webkit-scrollbar-track {
		background: transparent;
	}

	.block-content::-webkit-scrollbar-thumb {
		background: rgba(255, 215, 0, 0.2);
		border-radius: 3px;
	}

	.block-content::-webkit-scrollbar-thumb:hover {
		background: rgba(255, 215, 0, 0.3);
	}
</style>
