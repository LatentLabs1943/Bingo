"use strict";

(() => {
  const form = document.getElementById("room-settings-form");
  const status = document.getElementById("admin-status");
  const save = document.getElementById("save-room-settings");
  let version = null;
  function priceAccess(allowed) {
    const input = form.elements.namedItem("entry_credits");
    input.disabled = !allowed;
    input.closest("label").hidden = !allowed;
    if (!allowed) input.value = "";
  }
  window.addEventListener("bingo:state", event => {
    document.getElementById("admin-button").hidden = !event.detail.user.is_admin;
    priceAccess(!!event.detail.user.is_owner);
    if (!event.detail.user.is_admin) {
      if (document.getElementById("admin-dialog").open) document.getElementById("admin-dialog").close();
      form.reset(); priceAccess(false); version = null; save.disabled = true; status.textContent = "";
    }
  });
  document.getElementById("admin-button").addEventListener("click", async () => {
    if (!snapshot?.user.is_admin) return;
    document.getElementById("admin-dialog").showModal();
    status.textContent = t("loading"); save.disabled = true; version = null;
    try {
      const data = await api("/api/admin/settings");
      if (!snapshot?.user.is_admin) return;
      version = data.version;
      for (const [key, value] of Object.entries(data.settings)) if (form.elements.namedItem(key)) form.elements.namedItem(key).value = value;
      priceAccess(data.can_edit_price === true);
      status.textContent = ""; save.disabled = false;
    } catch (error) { status.textContent = error.message; }
  });
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (version === null || !snapshot?.user.is_admin) return;
    const values = Object.fromEntries(new FormData(form));
    for (const key of Object.keys(values)) if (key !== "draw_mode") values[key] = Number(values[key]);
    if (values.min_players > values.seat_limit) { status.textContent = t("invalidSettings"); return; }
    save.disabled = true;
    try {
      const data = await api("/api/admin/settings", {version, ...values}, "PUT");
      version = data.version;
      status.textContent = t(data.applies === "current_round" ? "settingsCurrent" : "settingsNext");
      await enqueue(async () => acceptState(await api("/api/state")));
    } catch (error) { status.textContent = error.message; }
    finally { save.disabled = false; }
  });
})();
