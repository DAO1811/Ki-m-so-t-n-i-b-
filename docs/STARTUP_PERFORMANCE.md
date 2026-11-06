# Giảm thời gian khởi động ứng dụng

Phạm vi ngày 06/11/2026: khởi động máy chủ, không sửa giao diện đăng nhập,
nghiệp vụ, phân quyền, migration hoặc cấu hình dịch vụ đang chạy.

## Nguyên nhân và giới hạn

Render Free ngủ sau 15 phút không có lưu lượng vào. Lần truy cập tiếp theo đánh
thức dịch vụ và Render có thể hiện trang chờ khoảng một phút trước khi ứng dụng
sẵn sàng. Mã Django không điều khiển được thời gian cấp lại máy chủ này.

Thay đổi này giảm phần thời gian ứng dụng tự chuẩn bị sau khi môi trường chạy đã
sẵn sàng. Nó không loại bỏ chế độ ngủ, không thêm ping giữ máy chủ thức, không
nâng gói trả phí hoặc chuyển hosting.

Nguồn kiểm tra ngày 06/11/2026: <https://render.com/docs/free>.

## Thay đổi có giới hạn

- Docker và `start.sh` gọi `python manage.py prepare_runtime` thay cho ba tiến
  trình Django riêng. Lệnh mới vẫn gọi tuần tự `safe_migrate`, `setup_roles`,
  `bootstrap_admin`; giữ nguyên nội dung các lệnh con và dừng khi có lỗi.
- Chỉ nạp Django/kiểm tra cấu hình một lần cho giai đoạn chuẩn bị. Các lệnh con
  tái sử dụng kết nối ORM của cùng tiến trình khi có thể.
- Xác minh snapshot gửi các truy vấn đếm chính xác theo nhóm tối đa 32 bảng qua
  psycopg pipeline. Đọc kết quả sau khi đồng bộ nhóm; vẫn kiểm tra mọi mục trong
  manifest, giữ nguyên từng câu SQL và thời hạn của từng câu lệnh.
- Giữ khóa triển khai, transaction snapshot nhất quán và bản chụp gốc qua các lần
  khởi động. Không dùng dấu hiệu phiên bản để bỏ qua xác minh.
- Thêm nhật ký tên giai đoạn và số giây hoàn tất. Lỗi database vẫn đi qua thông
  báo đã làm sạch của `safe_migrate`; không ghi môi trường, token hay dữ liệu.
- Giữ nguyên tham số Gunicorn: Docker có 2 worker, timeout 120 giây; `start.sh`
  giữ `WEB_CONCURRENCY`, `PORT` và timeout mặc định hiện có.

## Kiểm chứng

Đo trước–sau phải dùng cùng database PostgreSQL thử, snapshot và dữ liệu tổng
hợp; đảo thứ tự phiên bản giữa các lượt. Đo từ khi chạy `start.sh` tới khi HTTP
trả về biểu mẫu đăng nhập thật, rồi xác nhận `/healthz/` trả `ok`.

Các kiểm tra bảo vệ gồm:

- Khởi tạo mới, khởi động lặp lại, giữ mật khẩu admin, nhóm/quyền tùy chỉnh và tồn.
- Không tự nâng tài khoản nhân viên thành admin qua cấu hình bootstrap.
- Mỗi giai đoạn thất bại đều ngăn chạy các giai đoạn tiếp theo và Gunicorn.
- Bản chụp thiếu/hỏng, lỗi giữa pipeline và triển khai trùng đều chặn migration.
- Đếm đủ qua ranh giới nhóm; quote tên bảng; không ghi thông tin kết nối khi lỗi.
- Kiểm thử snapshot nhất quán, rollback, quyền riêng tư và toàn bộ bộ kiểm thử cũ.

Số đo máy phát triển chỉ mô tả phần khởi động ứng dụng. Không được diễn giải
thành thời gian chờ trên Render hoặc bảo đảm hoạt động tức thì trên gói Free.

## Xem thử và phát hành

Chạy đúng commit trên database/tài khoản/tệp thử riêng, không nối Drive, email
hoặc mô hình AI thật để minh họa. Chủ phần mềm xem và duyệt đúng phiên bản trước
khi phát hành theo `AGENTS.md`; kết quả test không tự cấp quyền triển khai.

Sau khi được duyệt và triển khai, kiểm tra nhật ký `startup phase=...`, phiên bản
trả về từ `/healthz/`, đăng nhập và các route cần quyền. So sánh thời gian khởi
động từ nhật ký Render với số đo thử; không dùng thời gian truy cập lúc máy chủ
đã thức để tuyên bố đã xử lý cold start.

Không có migration mới. Nếu cần quay lại, khôi phục commit mã nguồn đã biết chạy
được; không xóa database, snapshot hoặc đổi mật khẩu/quyền để xử lý thời gian chờ.
