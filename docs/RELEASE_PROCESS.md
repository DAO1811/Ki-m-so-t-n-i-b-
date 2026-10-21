# Phát triển, kiểm tra và phát hành

Cập nhật ngày 21/10/2026. Mã được quản lý trên GitHub; bản thật chạy tại https://kiemsoatnoibolemon.onrender.com. `/healthz/` là nguồn xác định commit đang chạy; tên nhánh, thông báo commit hoặc màu giao diện không thay thế kiểm tra release.

## Trong lúc phát triển

1. Tạo nhánh riêng từ main, thực hiện thay đổi theo phạm vi đã được chốt.
2. Chạy bằng database và tài khoản thử. Không dùng Neon production để tạo mẫu, chạy test hoặc diễn tập migration.
3. Với CSS, sửa `assets/styles/`, chạy `python scripts/build_styles.py` và commit bundle đồng bộ. Login có stylesheet riêng.
4. Chạy lint, check Django, kiểm tra migration, PostgreSQL test và collectstatic theo README. Kiểm tra trình duyệt cho luồng bị ảnh hưởng; dùng ảnh trước–sau khi refactor giao diện.
5. Kiểm tra diff: không có bí mật, database/file thử, thay đổi migration cũ hoặc sửa nghiệp vụ ngoài phạm vi.

Bản đang dùng tiếp tục chạy trong thời gian chuẩn bị nhánh. Không đổi môi trường hosting hoặc triển khai nhánh chưa kiểm tra lên dịch vụ thật.

## GitHub Actions và điều kiện merge

Workflow `.github/workflows/ci.yml` chạy trên push/PR, với PostgreSQL tạm và thông tin thử riêng, không dùng secret production. Nó kiểm tra:

- Ruff và cú pháp JavaScript.
- Bundle CSS đồng bộ nguồn.
- Cấu hình Django và thiếu migration.
- Toàn bộ test trên PostgreSQL.
- Thu gom static bằng cấu hình ứng dụng.

Xem kết quả từng lần chạy tại tab Actions. Để **bắt buộc** các bước đạt trước khi đổi main, chủ repository cần bật Rulesets/branch protection và yêu cầu job `checks` của workflow `Application checks`. Tên check có thể xem trực tiếp ở lần chạy GitHub đầu tiên. Có file workflow chưa có nghĩa Rulesets đã được bật. Không yêu cầu thêm reviewer khi dự án chỉ có một người quản trị, trừ khi chủ dự án muốn quy tắc đó.

Render hiện sử dụng triển khai từ main. Nếu muốn Render chờ CI, cần chọn chế độ **After CI Checks Pass** trong thiết lập Auto-Deploy của dịch vụ. File mã nguồn không xác nhận được thiết lập hiện tại trên tài khoản hosting. Không hứa CI tự chặn phát hành khi hai cấu hình bắt buộc này chưa được kiểm tra.

## Chờ chủ phần mềm duyệt bản chạy thử

Chủ phần mềm đã thay đổi yêu cầu ngày 21/10/2026: phải xem bản thử trong VS Code trước. Các yêu cầu tự cập nhật trước đây không còn là quyền đưa mọi bản sửa mới lên production. Dùng nhánh `preview/*` và [môi trường thử riêng](PREVIEW_IN_VSCODE.md); ghi commit đã xem. Chỉ sau khi người dùng đồng ý bản cụ thể mới merge/push main hoặc gọi deploy. Chưa bật branch protection không có nghĩa được bỏ qua bước này.

## Khi bản thử đã được đồng ý phát hành

1. Kiểm tra thay đổi mới trên main, giữ các chỉnh sửa của người dùng và giải quyết xung đột nếu có.
2. Xem các kiểm tra và bằng chứng của đúng commit cần đưa lên. Kiểm thử ở máy phát triển và CI là hai lần chạy riêng; ghi rõ lần nào đã xác minh.
3. Với schema mới, chuẩn bị backup/khôi phục và diễn tập bằng dữ liệu thử. `safe_migrate` giữ snapshot trong cùng database, không thay backup độc lập. Rollback code không tự rollback schema.
4. Đưa bản đã kiểm tra lên main theo quyền phát hành đã được cấp. Khi có migration, có thể có khoảng khởi động/chuyển đổi; không hứa không gián đoạn chỉ từ việc thay code.
5. Chờ `/healthz/` báo `status=ok` với đúng SHA; kiểm tra snapshot sẵn sàng, trang đăng nhập, route bảo vệ, static và các luồng bị ảnh hưởng.
6. Chỉ thông báo đã cập nhật sau khi xác nhận bản thật. Nếu chỉ xác minh bằng tài khoản thử, không ghi rằng đã kiểm tra dữ liệu công ty thực tế.

## Khôi phục và giới hạn

- Lưu commit phát hành, báo cáo kiểm tra và thông tin snapshot để đối chiếu.
- Không xóa snapshot hoặc dữ liệu thật để chữa lỗi giao diện/cấu trúc file.
- Lỗi không có migration có thể xử lý bằng đưa bản code đã biết hoạt động trở lại và xác minh health; nếu có schema mới phải theo kế hoạch phục hồi riêng.
- Tài liệu `AUTOMATED_RELEASE_SNAPSHOT.md` mô tả cơ chế snapshot. Các báo cáo phát hành cũ được giữ làm lịch sử, không phải mô tả phiên bản hiện hành.
