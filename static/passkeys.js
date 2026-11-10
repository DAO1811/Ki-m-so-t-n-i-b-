/* Passkeys use the browser's WebAuthn API; passwords keep their existing flow. */
(() => {
  "use strict";

  const loginButton = document.getElementById("passkey-login");
  const registerForm = document.getElementById("passkey-register-form");
  const registerButton = document.getElementById("passkey-register");
  const button = loginButton || registerButton;
  if (!button) return;

  const status = document.getElementById("passkey-status");
  const support = document.getElementById("passkey-support");
  const supported = window.isSecureContext === true &&
    typeof window.PublicKeyCredential !== "undefined" &&
    typeof navigator.credentials?.create === "function" &&
    typeof navigator.credentials?.get === "function";
  let busy = false;

  function showStatus(message, failed = false) {
    if (!status) return;
    status.textContent = message;
    status.classList.toggle("pk-status-error", failed);
    status.hidden = !message;
  }

  class PasskeyRequestError extends Error {}

  function csrfToken() {
    const hidden = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (hidden?.value) return hidden.value;
    const cookie = document.cookie.split(";").find((part) => part.trim().startsWith("csrftoken="));
    if (!cookie) return "";
    try { return decodeURIComponent(cookie.trim().slice("csrftoken=".length)); }
    catch { return ""; }
  }

  async function postJSON(url, payload) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 20000);
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
        throw new PasskeyRequestError("Không đọc được phản hồi. Vui lòng tải lại trang rồi thử lại.");
      }
      if (!response.ok) {
        throw new PasskeyRequestError(
          typeof data?.error === "string" ? data.error.slice(0, 400) :
            "Chưa thể hoàn tất yêu cầu. Vui lòng tải lại trang rồi thử lại.",
        );
      }
      if (!data || typeof data !== "object") {
        throw new PasskeyRequestError("Phản hồi chưa hợp lệ. Vui lòng tải lại trang rồi thử lại.");
      }
      return data;
    } finally {
      window.clearTimeout(timer);
    }
  }

  function decode(value) {
    if (typeof value !== "string" || !/^[A-Za-z0-9_-]+$/.test(value) || value.length % 4 === 1) {
      throw new PasskeyRequestError("Thông tin passkey chưa hợp lệ. Vui lòng tải lại trang rồi thử lại.");
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
      throw new PasskeyRequestError("Chưa nhận được passkey từ thiết bị. Vui lòng thử lại.");
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

  function errorMessage(error) {
    if (error instanceof PasskeyRequestError) return error.message;
    if (error?.name === "NotAllowedError") {
      return "Bạn đã hủy hoặc chưa hoàn tất xác minh trên thiết bị. Hãy thử lại khi sẵn sàng.";
    }
    if (error?.name === "InvalidStateError") {
      return "Passkey này có thể đã được đăng ký. Hãy kiểm tra danh sách hoặc chọn passkey khác.";
    }
    if (error?.name === "SecurityError" || error?.name === "NotSupportedError") {
      return "Chưa thể dùng passkey tại đây. Cần HTTPS và trình duyệt, thiết bị có hỗ trợ passkey.";
    }
    if (error?.name === "AbortError") {
      return "Yêu cầu đã hết thời gian chờ. Vui lòng kiểm tra kết nối rồi thử lại.";
    }
    return "Chưa thể hoàn tất xác minh passkey. Vui lòng thử lại; bạn vẫn có thể dùng mật khẩu.";
  }

  async function run(registering) {
    if (busy || !supported || button.disabled) return;
    if (registering && !registerForm.reportValidity()) return;
    busy = true;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    const label = button.querySelector("[data-pk-label]");
    const originalLabel = label?.textContent;
    if (label) label.textContent = "Đang xác minh…";
    showStatus("Đang chuẩn bị xác minh trên thiết bị…");
    const password = registerForm?.querySelector('[name="password"]');
    try {
      const prefix = registering ? "/account/passkeys/register/" : "/passkeys/login/";
      const payload = registering ? {
        password: password.value,
        label: registerForm.querySelector('[name="label"]').value.trim(),
      } : { next: document.querySelector('input[name="next"]')?.value || "" };
      const options = await postJSON(`${prefix}options/`, payload);
      if (password) password.value = "";
      showStatus("Làm theo hướng dẫn của thiết bị để xác minh bằng khuôn mặt, vân tay hoặc PIN.");
      const request = { publicKey: publicKeyOptions(options.publicKey, registering) };
      const credential = registering ? await navigator.credentials.create(request) : await navigator.credentials.get(request);
      const result = await postJSON(`${prefix}verify/`, {
        ceremony_id: options.ceremony_id,
        credential: serialize(credential, registering),
      });
      if (registering) {
        if (result.ok !== true) throw new PasskeyRequestError("Chưa xác nhận được đăng ký passkey. Vui lòng tải lại để kiểm tra.");
        showStatus("Đã thêm passkey. Đang cập nhật danh sách…");
        window.location.reload();
      } else {
        if (typeof result.redirect !== "string" || !result.redirect) throw new PasskeyRequestError("Chưa nhận được trang chuyển tiếp. Vui lòng thử lại.");
        const target = new URL(result.redirect, window.location.origin);
        if (target.origin !== window.location.origin || !["http:", "https:"].includes(target.protocol)) {
          throw new PasskeyRequestError("Địa chỉ chuyển tiếp chưa hợp lệ. Vui lòng tải lại trang.");
        }
        showStatus("Đăng nhập thành công. Đang chuyển trang…");
        window.location.assign(target.href);
      }
    } catch (error) {
      showStatus(errorMessage(error), true);
    } finally {
      if (password) password.value = "";
      busy = false;
      button.disabled = false;
      button.removeAttribute("aria-busy");
      if (label) label.textContent = originalLabel;
    }
  }

  if (registerForm) {
    registerForm.addEventListener("submit", (event) => {
      event.preventDefault();
      run(true);
    }, true);
    registerForm.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.isComposing && event.target.matches("input")) {
        event.preventDefault();
        run(true);
      }
    });
  }
  if (!supported) {
    if (support) {
      support.textContent = window.isSecureContext ?
        "Trình duyệt hoặc thiết bị này chưa hỗ trợ passkey. Bạn vẫn có thể dùng mật khẩu." :
        "Passkey cần kết nối HTTPS và thiết bị có hỗ trợ. Bạn vẫn có thể dùng mật khẩu.";
      support.hidden = false;
    }
    return;
  }
  button.hidden = false;
  button.addEventListener("click", () => run(Boolean(registerForm)));
})();
