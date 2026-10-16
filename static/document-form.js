(() => {
  const kind = document.getElementById('id_kind');
  if (!kind) return;
  const source = document.getElementById('id_source');
  const destination = document.getElementById('id_destination');
  const loan = document.getElementById('id_loan');
  const help = document.getElementById('kind-help');
  const descriptions = {
    IN: 'Nhập hàng mua về: chọn kho nhận, nhập số lượng và đơn giá. Quản lý kho nhận xác nhận mới tăng tồn.',
    OUT: 'Xuất hàng: chỉ dùng tồn khả dụng. Người được admin chỉ định tại kho xuất sẽ duyệt phiếu.',
    TRANSFER: 'Chuyển chính thức: duyệt xuất → hàng đang chuyển → kho nhận xác nhận. Hai kho phải khác nhau.',
    LOAN: 'Hàng cho mượn treo ở sổ trung gian. Khi bên mượn nhận, chỉ tạo tồn mượn tạm bị khóa, không được xuất hoặc cho mượn tiếp.',
    RETURN: 'Chọn lệnh mượn gốc để tự điền chiều trả. Chỉ trả từ tồn mượn tạm; được trả từng phần, không được trả vượt số còn nợ.',
    COUNT: 'Nhập số thực đếm của tồn thường (không gồm hàng mượn tạm), không nhập số chênh lệch. Bắt buộc ghi lý do.',
    ADJUST: 'Nhập số chênh lệch: số dương để tăng, số âm để giảm. Bắt buộc lý do, không được làm âm tồn.'
  };
  function toggle(name, visible) {
    const wrapper = document.querySelector(`[data-doc-field="${name}"]`);
    if (!wrapper) return;
    wrapper.hidden = !visible;
    wrapper.querySelectorAll('input,select,textarea').forEach(control => {
      control.disabled = !visible;
      if (!visible) control.value = '';
    });
  }
  function update() {
    const type = kind.value;
    toggle('source', ['OUT','TRANSFER','LOAN','RETURN'].includes(type));
    toggle('destination', type !== 'OUT');
    toggle('loan', type === 'RETURN');
    help.textContent = descriptions[type] || '';
    document.querySelectorAll('input[name$="-unit_price"]').forEach(input => {
      const visible = ['IN','COUNT','ADJUST'].includes(type);
      input.closest('.field').hidden = !visible;
      input.disabled = !visible;
      input.required = type === 'IN';
      // Blank optional rows must stay optional, including their price fields.
      input.required = false;
      input.placeholder = type === 'IN' ? 'Đơn giá VNĐ' : 'Để trống: giá bình quân';
    });
    document.querySelectorAll('input[name$="-quantity"]').forEach(input => {
      input.step = '0.001';
      input.min = type === 'ADJUST' ? '' : (type === 'COUNT' ? '0' : '0.001');
      input.placeholder = type === 'COUNT' ? 'Số thực đếm' : (type === 'ADJUST' ? 'Ví dụ: −2 hoặc 5' : 'Số lượng');
    });
    document.getElementById('id_note').required = ['COUNT','ADJUST'].includes(type);
  }
  kind.addEventListener('change',update);
  document.getElementById('add-line').addEventListener('click',update);
  loan.addEventListener('change',()=>{
    const data=JSON.parse(document.getElementById('loan-data').textContent);
    const original=data.find(item=>String(item.id)===loan.value);
    if(original){source.value=String(original.destination_id);destination.value=String(original.source_id);}
  });
  update();
})();
