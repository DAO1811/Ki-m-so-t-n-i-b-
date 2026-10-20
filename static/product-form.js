(() => {
  const auto = document.getElementById('id_qr_auto');
  const code = document.getElementById('id_qr_code');
  const help = document.getElementById('qr-code-help');
  if (!auto || !code || auto.disabled || code.disabled) return;
  function update() {
    code.readOnly = auto.checked;
    code.required = !auto.checked;
    code.placeholder = auto.checked ? 'Mã QR được tạo khi lưu hàng hóa' : 'Ví dụ: LEMON-TS-0001 hoặc nội dung QR sẵn có';
    help.textContent = auto.checked ? 'Phần mềm tạo mã duy nhất khi lưu. QR sẽ gắn với hàng hóa suốt vòng đời.' : 'Nhập đúng nội dung mã QR có sẵn hoặc tự đặt mã duy nhất. Không đổi mã sau khi lưu.';
  }
  auto.addEventListener('change', update);
  update();
})();
