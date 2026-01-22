<!--
  DiataxisBlock.svelte — Content type detection and guidance (RFC-086)

  Shows:
  - Detected Diataxis type with confidence
  - Signals that contributed to detection
  - Warnings for mixed content
  - Recommendations
-->
<script lang="ts">
  import {
    writerState,
    detectDiataxis as detectDiataxisAction,
    type DiataxisType,
    type DiataxisSignal,
  } from '../../stores';

  interface Props {
    /** Override values (optional - uses writer store by default) */
    detectedType?: DiataxisType | null;
    confidence?: number;
    signals?: DiataxisSignal[];
    scores?: Record<string, number>;
    mixedWarning?: string | null;
    onReclassify?: () => void;
    onSplit?: () => void;
  }

  let {
    detectedType: propType,
    confidence: propConfidence,
    signals: propSignals,
    scores: propScores,
    mixedWarning: propWarning,
    onReclassify,
    onSplit,
  }: Props = $props();

  // Use props if provided, otherwise use writer store
  const detectedType = $derived(propType ?? writerState.diataxis?.detectedType ?? null);
  const confidence = $derived(propConfidence ?? writerState.diataxis?.confidence ?? 0);
  const signals = $derived(propSignals ?? writerState.diataxis?.signals ?? []);
  const scores = $derived(propScores ?? writerState.diataxis?.scores ?? {});
  const mixedWarning = $derived(
    propWarning ?? writerState.diataxisWarnings[0]?.message ?? null,
  );

  function handleReclassify() {
    if (onReclassify) {
      onReclassify();
    } else {
      detectDiataxisAction();
    }
  }

  let expanded = $state(false);

  const typeLabels: Record<string, { label: string; icon: string; color: string }> = {
    TUTORIAL: { label: 'Tutorial', icon: '📚', color: '#6bff6b' },
    HOW_TO: { label: 'How-To', icon: '📋', color: '#6bcbff' },
    EXPLANATION: { label: 'Explanation', icon: '💡', color: '#ffd93d' },
    REFERENCE: { label: 'Reference', icon: '📖', color: '#ff6b6b' },
  };

  const typeInfo = $derived(detectedType ? typeLabels[detectedType] : null);
  const confidencePct = $derived(Math.round(confidence * 100));

  const confidenceColor = $derived(() => {
    if (confidence >= 0.8) return 'var(--success, #6bff6b)';
    if (confidence >= 0.5) return 'var(--warning, #ffd93d)';
    return 'var(--error, #ff6b6b)';
  });
</script>

<div class="diataxis-block" class:has-warning={!!mixedWarning}>
  <button class="header" onclick={() => (expanded = !expanded)}>
    {#if typeInfo}
      <span class="type-icon">{typeInfo.icon}</span>
      <span class="type-label" style="color: {typeInfo.color}">{typeInfo.label}</span>
      <span class="confidence" style="color: {confidenceColor()}">{confidencePct}%</span>
    {:else}
      <span class="type-icon">❓</span>
      <span class="type-label">Unknown Type</span>
    {/if}
    {#if mixedWarning}
      <span class="warning-badge">⚠️</span>
    {/if}
    <span class="toggle">{expanded ? '▼' : '▶'}</span>
  </button>

  {#if expanded}
    <div class="content">
      {#if mixedWarning}
        <div class="warning-message">
          <span class="icon">⚠️</span>
          {mixedWarning}
        </div>
      {/if}

      {#if signals.length > 0}
        <div class="signals-section">
          <div class="section-title">Signals:</div>
          <div class="signals">
            {#each signals.slice(0, 5) as signal}
              <div class="signal">
                <span class="signal-icon">{typeLabels[signal.dtype]?.icon || '•'}</span>
                <span class="signal-reason">{signal.reason}</span>
                <span class="signal-weight">+{(signal.weight * 100).toFixed(0)}%</span>
              </div>
            {/each}
            {#if signals.length > 5}
              <div class="more-signals">+{signals.length - 5} more signals</div>
            {/if}
          </div>
        </div>
      {/if}

      {#if Object.keys(scores).length > 0}
        <div class="scores-section">
          <div class="section-title">Type Scores:</div>
          <div class="scores">
            {#each Object.entries(scores).sort(([, a], [, b]) => b - a) as [type, score]}
              <div class="score-bar">
                <span class="score-label">{typeLabels[type as DiataxisType]?.label || type}</span>
                <div class="bar-container">
                  <div
                    class="bar-fill"
                    style="width: {Math.min(100, score * 100)}%; background: {typeLabels[type as DiataxisType]?.color || '#888'}"
                  ></div>
                </div>
                <span class="score-value">{(score * 100).toFixed(0)}%</span>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <div class="actions">
        <button class="action-btn" onclick={handleReclassify}>
          ↻ Reclassify
        </button>
        {#if onSplit && mixedWarning}
          <button class="action-btn split" onclick={onSplit}>
            ✂ Split Page
          </button>
        {/if}
      </div>

      <div class="tip">
        {#if detectedType === 'TUTORIAL'}
          Tutorials teach by doing. Include learning objectives, guided steps, and expected outcomes.
        {:else if detectedType === 'HOW_TO'}
          How-to guides accomplish tasks. Include clear goals, practical steps, and troubleshooting.
        {:else if detectedType === 'EXPLANATION'}
          Explanations provide understanding. Focus on concepts, architecture, and design rationale.
        {:else if detectedType === 'REFERENCE'}
          Reference docs provide facts. Include comprehensive tables, parameters, and examples.
        {:else}
          Unable to detect content type. Consider clarifying the document's purpose.
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .diataxis-block {
    background: var(--surface-2, #1a1a2e);
    border-radius: 8px;
    overflow: hidden;
    font-family: var(--font-mono, 'JetBrains Mono', monospace);
    font-size: 12px;
  }

  .diataxis-block.has-warning {
    border: 1px solid var(--warning, #ffd93d);
  }

  .header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: var(--surface-3, #252547);
    cursor: pointer;
    border: none;
    width: 100%;
    text-align: left;
    color: inherit;
  }

  .header:hover {
    background: var(--surface-4, #2d2d5a);
  }

  .type-icon {
    font-size: 14px;
  }

  .type-label {
    font-weight: 600;
    flex: 1;
  }

  .confidence {
    font-size: 11px;
    font-weight: 500;
  }

  .warning-badge {
    font-size: 14px;
  }

  .toggle {
    color: var(--text-muted, #888);
    font-size: 10px;
  }

  .content {
    padding: 12px;
  }

  .warning-message {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    background: rgba(255, 217, 61, 0.1);
    border: 1px solid var(--warning, #ffd93d);
    border-radius: 4px;
    padding: 8px;
    margin-bottom: 12px;
    color: var(--warning, #ffd93d);
    font-size: 11px;
  }

  .warning-message .icon {
    flex-shrink: 0;
  }

  .section-title {
    font-size: 10px;
    color: var(--text-muted, #888);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 6px;
  }

  .signals-section {
    margin-bottom: 12px;
  }

  .signals {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .signal {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 8px;
    background: var(--surface-1, #0f0f1a);
    border-radius: 4px;
    font-size: 11px;
  }

  .signal-icon {
    flex-shrink: 0;
  }

  .signal-reason {
    flex: 1;
    color: var(--text-muted, #888);
  }

  .signal-weight {
    color: var(--accent, #6366f1);
    font-size: 10px;
  }

  .more-signals {
    font-size: 10px;
    color: var(--text-muted, #666);
    text-align: center;
    padding: 4px;
  }

  .scores-section {
    margin-bottom: 12px;
  }

  .scores {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .score-bar {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .score-label {
    min-width: 80px;
    font-size: 10px;
  }

  .bar-container {
    flex: 1;
    height: 4px;
    background: var(--surface-1, #0f0f1a);
    border-radius: 2px;
    overflow: hidden;
  }

  .bar-fill {
    height: 100%;
    border-radius: 2px;
    transition: width 0.3s ease;
  }

  .score-value {
    font-size: 10px;
    color: var(--text-muted, #888);
    min-width: 32px;
    text-align: right;
  }

  .actions {
    display: flex;
    gap: 8px;
    margin-bottom: 12px;
  }

  .action-btn {
    background: var(--surface-3, #252547);
    color: var(--text, #fff);
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
    font-size: 11px;
    cursor: pointer;
    font-family: inherit;
  }

  .action-btn:hover {
    background: var(--surface-4, #2d2d5a);
  }

  .action-btn.split {
    background: var(--warning-bg, rgba(255, 217, 61, 0.2));
    color: var(--warning, #ffd93d);
  }

  .tip {
    font-size: 10px;
    color: var(--text-muted, #666);
    padding: 8px;
    background: var(--surface-1, #0f0f1a);
    border-radius: 4px;
    line-height: 1.4;
  }
</style>
