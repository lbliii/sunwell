<!--
  Logo — Sunwell sun logo with title
-->
<script lang="ts">
  export let size: 'sm' | 'md' | 'lg' = 'md';
  export let showTitle = true;
</script>

<div class="logo {size}">
  <span class="sun">☀️</span>
  {#if showTitle}
    <span class="title">SUNWELL</span>
  {/if}
</div>

<style>
  .logo {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-2);
  }
  
  .sun {
    line-height: 1;
  }
  
  .title {
    font-family: var(--font-mono);
    font-weight: 500;
    letter-spacing: 0.2em;
    color: var(--text-primary);
  }
  
  /* Sizes */
  .sm .sun {
    font-size: 24px;
  }
  
  .sm .title {
    font-size: var(--text-sm);
  }
  
  .md .sun {
    font-size: 48px;
  }
  
  .md .title {
    font-size: var(--text-lg);
  }
  
  .lg .sun {
    font-size: 72px;
  }
  
  .lg .title {
    font-size: var(--text-2xl);
  }
</style>
