/* Password show/hide, and the bank-app style sign-in (owner request 24/11/2026,
   "giống app ACB"): a device that signed in before greets that account and asks
   only for Face ID or the password. The device keeps the account name, never
   the password. */
(() => {
  "use strict";
  const store = {
    get(key) { try { return window.localStorage.getItem(key); } catch { return null; } },
    remove(key) { try { window.localStorage.removeItem(key); } catch { /* private mode */ } },
  };

  for (const toggle of document.querySelectorAll(".auth-password-toggle")) {
    const password = document.getElementById(toggle.getAttribute("aria-controls"));
    if (!password) continue;
    toggle.hidden = false;
    toggle.addEventListener("click", () => {
      const visible = password.type === "password";
      password.type = visible ? "text" : "password";
      toggle.setAttribute("aria-pressed", String(visible));
      toggle.setAttribute("aria-label", visible ? "Ẩn mật khẩu" : "Hiện mật khẩu");
    });
  }

  // Signing in as someone else on this device forgets the greeting and Face ID.
  function forgetAccount() {
    for (const key of ["dhd-last-user", "dhd-faceid-enabled", "dhd-faceid-user", "dhd-faceid-name"]) {
      store.remove(key);
    }
  }
  for (const form of document.querySelectorAll("[data-bank-other-form]")) {
    form.addEventListener("submit", forgetAccount);
  }

  const card = document.querySelector("[data-bank-login]");
  const username = document.getElementById("id_username");
  if (!card || !username) return;
  let account = null;
  try { account = JSON.parse(store.get("dhd-last-user") || "null"); } catch { account = null; }
  if (!account || typeof account.u !== "string" || !account.u || account.u.length > 150) return;
  // After a failed attempt as another account, keep the full form.
  const typed = username.value.trim();
  if (typed && typed.toLowerCase() !== account.u.toLowerCase()) return;
  const name = ((typeof account.n === "string" && account.n.trim()) || account.u).slice(0, 80);
  const words = name.replace(/\([^)]*\)/g, " ").match(/\p{L}+/gu) || [name];
  const hello = card.querySelector("[data-bank-hello]");
  const plain = card.querySelector("[data-bank-default]");
  const other = card.querySelector("[data-bank-other]");
  username.value = account.u;
  card.querySelector("[data-bank-name]").textContent = name;
  card.querySelector("[data-bank-avatar]").textContent = (words[words.length - 1].charAt(0) || "?").toUpperCase();
  hello.hidden = false;
  plain.hidden = true;
  other.hidden = false;
  card.classList.add("bank-remembered");
  card.dataset.bankUser = account.u;
  other.addEventListener("click", () => {
    forgetAccount();
    username.value = "";
    hello.hidden = true;
    plain.hidden = false;
    other.hidden = true;
    card.classList.remove("bank-remembered");
    delete card.dataset.bankUser;
    username.focus();
    document.dispatchEvent(new CustomEvent("dhd-login-other"));
  });
})();
