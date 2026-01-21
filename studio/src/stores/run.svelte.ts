/**
 * Run Store — manages active run sessions (Svelte 5 runes)
 * 
 * Tracks running processes and handles port readiness detection
 * for auto-opening Preview when dev servers start.
 */

import type { RunSession } from '$lib/types';

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

let _activeSession = $state<RunSession | null>(null);
let _previewUrl = $state<string | null>(null);
let _isPortReady = $state(false);
let _isCheckingPort = $state(false);

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const runStore = {
  get activeSession() { return _activeSession; },
  get previewUrl() { return _previewUrl; },
  get isPortReady() { return _isPortReady; },
  get isCheckingPort() { return _isCheckingPort; },
  get isRunning() { return _activeSession !== null; },
  get hasPreviewUrl() { return _previewUrl !== null; },
};

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Set the active run session and start port readiness check if URL is provided.
 */
export function setActiveSession(session: RunSession | null, expectedUrl?: string): void {
  _activeSession = session;
  _previewUrl = expectedUrl ?? null;
  _isPortReady = false;
  
  if (session && expectedUrl) {
    startPortReadinessCheck(expectedUrl);
  }
}

/**
 * Clear the active session (on stop).
 */
export function clearActiveSession(): void {
  _activeSession = null;
  _previewUrl = null;
  _isPortReady = false;
  _isCheckingPort = false;
}

/**
 * Set preview URL for when navigating to Preview.
 */
export function setPreviewUrl(url: string | null): void {
  _previewUrl = url;
}

/**
 * Mark port as ready (triggers auto-navigation).
 */
export function markPortReady(): void {
  _isPortReady = true;
}

// ═══════════════════════════════════════════════════════════════
// PORT READINESS DETECTION
// ═══════════════════════════════════════════════════════════════

let portCheckInterval: ReturnType<typeof setInterval> | null = null;

/**
 * Start polling to detect when the server is ready.
 * Uses fetch HEAD request to check if the URL responds.
 */
function startPortReadinessCheck(url: string): void {
  // Clear any existing interval
  if (portCheckInterval) {
    clearInterval(portCheckInterval);
  }
  
  _isCheckingPort = true;
  _isPortReady = false;
  
  let attempts = 0;
  const maxAttempts = 60; // Try for 60 seconds
  
  portCheckInterval = setInterval(async () => {
    attempts++;
    
    // Check if session was stopped
    if (!_activeSession) {
      stopPortReadinessCheck();
      return;
    }
    
    // Give up after max attempts
    if (attempts > maxAttempts) {
      console.log(`Port readiness check timed out after ${maxAttempts}s`);
      stopPortReadinessCheck();
      return;
    }
    
    try {
      // Use fetch with a short timeout to check if server responds
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 1000);
      
      await fetch(url, {
        method: 'HEAD',
        mode: 'no-cors', // We just want to know if it responds
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);
      
      // If we get here, the server is responding!
      console.log(`Server ready at ${url}`);
      _isPortReady = true;
      stopPortReadinessCheck();
    } catch {
      // Server not ready yet, keep polling
      console.log(`Waiting for server at ${url}... (attempt ${attempts})`);
    }
  }, 1000);
}

/**
 * Stop the port readiness check.
 */
function stopPortReadinessCheck(): void {
  if (portCheckInterval) {
    clearInterval(portCheckInterval);
    portCheckInterval = null;
  }
  _isCheckingPort = false;
}
