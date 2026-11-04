# Trợ lý AI ngay trong màn hình làm việc

Yêu cầu chủ phần mềm chốt ngày 04/11/2026: người dùng đang làm ở mục nào thì mở trợ lý để hỏi ngay tại đó; hỗ trợ hướng dẫn/soạn nội dung và tra cứu theo quyền; không phát sinh phí API; phải xem bản thử trước khi cập nhật chính thức.

## Cách sử dụng và phạm vi

Admin có quyền dùng như các chức năng khác. Tài khoản còn lại cần admin cấp **Trợ lý AI trong phần mềm → Hỏi hướng dẫn và tra cứu theo quyền hiện có**. Quyền này không tự cấp quyền xem kho, danh mục hoặc phiếu. Không tự cập nhật quyền của tài khoản hiện có khi cài bản mới.

Nút **Trợ lý AI** xuất hiện ở các trang dùng layout chính của phần mềm. Bấm mở một khung không modal; trang và biểu mẫu vẫn ở đó. Đóng trả con trỏ về ô đang nhập. Khung chỉ gửi tên đường dẫn đang mở và kho đang chọn, không đọc các ô biểu mẫu chưa lưu, tệp, nội dung chat nhân viên hoặc mật khẩu.

- **Tra cứu trực tiếp** hoạt động không cần mô hình: hướng dẫn đã rà soát và dữ liệu thật từ máy chủ, có nguồn và thời điểm. Không trình bày đây là câu trả lời của mô hình AI.
- **Bật trả lời AI → Tải và bật AI** khởi động Qwen2.5 0.5B qua Transformers.js/WebAssembly ngay trong worker trình duyệt. Câu trả lời tự nhiên/soạn nội dung được xử lý trên thiết bị. Với tra cứu số liệu, ưu tiên kết quả tính trực tiếp của phần mềm, không để mô hình viết lại số liệu. Lần đầu tải khoảng 800 MB mô hình, dùng bộ nhớ và CPU của trình duyệt; máy Windows RAM 8 GB cần kiểm chứng thực tế. Không cần GPU rời; worker dùng một luồng CPU để không thay đổi chính sách cross-origin của toàn ứng dụng. Không yêu cầu cài Ollama hoặc mở phần mềm AI riêng.
- Trình duyệt/bộ nhớ không phù hợp hoặc lỗi tải thì báo rõ và vẫn tra cứu trực tiếp được. Không tự chuyển sang API trả phí hoặc dịch vụ suy luận bên ngoài.
- Có nút dừng và tắt AI để giải phóng worker. Thời gian xử lý và câu trả lời được giới hạn. Lịch sử chỉ ở bộ nhớ của trang, không tự lưu hội thoại/câu trả lời vào database hoặc localStorage. Cache API chỉ cache mô hình công khai.

Đây là Trợ lý AI dùng mô hình Qwen, không phải tích hợp dịch vụ ChatGPT của OpenAI. Chất lượng mô hình nhỏ và tốc độ phụ thuộc thiết bị; không cam kết ngang ChatGPT. Người dùng cần đối chiếu dữ liệu gốc. Chưa thêm tính năng chẩn đoán hồ sơ đầy đủ, đọc tệp hoặc tự hành động.

## Bảo vệ dữ liệu và nghiệp vụ

App riêng `ai_assistant/`, không có model/bảng hoặc migration mới. `/assistant/api/context/` chỉ POST có CSRF và phiên đăng nhập, kiểm tra quyền mỗi lần. Tồn lấy qua `warehouses_for`, phiếu qua `documents_for`; quyền xem danh mục và tồn khác nhau. Kho giả mạo hoặc ngữ cảnh phiếu ngoài quyền bị từ chối. Hồ sơ sai lệch áp dụng quyền xem toàn công ty đã có; không thay các quyền sửa/duyệt riêng.

Nguồn chỉ gồm các trường cần thiết. Không gửi toàn bộ database, dữ liệu chat, tệp Drive hoặc token. Phần tra cứu không truy vấn từ SQL của mô hình. Chỉ đọc số liệu, không gọi dịch vụ tạo/sửa/xóa/duyệt. Mã hàng không có kết quả phải báo không tìm thấy, không thay bằng các dòng hàng khác. Danh sách dài được giới hạn và ghi rõ chưa phải tổng toàn công ty.

Văn bản mô hình hiển thị bằng `textContent`. Nguồn bấm được chỉ lấy từ URL cùng ứng dụng do máy chủ tạo, không lấy URL do mô hình bịa. Thông tin tra cứu là dữ liệu tham khảo, không được dùng làm chỉ thị thay quyền. API trả `private, no-store`.

## Tài nguyên và bản dựng

Không có khóa OpenAI/Gemini và không có endpoint tính phí trong triển khai này. Máy chủ hiện tại không chạy mô hình ngôn ngữ; chỉ truy vấn dữ liệu có giới hạn. SDK chỉ tải khi người dùng đồng ý bật AI, không tải mô hình khi đăng nhập hoặc mở trang.

SDK Transformers.js 3.8.1 cùng ONNX Runtime Web được lưu tại `static/vendor/transformers-3.8.1/`, có SHA256, nguồn, phiên bản và giấy phép đi kèm. `assistant-models.json` pin revision kho mô hình và SHA256 mong đợi của trọng số. Trọng số tải từ Hugging Face qua HTTPS, thư viện WASM phục vụ cùng ứng dụng; nội dung câu hỏi không được gửi tới các máy chủ tải mô hình. Không đổi các revision này mà không kiểm tra lại tương thích/giấy phép.

Để dựng lại SDK (chỉ cho môi trường phát triển):

```bash
npm install --prefix /tmp/dhd-ai-vendor --ignore-scripts --no-audit --no-fund --save-exact @huggingface/transformers@3.8.1
python scripts/build_assistant_sdk.py --node-modules /tmp/dhd-ai-vendor/node_modules
python scripts/build_styles.py
python scripts/build_assistant_sdk.py --check
```

Phải kiểm tra diff/hash và `collectstatic` sau khi dựng. Node không phải phụ thuộc chạy production. Không tắt xác minh TLS để thử mô hình; nếu trình duyệt môi trường thử thiếu CA của proxy, dùng bộ tải artifact xác minh TLS của môi trường thử và ghi rõ cách kiểm chứng.

## Kiểm chứng và phát hành

Chạy toàn bộ test hiện có cùng các test mới: quyền trợ lý, giữ nguyên quyền dữ liệu, kho/phiếu ngoài phạm vi, phản hồi chỉ đọc, CSRF, câu hỏi không hợp lệ và widget theo trang. Kiểm tra trình duyệt với dữ liệu/tài khoản thử, biểu mẫu chưa lưu, con trỏ, mobile/sáng/tối, lỗi mạng, thiếu WebAssembly/Worker, mô hình tải theo lựa chọn và suy luận thật nếu thiết bị thử hỗ trợ.

Phân biệt kết quả tra cứu trực tiếp, kiểm thử giao thức mô phỏng và phản hồi mô hình thật. Không dùng ảnh demo hoặc mock để tuyên bố mô hình đã trả lời thật. Chưa đưa lên main hoặc dịch vụ chính khi chủ phần mềm chưa xem và duyệt đúng commit.
