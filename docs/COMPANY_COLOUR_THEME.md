# Nhận diện vàng kim và bạc

`static/company-theme.css` được nạp sau CSS bố cục trên các trang đã đăng nhập. Các biến màu giữ nguyên bố cục, URL, quyền, dữ liệu và nghiệp vụ. Các tên biến `--green*` cũ được dùng làm bí danh cho màu nhận diện để các biểu mẫu cũ nhận bộ màu mới; trạng thái thành công có bộ `--success*` riêng.

- Sáng: nền bạc sáng, panel trắng, menu than đậm, điểm nhấn vàng.
- Tối: nền than, panel graphite, chữ bạc, điểm nhấn vàng champagne.
- Nút chính: vàng, chữ đậm; nút hủy/nguy hiểm đỏ; chuyển kho màu hổ phách.
- Phiếu hoàn tất, số dương và dòng Excel hợp lệ vẫn dùng xanh trạng thái. Cảnh báo/lỗi vẫn có nhãn và màu riêng, không biến thành màu nhận diện.
- Biểu đồ: nhập vàng, xuất bạc, kèm chú giải và giá trị. SVG dùng biến CSS để thay màu ngay khi chuyển chế độ.
- Giữ lựa chọn sáng/tối cũ trong trình duyệt. Không đổi mặc định hoặc bắt buộc người dùng đổi chế độ.
- CSS in dùng nền trắng, chữ đậm cho cả khi đang xem chế độ tối.

Màn hình đăng nhập vẫn dùng stylesheet riêng `login.css`, đã phối cùng vàng kim/bạc. Không nạp stylesheet công ty vào trang đăng nhập hoặc sửa xác thực.
