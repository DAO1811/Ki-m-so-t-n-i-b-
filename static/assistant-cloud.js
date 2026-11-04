/* Multi-turn Groq conversation. No API key, model download, localStorage or form scraping. */
export class CloudConversation {
  constructor({
    root,
    $,
    controls,
    error,
    message,
    sources,
    cancelLocal,
    thread,
  }) {
    Object.assign(this, {
      root,
      $,
      controls,
      error,
      message,
      sources,
      cancelLocal,
      thread,
    });
    this.active = false;
    this.busy = false;
    this.available = false;
    this.conversation = "";
    this.continuation = "";
    this.job = null;
    this.generation = 0;
    this.controller = null;
    $("ai-mode-cloud").onclick = () => this.select(true);
    $("ai-mode-internal").onclick = () => this.select(false);
    $("ai-cloud-refresh").onclick = () => this.status();
  }
  select(active) {
    if (this.$("ai-send").disabled || this.busy) return;
    this.cancelLocal();
    this.active = active;
    this.$("ai-mode-cloud").setAttribute("aria-pressed", String(active));
    this.$("ai-mode-internal").setAttribute("aria-pressed", String(!active));
    this.$("ai-cloud-info").hidden = !active;
    this.$("ai-enable").hidden = active;
    this.$("ai-question").placeholder = active
      ? "Trò chuyện, nhờ viết nội dung hoặc hỏi tiếp…"
      : "Hỏi về thao tác, mã hàng, số phiếu…";
    this.controls();
    if (active) this.status();
  }
  async fetch(path, body, signal, keepalive = false) {
    const options = { credentials: "same-origin", cache: "no-store", signal };
    if (body !== undefined) {
      options.method = "POST";
      options.keepalive = keepalive;
      options.headers = {
        "Content-Type": "application/json",
        "X-CSRFToken": this.root.querySelector("[name=csrfmiddlewaretoken]")
          .value,
      };
      options.body = JSON.stringify(body);
    }
    const response = await fetch(path, options);
    let data;
    try {
      data = await response.json();
    } catch {
      throw Error(
        response.status === 403
          ? "Quyền trò chuyện AI đã thay đổi. Nhờ Admin kiểm tra lại quyền."
          : "Máy chủ chưa phản hồi đúng. Câu hỏi được giữ để thử lại.",
      );
    }
    if (!response.ok)
      throw Error(data.error || "Chưa lấy được câu trả lời AI.");
    return data;
  }
  async status() {
    this.$("ai-cloud-status").textContent = "Đang kiểm tra kết nối…";
    try {
      const data = await this.fetch("/assistant/api/cloud/status/");
      this.available = data.permitted && data.configured;
      this.$("ai-cloud-consent").hidden = !this.available;
      this.$("ai-cloud-setup").hidden = !data.admin;
      this.$("ai-cloud-status").textContent = !data.permitted
        ? "Admin cần cấp quyền Trò chuyện qua Groq Free cho tài khoản này."
        : !data.configured
          ? "Groq Free chưa kết nối. Tra cứu nội bộ vẫn dùng được."
          : `Groq Free đã cấu hình · Tối đa ${data.requests_per_day} lượt/người/ngày trong hạn mức chung. Lượt hỏi dài có thể hết token sớm hơn.`;
      if (this.active)
        this.$("ai-engine-state").textContent = this.available
          ? "Groq Free · Không cần tải mô hình"
          : "Trò chuyện AI · Chưa sẵn sàng";
    } catch (e) {
      this.available = false;
      this.$("ai-cloud-status").textContent = e.message;
    }
  }
  cancelRequest() {
    const id = this.job;
    this.job = null;
    if (id)
      this.fetch(
        `/assistant/api/cloud/jobs/${id}/cancel/`,
        {},
        undefined,
        true,
      ).catch(() => {});
  }
  stop() {
    this.generation++;
    this.controller?.abort();
    this.cancelRequest();
    if (this.card)
      this.card.querySelector(".ai-msg-label").textContent =
        "Đã dừng · Nội dung một phần";
    this.busy = false;
    this.controls();
  }
  clear() {
    this.stop();
    this.conversation = "";
    this.continuation = "";
    this.card = null;
  }
  async ask(question) {
    if (this.busy) return;
    if (!this.available) {
      this.error(
        "Groq Free chưa sẵn sàng. Xem trạng thái kết nối bên trên hoặc dùng Tra cứu nội bộ.",
      );
      return;
    }
    if (!this.$("ai-cloud-accept").checked) {
      this.error(
        "Bạn cần chọn đồng ý gửi nội dung trò chuyện tới Groq trước khi hỏi AI.",
      );
      return;
    }
    this.error();
    this.busy = true;
    this.controls();
    const generation = ++this.generation;
    this.controller = new AbortController();
    const controller = this.controller;
    this.message(question, "Bạn", true);
    const card = (this.card = this.message(
      "Đang gửi câu hỏi…",
      "Trò chuyện AI · Groq Free",
    ));
    const timer = setTimeout(() => controller.abort(), 50000);
    try {
      const start = await this.fetch(
        "/assistant/api/cloud/start/",
        {
          question,
          page: this.root.dataset.page,
          warehouse: this.root.dataset.warehouse,
          continuation: this.continuation,
          conversation: this.conversation,
          consent: true,
          client_key: crypto.randomUUID(),
        },
        controller.signal,
      );
      if (generation !== this.generation) {
        if (start.id) {
          this.job = start.id;
          this.cancelRequest();
        }
        return;
      }
      this.continuation = start.continuation || "";
      if (start.kind === "direct") {
        card.querySelector(".ai-msg-label").textContent =
          "Dữ liệu trực tiếp · Đã đối chiếu quyền";
        card.querySelector(".ai-msg-body").textContent = start.answer;
        this.sources(card, start);
      } else {
        this.job = start.id;
        card.querySelector(".ai-msg-body").textContent = "AI đang suy nghĩ…";
        while (generation === this.generation) {
          const data = await this.fetch(
            `/assistant/api/cloud/jobs/${start.id}/`,
            undefined,
            controller.signal,
          );
          if (generation !== this.generation) return;
          if (data.text)
            card.querySelector(".ai-msg-body").textContent = data.text;
          if (data.state === "DONE") {
            this.conversation = data.conversation;
            this.job = null;
            card.querySelector(".ai-msg-label").textContent =
              "Groq Free · GPT-OSS · Nội dung AI tham khảo";
            break;
          }
          if (["FAILED", "CANCELLED"].includes(data.state)) {
            this.job = null;
            card.querySelector(".ai-msg-label").textContent = data.text
              ? "Nội dung một phần · Chưa hoàn tất"
              : "Chưa có câu trả lời";
            card.querySelector(".ai-msg-body").textContent =
              data.text || data.error;
            throw Error(data.error || "Lượt trả lời đã dừng.");
          }
          await new Promise((resolve) => setTimeout(resolve, 650));
        }
      }
      if (
        generation === this.generation &&
        this.$("ai-question").value.trim() === question
      )
        this.$("ai-question").value = "";
      this.thread.scrollTop = this.thread.scrollHeight;
    } catch (e) {
      if (generation === this.generation) {
        this.cancelRequest();
        card.querySelector(".ai-msg-label").textContent =
          "Chưa hoàn tất · Câu hỏi được giữ lại";
        if (
          card
            .querySelector(".ai-msg-body")
            .textContent.startsWith("AI đang") ||
          card.querySelector(".ai-msg-body").textContent.startsWith("Đang gửi")
        )
          card.querySelector(".ai-msg-body").textContent =
            "Chưa nhận được câu trả lời hoàn chỉnh; bạn có thể thử lại.";
        this.error(
          e.name === "AbortError"
            ? "Kết nối AI gián đoạn hoặc phản hồi quá lâu. Câu hỏi vẫn được giữ."
            : e.message,
        );
      }
    } finally {
      clearTimeout(timer);
      if (generation === this.generation) {
        this.busy = false;
        this.controller = null;
        this.controls();
      }
    }
  }
}
