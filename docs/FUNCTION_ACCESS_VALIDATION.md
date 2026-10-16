# Kết quả rà soát và kiểm tra phân quyền

Bản phát triển `feature/admin-function-permissions`, kế thừa hai đợt chi tiết chứng từ và QR/hồ sơ chưa phát hành. Thực hiện trong môi trường thử tách biệt; không dùng database hoặc tài khoản thật của công ty. Kết quả này không phải bằng chứng đã triển khai production hoặc cam kết mọi thiết bị/mọi tình huống đều không lỗi.

## Phần sửa chính

- Admin tự có toàn bộ quyền. Các tài khoản khác dùng bảng cấp từng chức năng; tài khoản mới bắt đầu không có quyền nghiệp vụ.
- Kiểm tra quyền ở máy chủ cho đường dẫn trực tiếp, biểu mẫu, API, CSV và tải tệp. Bỏ quyền thì phiên đang đăng nhập cũng bị chặn ở yêu cầu tiếp theo.
- Tách quyền xem/lập/duyệt/xác nhận nhận hàng và phạm vi kho. Sửa danh mục kho không cho tài khoản thường tự thêm người hoặc đổi người duyệt.
- Khu vực quản trị chỉ admin vào được. Vai trò Django cũ và cờ `is_staff` không tạo đường vòng.
- Lưu tài khoản, mật khẩu, quyền và phân công kho trong transaction. Phiên bản bản cấp quyền ngăn cửa sổ cũ ghi đè lần lưu mới; nhật ký không ghi mật khẩu.
- Menu và nút theo quyền. Các tab trạng thái và nút xóa bộ lọc giữ loại phiếu đang xem; người chỉ xem nhập kho không bị dẫn sang trang chung thiếu quyền.
- Sau khi thu hồi quyền thao tác kiểm kê, màn hình chỉ xem không còn hiện nút hủy phiên; gửi đường dẫn hủy trực tiếp cũng bị chặn.
- Migration 0016 chuyển một lần các quyền/phân công đã có; không lấy quyền trùng tên từ ứng dụng khác và không tự cấp duyệt điều chỉnh từ nhóm quản lý kho.
- Có `/healthz/` kiểm tra kết nối DB, migration 0016, mã release; lỗi không trả chuỗi kết nối.

## Kiểm thử PostgreSQL

**142 bài kiểm thử đạt, không bỏ qua.** Chạy toàn bộ `manage.py test --noinput` trên PostgreSQL thử, bao gồm các bài nghiệp vụ và nâng cấp trước đây cùng 19 bài kiểm tra quyền/điều hướng/health và 7 bài snapshot. Bài nâng cấp cũng diễn tập phục hồi schema/dữ liệu trước nâng cấp.

Các tình huống có kiểm tra kết quả dữ liệu, không chỉ mã HTTP:

- Nhập/xuất, chuyển đi/nhận về, mượn/trả từng phần, hàng mượn bị khóa, thiếu/hỏng/thực nhận và định giá.
- Không âm tồn khi nhiều transaction cùng duyệt; không tự duyệt phiếu mình lập, kể cả admin.
- Ngày nghiệp vụ hôm nay; phiếu đã ghi sổ không sửa trực tiếp; kiểm kê tạo phiếu chênh lệch và người đủ quyền duyệt mới đổi tồn.
- Lượt đếm QR có UUID chống xử lý lặp, số đếm có phiên bản và mốc tồn; chặn chốt khi còn dòng chưa xác nhận hoặc tồn đã thay đổi.
- Tài khoản không quyền không thấy dữ liệu; chỉ xem không lập/sửa/hủy; từng quyền phải đi cùng phân công kho. Quyền hết hiệu lực ngay với phiên đăng nhập cũ.
- Không xem/tải hóa đơn hoặc số tồn chỉ nhờ quyền danh mục hàng hóa; xuất CSV có quyền riêng.
- Bản cấp quyền cũ, quyền giả mạo và CSRF không thay đổi một phần tài khoản/mật khẩu/quyền.
- Nâng schema từ 0007 đến 0016 trên dữ liệu thử giữ số lượng, giá trị, ngày chứng từ lịch sử và mật khẩu băm; QR các mã hàng khác nhau và quyền cũ được chuyển đúng. Đây là dữ liệu thử, không phải bản sao lưu Neon thật.
- Tệp ảnh/PDF, giới hạn dung lượng, kiểm tra nội dung, lịch sử hóa đơn, quyền tải và tích hợp Drive bằng phản hồi mô phỏng.

## Kiểm tra trình duyệt Chromium

Đã chạy với tài khoản thử nhân viên, quản lý, Tổng giám đốc và admin:

| Luồng | Kết quả |
| --- | --- |
| Admin tạo tài khoản chỉ được nhập, tự chọn quyền xem cần thiết, cấp kho, nhân viên lập phiếu | Đạt; không thấy menu xuất/duyệt, truy cập thẳng URL xuất bị chặn. |
| Admin thu hồi quyền trong khi nhân viên giữ nguyên phiên và biểu mẫu cũ | Đạt; gửi biểu mẫu cũ bị chặn, dữ liệu không ghi thêm. |
| Tài khoản chỉ xem phiếu nhập: cả 7 tab trạng thái, lọc và xóa bộ lọc | Đạt; giữ loại IN, trang chung không được cấp vẫn bị chặn. |
| Nhập, duyệt nhập, xuất, chuyển hai bước, mượn/trả, COUNT/ADJUST, Excel | Đạt; kiểm tra qua biểu mẫu và người duyệt khác người lập. |
| QR đọc video camera mô phỏng và ảnh QR thật | Đạt; đưa mã vào khung 2 lượt cộng 2, giữ mã không cộng liên tục; chốt → phiếu điều chỉnh → Tổng giám đốc duyệt → xem biên bản. |
| Mất phản hồi sau khi máy chủ đã ghi lượt quét | Đạt; tải lại chặn chốt khi chưa đối soát, thử lại cùng UUID không cộng lần hai, lượt tiếp theo mới cộng thêm. |
| Đổi mật khẩu, thay phạm vi kho, giao diện sáng/tối, menu điện thoại | Đạt trong các luồng đã thử. |
| Bảng quyền trên desktop và màn hình 390px | Không tràn ngang; không lỗi JavaScript hoặc HTTP 500 trong các luồng chạy đạt. |

Camera mô phỏng không thay thế nghiệm thu bằng điện thoại/máy quét thật và không chứng minh hiệu năng nhiều người dùng. Chưa thử OAuth/Picker bằng tài khoản Google thật của chủ dự án.

Ảnh có dữ liệu minh họa:

- [Màn hình cấp quyền](preview-permissions/cap-quyen-chuc-nang.png)
- [Chi tiết bảng quyền](preview-permissions/bang-quyen.png)
- [Giao diện điện thoại](preview-permissions/cap-quyen-mobile.png)
- [Tài khoản chỉ được nhập](preview-permissions/nhan-vien-chi-quyen-nhap.png)

## Kiểm tra triển khai và mã nguồn

- Django system check: đạt; `makemigrations --check --dry-run`: không còn thay đổi schema chưa ghi.
- Ruff kiểm tra lỗi F, định dạng các tệp Python đã sửa, cú pháp JavaScript/shell và `git diff --check`: đạt.
- Biên dịch toàn bộ template và thu thập 137 static assets: đạt.
- Docker dùng cùng base/dependency/code, cài wheel đã tải từ PyPI qua TLS trong build tách biệt vì mạng Docker không tải trực tiếp được. Dockerfile production dùng pip thông thường và khởi động bằng `safe_migrate`. Container dùng PostgreSQL riêng, `DEBUG=0`, thử từ schema 0007 → snapshot → 0016 → khởi động lại bằng CMD thật; health xác nhận snapshot nguồn 0007, login/static HTTP 200, Django check và `pip check` đạt.
- Cấu hình `DEBUG=0`, PostgreSQL thử và khóa thử ngẫu nhiên: deploy check không có lỗi, còn hai khuyến nghị HSTS `includeSubDomains`/`preload`. Chưa bật hai tùy chọn này trước khi chốt quyền kiểm soát domain/subdomain; HTTPS, secure cookies và HSTS cho hostname hiện tại đã bật.
- Quét chuỗi bí mật trong các tệp dự kiến commit; không đưa tài khoản thử, DB, file môi trường, token hoặc wheel vào Git.

## Điều kiện còn thiếu ở hệ thống thật

Chủ dự án đã cho phép phát hành và yêu cầu tự cập nhật ngày 17/10/2026. Đã bổ sung [snapshot tự động trước migration](AUTOMATED_RELEASE_SNAPSHOT.md), dùng kết nối database sẵn có trong Render. Cơ chế đã thử sao chép, lỗi, đồng thời và khôi phục trên DB thử; trạng thái production phải được đối chiếu qua health sau deploy, không suy ra đã tạo snapshot thật chỉ từ test. Bản chụp nằm trong cùng Neon, chưa thay thế backup độc lập.

Trước khi push đợt phát hành 17/10, remote main được kiểm tra là `f0a38e7` và schema inventory cũ là 0007. Trang đăng nhập production phản hồi HTTP 200; chưa dùng tài khoản thật để nghiệm thu nghiệp vụ. Sau push, phải đối chiếu chính xác mã release và metadata snapshot tại `/healthz/` cùng login/static; kết quả HTTP 200 trước push không chứng minh bản mới đã triển khai. Xem [quy trình phát hành](RELEASE_PROCESS.md).

Google Drive vẫn cần cấu hình OAuth và kết nối tài khoản/thư mục thật. Chưa tải tệp công ty vào Drive, chưa kiểm chứng lưu/tải thật. Kho vẫn dùng database; tải ảnh/hóa đơn online phải hoàn tất cấu hình Drive, không ghi tạm vào ổ Render và không tuyên bố đã kết nối chỉ vì có link thư mục.

Sau phát hành cần đối chiếu release/health, đăng nhập với tài khoản nghiệm thu thật, quyền kế thừa và một luồng kho phù hợp. Tài liệu này sẽ cập nhật theo kết quả thực tế; không ghi là đã nghiệm thu khi chưa có quyền truy cập đó.
