# Kiểm tra bản kiểm kê QR và hồ sơ hàng hóa

Ngày 16/10/2026, nhánh `feature/qr-stocktake-product-records`. Chỉ dùng database và tài khoản thử tách riêng; không thay website Render, Neon hoặc Drive thật của chủ dự án.

## Kết quả tự động

**116 kiểm thử PostgreSQL, 116 đạt, 0 thất bại, 0 bỏ qua.** Chạy PostgreSQL 17, bao gồm 86 kiểm thử hồi quy từ bản chi tiết chứng từ và 30 bài bổ sung. Đã chạy lại sau khi bổ sung giữ tên hàng trên biên bản và kiểm tra thu hồi quyền giữa phiên; Django system check không phát hiện lỗi.

| Nhóm | Những điều đã kiểm tra |
| --- | --- |
| Nghiệp vụ cũ | Nhập/xuất, bình quân giá trị, chống âm tồn, chuyển hai bước, mượn khóa riêng và trả từng phần; ngày hôm nay, thiếu/không nhận, sửa/hủy/chờ duyệt, Excel, quyền kho, tài khoản và báo cáo. |
| QR và số đếm | QR tự sinh, xác thực đường dẫn/ảnh tem, tìm mã không mở liên kết ngoài; cộng 1, ghi tổng, chưa đếm khác 0, hàng ngoài sổ cần giá, giữ tên/mã/đơn vị trên biên bản, khóa sau chốt. |
| Kiểm soát duyệt | Chốt chỉ tạo phiếu chênh lệch; tồn không đổi trước duyệt. Quản lý kho và superuser không mặc nhiên duyệt được. Chỉ quyền được cấp trực tiếp, không tự duyệt, cấp/thu hồi có nhật ký không chứa mật khẩu. |
| Mốc tồn | Chặn chốt/duyệt nếu có biến động sau khi mở phiên, kể cả mã mới; không sửa phiếu nguồn đã khóa. Không tiếp tục ghi số qua ngày khác hoặc sau khi bị thu quyền. |
| Tính đồng thời | Hai yêu cầu cùng UUID chỉ cộng một lần; số phiên bản cũ không ghi đè. Tổng giám đốc duyệt đồng thời với người lập hủy thì chỉ một thao tác thành công và số tồn/lịch sử nhất quán. |
| Hồ sơ | Ảnh tùy chọn lúc tạo mã; hóa đơn theo đợt, không nhân đôi theo nhiều sản phẩm. Tệp không công khai, người ngoài kho không tải được. Giữ bản cũ khi đánh dấu không dùng, gắn lại nội dung với metadata đúng không mất lịch sử. |
| Xác minh tệp | Ảnh/PDF/XML sai bị chặn; giới hạn dung lượng; quota phát triển; Drive lỗi không chuyển sang DB; thay nội dung Drive bị phát hiện bằng SHA-256. Bản production không cho chọn database làm nơi lưu bytes tệp. |
| Google OAuth mô phỏng | Chỉ quản trị, CSRF và state/nonce, mã hóa refresh token, không lộ token trong trang; chỉ đúng thư mục đã chỉ định, cấu trúc con và metadata, không tạo quyền chia sẻ công khai. Chưa thay thế nghiệm thu Google thật. |
| Nâng cấp dữ liệu | Migration từ schema 0007 lên 0014 giữ người dùng, mật khẩu băm, tồn, giá trị, ngày cũ và timestamp; QR của hai hàng cũ khác nhau. Không dựng nhật ký giả cho phiếu cũ. |
| Đầu vào bộ lọc | Mã số dài bất thường ở tồn khả dụng, thẻ kho, phạm vi kho và lệnh trả được xử lý, không gây HTTP 500. |

Lệnh chạy lại trên một PostgreSQL **thử nghiệm** có quyền tạo DB test:

```sh
python manage.py test --noinput
python manage.py check
python manage.py makemigrations --check --dry-run
```

Không đặt `DATABASE_URL` production để chạy các lệnh test hoặc seed demo. SQLite bỏ qua kiểm thử khóa dòng nên không đủ làm bằng chứng kiểm tra đồng thời.

## Thử trên Chromium

Các tài khoản thử riêng gồm nhân viên, quản lý kho, quản trị và Tổng giám đốc. Bộ kiểm tra dùng Playwright + Chromium hệ thống; không giả lập hàm giải mã QR bằng kết quả trả sẵn.

- Video đưa QR vào camera hai lần, xen khoảng trắng: bộ giải mã thật tạo đúng hai lượt, giữ nguyên tem trong khung không cộng liên tục. Đọc QR từ ảnh cũng cộng đúng một lượt.
- Kiểm kê tồn sổ 3, đếm 2 → chốt → phiếu điều chỉnh −1; tài khoản quản lý kho không có nút duyệt; Tổng giám đốc duyệt mới cập nhật còn 2; mở và xuất PDF biên bản.
- Cố ý để máy chủ ghi lượt +1 rồi ngắt phản hồi. Tải lại trang vẫn có lượt chưa xác nhận, chốt bị chặn; gửi lại cùng UUID trả replay, tổng vẫn 1. Quét Enter lượt kế tiếp thành 2; chốt không chênh lệch không tạo điều chỉnh.
- Xuất giảm tồn thực; chuyển đi và xác nhận nhận; cho mượn không cộng tồn thường bên mượn; trả một phần; kiểm kê nhập số và điều chỉnh trực tiếp đều qua tài khoản Tổng giám đốc; nhập Excel xem trước rồi duyệt riêng.
- Tạo nhân viên với tên đăng nhập và mật khẩu do quản trị quy định; tự đổi mật khẩu; lập nhập không tự duyệt; quản lý duyệt tăng đúng 7 đơn vị. Kiểm tra hủy hộp xác nhận không khóa nút duyệt.
- Danh mục, nhân viên, kho, hàng chờ, tồn, thẻ kho, báo cáo, mượn, trường bổ sung, đổi mật khẩu và nhập Excel mở được; bộ lọc kho giữ giữa trang; giao diện sáng/tối và menu điện thoại hoạt động.
- Desktop 1440/1600 px và điện thoại 390 px, không tràn ngang ngoài vùng bảng cuộn. Không phát hiện lỗi JavaScript hoặc HTTP 500 trong các luồng thành công đã chạy.

Ảnh sau vòng kiểm tra giao diện cuối, dùng dữ liệu minh họa:

- [Hồ sơ hàng hóa, QR và các đợt nhập](preview-qr/ho-so-hang-hoa.png)
- [Đếm bằng QR trên desktop](preview-qr/kiem-ke-qr.png)
- [Đếm trên điện thoại](preview-qr/kiem-ke-mobile.png)
- [Biên bản đã duyệt điều chỉnh](preview-qr/bien-ban-kiem-ke.png)
- [PDF biên bản minh họa](preview-qr/bien-ban-kiem-ke.pdf)

## Kiểm tra đóng gói và mã

- Django check, migration drift, Ruff F, cú pháp JavaScript, cú pháp shell, Python dependency check và Git whitespace đạt.
- `collectstatic` đạt, có cả bộ đọc QR vendored. Bản npm 2.3.8 được đối chiếu integrity từ registry và giữ giấy phép trong `static/vendor/`.
- Docker build trực tiếp bị giới hạn mạng ở bước tải PyPI trong môi trường này (network unreachable, cả bridge và host). Không sửa production Dockerfile để bỏ xác minh TLS hoặc đổi nguồn không tin cậy. Đã tải đúng bộ wheel từ PyPI qua TLS tại workspace rồi build bằng Dockerfile thử ngoài repository, chỉ thay bước pip bằng nguồn wheel offline. Các bước còn lại giữ nguyên; đóng gói thành công và chạy migration đến 0014, Django check, pip check trong container dưới user ứng dụng thành công, không dùng mạng. Đây là bằng chứng đóng gói offline, chưa phải một lần deploy Render thật.
- Log Gunicorn dùng đường dẫn không có query string, tránh ghi code OAuth vào access log. Không đưa token, file DB, tài khoản demo hoặc cấu hình bí mật vào Git.

## Những việc chưa được nghiệm thu

- Google OAuth/Picker và upload/download vào **Drive thật của chủ dự án**, hạn mức và khả năng refresh token dài hạn. Hiện các kiểm thử Google dùng mock; link thư mục chưa đủ để thực hiện kết nối thật.
- Camera trên điện thoại Android/iPhone thật, máy quét USB vật lý, tem in và ánh sáng tại từng kho. Chromium camera giả lập/ảnh không thay nghiệm thu thiết bị thực tế.
- Tải dài hạn với nhiều người dùng, phục hồi backup Neon/Drive thật, chuyển phiên bản chính và xác nhận số dư bằng dữ liệu công ty. Đợt phát triển không thay production.
- Biên bản hiện là mẫu nội bộ, chưa chữ ký số hoặc mẫu pháp lý được công ty duyệt. Không có quản lý serial, FIFO hay phân bổ xuất theo từng hóa đơn.

Các kết quả trên xác nhận những tình huống đã chạy, không phải cam kết phần mềm không bao giờ có lỗi. Xem [điều kiện phát hành](RELEASE_PROCESS.md) và [đề xuất quản trị công ty](COMPANY_PLATFORM_REVIEW.md).
