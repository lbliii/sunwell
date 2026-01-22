<!--
  Surface — Dynamic surface renderer (RFC-072)
  
  Renders the current surface layout with smooth transitions
  between compositions.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { fade, fly } from 'svelte/transition';
  import { 
    surface,
    loadRegistry,
    composeSurface,
  } from '../stores/surface.svelte';
  
  // Primitive components (dynamically imported)
  import CodeEditor from './primitives/CodeEditor.svelte';
  import Terminal from './primitives/Terminal.svelte';
  import TestRunner from './primitives/TestRunner.svelte';
  import DiffView from './primitives/DiffView.svelte';
  import Preview from './primitives/Preview.svelte';
  import Dependencies from './primitives/Dependencies.svelte';
  import KanbanBoard from './primitives/KanbanBoard.svelte';
  import Timeline from './primitives/Timeline.svelte';
  import GoalTree from './primitives/GoalTree.svelte';
  import TaskList from './primitives/TaskList.svelte';
  import Calendar from './primitives/Calendar.svelte';
  import Metrics from './primitives/Metrics.svelte';
  import ProseEditor from './primitives/ProseEditor.svelte';
  import Outline from './primitives/Outline.svelte';
  import References from './primitives/References.svelte';
  import WordCount from './primitives/WordCount.svelte';
  import DataTable from './primitives/DataTable.svelte';
  import Chart from './primitives/Chart.svelte';
  import QueryBuilder from './primitives/QueryBuilder.svelte';
  import Summary from './primitives/Summary.svelte';
  import MemoryPane from './primitives/MemoryPane.svelte';
  import DAGView from './primitives/DAGView.svelte';
  import BriefingCard from './primitives/BriefingCard.svelte';
  import FileTree from './FileTree.svelte';
  import { WriterSurface } from './writer';
  
  // Component registry for dynamic rendering
  const components: Record<string, any> = {
    CodeEditor,
    FileTree,
    Terminal,
    TestRunner,
    DiffView,
    Preview,
    Dependencies,
    KanbanBoard,
    Timeline,
    GoalTree,
    TaskList,
    Calendar,
    Metrics,
    ProseEditor,
    Outline,
    References,
    WordCount,
    DataTable,
    Chart,
    QueryBuilder,
    Summary,
    MemoryPane,
    DAGView,
    BriefingCard,
    WriterSurface,
  };
  
  interface Props {
    initialGoal?: string;
    projectPath?: string;
  }
  
  let { initialGoal, projectPath }: Props = $props();
  
  onMount(async () => {
    await loadRegistry();
    if (initialGoal) {
      await composeSurface(initialGoal, projectPath);
    }
  });
  
  function getComponent(id: string) {
    // Try direct match first
    if (components[id]) return components[id];
    
    // Try component name from registry
    const def = surface.registry.find(p => p.id === id);
    if (def && components[def.component]) {
      return components[def.component];
    }
    
    return null;
  }
  
  // Arrangement-specific grid classes
  const arrangementClasses: Record<string, string> = {
    standard: 'grid-standard',
    focused: 'grid-focused',
    split: 'grid-split',
    dashboard: 'grid-dashboard',
    writer: 'grid-writer',
  };
</script>

<div class="surface" class:composing={surface.isComposing}>
  {#if surface.isComposing}
    <div class="composing-overlay" transition:fade={{ duration: 150 }}>
      <div class="motes"></div>
      <span class="composing-text">Composing surface...</span>
    </div>
  {/if}
  
  {#if surface.error}
    <div class="error-banner" transition:fly={{ y: -20 }}>
      <span>⚠️ {surface.error}</span>
    </div>
  {/if}
  
  {#if surface.layout}
    {@const PrimaryComponent = getComponent(surface.layout.primary.id)}
    <div 
      class="surface-grid {arrangementClasses[surface.layout.arrangement]}"
      in:fade={{ duration: 200, delay: 100 }}
    >
      <!-- Primary primitive (always present) -->
      <div class="primary-slot" data-size={surface.layout.primary.size}>
        {#if PrimaryComponent}
          <PrimaryComponent
            {...surface.layout.primary.props}
            size={surface.layout.primary.size}
          />
        {:else}
          <div class="unknown-primitive">
            Unknown: {surface.layout.primary.id}
          </div>
        {/if}
      </div>
      
      <!-- Secondary primitives (sidebars, panels) -->
      {#if surface.layout.secondary.length > 0}
        <div class="secondary-slots">
          {#each surface.layout.secondary as prim (prim.id)}
            {@const SecondaryComponent = getComponent(prim.id)}
            <div 
              class="secondary-slot"
              data-size={prim.size}
              in:fly={{ x: prim.size === 'sidebar' ? -20 : 0, y: prim.size === 'bottom' ? 20 : 0, duration: 200 }}
            >
              {#if SecondaryComponent}
                <SecondaryComponent
                  {...prim.props}
                  size={prim.size}
                />
              {:else}
                <div class="unknown-primitive">
                  Unknown: {prim.id}
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
      
      <!-- Contextual primitives (widgets, floating) -->
      {#if surface.layout.contextual.length > 0}
        <div class="contextual-slots">
          {#each surface.layout.contextual as prim (prim.id)}
            {@const ContextualComponent = getComponent(prim.id)}
            <div 
              class="contextual-slot"
              data-size={prim.size}
              in:fly={{ y: -10, duration: 200 }}
            >
              {#if ContextualComponent}
                <ContextualComponent
                  {...prim.props}
                  size={prim.size}
                />
              {:else}
                <div class="unknown-primitive">
                  Unknown: {prim.id}
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {:else}
    <div class="empty-surface">
      <div class="empty-content">
        <span class="empty-icon">✨</span>
        <p>Enter a goal to begin</p>
      </div>
    </div>
  {/if}
</div>

<style>
  .surface {
    position: relative;
    width: 100%;
    height: 100%;
    overflow: hidden;
    background: var(--bg-primary);
  }
  
  .composing-overlay {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: rgba(13, 13, 13, 0.85);
    z-index: 100;
  }
  
  .composing-text {
    color: var(--gold);
    font-size: 1rem;
    margin-top: var(--spacing-md);
  }
  
  .error-banner {
    position: absolute;
    top: var(--spacing-md);
    left: 50%;
    transform: translateX(-50%);
    padding: var(--spacing-sm) var(--spacing-md);
    background: var(--error);
    color: white;
    border-radius: var(--radius-md);
    z-index: 50;
  }
  
  .surface-grid {
    display: grid;
    width: 100%;
    height: 100%;
    gap: var(--spacing-sm);
    padding: var(--spacing-sm);
  }
  
  /* Standard: Primary fills, secondary in sidebar/bottom */
  .grid-standard {
    grid-template-columns: auto 1fr;
    grid-template-rows: 1fr auto;
    grid-template-areas:
      "secondary primary"
      "bottom bottom";
  }
  
  /* Focused: Primary only, minimal secondary */
  .grid-focused {
    grid-template-columns: 1fr;
    grid-template-rows: 1fr;
    grid-template-areas: "primary";
  }
  
  /* Split: Primary and one secondary side-by-side */
  .grid-split {
    grid-template-columns: 1fr 1fr;
    grid-template-rows: 1fr;
    grid-template-areas: "primary secondary";
  }
  
  /* Dashboard: Multiple panels in grid */
  .grid-dashboard {
    grid-template-columns: repeat(2, 1fr);
    grid-template-rows: repeat(2, 1fr);
    grid-template-areas:
      "primary secondary"
      "tertiary contextual";
  }
  
  /* Writer: Full-screen writing environment (RFC-086) */
  .grid-writer {
    grid-template-columns: 1fr;
    grid-template-rows: 1fr;
    grid-template-areas: "primary";
    padding: 0;
    gap: 0;
  }
  
  .primary-slot {
    grid-area: primary;
    min-height: 0;
    overflow: hidden;
    border-radius: var(--radius-lg);
    background: var(--bg-secondary);
  }
  
  .secondary-slots {
    display: contents;
  }
  
  .secondary-slot {
    overflow: hidden;
    border-radius: var(--radius-md);
    background: var(--bg-secondary);
  }
  
  .secondary-slot[data-size="sidebar"] {
    grid-area: secondary;
    width: 280px;
    overflow-y: auto;
  }
  
  .secondary-slot[data-size="bottom"] {
    grid-area: bottom;
    height: 200px;
  }
  
  .secondary-slot[data-size="panel"] {
    grid-area: secondary;
    overflow: auto;
  }
  
  .secondary-slot[data-size="split"] {
    overflow: auto;
  }
  
  .contextual-slots {
    position: fixed;
    top: var(--spacing-lg);
    right: var(--spacing-lg);
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
    z-index: 50;
  }
  
  .contextual-slot {
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    box-shadow: var(--glow-gold-subtle, 0 0 20px rgba(218, 165, 32, 0.1));
    overflow: hidden;
  }
  
  .contextual-slot[data-size="widget"] {
    width: 240px;
    max-height: 180px;
  }
  
  .contextual-slot[data-size="floating"] {
    width: 320px;
    max-height: 400px;
  }
  
  .empty-surface {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
  }
  
  .empty-content {
    text-align: center;
  }
  
  .empty-icon {
    font-size: 3rem;
    display: block;
    margin-bottom: var(--spacing-md);
  }
  
  .empty-content p {
    color: var(--text-secondary);
    font-size: 1.125rem;
  }
  
  .unknown-primitive {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-tertiary);
    font-style: italic;
  }
  
  /* Rising motes animation for composing state */
  .motes {
    position: absolute;
    width: 100px;
    height: 100px;
    background-image: radial-gradient(
      circle at 50% 100%,
      var(--gold) 0%,
      transparent 60%
    );
    opacity: 0.3;
    animation: motes-rise 2s ease-in-out infinite;
  }
  
  @keyframes motes-rise {
    0%, 100% { 
      transform: translateY(0) scale(1); 
      opacity: 0.3; 
    }
    50% { 
      transform: translateY(-30px) scale(1.1); 
      opacity: 0.5; 
    }
  }
</style>
