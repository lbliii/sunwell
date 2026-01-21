<!--
  BaseLayout — Base layout structure for all project types (Svelte 5)
-->
<script lang="ts">
  import type { Snippet } from 'svelte';
  import { layout, toggleSidebar } from '../stores/layout.svelte';
  
  interface Props {
    sidebarWidth?: number;
    sidebarHeader?: Snippet;
    sidebar?: Snippet;
    panel?: Snippet;
    children: Snippet;
  }
  
  let { sidebarWidth = 250, sidebarHeader, sidebar, panel, children }: Props = $props();
</script>

<div class="layout">
  {#if !layout.isSidebarOpen}
    <button class="sidebar-toggle" onclick={toggleSidebar} aria-label="Show sidebar">›</button>
  {/if}
  
  {#if layout.isSidebarOpen}
    <aside class="sidebar" style="width: {sidebarWidth}px">
      <div class="sidebar-header">
        {#if sidebarHeader}{@render sidebarHeader()}{/if}
        <button class="sidebar-close" onclick={toggleSidebar} aria-label="Hide sidebar">‹</button>
      </div>
      <div class="sidebar-content">
        {#if sidebar}{@render sidebar()}{/if}
      </div>
    </aside>
  {/if}
  
  <main class="main">
    {@render children()}
  </main>
  
  {#if panel}{@render panel()}{/if}
</div>

<style>
  .layout { display: flex; height: 100%; background: var(--bg-primary); }
  .sidebar-toggle { position: fixed; left: 0; top: 50%; transform: translateY(-50%); width: 24px; height: 48px; background: var(--bg-secondary); border: var(--border-width) solid var(--border-color); border-left: none; border-radius: 0 var(--radius-sm) var(--radius-sm) 0; color: var(--text-tertiary); font-size: var(--text-lg); display: flex; align-items: center; justify-content: center; z-index: var(--z-sticky); transition: color var(--transition-fast), background var(--transition-fast); }
  .sidebar-toggle:hover { color: var(--text-primary); background: var(--bg-tertiary); }
  .sidebar { flex-shrink: 0; display: flex; flex-direction: column; background: var(--bg-secondary); border-right: var(--border-width) solid var(--border-color); overflow: hidden; }
  .sidebar-header { display: flex; align-items: center; justify-content: space-between; padding: var(--space-3) var(--space-4); border-bottom: var(--border-width) solid var(--border-color); min-height: 48px; }
  .sidebar-close { width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; color: var(--text-tertiary); font-size: var(--text-lg); border-radius: var(--radius-sm); transition: color var(--transition-fast), background var(--transition-fast); }
  .sidebar-close:hover { color: var(--text-primary); background: var(--bg-tertiary); }
  .sidebar-content { flex: 1; overflow-y: auto; }
  .main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
</style>
