<!--
  BaseLayout — Base layout structure for all project types
  
  Provides the common sidebar/content/panel structure that
  adaptive layouts build upon.
-->
<script lang="ts">
  import { showSidebar, toggleSidebar } from '../stores/layout';
  
  export let sidebarWidth = 250;
</script>

<div class="layout">
  <!-- Sidebar Toggle (visible when collapsed) -->
  {#if !$showSidebar}
    <button class="sidebar-toggle" on:click={toggleSidebar} aria-label="Show sidebar">
      ›
    </button>
  {/if}
  
  <!-- Sidebar -->
  {#if $showSidebar}
    <aside class="sidebar" style="width: {sidebarWidth}px">
      <div class="sidebar-header">
        <slot name="sidebar-header" />
        <button class="sidebar-close" on:click={toggleSidebar} aria-label="Hide sidebar">
          ‹
        </button>
      </div>
      <div class="sidebar-content">
        <slot name="sidebar" />
      </div>
    </aside>
  {/if}
  
  <!-- Main Content -->
  <main class="main">
    <slot />
  </main>
  
  <!-- Right Panel (optional) -->
  <slot name="panel" />
</div>

<style>
  .layout {
    display: flex;
    height: 100%;
    background: var(--bg-primary);
  }
  
  /* Sidebar Toggle */
  .sidebar-toggle {
    position: fixed;
    left: 0;
    top: 50%;
    transform: translateY(-50%);
    width: 24px;
    height: 48px;
    background: var(--bg-secondary);
    border: var(--border-width) solid var(--border-color);
    border-left: none;
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
    color: var(--text-tertiary);
    font-size: var(--text-lg);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: var(--z-sticky);
    transition: color var(--transition-fast), background var(--transition-fast);
  }
  
  .sidebar-toggle:hover {
    color: var(--text-primary);
    background: var(--bg-tertiary);
  }
  
  /* Sidebar */
  .sidebar {
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    background: var(--bg-secondary);
    border-right: var(--border-width) solid var(--border-color);
    overflow: hidden;
  }
  
  .sidebar-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-3) var(--space-4);
    border-bottom: var(--border-width) solid var(--border-color);
    min-height: 48px;
  }
  
  .sidebar-close {
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-tertiary);
    font-size: var(--text-lg);
    border-radius: var(--radius-sm);
    transition: color var(--transition-fast), background var(--transition-fast);
  }
  
  .sidebar-close:hover {
    color: var(--text-primary);
    background: var(--bg-tertiary);
  }
  
  .sidebar-content {
    flex: 1;
    overflow-y: auto;
  }
  
  /* Main */
  .main {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
</style>
