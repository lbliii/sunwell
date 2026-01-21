<!--
  WaveExecutionPanel — Wave-by-wave cascade execution UI (RFC-063)
-->
<script lang="ts">
  import { weakness } from '../../stores/weakness.svelte';
  import { getConfidenceColor } from '$lib/types/weakness';
  import Button from '../Button.svelte';
  import Panel from '../Panel.svelte';
  import Spinner from '../ui/Spinner.svelte';
  
  interface Props {
    onAbort?: () => void;
    onApprove?: () => void;
  }
  
  let { onAbort, onApprove }: Props = $props();
  
  let currentConf = $derived(weakness.currentWaveConfidence);
</script>

{#if weakness.execution && !weakness.execution.completed}
  <Panel title="Cascade Execution" icon="⟁">
    <div class="execution-panel">
      <!-- Wave progress -->
      <div class="wave-progress">
        {#each weakness.cascadePreview?.waves ?? [] as _wave, i}
          <div 
            class="wave-marker"
            class:completed={i < weakness.execution.current_wave}
            class:current={i === weakness.execution.current_wave}
            class:pending={i > weakness.execution.current_wave}
          >
            <span class="wave-num">{i}</span>
            {#if weakness.execution.wave_confidences[i]}
              <span 
                class="wave-confidence" 
                style="color: {getConfidenceColor(weakness.execution.wave_confidences[i].confidence)}"
              >
                {(weakness.execution.wave_confidences[i].confidence * 100).toFixed(0)}%
              </span>
            {/if}
          </div>
        {/each}
      </div>
      
      <!-- Current wave details -->
      {#if weakness.execution.paused_for_approval && currentConf}
        <div class="approval-prompt">
          <h5>Wave {weakness.execution.current_wave} Complete</h5>
          
          <div class="confidence-details">
            <div 
              class="confidence-score" 
              style="color: {getConfidenceColor(currentConf.confidence)}"
            >
              Confidence: {(currentConf.confidence * 100).toFixed(0)}%
            </div>
            
            <div class="checks">
              <span class:pass={currentConf.tests_passed} class:fail={!currentConf.tests_passed}>
                {currentConf.tests_passed ? '✓' : '✗'} Tests
              </span>
              <span class:pass={currentConf.types_clean} class:fail={!currentConf.types_clean}>
                {currentConf.types_clean ? '✓' : '✗'} Types
              </span>
              <span class:pass={currentConf.lint_clean} class:fail={!currentConf.lint_clean}>
                {currentConf.lint_clean ? '✓' : '✗'} Lint
              </span>
              <span class:pass={currentConf.contracts_preserved} class:fail={!currentConf.contracts_preserved}>
                {currentConf.contracts_preserved ? '✓' : '✗'} Contracts
              </span>
            </div>
            
            {#if currentConf.deductions.length > 0}
              <div class="deductions">
                {#each currentConf.deductions as d}
                  <span class="deduction">▲ {d}</span>
                {/each}
              </div>
            {/if}
          </div>
          
          {#if weakness.execution.escalated_to_human}
            <div class="escalation-warning">
              ▲ Escalated to human review due to consecutive low-confidence waves
            </div>
          {/if}
          
          <div class="approval-actions">
            <Button variant="secondary" onclick={onAbort}>
              ⊗ Abort
            </Button>
            <Button variant="primary" onclick={onApprove}>
              » Wave {weakness.execution.current_wave + 1}
            </Button>
          </div>
        </div>
      {:else}
        <div class="executing">
          <Spinner style="moon" speed={80} />
          Executing Wave {weakness.execution.current_wave}...
        </div>
      {/if}
      
      <!-- Overall progress -->
      <div class="overall-progress">
        <span class="label">Overall Confidence:</span>
        <span 
          class="value"
          style="color: {getConfidenceColor(weakness.execution.overall_confidence)}"
        >
          {(weakness.execution.overall_confidence * 100).toFixed(0)}%
        </span>
      </div>
    </div>
  </Panel>
{/if}

{#if weakness.execution?.completed}
  <Panel title="Cascade Complete" icon="◆">
    <div class="execution-complete">
      <div class="complete-icon">◆</div>
      <div class="final-stats">
        <div class="stat-row">
          <span class="label">Overall Confidence</span>
          <span 
            class="value"
            style="color: {getConfidenceColor(weakness.execution.overall_confidence)}"
          >
            {(weakness.execution.overall_confidence * 100).toFixed(0)}%
          </span>
        </div>
        <div class="stat-row">
          <span class="label">Waves Completed</span>
          <span class="value">{weakness.execution.wave_confidences.length}</span>
        </div>
        <div class="stat-row">
          <span class="label">Files Updated</span>
          <span class="value">{weakness.cascadePreview?.total_impacted ?? 0}</span>
        </div>
      </div>
    </div>
  </Panel>
{/if}

{#if weakness.execution?.aborted}
  <Panel title="Cascade Aborted" icon="⊗">
    <div class="execution-aborted">
      <div class="abort-icon">⊗</div>
      <div class="abort-reason">
        {weakness.execution.abort_reason ?? 'Unknown reason'}
      </div>
    </div>
  </Panel>
{/if}

<style>
  .execution-panel {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  
  .wave-progress {
    display: flex;
    gap: 8px;
    justify-content: center;
    flex-wrap: wrap;
  }
  
  .wave-marker {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    padding: 8px 12px;
    background: var(--bg-secondary);
    border-radius: 6px;
    border: 2px solid transparent;
    transition: all 0.15s ease;
  }
  
  .wave-marker.completed {
    background: var(--success);
    color: white;
  }
  
  .wave-marker.current {
    border-color: var(--accent);
    background: var(--accent-muted);
  }
  
  .wave-marker.pending {
    opacity: 0.5;
  }
  
  .wave-num {
    font-weight: 700;
    font-size: 14px;
  }
  
  .wave-confidence {
    font-size: 10px;
    font-weight: 600;
  }
  
  .approval-prompt {
    background: var(--bg-tertiary);
    padding: 16px;
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  
  .approval-prompt h5 {
    margin: 0;
    font-size: 14px;
    color: var(--text-primary);
  }
  
  .confidence-details {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  
  .confidence-score {
    font-size: 18px;
    font-weight: 700;
  }
  
  .checks {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
  }
  
  .checks span {
    font-size: 11px;
    font-weight: 500;
  }
  
  .checks .pass {
    color: var(--success);
  }
  
  .checks .fail {
    color: var(--error);
  }
  
  .deductions {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  
  .deduction {
    font-size: 11px;
    color: var(--warning);
  }
  
  .escalation-warning {
    padding: 8px;
    background: var(--warning);
    color: black;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
  }
  
  .approval-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }
  
  .executing {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 24px;
    font-size: 14px;
    color: var(--text-secondary);
  }
  
  .executing :global(.spinner) {
    font-size: 18px;
  }
  
  .overall-progress {
    display: flex;
    justify-content: space-between;
    padding: 8px 12px;
    background: var(--bg-secondary);
    border-radius: 6px;
    font-size: 12px;
  }
  
  .overall-progress .label {
    color: var(--text-secondary);
  }
  
  .overall-progress .value {
    font-weight: 700;
  }
  
  .execution-complete, .execution-aborted {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
    padding: 24px;
  }
  
  .complete-icon, .abort-icon {
    font-size: 48px;
  }
  
  .final-stats {
    display: flex;
    flex-direction: column;
    gap: 8px;
    width: 100%;
  }
  
  .stat-row {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
  }
  
  .stat-row .label {
    color: var(--text-secondary);
  }
  
  .stat-row .value {
    font-weight: 600;
  }
  
  .abort-reason {
    color: var(--error);
    font-size: 14px;
  }
</style>
