# Nhập hàng vào nhiều kho từ Excel

Vào **Nhập kho → Lập phiếu nhập bằng Excel → Tải mẫu nhập kho theo kho**. Đường dẫn tải `/import/receipt/template/`, tên file **mau-nhap-kho-theo-kho.xlsx**, riêng với mẫu tạo mã hàng tại Danh mục hàng hóa.

Mẫu nhận hàng đã có trong danh mục, gồm 7 cột: `ma_hang`, `so_luong`, `don_gia`, `sl_chung_tu`, `sl_khong_nhan`, `ly_do`, **`ma_kho` (cột G)**. Trang **Danh sach kho** chỉ liệt kê mã/tên kho trong phạm vi được cấp quyền; trang **Huong dan** giải thích cách nhập.

- Có `ma_kho`: dòng nhận vào đúng kho đó. Không cần chọn kho chung khi mọi dòng đều đã có mã kho.
- `ma_kho` trống: dùng **Kho nhận chung** trên màn hình; thiếu cả hai sẽ báo lỗi.
- Cùng mã hàng có thể có nhiều dòng khác kho, với số lượng và đơn giá riêng. Không lặp cùng mã ở cùng kho, kể cả một dòng dùng kho chung và dòng kia ghi mã kho tương ứng.
- `so_luong` là số thực nhận đạt yêu cầu. Các trường chứng từ/không nhận/lý do giữ quy tắc thiếu/hỏng hiện có; chỉ thực nhận được cộng tồn. Đơn giá miễn phí phải ghi 0.
- Mẫu mới tối đa 500 dòng, 5 MB. Mỗi kho tự tạo phiếu nhập riêng, tối đa 50 mã/phiếu. Mẫu cũ 3/6 cột vẫn dùng với kho chung, tối đa 50 mã.

Xem trước hiển thị từng kho nhận, từng dòng, giá trị và số phiếu dự kiến. Toàn bộ phiếu được tạo trong một giao dịch; lỗi ở phiếu sau hoàn tác cả phiếu trước. Kết quả có danh sách phiếu của lượt nhập, lọc theo phạm vi quyền và có phân trang. Một phiếu thì mở thẳng chi tiết.

Chỉ tạo phiếu **DRAFT chờ duyệt**, không tạo sản phẩm hoặc đổi QR, không cộng tồn trực tiếp. Cấp duyệt, cảnh báo admin tự duyệt, khóa kiểm kê và ngày hôm nay vẫn áp dụng. Ảnh/hóa đơn bổ sung trên phiếu theo cơ chế lưu trữ hiện có.

Xem trước gắn người dùng, khóa lượt nhập, hạn 30 phút và ngày nghiệp vụ; khi xác nhận kiểm tra lại quyền tạo phiếu, phạm vi kho, ID/mã kho, mã/đơn vị sản phẩm. Phiếu dùng khóa nhập duy nhất, xác nhận lại không tạo thêm. Không tin số lượng/kho giả gửi kèm nút xác nhận từ trình duyệt.

Kiểm chứng: **258/258 kiểm thử PostgreSQL đạt**, gồm 12 ca mới cho nhập theo kho và các ca nhập 3/6 cột, thiếu/hỏng, cấp duyệt đã có. Trình duyệt dùng dữ liệu cách ly kiểm tra đúng nút tải, tên file và cột G thực tế; nhập một mã đã có vào hai kho; không thêm mã/đổi QR; không cộng tồn trước duyệt; duyệt xong đúng số lượng/giá trị thực nhận. Kiểm tra bố cục 320–1440px. Không tạo phiếu thử trong dữ liệu công ty. Không thêm migration hoặc dependency.
