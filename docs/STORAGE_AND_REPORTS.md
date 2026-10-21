# Dung lượng và báo cáo lưu trữ

## Quyết định vận hành

- PostgreSQL giữ dữ liệu nghiệp vụ chính thức, tồn kho, phê duyệt, kiểm kê,
  phân quyền và lịch sử. Không chuyển những bảng này sang Google Sheets.
- Drive giữ ảnh, hóa đơn và tệp hồ sơ. Không dùng database làm nơi dự phòng tệp
  khi Drive lỗi; quy tắc hiện tại không thay đổi.
- Google Sheets là bản tra cứu theo tháng, không phải bản sao lưu phục hồi.
  Xuất báo cáo không tự giảm dung lượng database.
- Bản phát hành này không xóa, chuyển dữ liệu gốc, thay đổi quyền Google,
  gỡ snapshot hoặc thay đổi SECRET_KEY/DATABASE_URL.

## Màn hình quản trị

**Quản trị hệ thống → Dung lượng & báo cáo**, URL `/settings/storage/`.
Chỉ tài khoản active superuser truy cập được, kể cả đường dẫn tải/POST trực tiếp.
GET không liên hệ Google hoặc tự xuất báo cáo. Các thao tác có CSRF và POST.
Tất cả phản hồi của mục này đặt `Cache-Control: private, no-store`.

**Kiểm tra dung lượng** đọc `pg_database_size`, dung lượng từng bảng/chỉ mục,
nhóm schema snapshot, số lượng và dung lượng nội dung tệp trong StoredFile.
Dòng ước tính lấy từ PostgreSQL statistics, không dùng làm số đối soát nghiệp vụ.
Số byte tệp là dung lượng nội dung, không phải kích thước vật lý PostgreSQL.
Giới hạn mỗi câu đọc là 8 giây, lỗi không làm thay đổi dữ liệu.
Kết quả cache 10 phút theo database, có thể tải JSON không chứa bí mật hoặc
nội dung phiếu. Cache metadata dùng tệp tạm chung giữa các web worker, không lưu nội dung
nghiệp vụ hoặc token. Cache có thể mất sau khởi động; bấm kiểm tra lại khi cần.
Không cộng metadata cache vào database.

Chỉ cấu hình `DATABASE_STORAGE_LIMIT_MB` khi đã xác nhận ngân sách cho riêng
DB này (đơn vị MiB). Nếu trống, không đoán số còn lại. PostgreSQL measurement
không thay thế số sử dụng toàn tài khoản Neon: nhánh khác, PITR/lịch sử và các
DB khác có thể được tính riêng. Quota Google lấy từ chính tài khoản OAuth và
có thể được dùng chung với các dịch vụ Google khác.

Có thể kiểm tra trên máy chủ bằng:

```sh
python manage.py storage_audit
```

Không chép biến môi trường, connection string hoặc refresh token vào báo cáo.

## Báo cáo Google Sheets

Xuất cho **tháng đã kết thúc**; mặc định tháng trước. Chưa cài lịch chạy tự động
hoặc dịch vụ trả phí. Admin bấm xuất trong phần mềm. Có command phục vụ lịch
vận hành sau này nếu hạ tầng đã có bộ lập lịch phù hợp:

```sh
python manage.py export_storage_report --period 2026-09
```

Thư mục: thư mục gốc đã chọn → **Báo cáo quản trị → năm → Báo cáo kho YYYY-MM**.
Không đổi thư mục ảnh/hóa đơn hiện tại. Đọc đầy đủ danh sách quyền ở thư mục
gốc, thư mục báo cáo và thư mục năm trước khi xuất; chặn quyền loại anyone và
trường hợp không xác minh được. Không tự sửa ACL. Báo cáo kế thừa quyền người
được chia sẻ trong thư mục, nên admin vẫn cần kiểm soát danh sách này.

Kết nối OAuth hiện có với `drive.file` tạo Sheets bằng Drive API nhập XLSX.
Không cần xin quyền đọc toàn Drive, đổi client secret hoặc bật Sheets API.
Tối đa 25.000 dòng dữ liệu/5 MiB; vượt giới hạn báo lỗi, không cắt bớt dữ liệu.
Số tiền, mã hàng và chuỗi được lưu là text để giữ chính xác, không thực thi
công thức từ tên hàng hoặc ghi chú. Muốn tính toán thêm nên dùng tab riêng.

Các tab:

- Thông tin mốc xuất, múi giờ và phạm vi.
- Tổng hợp giao dịch theo kho và đơn vị tính: tăng, giảm, ròng và giá trị ròng.
  Không cộng số lượng khác đơn vị (ví dụ Cái với Hộp) thành cùng một dòng.
- Nhật ký biến động theo **thời điểm thực tế của từng chặng** trong tháng:
  bao gồm chặng chuyển kho đã xuất nhưng đang chờ nhận.
- Phiếu liên quan; trạng thái tại thời điểm xuất.
- Tồn khả dụng **tại thời điểm xuất**, không gọi là tồn cuối tháng.
- Hàng mượn còn giữ **tại thời điểm xuất**.
- Các dòng kiểm kê có ngày chốt trong tháng, đối chiếu ảnh chụp lúc chốt;
  trạng thái phê duyệt tại thời điểm xuất.

Mã/tên/ĐVT trong nhật ký là danh mục tại thời điểm xuất và ghi rõ trong tiêu đề;
phiếu kiểm kê dùng các trường snapshot. Không xuất tài khoản, quyền, token,
chat, ảnh hoặc PDF vào bản báo cáo.

Đọc nguồn bằng PostgreSQL REPEATABLE READ READ ONLY; không giữ khóa kho khi
liên hệ Drive. Dedicated advisory lock cho luồng xuất báo cáo ngăn các web worker xuất
trùng hoặc đồng thời tạo trùng thư mục chung giữa các tháng. Nếu phản hồi Google bị mất, lần thử lại tìm đúng appProperties trong
thư mục năm và kiểm tra bản đang tồn tại.

Bản đầu tiên mỗi tháng được giữ nguyên. Sau upload, xuất lại XLSX từ Google,
kiểm tra đầy đủ từng ô bằng SHA-256 canonical trước khi đánh dấu verified.
Cả bản đã verified cũng được kiểm tra lại khi bấm xuất lại. Có thay đổi ngoài
phần mềm hoặc công thức bất thường thì báo lỗi, không ghi đè hoặc giả thành công.
Bản pending có thể nằm trên Drive nếu kiểm tra lỗi; dữ liệu gốc không bị xóa.
Không tự tạo bản thay thế khi phát hiện nhiều bản cùng khóa hoặc sai số.

## Điều kiện cho tối ưu tiếp theo

Dựa trên số đo chính thức, lập phương án riêng cho tệp cũ trong DB hoặc
snapshot lớn. Trước khi gỡ snapshot phải có bản sao lưu bên ngoài đầy đủ,
được mã hóa, có kiểm tra khôi phục trên DB tách biệt và mốc lưu giữ rõ ràng.
Không dùng Sheets hoặc tổng số dòng thay cho kiểm tra phục hồi. Không tự
chạy VACUUM FULL, DROP SCHEMA, DELETE giao dịch, hoặc xóa lịch sử phê duyệt.

## Giới hạn xác minh

Kiểm tra PostgreSQL và trình duyệt dùng dữ liệu giả lập độc lập. API Google
được kiểm tra mô phỏng (tạo/đọc lại/retry/từ chối bản chỉnh sửa). Việc tạo
Sheet thật cần chạy bằng kết nối OAuth của chủ thư mục trong hệ thống online;
không lấy hoặc sao chép bí mật sản xuất vào máy kiểm thử.

## Hạn mức Free đã xác nhận cho website chính thức

Ngày 21/10/2026, chủ ứng dụng xác nhận dự án Neon
`bold-resonance-26000114` dùng Free. Tài liệu chính thức tại
https://neon.com/docs/introduction/plans ghi **1 GB Postgres / dự án**,
tách riêng Object Storage và giới hạn tổng nhiều dự án.
`config/storage_profiles.py` chỉ áp dụng thông tin này cho hostname Render
`kiemsoatnoibolemon.onrender.com` kết nối database Neon. Không áp dụng mặc định
cho các bản sao, máy phát triển, DB khác nhà cung cấp hoặc deployment khác.
`DATABASE_STORAGE_LIMIT_MB` nếu được cấu hình sẽ ưu tiên ngân sách riêng đó.

UI ghi rõ tử số là database ứng dụng, mẫu số là hạn mức toàn dự án. Không
lấy 1 GB trừ pg_database_size để gọi là dung lượng Neon còn lại, không dùng
số Storage 37,36 MB chủ tài khoản gửi làm số liệu tự cập nhật. Khi thay đổi
gói/dự án phải cập nhật cấu hình. Không truy cập tài khoản Neon hoặc lưu API key.
