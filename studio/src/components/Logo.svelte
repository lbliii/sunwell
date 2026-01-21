<!--
  Logo — Sunwell ornate sun logo with title (Svelte 5)
-->
<script lang="ts">
  import { Size } from '$lib/constants';
  
  interface Props {
    size?: 'sm' | 'md' | 'lg';
  }
  
  let { size = Size.MD }: Props = $props();
</script>

<div class="logo {size}">
  <img src="/sunwell.svg" alt="Sunwell Logo" class="logo-image" />
</div>

<style>
  .logo {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }
  
  .logo-image {
    display: block;
    width: 100%;
    height: auto;
    object-fit: contain;
  }
  
  /* Sizes */
  .sm .logo-image {
    width: 120px;
    max-height: 150px;
  }
  
  .md .logo-image {
    width: 200px;
    max-height: 250px;
  }
  
  .lg .logo-image {
    width: 320px;
    max-height: 400px;
  }
</style>
