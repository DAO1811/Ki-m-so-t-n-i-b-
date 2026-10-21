# Nhập hàng vào nhiều kho từ Excel

Vào **Nhập kho → Lập phiếu nhập bằng Excel → Tải mẫu nhập kho theo kho**. Đường dẫn tải `/import/receipt/template/`, tên file **mau-nhap-kho-theo-kho.xlsx**, riêng với mẫu tạo mã hàng tại Danh mục hàng hóa.

Mẫu nhận hàng đã có trong danh mục, gồm 7 cột: `ma_hang`, `so_luong`, `don_gia`, `sl_chung_tu`, `sl_khong_nhan`, `ly_do`, **`ma_kho` (cột G)**. Trang **Danh sach kho** chỉ liệt kê mã/tên kho trong phạm vi được cấp quyền; trang **Huong dan** giải thích cách nhập.

- Có `ma_kho`: dòng nhận vào đúng kho đó. Không cần chọn kho chung khi mọi dòng đều đã có mã kho.
- `ma_kho` trống: dùng **Kho nhận chung** trên màn hình; thiếu cả hai sẽ báo lỗi.
- Cùng mã hàng có thể có nhiều dòng khác kho, với số lượng và đơn giá riêng. Không lặp cùng mã ở cùng kho, kể cả một dòng dùng kho chung và dòng kia ghi mã kho tương ứng.
- `so_luong` là số thực nhận đạt yêu cầu. Các trường chứng từ/không nhận/lý do giữ quy tắc thiếu/hỏng hiện có; chỉ thực nhận được cộng tồn. Đơn giá miễn phí phải ghi 0.
- Mẫu mới tối đa **1.000 dòng dữ liệu** (không tính tiêu đề), 5 MB. Mỗi kho tự tạo phiếu nhập riêng, tối đa 50 mã/phiếu. Mẫu cũ 3/6 cột vẫn dùng với kho chung, tối đa 50 mã.

Xem trước hiển thị từng kho nhận, từng dòng, giá trị và số phiếu dự kiến. Toàn bộ phiếu được tạo trong một giao dịch; lỗi ở phiếu sau hoàn tác cả phiếu trước. Kết quả có danh sách phiếu của lượt nhập, lọc theo phạm vi quyền và có phân trang. Một phiếu thì mở thẳng chi tiết.

Chỉ tạo phiếu **DRAFT chờ duyệt**, không tạo sản phẩm hoặc đổi QR, không cộng tồn trực tiếp. Cấp duyệt, cảnh báo admin tự duyệt, khóa kiểm kê và ngày hôm nay vẫn áp dụng. Ảnh/hóa đơn bổ sung trên phiếu theo cơ chế lưu trữ hiện có.

Xem trước gắn người dùng, khóa lượt nhập, hạn 30 phút và ngày nghiệp vụ; khi xác nhận kiểm tra lại quyền tạo phiếu, phạm vi kho, ID/mã kho, mã/đơn vị sản phẩm. Phiếu dùng khóa nhập duy nhất, xác nhận lại không tạo thêm. Không tin số lượng/kho giả gửi kèm nút xác nhận từ trình duyệt.

Kiểm tra nâng giới hạn: **77 kiểm thử PostgreSQL đạt** cho nhập theo kho, nhập mẫu cũ và kiểm soát tài sản. Tệp đủ 1.000 dòng tạo đúng 20 phiếu nháp cho hai kho; tệp 1.001 dòng bị từ chối cả khi khai báo sai kích thước trang tính; lỗi ở dòng dữ liệu cuối không tạo xem trước một phần. Mẫu cũ 3/6 cột vẫn tối đa 50 mã.

Trình duyệt với dữ liệu cách ly đã tải file mẫu thực tế, điền đủ 1.000 dòng, xem trước và tạo 20 phiếu nháp theo hai kho, mỗi phiếu 50 mã; chưa duyệt nên không có biến động tồn. Kiểm tra bố cục 320–1440px và nút xác nhận trên điện thoại. Không tạo phiếu thử trong dữ liệu công ty. Không thêm migration hoặc dependency.

Rà soát định dạng và xác nhận: **278 kiểm thử PostgreSQL toàn phần mềm đạt**. Bổ sung các ca file XML hỏng, giá trị ô số hỏng, cột/dòng ngoài mẫu dù metadata khai báo thiếu, mã hàng dạng số làm mất số 0 đầu mã, dòng thừa chỉ có giá 0, giá tiền dán dạng chữ, tệp quá 5 MB, thu hồi quyền sau xem trước và CSRF. Tổng số lỗi được hiển thị khi vượt 30 lỗi chi tiết. Hai xác nhận chạy đồng thời trên các kết nối PostgreSQL riêng vẫn tạo mỗi phiếu đúng một lần; gửi kho/số lượng/trạng thái khác qua nút xác nhận không thay đổi bản xem trước.

Đơn giá và số lượng phải là ô số (ví dụ `600000`); ký hiệu tiền chỉ dùng trong định dạng hiển thị, không dán chuỗi `600.000 đ`. Hướng dẫn đã chỉ rõ tên ba cột tùy chọn thay cho cách gọi nhầm “ba cột cuối”. Tên/mã kho trong trang tra cứu được ghi dạng chữ thuần, không thành công thức Excel.
