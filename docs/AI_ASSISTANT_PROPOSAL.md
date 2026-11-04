# Đề xuất tích hợp Trợ lý AI — 04/11/2026

**Cập nhật sau khi chủ phần mềm làm rõ:** cần cửa sổ trợ lý mở ngay tại mục đang sử dụng, không yêu cầu mở/cài Ollama riêng. Bản triển khai thử chọn mô hình chạy trong trình duyệt bằng CPU/WebAssembly; xem [thiết kế hiện hành](IN_APP_ASSISTANT.md). Các phương án Ollama/OpenAI bên dưới là lịch sử nghiên cứu, chưa được cài hoặc kích hoạt.

## Phạm vi chủ phần mềm đã chọn

Hỗ trợ cả hướng dẫn sử dụng/soạn nội dung và tra cứu, tổng hợp dữ liệu kho, hồ sơ sai lệch theo quyền của tài khoản. Chủ phần mềm đã chọn **không phát sinh phí API**. Vì vậy, phương án OpenAI API trả phí bên dưới chỉ là tham khảo ban đầu, không được kích hoạt hoặc dùng làm fallback. Đây là đề xuất triển khai, chưa phải chức năng đã kết nối AI.

Chủ phần mềm cần xem bản thử thật và đồng ý phiên bản cụ thể trước khi phát hành chính thức. Không sửa hoặc triển khai bản chính trong bước chuẩn bị này.

## Phương án hiện được đề xuất: mô hình chạy tại công ty

- Dùng Ollama hoặc bộ chạy tương đương trên một máy công ty với mô hình có giấy phép phù hợp. Chọn và kiểm chứng mô hình tiếng Việt sau khi biết RAM/GPU, không cam kết chất lượng ngang ChatGPT.
- Không có phí API theo lượt/token của OpenAI. Máy vẫn tiêu thụ điện, RAM và tài nguyên xử lý; có thể cần đầu tư phần cứng nếu máy hiện có không đáp ứng. Không mô tả là miễn phí mọi chi phí vận hành.
- Đặt tên tính năng **Trợ lý AI**, ghi đúng tên mô hình; không giới thiệu mô hình của đơn vị khác là ChatGPT/OpenAI.
- Phần suy luận xử lý trên máy công ty. Database Render/Neon và nơi lưu tệp hiện có giữ nguyên; không nói toàn bộ dữ liệu phần mềm chuyển về máy nội bộ.
- Máy cần bật khi người dùng hỏi AI. Khi máy tắt hoặc mất kết nối, chỉ AI báo chưa sẵn sàng; các phân hệ khác tiếp tục hoạt động.
- Kết nối từ máy chủ phần mềm tới máy chạy AI qua cổng trung gian có xác thực và mã hóa. Không công khai cổng Ollama không có xác thực; không đưa bí mật kết nối vào JavaScript.
- Chỉ sử dụng endpoint/model đã cấu hình và cấp quyền. Không tự chuyển sang API có tính phí hoặc nhà cung cấp AI miễn phí khác khi gặp lỗi.
- Một phương án khác cần đánh giá là chạy mô hình ngay trong trình duyệt bằng WebLLM: không cần máy AI luôn bật nhưng phụ thuộc WebGPU, bộ nhớ và dung lượng tải mô hình của từng thiết bị. Chưa chọn phương án này khi chưa biết thiết bị thực tế.
- Chưa cài đặt phần mềm lên máy của chủ phần mềm, chưa kết nối máy tính hoặc tạo dịch vụ hosting mới. Đang chờ thông tin cấu hình máy.

Thông tin máy chủ phần mềm cung cấp: **Windows, RAM 8 GB**; chưa biết CPU/GPU. Chỉ đề xuất diễn tập với mô hình nhỏ (ví dụ Qwen3 1.7B, kiểm tra lại giấy phép và model tải), ngữ cảnh khởi đầu khoảng 2.048 token, một yêu cầu đồng thời. Không hứa tốc độ hoặc khả năng hiểu ngang ChatGPT, không coi đây là cấu hình trung tâm đã đạt cho nhiều nhân viên. Cần kiểm chứng tiếng Việt và đối chiếu số liệu trước khi chọn mô hình chính thức. Không tự nâng cấu hình hoặc phát sinh phí phần cứng.

Bước người dùng cần làm trên máy Windows: tải Ollama từ trang chính thức, cài đặt, thử `ollama run qwen3:1.7b` và hỏi một câu tiếng Việt không chứa dữ liệu công ty. Quá trình này tải mô hình về máy, không gọi OpenAI API. Phiên Codex hiện không có công cụ điều khiển máy Windows đó; cài đặt và kết nối chưa được thực hiện. Không hướng dẫn công khai cổng 11434 để nối website; kết nối phải được thiết kế/xác thực riêng.

## Trải nghiệm đề xuất

- Một mục riêng **Trợ lý AI**, không đọc hoặc tham gia các hội thoại nhân viên hiện có.
- Có hai chế độ rõ ràng: **Hướng dẫn & soạn thảo** và **Tra cứu công việc**. Hiện phạm vi kho đang được phép xem và thời điểm dữ liệu của câu trả lời.
- Ví dụ câu hỏi: “Mã A đang còn bao nhiêu ở kho tôi phụ trách?”, “Các phiếu nhập đang chờ duyệt?”, “Tóm tắt hồ sơ sai lệch tôi được xem”, “Hướng dẫn nhập kho bằng Excel”, “Soạn nội dung báo cáo sai lệch”.
- Câu trả lời tra cứu có đường dẫn về danh mục, phiếu hoặc hồ sơ gốc; số lượng, giá trị và thời hạn được tính ở máy chủ. Không để mô hình tự suy ra số tồn hoặc dựng số phiếu.
- Đánh dấu nội dung AI soạn là bản gợi ý để người dùng kiểm tra. Nếu dữ liệu thiếu hoặc người dùng không có quyền, trả lời rõ; không thay bằng số liệu suy đoán.
- Mỗi người chỉ truy cập lịch sử hỏi AI của mình qua ứng dụng. Admin quản lý cấu hình/quyền/hạn mức, không có tính năng đọc lịch sử riêng của người khác.

## Phân quyền và dữ liệu

Quyền dùng AI và quyền cho AI tra cứu được cấp riêng. Quyền AI không thay thế quyền xem sản phẩm, từng loại phiếu hoặc phạm vi kho hiện có. Hồ sơ sai lệch tuân theo cơ chế xem đang có; không thay đổi quy tắc xem của phân hệ đó.

Mọi công cụ tra cứu xác định người dùng từ phiên đăng nhập và truy vấn qua bộ lọc quyền của máy chủ. Không nhận user ID hoặc danh sách kho do trình duyệt/mô hình gửi lên làm căn cứ cấp quyền. Không cung cấp công cụ chạy SQL, shell hoặc URL tùy ý.

Chỉ gửi câu hỏi và phần thông tin cần thiết, đã lọc quyền, tới bộ chạy AI được duyệt. Không gửi toàn bộ database, mật khẩu, token Drive, lịch sử chat nhân viên, dữ liệu nhân sự riêng tư hoặc cả kho tệp. Quyền xem hồ sơ trong phần mềm không tự đồng nghĩa với việc được tải mọi tệp lên hệ thống AI.

Bản đầu chỉ đọc. Không tự tạo, sửa, xóa, gửi mail, phê duyệt phiếu, điều chỉnh tồn hoặc kết thúc sai lệch. Mọi khả năng thực hiện giao dịch trong tương lai cần yêu cầu và thiết kế xác nhận riêng.

## Kiến trúc và giới hạn tích hợp

- App Django riêng, ví dụ `ai_assistant/`, cùng URL, template, JavaScript và bảng lịch sử/usage riêng.
- Điểm tích hợp chung tối thiểu: khai báo app/URL, menu, cấp quyền, middleware và điều kiện sẵn sàng của bản phát hành khi có migration. Không đổi dịch vụ ghi sổ kho, các bước duyệt hoặc dịch vụ chat.
- Tách lớp kết nối nhà cung cấp khỏi dịch vụ tra cứu/phân quyền. Với phương án hiện tại, máy chủ gọi bộ chạy mô hình nội bộ thông qua kết nối được bảo vệ. Bí mật kết nối chỉ lưu trong cấu hình bí mật của hosting, không nằm trong mã nguồn, HTML, JavaScript, log hoặc nội dung hỏi AI.
- Nội dung tài liệu, phiếu và kết quả tra cứu là dữ liệu tham khảo, không phải chỉ thị để đổi quyền hoặc gọi công cụ. Chỉ cho phép danh sách công cụ đọc đã xác định; kiểm tra tham số ở máy chủ và giới hạn số lần gọi.
- Có timeout, giới hạn độ dài câu hỏi/câu trả lời, số yêu cầu đồng thời, số lượt theo tài khoản và công tắc tắt toàn bộ AI. Mất kết nối AI không chặn chức năng kho, chat hoặc sai lệch.
- Cấu hình model, giới hạn bộ nhớ/ngữ cảnh và số lượt đồng thời sau khi biết cấu hình máy. Chặn gọi thật khi chưa cấu hình; không tạo câu trả lời giả để trình bày như AI đã kết nối thành công.
- Giới hạn ngữ cảnh, độ dài đầu ra, thời gian xử lý và số lượt đồng thời để bảo vệ máy chạy mô hình. Không dùng nhà cung cấp API khác khi máy nội bộ quá tải hoặc tắt.
- Lịch sử/usage lưu riêng theo tài khoản; không ghi prompt, câu trả lời hoặc bí mật vào log của cổng trung gian. Cách lưu lịch sử và thời hạn lưu cần chọn rõ, không tự xóa dữ liệu nghiệp vụ hiện có.

## Kiểm tra và bản xem trước

1. Test phân quyền theo tài khoản và kho, không lộ nguồn ngoài quyền; admin không có tính năng đọc hội thoại riêng qua AI.
2. Test số liệu tra cứu khớp kết quả tính máy chủ, không ghi phiếu/tồn khi hỏi; câu trả lời không bịa nguồn.
3. Test lỗi nhà cung cấp, thiếu khóa, giới hạn lượt, thao tác gửi lại và requests đồng thời. Kiểm thử giao thức bằng mô phỏng được ghi rõ; chưa chứng minh AI thật đã kết nối.
4. Chạy toàn bộ kiểm thử hiện có, rà soát diff ngoài phạm vi và kiểm tra giao diện bằng tài khoản/database thử riêng.
5. Khi bộ chạy mô hình nội bộ và kết nối xác thực đã sẵn sàng, kiểm chứng phản hồi thật bằng câu hỏi ít dữ liệu trên bản thử. Không dùng dữ liệu công ty để minh họa mặc định; không trình bày phản hồi mô phỏng là đã gọi mô hình thật.
6. Cho chủ phần mềm xem đúng commit và cách hoạt động thực tế, gồm giới hạn đã biết; chờ duyệt rồi mới phát hành.

## Thông tin cần hoàn tất

- Chủ phần mềm đã chọn cả hai nhóm chức năng.
- Chủ phần mềm đã chọn không phát sinh phí API; không yêu cầu tạo OpenAI API key hoặc nạp tiền.
- Đã biết Windows, RAM 8 GB. Còn thiếu CPU/GPU, việc cài/chạy mô hình tại máy và khả năng duy trì máy công ty hoạt động; cần benchmark trước khi kết nối cho nhiều người.
- Chưa có công cụ nhúng ứng dụng Django tương tác trực tiếp trong phiên ChatGPT này; ảnh chụp bản chạy và đường dẫn thử riêng phải được mô tả đúng loại.

## Tài liệu chính thức đã kiểm tra

- [Thanh toán ChatGPT và API là hai phần riêng](https://help.openai.com/en/articles/9039756-managing-billing-for-chatgpt-and-the-api-platform).
- [Tạo phản hồi qua Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create).
- [Thông tin giá API](https://openai.com/api/pricing/); tra lại khi chọn model, không ghi giá ước đoán thành hạn mức cố định.
- [Ollama: bắt đầu sử dụng](https://docs.ollama.com/quickstart), [FAQ và cấu hình mạng](https://docs.ollama.com/faq).
- [Danh mục mô hình Qwen3 trên Ollama](https://ollama.com/library/qwen3); lựa chọn/giấy phép/tài nguyên cần kiểm tra cho đúng model.
- [WebLLM: chạy mô hình trong trình duyệt](https://webllm.mlc.ai/docs/).
