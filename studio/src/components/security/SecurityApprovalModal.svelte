<!--
  SecurityApprovalModal.svelte — Permission approval dialog (RFC-089)
  
  Shows permission scope and risk assessment before DAG execution.
  User can approve, reject, or modify permissions.
-->
<script lang="ts">
  import type {
    SecurityApprovalDetailed,
    SecurityApprovalResponse,
    RiskLevel,
  } from '$lib/security-types';
  import {
    submitApproval,
    rememberApprovalForSession,
  } from '../../stores/security.svelte';

  interface Props {
    approval: SecurityApprovalDetailed;
    onClose: () => void;
  }

  let { approval, onClose }: Props = $props();

  let rememberForSession = $state(false);
  let acknowledgedRisks = $state<string[]>([]);
  let isSubmitting = $state(false);
  let showBreakdown = $state(false);

  const riskColors: Record<RiskLevel, string> = {
    low: 'bg-green-500/20 text-green-400 border-green-500/50',
    medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50',
    high: 'bg-orange-500/20 text-orange-400 border-orange-500/50',
    critical: 'bg-red-500/20 text-red-400 border-red-500/50',
  };

  const riskBgColors: Record<RiskLevel, string> = {
    low: 'bg-green-500/10',
    medium: 'bg-yellow-500/10',
    high: 'bg-orange-500/10',
    critical: 'bg-red-500/10',
  };

  const contributionColors: Record<string, string> = {
    none: 'text-zinc-400',
    low: 'text-green-400',
    medium: 'text-yellow-400',
    high: 'text-red-400',
  };

  const allRisksAcknowledged = $derived(
    approval.risk.flags.length === 0 ||
      acknowledgedRisks.length >= approval.risk.flags.length
  );

  async function handleApprove() {
    isSubmitting = true;

    try {
      const response: SecurityApprovalResponse = {
        dagId: approval.dagId,
        approved: true,
        rememberForSession,
        acknowledgedRisks,
      };

      await submitApproval(response);
      onClose();
    } catch (error) {
      console.error('Failed to submit approval:', error);
    } finally {
      isSubmitting = false;
    }
  }

  async function handleReject() {
    isSubmitting = true;

    try {
      const response: SecurityApprovalResponse = {
        dagId: approval.dagId,
        approved: false,
        rememberForSession: false,
        acknowledgedRisks: [],
      };

      await submitApproval(response);
      onClose();
    } catch (error) {
      console.error('Failed to submit rejection:', error);
    } finally {
      isSubmitting = false;
    }
  }

  function toggleRiskAcknowledgment(flag: string) {
    if (acknowledgedRisks.includes(flag)) {
      acknowledgedRisks = acknowledgedRisks.filter((f) => f !== flag);
    } else {
      acknowledgedRisks = [...acknowledgedRisks, flag];
    }
  }
</script>

<div
  class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
  role="dialog"
  aria-modal="true"
  aria-labelledby="modal-title"
>
  <div
    class="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-xl bg-zinc-900 border border-zinc-700 shadow-2xl"
  >
    <!-- Header -->
    <div
      class="sticky top-0 z-10 flex items-center justify-between p-4 border-b border-zinc-700 bg-zinc-900/95 backdrop-blur-sm"
    >
      <div class="flex items-center gap-3">
        <span class="text-2xl">🔒</span>
        <h2 id="modal-title" class="text-lg font-semibold text-zinc-100">
          Security Review Required
        </h2>
      </div>
      <span
        class="px-3 py-1 text-sm font-medium rounded-full border {riskColors[approval.risk.level]}"
      >
        {approval.risk.level.toUpperCase()} RISK
      </span>
    </div>

    <!-- Content -->
    <div class="p-4 space-y-4">
      <!-- DAG Info -->
      <div class="flex items-center gap-3 p-3 rounded-lg {riskBgColors[approval.risk.level]}">
        <span class="text-xl">📋</span>
        <div class="flex-1">
          <div class="font-medium text-zinc-100">{approval.dagName}</div>
          <div class="text-sm text-zinc-400">{approval.skillCount} skills</div>
        </div>
        {#if approval.skillBreakdown.length > 0}
          <button
            class="text-xs text-zinc-300 hover:text-zinc-100"
            onclick={() => (showBreakdown = !showBreakdown)}
          >
            {showBreakdown ? '▲ Hide breakdown' : '▼ Show breakdown'}
          </button>
        {/if}
      </div>

      {#if showBreakdown && approval.skillBreakdown.length > 0}
        <div class="space-y-3">
          <h3 class="text-sm font-medium text-zinc-400 uppercase tracking-wide">
            Skill Breakdown
          </h3>
          <div class="space-y-2">
            {#each approval.skillBreakdown as skill, i}
              <div
                class={`p-3 rounded-lg border ${
                  skill.skillName === approval.highestRiskSkill
                    ? 'border-yellow-500/60 bg-yellow-500/10'
                    : 'border-zinc-700/50 bg-zinc-800/50'
                }`}
              >
                <div class="flex items-center gap-2 text-sm text-zinc-200">
                  <span class="text-zinc-500">{i + 1}.</span>
                  <span class="font-medium">{skill.skillName}</span>
                  {#if skill.preset}
                    <span class="px-2 py-0.5 text-xs rounded bg-zinc-800 text-zinc-300">
                      {skill.preset}
                    </span>
                  {/if}
                  {#if skill.skillName === approval.highestRiskSkill}
                    <span class="text-xs text-yellow-400">⚠️ Highest</span>
                  {/if}
                </div>

                <div class="mt-2 flex flex-wrap gap-3 text-xs text-zinc-400">
                  <span title="Filesystem Read">
                    📁 R {skill.permissions.filesystemRead.length > 0 ? '✅' : '❌'}
                  </span>
                  <span title="Filesystem Write">
                    ✏️ W {skill.permissions.filesystemWrite.length > 0 ? '✅' : '❌'}
                  </span>
                  <span title="Network">
                    🌐 {skill.permissions.networkAllow.length > 0 ? '✅' : '❌'}
                  </span>
                  <span title="Shell">
                    💻 {skill.permissions.shellAllow.length > 0 ? '✅' : '❌'}
                  </span>
                </div>

                <div
                  class={`mt-2 text-xs uppercase ${
                    contributionColors[skill.riskContribution] || 'text-zinc-400'
                  }`}
                >
                  {skill.riskContribution}
                  {#if skill.riskReason}
                    <span class="normal-case text-zinc-400">({skill.riskReason})</span>
                  {/if}
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <!-- Permissions Section -->
      <div class="space-y-3">
        <h3 class="text-sm font-medium text-zinc-400 uppercase tracking-wide">
          Permissions Requested
        </h3>

        {#if approval.permissions.filesystemRead.length > 0}
          <div class="p-3 rounded-lg bg-zinc-800/50">
            <div class="flex items-center gap-2 mb-2 text-sm text-zinc-300">
              <span>📁</span>
              <span class="font-medium">Filesystem Read</span>
            </div>
            <ul class="space-y-1 pl-6">
              {#each approval.permissions.filesystemRead as path}
                <li class="text-sm text-zinc-400">
                  <code class="text-emerald-400">{path}</code>
                </li>
              {/each}
            </ul>
          </div>
        {/if}

        {#if approval.permissions.filesystemWrite.length > 0}
          <div class="p-3 rounded-lg bg-zinc-800/50">
            <div class="flex items-center gap-2 mb-2 text-sm text-zinc-300">
              <span>✏️</span>
              <span class="font-medium">Filesystem Write</span>
            </div>
            <ul class="space-y-1 pl-6">
              {#each approval.permissions.filesystemWrite as path}
                <li class="text-sm text-zinc-400">
                  <code class="text-amber-400">{path}</code>
                </li>
              {/each}
            </ul>
          </div>
        {/if}

        {#if approval.permissions.networkAllow.length > 0}
          <div class="p-3 rounded-lg bg-zinc-800/50">
            <div class="flex items-center gap-2 mb-2 text-sm text-zinc-300">
              <span>🌐</span>
              <span class="font-medium">Network</span>
            </div>
            <ul class="space-y-1 pl-6">
              {#each approval.permissions.networkAllow as host}
                <li class="text-sm text-zinc-400">
                  <code class="text-blue-400">{host}</code>
                </li>
              {/each}
            </ul>
          </div>
        {/if}

        {#if approval.permissions.shellAllow.length > 0}
          <div class="p-3 rounded-lg bg-zinc-800/50">
            <div class="flex items-center gap-2 mb-2 text-sm text-zinc-300">
              <span>💻</span>
              <span class="font-medium">Shell Commands</span>
            </div>
            <ul class="space-y-1 pl-6">
              {#each approval.permissions.shellAllow as cmd}
                <li class="text-sm text-zinc-400">
                  <code class="text-purple-400">{cmd}</code>
                </li>
              {/each}
            </ul>
          </div>
        {/if}

        {#if approval.permissions.envRead.length > 0}
          <div class="p-3 rounded-lg bg-zinc-800/50">
            <div class="flex items-center gap-2 mb-2 text-sm text-zinc-300">
              <span>🔑</span>
              <span class="font-medium">Environment Variables</span>
            </div>
            <ul class="space-y-1 pl-6">
              {#each approval.permissions.envRead as env}
                <li class="text-sm text-zinc-400">
                  <code class="text-cyan-400">{env}</code>
                </li>
              {/each}
            </ul>
          </div>
        {/if}
      </div>

      <!-- Risk Flags -->
      {#if approval.risk.flags.length > 0}
        <div class="space-y-3">
          <h3 class="text-sm font-medium text-zinc-400 uppercase tracking-wide">
            ⚠️ Risk Flags
          </h3>
          <div class="space-y-2">
            {#each approval.risk.flags as flag}
              <label
                class="flex items-start gap-3 p-3 rounded-lg bg-red-500/10 border border-red-500/30 cursor-pointer hover:bg-red-500/20 transition-colors"
              >
                <input
                  type="checkbox"
                  checked={acknowledgedRisks.includes(flag)}
                  onchange={() => toggleRiskAcknowledgment(flag)}
                  class="mt-0.5 rounded border-zinc-600 bg-zinc-800 text-red-500 focus:ring-red-500"
                />
                <span class="text-sm text-zinc-300">{flag}</span>
              </label>
            {/each}
          </div>
          <p class="text-xs text-zinc-500">
            Acknowledge all risks to enable approval.
          </p>
        </div>
      {/if}

      <!-- Recommendations -->
      {#if approval.risk.recommendations.length > 0}
        <div class="space-y-3">
          <h3 class="text-sm font-medium text-zinc-400 uppercase tracking-wide">
            💡 Recommendations
          </h3>
          <ul class="space-y-2">
            {#each approval.risk.recommendations as rec}
              <li class="flex items-start gap-2 text-sm text-zinc-400">
                <span class="text-blue-400">•</span>
                <span>{rec}</span>
              </li>
            {/each}
          </ul>
        </div>
      {/if}
    </div>

    <!-- Actions -->
    <div
      class="sticky bottom-0 p-4 border-t border-zinc-700 bg-zinc-900/95 backdrop-blur-sm"
    >
      <div class="flex items-center justify-between">
        <label class="flex items-center gap-2 text-sm text-zinc-400 cursor-pointer">
          <input
            type="checkbox"
            bind:checked={rememberForSession}
            class="rounded border-zinc-600 bg-zinc-800 text-blue-500 focus:ring-blue-500"
          />
          Remember for this session
        </label>

        <div class="flex gap-3">
          <button
            onclick={handleReject}
            disabled={isSubmitting}
            class="px-4 py-2 text-sm font-medium rounded-lg border border-zinc-600 text-zinc-300 hover:bg-zinc-800 disabled:opacity-50 transition-colors"
          >
            Reject
          </button>
          <button
            onclick={handleApprove}
            disabled={isSubmitting || !allRisksAcknowledged}
            class="px-4 py-2 text-sm font-medium rounded-lg text-white disabled:opacity-50 transition-colors {approval
              .risk.level === 'critical'
              ? 'bg-red-600 hover:bg-red-700'
              : 'bg-blue-600 hover:bg-blue-700'}"
          >
            {#if approval.risk.level === 'critical'}
              Approve Anyway
            {:else}
              Approve
            {/if}
          </button>
        </div>
      </div>
    </div>
  </div>
</div>
