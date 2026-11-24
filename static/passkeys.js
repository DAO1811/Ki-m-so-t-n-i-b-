/* Face ID / fingerprint sign-in, turn-on and the bank-style "sign in again"
   screen through the browser's WebAuthn (passkey) API. If Face ID fails, the
   password still works; a forgotten password is reset by an Admin. The device
   only remembers that Face ID is on for an account name, never a password. */
(() => {
  "use strict";
  if (window.__dhdFaceId) return;
  window.__dhdFaceId = true;

  const supported = window.isSecureContext === true &&
    typeof window.PublicKeyCredential !== "undefined" &&
    typeof navigator.credentials?.create === "function" &&
    typeof navigator.credentials?.get === "function";
  const FALLBACK = "Hãy dùng mật khẩu. Quên mật khẩu, liên hệ quản trị viên.";
  const ua = navigator.userAgent || "";
  const iPad = /iPad/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
  const platform = /iPhone|iPod/.test(ua) ? "iphone" : iPad ? "ipad" : /Macintosh/.test(ua) ? "mac" :
    /Android/.test(ua) ? "android" : /Windows/.test(ua) ? "windows" : "other";
  const method = {
    iphone: "Face ID", ipad: "Face ID / Touch ID", mac: "Touch ID",
    android: "vân tay / khuôn mặt", windows: "Windows Hello", other: "Face ID",
  }[platform];
  const deviceName = {
    iphone: "iPhone", ipad: "iPad", mac: "Máy Mac", android: "Điện thoại Android",
    windows: "Máy tính Windows", other: "Thiết bị của tôi",
  }[platform];
  const inApp = /FBAN|FBAV|FB_IAB|Instagram|Zalo|Line\//i.test(ua);
  const PREFIX = {
    register: "/account/passkeys/register/",
    login: "/passkeys/login/",
    unlock: "/unlock/",
  };
  let busy = false;
  let conditional = null;

  class PasskeyRequestError extends Error {}

  const storage = {
    get(key) { try { return window.localStorage.getItem(key); } catch { return null; } },
    set(key, value) { try { window.localStorage.setItem(key, value); } catch { /* private mode */ } },
    remove(key) { try { window.localStorage.removeItem(key); } catch { /* private mode */ } },
  };

  function remember(username, name) {
    storage.set("dhd-faceid-enabled", "1");
    if (typeof username === "string" && username) {
      storage.set("dhd-faceid-user", username.slice(0, 150));
      storage.set("dhd-last-user", JSON.stringify({
        u: username.slice(0, 150),
        n: (typeof name === "string" && name ? name : username).slice(0, 80),
      }));
    }
    if (typeof name === "string" && name) storage.set("dhd-faceid-name", name.slice(0, 80));
  }

  function forget() {
    storage.remove("dhd-faceid-enabled");
    storage.remove("dhd-faceid-user");
    storage.remove("dhd-faceid-name");
  }

  /* Face ID was turned on (or used) on this device for this account. */
  function faceIdOn(username) {
    if (storage.get("dhd-faceid-enabled") !== "1") return false;
    const owner = (storage.get("dhd-faceid-user") || "").toLowerCase();
    return !owner || !username || owner === String(username).toLowerCase();
  }

  async function platformReady() {
    try { return await window.PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable(); }
    catch { return false; }
  }

  function unlockedElsewhereSignal() {
    // Other open tabs of the app drop their lock screen too (app-lock.js).
    storage.set("dhd-app-unlocked", String(Date.now()));
  }

  function finishRegister(scope, show, message) {
    show(message);
    if (scope.hasAttribute("data-pk-offer")) {
      for (const button of scope.querySelectorAll("button")) button.hidden = true;
      window.setTimeout(() => { scope.hidden = true; }, 4000);
    } else {
      window.setTimeout(() => window.location.reload(), 1500);
    }
  }

  function statusIn(scope) {
    const status = scope.querySelector("[data-pk-status]");
    return (message, failed = false) => {
      if (!status) return;
      status.textContent = message;
      status.classList.toggle("pk-status-error", failed);
      status.hidden = !message;
    };
  }

  function csrfToken() {
    const hidden = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (hidden?.value) return hidden.value;
    const cookie = document.cookie.split(";").find((part) => part.trim().startsWith("csrftoken="));
    if (!cookie) return "";
    try { return decodeURIComponent(cookie.trim().slice("csrftoken=".length)); }
    catch { return ""; }
  }

  async function postJSON(url, payload, signal) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 20000);
    signal?.addEventListener("abort", () => controller.abort(), { once: true });
    try {
      const response = await fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Accept": "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken(),
        },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      let data;
      try { data = await response.json(); }
      catch {
        throw new PasskeyRequestError("Không đọc được phản hồi. Tải lại trang rồi thử lại. " + FALLBACK);
      }
      if (!response.ok) {
        throw new PasskeyRequestError(
          typeof data?.error === "string" ? data.error.slice(0, 400) :
            "Chưa thể hoàn tất. Tải lại trang rồi thử lại. " + FALLBACK,
        );
      }
      if (!data || typeof data !== "object") {
        throw new PasskeyRequestError("Phản hồi chưa hợp lệ. Tải lại trang rồi thử lại.");
      }
      return data;
    } finally {
      window.clearTimeout(timer);
    }
  }

  function decode(value) {
    if (typeof value !== "string" || !/^[A-Za-z0-9_-]+$/.test(value) || value.length % 4 === 1) {
      throw new PasskeyRequestError("Thông tin xác minh chưa hợp lệ. Tải lại trang rồi thử lại.");
    }
    const base64 = value.replace(/-/g, "+").replace(/_/g, "/");
    const binary = window.atob(base64 + "=".repeat((4 - base64.length % 4) % 4));
    return Uint8Array.from(binary, (character) => character.charCodeAt(0)).buffer;
  }

  function encode(value) {
    const bytes = new Uint8Array(value);
    let binary = "";
    bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
    return window.btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }

  function publicKeyOptions(options, registering) {
    if (!options || typeof options !== "object") {
      throw new PasskeyRequestError("Không nhận được yêu cầu xác minh. Vui lòng thử lại.");
    }
    const publicKey = { ...options, challenge: decode(options.challenge) };
    const decodeCredential = (credential) => ({ ...credential, id: decode(credential.id) });
    if (registering) {
      publicKey.user = { ...options.user, id: decode(options.user?.id) };
      publicKey.excludeCredentials = (options.excludeCredentials || []).map(decodeCredential);
      publicKey.authenticatorSelection = { ...options.authenticatorSelection, userVerification: "required" };
    } else {
      if (options.allowCredentials) publicKey.allowCredentials = options.allowCredentials.map(decodeCredential);
      publicKey.userVerification = "required";
    }
    return publicKey;
  }

  function serialize(credential, registering) {
    if (!credential || credential.type !== "public-key") {
      throw new PasskeyRequestError(`Chưa nhận được xác minh ${method} từ thiết bị. Vui lòng thử lại.`);
    }
    const response = { clientDataJSON: encode(credential.response.clientDataJSON) };
    if (registering) {
      response.attestationObject = encode(credential.response.attestationObject);
      if (typeof credential.response.getTransports === "function") {
        response.transports = credential.response.getTransports();
      }
    } else {
      response.authenticatorData = encode(credential.response.authenticatorData);
      response.signature = encode(credential.response.signature);
      response.userHandle = credential.response.userHandle == null ? null : encode(credential.response.userHandle);
    }
    return {
      id: credential.id,
      rawId: encode(credential.rawId),
      type: credential.type,
      authenticatorAttachment: credential.authenticatorAttachment || null,
      response,
    };
  }

  function errorMessage(error, kind) {
    if (error instanceof PasskeyRequestError) return error.message;
    if (error?.name === "NotAllowedError") {
      if (kind === "register") return `Chưa bật được ${method}: bạn đã hủy hoặc xác minh chưa xong. Bấm lại nút để thử lần nữa.`;
      if (kind === "unlock") return `Chưa đăng nhập được bằng ${method}. Chạm lại biểu tượng ${method}, hoặc nhập mật khẩu.`;
      return `Chưa đăng nhập được bằng ${method}: bạn đã hủy, hoặc thiết bị này chưa bật ${method} cho phần mềm. ` + FALLBACK;
    }
    if (error?.name === "InvalidStateError") {
      return `Thiết bị này đã bật ${method} cho tài khoản rồi. Lần sau bấm "Đăng nhập bằng ${method}" ở trang đăng nhập.`;
    }
    if (error?.name === "SecurityError" || error?.name === "NotSupportedError") {
      return `Trình duyệt này chưa dùng được ${method}. Trên iPhone hãy mở bằng Safari (không mở từ Zalo/Messenger). ` + FALLBACK;
    }
    if (error?.name === "AbortError") return "Hết thời gian chờ. Kiểm tra kết nối rồi thử lại. " + FALLBACK;
    return `Chưa xác minh được bằng ${method}. ` + FALLBACK;
  }

  function go(result) {
    if (typeof result.redirect !== "string" || !result.redirect) {
      throw new PasskeyRequestError("Chưa nhận được trang chuyển tiếp. Vui lòng thử lại.");
    }
    const target = new URL(result.redirect, window.location.origin);
    if (target.origin !== window.location.origin || !["http:", "https:"].includes(target.protocol)) {
      throw new PasskeyRequestError("Địa chỉ chuyển tiếp chưa hợp lệ. Vui lòng tải lại trang.");
    }
    window.location.assign(target.href);
  }

  function nextValue(scope) {
    return scope.querySelector('input[name="next"]')?.value ||
      document.querySelector('input[name="next"]')?.value || "";
  }

  function stopConditional() {
    if (conditional) {
      conditional.abort();
      conditional = null;
    }
  }

  async function ceremony(kind, payload, signal) {
    const options = await postJSON(`${PREFIX[kind]}options/`, payload, signal);
    const request = { publicKey: publicKeyOptions(options.publicKey, kind === "register") };
    const credential = kind === "register" ?
      await navigator.credentials.create(request) : await navigator.credentials.get(request);
    return postJSON(`${PREFIX[kind]}verify/`, {
      ceremony_id: options.ceremony_id,
      credential: serialize(credential, kind === "register"),
      next: payload.next || "",
    });
  }

  /* One Face ID request at a time; `auto` attempts (no tap yet) stay quiet if
     the browser wants a tap first. */
  async function run(kind, trigger, scope, { auto = false, inline = false } = {}) {
    const show = statusIn(scope);
    if (busy || !supported || trigger.disabled) return false;
    if (kind === "register") {
      const form = scope.closest("form") || scope;
      if (typeof form.reportValidity === "function" && !form.reportValidity()) {
        form.querySelector("details.pk-rename")?.setAttribute("open", "");
        return false;
      }
    }
    stopConditional();
    busy = true;
    trigger.disabled = true;
    trigger.setAttribute("aria-busy", "true");
    const label = trigger.querySelector("[data-pk-label]");
    const originalLabel = label?.textContent;
    if (label) label.textContent = "Đang xác minh…";
    show(`Nhìn vào màn hình để ${method} xác nhận (hoặc chạm vân tay / nhập mã PIN của thiết bị).`);
    const password = kind === "register" ? scope.querySelector('[name="password"]') : null;
    const started = window.performance.now();
    let succeeded = false;
    try {
      const payload = kind === "register" ? {
        password: password?.value || "",
        label: scope.querySelector('[name="label"]').value.trim(),
      } : { next: nextValue(scope) };
      if (password && password.type !== "hidden") password.value = "";
      const result = await ceremony(kind, payload);
      succeeded = true;
      if (kind === "register") {
        if (result.ok !== true) throw new PasskeyRequestError(`Chưa xác nhận được việc bật ${method}. Tải lại trang để kiểm tra.`);
        remember(scope.dataset.pkUsername || "", scope.dataset.pkAccount || "");
        finishRegister(scope, show, `Đã bật ${method} cho thiết bị này. Lần sau mở phần mềm, chỉ cần nhìn vào màn hình để đăng nhập.`);
      } else if (kind === "unlock") {
        // Binds an older device flag to this account.
        if (scope.dataset.account) storage.set("dhd-faceid-user", scope.dataset.account.slice(0, 150));
        unlockedElsewhereSignal();
        if (inline) {
          show("");
          document.dispatchEvent(new CustomEvent("dhd-faceid-unlocked"));
        } else {
          show("Đăng nhập thành công. Đang quay lại…");
          go(result);
        }
      } else {
        remember(result.username, result.name);
        show("Đăng nhập thành công. Đang chuyển trang…");
        go(result);
      }
    } catch (error) {
      const quick = window.performance.now() - started < 1500;
      if (kind === "register" && error?.name === "InvalidStateError") {
        // This device already has Face ID for the account: treat it as on.
        remember(scope.dataset.pkUsername || "", scope.dataset.pkAccount || "");
        finishRegister(scope, show, `${method} đã được bật sẵn trên thiết bị này. Lần sau chỉ cần nhìn vào màn hình để đăng nhập.`);
      } else if (auto && quick && error?.name === "NotAllowedError") {
        show(`Chạm biểu tượng ${method} bên cạnh nút Đăng nhập để ${kind === "unlock" ? "đăng nhập lại" : "đăng nhập"}.`);
      } else {
        show(errorMessage(error, kind), true);
        scope.querySelector("[data-pk-offer-more]")?.removeAttribute("hidden");
      }
    } finally {
      if (password && password.type !== "hidden") password.value = "";
      busy = false;
      trigger.disabled = false;
      trigger.removeAttribute("aria-busy");
      if (label) label.textContent = originalLabel;
    }
    return succeeded;
  }

  function unsupportedNote(scope) {
    const support = scope.querySelector("[data-pk-support]");
    if (!support) return;
    support.textContent = inApp ?
      `Trình duyệt trong Zalo/Messenger/Facebook chưa dùng được ${method}. Mở phần mềm bằng Safari hoặc Chrome. ` + FALLBACK :
      window.isSecureContext ?
        `Trình duyệt hoặc thiết bị này chưa hỗ trợ ${method}. ` + FALLBACK :
        `${method} cần kết nối HTTPS. ` + FALLBACK;
    support.hidden = false;
  }

  /* iPhone/Android: tapping the username field shows the saved Face ID sign-in
     above the keyboard. A prepared request lives 2 minutes, so refresh it. */
  async function startConditional(scope, round = 0) {
    if (round > 15 || busy) return;
    let available = false;
    try { available = await window.PublicKeyCredential.isConditionalMediationAvailable?.(); }
    catch { available = false; }
    if (!available) return;
    const controller = new AbortController();
    conditional = controller;
    const refresh = window.setTimeout(() => {
      if (conditional === controller) {
        controller.abort();
        conditional = null;
        startConditional(scope, round + 1);
      }
    }, 100000);
    const show = statusIn(scope);
    try {
      const options = await postJSON("/passkeys/login/options/", { next: nextValue(scope) }, controller.signal);
      if (controller.signal.aborted) return;
      const credential = await navigator.credentials.get({
        publicKey: publicKeyOptions(options.publicKey, false),
        mediation: "conditional",
        signal: controller.signal,
      });
      window.clearTimeout(refresh);
      if (conditional !== controller || busy) return;
      conditional = null;
      busy = true;
      show(`Đang đăng nhập bằng ${method}…`);
      const result = await postJSON("/passkeys/login/verify/", {
        ceremony_id: options.ceremony_id,
        credential: serialize(credential, false),
      });
      remember(result.username, result.name);
      go(result);
    } catch (error) {
      window.clearTimeout(refresh);
      if (controller.signal.aborted || error?.name === "AbortError") return;
      if (conditional === controller) conditional = null;
      // A failure before anyone picked a sign-in stays silent; the button still works.
      if (busy) {
        show(errorMessage(error, "login"), true);
        busy = false;
      }
    }
  }

  /* ---- Login page (bank-app style) -------------------------------------- */
  const loginSection = document.querySelector("[data-pk-login]");
  const loginButton = document.querySelector("[data-pk-login-button]");
  if (loginSection && loginButton) {
    const card = loginButton.closest("[data-bank-login]");
    const label = `Đăng nhập bằng ${method}`;
    loginButton.setAttribute("aria-label", label);
    loginButton.title = label;
    loginButton.querySelector("[data-pk-label]").textContent = label;
    if (!supported) {
      unsupportedNote(loginSection);
    } else {
      // After a failed password attempt keep the password in front.
      const hadError = Boolean(document.querySelector(".auth-error, .auth-page .errorlist"));
      const account = () => card?.dataset.bankUser || "";
      loginButton.addEventListener("click", () => run("login", loginButton, loginSection));
      document.addEventListener("dhd-login-other", () => startConditional(loginSection));
      platformReady().then((ready) => {
        const enabled = Boolean(account()) && faceIdOn(account());
        if (ready || enabled) loginButton.hidden = false;
        if (enabled && !hadError) {
          /* Like a banking app: this device turned on Face ID, so ask for it now. */
          run("login", loginButton, loginSection, { auto: true });
        } else if (!account()) {
          startConditional(loginSection);
        }
      });
    }
  }

  /* ---- Turn on Face ID (account page) ------------------------------------ */
  const registerForm = document.getElementById("passkey-register-form");
  if (registerForm) {
    const registerButton = registerForm.querySelector("[data-pk-register-button]");
    const labelInput = registerForm.querySelector('[name="label"]');
    const shown = registerForm.querySelector("[data-pk-device-name]");
    if (labelInput && !labelInput.value) labelInput.value = deviceName;
    if (shown && labelInput) {
      shown.textContent = labelInput.value;
      labelInput.addEventListener("input", () => { shown.textContent = labelInput.value.trim() || deviceName; });
    }
    registerButton.querySelector("[data-pk-label]").textContent = `Bật ${method} cho thiết bị này`;
    registerForm.addEventListener("submit", (event) => {
      event.preventDefault();
      run("register", registerButton, registerForm);
    }, true);
    registerForm.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.isComposing && event.target.matches("input")) {
        event.preventDefault();
        run("register", registerButton, registerForm);
      }
    });
    if (!supported) {
      unsupportedNote(registerForm);
    } else {
      registerButton.hidden = false;
      registerButton.addEventListener("click", () => run("register", registerButton, registerForm));
      if (new URLSearchParams(window.location.search).has("bat")) {
        registerButton.scrollIntoView({ block: "center" });
        registerButton.focus({ preventScroll: true });
      }
    }
  }

  /* ---- One-tap "Bật Face ID" right after a password sign-in --------------- */
  const offer = document.querySelector("[data-pk-offer]");
  const offerButton = offer?.querySelector("[data-pk-offer-enable]");
  if (offer && offerButton) {
    const labelInput = offer.querySelector('[name="label"]');
    if (labelInput && !labelInput.value) labelInput.value = deviceName;
    offerButton.querySelector("[data-pk-label]").textContent = `Bật ${method}`;
    if (supported) offerButton.addEventListener("click", () => run("register", offerButton, offer));
  }

  /* ---- Sign in again (the /unlock/ page and the in-page lock screen) ------ */
  for (const scope of document.querySelectorAll("[data-pk-unlock]")) {
    const inline = scope.dataset.pkUnlock === "inline";
    const unlockButton = scope.querySelector("[data-pk-unlock-button]");
    const account = scope.dataset.account || "";
    const accountHasFaceId = scope.dataset.pkFaceid === "1";
    const label = `Đăng nhập bằng ${method}`;
    unlockButton.setAttribute("aria-label", label);
    unlockButton.title = label;
    unlockButton.querySelector("[data-pk-label]").textContent = label;
    if (!accountHasFaceId && account &&
        (storage.get("dhd-faceid-user") || "").toLowerCase() === account.toLowerCase()) {
      forget();  // Face ID was turned off for this account on the server.
    }
    const start = (auto) => run("unlock", unlockButton, scope, { auto, inline });
    if (accountHasFaceId && supported && faceIdOn(account)) {
      unlockButton.hidden = false;
      unlockButton.addEventListener("click", () => start(false));
      if (!inline) start(true);
      // Ask for Face ID only in the tab the person is looking at.
      else document.addEventListener("dhd-app-locked", () => { if (!document.hidden) start(true); });
    } else if (accountHasFaceId && !supported) {
      unsupportedNote(scope);
    }
    const passwordForm = scope.querySelector("[data-pk-unlock-password]");
    // Capture phase: runs before the page-wide "disable buttons on submit"
    // handler (workspace.js), which then sees the submit was handled here.
    passwordForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const show = statusIn(scope);
      const input = passwordForm.querySelector('[name="password"]');
      const submit = passwordForm.querySelector('button[type="submit"]');
      submit.disabled = true;
      try {
        const result = await postJSON("/unlock/password/", {
          password: input.value,
          next: nextValue(scope),
        });
        input.value = "";
        if (input.type !== "password") input.type = "password";
        unlockedElsewhereSignal();
        if (inline) {
          show("");
          document.dispatchEvent(new CustomEvent("dhd-faceid-unlocked"));
        } else {
          show("Đăng nhập thành công. Đang quay lại…");
          go(result);
        }
      } catch (error) {
        input.value = "";
        show(errorMessage(error, "unlock"), true);
      } finally {
        submit.disabled = false;
      }
    }, true);
  }
})();
