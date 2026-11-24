/* Bank-app style session lock for every account (owner requests 23-24/11/2026,
   "giống app ACB"). Leaving the app (no tab of it on screen) for the away time,
   or not touching it for the idle time, shows the "Xin chào – đăng nhập lại"
   screen over the page. Face ID (if turned on for this device) or the password
   continues, and unsaved work under the lock screen is kept. All tabs of the app
   share one state, and the server enforces the same lock
   (passkeys.middleware.AppLockMiddleware). */
(() => {
  "use strict";
  const screen = document.getElementById("app-lock");
  if (!screen) return;
  const AWAY = Math.max(15, Number(screen.dataset.lockAway) || 60) * 1000;
  const IDLE = Math.max(60, Number(screen.dataset.lockIdle) || 300) * 1000;
  const minutes = Number(screen.dataset.idleMinutes) || Math.round(IDLE / 60000);
  const KEY = { seen: "dhd-app-seen", active: "dhd-app-active", locked: "dhd-app-locked", unlocked: "dhd-app-unlocked" };
  const REASON = {
    away: "Bạn vừa rời khỏi phần mềm. Vui lòng đăng nhập lại để tiếp tục.",
    idle: `Phiên đăng nhập đã hết hạn do không thao tác trong ${minutes} phút. Vui lòng đăng nhập lại.`,
    expired: "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại để tiếp tục.",
  };
  const store = {
    get(key) { try { return window.localStorage.getItem(key); } catch { return null; } },
    set(key, value) { try { window.localStorage.setItem(key, value); } catch { /* private mode */ } },
  };
  const stamp = (key) => Number(store.get(key)) || 0;
  let locked = false;
  let lastActivity = Date.now();
  let lastShared = 0;
  let lastPing = Date.now();
  let hiddenAt = 0;

  // Like a banking app, this device remembers who signed in (never the password).
  if (screen.dataset.account) {
    store.set("dhd-last-user", JSON.stringify({
      u: screen.dataset.account,
      n: screen.dataset.accountName || screen.dataset.account,
    }));
  }

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

  // A call in progress counts as use: never lock over it.
  const inCall = () => Boolean(document.querySelector("#chat-call-dialog[open]"));

  function seenNow(active) {
    const now = Date.now();
    store.set(KEY.seen, String(now));
    if (active) store.set(KEY.active, String(now));
  }

  function lock(reason, { server = true, tabs = true } = {}) {
    if (locked) return;
    locked = true;
    if (server) post("/unlock/lock/");
    if (tabs) store.set(KEY.locked, String(Date.now()));
    const text = screen.querySelector("[data-lock-reason]");
    if (text) text.textContent = REASON[reason] || REASON.expired;
    const status = screen.querySelector("[data-pk-status]");
    if (status) {
      status.textContent = "";
      status.hidden = true;
    }
    const password = screen.querySelector('input[name="password"]');
    if (password) password.value = "";
    if (document.activeElement && !screen.contains(document.activeElement)) document.activeElement.blur?.();
    screen.hidden = false;
    document.documentElement.classList.add("app-locked");
    document.dispatchEvent(new CustomEvent("dhd-app-locked", { detail: { reason } }));
  }

  function unlocked() {
    if (!locked) return;
    locked = false;
    lastActivity = Date.now();
    seenNow(true);
    screen.hidden = true;
    document.documentElement.classList.remove("app-locked");
  }

  document.addEventListener("dhd-faceid-unlocked", unlocked);
  window.addEventListener("storage", (event) => {
    if (!event.newValue) return;
    if (event.key === KEY.locked) lock("expired", { server: false, tabs: false });
    else if (event.key === KEY.unlocked) unlocked();
  });

  const activity = () => {
    if (locked) return;
    const now = Date.now();
    lastActivity = now;
    if (now - lastShared > 5000) {
      lastShared = now;
      seenNow(true);
    }
  };
  for (const name of ["pointerdown", "pointermove", "keydown", "touchstart", "wheel", "input", "scroll"]) {
    window.addEventListener(name, activity, { passive: true, capture: true });
  }

  function cameBack() {
    if (locked) return;
    if (inCall()) {
      seenNow(true);
      return;
    }
    const seen = Math.max(stamp(KEY.seen), hiddenAt);
    if (seen && Date.now() - seen > AWAY) lock("away");
    else seenNow(false);
  }

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      hiddenAt = Date.now();
      if (!locked) seenNow(false);
    } else if (locked) {
      // Back to a tab that was locked meanwhile: offer Face ID now.
      document.dispatchEvent(new CustomEvent("dhd-app-locked", { detail: { reason: "expired" } }));
    } else {
      cameBack();
    }
  });
  window.addEventListener("pageshow", (event) => { if (event.persisted) cameBack(); });

  window.setInterval(() => {
    if (locked || document.hidden) return;
    const now = Date.now();
    if (inCall()) {
      lastActivity = now;
      seenNow(true);
    } else {
      store.set(KEY.seen, String(now));
      if (now - Math.max(lastActivity, stamp(KEY.active)) > IDLE) {
        lock("idle");
        return;
      }
    }
    if (now - lastPing >= 30000) {
      lastPing = now;
      // Still in use: keep the server from locking this session.
      post("/unlock/ping/").then((data) => {
        if (data.locked === true) lock("expired", { server: false });
      });
    }
  }, 5000);

  seenNow(true);
})();
