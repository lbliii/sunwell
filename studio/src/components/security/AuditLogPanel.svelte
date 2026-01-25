<!--
  AuditLogPanel.svelte — Security audit log viewer (RFC-089)
  
  Displays recent security audit entries with integrity verification.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import type { AuditEntryDisplay, AuditAction, RiskLevel } from '$lib/security-types';
  import { getActionIcon, getRiskColor } from '$lib/security-types';
  import {
    securityState,
    loadAuditLog,
    verifyAuditIntegrity,
  } from '../../stores/security.svelte';

  let isRefreshing = $state(false);
  let isVerifying = $state(false);

  const actionClasses: Record<AuditAction, string> = {
    execute: 'text-green-400',
    violation: 'text-red-400',
    denied: 'text-orange-400',
    error: 'text-yellow-400',
  };

  const riskBadgeClasses: Record<RiskLevel, string> = {
    low: 'bg-green-500/20 text-green-400',
    medium: 'bg-yellow-500/20 text-yellow-400',
    high: 'bg-orange-500/20 text-orange-400',
    critical: 'bg-red-500/20 text-red-400',
  };

  onMount(async () => {
    await loadAuditLog(50);
    await verifyAuditIntegrity();
  });

  async function handleRefresh() {
    isRefreshing = true;
    try {
      await loadAuditLog(50);
    } finally {
      isRefreshing = false;
    }
  }

  async function handleVerify() {
    isVerifying = true;
    try {
      await verifyAuditIntegrity();
    } finally {
      isVerifying = false;
    }
  }

  function formatTimestamp(ts: string): string {
    try {
      const date = new Date(ts);
      return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return ts;
    }
  }
</script>

<div class="flex flex-col h-full bg-zinc-900 rounded-lg border border-zinc-700">
  <!-- Header -->
  <div class="flex items-center justify-between p-4 border-b border-zinc-700">
    <div class="flex items-center gap-3">
      <span class="text-xl">🔐</span>
      <h3 class="text-lg font-semibold text-zinc-100">Security Audit Log</h3>
    </div>

    <div class="flex items-center gap-2">
      <!-- Integrity Status -->
      {#if securityState.auditVerified !== null}
        <div
          class="flex items-center gap-2 px-3 py-1 rounded-full text-sm {securityState.auditVerified
            ? 'bg-green-500/20 text-green-400'
            : 'bg-red-500/20 text-red-400'}"
        >
          {#if securityState.auditVerified}
            <span>✓</span>
            <span>Integrity verified</span>
          {:else}
            <span>⚠️</span>
            <span>Integrity issue</span>
          {/if}
        </div>
      {/if}

      <!-- Verify Button -->
      <button
        onclick={handleVerify}
        disabled={isVerifying}
        class="p-2 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 disabled:opacity-50 transition-colors"
        title="Verify integrity"
      >
        {#if isVerifying}
          <svg
            class="w-5 h-5 animate-spin"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
          >
            <circle
              cx="12"
              cy="12"
              r="10"
              stroke-width="2"
              stroke-dasharray="60"
              stroke-linecap="round"
            />
          </svg>
        {:else}
          <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
            />
          </svg>
        {/if}
      </button>

      <!-- Refresh Button -->
      <button
        onclick={handleRefresh}
        disabled={isRefreshing}
        class="p-2 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 disabled:opacity-50 transition-colors"
        title="Refresh"
      >
        {#if isRefreshing}
          <svg
            class="w-5 h-5 animate-spin"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
          >
            <circle
              cx="12"
              cy="12"
              r="10"
              stroke-width="2"
              stroke-dasharray="60"
              stroke-linecap="round"
            />
          </svg>
        {:else}
          <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
        {/if}
      </button>
    </div>
  </div>

  <!-- Integrity Message -->
  {#if securityState.auditVerificationMessage && !securityState.auditVerified}
    <div class="p-3 mx-4 mt-4 rounded-lg bg-red-500/10 border border-red-500/30">
      <p class="text-sm text-red-400">{securityState.auditVerificationMessage}</p>
    </div>
  {/if}

  <!-- Entries List -->
  <div class="flex-1 overflow-y-auto">
    {#if securityState.isLoadingAudit}
      <div class="flex items-center justify-center h-32">
        <div class="text-zinc-500">Loading audit log...</div>
      </div>
    {:else if securityState.auditEntries.length === 0}
      <div class="flex flex-col items-center justify-center h-32 gap-2">
        <span class="text-3xl">📜</span>
        <p class="text-zinc-500">No audit entries yet</p>
      </div>
    {:else}
      <div class="divide-y divide-zinc-800">
        {#each securityState.auditEntries as entry (entry.timestamp)}
          <div
            class="p-4 hover:bg-zinc-800/50 transition-colors {entry.action === 'violation'
              ? 'bg-red-500/5'
              : ''}"
          >
            <div class="flex items-start gap-3">
              <!-- Icon -->
              <span class="text-lg">{getActionIcon(entry.action)}</span>

              <!-- Content -->
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 flex-wrap">
                  <!-- Timestamp -->
                  <span class="text-xs text-zinc-500">
                    {formatTimestamp(entry.timestamp)}
                  </span>

                  <!-- Skill Name -->
                  <span class="text-sm font-medium text-zinc-300">
                    {entry.skillName}
                  </span>

                  <!-- Risk Badge -->
                  <span
                    class="px-2 py-0.5 text-xs rounded-full {riskBadgeClasses[
                      entry.riskLevel as RiskLevel
                    ] || riskBadgeClasses.low}"
                  >
                    {entry.riskLevel}
                  </span>
                </div>

                <!-- Details -->
                <p class="mt-1 text-sm text-zinc-400 truncate">
                  {entry.details}
                </p>
              </div>

              <!-- Action Badge -->
              <span
                class="px-2 py-1 text-xs font-medium rounded uppercase {actionClasses[
                  entry.action
                ]}"
              >
                {entry.action}
              </span>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Footer -->
  <div class="p-3 border-t border-zinc-700 text-center">
    <p class="text-xs text-zinc-500">
      {securityState.auditEntries.length} entries • Showing most recent first
    </p>
  </div>
</div>
