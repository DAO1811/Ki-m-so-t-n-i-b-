# Đưa ứng dụng lên web và cơ sở dữ liệu trực tuyến

Ứng dụng đã có Dockerfile để triển khai trên dịch vụ chạy Docker và kết nối PostgreSQL quản lý trực tuyến. Chưa có tài khoản dịch vụ, tên miền hoặc cơ sở dữ liệu online được cấp cho dự án. Chạy thành công trong môi trường phát triển không đồng nghĩa đã có website công khai.

## Các bước thực hiện cùng chủ dự án

1. Chủ dự án chọn hoặc tạo tài khoản dịch vụ hosting chạy Docker và PostgreSQL (ví dụ Render, Railway hoặc một máy chủ do đơn vị quản lý). Nếu có gói trả phí, chủ dự án tự xác nhận gói. Không tự đăng ký dịch vụ hoặc thu phí.
2. Đưa mã nguồn đã được duyệt vào GitHub, kết nối kho với dịch vụ hosting. Chưa có thao tác push tự động trong phiên xây dựng này.
3. Tạo PostgreSQL, bật sao lưu tự động phù hợp; lấy URL kết nối từ dịch vụ. Nhập trực tiếp vào biến `DATABASE_URL` trong bảng cấu hình hosting, không gửi mật khẩu qua chat. Ưu tiên URL nội bộ nếu app và DB cùng mạng; URL công khai phải bật `sslmode=require` hoặc cấu hình TLS chặt hơn theo nhà cung cấp.
4. Cấu hình `DEBUG=0`, `SECRET_KEY` ngẫu nhiên dài, `ALLOWED_HOSTS` là tên miền ứng dụng, `CSRF_TRUSTED_ORIGINS=https://tên-miền`. Tệp `.env.example` chỉ là tài liệu; chương trình không tự nạp tệp `.env`.
5. Build từ Dockerfile. Lệnh khởi động thực hiện migrate, tạo vai trò nếu chưa có và chạy Gunicorn. Khi có nhiều instance, chạy migrate một lần trong release job trước khi scale.
6. Tại console của hosting: `python manage.py createsuperuser` để tự nhập mật khẩu quản trị. Nếu gói Free không có console, nhập `INITIAL_ADMIN_USERNAME` và `INITIAL_ADMIN_PASSWORD` vào biến bảo mật của hosting; `bootstrap_admin` tạo tài khoản đúng một lần và không đổi mật khẩu tài khoản đã có. Xóa biến mật khẩu sau khi đăng nhập. Không ghi mật khẩu trong mã nguồn, README, ảnh hoặc log.
7. Đăng nhập, tạo các kho, tạo nhân viên, phân vai trò, gán phạm vi kho. Chỉ quản trị viên được quản lý người dùng và quyền. Không đặt `is_staff` hay `is_superuser` cho nhân viên thông thường.
8. Nhập thử bằng hai tài khoản khác nhau (người lập / người duyệt); kiểm tra nhập, xuất, chuyển, kiểm kê và báo cáo. Không dùng dữ liệu minh họa làm tồn thực.
9. Kiểm tra HTTPS, backup và khôi phục từ backup trước khi dùng dữ liệu thật. Mật khẩu PostgreSQL và SECRET_KEY được quản lý trong hosting; không đưa vào Git. Cần giới hạn thử đăng nhập tại proxy/WAF hoặc bổ sung rate limiting trước khi công khai cho nhiều người.

## Nâng cấp sau này

Sao lưu DB → thử thay đổi trong môi trường thử nghiệm → chạy test PostgreSQL → migrate → triển khai → kiểm tra quy trình nhập/xuất. Không xóa DB để nâng cấp. Không dùng `demo_data` trên dữ liệu thật. Cấu hình thời gian lưu backup và trách nhiệm khôi phục với chủ dự án.

## Phương án miễn phí đã chuẩn bị

Xem [Render Free + Neon Free](FREE_HOSTING.md). Có `render.yaml`, `build.sh`, `start.sh`, cấu hình hostname tự động của Render và bootstrap admin không cần console. Production bắt buộc PostgreSQL để không vô tình lưu DB trong ổ tạm. Chưa triển khai vào tài khoản nhà cung cấp; điều kiện gói Free cần kiểm tra trong tài khoản của chủ dự án.
