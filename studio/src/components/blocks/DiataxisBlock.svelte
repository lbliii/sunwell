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
    if (confidence >= 0.8) return 'var(--success)';
    if (confidence >= 0.5) return 'var(--warning)';
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
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    overflow: hidden;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
  }

  .diataxis-block.has-warning {
    border: 1px solid var(--warning);
  }

  .header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    background: var(--bg-tertiary);
    cursor: pointer;
    border: none;
    width: 100%;
    text-align: left;
    color: inherit;
    transition: background var(--transition-fast);
  }

  .header:hover {
    background: var(--accent-hover);
  }

  .type-icon {
    font-size: var(--text-sm);
  }

  .type-label {
    font-weight: 600;
    flex: 1;
  }

  .confidence {
    font-size: var(--text-xs);
    font-weight: 500;
  }

  .warning-badge {
    font-size: var(--text-sm);
  }

  .toggle {
    color: var(--text-secondary);
    font-size: var(--text-xs);
  }

  .content {
    padding: var(--space-3);
  }

  .warning-message {
    display: flex;
    align-items: flex-start;
    gap: var(--space-2);
    background: var(--warning-bg);
    border: 1px solid var(--warning);
    border-radius: var(--radius-sm);
    padding: var(--space-2);
    margin-bottom: var(--space-3);
    color: var(--warning);
    font-size: var(--text-xs);
  }

  .warning-message .icon {
    flex-shrink: 0;
  }

  .section-title {
    font-size: var(--text-xs);
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: var(--space-1);
  }

  .signals-section {
    margin-bottom: var(--space-3);
  }

  .signals {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .signal {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-1) var(--space-2);
    background: var(--bg-primary);
    border-radius: var(--radius-sm);
    font-size: var(--text-xs);
  }

  .signal-icon {
    flex-shrink: 0;
  }

  .signal-reason {
    flex: 1;
    color: var(--text-secondary);
  }

  .signal-weight {
    color: var(--text-gold);
    font-size: var(--text-xs);
  }

  .more-signals {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    text-align: center;
    padding: var(--space-1);
  }

  .scores-section {
    margin-bottom: var(--space-3);
  }

  .scores {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .score-bar {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .score-label {
    min-width: 80px;
    font-size: var(--text-xs);
  }

  .bar-container {
    flex: 1;
    height: var(--space-1);
    background: var(--bg-primary);
    border-radius: var(--radius-full);
    overflow: hidden;
  }

  .bar-fill {
    height: 100%;
    border-radius: var(--radius-full);
    transition: width var(--transition-normal);
  }

  .score-value {
    font-size: var(--text-xs);
    color: var(--text-secondary);
    min-width: 32px;
    text-align: right;
  }

  .actions {
    display: flex;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
  }

  .action-btn {
    background: var(--bg-tertiary);
    color: var(--text-primary);
    border: none;
    border-radius: var(--radius-sm);
    padding: var(--space-1) var(--space-3);
    font-size: var(--text-xs);
    cursor: pointer;
    font-family: inherit;
    transition: background var(--transition-fast);
  }

  .action-btn:hover {
    background: var(--accent-hover);
  }

  .action-btn.split {
    background: var(--warning-bg);
    color: var(--warning);
  }

  .tip {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    padding: var(--space-2);
    background: var(--bg-primary);
    border-radius: var(--radius-sm);
    line-height: var(--leading-normal);
  }
</style>
