/**
 * Project store tests — verify CRUD operations and error handling
 *
 * Tests that the project store properly handles API interactions,
 * error states, and concurrent operation prevention.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
	project,
	loadRecentProjects,
	scanProjects,
	openProject,
	closeProject,
	deleteProject,
	archiveProject,
	createProject,
	analyzeProject,
	clearAnalysis,
} from './project.svelte';

// Mock the socket module
vi.mock('$lib/socket', () => ({
	apiGet: vi.fn(),
	apiPost: vi.fn(),
}));

// Import mocked functions for configuration
import { apiGet, apiPost } from '$lib/socket';
const mockApiGet = apiGet as ReturnType<typeof vi.fn>;
const mockApiPost = apiPost as ReturnType<typeof vi.fn>;

// Mock the indexing module
vi.mock('./indexing.svelte', () => ({
	initIndexing: vi.fn(),
	stopIndexing: vi.fn(),
}));

describe('project store', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		// Reset project state by closing any open project
		closeProject();
	});

	// ═══════════════════════════════════════════════════════════════════════════
	// LOAD RECENT PROJECTS
	// ═══════════════════════════════════════════════════════════════════════════

	describe('loadRecentProjects', () => {
		it('loads recent projects from API', async () => {
			const mockRecent = [
				{ path: '/path/to/project1', name: 'project1', project_type: 'code_python', description: 'Test 1', last_opened: Date.now() },
				{ path: '/path/to/project2', name: 'project2', project_type: 'code_js', description: 'Test 2', last_opened: Date.now() - 1000 },
			];
			mockApiGet.mockResolvedValueOnce({ recent: mockRecent });

			await loadRecentProjects();

			expect(mockApiGet).toHaveBeenCalledWith('/api/project/recent');
			expect(project.recent).toHaveLength(2);
			expect(project.recent[0].name).toBe('project1');
		});

		it('handles empty recent projects', async () => {
			mockApiGet.mockResolvedValueOnce({ recent: [] });

			await loadRecentProjects();

			expect(project.recent).toHaveLength(0);
		});

		it('handles API error gracefully', async () => {
			mockApiGet.mockRejectedValueOnce(new Error('Network error'));

			await loadRecentProjects();

			expect(project.error).toBe('Network error');
			expect(project.recent).toHaveLength(0);
		});

		it('prevents concurrent loads', async () => {
			mockApiGet.mockImplementation(() => new Promise((resolve) => setTimeout(() => resolve({ recent: [] }), 100)));

			// Start two loads
			const load1 = loadRecentProjects();
			const load2 = loadRecentProjects();

			await Promise.all([load1, load2]);

			// Should only have called API once
			expect(mockApiGet).toHaveBeenCalledTimes(1);
		});
	});

	// ═══════════════════════════════════════════════════════════════════════════
	// SCAN PROJECTS
	// ═══════════════════════════════════════════════════════════════════════════

	describe('scanProjects', () => {
		it('scans and discovers projects', async () => {
			const mockDiscovered = [
				{ id: '1', path: '/path/1', display_path: '~/path/1', name: 'proj1', status: 'none', last_goal: null, tasks_completed: null, tasks_total: null, tasks: null, last_activity: null },
				{ id: '2', path: '/path/2', display_path: '~/path/2', name: 'proj2', status: 'complete', last_goal: 'Build app', tasks_completed: 5, tasks_total: 5, tasks: null, last_activity: null },
			];
			mockApiGet.mockResolvedValueOnce({ projects: mockDiscovered });

			await scanProjects();

			expect(mockApiGet).toHaveBeenCalledWith('/api/project/scan');
			expect(project.discovered).toHaveLength(2);
			expect(project.discovered[1].status).toBe('complete');
		});

		it('handles scan error gracefully', async () => {
			mockApiGet.mockRejectedValueOnce(new Error('Scan failed'));

			await scanProjects();

			expect(project.error).toBe('Scan failed');
		});

		it('prevents concurrent scans', async () => {
			mockApiGet.mockImplementation(() => new Promise((resolve) => setTimeout(() => resolve({ projects: [] }), 100)));

			const scan1 = scanProjects();
			const scan2 = scanProjects();

			await Promise.all([scan1, scan2]);

			expect(mockApiGet).toHaveBeenCalledTimes(1);
		});
	});

	// ═══════════════════════════════════════════════════════════════════════════
	// OPEN PROJECT
	// ═══════════════════════════════════════════════════════════════════════════

	describe('openProject', () => {
		it('opens project and sets current', async () => {
			const mockProject = {
				id: 'proj-123',
				path: '/path/to/project',
				name: 'my-project',
				project_type: 'code_python',
				description: 'A test project',
				files_count: 42,
			};
			mockApiPost.mockResolvedValueOnce(mockProject);

			const result = await openProject('/path/to/project');

			expect(mockApiPost).toHaveBeenCalledWith('/api/project/open', { path: '/path/to/project' });
			expect(result).toEqual(mockProject);
			expect(project.current).toEqual(mockProject);
			expect(project.hasProject).toBe(true);
			expect(project.currentPath).toBe('/path/to/project');
		});

		it('handles open error gracefully', async () => {
			mockApiPost.mockRejectedValueOnce(new Error('Project not found'));

			const result = await openProject('/nonexistent/path');

			expect(result).toBeNull();
			expect(project.error).toBe('Project not found');
			expect(project.hasProject).toBe(false);
		});

		it('starts indexing after opening project', async () => {
			const { initIndexing } = await import('./indexing.svelte');
			const mockProject = { id: '1', path: '/path', name: 'test', project_type: 'general', files_count: 0 };
			mockApiPost.mockResolvedValueOnce(mockProject);

			await openProject('/path');

			expect(initIndexing).toHaveBeenCalledWith('/path');
		});
	});

	// ═══════════════════════════════════════════════════════════════════════════
	// CLOSE PROJECT
	// ═══════════════════════════════════════════════════════════════════════════

	describe('closeProject', () => {
		it('clears current project', async () => {
			const mockProject = { id: '1', path: '/path', name: 'test', project_type: 'general', files_count: 0 };
			mockApiPost.mockResolvedValueOnce(mockProject);
			await openProject('/path');

			expect(project.hasProject).toBe(true);

			closeProject();

			expect(project.current).toBeNull();
			expect(project.hasProject).toBe(false);
		});

		it('stops indexing when closing project', async () => {
			const { stopIndexing } = await import('./indexing.svelte');
			const mockProject = { id: '1', path: '/path', name: 'test', project_type: 'general', files_count: 0 };
			mockApiPost.mockResolvedValueOnce(mockProject);
			await openProject('/path');

			closeProject();

			expect(stopIndexing).toHaveBeenCalled();
		});
	});

	// ═══════════════════════════════════════════════════════════════════════════
	// CREATE PROJECT
	// ═══════════════════════════════════════════════════════════════════════════

	describe('createProject', () => {
		it('creates temporary project from goal', () => {
			const proj = createProject('Build a REST API');

			expect(proj.id).toMatch(/^temp-/);
			expect(proj.name).toBe('build-a-rest-api');
			expect(proj.description).toBe('Build a REST API');
			expect(project.current).toEqual(proj);
		});

		it('sanitizes goal for project name', () => {
			const proj = createProject('Create a "Hello, World!" app with spaces & symbols!!!');

			// Should be lowercase, alphanumeric with hyphens, max 30 chars
			expect(proj.name).toMatch(/^[a-z0-9-]+$/);
			expect(proj.name.length).toBeLessThanOrEqual(30);
		});

		it('handles empty goal gracefully', () => {
			const proj = createProject('');

			expect(proj.name).toBe('new-project');
		});
	});

	// ═══════════════════════════════════════════════════════════════════════════
	// DELETE PROJECT
	// ═══════════════════════════════════════════════════════════════════════════

	describe('deleteProject', () => {
		it('deletes project and rescans', async () => {
			mockApiPost.mockResolvedValueOnce({ success: true, message: 'Deleted', new_path: null });
			mockApiGet.mockResolvedValueOnce({ projects: [] }); // For rescan

			const result = await deleteProject('/path/to/delete');

			expect(mockApiPost).toHaveBeenCalledWith('/api/project/delete', { path: '/path/to/delete' });
			expect(result.success).toBe(true);
		});

		it('handles delete failure', async () => {
			mockApiPost.mockRejectedValueOnce(new Error('Permission denied'));

			const result = await deleteProject('/protected/path');

			expect(result.success).toBe(false);
			expect(result.message).toBe('Permission denied');
		});
	});

	// ═══════════════════════════════════════════════════════════════════════════
	// ARCHIVE PROJECT
	// ═══════════════════════════════════════════════════════════════════════════

	describe('archiveProject', () => {
		it('archives project successfully', async () => {
			mockApiPost.mockResolvedValueOnce({ success: true, message: 'Archived', new_path: '/archive/project' });
			mockApiGet.mockResolvedValueOnce({ projects: [] }); // For rescan

			const result = await archiveProject('/path/to/archive');

			expect(mockApiPost).toHaveBeenCalledWith('/api/project/archive', { path: '/path/to/archive' });
			expect(result.success).toBe(true);
			expect(result.new_path).toBe('/archive/project');
		});
	});

	// ═══════════════════════════════════════════════════════════════════════════
	// PROJECT ANALYSIS
	// ═══════════════════════════════════════════════════════════════════════════

	describe('analyzeProject', () => {
		it('analyzes project and stores result', async () => {
			const mockAnalysis = {
				project_type: 'code',
				suggested_workspace_primary: 'CodeEditor',
				confidence: 0.95,
				confidence_level: 'high',
			};
			mockApiPost.mockResolvedValueOnce(mockAnalysis);

			const result = await analyzeProject('/path/to/analyze');

			expect(mockApiPost).toHaveBeenCalledWith('/api/project/analyze', { path: '/path/to/analyze', fresh: false });
			expect(result).toEqual(mockAnalysis);
			expect(project.analysis).toEqual(mockAnalysis);
			expect(project.hasAnalysis).toBe(true);
			expect(project.confidence).toBe(0.95);
		});

		it('can force fresh analysis', async () => {
			mockApiPost.mockResolvedValueOnce({ project_type: 'code', confidence: 0.9, confidence_level: 'high' });

			await analyzeProject('/path', true);

			expect(mockApiPost).toHaveBeenCalledWith('/api/project/analyze', { path: '/path', fresh: true });
		});

		it('handles analysis error', async () => {
			mockApiPost.mockRejectedValueOnce(new Error('Analysis failed'));

			const result = await analyzeProject('/path/to/analyze');

			expect(result).toBeNull();
			expect(project.analysisError).toBe('Analysis failed');
		});

		it('prevents concurrent analyses', async () => {
			mockApiPost.mockImplementation(() => new Promise((resolve) => setTimeout(() => resolve({ project_type: 'code', confidence: 0.9 }), 100)));

			const analysis1 = analyzeProject('/path1');
			const analysis2 = analyzeProject('/path2');

			await Promise.all([analysis1, analysis2]);

			// Second call should return cached result, not make new API call
			expect(mockApiPost).toHaveBeenCalledTimes(1);
		});
	});

	describe('clearAnalysis', () => {
		it('clears analysis state', async () => {
			mockApiPost.mockResolvedValueOnce({ project_type: 'code', confidence: 0.9, confidence_level: 'high' });
			await analyzeProject('/path');

			expect(project.hasAnalysis).toBe(true);

			clearAnalysis();

			expect(project.analysis).toBeNull();
			expect(project.hasAnalysis).toBe(false);
			expect(project.analysisError).toBeNull();
		});
	});

	// ═══════════════════════════════════════════════════════════════════════════
	// COMPUTED PROPERTIES
	// ═══════════════════════════════════════════════════════════════════════════

	describe('computed properties', () => {
		it('isCodeProject returns true for code types', async () => {
			mockApiPost.mockResolvedValueOnce({ id: '1', path: '/path', name: 'test', project_type: 'code_python', files_count: 0 });
			await openProject('/path');

			expect(project.isCodeProject).toBe(true);
		});

		it('isCreativeProject returns true for creative types', async () => {
			mockApiPost.mockResolvedValueOnce({ id: '1', path: '/path', name: 'test', project_type: 'novel', files_count: 0 });
			await openProject('/path');

			expect(project.isCreativeProject).toBe(true);
		});

		it('currentId returns project id when project is open', async () => {
			mockApiPost.mockResolvedValueOnce({ id: 'proj-456', path: '/path', name: 'test', project_type: 'general', files_count: 0 });
			await openProject('/path');

			expect(project.currentId).toBe('proj-456');
		});

		it('currentId returns null when no project', () => {
			expect(project.currentId).toBeNull();
		});
	});
});
