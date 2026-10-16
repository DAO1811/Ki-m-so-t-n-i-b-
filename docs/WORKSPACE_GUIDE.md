# Bản giao diện mới — hướng dẫn theo công việc

Bản này được phát triển trên nhánh `feature/modern-warehouse-workspace`. Chưa cập nhật website production. Ảnh trong `docs/preview/` dùng dữ liệu thử riêng; không phải số liệu Neon của đơn vị.

## Khởi tạo

1. Quản trị viên vào **Kho hàng → Thêm kho**: mã, tên, địa chỉ; phân công được ngay tại màn hình này.
2. Vào **Nhân viên & quyền → Thêm nhân viên**: đặt tên đăng nhập, họ tên và mật khẩu ban đầu. Chọn vai trò, kho được truy cập, kho được duyệt nhập và kho được duyệt xuất.
3. Vào **Hàng hóa → Thêm hàng hóa**: chỉ cần mã, tên, đơn vị. Định mức và các trường tự khai báo nằm trong phần thông tin bổ sung.
4. Nhân viên lập phiếu nhập; một tài khoản khác đủ quyền duyệt. Quản trị viên không tự duyệt phiếu chính mình lập.

## Đăng nhập & mật khẩu

Tên đăng nhập do quản trị viên đặt. Mật khẩu ban đầu và mật khẩu người dùng tự đổi không có quy định tối thiểu độ dài hay tổ hợp ký tự, theo lựa chọn của chủ dự án. Không cho mật khẩu rỗng. Mật khẩu luôn dùng cơ chế băm của Django. Nhân viên vào **Đổi mật khẩu**, nhập mật khẩu hiện tại và nhập xác nhận mật khẩu mới; không được đổi tên đăng nhập hoặc tự cấp quyền. Sửa nhân viên để trống ô mật khẩu sẽ giữ mật khẩu cũ.

## Làm việc hằng ngày

- Chọn kho đang xem ở góc trên. Bộ lọc được giữ khi chuyển sang trang tổng quan, tồn, báo cáo, thẻ kho và danh sách phiếu.
- **Nhập kho**: kho nhận → tìm hàng bằng mã/tên (có thể gõ không dấu) → số lượng/đơn giá → Lưu & chờ duyệt.
- **Xuất kho**: kho xuất → chọn hàng → xem số có thể xuất → nhập số lượng → lưu. Hệ thống chặn thiếu tồn ngay khi tạo phiếu; kiểm tra lần nữa bằng khóa giao dịch khi duyệt.
- **Chuyển kho**: kho xuất và kho nhận → hàng/số lượng → chờ người duyệt xuất; sau đó quản lý kho nhận xác nhận. Số liệu giữa hai bước theo dõi trạng thái chờ nhận.
- **Mượn & trả**: lập lệnh cho mượn bằng tồn khả dụng. Bên nhận có tồn mượn tạm bị khóa, không dùng để xuất hoặc cho mượn tiếp. Muốn trả, bấm **Trả hàng** ngay tại lệnh gốc; kho và các dòng hàng còn mượn được điền sẵn. Có thể giảm số lượng để trả từng phần. Giá trị trả giữ nguyên giá trị hàng mượn.
- **Kiểm kê**: nhập số thực đếm của tồn thường, ghi lý do; không cộng hàng mượn tạm.
- **Điều chỉnh tồn**: từ trang Tồn kho, bấm Điều chỉnh tồn; nhập số tăng/giảm và lý do. Không điều chỉnh xuống âm.
- **Nhập từ Excel**: tải mẫu → chọn kho/file → kiểm tra và xem trước → tạo phiếu chờ duyệt. Không tự ghi sổ từ file.

## Duyệt phiếu

Trang **Duyệt phiếu** chỉ hiển thị phiếu người dùng có thể xử lý theo kho, loại nghiệp vụ và giai đoạn. Phiếu do chính người dùng lập được loại khỏi hàng chờ của người đó. Mở phiếu để kiểm tra hàng, người lập, nội dung rồi bấm duyệt. Hủy hộp xác nhận không làm khóa nút duyệt.

Người lập xem **Quản lý phiếu → Phiếu tôi lập**. Chi tiết phiếu cho biết người được phân công duyệt, cho sửa khi chưa duyệt và giữ lịch sử khi đã xử lý. Lưu lại cùng một lần gửi phiếu không tạo thêm phiếu trùng.

## Báo cáo

Tổng quan có nhập và xuất theo khoảng ngày; giá trị tồn là số **hiện tại**, không phải số cuối kỳ lịch sử. Biểu đồ dùng các giao dịch đã xác nhận và phân tách hàng mượn. Không cộng số lượng có đơn vị khác nhau vào một số tổng.

Tồn kho và thẻ kho xuất CSV, mở được bằng Excel. CSV có một dấu BOM UTF-8 duy nhất, không có ký tự thừa đầu mỗi dòng; các chuỗi có thể bị Excel hiểu là công thức được xử lý khi xuất. Danh sách phiếu/hàng hóa có tìm kiếm và phân trang.
