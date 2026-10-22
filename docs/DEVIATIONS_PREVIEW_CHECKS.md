# Bản thử Xử lý sai lệch — kiểm tra trước khi phát hành

Ngày kiểm tra: 22/10/2026. Nhánh: `preview/shared-review`. Mã nghiệp vụ mới: `35ac19e` (kế thừa `0ba0e2b`, `ba3d651`, `0f7654a`). **Chưa phát hành lên main/Render.**

## Phạm vi đợt bổ sung này

Chỉ xây phân hệ mới theo khung chủ phần mềm đã duyệt. Không đổi luồng nhập/xuất/chuyển kho, mượn trả, kiểm kê, Excel, QR, danh mục hàng hóa hoặc giao diện đăng nhập. Những thay đổi kiểm kê đã chuẩn bị ở các commit trước vẫn thuộc công việc trước đó; không phát triển thêm chúng trong đợt này.

Các điểm tích hợp dùng chung chỉ thêm đường vào mới:

- Thêm nhóm quyền ghi cho sai lệch vào bộ chọn quyền hiện có; không ghi hoặc cấp lại quyền của tài khoản cũ.
- Thêm menu con, nhãn trang và xử lý phân quyền cho URL của app `deviations`.
- Thêm loại tệp `deviation` và nhánh thư mục Drive riêng; giữ các nhánh hàng hóa/hóa đơn cũ.
- Thêm stylesheet với selector riêng; không sửa các file CSS nguồn cũ hoặc template màn hình cũ.

Mọi bảng mới thuộc `deviations_*`. Migration của app chỉ tạo bảng, nhóm danh mục, cấu hình mặc định tắt xử lý và revision danh mục; không UPDATE/DELETE dữ liệu kho/tài khoản.

## Có thể xem trên bản thử

- Tổng quan và danh sách: tìm kiếm, bộ lọc trạng thái/nhóm/mức độ; hồ sơ của tôi, liên quan đến tôi, quá hạn, đã kết thúc.
- Một mã hồ sơ xuyên suốt, năm phần thông tin, người phụ trách và lịch sử trước/sau khi thay đổi.
- Ba loại hành động: tức thời, khắc phục, phòng ngừa; người thực hiện, hạn và kết quả riêng.
- Kế hoạch, thực hiện, đề nghị/quyết định gia hạn, đánh giá hiệu quả và kết thúc/mở lại. Các thao tác xử lý chỉ xuất hiện khi cấu hình được mở và đúng quyền.
- Ảnh/PDF, tệp giữ lịch sử, bản in/PDF hồ sơ và báo cáo tổng hợp ban đầu.
- Admin cấu hình có phiên bản. Hồ sơ đã tiếp nhận giữ quy tắc tại thời điểm tiếp nhận. Cảnh báo và checkbox khi Admin tự xác nhận hồ sơ liên quan chính mình.

Bản Docker có hồ sơ **DEMO**, nhân viên/phòng ban giả lập. Các quy tắc giả lập đã được tắt lại sau khi thử hết luồng; đây không phải quy trình vận hành công ty đã được chốt.

## Bằng chứng kiểm tra

| Kiểm tra | Kết quả |
| --- | --- |
| Toàn bộ ứng dụng, PostgreSQL 17 | 361 kiểm thử đạt ở bản nghiệp vụ đầu tiên `0ba0e2b` |
| Toàn bộ ứng dụng, PostgreSQL 18 | 363 kiểm thử đạt sau bổ sung kiểm tra tích hợp và định dạng template `ba3d651` |
| Kiểm thử riêng phân hệ bản `35ac19e` | 36 kiểm thử; có thêm tình huống đánh giá cùng phút với gửi ghi nhận, không buộc chờ đồng hồ sang phút |
| Đồng thời PostgreSQL | Hai lần gửi, gửi tranh chấp hủy, hai người sửa: chỉ một lần lưu thành công, lần còn lại bị từ chối do revision cũ |
| Phân quyền / toàn vẹn | Không có quyền ghi thì bị chặn; không sửa chéo công việc/hồ sơ; trạng thái đóng không sửa trực tiếp; không ảnh hưởng Balance/Document/Movement/Product |
| Tệp | Kiểm tra loại/nội dung/dung lượng, băm đối chiếu, tải riêng tư; Drive lỗi không tự lưu vào database sản xuất |
| Drive và chức năng cũ | Kiểm thử giả lập xác nhận đúng nhánh thư mục mới; đường dẫn lưu hàng hóa và hóa đơn cũ giữ nguyên |
| Trình duyệt Chromium | Đăng nhập, tạo/gửi, ảnh và đọc riêng tư, phân công, xác minh, kế hoạch, cảnh báo tự duyệt, thực hiện, đánh giá, kết thúc, PDF, sáng/tối, màn hình 390 px |
| Tài nguyên | Ruff, Django check, migration check, CSS bundle và collectstatic đạt; không bổ sung JavaScript |

GitHub Actions sẽ chạy lại toàn bộ trên đúng HEAD được push. Kiểm tra SHA và trạng thái tại PR bản thử trước khi đề nghị phát hành.

## Giới hạn cần biết

- Cấp xác nhận, tính độc lập, yêu cầu cấp cao hơn và số lần gia hạn phải được công ty chốt rồi Admin cấu hình. Chưa tự áp thời hạn/SLA, cơ chế email hoặc chế tài.
- Tất cả nhân viên hoạt động xem được mọi hồ sơ và bằng chứng sai lệch theo quyết định của chủ phần mềm. Quyền này không mở phiếu gốc trong kho.
- Báo cáo ban đầu là tổng hợp số hồ sơ/tiến độ/theo nhóm; phân tích xu hướng, tái diễn và SLA chi tiết chưa nằm trong bản nền.
- Đọc/ghi Google Drive thật chưa được thử bằng hồ sơ công ty. Kiểm thử mạng dùng giả lập; Docker cố ý tắt kết nối thật và lưu tệp minh họa riêng.
- Chưa xác minh VS Code/Docker Desktop trên máy Windows của chủ phần mềm. Không cung cấp link localhost như một địa chỉ public.
- Bản chính chỉ được cập nhật sau khi chủ phần mềm đã xem và đồng ý đúng bản thử cụ thể. Không merge, gọi deploy hook hoặc thay đổi Render trong đợt này.

Cách bảo trì: [deviations/README.md](../deviations/README.md). Cấu hình chạy thử: [PREVIEW_IN_VSCODE.md](PREVIEW_IN_VSCODE.md).
