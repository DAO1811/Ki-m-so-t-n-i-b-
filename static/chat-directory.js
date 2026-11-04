/* Read-only employee directory and the groups that this account has joined. */
(() => {
  "use strict";
  const app = document.querySelector("[data-chat-app]");
  if (!app || !window.DHDChat) return;
  const { api, node, boot } = window.DHDChat;
  const $ = (id) => document.getElementById(id);
  let view = "messages",
    generation = 0,
    next = null,
    rows = new Map(),
    timer;
  const initials = (name) =>
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(-2)
      .map((part) => part[0])
      .join("")
      .toUpperCase();
  function personCard(person) {
    const card = node("article", "chat-contact-card");
    card.append(node("span", "chat-avatar", initials(person.name)));
    const details = node("div", "chat-contact-details");
    details.append(
      node("h3", "", person.name),
      node("p", "", "@" + person.username),
    );
    if (person.job_title)
      details.append(node("small", "chat-job-title", person.job_title));
    const button = node("button", "chat-contact-message", "Nhắn tin ↗");
    button.type = "button";
    button.setAttribute("aria-label", "Nhắn tin với " + person.name);
    button.onclick = async () => {
      button.disabled = true;
      try {
        const result = await api(
          "/chat/api/rooms/",
          { members: [person.id], group: false },
          "POST",
        );
        location.assign(result.url);
      } catch (e) {
        showError(e.message);
      } finally {
        button.disabled = false;
      }
    };
    card.append(details, button);
    return card;
  }
  function groupCard(group) {
    const card = node("a", "chat-contact-card chat-group-card");
    card.href = group.url;
    card.append(node("span", "chat-avatar", "✦"));
    const details = node("div", "chat-contact-details");
    details.append(
      node("h3", "", group.title),
      node("p", "", `${group.member_count} thành viên`),
    );
    details.append(
      node(
        "small",
        "chat-job-title",
        group.owner_id === boot.user_id
          ? "Bạn là trưởng nhóm"
          : "Bạn đang tham gia",
      ),
    );
    card.append(details, node("span", "chat-contact-message", "Mở nhóm ↗"));
    return card;
  }
  function showError(message = "") {
    $("chat-directory-error").textContent = message;
    $("chat-directory-error").hidden = !message;
  }
  function render() {
    const list = $("chat-directory-list");
    list.replaceChildren();
    for (const row of rows.values())
      list.append(view === "contacts" ? personCard(row) : groupCard(row));
    $("chat-directory-count").textContent =
      `${rows.size}${next !== null ? "+" : ""} ${view === "contacts" ? "đồng nghiệp" : "nhóm đã tham gia"}`;
    if (!rows.size) {
      const empty = node("div", "chat-directory-empty");
      empty.append(
        node("span", "", view === "contacts" ? "☏" : "✦"),
        node("h3", "", "Chưa có kết quả phù hợp"),
        node(
          "p",
          "chat-muted",
          view === "contacts"
            ? "Thử tên không dấu, tài khoản hoặc chức vụ. Đồng nghiệp cần được admin cấp quyền chat."
            : "Chỉ hiển thị nhóm bạn đang tham gia. Bạn có thể tạo nhóm mới nếu được cấp quyền.",
        ),
      );
      list.append(empty);
    }
    $("chat-directory-more").hidden = next === null;
  }
  async function load(reset = true) {
    if (view === "messages") return;
    const current = ++generation,
      mode = view;
    const params = new URLSearchParams({ q: $("chat-directory-search").value });
    if (mode === "contacts")
      params.set("field", $("chat-directory-field").value);
    if (!reset && next !== null) params.set("offset", next);
    $("chat-directory-more").disabled = true;
    showError();
    if (reset) {
      next = null;
      $("chat-directory-more").hidden = true;
      rows.clear();
      $("chat-directory-list").replaceChildren(
        node("p", "chat-muted", "Đang tải…"),
      );
      $("chat-directory-count").textContent = "Đang tìm…";
    }
    try {
      const data = await api(
        `/chat/api/${mode === "contacts" ? "people" : "groups"}/?` + params,
      );
      if (generation !== current || view !== mode) return;
      for (const row of data[mode === "contacts" ? "people" : "groups"])
        rows.set(row.id, row);
      next = data.next_offset;
      render();
    } catch (e) {
      if (generation === current) {
        showError(e.message);
        $("chat-directory-count").textContent = "Chưa tải được danh sách";
      }
    } finally {
      if (generation === current) $("chat-directory-more").disabled = false;
    }
  }
  function open(mode, showThread = true) {
    view = mode;
    generation++;
    clearTimeout(timer);
    const directory = mode !== "messages";
    if (directory && !app.classList.contains("is-directory"))
      window.dispatchEvent(new Event("chat-view-directory"));
    app.classList.toggle("is-directory", directory);
    app.classList.toggle(
      "is-room-open",
      directory || (showThread && Boolean(boot.room_id)),
    );
    $("chat-directory").hidden = !directory;
    for (const id of [
      "chat-inbox-search-label",
      "chat-inbox-filters",
      "chat-room-list",
    ])
      $(id).hidden = directory;
    $("chat-directory-shortcut").hidden = !directory;
    for (const button of document.querySelectorAll("[data-chat-view]")) {
      const active = button.dataset.chatView === mode;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
    }
    if (!directory) {
      if (showThread) window.dispatchEvent(new Event("chat-view-messages"));
      return;
    }
    const contacts = mode === "contacts";
    $("chat-directory-title").textContent = contacts
      ? "Danh bạ công ty"
      : "Nhóm của tôi";
    $("chat-directory-shortcut-title").textContent = contacts
      ? "Đồng nghiệp công ty"
      : "Nhóm đang tham gia";
    $("chat-directory-description").textContent = contacts
      ? "Đồng đội luôn ở đây. Tìm đúng người, trao đổi đúng việc."
      : "Các nhóm bạn đang tham gia, cùng một nơi dễ tìm.";
    $("chat-directory-search").placeholder = contacts
      ? "Tìm tên, tài khoản hoặc chức vụ…"
      : "Tìm tên nhóm…";
    $("chat-directory-search").setAttribute(
      "aria-label",
      contacts ? "Tìm trong danh bạ" : "Tìm nhóm đã tham gia",
    );
    $("chat-directory-field").hidden = !contacts;
    $("chat-directory-search").value = "";
    $("chat-directory-field").value = "all";
    next = null;
    load();
  }
  for (const button of document.querySelectorAll("[data-chat-view]"))
    button.onclick = () => open(button.dataset.chatView);
  for (const button of document.querySelectorAll("[data-new-group]"))
    button.onclick = () => window.DHDChat.openCreator();
  $("chat-directory-back").onclick = () => {
    open("messages", false);
  };
  $("chat-directory-search").oninput = () => {
    generation++;
    clearTimeout(timer);
    $("chat-directory-more").hidden = true;
    $("chat-directory-list").replaceChildren(
      node("p", "chat-muted", "Đang tìm…"),
    );
    timer = setTimeout(() => load(), 250);
  };
  $("chat-directory-field").onchange = () => load();
  $("chat-directory-more").onclick = () => load(false);
})();
