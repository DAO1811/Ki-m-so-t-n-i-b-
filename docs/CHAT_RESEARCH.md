# Tham khảo thiết kế và phản hồi công khai — 03/11/2026

Nguồn đọc trực tiếp:

- Zalo Help: https://help.zalo.me/
- Google Play, Messenger: https://play.google.com/store/apps/details?id=com.facebook.orca&hl=vi&gl=VN
- Google Play, Zalo: https://play.google.com/store/apps/details?id=com.zing.zalo&hl=vi&gl=VN
- Unicode 16, bộ dữ liệu emoji: https://unicode.org/Public/emoji/16.0/emoji-test.txt ; giấy phép đi kèm `static/chat-assets/UNICODE-LICENSE.txt`.

Đọc được 3 bình luận hiển thị công khai cho mỗi ứng dụng Google Play trong lần truy cập. Đây là mẫu rất nhỏ, không đại diện người dùng và không xác minh được thiết bị/phiên bản của người bình luận. Feed App Store được thử nhưng không trả bình luận, nên không dùng để kết luận. Không đánh giá hoặc tuyên bố phần mềm này tốt hơn Zalo/Messenger từ mẫu đó.

Các chủ đề ghi nhận từ bình luận Zalo: khó chịu khi tệp cũ không còn, chuông vẫn đổ sau khi chọn nghe, lớp trạng thái che hình. Bình luận Messenger trong mẫu chỉ nêu lỗi chung và cảm nhận, không đủ thông tin xác định lỗi cụ thể. Không chép tên người dùng hoặc bình luận xúc phạm vào phần mềm.

Áp dụng có kiểm chứng:

| Nhu cầu / rủi ro | Thiết kế DHD Connect | Cách kiểm tra |
| --- | --- | --- |
| Tìm lại ảnh và tài liệu | Drive riêng tư, không tự đặt hạn xóa; thư viện tệp, tìm tên và phân trang | Tải lại, hash nội dung, kiểm tra quyền và cursor nhiều tệp cùng tin |
| Cuộc gọi có trạng thái rõ ràng | Server giữ trạng thái mời/tham gia/kết thúc; nhận cuộc gọi đóng lời mời, không cho hai tab chiếm phiên | Hai hoặc nhiều trình duyệt, từ chối/kết thúc/timeout/thu hồi quyền |
| Hạn chế lớp phủ gây phiền | Bộ chọn có nút đóng, không che vĩnh viễn nội dung; không tự bật camera; thông báo không hiển thị nội dung nhạy cảm | Kiểm tra màn hình nhỏ, bàn phím và các modal |
| Tránh gửi trùng, hiểu nhầm đã gửi | Nonce, thông báo lỗi rõ, giữ draft khi mất mạng, đã xem chỉ theo mốc đọc | Retry giống/khác nội dung, lỗi lưu Drive, giới hạn quyền |
| Nhiều biểu cảm nhưng giao diện nhẹ | Emoji đóng gói tại ứng dụng, tìm theo nhóm và tải khi mở; atlas sticker riêng dùng chung | Kiểm tra bộ chọn, mạng lỗi và bố cục không chồng nút |

Giữ bố cục quen thuộc: danh sách bên trái, nội dung ở giữa, ô soạn dưới, tìm kiếm và gọi ở đầu. Thiết kế màu vàng/bạc phù hợp phần mềm DHD, không sao chép thương hiệu hoặc sticker độc quyền. Sticker minh họa được tạo riêng; emoji theo Unicode. Chất lượng được báo bằng những hành vi đã thử, không bằng lời khẳng định “đỉnh nhất”.
