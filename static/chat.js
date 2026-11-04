/* DHD Connect: safe DOM rendering, bounded history and idempotent sends. */
(() => {
  "use strict";
  const app = document.querySelector("[data-chat-app]");
  if (!app) return;
  const boot = JSON.parse(
    document.getElementById("chat-bootstrap").textContent,
  );
  const $ = (id) => document.getElementById(id);
  const state = {
    room: null,
    rooms: [],
    filter: "all",
    messages: new Map(),
    last: 0,
    version: 0,
    first: 0,
    more: false,
    query: "",
    reply: null,
    sticker: "",
    pendingKey: null,
    people: new Map(),
    addMode: false,
    sending: false,
    generation: 0,
    emoji: [],
    picker: "emoji",
    pickerLimit: 140,
    call: null,
  };
  const node = (tag, cls, text) => {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text !== undefined) el.textContent = text;
    return el;
  };
  const csrf = () =>
    document.querySelector("#chat-compose [name=csrfmiddlewaretoken]").value;
  const error = (message, id = "chat-error") => {
    $(id).textContent = message || "";
    $(id).hidden = !message;
  };
  async function api(url, data, method = "GET") {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 22000);
    try {
      const response = await fetch(url, {
        method,
        credentials: "same-origin",
        cache: "no-store",
        headers:
          method === "GET"
            ? {}
            : {
                "X-CSRFToken": csrf(),
                ...(data instanceof FormData
                  ? {}
                  : { "Content-Type": "application/json" }),
              },
        body:
          method === "GET"
            ? undefined
            : data instanceof FormData
              ? data
              : JSON.stringify(data),
        signal: controller.signal,
      });
      let result;
      try {
        result = await response.json();
      } catch {
        result = {
          error: "Máy chủ chưa phản hồi. Nội dung đang soạn vẫn được giữ.",
        };
      }
      if (!response.ok) {
        if (
          [401, 403, 404].includes(response.status) &&
          url.includes("/rooms/")
        )
          window.dispatchEvent(new Event("chat-access-denied"));
        throw new Error(
          result.error || "Chưa thực hiện được. Vui lòng thử lại.",
        );
      }
      return result;
    } catch (e) {
      if (e.name === "AbortError" || e instanceof TypeError)
        throw new Error(
          "Kết nối bị gián đoạn. Nội dung chưa được xác nhận gửi; bạn có thể thử lại.",
        );
      throw e;
    } finally {
      clearTimeout(timer);
    }
  }
  window.DHDChat = {
    boot,
    api,
    csrf,
    error,
    node,
    getRoom: () => state.room,
    getCall: () => state.call,
    refresh: () => loadTimeline(false),
    roomAPI: (suffix) => `/chat/api/rooms/${boot.room_id}/${suffix}`,
  };
  const roomAPI = (suffix) => window.DHDChat.roomAPI(suffix);
  function initials(name) {
    return name
      .split(/\s+/)
      .filter(Boolean)
      .slice(-2)
      .map((x) => x[0])
      .join("")
      .toUpperCase();
  }
  function sticker(el, item) {
    el.replaceChildren();
    el.className = "chat-sticker";
    el.style.backgroundPosition = `${(item.index % 6) * 20}% ${Math.floor(item.index / 6) * 20}%`;
    el.setAttribute("role", "img");
    el.setAttribute("aria-label", item.label);
    if (item.caption) {
      el.classList.add("chat-sticker-captioned");
      el.append(node("span", "chat-sticker-caption", item.caption));
    }
  }
  function badge(count) {
    const el = $("chat-global-unread");
    if (el) {
      el.textContent = count > 99 ? "99+" : String(count);
      el.hidden = !count;
    }
  }
  function renderInbox(rooms) {
    state.rooms = rooms;
    const list = $("chat-room-list");
    list.replaceChildren();
    const filtered = rooms.filter((r) =>
      state.filter === "groups"
        ? r.kind === "GROUP"
        : state.filter === "unread"
          ? r.unread > 0
          : true,
    );
    for (const room of filtered) {
      const link = node(
        "a",
        "chat-room-link" + (room.id === boot.room_id ? " is-active" : ""),
      );
      link.href = room.url;
      const avatar = node(
        "span",
        "chat-avatar",
        room.kind === "GROUP" ? "✦" : initials(room.title),
      );
      const body = node("span", "chat-room-link-body");
      body.append(
        node("strong", "", room.title),
        node(
          "small",
          "",
          room.kind === "GROUP"
            ? room.members
              ? `${room.members.length} thành viên`
              : "Nhóm làm việc"
            : "Trò chuyện cá nhân",
        ),
      );
      link.append(avatar, body);
      if (room.unread)
        link.append(
          node(
            "span",
            "chat-badge",
            room.unread > 99 ? "99+" : String(room.unread),
          ),
        );
      list.append(link);
    }
    if (!filtered.length)
      list.append(
        node(
          "p",
          "chat-muted",
          "Chưa có hội thoại phù hợp. Bấm biểu tượng bút để bắt đầu.",
        ),
      );
  }
  let inboxGeneration = 0;
  async function loadInbox() {
    const generation = ++inboxGeneration;
    try {
      const data = await api(
        "/chat/api/summary/?compact=1&q=" +
          encodeURIComponent($("chat-room-search").value),
      );
      if (generation !== inboxGeneration) return;
      renderInbox(data.rooms);
      badge(data.unread);
    } catch (e) {
      error(e.message);
    }
  }
  window.addEventListener("dhd-chat-summary", (event) => {
    badge(event.detail.unread);
    if (!$("chat-room-search").value) renderInbox(event.detail.rooms);
  });
  $("chat-room-search").addEventListener("input", debounce(loadInbox, 250));
  for (const b of app.querySelectorAll("[data-room-filter]"))
    b.onclick = () => {
      state.filter = b.dataset.roomFilter;
      for (const other of app.querySelectorAll("[data-room-filter]"))
        other.classList.toggle("is-active", b === other);
      renderInbox(state.rooms);
    };
  function debounce(fn, time) {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), time);
    };
  }
  function setRoom(room) {
    state.room = room;
    $("chat-title").textContent = room.title;
    $("chat-room-avatar").textContent =
      room.kind === "GROUP" ? "✦" : initials(room.title);
    $("chat-members-open").textContent =
      room.kind === "GROUP"
        ? `${room.members.length} thành viên · Thông tin nhóm`
        : "Trò chuyện cá nhân · Thông tin";
    $("chat-welcome").hidden = true;
    $("chat-active-thread").hidden = false;
    app.classList.add("is-room-open");
  }
  function messageElement(message) {
    const wrap = node(
      "article",
      "chat-message" + (message.mine ? " is-mine" : ""),
    );
    wrap.dataset.id = message.id;
    wrap.dataset.seq = message.seq;
    wrap.dataset.signature = JSON.stringify(message);
    if (!message.mine)
      wrap.append(node("div", "chat-message-name", message.sender.name));
    const bubble = node(
      "div",
      "chat-bubble" +
        (message.sticker &&
        !message.text &&
        !message.files.length &&
        !message.reply
          ? " is-sticker-only"
          : ""),
    );
    if (message.reply) {
      const quote = node("div", "chat-quote");
      quote.append(
        node("strong", "", message.reply.name),
        node("span", "", message.reply.text),
      );
      bubble.append(quote);
    }
    if (message.text) bubble.append(node("div", "", message.text));
    if (message.sticker) {
      const art = node("span");
      sticker(art, message.sticker);
      bubble.append(art);
    }
    for (const file of message.files) {
      const a = node("a", file.image ? "" : "chat-file");
      a.href = file.url;
      a.target = "_blank";
      a.rel = "noopener";
      if (file.image) {
        const img = node("img", "chat-image");
        img.src = file.url;
        img.alt = file.name;
        img.loading = "lazy";
        img.onerror = () => {
          img.replaceWith(
            node("span", "chat-muted", "Chưa tải được ảnh. Bấm để thử mở lại."),
          );
        };
        a.append(img);
      } else {
        a.append(
          node("span", "chat-file-icon", "PDF"),
          node("span", "", file.name),
        );
      }
      bubble.append(a);
    }
    wrap.append(bubble);
    const reactions = node("div", "chat-reactions");
    for (const reaction of message.reactions) {
      const b = node(
        "button",
        reaction.mine ? "is-mine" : "",
        `${reaction.emoji} ${reaction.count}`,
      );
      b.type = "button";
      b.setAttribute(
        "aria-label",
        `${reaction.emoji}: ${reaction.count}, ${reaction.mine ? "bỏ biểu cảm của bạn" : "thêm biểu cảm"}`,
      );
      b.onclick = () => react(message, reaction.emoji);
      reactions.append(b);
    }
    wrap.append(reactions);
    const meta = node("div", "chat-message-meta");
    const time = new Date(message.at);
    const stamp = node(
      "time",
      "",
      time.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" }),
    );
    stamp.dateTime = message.at;
    stamp.title = time.toLocaleString("vi-VN");
    meta.append(stamp);
    if (message.mine) {
      const status = node(
        "span",
        "",
        message.read_by.length
          ? `Đã xem · ${message.read_by.length}`
          : "Đã gửi",
      );
      status.title = message.read_by.join(", ");
      meta.append(status);
    }
    const reply = node("button", "chat-plain", "Trả lời");
    reply.type = "button";
    reply.onclick = () => {
      state.reply = message;
      $("chat-reply-label").textContent =
        `Trả lời ${message.sender.name}: ${(message.text || message.sticker?.label || "Tệp đính kèm").slice(0, 100)}`;
      $("chat-reply").hidden = false;
      resetKey();
      $("chat-text").focus();
    };
    const reactButton = node("button", "chat-plain", "☺");
    reactButton.type = "button";
    reactButton.setAttribute("aria-label", "Thêm biểu cảm");
    reactButton.onclick = () => {
      const old = wrap.querySelector(".chat-react-popover");
      if (old) {
        old.remove();
        return;
      }
      const pop = node("div", "chat-react-popover");
      for (const emoji of boot.emojis) {
        const b = node("button", "", emoji);
        b.type = "button";
        b.setAttribute("aria-label", emoji);
        b.onclick = () => {
          pop.remove();
          react(message, emoji);
        };
        pop.append(b);
      }
      wrap.append(pop);
    };
    meta.append(reply, reactButton);
    wrap.append(meta);
    return wrap;
  }
  async function react(message, emoji) {
    try {
      const result = await api(
        roomAPI(`messages/${message.id}/reaction/`),
        { emoji },
        "POST",
      );
      if (result.message) reconcile([result.message]);
      else await loadTimeline(false);
    } catch (e) {
      error(e.message);
    }
  }
  function reconcile(messages) {
    let changed = false;
    for (const m of messages) {
      const old = state.messages.get(m.id);
      if (JSON.stringify(old) !== JSON.stringify(m)) {
        state.messages.set(m.id, m);
        changed = true;
      }
    }
    if (!changed) return;
    const list = $("chat-messages");
    for (const message of [...state.messages.values()].sort(
      (a, b) => a.seq - b.seq,
    )) {
      const old = list.querySelector(`[data-id="${message.id}"]`);
      if (old?.dataset.signature === JSON.stringify(message)) continue;
      const fresh = messageElement(message);
      if (old) old.replaceWith(fresh);
      else {
        const next = [...list.children].find(
          (el) => Number(el.dataset.seq) > message.seq,
        );
        list.insertBefore(fresh, next || null);
      }
    }
  }
  let loading = false,
    failures = 0,
    pollTimer = null,
    needsReset = false;
  async function loadTimeline(initial = false, older = false) {
    if (!boot.room_id) return;
    if (
      !initial &&
      !older &&
      window.DHDChatActivity &&
      !window.DHDChatActivity.canPoll()
    ) {
      $("chat-connection").textContent = "Tạm dừng · chạm để cập nhật";
      clearTimeout(pollTimer);
      return;
    }
    if (loading) {
      if (initial) needsReset = true;
      return;
    }
    loading = true;
    const generation = state.generation;
    const scroller = $("chat-timeline"),
      oldHeight = scroller.scrollHeight,
      oldTop = scroller.scrollTop,
      nearBottom = oldHeight - oldTop - scroller.clientHeight < 110;
    try {
      const q = new URLSearchParams();
      if (state.query) q.set("q", state.query);
      if (older && state.first) q.set("before", state.first);
      else if (!initial && state.last && !state.query)
        q.set("after", state.last);
      if (!initial && !older && !state.query && state.version)
        q.set("version", state.version);
      const result = await api(roomAPI("messages/") + "?" + q);
      if (generation !== state.generation) return;
      if (result.unchanged) {
        state.call = result.call;
        window.dispatchEvent(
          new CustomEvent("chat-room-call", { detail: result.call }),
        );
        $("chat-typing").textContent = result.typing.length
          ? result.typing.slice(0, 3).join(", ") + " đang soạn…"
          : "";
        failures = 0;
        $("chat-connection").textContent = "Đang cập nhật tự động";
        return;
      }
      state.version = result.room.revision;
      setRoom(result.room);
      if (initial) {
        state.messages.clear();
        $("chat-messages").replaceChildren();
        state.first = 0;
        state.last = 0;
      }
      reconcile([...(result.updates || []), ...result.messages]);
      for (const m of result.messages) {
        state.last = Math.max(state.last, m.seq);
        state.first = state.first ? Math.min(state.first, m.seq) : m.seq;
      }
      state.more = result.more;
      if (initial || older) $("chat-older").hidden = !result.more;
      $("chat-empty-thread").hidden = state.messages.size > 0;
      $("chat-typing").textContent = result.typing.length
        ? result.typing.slice(0, 3).join(", ") + " đang soạn…"
        : "";
      state.call = result.call;
      window.dispatchEvent(
        new CustomEvent("chat-room-call", { detail: result.call }),
      );
      if (older)
        scroller.scrollTop = oldTop + scroller.scrollHeight - oldHeight;
      else if (initial || nearBottom)
        scroller.scrollTop = scroller.scrollHeight;
      else if (result.messages.length) $("chat-new-messages").hidden = false;
      if (
        !state.query &&
        document.visibilityState === "visible" &&
        (initial || nearBottom) &&
        state.last
      )
        await api(roomAPI("read/"), { seq: state.last }, "POST");
      failures = 0;
      $("chat-connection").textContent = "Đang cập nhật tự động";
      if (result.more && !older && q.has("after"))
        setTimeout(() => loadTimeline(false), 30);
    } catch (e) {
      failures++;
      $("chat-connection").textContent = "Mất kết nối · đang thử lại";
      error(e.message);
    } finally {
      loading = false;
      clearTimeout(pollTimer);
      if (needsReset) {
        needsReset = false;
        setTimeout(() => loadTimeline(true), 0);
        return;
      }
      if (boot.room_id)
        pollTimer = setTimeout(
          () => loadTimeline(false),
          Math.min(
            30000,
            (document.hidden ? 15000 : 3500) * Math.max(1, failures),
          ),
        );
    }
  }
  $("chat-older").onclick = () => loadTimeline(false, true);
  $("chat-message-search").addEventListener(
    "input",
    debounce(() => {
      state.query = $("chat-message-search").value.trim();
      state.generation++;
      loadTimeline(true);
    }, 350),
  );
  $("chat-new-messages").onclick = () => {
    $("chat-timeline").scrollTop = $("chat-timeline").scrollHeight;
    $("chat-new-messages").hidden = true;
    if (state.last)
      api(roomAPI("read/"), { seq: state.last }, "POST").catch((e) =>
        error(e.message),
      );
  };
  $("chat-timeline").addEventListener(
    "scroll",
    debounce(() => {
      const el = $("chat-timeline");
      if (el.scrollHeight - el.scrollTop - el.clientHeight < 100) {
        $("chat-new-messages").hidden = true;
        if (state.last && !state.query && !document.hidden)
          api(roomAPI("read/"), { seq: state.last }, "POST").catch(() => {});
      }
    }, 400),
  );
  $("chat-back").onclick = () => {
    app.classList.remove("is-room-open");
  };
  function resetKey() {
    state.pendingKey = null;
  }
  function fileFingerprint() {
    return JSON.stringify(
      [...$("chat-files").files].map((f) => [
        f.name,
        f.size,
        f.lastModified,
        f.type,
      ]),
    );
  }
  $("chat-compose").onsubmit = async (event) => {
    event.preventDefault();
    if (state.sending) return;
    if (
      !$("chat-text").value.trim() &&
      !$("chat-files").files.length &&
      !state.sticker
    )
      return;
    state.sending = true;
    $("chat-send").disabled = true;
    $("chat-send").textContent = "Đang gửi…";
    error("");
    state.pendingKey ||= crypto.randomUUID();
    const sent = {
      text: $("chat-text").value,
      reply: state.reply?.id || null,
      sticker: state.sticker,
      files: fileFingerprint(),
    };
    const data = new FormData();
    data.set("text", $("chat-text").value);
    data.set("client_key", state.pendingKey);
    data.set("sticker", state.sticker);
    if (state.reply) data.set("reply_id", state.reply.id);
    for (const file of $("chat-files").files) data.append("files", file);
    try {
      await api(roomAPI("send/"), data, "POST");
      // Keep the next draft if the user types while the previous upload is pending.
      // Acknowledged attachments must not carry into that next message.
      if ($("chat-text").value === sent.text) $("chat-text").value = "";
      if (fileFingerprint() === sent.files) {
        $("chat-files").value = "";
        $("chat-file-preview").replaceChildren();
      }
      if ((state.reply?.id || null) === sent.reply) {
        state.reply = null;
        $("chat-reply").hidden = true;
      }
      if (state.sticker === sent.sticker) {
        state.sticker = "";
        $("chat-sticker-preview").hidden = true;
      }
      resetKey();
      await loadTimeline(false);
      $("chat-timeline").scrollTop = $("chat-timeline").scrollHeight;
      loadInbox();
    } catch (e) {
      error(e.message);
    } finally {
      state.sending = false;
      $("chat-send").disabled = false;
      $("chat-send").textContent = "Gửi →";
    }
  };
  $("chat-text").onkeydown = (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      $("chat-compose").requestSubmit();
    }
  };
  let lastTyping = 0;
  $("chat-text").addEventListener("input", () => {
    resetKey();
    if (Date.now() - lastTyping > 3500) {
      lastTyping = Date.now();
      api(roomAPI("typing/"), {}, "POST").catch(() => {});
    }
  });
  $("chat-file-open").onclick = () => $("chat-files").click();
  $("chat-files").onchange = () => {
    const files = [...$("chat-files").files];
    if (
      files.length > 3 ||
      files.reduce((sum, f) => sum + f.size, 0) > 8 * 1024 * 1024
    ) {
      error("Chọn tối đa 3 ảnh/PDF, tổng không quá 8 MB.");
      $("chat-files").value = "";
    }
    resetKey();
    $("chat-file-preview").replaceChildren();
    for (const file of $("chat-files").files) {
      const chip = node(
        "span",
        "",
        `${file.name} · ${(file.size / 1024).toFixed(0)} KB `,
      );
      const remove = node("button", "chat-plain", "×");
      remove.type = "button";
      remove.setAttribute("aria-label", "Bỏ các tệp đã chọn");
      remove.onclick = () => {
        $("chat-files").value = "";
        $("chat-file-preview").replaceChildren();
        resetKey();
      };
      chip.append(remove);
      $("chat-file-preview").append(chip);
    }
  };
  $("chat-reply-cancel").onclick = () => {
    state.reply = null;
    $("chat-reply").hidden = true;
    resetKey();
  };
  $("chat-sticker-cancel").onclick = () => {
    state.sticker = "";
    $("chat-sticker-preview").hidden = true;
    resetKey();
  };
  const normalize = (s) =>
    s
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/đ/g, "d");
  const synonyms = {
    vui: "smile happy joy",
    cuoi: "laugh grin smile joy",
    yeu: "heart love",
    buon: "cry sad disappointed",
    camon: "thank fold pray",
    chao: "wave hand",
    congviec: "office laptop briefcase",
    dongy: "thumb check ok",
    tien: "money coin",
    meo: "cat",
    cho: "dog",
    hoa: "flower",
    an: "food",
    tay: "hand",
    xong: "check",
    lemon: "lemon",
  };
  function matches(text, query) {
    const norm = normalize(query).replace(/\s/g, ""),
      target = normalize(text);
    return (
      target.includes(normalize(query)) ||
      (synonyms[norm] || "").split(" ").some((x) => x && target.includes(x))
    );
  }
  function recent() {
    try {
      return JSON.parse(
        localStorage.getItem(`dhd-chat-recent-${boot.user_id}`) || "[]",
      ).slice(0, 36);
    } catch {
      return [];
    }
  }
  function remember(value) {
    try {
      localStorage.setItem(
        `dhd-chat-recent-${boot.user_id}`,
        JSON.stringify(
          [value, ...recent().filter((x) => x !== value)].slice(0, 36),
        ),
      );
    } catch {
      /* Storage is optional; private message text is never persisted here. */
    }
  }
  function categories() {
    const select = $("chat-picker-category");
    select.replaceChildren();
    for (const value of [
      "Tất cả",
      "Gần đây",
      ...new Set(
        (state.picker === "emoji" ? state.emoji : boot.stickers).map(
          (x) => x.category || x.pack,
        ),
      ),
    ]) {
      const option = node("option", "", value);
      option.value = value;
      select.append(option);
    }
  }
  function pickerRender() {
    const grid = $("chat-picker-grid"),
      query = $("chat-picker-search").value.trim(),
      category = $("chat-picker-category").value;
    grid.replaceChildren();
    grid.classList.toggle("is-stickers", state.picker === "stickers");
    let items = state.picker === "emoji" ? state.emoji : boot.stickers;
    if (category === "Gần đây") {
      const rec = recent();
      items = items
        .filter((x) => rec.includes(x.emoji || x.id))
        .sort(
          (a, b) => rec.indexOf(a.emoji || a.id) - rec.indexOf(b.emoji || b.id),
        );
    } else if (category !== "Tất cả")
      items = items.filter((x) => (x.category || x.pack) === category);
    if (query)
      items = items.filter((x) =>
        matches(`${x.label} ${x.category || x.pack}`, query),
      );
    for (const item of items.slice(0, state.pickerLimit)) {
      const button = node("button");
      button.type = "button";
      button.title = item.label;
      button.setAttribute("aria-label", item.label);
      if (state.picker === "emoji") button.textContent = item.emoji;
      else {
        const art = node("span");
        sticker(art, item);
        button.append(art);
      }
      button.onclick = () => {
        remember(item.emoji || item.id);
        if (item.emoji) {
          const text = $("chat-text"),
            start = text.selectionStart;
          text.setRangeText(item.emoji, start, text.selectionEnd, "end");
          resetKey();
          text.focus();
        } else {
          state.sticker = item.id;
          sticker($("chat-picked-sticker"), item);
          $("chat-sticker-preview").hidden = false;
          resetKey();
        }
        $("chat-picker").hidden = true;
      };
      grid.append(button);
    }
    if (!items.length)
      grid.append(node("p", "chat-muted", "Chưa có kết quả phù hợp."));
    $("chat-picker-more").hidden = items.length <= state.pickerLimit;
  }
  $("chat-emoji-open").onclick = async () => {
    const picker = $("chat-picker");
    picker.hidden = !picker.hidden;
    if (!picker.hidden) {
      if (!state.emoji.length) {
        try {
          const response = await fetch("/static/chat-assets/emoji.json", {
            credentials: "same-origin",
          });
          if (!response.ok) throw Error();
          state.emoji = await response.json();
        } catch {
          state.emoji = boot.emojis.map((emoji) => ({
            emoji,
            label: emoji,
            category: "Cảm xúc",
          }));
          error(
            "Chưa tải được toàn bộ emoji. Bạn vẫn dùng được các biểu cảm nhanh.",
          );
        }
      }
      categories();
      pickerRender();
    }
  };
  $("chat-picker-close").onclick = () => ($("chat-picker").hidden = true);
  for (const b of document.querySelectorAll("[data-picker-tab]"))
    b.onclick = () => {
      state.picker = b.dataset.pickerTab;
      state.pickerLimit = 140;
      for (const other of document.querySelectorAll("[data-picker-tab]"))
        other.classList.toggle("is-active", other === b);
      categories();
      pickerRender();
    };
  $("chat-picker-search").oninput = debounce(() => {
    state.pickerLimit = 140;
    pickerRender();
  }, 150);
  $("chat-picker-category").onchange = () => {
    state.pickerLimit = 140;
    pickerRender();
  };
  $("chat-picker-more").onclick = () => {
    state.pickerLimit += 140;
    pickerRender();
  };
  document.addEventListener("click", (event) => {
    if (
      !event.target.closest("#chat-picker") &&
      !event.target.closest("#chat-emoji-open")
    )
      $("chat-picker").hidden = true;
  });
  let peopleGeneration = 0;
  async function loadPeople() {
    const generation = ++peopleGeneration;
    try {
      const data = await api(
        "/chat/api/people/?q=" +
          encodeURIComponent($("chat-people-search").value),
      );
      if (generation !== peopleGeneration) return;
      $("chat-people-list").replaceChildren();
      for (const person of data.people) {
        const label = node("label", "chat-people-option"),
          check = node("input");
        check.type = "checkbox";
        check.value = person.id;
        check.checked = state.people.has(person.id);
        check.disabled =
          state.addMode && state.room.members.some((m) => m.id === person.id);
        const text = node("span", "", person.name);
        text.append(node("small", "", person.username));
        label.append(check, text);
        check.onchange = () => {
          if (!$("chat-create-group").checked && !state.addMode)
            state.people.clear();
          if (check.checked) state.people.set(person.id, person);
          else state.people.delete(person.id);
          renderSelected();
          loadPeople();
        };
        $("chat-people-list").append(label);
      }
    } catch (e) {
      error(e.message, "chat-create-error");
    }
  }
  function renderSelected() {
    $("chat-selected-people").replaceChildren();
    for (const person of state.people.values())
      $("chat-selected-people").append(node("span", "", person.name));
  }
  function newChat(add = false) {
    state.addMode = add;
    state.people.clear();
    $("chat-people-search").value = "";
    $("chat-create-group").checked = add;
    $("chat-create-group").disabled = add || !boot.can_groups;
    $("chat-group-title-label").hidden = true;
    $("chat-group-title").required = false;
    $("chat-group-title").value = "";
    $("chat-create-submit").textContent = add
      ? "Thêm vào nhóm"
      : "Bắt đầu trò chuyện";
    error("", "chat-create-error");
    renderSelected();
    $("chat-new-dialog").showModal();
    loadPeople();
  }
  $("chat-new").onclick = () => newChat();
  $("chat-welcome-new").onclick = () => newChat();
  const delayedPeople = debounce(loadPeople, 250);
  $("chat-people-search").addEventListener("input", () => {
    $("chat-people-list").replaceChildren(
      node("p", "chat-muted", "Đang tìm đồng nghiệp…"),
    );
    delayedPeople();
  });
  $("chat-create-group").onchange = () => {
    $("chat-group-title-label").hidden = !$("chat-create-group").checked;
    $("chat-group-title").required = $("chat-create-group").checked;
    state.people.clear();
    renderSelected();
    loadPeople();
  };
  $("chat-create-form").onsubmit = async (event) => {
    event.preventDefault();
    $("chat-create-submit").disabled = true;
    try {
      if (state.addMode) {
        await api(
          roomAPI("manage/"),
          { command: "add", members: [...state.people.keys()] },
          "POST",
        );
        $("chat-new-dialog").close();
        await loadTimeline(false);
        await showInfo("members");
      } else {
        const data = await api(
          "/chat/api/rooms/",
          {
            members: [...state.people.keys()],
            group: $("chat-create-group").checked,
            title: $("chat-group-title").value,
          },
          "POST",
        );
        location.assign(data.url);
      }
    } catch (e) {
      error(e.message, "chat-create-error");
    } finally {
      $("chat-create-submit").disabled = false;
    }
  };
  for (const button of document.querySelectorAll("[data-close-dialog]"))
    button.onclick = () => button.closest("dialog").close();
  async function manage(command, values = {}) {
    await api(roomAPI("manage/"), { command, ...values }, "POST");
    await loadTimeline(false);
  }
  async function showInfo(tab = "members") {
    if (!$("chat-info-dialog").open) $("chat-info-dialog").showModal();
    $("chat-info-title").textContent = state.room.title;
    $("chat-info-content").replaceChildren();
    error("", "chat-info-error");
    for (const b of document.querySelectorAll("[data-info-tab]"))
      b.classList.toggle("is-active", b.dataset.infoTab === tab);
    const canManage =
      state.room.kind === "GROUP" &&
      state.room.owner_id === boot.user_id &&
      boot.can_groups;
    $("chat-manage-group").hidden = !canManage || tab !== "members";
    $("chat-leave-group").hidden =
      state.room.kind !== "GROUP" || tab !== "members";
    $("chat-rename").value = state.room.title;
    try {
      if (tab === "members") {
        for (const member of state.room.members) {
          const row = node("div", "chat-info-member");
          row.append(
            node("span", "chat-avatar", initials(member.name)),
            node(
              "span",
              "",
              member.name +
                (member.id === state.room.owner_id &&
                state.room.kind === "GROUP"
                  ? " · Trưởng nhóm"
                  : ""),
            ),
          );
          if (canManage && member.id !== boot.user_id) {
            const remove = node("button", "chat-plain", "Mời rời");
            remove.onclick = async () => {
              if (
                !confirm(
                  `Mời ${member.name} rời nhóm? Người này sẽ không mở lại được nội dung và tệp trong nhóm.`,
                )
              )
                return;
              try {
                await manage("remove", { user_id: member.id });
                showInfo();
              } catch (e) {
                error(e.message, "chat-info-error");
              }
            };
            const owner = node("button", "chat-plain", "Giao trưởng nhóm");
            owner.onclick = async () => {
              if (!confirm(`Chuyển quyền trưởng nhóm cho ${member.name}?`))
                return;
              try {
                await manage("owner", { user_id: member.id });
                showInfo();
              } catch (e) {
                error(e.message, "chat-info-error");
              }
            };
            row.append(remove, owner);
          }
          $("chat-info-content").append(row);
        }
        $("chat-info-content").append(
          node(
            "p",
            "chat-muted",
            "Thành viên được thêm mới chỉ thấy nội dung từ lúc tham gia. Người rời nhóm không còn truy cập hội thoại.",
          ),
        );
      } else if (tab === "files") {
        const input = node("input");
        input.type = "search";
        input.placeholder = "Tìm tên ảnh / PDF";
        input.setAttribute("aria-label", "Tìm tệp trong hội thoại");
        input.maxLength = 100;
        const list = node("div"),
          more = node("button", "chat-plain", "Xem thêm tệp");
        more.type = "button";
        let cursor = null,
          fileGeneration = 0;
        const loadFiles = async (reset = true) => {
          const generation = ++fileGeneration;
          more.disabled = true;
          try {
            const params = new URLSearchParams({ q: input.value });
            if (!reset && cursor) params.set("before", cursor);
            const data = await api(roomAPI("files/") + "?" + params);
            if (generation !== fileGeneration) return;
            if (reset) list.replaceChildren();
            for (const file of data.files) {
              const a = node("a", "chat-file", file.name);
              a.href = file.url;
              a.target = "_blank";
              a.rel = "noopener";
              list.append(a);
            }
            cursor = data.next;
            more.hidden = !cursor;
            if (!list.children.length)
              list.append(node("p", "chat-muted", "Không có tệp phù hợp."));
          } catch (e) {
            error(e.message, "chat-info-error");
          } finally {
            more.disabled = false;
          }
        };
        input.oninput = debounce(() => loadFiles(true), 250);
        more.onclick = () => loadFiles(false);
        $("chat-info-content").append(input, list, more);
        await loadFiles(true);
      } else {
        const data = await api(roomAPI("calls/history/"));
        for (const call of data.calls) {
          const row = node(
            "p",
            "chat-muted",
            `${call.mode === "VIDEO" ? "▣ Video" : "☎ Thoại"} · ${new Date(call.at).toLocaleString("vi-VN")} · ${call.status === "ENDED" ? "Đã kết thúc" : call.status === "ACTIVE" ? "Đang gọi" : "Đang mời"}`,
          );
          $("chat-info-content").append(row);
        }
        if (!data.calls.length)
          $("chat-info-content").append(
            node("p", "chat-muted", "Chưa có cuộc gọi."),
          );
      }
    } catch (e) {
      error(e.message, "chat-info-error");
    }
  }
  $("chat-info").onclick = () => showInfo();
  $("chat-members-open").onclick = () => showInfo();
  for (const b of document.querySelectorAll("[data-info-tab]"))
    b.onclick = () => showInfo(b.dataset.infoTab);
  $("chat-rename-save").onclick = async () => {
    try {
      await manage("rename", { title: $("chat-rename").value });
      showInfo();
    } catch (e) {
      error(e.message, "chat-info-error");
    }
  };
  $("chat-add-member").onclick = () => {
    $("chat-info-dialog").close();
    newChat(true);
  };
  $("chat-leave-group").onclick = async () => {
    if (
      !confirm(
        "Rời nhóm này? Bạn sẽ không mở được các tin nhắn và tệp trong nhóm.",
      )
    )
      return;
    try {
      await manage("leave");
      location.assign("/chat/");
    } catch (e) {
      error(e.message, "chat-info-error");
    }
  };
  window.addEventListener("beforeunload", (event) => {
    if (
      $("chat-text").value.trim() ||
      $("chat-files").files.length ||
      state.sticker
    ) {
      event.preventDefault();
      event.returnValue = "";
    }
  });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      loadTimeline(false);
      loadInbox();
    }
  });
  window.addEventListener("chat-resume", () => {
    loadTimeline(false);
    loadInbox();
  });
  loadInbox();
  if (boot.room_id) loadTimeline(true);
})();
