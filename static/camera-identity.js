/* Camera capture only. All matching decisions belong to the evaluation server. */
(() => {
  "use strict";
  const root = document.querySelector("[data-camera-mode]");
  if (!root) return;
  const enrolling = root.dataset.cameraMode === "enroll";
  const form = document.getElementById("ci-form");
  const start = document.getElementById("ci-start");
  const capture = document.getElementById("ci-capture");
  const cancel = document.getElementById("ci-cancel");
  const area = document.getElementById("ci-capture-area");
  const video = document.getElementById("ci-video");
  const canvas = document.getElementById("ci-canvas");
  const status = document.getElementById("ci-status");
  const step = document.getElementById("ci-step");
  const counter = document.getElementById("ci-counter");
  const password = document.getElementById("ci-password");
  const directions = { CENTER: "Nhìn thẳng vào camera", LEFT: "Quay đầu nhẹ sang trái", RIGHT: "Quay đầu nhẹ sang phải" };
  let stream = null;
  let challenge = null;
  let frames = [];
  let busy = false;
  let generation = 0;
  let expiry = null;

  function message(text, error = false) {
    status.textContent = text;
    status.hidden = !text;
    status.classList.toggle("ci-status-error", error);
  }
  function stopCamera() {
    stream?.getTracks().forEach((track) => track.stop());
    stream = null;
    video.srcObject = null;
  }
  function reset() {
    generation += 1;
    stopCamera();
    if (expiry !== null) window.clearTimeout(expiry);
    expiry = null;
    frames = [];
    challenge = null;
    busy = false;
    start.disabled = false;
    capture.disabled = false;
    area.hidden = true;
    if (password) password.value = "";
    canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
  }
  async function post(url, payload) {
    const body = JSON.stringify(payload);
    if (new TextEncoder().encode(body).byteLength > 2 * 1024 * 1024) throw new Error("Ảnh vượt giới hạn. Hãy thử lại trong điều kiện đủ sáng.");
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch(url, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", "Accept": "application/json", "X-CSRFToken": form.querySelector('[name="csrfmiddlewaretoken"]').value }, body, signal: controller.signal });
      let result;
      try { result = await response.json(); } catch { throw new Error("Không đọc được phản hồi. Hãy tải lại trang."); }
      if (!response.ok) throw new Error(typeof result.error === "string" ? result.error.slice(0, 400) : "Chưa hoàn tất yêu cầu. Hãy thử lại.");
      return result;
    } finally { window.clearTimeout(timer); }
  }
  function guidance() {
    step.textContent = directions[challenge.steps[frames.length]];
    counter.textContent = `Bước ${frames.length + 1}/3 · Đã chụp ${frames.length}/3 ảnh. Chờ hình rõ rồi nhấn chụp.`;
  }
  function failure(error) {
    if (error?.name === "NotAllowedError") return "Chưa được phép mở camera. Kiểm tra quyền camera của website trong trình duyệt rồi thử lại.";
    if (error?.name === "NotFoundError") return "Không tìm thấy camera. Hãy kiểm tra camera hoặc dùng thiết bị khác.";
    if (error?.name === "AbortError") return "Yêu cầu hết thời gian chờ. Kiểm tra kết nối rồi thử lại.";
    return error?.message || "Chưa thể hoàn tất đánh giá camera. Hãy thử lại.";
  }
  async function begin() {
    if (busy || challenge || !form.reportValidity()) return;
    if (!window.isSecureContext || typeof navigator.mediaDevices?.getUserMedia !== "function") {
      message("Camera cần HTTPS và trình duyệt hỗ trợ. Bạn vẫn có thể đăng nhập bằng mật khẩu.", true);
      return;
    }
    busy = true; start.disabled = true;
    area.hidden = false; capture.disabled = true;
    step.textContent = "Cấp quyền camera để tiếp tục";
    counter.textContent = "Chưa chụp ảnh";
    const run = ++generation;
    const beganAt = window.performance.now();
    message("Đang xin quyền camera và chuẩn bị yêu cầu đánh giá…");
    const payload = enrolling ? { password: password.value, consent: document.getElementById("ci-consent").checked } : { username: document.getElementById("ci-username").value.trim() };
    try {
      // Invoke camera permission directly from the explicit user action.
      const cameraPromise = navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } }, audio: false }).then((camera) => {
        if (run !== generation) { camera.getTracks().forEach((track) => track.stop()); return null; }
        stream = camera; return camera;
      });
      // Attach a rejection handler immediately while the server request is pending.
      cameraPromise.catch(() => {});
      const prefix = enrolling ? "/account/camera/enroll/" : "/camera/verify/";
      const options = await post(`${prefix}options/`, payload);
      if (password) password.value = "";
      if (run !== generation) return;
      if (!options.challenge_id || !Array.isArray(options.steps) || options.steps.length !== 3 || new Set(options.steps).size !== 3 || options.steps.some((value) => !directions[value])) throw new Error("Hướng dẫn chụp chưa hợp lệ. Hãy thử lại.");
      const camera = await cameraPromise;
      if (run !== generation || !camera) return;
      const remaining = Math.min(Number(options.expires_in) || 120, 120) * 1000 - (window.performance.now() - beganAt);
      if (remaining <= 0) throw new Error("Yêu cầu đã hết hạn. Hãy bắt đầu lại.");
      video.srcObject = camera;
      video.muted = true;
      await video.play();
      if (run !== generation) return;
      challenge = { id: options.challenge_id, steps: options.steps };
      frames = []; area.hidden = false; busy = false; capture.disabled = false;
      expiry = window.setTimeout(() => { reset(); message("Yêu cầu đã hết hạn; camera đã tắt. Hãy bắt đầu lại.", true); }, remaining);
      guidance(); message("Camera đang hoạt động. Thực hiện từng bước rồi nhấn Chụp bước này.");
    } catch (error) {
      if (run === generation) { reset(); message(failure(error), true); }
    }
  }
  async function take() {
    if (busy || !challenge) return;
    if (!video.videoWidth || video.readyState < 2) { message("Camera chưa có hình rõ. Chờ một chút rồi chụp lại.", true); return; }
    busy = true; capture.disabled = true;
    const run = generation;
    try {
      const width = video.videoWidth, height = video.videoHeight;
      const cropWidth = Math.min(width, height * 4 / 3), cropHeight = cropWidth * 3 / 4;
      canvas.getContext("2d").drawImage(video, (width - cropWidth) / 2, (height - cropHeight) / 2, cropWidth, cropHeight, 0, 0, 640, 480);
      frames.push(canvas.toDataURL("image/jpeg", 0.82).split(",")[1]);
      if (frames.length < 3) { guidance(); busy = false; capture.disabled = false; return; }
      stopCamera(); area.hidden = true;
      if (expiry !== null) window.clearTimeout(expiry);
      expiry = null;
      message("Đã tắt camera. Máy chủ đang xử lý 3 ảnh đánh giá…");
      const prefix = enrolling ? "/account/camera/enroll/" : "/camera/verify/";
      const result = await post(enrolling ? `${prefix}verify/` : `${prefix}finish/`, { challenge_id: challenge.id, frames });
      if (run !== generation) return;
      if (result.mode !== "evaluation" || result.login_permitted !== false) throw new Error("Phản hồi đánh giá không hợp lệ. Không thực hiện đăng nhập.");
      if (enrolling) {
        if (result.ok !== true) throw new Error("Chưa xác nhận được đăng ký mẫu. Hãy tải lại trang để kiểm tra.");
        reset();
        message("Đã đăng ký mẫu đánh giá. Kết quả so khớp chưa cho phép đăng nhập. Tải lại trang để xem trạng thái mẫu.");
      } else {
        if (typeof result.matched !== "boolean") throw new Error("Chưa nhận được kết quả so khớp hợp lệ.");
        reset();
        message(result.matched ? "Kết quả máy chủ: khớp với mẫu trong bản đánh giá. Kết quả này KHÔNG cho phép đăng nhập; chưa kiểm chứng chống ảnh/video giả." : "Kết quả máy chủ: không khớp với mẫu trong bản đánh giá. Không tạo phiên đăng nhập.", !result.matched);
      }
    } catch (error) {
      if (run === generation) { reset(); message(failure(error), true); }
    }
  }
  form.addEventListener("submit", (event) => { event.preventDefault(); begin(); }, true);
  form.addEventListener("input", () => { if (challenge || busy) { reset(); message("Thông tin thay đổi; camera đã tắt. Hãy bắt đầu lại."); } });
  start.addEventListener("click", begin);
  capture.addEventListener("click", take);
  cancel.addEventListener("click", () => { reset(); message("Đã hủy đánh giá và tắt camera."); });
  window.addEventListener("pagehide", reset);
})();
