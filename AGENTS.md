# Quy tắc làm việc và phát hành

- Chủ phần mềm yêu cầu xem và duyệt bản chạy thử trước khi cập nhật bản chính. Quy tắc này thay thế các yêu cầu tự cập nhật trước đó.
- Làm trên nhánh `preview/*` hoặc nhánh tính năng, dùng database thử riêng. Không push/merge vào `main`, gọi deploy hook hoặc thay đổi Render production khi chưa có sự đồng ý cho bản thử cụ thể đã xem.
- Được push nhánh thử để người dùng cập nhật trong VS Code. Không ghi đè chỉnh sửa local của người dùng, không tự reset database hoặc lấy dữ liệu/bí mật production làm mẫu.
- Chuẩn bị kiểm thử, migration, ghi rõ commit và giới hạn trước khi đề nghị phát hành. Chỉ báo cập nhật thành công sau khi xác minh đúng commit production.
- Không thêm phân hệ ngoài phạm vi đã được duyệt. Không tự tạo dịch vụ tính phí.
