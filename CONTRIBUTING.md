# Phát triển và bảo trì

## Thay đổi theo phạm vi nhỏ

Tạo nhánh riêng từ `main`. Mỗi thay đổi cần nêu vấn đề, hành vi sau sửa và cách kiểm tra. Giữ nghiệp vụ, URL và dữ liệu cũ trừ khi yêu cầu đã được chốt. Giao diện có mục chuẩn bị không đồng nghĩa đã có quy trình tương ứng.

Dùng Python 3.12, dependency được ghim trong `requirements*.txt` và Ruff theo `pyproject.toml`. Không ghi token, mật khẩu thật, dữ liệu cá nhân, database thử hoặc tệp Drive vào Git. Cấu hình phát triển ở README; PostgreSQL thử phải tách khỏi production.

## Ranh giới mã nguồn

- `core`: tài khoản và tiện ích dùng chung; không đặt nghiệp vụ nhân sự mới vào quản lý tài khoản.
- `inventory`: nghiệp vụ kho. Views xử lý HTTP; phép tính và thao tác ghi sổ ở lớp nghiệp vụ.
- `workflows`, `people`: hiện chỉ có trang chuẩn bị. Nghiệp vụ mới cần được chốt, định nghĩa quyền và kiểm thử trước khi tạo.
- Không đổi `app_label` hoặc chuyển các model hiện có chỉ để đổi vị trí file. Nếu cần chuyển bảng, phải có thiết kế migration và diễn tập dữ liệu riêng.
- Ưu tiên import module cụ thể khi sửa code mới; `inventory/views/__init__.py` chỉ giữ tương thích cho các tên gọi đã có.

## Quyền và dữ liệu

Mọi endpoint mới phải được bảo vệ khi chưa đăng nhập và có kiểm tra quyền ở máy chủ. `FunctionAccessMiddleware` mặc định từ chối endpoint chưa đăng ký trong các namespace công ty; không đổi namespace để bỏ kiểm tra. Admin giữ toàn quyền theo yêu cầu chủ dự án. Quy trình xác nhận tự duyệt, kiểm tra cấp cao hơn và phạm vi kho vẫn cần thực hiện ở nghiệp vụ.

Các thao tác kho phải giữ transaction, thứ tự khóa, kiểm tra tồn và chống gửi lại. Không cập nhật trực tiếp Balance hoặc Movement trong view mới. Không chỉnh phiếu đã ghi sổ hoặc làm tròn tiền bằng float. QR đã cấp phải được giữ theo vòng đời hàng hóa.

## Giao diện

Sửa nguồn tại `assets/styles/`, chạy `python scripts/build_styles.py`, rồi kiểm tra `--check`. `static/app.css` là bundle sinh tự động; không thêm lớp CSS ghi đè riêng chỉ cho một đợt chỉnh sửa. Các biến `--accent*`, `--silver*` dùng cho nhận diện; `--success*`, `--red*`, `--amber*` dùng cho trạng thái có ý nghĩa.

Kiểm tra trang bị ảnh hưởng ở sáng/tối, máy tính/điện thoại, dữ liệu trống/có dữ liệu và trạng thái lỗi. Thay đổi giao diện phải giữ nhãn biểu mẫu, khả năng dùng bàn phím và độ tương phản. Khi refactor CSS, so sánh trước–sau để phát hiện thay đổi ngoài ý muốn.

## Kiểm tra và bàn giao

Chạy các lệnh ở README trên PostgreSQL riêng. Thêm kiểm thử cho quy tắc hoặc ranh giới quyền mới; không thêm kiểm thử chỉ để khớp lại cách triển khai. Không sửa migration lịch sử trong một refactor. Chạy kiểm tra migration và static trước khi đề nghị phát hành.

GitHub Actions kiểm tra trên push/PR; kiểm thử ở máy phát triển không tự chứng minh một lần chạy GitHub đã thành công. Xem tab Actions trước khi merge. Chủ repository cần bật Rulesets nếu muốn bắt buộc các kiểm tra trước khi thay đổi `main`.

Sau khi phát hành, kiểm tra đúng release tại `/healthz/`, đường dẫn cần đăng nhập, static và những luồng bị ảnh hưởng. Ghi rõ kiểm tra nào dùng dữ liệu thử và giới hạn nào chưa xác minh được trên tài khoản thực. Xem `docs/RELEASE_PROCESS.md`.
