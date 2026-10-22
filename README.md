# DHD · Kiểm soát nội bộ

Ứng dụng Django 5.2 / Python 3.12, dùng PostgreSQL khi triển khai. Giao diện tiếng Việt, hỗ trợ máy tính và điện thoại, chế độ sáng/tối vàng kim – bạc.

Website: https://kiemsoatnoibolemon.onrender.com

## Các phân hệ

| Phần | Trạng thái và trách nhiệm |
| --- | --- |
| Quản lý kho | Danh mục, nhập/xuất/chuyển, mượn trả, kiểm kê giấy/QR, duyệt phiếu, báo cáo và Excel |
| Quản trị hệ thống | Tài khoản, phân quyền, đổi mật khẩu; kết nối Drive, đo dung lượng và báo cáo Sheets |
| Xử lý sai lệch | Hồ sơ sự việc, hành động, bằng chứng và lịch sử riêng; mở xử lý sau khi Admin cấu hình quy tắc công ty |
| Quy trình | Trang chuẩn bị, chưa có nghiệp vụ mới |
| Quản lý nhân sự | Trang chuẩn bị, chưa có nghiệp vụ mới |

Admin có toàn quyền; tài khoản khác được cấp quyền từng chức năng và phạm vi kho. Người duyệt thông thường phải có cấp cao hơn người lập. Admin được tự duyệt với cảnh báo và xác nhận được ghi lịch sử. Xem [quy tắc duyệt](docs/APPROVAL_HIERARCHY.md).

Phiếu đã ghi sổ không được sửa nội dung hoặc xóa. Phiếu liên kho có bước chuyển đi và xác nhận nhận. Hàng mượn được quản lý riêng với tồn khả dụng; không dùng hàng mượn để xuất như hàng sở hữu. Kiểm kê khóa giao dịch kho trong phiên; số chênh lệch chỉ cập nhật tồn qua phiếu điều chỉnh được duyệt. Không triển khai các quy trình mới chỉ dựa trên đề xuất chưa được chốt.

## Cấu trúc để phát triển

```text
config/                  Cấu hình, URL gốc và health check
core/                    Tài khoản, quản trị dùng chung, tiện ích xuất dữ liệu
inventory/               Mô hình dữ liệu và nghiệp vụ kho
  views/                 Màn hình tách theo nghiệp vụ
  migrations/            Lịch sử thay đổi cấu trúc dữ liệu
workflows/               Điểm vào phân hệ Quy trình
people/                  Điểm vào phân hệ Nhân sự
assets/styles/           CSS nguồn: màu sắc, bố cục, thành phần và nghiệp vụ
static/                  CSS đã ghép, JavaScript và thư viện giao diện
scripts/build_styles.py  Ghép CSS có kiểm tra đồng bộ
templates/              Các màn hình Django
.github/workflows/       Kiểm tra tự động trên GitHub
docs/                   Kiến trúc, quy trình nghiệp vụ và phát hành
```

`inventory.views` giữ các tên hàm cũ để tương thích; code màn hình nằm trong `inventory/views/`. Các bảng và lịch sử migration vẫn thuộc `inventory`, kể cả những dữ liệu hiện được dùng chung. Tách giao diện/phân hệ trong đợt này không chuyển bảng hoặc ghi lại dữ liệu. Chi tiết tại [kiến trúc](docs/ARCHITECTURE.md).

## Khởi chạy ở máy phát triển

Cần Python 3.12; dùng PostgreSQL để kiểm tra đầy đủ giao dịch và khóa đồng thời.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt

docker compose -f compose.dev.yml up -d
export DEBUG=1
export DATABASE_URL=postgresql://dhd_dev:local-development-only@127.0.0.1:55434/dhd_dev

.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py setup_roles
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Compose chỉ mở cổng database ở loopback và lưu dữ liệu vào volume phát triển riêng. Không dùng URL database công ty để chạy thử, tạo mẫu hoặc kiểm thử. File `.env.example` mô tả các biến môi trường; ứng dụng đọc biến từ môi trường chạy, không tự nạp file `.env`.

## Kiểm tra trước khi gửi thay đổi

```sh
.venv/bin/ruff check .
.venv/bin/python scripts/build_styles.py --check
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py test --noinput
.venv/bin/python manage.py collectstatic --noinput
```

Các lệnh trên dùng cùng database **phát triển** đã cấu hình. Django tạo database test riêng. PostgreSQL cần cho phép tạo database test; SQLite chỉ phù hợp cho thử nhanh và bỏ qua các kiểm thử khóa đồng thời. Kiểm tra JavaScript bằng `node --check static/<ten-file>.js` với Node 22.

GitHub Actions chạy kiểm tra mã, CSS, JavaScript, migration, kiểm thử PostgreSQL và thu gom static trên mỗi lần push hoặc mở pull request. Trạng thái chạy thực tế xem ở tab **Actions**. Quy tắc bắt buộc kiểm tra đạt trước khi merge phải được chủ repository bật trong GitHub Rulesets; workflow không tự cấp quyền hoặc sửa cấu hình đó.

## Sửa giao diện

- Màu sắc và theme: `assets/styles/foundation.css`.
- Bố cục chung, thành phần và nghiệp vụ: các file trong `assets/styles/`.
- Sau khi sửa CSS nguồn, chạy `python scripts/build_styles.py` và commit cả nguồn lẫn `static/app.css`.
- Không sửa trực tiếp bundle `static/app.css`. CI và bước build sẽ phát hiện bundle lệch nguồn.
- Màn hình đăng nhập có stylesheet riêng `static/login.css`; không cần ghép vào bundle nội bộ.
- Giữ trạng thái thành công/cảnh báo/lỗi tách biệt với màu nhận diện; xem [quy ước màu](docs/COMPANY_COLOUR_THEME.md).

## Triển khai và tài liệu

Production dùng PostgreSQL, `DEBUG=0`, HTTPS và bí mật từ cấu hình hosting. Dockerfile và `build.sh` kiểm tra CSS trước khi thu gom static. `start.sh` / Docker chạy `safe_migrate` trước khi mở ứng dụng. Snapshot cùng database phục vụ phục hồi migration, không thay thế backup độc lập.

- [Hướng dẫn đóng góp và kiểm tra](CONTRIBUTING.md)
- [Kiến trúc và ranh giới phân hệ](docs/ARCHITECTURE.md)
- [Quy trình phát hành](docs/RELEASE_PROCESS.md)
- [Hướng dẫn nghiệp vụ](docs/WORKSPACE_GUIDE.md)
- [Kiểm kê và QR](docs/STOCKTAKE_WORKFLOW.md)
- [Excel danh mục](docs/PRODUCT_EXCEL_IMPORT.md) và [Excel nhập kho theo kho](docs/RECEIPT_EXCEL_WAREHOUSES.md)
- [Google Drive](docs/GOOGLE_DRIVE_CONNECTION.md)

Các tài liệu kiểm thử/phát hành có ngày hoặc số lượng test ở đợt cũ là bằng chứng lịch sử. Dùng kiến trúc, quy trình phát hành và kết quả CI hiện tại để tiếp tục phát triển; không suy ra phiên bản đang chạy từ số test trong báo cáo cũ. `/healthz/` công bố mã release và trạng thái sẵn sàng, không trả dữ liệu công ty.

Theo dõi dung lượng và lưu báo cáo: [hướng dẫn vận hành](docs/STORAGE_AND_REPORTS.md).
