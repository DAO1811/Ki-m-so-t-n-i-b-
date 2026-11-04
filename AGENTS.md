# Quy tắc chủ phần mềm đã xác nhận ngày 03/11/2026

- Khi thêm hoặc sửa một chức năng, tuyệt đối không được làm ảnh hưởng đến chức năng khác. Khoanh phạm vi thay đổi; giữ nguyên dữ liệu, phân quyền, luồng nghiệp vụ và hành vi của các chức năng không thuộc yêu cầu.
- Tách phân hệ mới thành mã nguồn và bảng dữ liệu riêng khi phù hợp. Các điểm tích hợp dùng chung phải nhỏ, có mục đích rõ ràng và có kiểm thử hồi quy bảo vệ chức năng cũ.
- Kiểm tra toàn bộ kiểm thử hiện có cùng kiểm thử cho thay đổi mới; rà soát diff ngoài phạm vi trước khi đề nghị phát hành. Không tuyên bố không ảnh hưởng nếu chưa có bằng chứng kiểm tra.
