/* Bank-app style lock for sessions that signed in with Face ID.
   Leaving the app (or no touch/typing) for the lock time shows a lock screen
   over the page; unlocking with Face ID or the password keeps unsaved work. */
(() => {
  "use strict";
  const lockScreen = document.getElementById("app-lock");
  if (!lockScreen) return;
  const after = Math.max(60, Number(lockScreen.dataset.lockAfter) || 300) * 1000;
  let lastActivity = Date.now();
  let hiddenAt = null;
  let locked = false;

  function csrfToken() {
    return document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || "";
  }

  function post(url) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Accept": "application/json", "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
      body: "{}",
      keepalive: true,
    }).then((response) => response.json()).catch(() => ({}));
  }

  function lock(tellServer = true) {
    if (locked) return;
    locked = true;
    if (tellServer) post("/unlock/lock/");
    lockScreen.hidden = false;
    document.documentElement.classList.add("app-locked");
    document.dispatchEvent(new CustomEvent("dhd-app-locked"));
  }

  document.addEventListener("dhd-faceid-unlocked", () => {
    locked = false;
    lastActivity = Date.now();
    lockScreen.hidden = true;
    document.documentElement.classList.remove("app-locked");
  });

  for (const name of ["pointerdown", "keydown", "touchstart", "wheel", "input"]) {
    window.addEventListener(name, () => { if (!locked) lastActivity = Date.now(); }, { passive: true, capture: true });
  }

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      hiddenAt = Date.now();
    } else if (hiddenAt !== null && Date.now() - hiddenAt > after) {
      lock();
    }
  });
  window.addEventListener("pageshow", (event) => {
    if (event.persisted && hiddenAt !== null && Date.now() - hiddenAt > after) lock();
  });

  window.setInterval(() => {
    if (locked || document.hidden) return;
    if (Date.now() - lastActivity > after) {
      lock();
      return;
    }
    // Still in use: keep the server from locking this session.
    post("/unlock/ping/").then((data) => { if (data.locked === true) lock(false); });
  }, 30000);
})();
