# Nhận diện vàng kim và bạc

Nguồn màu nằm trong `assets/styles/foundation.css`; các thành phần nhận diện nằm trong các file nguồn tương ứng tại `assets/styles/`. `scripts/build_styles.py` ghép thành `static/app.css`, được nạp chung trên các trang đã đăng nhập. Dùng `--accent*` cho nhận diện và `--success*` cho thành công; không dùng tên biến màu xanh cũ để chỉ màu vàng. Không còn lớp `company-theme.css` ghi đè riêng. Khi chỉnh CSS, sửa nguồn rồi tạo lại bundle.

- Sáng: nền bạc sáng, panel trắng, menu than đậm, điểm nhấn vàng.
- Tối: nền than, panel graphite, chữ bạc, điểm nhấn vàng champagne.
- Nút chính: vàng, chữ đậm; nút hủy/nguy hiểm đỏ; chuyển kho màu hổ phách.
- Phiếu hoàn tất, số dương và dòng Excel hợp lệ vẫn dùng xanh trạng thái. Cảnh báo/lỗi vẫn có nhãn và màu riêng, không biến thành màu nhận diện.
- Biểu đồ: nhập vàng, xuất bạc, kèm chú giải và giá trị. SVG dùng biến CSS để thay màu ngay khi chuyển chế độ.
- Giữ lựa chọn sáng/tối cũ trong trình duyệt. Không đổi mặc định hoặc bắt buộc người dùng đổi chế độ.
- CSS in dùng nền trắng, chữ đậm cho cả khi đang xem chế độ tối.

Màn hình đăng nhập vẫn dùng stylesheet riêng `login.css`, đã phối cùng vàng kim/bạc. Không nạp stylesheet công ty vào trang đăng nhập hoặc sửa xác thực.
