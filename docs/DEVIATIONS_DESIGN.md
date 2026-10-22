# Xử lý sai lệch · Phạm vi và bản thiết kế đề xuất

Ngày: 22/10/2026 (Việt Nam). Trạng thái: đang thống nhất nghiệp vụ; chưa triển khai xử lý hồ sơ hoặc thay đổi dữ liệu công ty.

## Đã xác nhận

- Phân hệ **Xử lý sai lệch** ngang cấp **Quản lý kho**, **Quy trình**, **Quản lý nhân sự**.
- Phạm vi mọi sai lệch trong công ty: kho, tài sản, nhân sự, quy trình và các lĩnh vực khác; không chỉ chênh lệch kiểm kê.
- Admin tổng có toàn quyền xử lý tổng; các tài khoản khác phải được cấp quyền theo chức năng. Xem hồ sơ không mặc nhiên có quyền xử lý hoặc duyệt.
- Bản thử phải được xem và đồng ý trước khi đưa lên phần mềm chính; việc cài VS Code đang tạm gác.

## Đề xuất bố cục gọn

Một danh sách hồ sơ là màn hình chính, có nút **Ghi nhận sai lệch**. Bộ lọc theo nhóm, trạng thái, người phụ trách, phòng ban và hạn xử lý. Các tab **Liên quan đến tôi**, **Chờ tôi xử lý**, **Chờ xác nhận**, **Quá hạn** dùng cùng danh sách và cùng quy tắc quyền, tránh các danh sách nhập trùng dữ liệu.

Một hồ sơ có các phần:

1. **Thông tin sai lệch:** mã tự sinh, tiêu đề, nhóm sai lệch, mô tả thực tế, yêu cầu/quy định cần đáp ứng, thời điểm phát hiện, phòng ban/địa điểm liên quan, người ghi nhận; mức ảnh hưởng và giá trị ước tính nếu có.
2. **Căn cứ:** liên kết hồ sơ nguồn khi có, ảnh/PDF và ghi chú. Mỗi liên kết và tệp phải kiểm tra quyền; biết mã/UUID không có nghĩa được mở hồ sơ nguồn.
3. **Kế hoạch xử lý:** người chịu trách nhiệm, người phối hợp, hạn hoàn thành, nguyên nhân, biện pháp khắc phục và cách ngăn tái diễn.
4. **Kết quả và xác nhận:** kết quả thực hiện, bằng chứng, người kiểm tra, kết luận chấp nhận hoặc yêu cầu bổ sung, lý do và thời điểm.
5. **Lịch sử:** người thao tác, thời điểm, trạng thái, nội dung thay đổi và lý do; không ghi đè các kết luận cũ.

Chỉ bắt buộc thông tin cần cho bước đang làm: người ghi nhận không phải điền trước nguyên nhân/kết quả chưa biết. Trường số tiền và thông tin mở rộng chỉ hiện khi có liên quan; không trộn biểu mẫu chi tiết từng nghiệp vụ vào bước ghi nhận ban đầu.

## Đề xuất luồng

**Nháp → Gửi ghi nhận → Tiếp nhận/phân công → Đang khắc phục → Chờ xác nhận → Hoàn tất.**

Người có quyền tiếp nhận có thể trả lại hồ sơ cần làm rõ hoặc kết luận không tiếp nhận, bắt buộc lý do. Người kiểm tra kết quả có thể yêu cầu bổ sung; giữ phiên bản kết quả trước đó. Hồ sơ hoàn tất khóa nội dung kết luận; mở lại phải có quyền và lý do, lưu thành một lượt xử lý mới. Chưa tự thêm cơ chế phạt, bồi thường hoặc khấu trừ lương.

Hạn xử lý và việc quá hạn là thông tin theo dõi, không tự kết luận lỗi của nhân viên. Không tự gửi email hoặc thông báo ra ngoài khi chưa chốt nhu cầu và người nhận.

## Hai quyết định đang chờ chủ phần mềm

1. **Phạm vi xem:** Admin xem tất cả; cần chốt KSNB có xem tất cả hay chỉ hồ sơ được giao/cấp quyền. Hồ sơ nhân sự/tài chính cần giới hạn người xem; tài khoản có quyền vào phân hệ chưa chắc được xem mọi hồ sơ.
2. **Xác nhận hoàn tất:** KSNB xác nhận trực tiếp, hay trưởng phòng duyệt trước rồi KSNB chốt, hay người cấp cao hơn có quyền phù hợp. Cần chốt quy tắc xác nhận hồ sơ do chính người duyệt tạo/thực hiện; ngoại lệ Admin phải có cảnh báo và lịch sử như quy tắc hiện có.

Không dựng dữ liệu hồ sơ hoặc tự chọn một trong các phương án này trước khi có câu trả lời.

## Liên kết với các phân hệ

Hồ sơ sai lệch theo dõi vụ việc và hành động khắc phục. Chênh lệch kiểm kê, phiếu điều chỉnh tồn và các chứng từ kho tiếp tục giữ luồng duyệt và sổ kho hiện có; hoàn tất hồ sơ sai lệch không tự cộng/trừ tồn hoặc sửa phiếu đã ghi sổ. Cập nhật kho, nhân sự hoặc tài chính phải qua chức năng gốc và quyền tương ứng.

Ảnh/PDF dự kiến lưu trong thư mục con riêng của thư mục Drive đã kết nối, phân theo năm/mã hồ sơ; database giữ metadata và liên kết. Không nhân bản file cho từng bình luận/lượt duyệt. Bản thử local dùng dữ liệu minh họa và không truy cập Drive công ty.

## Kiểm tra cần có khi xây nghiệp vụ

- Người không liên quan không xem được hồ sơ/tệp qua danh sách, tìm kiếm, URL, bộ đếm hoặc tải xuống.
- Phân quyền từng thao tác; thu hồi quyền có hiệu lực với phiên đang đăng nhập.
- Gửi lại, duyệt lặp, hai người xử lý đồng thời và thay đổi người phụ trách không tạo kết quả chồng nhau.
- Hồ sơ hoàn tất giữ lịch sử; mở lại hoặc yêu cầu bổ sung không xóa kết luận trước.
- Đính kèm lỗi không báo thành công giả; liên kết nguồn tôn trọng quyền của phân hệ gốc.
- Chốt hồ sơ sai lệch không làm thay đổi sổ kho hoặc hồ sơ nhân sự bằng đường vòng.
