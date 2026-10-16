# DHD — Quản lý kho & kiểm soát nội bộ

Ứng dụng web tiếng Việt để quản lý nhiều kho, số lượng và giá trị hàng hóa. Django 5.2 LTS, PostgreSQL cho môi trường online; giao diện dùng HTML, CSS và JavaScript nội bộ, không phụ thuộc CDN.

**Bản cải tiến được chủ dự án yêu cầu phát hành ngày 16/10/2026.** Website chính triển khai từ nhánh `main`; phát triển tiếp ở nhánh riêng và chỉ phát hành khi chủ dự án yêu cầu.

![Tổng quan mới — dữ liệu minh họa](docs/preview/tong-quan-desktop.png)

## Quy trình sử dụng

- Menu chia thành Tổng quan, Khai báo, Nghiệp vụ, Báo cáo và Tiện ích.
- Nhập, xuất, chuyển, kiểm kê và điều chỉnh có biểu mẫu riêng; tự điền kho khi xác định được phạm vi làm việc.
- Một dòng hàng ban đầu, tìm mã hoặc tên không dấu, thêm/xóa dòng, tính tạm tiền, hiển thị tồn khả dụng.
- Nhập phiếu từ Excel: tải mẫu → kiểm tra → xem trước → tạo phiếu chờ duyệt.
- Hàng chờ duyệt đúng kho, đúng người, đúng giai đoạn; người lập không tự duyệt. Trạng thái và người được phân công hiển thị trong chi tiết phiếu.
- Luân chuyển chính thức có bước chuyển đi và xác nhận nhận hàng. Mượn dùng sổ trung gian bị khóa, trả từng phần theo lệnh gốc và giữ nguyên giá trị mượn.
- Thiếu tồn được chặn khi tạo phiếu và được kiểm tra lại trong transaction khi duyệt. Khóa PostgreSQL chặn xuất quá tồn khi nhiều người thao tác.
- Bộ lọc kho thống nhất giữa các màn hình. Tổng quan có khoảng ngày và biểu đồ dữ liệu thực; các đơn vị tính khác nhau không bị cộng chung.
- Quản lý kho, nhân viên, vai trò và trường bổ sung trong giao diện chính. Danh mục/phiếu có tìm kiếm và phân trang.
- Quản trị viên quy định tên đăng nhập. Mật khẩu do người dùng tự chọn theo yêu cầu chủ dự án, không bắt buộc độ dài hoặc tổ hợp ký tự; không cho mật khẩu rỗng. Người dùng tự đổi mật khẩu sau khi xác nhận mật khẩu hiện tại. Mật khẩu được băm bằng Django.
- Hỗ trợ điện thoại, menu thu gọn và giao diện sáng/tối.

## Phát triển cục bộ

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py setup_roles
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Mỗi task cloud đã được tách biệt; dùng checkout hiện có, không tạo worktree nếu không được yêu cầu. Trong môi trường đang làm việc, Python environment là `/workspace/.venv-inventory`. Không dùng dữ liệu mẫu hoặc URL DB production để chạy thử. `demo_data` chỉ hỗ trợ DB trống sau khi tạo quản trị viên.

## Kiểm tra

```sh
.venv/bin/python manage.py test -v 2
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
```

Đặt `DATABASE_URL` trỏ PostgreSQL **thử nghiệm** để chạy cả kiểm thử đồng thời; tài khoản DB test cần quyền tạo DB test. SQLite bỏ qua bài kiểm thử khóa dòng.

Bản cải tiến đã chạy **60 test PostgreSQL, 60 đạt, không bỏ qua**. Đã kiểm tra Chromium theo các luồng nhân viên/quản lý thật trên dữ liệu thử: nhập, xuất, chuyển hai bước, mượn, trả từng phần, kiểm kê, điều chỉnh, Excel và đổi mật khẩu. Chi tiết tại [bằng chứng kiểm tra](docs/WORKSPACE_VALIDATION.md).

## Cấu trúc và tài liệu

- `inventory/services.py`: nghiệp vụ ghi sổ và kiểm soát quyền.
- `inventory/forms.py`: biểu mẫu và kiểm tra đầu vào.
- `inventory/workspace.py`: phạm vi kho dùng chung.
- `inventory/views.py`: các màn hình và xuất dữ liệu.
- `templates/`: giao diện Django; `static/app.css`: thiết kế; `static/document-form.js`: thao tác dòng hàng; `static/dashboard.js`: biểu đồ từ dữ liệu thật.
- [Hướng dẫn công việc](docs/WORKSPACE_GUIDE.md)
- [Giữ production ổn định và phát hành bản mới](docs/RELEASE_PROCESS.md)
- [Triển khai Render / Neon](docs/FREE_HOSTING.md)
- [Kiến trúc và định giá](docs/ARCHITECTURE.md)

Production dùng PostgreSQL, `DEBUG=0`, `SECRET_KEY` bảo mật và hostname HTTPS hợp lệ. `render.yaml`, Dockerfile, `build.sh` và `start.sh` giữ cơ chế triển khai hiện có. Bí mật nhập trong hosting; không gửi vào chat hoặc ghi vào Git. Bản giao diện mới không có migration DB, không cần tạo lại tài khoản hoặc nhập lại dữ liệu cũ.

Các giới hạn hiện tại: chưa theo dõi lô / hạn sử dụng theo lựa chọn chủ dự án; chưa có FIFO, nhận hàng từng phần, hủy hàng đang chuyển, kiểm kê riêng tồn mượn hoặc báo cáo tồn cuối kỳ hồi tố. Tổng quan nhập/xuất theo kỳ, còn số tồn hiển thị là tồn hiện tại. File nhập tối đa 50 mã hàng / 5 MB, dùng `.xlsx`; xuất báo cáo CSV mở được bằng Excel.
