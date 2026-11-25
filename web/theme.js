"use strict";

// Apply before CSS paints. Theme preferences stay on the player's device.
(() => {
  const key = "bingo-theme";
  const valid = value => value === "dark" || value === "light";
  const telegram = window.Telegram?.WebApp;
  const media = window.matchMedia?.("(prefers-color-scheme: dark)");
  let preference = null;
  try {
    const saved = localStorage.getItem(key);
    if (valid(saved)) preference = saved;
  } catch { /* Continue when storage is unavailable in the webview. */ }

  function automaticTheme() {
    if (telegram?.initData && valid(telegram.colorScheme)) return telegram.colorScheme;
    return media?.matches ? "dark" : "light";
  }

  function apply() {
    const theme = preference || automaticTheme();
    const changed = document.documentElement.dataset.theme !== theme;
    document.documentElement.dataset.theme = theme;
    const background = theme === "dark" ? "#101714" : "#f6f5f0";
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", background);
    if (telegram?.initData) {
      for (const [method, property, version] of [
        ["setHeaderColor", "headerColor", "6.9"],
        ["setBackgroundColor", "backgroundColor", "6.1"],
        ["setBottomBarColor", "bottomBarColor", "7.10"],
      ]) {
        if (telegram.isVersionAtLeast && !telegram.isVersionAtLeast(version)) continue;
        try {
          if (telegram[property] !== background) telegram[method]?.(background);
        } catch { /* Older clients can still use the in-page theme. */ }
      }
    }
    if (changed) window.dispatchEvent(new Event("bingo:themechange"));
  }

  window.BingoTheme = Object.freeze({
    get current() { return document.documentElement.dataset.theme; },
    toggle() {
      preference = this.current === "dark" ? "light" : "dark";
      try { localStorage.setItem(key, preference); } catch { /* Keep the choice for this session. */ }
      apply();
    },
    sync: apply,
  });

  telegram?.onEvent?.("themeChanged", apply);
  if (media?.addEventListener) media.addEventListener("change", apply);
  else media?.addListener?.(apply);
  window.addEventListener("storage", event => {
    if (event.key !== key && event.key !== null) return;
    preference = valid(event.newValue) ? event.newValue : null;
    apply();
  });
  apply();
})();
