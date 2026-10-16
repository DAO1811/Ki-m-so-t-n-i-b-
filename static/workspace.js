(() => {
  document
    .querySelectorAll("[data-print]")
    .forEach((button) =>
      button.addEventListener("click", () => window.print()),
    );
  const body = document.body;
  try {
    if (localStorage.getItem("warehouse-theme") === "dark")
      body.classList.add("dark");
  } catch {}
  const toggle = document.getElementById("sidebar-toggle");
  const backdrop = document.querySelector(".sidebar-backdrop");
  const small = () => window.matchMedia("(max-width:950px)").matches;
  function closeMenu() {
    body.classList.remove("sidebar-open");
    if (backdrop) backdrop.hidden = true;
    toggle?.setAttribute(
      "aria-expanded",
      String(!small() && !body.classList.contains("sidebar-collapsed")),
    );
  }
  toggle?.addEventListener("click", () => {
    if (small()) {
      body.classList.toggle("sidebar-open");
      backdrop.hidden = !body.classList.contains("sidebar-open");
      toggle.setAttribute("aria-expanded", String(!backdrop.hidden));
    } else {
      body.classList.toggle("sidebar-collapsed");
      toggle.setAttribute(
        "aria-expanded",
        String(!body.classList.contains("sidebar-collapsed")),
      );
    }
  });
  backdrop?.addEventListener("click", closeMenu);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeMenu();
  });
  window.addEventListener("resize", () => {
    if (!small()) closeMenu();
  });
  if (toggle) toggle.setAttribute("aria-expanded", String(!small()));
  document.getElementById("theme-toggle")?.addEventListener("click", () => {
    body.classList.toggle("dark");
    try {
      localStorage.setItem(
        "warehouse-theme",
        body.classList.contains("dark") ? "dark" : "light",
      );
    } catch {}
  });
  document
    .getElementById("refresh-page")
    ?.addEventListener("click", () => window.location.reload());
  document
    .getElementById("global-warehouse")
    ?.addEventListener("change", (e) => e.target.form.requestSubmit());
  document
    .querySelectorAll(".message-dismiss")
    .forEach((button) =>
      button.addEventListener("click", () =>
        button.closest(".message").remove(),
      ),
    );
  document.querySelectorAll("form[data-confirm]").forEach((form) =>
    form.addEventListener("submit", (e) => {
      if (!window.confirm(form.dataset.confirm)) e.preventDefault();
    }),
  );
  document.querySelectorAll("form").forEach((form) =>
    form.addEventListener("submit", (e) => {
      if (e.defaultPrevented || !form.checkValidity()) return;
      setTimeout(
        () =>
          form.querySelectorAll('button[type="submit"]').forEach((button) => {
            button.disabled = true;
          }),
        0,
      );
    }),
  );
})();
