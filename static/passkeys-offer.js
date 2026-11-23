/* Invite this device to turn on Face ID right after a password sign-in. */
(() => {
  "use strict";
  const box = document.getElementById("pk-offer");
  if (!box) return;
  const read = (store, key) => {
    try { return window[store].getItem(key); } catch { return null; }
  };
  const write = (store, key) => {
    try { window[store].setItem(key, "1"); } catch { /* private mode */ }
  };
  if (read("localStorage", "dhd-faceid-enabled") === "1" ||
      read("sessionStorage", "dhd-faceid-later") === "1") return;
  const api = window.PublicKeyCredential;
  if (!window.isSecureContext || !api ||
      typeof api.isUserVerifyingPlatformAuthenticatorAvailable !== "function") return;
  api.isUserVerifyingPlatformAuthenticatorAvailable().then((available) => {
    if (!available) return;
    const ua = navigator.userAgent || "";
    const title = box.querySelector("[data-pk-offer-title]");
    if (title && !/iPhone|iPad|Macintosh/.test(ua)) {
      title.textContent = /Windows/.test(ua) ?
        "Đăng nhập nhanh bằng Windows Hello?" :
        "Đăng nhập nhanh bằng vân tay / khuôn mặt?";
    }
    box.hidden = false;
  }).catch(() => {});
  box.querySelector("[data-pk-offer-dismiss]")?.addEventListener("click", () => {
    box.hidden = true;
    write("sessionStorage", "dhd-faceid-later");
  });
})();
