import { CloudConversation } from "./assistant-cloud.js";
/* Grounded internal lookup and Groq chat (Trợ lý AI v2). No on-device model. */
const root = document.getElementById("dhd-assistant");
if (root) {
  const $ = (id) => document.getElementById(id);
  const panel = $("ai-panel"),
    thread = $("ai-thread");
  let sending = false;
  let generation = 0,
    restoreFocus = null;
  let requestController = null,
    continuation = "",
    pendingCard = null;
  let cloud = null;
  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  function error(text = "") {
    $("ai-error").textContent = text;
    $("ai-error").hidden = !text;
  }
  function controls() {
    $("ai-send").disabled = sending || !!cloud?.busy;
    $("ai-clear").disabled = sending || !!cloud?.busy;
    $("ai-busy").hidden = !sending && !cloud?.busy;
    $("ai-stop").hidden = !sending && !cloud?.busy;
    $("ai-mode-internal").disabled = sending || !!cloud?.busy;
    $("ai-mode-cloud").disabled = sending || !!cloud?.busy;
  }
  function open() {
    panel.hidden = false;
    $("ai-launch").setAttribute("aria-expanded", "true");
    $("ai-question").focus({ preventScroll: true });
  }
  function close() {
    panel.hidden = true;
    $("ai-launch").setAttribute("aria-expanded", "false");
    if (restoreFocus?.isConnected) restoreFocus.focus({ preventScroll: true });
  }
  $("ai-launch").addEventListener("pointerdown", () => {
    if (panel.hidden) restoreFocus = document.activeElement;
  });
  $("ai-launch").onclick = () => (panel.hidden ? open() : close());
  $("ai-close").onclick = close;
  panel.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.stopPropagation();
      close();
    }
  });
  function message(text, label, user = false) {
    const card = el("article", "ai-msg" + (user ? " ai-user" : ""));
    card.append(
      el("small", "ai-msg-label", label),
      el("div", "ai-msg-body", text),
    );
    thread.append(card);
    thread.scrollTop = thread.scrollHeight;
    return card;
  }
  function sources(card, data) {
    if (data.sources.length) {
      const group = el("div", "ai-sources");
      group.append(el("strong", "", "Mở mục liên quan"));
      for (const source of data.sources) {
        const url = new URL(source.url, location.origin);
        if (url.origin !== location.origin) continue;
        const link = el("a", "", source.label);
        link.href = url.pathname + url.search;
        link.target = "_blank";
        link.rel = "noopener";
        group.append(link);
      }
      card.append(group);
    }
    card.append(
      el(
        "div",
        "ai-msg-note",
        `${data.notice} · ${new Date(data.at).toLocaleString("vi-VN")}`,
      ),
    );
  }
  $("ai-stop").onclick = () => {
    if (cloud?.busy) {
      cloud.stop();
      return;
    }
    if (sending) {
      generation++;
      requestController?.abort();
      sending = false;
      if (pendingCard) {
        pendingCard.querySelector(".ai-msg-label").textContent =
          "Đã dừng tra cứu";
        pendingCard.querySelector(".ai-msg-body").textContent =
          "Câu hỏi chưa hoàn tất; bạn có thể gửi lại.";
      }
      pendingCard = null;
      error("Đã dừng. Câu hỏi vẫn giữ trong ô soạn.");
    }
    controls();
  };
  $("ai-clear").onclick = () => {
    if (!sending) {
      cloud?.clear();
      thread.replaceChildren();
      continuation = "";
      error();
      controls();
    }
  };
  for (const button of root.querySelectorAll("[data-ai-prompt]"))
    button.onclick = () => {
      $("ai-question").value = button.dataset.aiPrompt;
      $("ai-form").requestSubmit();
    };
  $("ai-question").onkeydown = (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      $("ai-form").requestSubmit();
    }
  };
  // The shared business-form submit guard must not lock this asynchronous form.
  $("ai-form").addEventListener(
    "submit",
    (event) => event.preventDefault(),
    true,
  );
  $("ai-form").onsubmit = async (event) => {
    event.preventDefault();
    const question = $("ai-question").value.trim();
    if (!question || sending || cloud?.busy) return;
    if (cloud?.active) {
      await cloud.ask(question);
      return;
    }
    const current = ++generation;
    sending = true;
    controls();
    error();
    message(question, "Bạn", true);
    const card = message(
      "Đang đối chiếu hướng dẫn và dữ liệu được cấp quyền…",
      "Đang trả lời",
    );
    pendingCard = card;
    requestController = new AbortController();
    const controller = requestController;
    const timer = setTimeout(() => controller.abort(), 25000);
    const slow = setTimeout(() => {
      if (current === generation && sending)
        card.querySelector(".ai-msg-body").textContent =
          "Máy chủ đang phản hồi chậm hoặc khởi động lại. Chưa có kết quả mới; không dùng số liệu cũ để thay thế.";
    }, 3000);
    try {
      const response = await fetch("/assistant/api/context/", {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        signal: controller.signal,
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": root.querySelector("[name=csrfmiddlewaretoken]").value,
        },
        body: JSON.stringify({
          question,
          page: root.dataset.page,
          warehouse: root.dataset.warehouse,
          continuation,
        }),
      });
      let data;
      try {
        data = await response.json();
      } catch {
        throw Error(
          response.status === 403
            ? "Quyền dùng trợ lý đã thay đổi. Nhờ admin kiểm tra lại quyền tài khoản."
            : "Máy chủ chưa phản hồi đúng. Câu hỏi vẫn được giữ để thử lại.",
        );
      }
      if (!response.ok)
        throw Error(data.error || "Chưa truy vấn được thông tin.");
      if (current !== generation) return;
      continuation = data.continuation || "";
      const labels = {
        live: "Dữ liệu trực tiếp · Đã đối chiếu quyền",
        knowledge: "Hướng dẫn chức năng hiện có",
        draft: "Mẫu nội dung tham khảo",
        clarification: "Cần làm rõ yêu cầu",
      };
      card.querySelector(".ai-msg-label").textContent =
        labels[data.answer_kind] || "Tra cứu trực tiếp từ phần mềm";
      card.querySelector(".ai-msg-body").textContent = data.answer;
      sources(card, data);
      if ($("ai-question").value.trim() === question)
        $("ai-question").value = "";
      thread.scrollTop = thread.scrollHeight;
    } catch (e) {
      if (current === generation) {
        card.querySelector(".ai-msg-label").textContent = "Chưa có kết quả";
        card.querySelector(".ai-msg-body").textContent =
          "Chưa lấy được câu trả lời mới. Câu hỏi vẫn giữ trong ô soạn để thử lại.";
        error(
          e.name === "AbortError"
            ? "Kết nối gián đoạn hoặc máy chủ phản hồi chậm. Câu hỏi được giữ để gửi lại."
            : e.message || "Chưa trả lời được.",
        );
      }
    } finally {
      clearTimeout(timer);
      clearTimeout(slow);
      if (current === generation) {
        sending = false;
        pendingCard = null;
        requestController = null;
        controls();
      }
    }
  };
  cloud = new CloudConversation({
    root,
    $,
    controls,
    error,
    message,
    sources,
    thread,
    cancelLocal: () => {},
  });
  window.addEventListener("pagehide", () => {
    cloud.clear();
    generation++;
    requestController?.abort();
    sending = false;
  });
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) {
      continuation = "";
      controls();
    }
  });
}
