<!--
  Home — Unified Home Surface (RFC-080)
  
  One input, infinite possibilities. Type anything → AI understands intent → 
  beautiful response materializes (block, workspace, action, or conversation).
-->
<script lang="ts">
	import { untrack } from 'svelte';
	import Logo from '../components/Logo.svelte';
	import InputBar from '../components/InputBar.svelte';
	import RisingMotes from '../components/RisingMotes.svelte';
	import MouseMotes from '../components/MouseMotes.svelte';
	import Modal from '../components/Modal.svelte';
	import Button from '../components/Button.svelte';
	import SparkleField from '../components/ui/SparkleField.svelte';
	import LensPicker from '../components/LensPicker.svelte';
	import LensBadge from '../components/LensBadge.svelte';
	import ChatHistory from '../components/ChatHistory.svelte';
	import { BlockSurface, ActionToast, ConversationLayout, ProjectManager } from '../components';
	import { goToProject, goToDemo, goToObservatory } from '../stores/app.svelte';
	import {
		project,
		scanProjects,
		openProject,
		resumeProject,
		deleteProject,
		archiveProject,
		iterateProject,
		analyzeProject,
	} from '../stores/project.svelte';
	import { runGoal } from '../stores/agent.svelte';
	import { lens, loadLenses, selectLens } from '../stores/lens.svelte';
	import {
		homeState,
		routeInput,
		clearResponse,
		executeBlockAction,
		isViewResponse,
		isActionResponse,
		isConversationResponse,
		isWorkspaceResponse,
		isHybridResponse,
	} from '../stores/home.svelte';
	import type { ProjectStatus } from '$lib/types';

	let inputValue = $state('');
	let inputBar: InputBar | undefined = $state();

	// Chat history sidebar state
	let showChatHistory = $state(false);

	// Pre-computed messages for ConversationLayout (avoids .map() in template)
	const conversationMessages = $derived(
		homeState.conversationHistory.slice(0, -1).map(m => ({
			role: m.role,
			content: m.content
		}))
	);

	// Lens picker state (for workspace intents)
	let showLensPicker = $state(false);
	let pendingGoal = $state<string | null>(null);
	let pendingWorkspaceSpec = $state<Record<string, unknown> | null>(null);

	// Type guard for tool action data
	function isToolData(data: unknown): data is { tool: string } {
		return typeof data === 'object' && data !== null && 'tool' in data && typeof (data as Record<string, unknown>).tool === 'string';
	}

	// Project lookup map for O(1) access
	const projectsByPath = $derived(
		new Map(project.discovered.map(p => [p.path, p]))
	);

	// Handler for inline ProjectManager (avoid recreating arrow function)
	async function handleInlineOpenProject(path: string) {
		await openProject(path);
		analyzeProject(path);
		goToProject();
	}

	// Action toast state
	let actionToast = $state<{
		show: boolean;
		actionType: string;
		success: boolean;
		message: string;
	} | null>(null);

	// Confirmation modal state
	let confirmModal = $state<{
		show: boolean;
		title: string;
		message: string;
		action: 'delete' | 'archive';
		project: ProjectStatus | null;
		destructive: boolean;
	}>({
		show: false,
		title: '',
		message: '',
		action: 'delete',
		project: null,
		destructive: false,
	});

	function showConfirm(action: 'delete' | 'archive', proj: ProjectStatus) {
		if (action === 'delete') {
			confirmModal = {
				show: true,
				title: 'Delete Project',
				message: `Delete "${proj.name}" permanently? This cannot be undone.`,
				action: 'delete',
				project: proj,
				destructive: true,
			};
		} else {
			confirmModal = {
				show: true,
				title: 'Archive Project',
				message: `Archive "${proj.name}"? This will move it to ~/Sunwell/archived/`,
				action: 'archive',
				project: proj,
				destructive: false,
			};
		}
	}

	async function handleConfirm() {
		if (!confirmModal.project) return;

		const proj = confirmModal.project;
		const action = confirmModal.action;
		confirmModal = { ...confirmModal, show: false };

		if (action === 'delete') {
			await deleteProject(proj.path);
		} else {
			await archiveProject(proj.path);
		}
	}

	function handleCancel() {
		confirmModal = { ...confirmModal, show: false };
	}

	// One-time initialization on mount
	$effect(() => {
		untrack(() => {
			// Clear stale response when returning to Home (projects hidden otherwise)
			clearResponse();
			scanProjects();
			loadLenses();
			inputBar?.focus();
		});
	});

	// Unified input handler — routes to workspace, view, action, or conversation
	async function handleSubmit(goal: string) {
		if (!goal || homeState.isProcessing) return;

		inputValue = '';

		// Route through InteractionRouter (RFC-075)
		const response = await routeInput(goal);

		if (isWorkspaceResponse(response)) {
			// Show lens picker for workspace creation
			pendingGoal = goal;
			pendingWorkspaceSpec = response.workspace_spec || null;
			showLensPicker = true;
		} else if (isActionResponse(response)) {
			// Show action toast
			actionToast = {
				show: true,
				actionType: response.action_type,
				success: response.success,
				message: response.response,
			};
		}
		// View, Conversation, and Hybrid responses are rendered via reactive state
	}

	// Handle lens selection and run goal
	async function handleLensConfirm(lensName: string | null, autoSelect: boolean) {
		if (!pendingGoal) return;

		selectLens(lensName, autoSelect);

		// Run goal with lens selection
		// RFC-117: New parameter order - projectId comes before lens
		const workspacePath = await runGoal(pendingGoal, undefined, undefined, lensName, autoSelect);
		if (workspacePath) {
			await openProject(workspacePath);
			goToProject();
		}

		pendingGoal = null;
		pendingWorkspaceSpec = null;
		showLensPicker = false;
	}

	function handleLensPickerClose() {
		showLensPicker = false;
		pendingGoal = null;
		pendingWorkspaceSpec = null;
	}

	function handleDismissBlock() {
		clearResponse();
	}

	async function handleBlockAction(actionId: string, data?: unknown) {
		// Extract itemId if data is a string, otherwise keep as structured data
		const itemId = typeof data === 'string' ? data : undefined;

		// Handle follow-up: focus input to continue conversation
		if (actionId === 'follow_up') {
			inputBar?.focus();
			return;
		}

		// Handle dismiss: clear the current response
		if (actionId === 'dismiss') {
			clearResponse();
			return;
		}

		// Handle use_tool: insert tool reference into input (client-side only)
		if (actionId === 'use_tool' && isToolData(data)) {
			// TODO: Insert tool into input when that feature is implemented
			console.log('Tool selected:', data.tool);
			return;
		}

		// Handle panel_action: client-side panel interactions
		if (actionId === 'panel_action' && data && typeof data === 'object') {
			// TODO: Handle panel actions when that feature is implemented
			console.log('Panel action:', data);
			return;
		}

		// Handle project-specific actions
		if (actionId === 'open' && itemId) {
			await openProject(itemId);
			analyzeProject(itemId);
			goToProject();
			return;
		}
		if (actionId === 'resume' && itemId) {
			await openProject(itemId);
			analyzeProject(itemId);
			goToProject();
			await resumeProject(itemId);
			return;
		}
		if (actionId === 'archive' && itemId) {
			const proj = projectsByPath.get(itemId);
			if (proj) showConfirm('archive', proj);
			return;
		}

		// Execute other block actions through ActionExecutor
		const result = await executeBlockAction(actionId, itemId);
		if (result.success || result.message) {
			actionToast = {
				show: true,
				actionType: actionId,
				success: result.success,
				message: result.message,
			};
		}
	}

	function handleDismissToast() {
		actionToast = null;
	}

	async function handleSelectProject(proj: ProjectStatus) {
		await openProject(proj.path);
		analyzeProject(proj.path);
		goToProject();
	}

	async function handleResumeProject(proj: ProjectStatus) {
		await openProject(proj.path);
		analyzeProject(proj.path);
		goToProject();
		await resumeProject(proj.path);
	}

	async function handleIterateProject(proj: ProjectStatus) {
		const result = await iterateProject(proj.path);
		if (result.success && result.new_path) {
			await openProject(result.new_path);
			goToProject();
		}
	}

	function handleArchiveProject(proj: ProjectStatus) {
		showConfirm('archive', proj);
	}

	function handleDeleteProject(proj: ProjectStatus) {
		showConfirm('delete', proj);
	}
</script>

<MouseMotes spawnRate={50} maxParticles={30}>
	{#snippet children()}
		<div class="home">
			<!-- Chat history toggle button (visible when there's history) -->
			{#if homeState.conversationHistory.length > 0}
				<button
					class="history-toggle"
					onclick={() => (showChatHistory = true)}
					aria-label="View chat history"
					title="Chat history ({homeState.conversationHistory.length} messages)"
				>
					💬 <span class="history-count">{homeState.conversationHistory.length}</span>
				</button>
			{/if}

			<!-- Background aura centered on logo area -->
			<div class="background-aura"></div>

			<!-- Ambient rising motes (always visible, more prominent) -->
			<div class="ambient-motes">
				<RisingMotes count={12} intensity="normal" />
			</div>

			<div class="hero">
				<div class="logo-container">
					<div class="logo-sparkles">
						<SparkleField width={16} height={5} density={0.08} speed={250} />
					</div>
					<Logo size="lg" />
				</div>

				<!-- Hero input (hidden when in conversation) -->
				{#if !isConversationResponse(homeState.response)}
					<div class="input-section">
						<InputBar
							bind:this={inputBar}
							bind:value={inputValue}
							placeholder="Build a pirate game, show my habits, remind me at 5pm..."
							autofocus
							showMotes={true}
							onsubmit={handleSubmit}
							loading={homeState.isProcessing}
						/>
						<!-- Show selected lens badge -->
						{#if lens.selection.lens || !lens.selection.autoSelect}
							<div class="lens-indicator">
								<LensBadge size="sm" showAuto={false} />
							</div>
						{/if}
					</div>
				{/if}

				<!-- Dynamic Block Surface (Tetris layout) -->
				{#if homeState.response}
					<div class="response-surface">
						{#if isViewResponse(homeState.response)}
							<BlockSurface
								blockType={homeState.response.view_type}
								blockData={homeState.response.view_data}
								response={homeState.response.response}
								onDismiss={handleDismissBlock}
								onAction={handleBlockAction}
							/>
						{:else if isConversationResponse(homeState.response)}
							<ConversationLayout
								messages={conversationMessages}
								currentResponse={homeState.response.response}
								mode={homeState.response.conversation_mode}
								auxiliaryPanels={homeState.response.auxiliary_panels}
								suggestedTools={homeState.response.suggested_tools}
								loading={homeState.isProcessing}
								onSubmit={handleSubmit}
								onAction={handleBlockAction}
								onDismiss={handleDismissBlock}
							/>
						{:else if isHybridResponse(homeState.response)}
							<BlockSurface
								blockType={homeState.response.view_type}
								blockData={homeState.response.view_data}
								onDismiss={handleDismissBlock}
								onAction={handleBlockAction}
							/>
						{/if}
					</div>
				{/if}

				<!-- Contextual Projects (always shown if projects exist) -->
				{#if project.discovered.length > 0 && !homeState.response}
					<section class="contextual-blocks">
						<ProjectManager 
							mode="inline"
							onOpenProject={handleInlineOpenProject}
						/>
					</section>
				{/if}
			</div>

		<div class="bottom-buttons">
			<button class="demo-trigger" onclick={goToDemo} title="See the Prism Principle in action">
				🔮 Try Demo
			</button>
			<button class="observatory-trigger" onclick={goToObservatory} title="Watch AI cognition in real-time">
				🔭 Observatory
			</button>
		</div>

		<footer class="version">v0.1.0</footer>
		</div>
	{/snippet}
</MouseMotes>

<!-- Action Toast -->
{#if actionToast?.show}
	<ActionToast
		actionType={actionToast.actionType}
		success={actionToast.success}
		message={actionToast.message}
		onDismiss={handleDismissToast}
	/>
{/if}

<!-- Confirmation Modal -->
<Modal
	isOpen={confirmModal.show}
	onClose={handleCancel}
	title={confirmModal.title}
	description={confirmModal.message}
>
	<div class="modal-actions">
		<Button variant="ghost" onclick={handleCancel}>Cancel</Button>
		<Button
			variant={confirmModal.destructive ? 'secondary' : 'primary'}
			onclick={handleConfirm}
		>
			{confirmModal.action === 'delete' ? 'Delete' : 'Archive'}
		</Button>
	</div>
</Modal>

<!-- Lens Picker Modal -->
<LensPicker
	isOpen={showLensPicker}
	onClose={handleLensPickerClose}
	onConfirm={handleLensConfirm}
/>

<!-- Chat History Sidebar -->
<ChatHistory
	isOpen={showChatHistory}
	onClose={() => (showChatHistory = false)}
	onNewSession={() => inputBar?.focus()}
/>

<style>
	.home {
		display: flex;
		flex-direction: column;
		min-height: 100vh;
		padding: var(--space-8);
		position: relative;
		/* Note: Removed overflow:hidden - it clips dropdown menus and tooltips */
	}

	.background-aura {
		position: absolute;
		top: 0;
		left: 50%;
		transform: translateX(-50%);
		width: 100%;
		height: 60%;
		background: radial-gradient(
			ellipse 60% 50% at 50% 30%,
			rgba(255, 215, 0, 0.06) 0%,
			rgba(218, 165, 32, 0.03) 30%,
			transparent 60%
		);
		pointer-events: none;
		z-index: 0;
	}

	.ambient-motes {
		position: absolute;
		top: 15%;
		left: 50%;
		transform: translateX(-50%);
		width: 500px;
		height: 300px;
		pointer-events: none;
		z-index: 1;
	}

	.hero {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: flex-start;
		gap: var(--space-6);
		padding-top: 12vh;
		animation: fadeIn 0.3s ease;
		position: relative;
		z-index: 2;
	}

	.logo-container {
		position: relative;
	}

	.logo-sparkles {
		position: absolute;
		bottom: 100%;
		left: 50%;
		transform: translateX(-50%);
		opacity: 0.6;
		pointer-events: none;
	}

	.input-section {
		width: 100%;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--space-2);
		margin-top: var(--space-6);
	}

	.lens-indicator {
		animation: fadeIn 0.2s ease;
	}

	.response-surface {
		width: 100%;
		max-width: 1100px;
		margin-top: var(--space-4);
	}

	.contextual-blocks {
		width: 100%;
		max-width: 600px;
		margin-top: var(--space-6);
		animation: fadeIn 0.3s ease;
	}

	.version {
		position: fixed;
		bottom: var(--space-4);
		right: var(--space-4);
		color: var(--text-tertiary);
		font-size: var(--text-xs);
		z-index: 2;
	}

	.bottom-buttons {
		position: fixed;
		bottom: var(--space-4);
		left: var(--space-4);
		display: flex;
		gap: var(--space-2);
		z-index: 10;
	}

	.demo-trigger,
	.observatory-trigger {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		padding: var(--space-2) var(--space-4);
		font-family: var(--font-mono);
		font-size: var(--text-sm);
		font-weight: 500;
		color: var(--text-secondary);
		background: rgba(201, 162, 39, 0.08);
		border: 1px solid rgba(201, 162, 39, 0.2);
		border-radius: var(--radius-md);
		cursor: pointer;
		transition: all var(--transition-fast);
	}

	.demo-trigger:hover,
	.observatory-trigger:hover {
		color: var(--text-gold);
		background: rgba(201, 162, 39, 0.15);
		border-color: rgba(201, 162, 39, 0.4);
		box-shadow: var(--glow-gold-subtle);
	}

	.demo-trigger:focus-visible,
	.observatory-trigger:focus-visible {
		outline: 2px solid var(--border-emphasis);
		outline-offset: 2px;
	}

	@keyframes fadeIn {
		from {
			opacity: 0;
			transform: translateY(10px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	.history-toggle {
		position: fixed;
		top: var(--space-4);
		left: var(--space-4);
		display: flex;
		align-items: center;
		gap: var(--space-1);
		padding: var(--space-2) var(--space-3);
		background: rgba(255, 255, 255, 0.05);
		border: 1px solid var(--border-subtle);
		border-radius: var(--radius-md);
		color: var(--text-secondary);
		font-size: var(--text-sm);
		cursor: pointer;
		transition: all 0.15s ease;
		z-index: 10;
	}

	.history-toggle:hover {
		background: rgba(255, 215, 0, 0.1);
		border-color: rgba(255, 215, 0, 0.3);
		color: var(--text-gold);
	}

	.history-toggle:focus-visible {
		outline: 2px solid var(--border-emphasis);
		outline-offset: 2px;
	}

	.history-count {
		background: rgba(255, 215, 0, 0.2);
		color: var(--text-gold);
		padding: 0 var(--space-1);
		border-radius: var(--radius-sm);
		font-size: var(--text-xs);
		min-width: 1.2em;
		text-align: center;
	}
</style>
