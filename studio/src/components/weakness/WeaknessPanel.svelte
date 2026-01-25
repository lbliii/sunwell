<!--
  WeaknessPanel — Code health analysis and cascade preview (RFC-063)
-->
<script lang="ts">
  import { weakness, scanWeaknesses, selectWeakness, executeQuickFix, clearSelection as clearWeaknessSelection } from '../../stores/weakness.svelte';
  import { project } from '../../stores/project.svelte';
  import Button from '../Button.svelte';
  import Panel from '../Panel.svelte';
  import Spinner from '../ui/Spinner.svelte';
  import { getWeaknessIcon, getSeverityColor, getRiskColor, type WeaknessScore } from '$lib/types/weakness';
  
  let collapsed = $state(false);
  let fixNotice = $state<string | null>(null);
  
  function handleScan() {
    if (project.current?.path) {
      scanWeaknesses(project.current.path);
    }
  }
  
  function handleSelectWeakness(w: WeaknessScore) {
    if (project.current?.path) {
      selectWeakness(w, project.current.path);
    }
  }
  
  function handleQuickFix() {
    if (project.current?.path && weakness.selectedWeakness) {
      // TODO: Wire up to agent execution
      fixNotice = 'Cascade fix is coming soon! For now, review the weakness details and fix manually.';
      setTimeout(() => { fixNotice = null; }, 5000);
      // executeQuickFix(project.current.path, weakness.selectedWeakness.artifact_id);
    }
  }
  
  /** Format weakness type for display */
  function formatWeaknessType(type: string): string {
    return type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  }
  
  /** Format evidence dict into human-readable string */
  function formatEvidence(type: string, evidence: Record<string, unknown>): string {
    if (!evidence || Object.keys(evidence).length === 0) return '';
    
    switch (type) {
      case 'low_coverage':
        return `${((evidence.coverage as number) * 100).toFixed(0)}% (need ${((evidence.threshold as number) * 100).toFixed(0)}%)`;
      case 'high_complexity':
        return `complexity: ${evidence.complexity ?? evidence.value ?? '?'}`;
      case 'lint_errors':
        return `${evidence.count ?? evidence.errors ?? '?'} errors`;
      case 'missing_types':
        return `${evidence.count ?? '?'} untyped`;
      case 'stale_code':
        return `${evidence.days_since_change ?? '?'} days stale`;
      default:
        // Generic formatting for unknown types
        return Object.entries(evidence)
          .map(([k, v]) => `${k}: ${v}`)
          .join(', ');
    }
  }
</script>

<Panel title="Code Health" icon="◈" collapsible bind:collapsed={collapsed}>
  <div class="weakness-panel">
    <!-- Scan button -->
    <div class="scan-controls">
      <Button 
        variant="secondary" 
        onclick={handleScan}
        disabled={weakness.isScanning}
      >
        {#if weakness.isScanning}
          <Spinner style="dots" speed={80} /> Scanning
        {:else}
          ⊛ Scan
        {/if}
      </Button>
    </div>
    
    <!-- Summary stats -->
    {#if weakness.report}
      <div class="stats-row">
        <div class="stat" style="--color: var(--error)">
          <span class="stat-value">{weakness.criticalCount}</span>
          <span class="stat-label">Critical</span>
        </div>
        <div class="stat" style="--color: var(--warning)">
          <span class="stat-value">{weakness.highCount}</span>
          <span class="stat-label">High</span>
        </div>
        <div class="stat" style="--color: var(--info)">
          <span class="stat-value">{weakness.mediumCount}</span>
          <span class="stat-label">Medium</span>
        </div>
        <div class="stat" style="--color: var(--text-tertiary)">
          <span class="stat-value">{weakness.lowCount}</span>
          <span class="stat-label">Low</span>
        </div>
      </div>
      
      <!-- Weakness list -->
      {#if weakness.hasWeaknesses}
        <div class="weakness-list">
          {#each weakness.report.weaknesses as w (w.artifact_id)}
            <button
              class="weakness-item"
              class:selected={weakness.selectedWeakness?.artifact_id === w.artifact_id}
              onclick={() => handleSelectWeakness(w)}
            >
              <div class="weakness-header">
                <span class="weakness-icons">
                  {#each w.signals as signal (`${w.artifact_id}-icon-${signal.weakness_type}`)}
                    <span title={signal.weakness_type}>{getWeaknessIcon(signal.weakness_type)}</span>
                  {/each}
                </span>
                <span class="weakness-file">{w.file_path}</span>
              </div>
              <div class="weakness-meta">
                <span 
                  class="severity-badge"
                  style="background: {getSeverityColor(w.total_severity)}"
                >
                  {(w.total_severity * 100).toFixed(0)}%
                </span>
                <span class="fan-out" title="Files that depend on this">
                  → {w.fan_out}
                </span>
                <span 
                  class="risk-badge"
                  style="background: {getRiskColor(w.cascade_risk)}"
                >
                  {w.cascade_risk.toUpperCase()}
                </span>
              </div>
              <!-- Expanded signal details when selected -->
              {#if weakness.selectedWeakness?.artifact_id === w.artifact_id}
                <div class="signal-details">
                  {#each w.signals as signal (`${w.artifact_id}-detail-${signal.weakness_type}`)}
                    <div class="signal-row">
                      <span class="signal-icon">{getWeaknessIcon(signal.weakness_type)}</span>
                      <span class="signal-type">{formatWeaknessType(signal.weakness_type)}</span>
                      <span class="signal-evidence">
                        {formatEvidence(signal.weakness_type, signal.evidence)}
                      </span>
                    </div>
                  {/each}
                </div>
              {/if}
            </button>
          {/each}
        </div>
      {:else}
        <div class="no-weaknesses">
          ◆ No weaknesses found
        </div>
      {/if}
    {/if}
    
    <!-- Cascade preview -->
    {#if weakness.cascadePreview}
      <div class="cascade-preview">
        <h4>Cascade Impact</h4>
        <div class="cascade-stats">
          <div class="cascade-stat">
            <span class="label">Direct dependents</span>
            <span class="value">{weakness.cascadePreview.direct_dependents.length}</span>
          </div>
          <div class="cascade-stat">
            <span class="label">Transitive</span>
            <span class="value">{weakness.cascadePreview.transitive_dependents.length}</span>
          </div>
          <div class="cascade-stat">
            <span class="label">Total impacted</span>
            <span class="value">{weakness.cascadePreview.total_impacted}</span>
          </div>
          <div class="cascade-stat">
            <span class="label">Effort</span>
            <span class="value">{weakness.cascadePreview.estimated_effort}</span>
          </div>
        </div>
        
        <div class="risk-assessment">
          <span class="risk-label">Risk:</span>
          <span class="risk-value risk-{weakness.cascadePreview.cascade_risk}">
            {weakness.cascadePreview.cascade_risk.toUpperCase()}
          </span>
          <p class="risk-detail">{weakness.cascadePreview.risk_assessment}</p>
        </div>
        
        <!-- Execution waves preview -->
        <div class="waves-preview">
          <h5>Regeneration Waves</h5>
          {#each weakness.cascadePreview.waves as wave, i (i)}
            <div class="wave">
              <span class="wave-num">Wave {i}</span>
              <span class="wave-files">
                {wave.slice(0, 2).join(', ')}{wave.length > 2 ? `... (+${wave.length - 2})` : ''}
              </span>
            </div>
          {/each}
        </div>
        
        <div class="fix-controls">
          <Button variant="secondary" onclick={clearWeaknessSelection}>
            Cancel
          </Button>
          <Button variant="primary" onclick={handleQuickFix} disabled={weakness.isExecuting}>
            ⟁ Fix {weakness.cascadePreview.total_impacted} files
          </Button>
        </div>
      </div>
    {:else if weakness.isPreviewing}
      <div class="loading">
        <Spinner style="braille" speed={60} /> Computing cascade impact...
      </div>
    {/if}
    
    <!-- Error display -->
    {#if weakness.error}
      <div class="error">
        ⊗ {weakness.error}
      </div>
    {/if}
    
    <!-- Fix notice -->
    {#if fixNotice}
      <div class="notice">
        ◈ {fixNotice}
      </div>
    {/if}
  </div>
</Panel>

<style>
  .weakness-panel {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  
  .scan-controls {
    display: flex;
    justify-content: center;
  }
  
  .stats-row {
    display: flex;
    justify-content: space-around;
    padding: 8px 0;
    border-bottom: 1px solid var(--border-color);
  }
  
  .stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
  }
  
  .stat-value {
    font-size: 18px;
    font-weight: 700;
    color: var(--color);
  }
  
  .stat-label {
    font-size: 10px;
    color: var(--text-secondary);
    text-transform: uppercase;
  }
  
  .weakness-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-height: 200px;
    overflow-y: auto;
  }
  
  .weakness-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 8px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s ease;
    text-align: left;
    width: 100%;
  }
  
  .weakness-item:hover {
    background: var(--bg-tertiary);
    border-color: var(--text-tertiary);
  }
  
  .weakness-item.selected {
    border-color: var(--accent);
    background: var(--accent-muted);
  }
  
  .weakness-header {
    display: flex;
    gap: 8px;
    align-items: center;
  }
  
  .weakness-icons {
    display: flex;
    gap: 2px;
  }
  
  .weakness-file {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  .weakness-meta {
    display: flex;
    gap: 8px;
    align-items: center;
  }
  
  .severity-badge, .risk-badge {
    font-size: 10px;
    font-weight: 600;
    color: white;
    padding: 2px 6px;
    border-radius: 4px;
  }
  
  .fan-out {
    font-size: 10px;
    color: var(--text-secondary);
  }
  
  .no-weaknesses {
    text-align: center;
    color: var(--success);
    padding: 16px;
    font-size: 14px;
  }
  
  .cascade-preview {
    padding: 12px;
    background: var(--bg-tertiary);
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  
  .cascade-preview h4 {
    margin: 0;
    font-size: 12px;
    text-transform: uppercase;
    color: var(--text-secondary);
  }
  
  .cascade-stats {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  
  .cascade-stat {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
  }
  
  .cascade-stat .label {
    color: var(--text-secondary);
  }
  
  .cascade-stat .value {
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .risk-assessment {
    padding: 8px;
    background: var(--bg-secondary);
    border-radius: 6px;
  }
  
  .risk-label {
    font-size: 10px;
    color: var(--text-secondary);
  }
  
  .risk-value {
    font-size: 12px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 4px;
    margin-left: 4px;
  }
  
  .risk-low { background: var(--success); color: white; }
  .risk-medium { background: var(--info); color: white; }
  .risk-high { background: var(--warning); color: black; }
  .risk-critical { background: var(--error); color: white; }
  
  .risk-detail {
    margin: 4px 0 0;
    font-size: 10px;
    color: var(--text-secondary);
  }
  
  .waves-preview {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  
  .waves-preview h5 {
    margin: 0;
    font-size: 10px;
    color: var(--text-secondary);
  }
  
  .wave {
    display: flex;
    gap: 8px;
    font-size: 10px;
    padding: 4px 8px;
    background: var(--bg-secondary);
    border-radius: 4px;
  }
  
  .wave-num {
    font-weight: 600;
    color: var(--accent);
  }
  
  .wave-files {
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  .fix-controls {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }
  
  .loading {
    text-align: center;
    color: var(--text-secondary);
    font-size: 12px;
    padding: 16px;
  }
  
  .error {
    padding: 8px;
    background: var(--error);
    color: white;
    border-radius: 6px;
    font-size: 11px;
  }
  
  .notice {
    padding: 8px;
    background: var(--info);
    color: white;
    border-radius: 6px;
    font-size: 11px;
  }
  
  .signal-details {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1px solid var(--border-color);
  }
  
  .signal-row {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 10px;
  }
  
  .signal-icon {
    font-size: 12px;
  }
  
  .signal-type {
    color: var(--text-secondary);
    min-width: 100px;
  }
  
  .signal-evidence {
    color: var(--warning);
    font-family: var(--font-mono);
    font-weight: 500;
  }
</style>
