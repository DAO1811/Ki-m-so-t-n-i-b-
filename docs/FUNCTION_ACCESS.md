# Admin toàn quyền, cấp quyền riêng cho từng tài khoản

Quy tắc mới do chủ dự án chốt sau bản kiểm kê QR: **admin dùng tất cả chức năng; tài khoản khác chỉ dùng những mục admin cấp**. Quy tắc này thay phần mô tả trước đây rằng admin chưa tự có quyền duyệt điều chỉnh.

## Cách cấp quyền

1. Admin vào **Nhân viên & quyền → Thêm nhân viên / Sửa**.
2. Đặt tên đăng nhập và mật khẩu ban đầu, hoặc để trống mật khẩu khi sửa để giữ mật khẩu cũ.
3. Trong **Quyền từng chức năng**, chỉ đánh dấu mục được xem và việc được làm. Có các nhóm nhập, xuất, chuyển, cho mượn, trả, kiểm kê, điều chỉnh, danh mục, tồn, thẻ kho, báo cáo và tiện ích.
4. Chọn kho được truy cập, kho được duyệt nhập/nhận liên kho, kho được duyệt xuất/chuyển đi/mượn/trả. Quyền nghiệp vụ và phân công kho phải cùng phù hợp.
5. Lưu. Quyền mới áp dụng từ lần truy cập tiếp theo của tài khoản, không cần họ đăng xuất. Bản sửa quyền có người thực hiện, thời điểm và danh sách quyền trước/sau trong nhật ký quản trị; không ghi mật khẩu.

Tài khoản mới không có quyền nghiệp vụ mặc định. Vẫn đăng nhập, đăng xuất và đổi mật khẩu được; trang đầu chỉ chào người dùng và hướng dẫn chọn công việc đã được cấp. Chọn một thao tác sẽ chọn kèm các quyền xem cần để hoàn thành việc đó; bỏ quyền xem trên giao diện sẽ bỏ thao tác phụ thuộc. Không có thao tác nào tự kéo theo quyền duyệt khác.

Ví dụ chỉ cấp **Nhập kho → Lập/sửa phiếu của mình**, chọn kho A: nhân viên xem danh mục để chọn hàng, lập phiếu nhập kho A, xem phiếu của mình; không có quyền xuất, duyệt nhập, kiểm kê hoặc báo cáo. Người có quyền xem đơn thuần không lập/sửa/hủy phiếu được. Các quyền xem tồn/giá trị, xem thẻ kho, báo cáo, xuất CSV, hóa đơn và in QR cũng cấp riêng.

## Các nguyên tắc giữ nguyên

- Admin không cần đánh dấu từng quyền hay phân công từng kho; mọi chức năng hiện tại và chức năng được bổ sung vào danh mục quyền sau này đều thuộc quyền admin.
- Theo thay đổi ngày 19/10/2026, admin được tự duyệt sau cảnh báo và xác nhận, có ghi lịch sử riêng. Tài khoản thường cần cấp cao hơn người lập và không tự duyệt/ngang cấp/ngược cấp. Mọi tài khoản vẫn không được âm tồn, sửa số đã ghi sổ hoặc xóa lịch sử. Xem [cấp duyệt và cơ cấu mới](APPROVAL_HIERARCHY.md).
- Tài khoản khác muốn duyệt điều chỉnh kiểm kê phải được admin cấp **Điều chỉnh tồn → Duyệt kiểm kê/điều chỉnh (Tổng giám đốc)**. Đây là quyền duyệt toàn công ty; không tự có từ vai trò quản lý kho. Chốt biên bản vẫn chỉ tạo phiếu chênh lệch; phiếu được người đủ quyền duyệt mới cập nhật tồn.
- Quyền sửa thông tin kho của tài khoản thường không cho sửa người được truy cập/duyệt kho. Những phân công này chỉ admin thay đổi. Tài khoản được cấp xem nhân viên chỉ xem danh sách, không cấp quyền hay sửa tài khoản.
- Quản lý tài khoản/phân quyền, kết nối Google Drive và khu vực quản trị hệ thống dành cho admin. Cờ kỹ thuật `is_staff` hoặc các quyền Django cũ không mở đường vòng cho tài khoản thường.
- Bỏ phạm vi kho thì người lập cũng không còn được mở hồ sơ kho đó chỉ vì từng tạo phiếu ở đó. Quyền Tổng giám đốc ở trên là ngoại lệ có chủ đích cho biên bản/điều chỉnh toàn công ty.

## Kiểm soát phía máy chủ

Menu, nút, đường dẫn trực tiếp, API, tải hồ sơ và CSV dùng cùng danh mục quyền. Không chỉ ẩn nút. Danh sách phiếu và hồ sơ hàng hóa lọc cả loại nghiệp vụ được xem và kho được giao. Chỉ xem hàng hóa không tự lộ số tồn hoặc hóa đơn.

Bảng quyền có phiên bản chống hai cửa sổ sửa cùng tài khoản: bản cũ không ghi đè bản đã lưu mới, kể cả mật khẩu. Nếu có thông báo dữ liệu đã đổi, tải lại và kiểm tra trước khi lưu tiếp.

Các nhóm Django cũ được giữ như dữ liệu kế thừa, không quyết định quyền vận hành sau nâng cấp. Migration chuyển một lần những quyền đã được cấp và phân công kho cũ sang bảng quyền mới để giảm gián đoạn. Không cấp quyền duyệt điều chỉnh cho người quản lý thường. Admin cần rà lại bảng từng người sau phát hành; tài khoản cũ chưa có vai trò hoặc phân công có thể không có mục nghiệp vụ.

## Kỹ thuật và kiểm tra

- `FunctionAccess` lưu mã quyền ổn định, người cập nhật, phiên bản và thời điểm. Danh mục ở `inventory/access.py`; menu ở `inventory/navigation.py`; `permission_middleware.py` chặn mặc định các màn hình nghiệp vụ chưa được ánh xạ quyền.
- Khi thêm phân hệ tương lai, thêm quyền tương ứng và ánh xạ kiểm tra. Admin tự có quyền mới; tài khoản khác không tự nhận quyền mới từ nhóm rộng.
- Migration mới của đợt này: 0015–0016, kế thừa migration 0008–0014 của hai đợt chưa phát hành trước. Phát hành từ main schema 0007 cần backup và thử nâng cấp toàn chuỗi.
- [Kết quả kiểm tra đợt quyền](FUNCTION_ACCESS_VALIDATION.md), [quy trình phát hành](RELEASE_PROCESS.md), [đề xuất nhân sự chờ duyệt](HR_COMPANY_PROPOSAL.md).
