# Bản test riêng trên Render

Nhánh `preview/dhd-live-test` có cấu hình riêng, không hợp nhất `render.yaml` của nhánh này vào main. Website production tiếp tục theo main. Bản test tự tạo PostgreSQL mới, không sử dụng kết nối Neon production, không sao chép dữ liệu thật. Tắt tự động deploy để các lần sửa mã không ngắt phiên thử.

1. Mở https://render.com/deploy?repo=https%3A%2F%2Fgithub.com%2FDAO1811%2FKi-m-so-t-n-i-b-%2Ftree%2Fpreview%2Fdhd-live-test
2. Kiểm tra chỉ có web `dhd-ksnb-test` và database `dhd-ksnb-test-db`, cả hai gói Free. Không chọn dịch vụ production hiện có.
3. Điền `INITIAL_ADMIN_PASSWORD` bằng mật khẩu riêng cho bản test. Tài khoản là `admin_test`. Không dán token GitHub hoặc mật khẩu production vào đây.
4. Triển khai Blueprint. Khi web báo Live, mở URL Render cấp và đăng nhập.
5. Bản mới ban đầu trống: thêm kho, hàng hóa và nhân viên; tạo phiếu nhập bằng tài khoản nhân viên, sau đó duyệt bằng tài khoản quản lý của kho. Không tự duyệt phiếu do chính mình lập.

Render Free Postgres hết hạn sau 30 ngày; bản này chỉ để thử. Các web Free cùng workspace chia sẻ 750 giờ/tháng, vì vậy tạm dừng bản test khi không sử dụng. Nếu workspace có nhiều dịch vụ Free đang chạy, cần kiểm tra phần Usage trước khi triển khai để giữ đủ giờ cho production. Không nâng gói trả phí khi chưa được chủ dự án yêu cầu.

Nguồn: https://render.com/docs/free và https://render.com/docs/deploy-to-render .

Để phát hành bản chính thức, dùng nhánh `feature/modern-warehouse-workspace` theo `RELEASE_PROCESS.md`; không dùng trực tiếp nhánh triển khai test.
