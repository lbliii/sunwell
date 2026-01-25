/**
 * Workspace Components (RFC-103, RFC-140)
 *
 * RFC-103: Workspace-aware scanning:
 * - WorkspaceToast: Non-blocking setup notification
 * - ProjectCard: Detected project representation
 * - DriftBadge: Drift status indicator
 *
 * RFC-140: Workspace management:
 * - WorkspaceSwitcher: Quick workspace switching dropdown
 * - WorkspaceDiscovery: Full-page discovery interface
 * - WorkspaceList: Unified workspace listing
 * - WorkspaceStatusBadge: Current workspace badge
 * - CurrentWorkspaceIndicator: Header workspace indicator
 */

export { default as WorkspaceToast } from './WorkspaceToast.svelte';
export { default as ProjectCard } from './ProjectCard.svelte';
export { default as DriftBadge } from './DriftBadge.svelte';
export { default as WorkspaceSwitcher } from './WorkspaceSwitcher.svelte';
export { default as WorkspaceDiscovery } from './WorkspaceDiscovery.svelte';
export { default as WorkspaceList } from './WorkspaceList.svelte';
export { default as WorkspaceStatusBadge } from './WorkspaceStatusBadge.svelte';
export { default as CurrentWorkspaceIndicator } from './CurrentWorkspaceIndicator.svelte';
