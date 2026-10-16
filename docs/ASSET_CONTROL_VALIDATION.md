# Kiểm tra đợt chi tiết kiểm soát tài sản

Ngày 16/10/2026, nhánh `feature/asset-control-details`. Chỉ sử dụng dữ liệu thử tách riêng. Không dùng Neon production, không ghi lên website thật.

## PostgreSQL

**86 kiểm thử, 86 đạt, 0 thất bại, 0 bỏ qua**, trên PostgreSQL 17. Gồm 60 bài hồi quy và 26 bài bổ sung; bao gồm kiểm thử migration.

- Nhập, xuất, giá bình quân, giá trị tồn, chống âm tồn và hai luồng đồng thời xuất hàng.
- Chuyển hai bước, bảo toàn giá trị; mượn khóa riêng, trả một phần, chống trả quá số còn mượn.
- Mã hàng / đơn vị, các vai trò và phạm vi kho; người lập không tự duyệt, không tự nâng quyền; mật khẩu theo chính sách đã chốt.
- Ngày quá khứ / tương lai bị chặn tại biểu mẫu và khi duyệt. Phiếu cũ được cập nhật ngày hôm nay qua thao tác sửa; hàng đang chuyển vẫn nhận được ngày sau.
- Thiếu / không nhận phải có lý do, không vượt số theo chứng từ; chỉ số thực nhận vào tồn và giá trị. Toàn bộ hàng bị từ chối không tạo tồn / movement bằng 0.
- Kiểm kê có mốc tồn; chặn sau biến động, kể cả thay đổi có tổng bằng 0. Phiếu kiểm kê cũ thiếu mốc phải được cập nhật lại.
- Tên / mã / đơn vị chụp trên dòng, lịch sử trước sửa, chống ghi đè phiên cũ; yêu cầu sửa, gửi lại, hủy trước ghi sổ, kiểm tra quyền và lý do.
- Excel mẫu cũ và mới, công thức / số sai / thiếu lý do, giữ thông tin qua xem trước và xác nhận, từ chối phiên qua ngày mới.
- Xuất CSV dữ liệu kiểm soát, an toàn ô công thức, lọc ngày từng bước chuyển kho; không lỗi với truy vấn mã số quá dài.
- Không cho người ngoài phạm vi xem nhật ký hoặc hủy phiếu; diễn giải HTML được escape.
- Migration từ schema 0007 lên 0011 trên DB test giữ tài khoản / mật khẩu băm, phiếu, số lượng, giá trị và timestamp cũ. Kiểm tra chuyển ngày UTC sang Việt Nam đúng; không tạo nhật ký giả cho lịch sử.

## Trình duyệt Chromium

Chạy trên database preview tách riêng, bằng nhân viên, quản lý và quản trị viên thật trong môi trường thử:

- Toàn bộ luồng nhập, xuất, chuyển đi / nhận, mượn / trả một phần, kiểm kê, điều chỉnh và Excel; kiểm tra số tồn sau từng thao tác.
- Tạo nhân viên, đổi mật khẩu, bộ lọc kho, hàng chờ duyệt, các trang danh mục / báo cáo / thẻ kho.
- Lập phiếu nhập có chứng từ nguồn, đối tác, người giao / nhận, bộ phận; 10 theo chứng từ, 7 nhận, 2 không nhận, 1 thiếu.
- Quản lý yêu cầu bổ sung; người lập sửa và gửi lại; quản lý duyệt; nhật ký và báo cáo hiển thị.
- Desktop, điện thoại 390 px, phần thông tin chi tiết mở; kiểm tra tràn ngang sau khi bố cục ổn định. Resize có transition của giao diện được chờ hoàn tất trong kiểm tra.
- Tạo được PDF từ chế độ in. Không phát hiện lỗi JavaScript hoặc HTTP 500 trong các luồng chạy.

## Kiểm tra nền và phạm vi kết luận

Django check, phát hiện migration chưa tạo, Ruff F, cú pháp JavaScript, kiểm tra phụ thuộc Python và Git whitespace đạt. Không thay requirements hoặc cấu hình hosting.

Đây là bằng chứng cho các tình huống đã chạy, không phải bảo đảm phần mềm không bao giờ có lỗi. Chưa có kiểm thử tải nhiều người dùng dài hạn, nghiệm thu bằng dữ liệu thật hoặc phục hồi backup Neon production. Bản in là bản đối chiếu nội bộ, chưa có ký số.

Trước triển khai cần backup / thử phục hồi Neon và lên lịch chuyển phiên bản. Migration bổ sung cột không phải cơ chế nâng cấp hai phiên bản ghi đồng thời; cần kiểm soát khoảng chuyển đổi thay vì cam kết không gián đoạn ghi dữ liệu. Các cấu hình và dữ liệu production chưa bị tác động trong đợt phát triển này.
