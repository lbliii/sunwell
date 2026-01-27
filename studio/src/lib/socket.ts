/**
 * HTTP and WebSocket API utilities for Sunwell Studio.
 * 
 * Provides a unified interface for communicating with the Python backend.
 */

// API base URL - uses Vite dev server proxy in dev, relative path in prod
const API_BASE = '';

// ============================================================================
// Types
// ============================================================================

export interface AgentEvent {
  type: string;
  data: Record<string, unknown>;
  timestamp?: string;
}

export interface BusEvent {
  v: 1;
  run_id: string;
  type: string;
  data: Record<string, unknown>;
  timestamp: string;
  source: string;
  project_id?: string;
}

export type EventCallback = (event: AgentEvent) => void;

// ============================================================================
// HTTP API
// ============================================================================

/**
 * Make a GET request to the API.
 */
export async function apiGet<T>(endpoint: string): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Make a POST request to the API.
 */
export async function apiPost<T, R = unknown>(endpoint: string, data?: T): Promise<R> {
  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: data ? JSON.stringify(data) : undefined,
  });
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Make a DELETE request to the API.
 */
export async function apiDelete<T>(endpoint: string): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
    },
  });
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  
  return response.json();
}

// ============================================================================
// WebSocket Event Stream
// ============================================================================

// Global event listeners
const eventListeners = new Set<EventCallback>();

// WebSocket connection state
let globalSocket: WebSocket | null = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAY_MS = 2000;

/**
 * Get the WebSocket URL for events.
 */
function getWebSocketUrl(projectId?: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  const baseUrl = `${protocol}//${host}/api/events`;
  return projectId ? `${baseUrl}?project_id=${encodeURIComponent(projectId)}` : baseUrl;
}

/**
 * Connect to the global event stream.
 */
export function connectEventStream(projectId?: string): void {
  if (globalSocket?.readyState === WebSocket.OPEN) {
    return; // Already connected
  }
  
  const url = getWebSocketUrl(projectId);
  globalSocket = new WebSocket(url);
  
  globalSocket.onopen = () => {
    console.log('[socket] Connected to event stream');
    reconnectAttempts = 0;
  };
  
  globalSocket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as AgentEvent;
      // Broadcast to all listeners
      eventListeners.forEach((callback) => {
        try {
          callback(data);
        } catch (err) {
          console.error('[socket] Listener error:', err);
        }
      });
    } catch (err) {
      console.error('[socket] Failed to parse event:', err);
    }
  };
  
  globalSocket.onclose = (event) => {
    console.log('[socket] Connection closed:', event.code, event.reason);
    globalSocket = null;
    
    // Attempt reconnection if not a clean close
    if (event.code !== 1000 && reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
      reconnectAttempts++;
      console.log(`[socket] Reconnecting in ${RECONNECT_DELAY_MS}ms (attempt ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);
      setTimeout(() => connectEventStream(projectId), RECONNECT_DELAY_MS);
    }
  };
  
  globalSocket.onerror = (error) => {
    console.error('[socket] WebSocket error:', error);
  };
}

/**
 * Disconnect from the global event stream.
 */
export function disconnectEventStream(): void {
  if (globalSocket) {
    globalSocket.close(1000, 'Client disconnect');
    globalSocket = null;
  }
}

/**
 * Subscribe to events from the global event stream.
 * Returns a cleanup function to unsubscribe.
 */
export function onEvent(callback: EventCallback): () => void {
  eventListeners.add(callback);
  
  // Auto-connect if not already connected
  if (!globalSocket || globalSocket.readyState !== WebSocket.OPEN) {
    connectEventStream();
  }
  
  return () => {
    eventListeners.delete(callback);
  };
}

// ============================================================================
// Run-Specific Event Stream
// ============================================================================

/**
 * Create a WebSocket connection for a specific run.
 * Returns an async generator that yields events.
 */
export async function* streamRunEvents(runId: string): AsyncGenerator<AgentEvent> {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  const url = `${protocol}//${host}/api/run/${runId}/events`;
  
  const socket = new WebSocket(url);
  const eventQueue: AgentEvent[] = [];
  let resolveNext: ((value: AgentEvent | null) => void) | null = null;
  let closed = false;
  
  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as AgentEvent;
      if (resolveNext) {
        resolveNext(data);
        resolveNext = null;
      } else {
        eventQueue.push(data);
      }
    } catch (err) {
      console.error('[socket] Failed to parse run event:', err);
    }
  };
  
  socket.onclose = () => {
    closed = true;
    if (resolveNext) {
      resolveNext(null);
      resolveNext = null;
    }
  };
  
  socket.onerror = (error) => {
    console.error('[socket] Run WebSocket error:', error);
    closed = true;
    if (resolveNext) {
      resolveNext(null);
      resolveNext = null;
    }
  };
  
  // Wait for connection
  await new Promise<void>((resolve, reject) => {
    socket.onopen = () => resolve();
    const errorHandler = () => reject(new Error('Failed to connect'));
    socket.addEventListener('error', errorHandler, { once: true });
  });
  
  try {
    while (!closed) {
      if (eventQueue.length > 0) {
        yield eventQueue.shift()!;
      } else {
        const event = await new Promise<AgentEvent | null>((resolve) => {
          resolveNext = resolve;
        });
        if (event === null) {
          break;
        }
        yield event;
      }
    }
  } finally {
    if (socket.readyState === WebSocket.OPEN) {
      socket.close();
    }
  }
}

// ============================================================================
// API Endpoints
// ============================================================================

// Project API
export interface ScannedProject {
  id: string;
  path: string;
  display_path: string;
  name: string;
  status: string;
  last_goal: string | null;
  tasks_completed: number | null;
  tasks_total: number | null;
  last_activity: string | null;
}

export interface ScanProjectsResponse {
  projects: ScannedProject[];
  total: number;
}

export interface RecentProject {
  path: string;
  name: string;
  project_type: string;
  description: string | null;
  last_opened: number;
}

export interface RecentProjectsResponse {
  recent: RecentProject[];
}

export interface ProjectInfo {
  id: string;
  path: string;
  name: string;
  project_type: string;
  description: string | null;
  files_count: number;
}

export interface CreateProjectRequest {
  name: string;
  path?: string;
}

export interface CreateProjectResponse {
  project: { id?: string; name?: string; root?: string };
  path: string;
  isNew: boolean;
  isDefault: boolean;
  error?: string;
  message?: string;
}

export interface OpenProjectRequest {
  path: string;
}

export interface ListProjectsResponse {
  projects: {
    id: string;
    name: string;
    root: string;
    valid: boolean;
    isDefault: boolean;
    lastUsed: string | null;
  }[];
}

export const projectApi = {
  scan: () => apiGet<ScanProjectsResponse>('/api/project/scan'),
  recent: () => apiGet<RecentProjectsResponse>('/api/project/recent'),
  list: () => apiGet<ListProjectsResponse>('/api/project/list'),
  create: (request: CreateProjectRequest) => apiPost<CreateProjectRequest, CreateProjectResponse>('/api/project/create', request),
  open: (path: string) => apiPost<OpenProjectRequest, { success: boolean; message?: string }>('/api/project/open', { path }),
  openById: (projectId: string) => apiPost<{ project_id: string }, ProjectInfo>('/api/project/open-by-id', { project_id: projectId }),
  getSlug: (path: string) => apiPost<{ path: string }, { slug?: string; error?: string }>('/api/project/slug', { path }),
  resolve: (slug: string) => apiPost<{ slug: string }, { project?: ProjectInfo; error?: string }>('/api/project/resolve', { slug }),
};

// Run API
export interface RunStartResponse {
  run_id: string;
  status: string;
  use_v2: boolean;
}

export interface RunStatusResponse {
  run_id: string;
  status: string;
  goal: string;
  event_count: number;
  error?: string;
}

export interface RunItem {
  run_id: string;
  goal: string;
  status: string;
  source: string;
  started_at: string;
  completed_at: string | null;
  event_count: number;
}

export interface RunsListResponse {
  runs: RunItem[];
}

export interface RunEventsResponse {
  run_id: string;
  events: AgentEvent[];
  error?: string;
}

export interface StartRunRequest {
  goal: string;
  workspace?: string;
  project_id?: string;
  lens?: string;
  provider?: string;
  model?: string;
  trust?: string;
  timeout?: number;
}

export const runApi = {
  start: (request: StartRunRequest) => apiPost<StartRunRequest, RunStartResponse>('/api/run', request),
  status: (runId: string) => apiGet<RunStatusResponse>(`/api/run/${runId}`),
  cancel: (runId: string) => apiDelete<{ status: string }>(`/api/run/${runId}`),
  list: (options?: { project_id?: string; limit?: number }) => {
    const params = new URLSearchParams();
    if (options?.project_id) params.set('project_id', options.project_id);
    if (options?.limit) params.set('limit', options.limit.toString());
    const query = params.toString();
    return apiGet<RunsListResponse>(`/api/runs${query ? `?${query}` : ''}`);
  },
  events: (runId: string) => apiGet<RunEventsResponse>(`/api/run/${runId}/events`),
  history: (options?: { limit?: number; project_id?: string }) => {
    const params = new URLSearchParams();
    if (options?.project_id) params.set('project_id', options.project_id);
    if (options?.limit) params.set('limit', options.limit.toString());
    const query = params.toString();
    return apiGet<RunItem[]>(`/api/run/history${query ? `?${query}` : ''}`);
  },
};

// Observatory API
export interface ObservatoryData {
  run_id: string;
  resonance_iterations?: unknown[];
  prism_candidates?: unknown[];
  selected_candidate?: unknown;
  tasks?: unknown[];
  learnings?: string[];
  convergence_iterations?: unknown[];
  convergence_status?: string;
  error?: string;
}

export const observatoryApi = {
  getData: (runId: string) => apiGet<ObservatoryData>(`/api/observatory/data/${runId}`),
};
