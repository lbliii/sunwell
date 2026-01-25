<!--
  Gallery.svelte — Component showcase for visual testing (RFC-097)
  
  Displays all primitives and blocks with various states.
  Used for visual regression testing and design review.
  
  Access at /gallery — Development/QA tool, not user-facing.
-->
<script lang="ts">
  import { fade, fly } from 'svelte/transition';
  
  // Import primitives for showcase
  import CodeBlock from '../components/primitives/CodeBlock.svelte';
  import ThinkingBlock from '../components/blocks/ThinkingBlock.svelte';
  
  // Component categories with their status (readonly to prevent mutation)
  const categories = [
    { 
      name: 'Code', 
      icon: '💻',
      components: [
        { name: 'CodeBlock', status: 's-tier' },
        { name: 'CodeEditor', status: 'needs-work' },
        { name: 'Terminal', status: 'acceptable' },
        { name: 'DiffView', status: 'acceptable' },
        { name: 'Preview', status: 'good' },
        { name: 'TestRunner', status: 'needs-work' },
      ] 
    },
    { 
      name: 'Planning', 
      icon: '📋',
      components: [
        { name: 'KanbanBoard', status: 'acceptable' },
        { name: 'Timeline', status: 'good' },
        { name: 'TaskList', status: 'acceptable' },
        { name: 'GoalTree', status: 'needs-work' },
        { name: 'DAGView', status: 'good' },
      ] 
    },
    { 
      name: 'Writing', 
      icon: '✍️',
      components: [
        { name: 'ProseEditor', status: 'acceptable' },
        { name: 'Outline', status: 'acceptable' },
        { name: 'References', status: 'needs-work' },
        { name: 'WordCount', status: 'acceptable' },
      ] 
    },
    { 
      name: 'Data', 
      icon: '📊',
      components: [
        { name: 'DataTable', status: 'acceptable' },
        { name: 'Chart', status: 'placeholder' },
        { name: 'Metrics', status: 'placeholder' },
        { name: 'Summary', status: 'needs-work' },
        { name: 'QueryBuilder', status: 'placeholder' },
      ] 
    },
    {
      name: 'Blocks',
      icon: '🧱',
      components: [
        { name: 'ThinkingBlock', status: 's-tier' },
        { name: 'ConversationBlock', status: 'good' },
        { name: 'ProjectsBlock', status: 's-tier' },
        { name: 'ValidationBlock', status: 'acceptable' },
        { name: 'ModelComparisonBlock', status: 's-tier' },
      ]
    },
    {
      name: 'Pages',
      icon: '📄',
      components: [
        { name: 'Home', status: 's-tier' },
        { name: 'Demo', status: 's-tier' },
        { name: 'Interface', status: 'needs-work' },
        { name: 'Library', status: 'needs-work' },
        { name: 'Planning', status: 'good' },
      ]
    },
  ] as const;
  
  let activeCategory = $state(categories[0]);
  let activeComponent = $state(categories[0].components[0]);
  
  // Quality rubric checklist (readonly to prevent mutation)
  const rubric = [
    { id: 'tokens', label: 'Token Compliance', desc: 'Uses CSS variables, no hardcoded colors' },
    { id: 'hierarchy', label: 'Visual Hierarchy', desc: 'Clear primary/secondary/tertiary levels' },
    { id: 'interactions', label: 'Micro-Interactions', desc: 'Hover, focus, active states' },
    { id: 'motion', label: 'Motion', desc: 'Entrance animations, feedback' },
    { id: 'typography', label: 'Typography', desc: 'Correct font families and scale' },
  ] as const;
  
  let checks = $state<Record<string, boolean>>({});
  
  // Computed pass count - avoid recalculating in template
  const passedChecksCount = $derived(Object.values(checks).filter(Boolean).length);
  
  // Status badge colors
  function getStatusColor(status: string): string {
    switch (status) {
      case 's-tier': return 'var(--success)';
      case 'good': return 'var(--ui-gold)';
      case 'acceptable': return 'var(--text-secondary)';
      case 'needs-work': return 'var(--warning)';
      case 'placeholder': return 'var(--error)';
      default: return 'var(--text-tertiary)';
    }
  }
  
  // Sample code for CodeBlock demo
  const sampleCode = `def divide(a: float, b: float) -> float:
    """Divide two numbers with error handling."""
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero")
    
    # Perform the division
    result = a / b
    return result

@dataclass(frozen=True, slots=True)
class Config:
    """Application configuration."""
    name: str
    value: int = 42
    enabled: bool = True`;
</script>

<div class="gallery" in:fade={{ duration: 200 }}>
  <aside class="sidebar">
    <header class="gallery-header">
      <h1 class="gallery-title">Component Gallery</h1>
      <p class="gallery-subtitle">S-Tier quality testing surface</p>
    </header>
    
    <nav class="categories">
      {#each categories as category, i (category.name)}
        <div class="category" in:fly={{ x: -20, delay: i * 50, duration: 200 }}>
          <button 
            class="category-header"
            class:active={activeCategory === category}
            onclick={() => { activeCategory = category; activeComponent = category.components[0]; }}
          >
            <span class="category-icon">{category.icon}</span>
            <span class="category-name">{category.name}</span>
            <span class="category-count">{category.components.length}</span>
          </button>
          
          {#if activeCategory === category}
            <div class="component-list" in:fly={{ y: -10, duration: 150 }}>
              {#each category.components as component (component.name)}
                <button 
                  class="component-btn"
                  class:active={activeComponent === component}
                  onclick={() => activeComponent = component}
                >
                  <span class="component-name">{component.name}</span>
                  <span 
                    class="status-dot" 
                    style:background={getStatusColor(component.status)}
                    title={component.status}
                  ></span>
                </button>
              {/each}
            </div>
          {/if}
        </div>
      {/each}
    </nav>
    
    <footer class="sidebar-footer">
      <div class="legend">
        <span class="legend-item"><span class="dot" style:background="var(--success)"></span> S-Tier</span>
        <span class="legend-item"><span class="dot" style:background="var(--ui-gold)"></span> Good</span>
        <span class="legend-item"><span class="dot" style:background="var(--text-secondary)"></span> Acceptable</span>
        <span class="legend-item"><span class="dot" style:background="var(--warning)"></span> Needs Work</span>
        <span class="legend-item"><span class="dot" style:background="var(--error)"></span> Placeholder</span>
      </div>
    </footer>
  </aside>
  
  <main class="preview">
    <header class="preview-header">
      <h2 class="component-name-title">{activeComponent.name}</h2>
      <span 
        class="status-badge"
        style:background={getStatusColor(activeComponent.status)}
      >
        {activeComponent.status.replace('-', ' ')}
      </span>
    </header>
    
    <div class="component-frame">
      <!-- Dynamic component preview -->
      {#if activeComponent.name === 'CodeBlock'}
        <div class="demo-area">
          <CodeBlock 
            code={sampleCode}
            language="python"
            filename="example.py"
            showLineNumbers={true}
          />
        </div>
      {:else if activeComponent.name === 'ThinkingBlock'}
        <div class="demo-area">
          <ThinkingBlock 
            model="claude-opus-4"
            tokens={247}
            tokensPerSecond={42.5}
            elapsed={5.8}
            thinking="Analyzing the code structure and identifying potential improvements..."
            phase="analysis"
          />
          <div style="margin-top: var(--space-4);">
            <ThinkingBlock 
              model="claude-opus-4"
              tokens={512}
              elapsed={12.1}
              isComplete={true}
              ttft={145}
            />
          </div>
        </div>
      {:else}
        <div class="frame-placeholder">
          <span class="placeholder-icon">🎨</span>
          <p class="placeholder-text">Component: {activeComponent.name}</p>
          <p class="placeholder-hint">Add demo content here</p>
        </div>
      {/if}
    </div>
    
    <section class="quality-section">
      <h3>Quality Rubric</h3>
      <div class="rubric-grid">
        {#each rubric as item (item.id)}
          <label class="rubric-item">
            <input 
              type="checkbox" 
              bind:checked={checks[item.id]}
            />
            <div class="rubric-content">
              <span class="rubric-label">{item.label}</span>
              <span class="rubric-desc">{item.desc}</span>
            </div>
          </label>
        {/each}
      </div>
      
      <div class="score">
        <span class="score-label">Score:</span>
        <span class="score-value">{passedChecksCount}</span>
        <span class="score-total">/ {rubric.length}</span>
      </div>
    </section>
  </main>
</div>

<style>
  .gallery {
    display: grid;
    grid-template-columns: 280px 1fr;
    height: 100vh;
    background: var(--bg-primary);
  }
  
  .sidebar {
    display: flex;
    flex-direction: column;
    background: var(--bg-secondary);
    border-right: 1px solid var(--border-subtle);
  }
  
  .gallery-header {
    padding: var(--space-6) var(--space-4);
    border-bottom: 1px solid var(--border-subtle);
  }
  
  .gallery-title {
    font-family: var(--font-serif);
    font-size: var(--text-2xl);
    color: var(--text-gold);
    margin: 0 0 var(--space-1);
  }
  
  .gallery-subtitle {
    font-size: var(--text-sm);
    color: var(--text-tertiary);
    margin: 0;
  }
  
  .categories {
    flex: 1;
    overflow-y: auto;
    padding: var(--space-4);
  }
  
  .category {
    margin-bottom: var(--space-2);
  }
  
  .category-header {
    width: 100%;
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    background: transparent;
    border: 1px solid transparent;
    border-radius: var(--radius-md);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all var(--transition-fast);
    font-family: var(--font-sans);
    font-size: var(--text-sm);
    text-align: left;
  }
  
  .category-header:hover {
    background: var(--bg-tertiary);
    color: var(--text-primary);
  }
  
  .category-header.active {
    background: var(--accent-hover);
    border-color: var(--border-default);
    color: var(--text-gold);
  }
  
  .category-icon {
    font-size: var(--text-base);
  }
  
  .category-name {
    flex: 1;
    font-weight: 500;
  }
  
  .category-count {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    background: var(--bg-tertiary);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-full);
  }
  
  .component-list {
    padding-left: var(--space-8);
    margin-top: var(--space-1);
  }
  
  .component-btn {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-1) var(--space-2);
    background: transparent;
    border: none;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    cursor: pointer;
    transition: all var(--transition-fast);
    text-align: left;
  }
  
  .component-btn:hover {
    color: var(--text-primary);
    background: var(--bg-tertiary);
  }
  
  .component-btn.active {
    color: var(--text-gold);
    background: var(--accent-hover);
  }
  
  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: var(--radius-full);
    flex-shrink: 0;
  }
  
  .sidebar-footer {
    padding: var(--space-4);
    border-top: 1px solid var(--border-subtle);
  }
  
  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }
  
  .legend-item {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .dot {
    width: 8px;
    height: 8px;
    border-radius: var(--radius-full);
  }
  
  .preview {
    padding: var(--space-6);
    overflow-y: auto;
  }
  
  .preview-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-6);
  }
  
  .component-name-title {
    font-family: var(--font-mono);
    font-size: var(--text-xl);
    color: var(--text-primary);
    margin: 0;
  }
  
  .status-badge {
    font-size: var(--text-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    color: var(--bg-primary);
  }
  
  .component-frame {
    background: var(--bg-secondary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-lg);
    min-height: 400px;
    margin-bottom: var(--space-6);
    overflow: hidden;
  }
  
  .demo-area {
    padding: var(--space-6);
  }
  
  .frame-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 400px;
    text-align: center;
  }
  
  .placeholder-icon {
    font-size: 3rem;
    margin-bottom: var(--space-4);
    opacity: 0.5;
  }
  
  .placeholder-text {
    font-family: var(--font-mono);
    font-size: var(--text-lg);
    color: var(--text-secondary);
    margin: 0 0 var(--space-2);
  }
  
  .placeholder-hint {
    font-size: var(--text-sm);
    color: var(--text-tertiary);
    margin: 0;
  }
  
  .quality-section h3 {
    font-size: var(--text-lg);
    color: var(--text-primary);
    margin: 0 0 var(--space-4);
  }
  
  .rubric-grid {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  
  .rubric-item {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3);
    padding: var(--space-3);
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: background var(--transition-fast);
  }
  
  .rubric-item:hover {
    background: var(--bg-tertiary);
  }
  
  .rubric-item input[type="checkbox"] {
    width: 18px;
    height: 18px;
    accent-color: var(--accent);
    cursor: pointer;
    flex-shrink: 0;
    margin-top: 2px;
  }
  
  .rubric-content {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  
  .rubric-label {
    font-weight: 500;
    color: var(--text-primary);
  }
  
  .rubric-desc {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .score {
    margin-top: var(--space-4);
    padding: var(--space-3);
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
  }
  
  .score-label {
    color: var(--text-secondary);
  }
  
  .score-value {
    font-family: var(--font-mono);
    font-size: var(--text-2xl);
    font-weight: 600;
    color: var(--text-gold);
  }
  
  .score-total {
    font-family: var(--font-mono);
    font-size: var(--text-lg);
    color: var(--text-tertiary);
  }
</style>
