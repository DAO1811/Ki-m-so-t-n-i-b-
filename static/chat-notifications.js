/* Visible-session notifications only. No private message text in browser alerts. */
(() => {
  "use strict";
  const badge = document.getElementById("chat-global-unread");
  if (!badge) return;
  const dialog = document.getElementById("chat-incoming"),
    ignored = new Set();
  let busy = false,
    timer,
    failures = 0,
    stopped = false;
  const activity = (window.DHDChatActivity = {
    lastActive: Date.now(),
    hiddenSince: document.hidden ? Date.now() : 0,
    canPoll() {
      if (document.getElementById("chat-call-dialog")?.open) return true;
      return (
        Date.now() - this.lastActive < 15 * 60 * 1000 &&
        !(
          document.hidden &&
          this.hiddenSince &&
          Date.now() - this.hiddenSince > 5 * 60 * 1000
        )
      );
    },
  });
  function activate() {
    const paused = !activity.canPoll();
    activity.lastActive = Date.now();
    if (paused) {
      update();
      window.dispatchEvent(new Event("chat-resume"));
    }
  }
  for (const event of ["pointerdown", "keydown", "wheel"])
    document.addEventListener(event, activate, { passive: true });
  window.addEventListener("focus", activate);
  async function update() {
    if (busy || stopped) return;
    if (!activity.canPoll()) {
      clearTimeout(timer);
      return;
    }
    busy = true;
    const controller = new AbortController(),
      timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(
        "/chat/api/summary/?compact=1&rooms=" +
          (document.querySelector("[data-chat-app]") ? "1" : "0"),
        {
          credentials: "same-origin",
          cache: "no-store",
          signal: controller.signal,
        },
      );
      if ([401, 403].includes(response.status)) {
        stopped = true;
        badge.hidden = true;
        if (dialog.open) dialog.close();
        window.dispatchEvent(new Event("chat-access-denied"));
        clearTimeout(timer);
        return;
      }
      if (!response.ok) throw new Error();
      const data = await response.json();
      failures = 0;
      badge.textContent = data.unread > 99 ? "99+" : String(data.unread);
      badge.hidden = !data.unread;
      window.dispatchEvent(
        new CustomEvent("dhd-chat-summary", { detail: data }),
      );
      const invite = data.incoming.find((call) => !ignored.has(call.id));
      const activeCall = document.getElementById("chat-call-dialog")?.open;
      if (invite && !activeCall && !document.hidden && !dialog.open) {
        dialog.dataset.callId = invite.id;
        document.getElementById("chat-incoming-label").textContent =
          `${invite.initiator_name} đang mời bạn ${invite.mode === "VIDEO" ? "gọi video" : "gọi thoại"}.`;
        document.getElementById("chat-incoming-open").href = invite.url;
        const focused = document.activeElement;
        dialog.show();
        if (focused && typeof focused.focus === "function")
          focused.focus({ preventScroll: true });
      }
      if (
        dialog.open &&
        !data.incoming.some((call) => call.id === dialog.dataset.callId)
      )
        dialog.close();
    } catch {
      failures++;
    } finally {
      clearTimeout(timeout);
      busy = false;
      clearTimeout(timer);
      if (!stopped)
        timer = setTimeout(
          update,
          Math.min(
            45000,
            (document.hidden ? 25000 : 6500) * Math.max(1, failures),
          ),
        );
    }
  }
  document.getElementById("chat-incoming-dismiss").onclick = () => {
    ignored.add(dialog.dataset.callId);
    dialog.close();
  };
  dialog.addEventListener("cancel", () => ignored.add(dialog.dataset.callId));
  document.addEventListener("visibilitychange", () => {
    activity.hiddenSince = document.hidden ? Date.now() : 0;
    if (!document.hidden) {
      activate();
      update();
    }
  });
  update();
})();
