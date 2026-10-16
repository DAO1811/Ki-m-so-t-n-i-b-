(() => {
  const root = document.getElementById("stocktake-scanner");
  if (!root) return;
  const byId = (id) => document.getElementById(id),
    status = byId("scan-status");
  const token = root.querySelector("[name=csrfmiddlewaretoken]").value;
  let scanner = null,
    running = false,
    busy = false,
    armed = true,
    lastSeen = 0,
    current = null,
    code = "";
  const number = (value) =>
    new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 3 }).format(
      Number(value),
    );
  function say(text, error = false) {
    status.textContent = text;
    status.classList.toggle("negative", error);
  }
  async function jsonResponse(response) {
    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error(
        "Không nhận được phản hồi hợp lệ. Kiểm tra phiên đăng nhập và xác minh lượt đếm trước khi tiếp tục.",
      );
    }
    if (!response.ok)
      throw new Error(data.error || "Không xử lý được. Hãy tải lại phiên.");
    return data;
  }
  function show(data) {
    current = data;
    byId("scanned-product").hidden = false;
    byId("scan-name").textContent =
      data.product.sku + " · " + data.product.name;
    byId("scan-summary").textContent =
      "Tồn sổ: " +
      number(data.book) +
      " " +
      data.product.unit +
      " · Mượn tạm, không tính: " +
      number(data.borrowed);
    byId("scan-quantity").value = data.counted === null ? "" : data.counted;
    byId("scan-price").value = data.unit_price;
    byId("scan-note").value = data.note;
    byId("scan-photo").hidden = !data.product.image;
    if (data.product.image) byId("scan-photo").src = data.product.image;
  }
  async function lookup(text) {
    return jsonResponse(
      await fetch(
        root.dataset.lookup + "?" + new URLSearchParams({ code: text }),
        { headers: { Accept: "application/json" } },
      ),
    );
  }
  function updateRow(data) {
    const rows = byId("stocktake-rows");
    let row = [...rows.querySelectorAll("[data-sku]")].find(
      (r) => r.dataset.sku === current.product.sku,
    );
    if (!row) {
      rows
        .querySelectorAll("tr:not([data-sku])")
        .forEach((node) => node.remove());
      row = document.createElement("tr");
      row.dataset.sku = current.product.sku;
      for (let i = 0; i < 6; i++) row.append(document.createElement("td"));
      row.children[0].textContent =
        current.product.sku + " · " + current.product.name;
      row.children[1].textContent = current.product.unit;
      row.children[2].textContent = number(current.book);
      row.children[3].setAttribute("data-counted", "");
      row.children[4].setAttribute("data-difference", "");
      const select = document.createElement("button");
      select.type = "button";
      select.className = "button secondary small";
      select.textContent = "Ghi số / xác nhận 0";
      select.addEventListener("click", () => {
        byId("scan-mode").value = "SET";
        scan(row.dataset.sku, true);
        root.scrollIntoView({ behavior: "smooth" });
      });
      row.children[5].append(select);
      rows.append(row);
    }
    row.querySelector("[data-counted]").textContent = number(data.quantity);
    row.querySelector("[data-difference]").textContent = number(
      data.difference,
    );
    byId("count-progress").textContent =
      data.counted_count + "/" + data.total_count + " mã đã đếm";
  }
  const pendingKey = "dhd-count:" + root.dataset.count;
  let pending = null;
  try {
    pending = sessionStorage.getItem(pendingKey);
  } catch {}
  const retryButton = document.createElement("button");
  retryButton.type = "button";
  retryButton.className = "button secondary";
  retryButton.textContent = "Xác minh / gửi lại lượt chưa nhận phản hồi";
  retryButton.hidden = !pending;
  status.after(retryButton);
  function clearPending() {
    pending = null;
    retryButton.hidden = true;
    try {
      sessionStorage.removeItem(pendingKey);
    } catch {}
  }
  async function persist(mode, retry = false) {
    if (!retry) {
      pending = new URLSearchParams({
        code,
        mode,
        quantity: byId("scan-quantity").value,
        unit_price: byId("scan-price").value,
        note: byId("scan-note").value,
        revision: String(current.revision),
        request_id: crypto.randomUUID(),
      }).toString();
      try {
        sessionStorage.setItem(pendingKey, pending);
      } catch {}
    }
    retryButton.hidden = false;
    const response = await fetch(root.dataset.count, {
      method: "POST",
      headers: { "X-CSRFToken": token, Accept: "application/json" },
      body: new URLSearchParams(pending),
    });
    if (response.status >= 400 && response.status < 500) clearPending();
    const data = await jsonResponse(response);
    clearPending();
    current.revision = data.revision;
    current.counted = data.quantity;
    byId("scan-quantity").value = data.quantity;
    updateRow(data);
    say(
      (mode === "ADD" ? "Đã cộng 1" : "Đã ghi tổng số") +
        " · " +
        current.product.sku +
        ": " +
        number(data.quantity) +
        " " +
        current.product.unit +
        ". Đưa tem ra khỏi khung trước lượt tiếp theo.",
    );
  }
  retryButton.addEventListener("click", async () => {
    if (!pending || busy) return;
    busy = true;
    try {
      const body = new URLSearchParams(pending);
      code = body.get("code");
      show(await lookup(code));
      await persist(body.get("mode"), true);
    } catch (error) {
      say(error.message + " Chưa xác nhận được lượt đếm; không quét bù.", true);
    } finally {
      busy = false;
    }
  });
  document
    .querySelector('form[action$="/submit/"]')
    ?.addEventListener("submit", (event) => {
      if (pending || busy) {
        event.preventDefault();
        say(
          "Còn lượt đếm chưa xác nhận. Hãy xác minh trước khi chốt biên bản.",
          true,
        );
        root.scrollIntoView();
      }
    });
  async function scan(text, forceSet = false) {
    if (pending) {
      say(
        "Còn lượt đếm chưa nhận phản hồi. Bấm xác minh, không quét bù.",
        true,
      );
      return;
    }
    if (busy) {
      say(
        "Đang lưu lượt trước; lượt mới chưa được ghi. Chờ xác nhận rồi quét lại.",
        true,
      );
      return;
    }
    busy = true;
    try {
      code = text.trim();
      if (!code) throw new Error("Nhập mã hàng hoặc quét QR.");
      show(await lookup(code));
      if (!forceSet && byId("scan-mode").value === "ADD") await persist("ADD");
      else
        say(
          "Đã chọn " + current.product.sku + ". Nhập tổng số và bấm Ghi tổng.",
        );
    } catch (error) {
      say(
        error.message +
          " Nếu mất mạng sau lượt quét, chọn lại mã ở chế độ ghi tổng để đối chiếu; không quét bù ngay.",
        true,
      );
    } finally {
      busy = false;
    }
  }
  function decoded(text) {
    lastSeen = Date.now();
    if (!armed || busy) return;
    armed = false;
    scan(text);
  }
  function absent() {
    if (!armed && Date.now() - lastSeen > 900 && !busy) {
      armed = true;
    }
  }
  byId("start-camera").addEventListener("click", async () => {
    if (running) return;
    try {
      scanner =
        scanner ||
        new Html5Qrcode("qr-reader", {
          formatsToSupport: [Html5QrcodeSupportedFormats.QR_CODE],
          verbose: false,
        });
      armed = true;
      await scanner.start(
        { facingMode: "environment" },
        { fps: 6, qrbox: { width: 220, height: 220 } },
        decoded,
        absent,
      );
      running = true;
      byId("start-camera").hidden = true;
      byId("stop-camera").hidden = false;
      say(
        "Camera sẵn sàng. Mỗi lượt quét cộng 1; giữ yên cùng một tem không cộng thêm.",
      );
    } catch (error) {
      say(
        "Không mở được camera. Kiểm tra quyền camera và HTTPS, hoặc dùng ảnh QR / máy quét USB.",
        true,
      );
    }
  });
  async function stop() {
    if (running) {
      await scanner.stop();
      running = false;
    }
    byId("start-camera").hidden = false;
    byId("stop-camera").hidden = true;
  }
  byId("stop-camera").addEventListener("click", () =>
    stop().catch(() => say("Camera đã dừng.")),
  );
  byId("qr-image").addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    try {
      await stop();
      scanner =
        scanner ||
        new Html5Qrcode("qr-reader", {
          formatsToSupport: [Html5QrcodeSupportedFormats.QR_CODE],
        });
      const text = await scanner.scanFile(file, false);
      await scan(text);
    } catch (error) {
      say(
        "Không đọc được QR trong ảnh. Chọn ảnh rõ nét hoặc nhập mã hàng.",
        true,
      );
    } finally {
      event.target.value = "";
    }
  });
  byId("scan-code-form").addEventListener("submit", (event) => {
    event.preventDefault();
    scan(byId("scan-code").value);
    byId("scan-code").select();
  });
  byId("save-count").addEventListener("click", async () => {
    if (!current || busy || pending) return;
    busy = true;
    try {
      await persist("SET");
    } catch (error) {
      say(error.message, true);
    } finally {
      busy = false;
    }
  });
  document.querySelectorAll(".select-count-item").forEach((button) =>
    button.addEventListener("click", () => {
      byId("scan-mode").value = "SET";
      scan(button.dataset.code, true);
      root.scrollIntoView({ behavior: "smooth", block: "start" });
    }),
  );
  window.addEventListener("pagehide", () => {
    if (running) scanner.stop().catch(() => {});
  });
})();
