(() => {
  const form = document.querySelector("#loan-return-form");
  if (!form) return;

  const quantities = [...form.querySelectorAll("input[data-available]")];
  const summary = form.querySelector("[data-return-summary]");
  const updateSummary = () => {
    const chosen = quantities.filter((field) => Number(field.value.replace(",", ".")) > 0).length;
    if (summary) {
      summary.textContent = chosen
        ? `${chosen} mã hàng được chọn trả lần này.`
        : "Chưa chọn hàng trả. Nhập số lượng hoặc điền số có thể trả.";
    }
  };
  const setQuantities = (fill) => {
    quantities.forEach((field) => {
      if (field.disabled || field.readOnly) return;
      field.value = fill ? field.dataset.available.replace(",", ".") : "0";
      field.dispatchEvent(new Event("input", { bubbles: true }));
      field.dispatchEvent(new Event("change", { bubbles: true }));
    });
    updateSummary();
  };

  form.querySelector("[data-return-fill]")?.addEventListener("click", () => setQuantities(true));
  form.querySelector("[data-return-clear]")?.addEventListener("click", () => setQuantities(false));
  quantities.forEach((field) => field.addEventListener("input", updateSummary));
  updateSummary();
})();
