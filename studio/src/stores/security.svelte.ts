/**
 * Security State Store (RFC-089)
 *
 * Manages security-related state for the Studio frontend:
 * - Pending approval requests
 * - Security violations
 * - Session approvals (remembered permissions)
 * - Audit log entries
 */

import { apiGet, apiPost } from '$lib/socket';
import type {
  SecurityApprovalDetailed,
  SecurityApprovalResponse,
  SecurityViolation,
  PermissionScope,
  AuditEntryDisplay,
  RiskLevel,
} from '$lib/security-types';

// =============================================================================
// STATE
// =============================================================================

interface SecurityState {
  /** Currently pending approval request (shown in modal). */
  pendingApproval: SecurityApprovalDetailed | null;

  /** Security violations detected during execution. */
  violations: SecurityViolation[];

  /** Session-level approvals (dagId → approved scope). */
  sessionApprovals: Map<string, PermissionScope>;

  /** Recent audit log entries. */
  auditEntries: AuditEntryDisplay[];

  /** Whether the audit log has been verified. */
  auditVerified: boolean | null;

  /** Audit verification message. */
  auditVerificationMessage: string;

  /** Loading states. */
  isLoading: boolean;
  isLoadingAudit: boolean;
}

const initialState: SecurityState = {
  pendingApproval: null,
  violations: [],
  sessionApprovals: new Map(),
  auditEntries: [],
  auditVerified: null,
  auditVerificationMessage: '',
  isLoading: false,
  isLoadingAudit: false,
};

let _state = $state<SecurityState>({ ...initialState });

// =============================================================================
// REACTIVE GETTERS
// =============================================================================

export const securityState = {
  /** Currently pending approval request. */
  get pendingApproval() {
    return _state.pendingApproval;
  },

  /** All detected violations. */
  get violations() {
    return _state.violations;
  },

  /** Session-level approvals. */
  get sessionApprovals() {
    return _state.sessionApprovals;
  },

  /** Recent audit entries. */
  get auditEntries() {
    return _state.auditEntries;
  },

  /** Whether there are unacknowledged violations. */
  get hasUnacknowledgedViolations() {
    return _state.violations.some((v) => !v.acknowledged);
  },

  /** Total violation count. */
  get violationCount() {
    return _state.violations.length;
  },

  /** Whether audit has been verified. */
  get auditVerified() {
    return _state.auditVerified;
  },

  /** Audit verification message. */
  get auditVerificationMessage() {
    return _state.auditVerificationMessage;
  },

  /** Loading state. */
  get isLoading() {
    return _state.isLoading;
  },

  /** Loading audit state. */
  get isLoadingAudit() {
    return _state.isLoadingAudit;
  },

  /** Count of violations by risk level. */
  get violationsByLevel(): Record<RiskLevel, number> {
    const counts: Record<RiskLevel, number> = {
      low: 0,
      medium: 0,
      high: 0,
      critical: 0,
    };

    for (const v of _state.violations) {
      // Classify based on violation type
      if (v.violationType === 'credential_leak' || v.violationType === 'shell_injection') {
        counts.critical++;
      } else if (v.violationType === 'path_traversal' || v.violationType === 'network_exfil') {
        counts.high++;
      } else if (v.violationType === 'pii_exposure') {
        counts.medium++;
      } else {
        counts.low++;
      }
    }

    return counts;
  },
};

// =============================================================================
// ACTIONS
// =============================================================================

/**
 * Set a pending approval request (shows modal).
 */
export function setPendingApproval(approval: SecurityApprovalDetailed | null): void {
  _state = { ..._state, pendingApproval: approval };
}

/**
 * Add a security violation.
 */
export function addSecurityViolation(violation: SecurityViolation): void {
  _state = {
    ..._state,
    violations: [..._state.violations, violation],
  };
}

/**
 * Mark a violation as acknowledged.
 */
export function acknowledgeViolation(index: number): void {
  const violations = [..._state.violations];
  if (violations[index]) {
    violations[index] = { ...violations[index], acknowledged: true };
    _state = { ..._state, violations };
  }
}

/**
 * Remember an approval for the session.
 */
export function rememberApprovalForSession(dagId: string, scope: PermissionScope): void {
  const newApprovals = new Map(_state.sessionApprovals);
  newApprovals.set(dagId, scope);
  _state = { ..._state, sessionApprovals: newApprovals };
}

/**
 * Check if a DAG has been approved for this session.
 */
export function isApprovedForSession(dagId: string): boolean {
  return _state.sessionApprovals.has(dagId);
}

/**
 * Get the session approval for a DAG.
 */
export function getSessionApproval(dagId: string): PermissionScope | undefined {
  return _state.sessionApprovals.get(dagId);
}

/**
 * Set audit entries.
 */
export function setAuditEntries(entries: AuditEntryDisplay[]): void {
  _state = { ..._state, auditEntries: entries };
}

/**
 * Clear all violations.
 */
export function clearViolations(): void {
  _state = { ..._state, violations: [] };
}

/**
 * Reset all security state.
 */
export function resetSecurityState(): void {
  _state = { ...initialState };
}

// =============================================================================
// TAURI INTEGRATION
// =============================================================================

/**
 * Analyze DAG permissions before execution.
 */
export async function analyzeDagPermissions(dagId: string): Promise<SecurityApprovalDetailed> {
  _state = { ..._state, isLoading: true };

  try {
    const approval = await invoke<SecurityApprovalDetailed>('analyze_dag_permissions', { dagId });
    setPendingApproval(approval);
    return approval;
  } finally {
    _state = { ..._state, isLoading: false };
  }
}

/**
 * Submit security approval response.
 */
export async function submitApproval(response: SecurityApprovalResponse): Promise<boolean> {
  _state = { ..._state, isLoading: true };

  try {
    const success = await invoke<boolean>('submit_security_approval', { response });

    if (success && response.approved && response.rememberForSession) {
      rememberApprovalForSession(
        response.dagId,
        response.modifiedPermissions ||
          _state.pendingApproval?.permissions || {
            filesystemRead: [],
            filesystemWrite: [],
            networkAllow: [],
            networkDeny: ['*'],
            shellAllow: [],
            shellDeny: [],
            envRead: [],
            envWrite: [],
          }
      );
    }

    setPendingApproval(null);
    return success;
  } finally {
    _state = { ..._state, isLoading: false };
  }
}

/**
 * Load recent audit log entries.
 */
export async function loadAuditLog(limit: number = 50): Promise<void> {
  _state = { ..._state, isLoadingAudit: true };

  try {
    const entries = await invoke<AuditEntryDisplay[]>('get_audit_log', { limit });
    setAuditEntries(entries);
  } catch (error) {
    console.error('Failed to load audit log:', error);
    setAuditEntries([]);
  } finally {
    _state = { ..._state, isLoadingAudit: false };
  }
}

/**
 * Verify audit log integrity.
 */
export async function verifyAuditIntegrity(): Promise<{ valid: boolean; message: string }> {
  _state = { ..._state, isLoadingAudit: true };

  try {
    const result = await invoke<{ valid: boolean; message: string }>('verify_audit_integrity');
    _state = {
      ..._state,
      auditVerified: result.valid,
      auditVerificationMessage: result.message,
    };
    return result;
  } catch (error) {
    const message = `Verification failed: ${error}`;
    _state = {
      ..._state,
      auditVerified: false,
      auditVerificationMessage: message,
    };
    return { valid: false, message };
  } finally {
    _state = { ..._state, isLoadingAudit: false };
  }
}

/**
 * Scan content for security issues.
 */
export async function scanForSecurityIssues(content: string): Promise<SecurityViolation[]> {
  try {
    const violations = await invoke<SecurityViolation[]>('scan_for_security_issues', { content });

    // Add to state
    for (const violation of violations) {
      addSecurityViolation(violation);
    }

    return violations;
  } catch (error) {
    console.error('Failed to scan for security issues:', error);
    return [];
  }
}

// =============================================================================
// EVENT HANDLERS
// =============================================================================

/**
 * Handle security-related agent events.
 */
export function handleSecurityEvent(
  type: string,
  data: Record<string, unknown>
): string | null {
  switch (type) {
    case 'security_approval_requested': {
      const dagId = (data.dag_id as string) ?? '';
      const dagName = (data.dag_name as string) ?? '';
      const skillCount = (data.skill_count as number) ?? 0;
      const riskLevel = (data.risk_level as string) ?? 'low';
      const flags = (data.flags as string[]) ?? [];

      // Create approval object for modal
      const approval: SecurityApprovalDetailed = {
        dagId,
        dagName,
        skillCount,
        permissions: {
          filesystemRead: [],
          filesystemWrite: [],
          networkAllow: [],
          networkDeny: ['*'],
          shellAllow: [],
          shellDeny: [],
          envRead: [],
          envWrite: [],
        },
        risk: {
          level: riskLevel as RiskLevel,
          score: (data.risk_score as number) ?? 0,
          flags,
          recommendations: [],
        },
        timestamp: new Date().toISOString(),
        skillBreakdown: [],
      };

      setPendingApproval(approval);
      return `🔒 Security review: ${riskLevel.toUpperCase()} risk (${flags.length} flags)`;
    }

    case 'security_violation': {
      const skillName = (data.skill_name as string) ?? '';
      const violationType = (data.violation_type as string) ?? '';
      const evidence = (data.evidence as string) ?? '';
      const detectionMethod = (data.detection_method as string) ?? 'deterministic';
      const actionTaken = (data.action_taken as string) ?? 'logged';

      addSecurityViolation({
        skillName,
        violationType,
        evidence,
        position: 0,
        detectionMethod: detectionMethod as 'deterministic' | 'llm',
        timestamp: new Date().toISOString(),
      });

      const icon = actionTaken === 'aborted' ? '🛑' : '⚠️';
      return `${icon} Security: ${violationType} in ${skillName} (${actionTaken})`;
    }

    case 'security_scan_complete': {
      const violations = (data.violations_found as number) ?? 0;
      const icon = violations > 0 ? '⚠️' : '✅';
      return `${icon} Security scan: ${violations} violations found`;
    }

    case 'audit_log_entry': {
      // Refresh audit log when new entry is added
      loadAuditLog();
      return null; // No visible message needed
    }

    default:
      return null;
  }
}
