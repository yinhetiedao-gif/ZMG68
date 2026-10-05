<script>
  import { onMount } from "svelte";
  import Logo from "./Logo.svelte";
  import { themeStore } from "../routes/stores.js";
  export let segment;
  let theme = "light";
  onMount(() => {
    theme = localStorage.getItem("defaultNewTheme") === "dark" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", theme);
    themeStore.set(theme);
  });
  function changeTheme() {
    theme = theme === "light" ? "dark" : "light";
    localStorage.setItem("defaultNewTheme", theme);
    document.documentElement.setAttribute("data-theme", theme);
    themeStore.set(theme);
  }
</script>

<nav>
  <a href="." aria-current={segment === undefined ? "page" : undefined}><Logo /></a>
  <div class="links">
    <a href="/" rel="external">← 返回图案实验室</a>
    <button on:click={changeTheme} aria-label="切换明暗主题">切换主题</button>
  </div>
</nav>
<style>
  nav { display:flex; justify-content:space-between; align-items:center; gap:1rem; padding:0.8rem 1rem; background:var(--main-bg-color); color:var(--primary-text-color); border-bottom:1px solid var(--accent-color); }
  a { color:var(--secondary-color); text-decoration:none; }
  .links { display:flex; align-items:center; gap:1rem; }
  button { padding:0.4rem 0.7rem; border-radius:0.4rem; background:var(--accent-color); }
  @media(max-width:600px) { nav { flex-wrap:wrap; } .links { font-size:0.85rem; } }
</style>
