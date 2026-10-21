# Kiểm tra đợt chuẩn hóa cấu trúc — 21/10/2026

## Phạm vi

Tách màn hình kho thành package `inventory/views/`; đưa màn hình tài khoản sang `core`; tạo app/URL độc lập cho hai trang chuẩn bị Quy trình và Nhân sự. Hợp nhất palette giao diện vào nguồn CSS có tổ chức, ghép bundle có kiểm tra đồng bộ. Thêm cấu hình lint, dependency phát triển, GitHub Actions và hướng dẫn tiếp nhận.

Không thêm nghiệp vụ quản lý nhân sự/quy trình, không thay schema, model, URL hoặc quy tắc nhập/xuất/duyệt. Không sửa migration cũ.

## Bằng chứng ở môi trường thử

- 264 kiểm thử PostgreSQL đạt, không bỏ qua. Có kiểm tra namespace mới mặc định từ chối chức năng chưa cấp quyền và giữ các URL hiện có.
- 35 hàm được di chuyển giữ các câu lệnh và decorator cũ; thay đổi tổ chức import và tên biến vòng lặp, không đổi phép tính hoặc điều kiện.
- 16 ảnh màn hình trước–sau ở sáng/tối đối chiếu trùng từng pixel sau khi xử lý một khác biệt cascade của bước lập phiếu. Nội dung và các thuộc tính style chính được đối chiếu tự động.
- Kiểm tra trình duyệt trên tổng quan, danh mục, kho, phiếu, mượn trả, kiểm kê, duyệt, tài khoản, báo cáo, Excel, tồn/thẻ kho, trường bổ sung, mật khẩu, Drive và hai trang chuẩn bị ở cả hai theme; kiểm tra chiều rộng 320–1440px. Không có lỗi JavaScript hoặc HTTP lỗi ngoài favicon.
- Ruff đạt; không thiếu migration; bundle CSS đồng bộ nguồn; cấu hình Compose và cấu trúc workflow được kiểm tra.
- Image Docker được dựng bằng cùng Dockerfile, chỉ thay bước tải pip bằng wheelhouse ngoại tuyến của đúng dependency. Container dùng PostgreSQL mới hoàn toàn ở máy thử, `DEBUG=0`; khởi động/migration, health, static và yêu cầu đăng nhập đạt. Không dùng database công ty.

Báo cáo và ảnh thử của phiên làm việc ở `/workspace/scratch/platform-refactor/`; log PostgreSQL ở `/workspace/platform-refactor-full-tests.log`. Đây là dữ liệu minh họa, không phải hiện trạng kho công ty.

## CI và phát hành

Workflow chạy trên push/PR. Kết quả GitHub thực tế phải xem ở tab Actions của đúng commit; kiểm tra tại máy thử không được ghi thành kết quả của GitHub. Việc bắt buộc CI trước merge/triển khai thuộc cấu hình GitHub Rulesets và Render, được mô tả riêng tại `RELEASE_PROCESS.md`.

Khi đưa lên bản thật, đối chiếu SHA tại `/healthz/` và static của đúng release. Kiểm tra nghiệp vụ có đăng nhập được thực hiện bằng tài khoản thử riêng; không coi đó là xác minh dữ liệu công ty thực tế. Snapshot cùng database không thay backup độc lập.
