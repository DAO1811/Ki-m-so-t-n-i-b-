(() => {
  const form = document.getElementById("document-form");
  if (!form) return;
  const kind = document.getElementById("id_kind"),
    source = document.getElementById("id_source"),
    destination = document.getElementById("id_destination"),
    loan = document.getElementById("id_loan");
  const lines = document.getElementById("lines"),
    count = document.getElementById("id_form-TOTAL_FORMS");
  let stock = {},
    fetchVersion = 0;
  const fold = (text) =>
    text
      .normalize("NFD")
      .replace(/\p{Diacritic}/gu, "")
      .replace(/[đĐ]/g, "d")
      .toLowerCase();
  const priceKinds = ["IN", "COUNT", "ADJUST"];
  const currency = (n) =>
    new Intl.NumberFormat("vi-VN", {
      style: "currency",
      currency: "VND",
      maximumFractionDigits: 0,
    }).format(n);
  const number = (n) =>
    new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 3 }).format(n);
  const currentKind = () => kind.value || form.dataset.kind;
  const help = {
    IN: "Chọn kho nhận và nhập đơn giá. Quản lý kho sẽ kiểm tra trước khi tăng tồn.",
    OUT: "Chỉ số tồn khả dụng mới được xuất. Giá vốn được tính tự động khi duyệt.",
    TRANSFER:
      "Chuyển đi được duyệt trước; kho nhận xác nhận sau khi kiểm tra đủ hàng.",
    LOAN: "Hàng mượn được khóa trong sổ trung gian, không được xuất hoặc cho mượn tiếp.",
    RETURN:
      "Trả theo lệnh mượn gốc, chỉ lấy từ tồn mượn tạm và giữ nguyên giá trị đã mượn.",
    COUNT:
      "Nhập số thực đếm của tồn thường. Không cộng số hàng mượn vào phiếu kiểm kê này.",
    ADJUST: "Số dương là tăng, số âm là giảm. Bắt buộc ghi lý do.",
  };
  function toggle(name, visible) {
    const wrapper = document.querySelector(`[data-doc-field="${name}"]`);
    if (!wrapper) return;
    wrapper.hidden = !visible;
    wrapper.querySelectorAll("input,select,textarea").forEach((input) => {
      input.disabled =
        !visible ||
        (currentKind() === "RETURN" &&
          ["source", "destination"].includes(name));
      if (!visible) input.value = "";
    });
  }
  function totals() {
    let total = 0;
    lines.querySelectorAll("[data-line]").forEach((row) => {
      if (row.hidden) return;
      const q = Number(row.querySelector('[name$="-quantity"]').value) || 0;
      const price =
        Number(row.querySelector('[name$="-unit_price"]').value) || 0;
      row.querySelector("[data-line-amount]").textContent = currency(q * price);
      total += q * price;
    });
    document.getElementById("total-value").textContent = currency(total);
  }
  function availability() {
    lines.querySelectorAll("[data-line]").forEach((row) => {
      const p = row.querySelector('[name$="-product"]').value,
        q = Number(row.querySelector('[name$="-quantity"]').value) || 0,
        node = row.querySelector("[data-available]");
      if (
        !source.value ||
        !p ||
        !["OUT", "TRANSFER", "LOAN", "RETURN"].includes(currentKind())
      ) {
        node.textContent = "";
        return;
      }
      const available = Number(stock[p] || 0);
      node.textContent =
        (currentKind() === "RETURN" ? "Còn mượn: " : "Có thể xuất: ") +
        number(available);
      node.classList.toggle("insufficient", q > available);
    });
  }
  async function loadStock() {
    const version = ++fetchVersion;
    stock = {};
    if (!source.value) {
      availability();
      return;
    }
    const params = new URLSearchParams({ warehouse: source.value });
    if (currentKind() === "RETURN" && loan.value)
      params.set("loan", loan.value);
    try {
      const response = await fetch("/api/availability/?" + params, {
        headers: { Accept: "application/json" },
      });
      if (response.ok) {
        const data = await response.json();
        if (version === fetchVersion) stock = data.quantities;
      }
    } catch {}
    if (version === fetchVersion) availability();
  }
  function picker(select) {
    if (select.dataset.enhanced) return;
    select.dataset.enhanced = "true";
    const options = [...select.options]
      .filter((o) => o.value)
      .map((o) => ({ value: o.value, label: o.textContent }));
    const wrap = document.createElement("div");
    wrap.className = "product-combobox";
    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = "Tìm mã hoặc tên hàng…";
    input.autocomplete = "off";
    input.setAttribute("aria-label", "Tìm và chọn hàng hóa");
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-expanded", "false");
    input.required = select.required;
    input.value = select.value ? select.selectedOptions[0].textContent : "";
    select.required = false;
    select.hidden = true;
    select.before(wrap);
    wrap.append(select, input);
    const menu = document.createElement("div");
    menu.className = "product-options";
    menu.hidden = true;
    menu.setAttribute("role", "listbox");
    wrap.append(menu);
    let focused = -1;
    const close = () => {
      menu.hidden = true;
      input.setAttribute("aria-expanded", "false");
    };
    const choose = (option) => {
      select.value = option.value;
      input.value = option.label;
      input.setCustomValidity("");
      close();
      select.dispatchEvent(new Event("change", { bubbles: true }));
    };
    function show() {
      const query = fold(input.value).trim();
      const found = options
        .filter((o) => !query || fold(o.label).includes(query))
        .slice(0, 20);
      menu.replaceChildren();
      focused = -1;
      if (!found.length) {
        const msg = document.createElement("p");
        msg.textContent =
          "Không tìm thấy mã hàng. Bạn có thể thêm mã hàng ở nút phía trên.";
        menu.append(msg);
      }
      found.forEach((option) => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = option.label;
        button.setAttribute("role", "option");
        button.addEventListener("mousedown", (e) => e.preventDefault());
        button.addEventListener("click", () => choose(option));
        menu.append(button);
      });
      menu.hidden = false;
      input.setAttribute("aria-expanded", "true");
    }
    input.addEventListener("input", () => {
      select.value = "";
      input.setCustomValidity(
        input.value ? "Hãy chọn một hàng hóa trong danh sách." : "",
      );
      show();
      availability();
    });
    input.addEventListener("focus", () => {
      if (select.value) {
        input.select();
        const old = input.value;
        input.value = "";
        show();
        input.value = old;
      } else show();
    });
    input.addEventListener("blur", () => setTimeout(close, 120));
    input.addEventListener("keydown", (e) => {
      const buttons = [...menu.querySelectorAll("button")];
      if (e.key === "Escape") {
        close();
        return;
      }
      if (["ArrowDown", "ArrowUp"].includes(e.key)) {
        e.preventDefault();
        if (menu.hidden) show();
        focused = Math.max(
          0,
          Math.min(
            buttons.length - 1,
            focused + (e.key === "ArrowDown" ? 1 : -1),
          ),
        );
        buttons.forEach((b, i) => b.classList.toggle("focused", i === focused));
        buttons[focused]?.scrollIntoView({ block: "nearest" });
      }
      if (e.key === "Enter" && !menu.hidden && buttons.length) {
        e.preventDefault();
        buttons[Math.max(0, focused)].click();
      }
    });
  }
  function update() {
    const k = currentKind(),
      hasPrice = priceKinds.includes(k);
    toggle("source", ["OUT", "TRANSFER", "LOAN", "RETURN"].includes(k));
    toggle("destination", k !== "OUT");
    toggle("loan", k === "RETURN");
    const hint = document.querySelector("#kind-help span");
    if (hint) hint.textContent = help[k];
    document.getElementById("id_note").required = ["COUNT", "ADJUST"].includes(
      k,
    );
    document
      .querySelectorAll("[data-price-heading]")
      .forEach((node) => (node.hidden = !hasPrice));
    document
      .querySelector(".line-table-head")
      .classList.toggle("no-price", !hasPrice);
    document.getElementById("document-total").hidden = !hasPrice;
    lines.querySelectorAll("[data-line]").forEach((row) => {
      row.classList.toggle("no-price", !hasPrice);
      row.querySelectorAll(".receipt-line-detail").forEach((node) => {
        node.hidden = k !== "IN";
        node.querySelectorAll("input").forEach((input) => {
          input.disabled = k !== "IN" || row.hidden;
        });
      });
      const price = row.querySelector('[name$="-unit_price"]');
      price.closest(".field").hidden = !hasPrice;
      price.disabled = !hasPrice;
      row.querySelector("[data-line-amount]").hidden = !hasPrice;
      const q = row.querySelector('[name$="-quantity"]');
      q.min = k === "ADJUST" ? "" : ["COUNT", "IN"].includes(k) ? "0" : "0.001";
      q.placeholder =
        k === "COUNT"
          ? "Số thực đếm"
          : k === "ADJUST"
            ? "Ví dụ: -2 hoặc 5"
            : "0";
      picker(row.querySelector('[name$="-product"]'));
    });
    totals();
    loadStock();
  }
  document.getElementById("add-line").addEventListener("click", () => {
    if (Number(count.value) >= 50) return;
    lines.insertAdjacentHTML(
      "beforeend",
      document
        .getElementById("empty-line")
        .innerHTML.replaceAll("__prefix__", count.value),
    );
    count.value = Number(count.value) + 1;
    update();
    lines.lastElementChild.querySelector(".product-combobox input")?.focus();
  });
  lines.addEventListener("click", (e) => {
    const remove = e.target.closest(".remove-line");
    if (!remove) return;
    const row = remove.closest("[data-line]");
    row.querySelector('[name$="-DELETE"]').value = "on";
    row.hidden = true;
    row.querySelectorAll("input,select").forEach((input) => {
      input.required = false;
      if (!input.name.endsWith("-DELETE")) input.disabled = true;
    });
    totals();
  });
  lines.addEventListener("input", () => {
    totals();
    availability();
  });
  lines.addEventListener("change", availability);
  kind.addEventListener("change", update);
  source.addEventListener("change", loadStock);
  loan.addEventListener("change", () => {
    const data = JSON.parse(document.getElementById("loan-data").textContent);
    const original = data.find((row) => String(row.id) === loan.value);
    if (original) {
      source.value = String(original.destination_id);
      destination.value = String(original.source_id);
    }
    loadStock();
  });
  form.addEventListener("submit", (e) => {
    const visible = [...lines.querySelectorAll("[data-line]")].filter(
      (row) => !row.hidden,
    );
    if (!visible.length) {
      e.preventDefault();
      alert("Phiếu cần ít nhất một dòng hàng. Bấm Thêm dòng hàng để tiếp tục.");
    }
  });
  update();
})();
