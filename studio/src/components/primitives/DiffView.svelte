<!--
  DiffView Primitive (RFC-072, RFC-078)
  
  Show code changes side-by-side or unified (inline) diff view.
-->
<script lang="ts">
  import type { PrimitiveProps } from './types';
  
  interface Props extends PrimitiveProps {
    leftContent?: string;
    rightContent?: string;
    leftLabel?: string;
    rightLabel?: string;
    language?: string;
    mode?: 'side-by-side' | 'inline';
  }
  
  let { 
    size, 
    leftContent = '',
    rightContent = '',
    leftLabel = 'Original',
    rightLabel = 'Modified',
    language = 'text',
    mode = 'side-by-side',
  }: Props = $props();
  
  type DiffLine = {
    type: 'unchanged' | 'added' | 'removed' | 'modified';
    leftLine: number | null;
    rightLine: number | null;
    leftText: string | null;
    rightText: string | null;
  };
  
  // Simple diff algorithm (line-based)
  function computeDiff(left: string, right: string): DiffLine[] {
    const leftLines = left.split('\n');
    const rightLines = right.split('\n');
    const result: DiffLine[] = [];
    
    // Use LCS (Longest Common Subsequence) for better diffs
    const lcs = computeLCS(leftLines, rightLines);
    
    let leftIdx = 0;
    let rightIdx = 0;
    let lcsIdx = 0;
    
    while (leftIdx < leftLines.length || rightIdx < rightLines.length) {
      const currentLCS = lcsIdx < lcs.length ? lcs[lcsIdx] : null;
      
      if (currentLCS !== null && 
          leftIdx < leftLines.length && 
          leftLines[leftIdx] === currentLCS) {
        // Check if right side also matches
        if (rightIdx < rightLines.length && rightLines[rightIdx] === currentLCS) {
          // Unchanged line
          result.push({
            type: 'unchanged',
            leftLine: leftIdx + 1,
            rightLine: rightIdx + 1,
            leftText: leftLines[leftIdx],
            rightText: rightLines[rightIdx],
          });
          leftIdx++;
          rightIdx++;
          lcsIdx++;
        } else {
          // Right side has additions before matching
          result.push({
            type: 'added',
            leftLine: null,
            rightLine: rightIdx + 1,
            leftText: null,
            rightText: rightLines[rightIdx],
          });
          rightIdx++;
        }
      } else if (leftIdx < leftLines.length) {
        // Check if this line is removed or just not in LCS
        if (rightIdx < rightLines.length && 
            (currentLCS === null || rightLines[rightIdx] !== currentLCS)) {
          // Both sides have changes - could be modified
          result.push({
            type: 'removed',
            leftLine: leftIdx + 1,
            rightLine: null,
            leftText: leftLines[leftIdx],
            rightText: null,
          });
          leftIdx++;
        } else {
          // Left line is removed
          result.push({
            type: 'removed',
            leftLine: leftIdx + 1,
            rightLine: null,
            leftText: leftLines[leftIdx],
            rightText: null,
          });
          leftIdx++;
        }
      } else if (rightIdx < rightLines.length) {
        // Right side has additions
        result.push({
          type: 'added',
          leftLine: null,
          rightLine: rightIdx + 1,
          leftText: null,
          rightText: rightLines[rightIdx],
        });
        rightIdx++;
      }
    }
    
    return result;
  }
  
  // Compute Longest Common Subsequence
  function computeLCS(left: string[], right: string[]): string[] {
    const m = left.length;
    const n = right.length;
    
    // DP table
    const dp: number[][] = Array(m + 1).fill(null).map(() => Array(n + 1).fill(0));
    
    for (let i = 1; i <= m; i++) {
      for (let j = 1; j <= n; j++) {
        if (left[i - 1] === right[j - 1]) {
          dp[i][j] = dp[i - 1][j - 1] + 1;
        } else {
          dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
        }
      }
    }
    
    // Backtrack to find LCS
    const lcs: string[] = [];
    let i = m, j = n;
    while (i > 0 && j > 0) {
      if (left[i - 1] === right[j - 1]) {
        lcs.unshift(left[i - 1]);
        i--;
        j--;
      } else if (dp[i - 1][j] > dp[i][j - 1]) {
        i--;
      } else {
        j--;
      }
    }
    
    return lcs;
  }
  
  // Computed diff
  let diffLines = $derived(() => computeDiff(leftContent, rightContent));
  
  // Stats
  let stats = $derived(() => {
    const lines = diffLines();
    const added = lines.filter(l => l.type === 'added').length;
    const removed = lines.filter(l => l.type === 'removed').length;
    const unchanged = lines.filter(l => l.type === 'unchanged').length;
    return { added, removed, unchanged, total: lines.length };
  });
  
  // Escape HTML
  function escapeHtml(text: string): string {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }
  
  // Format line number
  function formatLineNum(num: number | null): string {
    if (num === null) return '';
    return String(num);
  }
</script>

<div class="diff-view" data-size={size} data-mode={mode}>
  <div class="diff-header">
    <span>📊 Diff View</span>
    <div class="diff-controls">
      <button 
        class="mode-btn" 
        class:active={mode === 'side-by-side'}
        onclick={() => mode = 'side-by-side'}
      >
        Side by Side
      </button>
      <button 
        class="mode-btn"
        class:active={mode === 'inline'}
        onclick={() => mode = 'inline'}
      >
        Inline
      </button>
    </div>
    <div class="diff-stats">
      <span class="stat added">+{stats().added}</span>
      <span class="stat removed">-{stats().removed}</span>
    </div>
  </div>
  
  <div class="diff-content">
    {#if !leftContent && !rightContent}
      <p class="placeholder">No changes to display</p>
    {:else if mode === 'side-by-side'}
      <!-- Side by side view -->
      <div class="side-by-side">
        <div class="diff-pane left">
          <div class="pane-header">{leftLabel}</div>
          <div class="pane-content">
            {#each diffLines() as line}
              <div class="diff-line" class:removed={line.type === 'removed'} class:unchanged={line.type === 'unchanged'}>
                <span class="line-num">{formatLineNum(line.leftLine)}</span>
                <span class="line-text">{line.leftText !== null ? escapeHtml(line.leftText) : ''}</span>
              </div>
            {/each}
          </div>
        </div>
        <div class="diff-pane right">
          <div class="pane-header">{rightLabel}</div>
          <div class="pane-content">
            {#each diffLines() as line}
              <div class="diff-line" class:added={line.type === 'added'} class:unchanged={line.type === 'unchanged'}>
                <span class="line-num">{formatLineNum(line.rightLine)}</span>
                <span class="line-text">{line.rightText !== null ? escapeHtml(line.rightText) : ''}</span>
              </div>
            {/each}
          </div>
        </div>
      </div>
    {:else}
      <!-- Inline (unified) view -->
      <div class="inline-view">
        <div class="inline-header">
          <span class="file-label">{leftLabel} → {rightLabel}</span>
        </div>
        <div class="inline-content">
          {#each diffLines() as line}
            <div 
              class="diff-line" 
              class:added={line.type === 'added'}
              class:removed={line.type === 'removed'}
              class:unchanged={line.type === 'unchanged'}
            >
              <span class="line-num left">{formatLineNum(line.leftLine)}</span>
              <span class="line-num right">{formatLineNum(line.rightLine)}</span>
              <span class="line-prefix">{line.type === 'added' ? '+' : line.type === 'removed' ? '-' : ' '}</span>
              <span class="line-text">
                {escapeHtml(line.type === 'removed' ? (line.leftText ?? '') : (line.rightText ?? line.leftText ?? ''))}
              </span>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  </div>
</div>

<style>
  .diff-view {
    height: 100%;
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    display: flex;
    flex-direction: column;
  }
  
  .diff-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--spacing-sm) var(--spacing-md);
    border-bottom: 1px solid var(--border-subtle);
    color: var(--text-primary);
  }
  
  .diff-controls {
    display: flex;
    gap: 2px;
    background: var(--bg-tertiary);
    border-radius: var(--radius-sm);
    padding: 2px;
  }
  
  .mode-btn {
    background: none;
    border: none;
    padding: 4px 12px;
    font-size: 0.75rem;
    color: var(--text-secondary);
    cursor: pointer;
    border-radius: var(--radius-sm);
  }
  
  .mode-btn:hover {
    color: var(--text-primary);
  }
  
  .mode-btn.active {
    background: var(--bg-primary);
    color: var(--text-primary);
  }
  
  .diff-stats {
    display: flex;
    gap: var(--spacing-sm);
    font-size: 0.75rem;
    font-family: var(--font-mono);
  }
  
  .stat.added {
    color: var(--success);
  }
  
  .stat.removed {
    color: var(--error);
  }
  
  .diff-content {
    flex: 1;
    overflow: hidden;
    display: flex;
  }
  
  .placeholder {
    color: var(--text-tertiary);
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
  }
  
  /* Side by side view */
  .side-by-side {
    display: flex;
    width: 100%;
    height: 100%;
  }
  
  .diff-pane {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  
  .diff-pane.left {
    border-right: 1px solid var(--border-subtle);
  }
  
  .pane-header {
    padding: var(--spacing-xs) var(--spacing-md);
    background: var(--bg-tertiary);
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--text-secondary);
  }
  
  .pane-content {
    flex: 1;
    overflow: auto;
    font-family: var(--font-mono);
    font-size: 0.8125rem;
    line-height: 1.4;
  }
  
  /* Inline view */
  .inline-view {
    width: 100%;
    display: flex;
    flex-direction: column;
  }
  
  .inline-header {
    padding: var(--spacing-xs) var(--spacing-md);
    background: var(--bg-tertiary);
    font-size: 0.75rem;
    color: var(--text-secondary);
  }
  
  .inline-content {
    flex: 1;
    overflow: auto;
    font-family: var(--font-mono);
    font-size: 0.8125rem;
    line-height: 1.4;
  }
  
  /* Diff lines */
  .diff-line {
    display: flex;
    white-space: pre;
    padding: 0 var(--spacing-sm);
    min-height: 1.4em;
  }
  
  .diff-line.added {
    background: rgba(46, 160, 67, 0.15);
  }
  
  .diff-line.removed {
    background: rgba(248, 81, 73, 0.15);
  }
  
  .diff-line.unchanged {
    background: transparent;
  }
  
  .line-num {
    display: inline-block;
    width: 4ch;
    text-align: right;
    color: var(--text-tertiary);
    padding-right: var(--spacing-sm);
    user-select: none;
    flex-shrink: 0;
  }
  
  .inline-view .line-num.left,
  .inline-view .line-num.right {
    width: 3ch;
  }
  
  .line-prefix {
    width: 1.5ch;
    text-align: center;
    flex-shrink: 0;
    font-weight: 600;
  }
  
  .diff-line.added .line-prefix {
    color: var(--success);
  }
  
  .diff-line.removed .line-prefix {
    color: var(--error);
  }
  
  .line-text {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  /* Scrollbar sync for side-by-side */
  .side-by-side .pane-content {
    scrollbar-width: thin;
  }
</style>
