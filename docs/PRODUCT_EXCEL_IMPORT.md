# Hàng hóa Excel và phân bổ nhập kho

Mở **Danh mục hàng hóa → Thêm mã hàng bằng Excel → Tải mẫu Excel**. Điền trang **Hàng hóa** từ dòng 2, tải lên xem trước rồi xác nhận. File tối đa **500 dòng / 5 MB**, định dạng `.xlsx`; mã hàng, QR và mã kho định dạng Text. Mẫu cũ không có cột kho vẫn dùng được.

## Danh mục và phân bổ

- Bắt buộc: Mã hàng, Tên hàng, Đơn vị tính. Thuộc tính khác, định mức cảnh báo và trường bổ sung là tùy chọn. QR tự động hoặc tự nhập theo quy tắc QR suốt vòng đời đã có.
- **Ba cột Mã kho nhập, Số lượng nhập, Đơn giá nhập cùng để trống:** chỉ tạo danh mục và QR, không tạo phiếu hoặc tồn.
- **Muốn nhập theo kho:** điền đủ ba cột; số lượng thực nhận đạt yêu cầu phải dương, tối đa 3 số lẻ; đơn giá không âm, tối đa 4 số lẻ. Miễn phí ghi rõ 0. Lấy mã tại trang **Danh sách kho** trong mẫu, không điền tên kho.
- Một mã phân bổ nhiều kho: lặp mã ở các dòng **khác kho**, giữ nguyên toàn bộ tên, đơn vị, QR và thông tin hàng hóa. Hệ thống chỉ tạo **một sản phẩm / một QR**, rồi tạo dòng nhập ở mỗi kho. Không lặp cùng mã trong cùng kho; sửa số lượng tại dòng đó.
- Chỉ tạo mã mới. Mã đã có trong danh mục cần dùng **Nhập kho → Lập phiếu nhập bằng Excel**; không tự ghi đè thông tin hoặc QR đã sử dụng.
- Định mức tồn tối thiểu chỉ dùng cảnh báo, không phải số lượng nhập. Nếu có thiếu/hỏng so với chứng từ, lập phiếu nhập chi tiết tại Nhập kho để ghi đầy đủ số theo chứng từ, số thực nhận, phần không nhận và lý do.

## Phiếu nhập và duyệt

Màn hình xem trước liệt kê từng dòng cùng kho nhận, số lượng, đơn giá; tóm tắt số mã, giá trị và số phiếu dự kiến theo kho. Tiền làm tròn giống quy trình ghi sổ. Ngày nghiệp vụ là hôm nay.

Xác nhận tạo mã và phiếu **trong một giao dịch**. Mỗi kho có phiếu riêng; trên 50 mã/kho tự chia thành nhiều phiếu, tối đa 50 dòng/phiếu. Tất cả là **phiếu nháp chờ duyệt**, không cộng hoặc giữ tồn. Có lịch sử tạo, người lập, cấp duyệt và thông tin nguồn file/dòng Excel.

Trang kết quả có liên kết đến từng phiếu và danh sách của cả lượt nhập (có phân trang). Danh sách lượt nhập gồm các kho còn trong phạm vi được cấp quyền, độc lập với bộ lọc kho trước đó. Có thể mở phiếu để bổ sung hóa đơn theo đợt nhập, kiểm tra và duyệt theo cơ chế hiện có. Người lập thường không tự duyệt; admin tự duyệt phải xác nhận cảnh báo. Kho đang kiểm kê cho tạo nháp nhưng chặn ghi sổ đến khi được mở khóa. Ngày đã qua phải mở sửa kiểm tra lại theo chính sách ngày hôm nay.

## Quyền và an toàn dữ liệu

Admin có toàn quyền. Tài khoản khác cần **Danh mục hàng hóa: Thêm hàng hóa**; nếu kèm kho còn cần **Tạo phiếu nhập kho** và phạm vi tại đúng kho. Danh sách kho trong mẫu chỉ cung cấp kho được phép sử dụng. Không tự tạo kho từ chuỗi trong Excel.

Xem trước không ghi dữ liệu, gắn người dùng và lượt nhập, hết hạn sau 30 phút. Khi xác nhận, kiểm tra lại quyền, mã trùng, QR, trường bổ sung, kho và ngày. Ghi nhận ID kho ở bước xem trước để không chuyển sang kho khác nếu mã kho bị đổi/tái sử dụng. Chỉ dùng dữ liệu xem trước ở máy chủ; bỏ qua số lượng/kho giả gửi theo nút xác nhận.

Tệp sai một dòng thì không ghi dở danh mục hay phiếu. Lỗi ở phiếu sau cũng hoàn tác các phiếu trước. Gửi lại hoặc xác nhận đồng thời không tạo thêm mã / phiếu trùng. Mã QR không đổi theo kho. Các giới hạn ZIP/XML, công thức, độ chính xác và dữ liệu văn bản vẫn áp dụng; không tải ảnh/tệp từ URL trong Excel. Google Drive chưa kết nối không cản trở tạo mã và phiếu; ảnh/hóa đơn thêm riêng theo quyền lưu trữ.

## Kiểm chứng

Đã đạt **246/246 kiểm thử PostgreSQL**, gồm **18 kiểm thử phân bổ kho** và 23 kiểm thử Excel danh mục trước đó. Bộ kiểm thử kiểm tra cả luồng cũ và mới, gồm template thật, mẫu cũ, một mã nhiều kho, QR thủ công/auto, đơn giá 0 và làm tròn, lỗi từng dòng, quyền/kho bị thu hồi, mã kho được tái sử dụng, ngày hết hạn, lỗi ở phiếu thứ hai, gửi lại/đồng thời, 500 dòng tạo 10 phiếu với số truy vấn giới hạn, khóa kiểm kê và cấp duyệt. Trình duyệt dùng dữ liệu riêng: tải mẫu, xem trước, tạo ba mã / hai phiếu, chưa cộng tồn trước duyệt, người cấp cao hơn duyệt đúng giá trị ở từng kho; bố cục 320–1440px. Không nhập thử vào dữ liệu công ty.

Không có migration hoặc dependency mới. Khi phát hành, kiểm tra mã release, health, trang đăng nhập, CSS và yêu cầu đăng nhập của các đường dẫn liên quan; không coi kiểm tra chỉ đọc là nghiệm thu CRUD trên dữ liệu thật.
