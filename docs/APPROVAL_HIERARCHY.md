# Cấp duyệt và cơ cấu vận hành

Quy tắc chủ dự án chốt ngày 19/10/2026: **Nhân viên < Leader < Trưởng phòng < Admin tổng**. Một người cấp cao hơn và đủ quyền duyệt là đủ. Không chạy chuỗi duyệt tuần tự qua mọi cấp.

## Tài khoản và quyền

Tại **Quản trị → Tài khoản & phân quyền**, admin nhập chức vụ/chức danh, chọn cấp duyệt, đánh dấu quyền công việc và kho được giao trên một màn hình. Chức danh là nội dung mô tả; cấp duyệt là lựa chọn có kiểm soát, không tự sinh quyền. Mọi cấp đều lập phiếu được khi có quyền lập loại phiếu đó. Tài khoản mới không nhận quyền nghiệp vụ tự động.

- Nhân viên: lập và theo dõi công việc được cấp, không duyệt.
- Leader: có thể duyệt phiếu nhân viên, cần đúng quyền loại phiếu và phân công kho.
- Trưởng phòng: có thể duyệt phiếu nhân viên/Leader, vẫn cần đúng quyền và kho.
- Admin tổng: xem tất cả phiếu và có toàn quyền, không cần cấp từng chức năng/kho. Cấp này gắn với tài khoản superuser; gửi giá trị cấp 40 vào form tài khoản thường không nâng quyền admin.

Người thường không tự duyệt, duyệt ngang cấp hoặc ngược cấp. Quyền duyệt kiểm kê/điều chỉnh vẫn là quyền riêng do admin giao cho Tổng giám đốc; chức danh Trưởng phòng hoặc phân công quản lý kho không tự mở quyền này.

## Ngoại lệ admin tự duyệt

Theo yêu cầu rõ ràng của chủ dự án, admin được tự duyệt phiếu do mình lập. Trang phiếu hiển thị cảnh báo và ô **Tôi đã kiểm tra và xác nhận tự duyệt phiếu này**; ô không được đánh dấu sẵn. Thiếu xác nhận thì máy chủ từ chối, kể cả gửi POST trực tiếp. Hộp xác nhận thao tác cũng nêu việc tự duyệt. Lịch sử lưu actor, thời điểm, cấp người lập/người duyệt, `admin_self_approved`; giao diện hiển thị **Admin tổng tự duyệt**.

Ngoại lệ không bỏ kiểm tra ngày hôm nay, tồn khả dụng, số lượng, giá trị, chênh lệch kiểm kê, trạng thái, chống gửi lặp hoặc phiếu đã ghi sổ. Mỗi lần xác nhận liên kho của phiếu do admin lập đều phải xác nhận tự duyệt. Chuyển/mượn/trả vẫn có bước giao đi và nhận hàng; đó là hai bước vận hành kho, không phải chuỗi duyệt cấp bậc.

## Theo dõi và xử lý

Admin có trung tâm **Duyệt & xử lý phiếu**: theo dõi phiếu chờ duyệt, chờ nhận, yêu cầu sửa; lọc theo loại, trạng thái, mã phiếu/người lập/chứng từ nguồn; chọn trạng thái Đã ghi sổ/Đã hủy để tra cứu hồ sơ kết thúc. Phiếu của chính admin cũng xuất hiện. Liên kết **Theo dõi toàn công ty** và **Tra cứu tất cả phiếu** xóa lọc kho; nếu đang lọc kho, màn hình thông báo rõ và có nút bỏ lọc.

Tài khoản khác thấy hàng chờ đúng cấp/quyền/kho. Quyền xem độc lập quyền duyệt; mở phiếu thấy lý do chưa được duyệt, không chỉ mất nút. Người đủ quyền yêu cầu sửa; admin hoặc người lập có quyền lập được hủy phiếu chưa chuyển/ghi sổ, bắt buộc lý do. Không cho sửa/xóa giao dịch đã ghi sổ qua màn hình quản trị; sai lệch dùng phiếu điều chỉnh được duyệt.

Các menu được nhóm theo công việc: danh mục, nghiệp vụ, báo cáo, tiện ích, quản trị. Tài khoản/chức vụ/quyền, thông tin tự thêm và Drive nằm trong Quản trị. Menu vẫn được lọc theo quyền thực tế.

## Thông tin tự thêm cho hàng hóa

Màn hình cũ bắt nhập mã kỹ thuật được thay bằng tên thông tin dễ đọc và xem trước ô nhập. Mã lưu trữ tự sinh, không đổi khi đổi tên hiển thị. Giá trị vẫn nằm trong `Product.extra` theo mã cũ, không mất dữ liệu hàng hóa đã nhập. Đổi tên có kiểm tra tên trùng. Chưa bổ sung kiểu số/ngày/danh sách; các ô hiện nhận văn bản và dùng chung cho danh mục hàng hóa.

## Nâng cấp và ràng buộc

Migration 0017 thêm chức danh/cấp duyệt và lưu cấp người lập trên phiếu/phiên kiểm kê. Người đã có quyền duyệt hoặc phân công duyệt kho được chuyển cấp Trưởng phòng để giữ khả năng xử lý; admin cần rà lại chức danh và cấp thực tế từng người. Không tự cấp thêm quyền chức năng. Tài khoản admin giữ cấp cao nhất, tài khoản khác mặc định Nhân viên.

Duyệt so với cấp đã lưu lúc tạo và cấp hiện tại của người lập, lấy mức cao hơn. Hạ cấp người lập không làm phiếu cũ dễ duyệt hơn. Chốt kiểm kê giữ mức đã lưu từ lúc mở phiên. Ghi sổ khóa phiếu và tài khoản/hồ sơ quyền theo thứ tự ổn định, đối chiếu quyền mới nhất trước cập nhật tồn; thay cấp đồng thời không vượt qua kiểm soát.

Trước migration, `safe_migrate` giữ bản chụp mới trong schema riêng `dhd_backup_inventory_0017`; không ghi đè bản 0016 trước đây. Khóa triển khai giữ ổn định giữa phiên bản. Health yêu cầu migration 0017 và snapshot sẵn sàng. Đây là bản phục hồi cùng database, không thay thế backup độc lập.
