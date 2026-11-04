# Trò chuyện Groq Free trong phần mềm

Chủ phần mềm đồng ý phương án Groq Free ngày 04/11/2026 và yêu cầu cập nhật bản chính sau khi thực hiện. Giữ yêu cầu không tự dùng API trả phí. Đây là mô hình GPT-OSS do Groq phục vụ, không phải dịch vụ ChatGPT/Plus. Chỉ ghi nhận đã gọi AI thật khi có bằng chứng từ tài khoản/khóa thực; test giao thức không phải kiểm chứng chất lượng mô hình.

## Kết nối

Admin tạo tài khoản tại https://console.groq.com/, giữ tổ chức ở gói **Free**, bật **Zero Data Retention** trong Settings → Data Controls và tạo khóa API tại https://console.groq.com/keys.

Trong Render → dịch vụ **kiemsoatnoibolemon** → Environment:

| Biến | Giá trị |
| --- | --- |
| `GROQ_API_KEY` | Khóa Groq riêng, thường bắt đầu `gsk_`; không gửi vào chat hoặc commit Git |
| `GROQ_FREE_ZDR_CONFIRMED` | `1` sau khi đã kiểm tra tổ chức Free và bật ZDR |

Lưu và đợi Render cập nhật. Mở Trợ lý → Trò chuyện AI → kiểm tra trạng thái cấu hình, đồng ý gửi nội dung tới Groq rồi hỏi một câu không có dữ liệu công ty để thử. Trạng thái “đã cấu hình” chưa xác minh khóa/hạn mức bằng một lần gọi thực. Admin cần xem đúng tổ chức và hạn mức trong Groq Console. Ứng dụng không có API chính thức để tự chứng minh tổ chức vẫn ở gói Free hoặc ZDR vẫn bật; cờ trên là xác nhận của người cấu hình, không phải kiểm tra thanh toán tự động.

Dừng dịch vụ bằng cách bỏ `GROQ_FREE_ZDR_CONFIRMED` hoặc xóa khóa. Thiếu/sai định dạng khóa hoặc thiếu xác nhận thì chặn gọi Groq. Không tự thêm thẻ, nâng gói, thay mô hình hoặc đổi nhà cung cấp. Nếu chủ tài khoản tự nâng gói/đổi chính sách ngoài phần mềm thì cần rà soát lại; không tuyên bố miễn phí vô điều kiện hoặc vĩnh viễn.

## Sử dụng và quyền

Nút trên cùng và biểu mẫu cũ giữ nguyên. Trong cùng khung có **Tra cứu nội bộ** (mặc định) và **Trò chuyện AI**. Cần quyền mới `assistant_chat`; cấp quyền này tự bao gồm `assistant_use`, không bao gồm quyền nghiệp vụ khác. Admin có như các chức năng còn lại; không tự cấp quyền mới cho tài khoản nhân viên cũ.

Trò chuyện hỗ trợ nhiều lượt văn bản, cập nhật câu trả lời tăng dần. Nhớ một vài lượt gần nhất trong cùng trang, ngữ cảnh hết hạn 10 phút; không hứa nhớ dài hạn hoặc tiếp nối trên máy/trang khác. Không có đọc tệp, ảnh, web thời gian thực hoặc thực thi công cụ trong bản đầu. Câu trả lời có thể sai; không cam kết tương đương ChatGPT.

Số liệu nhận diện được qua bộ tra cứu nội bộ vẫn tính bằng máy chủ, kiểm tra quyền/kho hiện hành và hiển thị trực tiếp, không chuyển sang mô hình để viết lại. Số liệu tự tra không tự đưa vào lịch sử gửi Groq. Các hướng dẫn phần mềm được rà soát có thể bổ sung cho prompt. Lịch sử bên ngoài chỉ có nội dung người dùng tự nhập và câu trả lời AI; dữ liệu tự nhập có thể chứa thông tin công ty nên thông báo này nằm ngay trong lựa chọn đồng ý gửi.

## Giới hạn miễn phí

Chỉ gọi endpoint cố định `https://api.groq.com/openai/v1/chat/completions`, mô hình `openai/gpt-oss-120b`. Không gọi OpenAI hoặc cho người dùng nhập URL/model tùy ý. Đối chiếu tài liệu Groq ngày 04/11/2026: Free của mô hình này công bố 30 yêu cầu/phút, 1.000/ngày, 8.000 token/phút, 200.000 token/ngày, dùng chung theo tổ chức/mô hình; hạn mức thực tế trong Console là nguồn quyết định và có thể khác.

Ứng dụng khởi đầu bảo thủ hơn: tối đa 100 yêu cầu/tổ chức/ngày, 20/người/ngày, 12 yêu cầu/tổ chức/phút, 6/người/phút, 100.000 token/tổ chức/ngày, 40.000 token/người/ngày; một lần suy luận đồng thời. Ngày tính UTC, tương đương đổi ngày lúc 07:00 Việt Nam. Giữ chỗ token theo số byte prompt + giới hạn đầu ra + phần dự phòng; chỉ trả phần giữ chỗ thừa khi nhận usage hợp lệ sau trả lời hoàn chỉnh. Khi lỗi/ngắt/dừng/usage không xác định, giữ nguyên phần dự phòng để không nới hạn mức sai. Vì vậy có thể hết hạn mức phần mềm sớm hơn mức Groq công bố. Nhà cung cấp tiếp tục áp TPM/TPD thực tế; HTTP 429 dừng lượt, không tự retry hoặc fallback trả phí.

Một yêu cầu đang chạy không giữ worker HTTP chờ Groq. HTTP trả mã yêu cầu nhanh; thread nền có hạn thời gian đọc luồng Groq, giao diện lấy bản nội dung mới bằng những yêu cầu ngắn. Một lease trong PostgreSQL giới hạn suy luận chung giữa hai worker Gunicorn. Các yêu cầu đồng thời vượt khả năng được báo bận, không đưa vào hàng đợi vô hạn. Lỗi/khởi động lại được nhận diện qua lease, không gửi lại tự động. Vẫn phải benchmark tải thật sau khi kết nối, không chỉ dựa vào test giao thức.

## Dữ liệu và bảng riêng

Chỉ thêm ba bảng trong app `ai_assistant`: quota ngày, lease và yêu cầu tạm. Không thay models/services của kho, chat nhân viên hay sai lệch. Không thêm thư viện chạy mới; HTTPS/TLS dùng thư viện chuẩn, mã hóa dùng cryptography đã có.

Prompt/đầu ra tạm được mã hóa Fernet bằng khóa dẫn xuất có miền riêng từ SECRET_KEY. Yêu cầu/ngữ cảnh hết hiệu lực sau 10 phút; các hàng hết hạn được dọn khi tạo yêu cầu AI mới, không hứa xóa vật lý đúng phút nếu ứng dụng không có hoạt động. Quota quá hai ngày cũng chỉ dọn trong bảng AI. Không tự ghi hội thoại vào Sheets/Drive hoặc lưu lâu dài vào database. SECRET_KEY thay đổi làm ngữ cảnh tạm cũ không đọc được.

Lượt hỏi gắn tài khoản và phiên đăng nhập, CSRF và quyền hiện hành. Admin cũng không xem/hủy yêu cầu AI của tài khoản khác. Token hội thoại mã hóa và xác thực tại máy chủ, không chấp nhận `messages/system` do trình duyệt tự khai. Không lấy ô biểu mẫu chưa lưu, mật khẩu, tệp, nội dung chat nhân viên hay toàn bộ database. Không dùng URL hoặc SQL của mô hình. Không đưa API key vào HTML/JS/lỗi/log. Không theo redirect với Authorization. Chỉ hiển thị delta nội dung, bỏ reasoning/tool calls. UI dùng textContent. Lỗi nhà cung cấp chỉ đổi thành mã thông báo cố định.

## Kiểm chứng/phát hành

Chạy toàn bộ test hiện có và test cloud mới trên PostgreSQL riêng; kiểm tra migration, lint, JS, CSS, static và diff ngoài phạm vi. Test bao gồm chưa cấu hình, quyền mới không lan sang tài khoản cũ, CSRF, đồng ý gửi, riêng tư giữa người dùng/phiên, lịch sử mã hóa, idempotency, quota dùng chung, usage, hủy, mất worker, lỗi/redirect/429 và dữ liệu nghiệp vụ không đổi.

Dùng Gunicorn hai worker với adapter giao thức giả chỉ trong máy thử để kiểm tra HTTP nghiệp vụ vẫn trả lời khi inference đang chạy, cập nhật từng đoạn, hỏi tiếp, lỗi và hủy. Báo cáo/ảnh phải ghi rõ đây là mô phỏng transport, không phải phản hồi Groq thật. Đo chất lượng và độ trễ thật cần khóa thực ở tài khoản Free đã xác nhận; thiếu khóa không được đánh dấu kết nối AI thành công. Bản chính có thể chứa phần tích hợp nhưng phải báo chưa kết nối khi chưa đủ cấu hình.

Nguồn: [giới hạn](https://console.groq.com/docs/rate-limits), [thanh toán](https://console.groq.com/docs/billing-faqs), [dữ liệu/ZDR](https://console.groq.com/docs/your-data), [hội thoại/stream](https://console.groq.com/docs/text-chat), [API reference](https://console.groq.com/docs/api-reference).
