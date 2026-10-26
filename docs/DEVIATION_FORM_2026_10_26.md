# Áp dụng biểu mẫu sai lệch của công ty — bản thử 26/10/2026

Nguồn: `Bieu-mau-bao-cao-sai-lech.docx` do chủ phần mềm gửi, gồm ba biểu mẫu trên 6 trang. Chỉ lấy trường dữ liệu và cách tổ chức công việc; không đưa vào tên tổ chức, mã SOP, số phiếu, ngày mẫu, nội dung N/A hay dấu tick minh họa.

## Quyết định đã được chủ phần mềm chốt

1. Duyệt tuần tự theo các cấp trên mẫu.
2. KSNB được phân quyền kiểm tra hiệu quả và kết thúc, không yêu cầu Tổng giám đốc duyệt kết thúc thêm lần nữa.
3. Tự tính RIV và mức rủi ro; TBP chuyên môn và KSNB chọn Nhỏ/Lớn/Nghiêm trọng khi duyệt, KSNB kết luận loại cuối cùng. Nếu khác đề xuất/kết luận trước, bắt buộc căn cứ; giữ nguyên loại đề xuất trong bản gửi, không tự đổi loại theo RIV.
4. Giữ nguyên các phân hệ khác; mọi thay đổi ở bản thử cho đến khi chủ phần mềm xem và chấp thuận phát hành bản cụ thể.

## Đối chiếu biểu mẫu vào phần mềm

| Biểu mẫu | Trường / cách áp dụng |
| --- | --- |
| Thông tin sai lệch | Ngày giờ xảy ra (có thể chưa biết), phát hiện, đã báo TBP; người lập/chức danh lưu riêng. Ngày tạo và lần gửi đầu trên phần mềm là dấu thời gian hệ thống, không bị thay bằng ngày báo TBP. |
| Mô tả 5W1H | Người phát hiện/chức danh, thời điểm phát hiện dùng chung, địa điểm, điều đã xảy ra, điều thay đổi, cách phát hiện. Không yêu cầu nhập hai lần cùng một mốc phát hiện. |
| Phân tích ban đầu | Thực tế, điều nên xảy ra, chênh lệch; nghi vấn/nhận xét; biện pháp tức thời đã thực hiện. Có thể lưu nháp chưa đủ, phải hoàn tất trước khi gửi. |
| Điều tra 5W1H | Từng câu trả lời và dữ liệu/căn cứ đối chiếu riêng. Lấy gợi ý từ báo cáo, người điều tra xác minh lại. |
| Chênh lệch sau điều tra | Thực tế xác minh, điều nên xảy ra, phân tích chênh lệch, khâu bị ảnh hưởng, phạm vi tác động. |
| Lịch sử/trình tự | Đã từng xảy ra hay chưa/chưa rõ, kết quả tra cứu lịch sử và trình tự sự cố. Không tự điền chưa từng xảy ra khi chưa tra cứu. |
| Xương cá | Sáu nhóm: đo lường, con người, phương pháp, môi trường, máy móc, thiết bị. Chọn có liên quan/loại trừ/không áp dụng và nêu căn cứ; không quy lỗi mặc định cho con người. |
| 5 Why | Nhiều dòng nguyên nhân, tối đa 20. Điền chuỗi Tại sao liên tục; được dừng khi đã tìm nguyên nhân, không ép bịa đủ năm câu. Dòng bị xóa khi soạn vẫn được giữ trong lịch sử thay đổi nếu đã lưu trước đó. |
| Rủi ro | Hai thang 1–5 theo mẫu. RIV = khả năng × hậu quả; dưới 5 thấp, 5–9 trung bình, từ 10 cao. Bắt buộc căn cứ và người có quyền chọn phân loại khi gửi điều tra. Không mặc định chọn 2 × 2. |
| Kết luận | Nguyên nhân trực tiếp, nguyên nhân gốc rễ và nhân tố liên quan nguyên nhân/hậu quả; người/bộ phận liên quan cùng căn cứ. |
| CAPA | Mã tự cấp, tồn tại, khắc phục, ngăn ngừa, người/bộ phận chịu trách nhiệm, phối hợp và hạn. Một dòng có thể gồm khắc phục và phòng ngừa. |
| Theo dõi đến kết thúc | Thực hiện, kết quả/căn cứ, gia hạn theo quy tắc đã cấu hình, đánh giá hiệu quả và kết luận KSNB. Chưa hiệu quả mở lượt điều tra/CAPA tiếp theo trong cùng hồ sơ. |

## Luồng xác nhận

- Báo cáo: người lập gửi → Trưởng bộ phận phát hiện → KSNB tiếp nhận, có thể phân công người điều tra ngay tại bước tiếp nhận.
- Điều tra: người phụ trách gửi → Trưởng bộ phận chuyên môn → KSNB.
- CAPA: người soạn gửi → bộ phận liên quan → KSNB → Tổng giám đốc. Chỉ sau bước cuối mới được cập nhật thực hiện.
- Thực hiện xong → gửi đánh giá → KSNB được phân công kiểm tra hiệu quả và kết thúc. Không hiệu quả → lượt điều tra/CAPA mới; các kết quả trước được giữ.

Mỗi bước có Đồng ý hoặc Không duyệt/trả lại, bắt buộc lý do khi trả lại. Không được bỏ qua bước bằng API cũ hoặc chỉ thay trạng thái. Các cấp trong cùng phiếu là người khác nhau; Admin có thể kiêm nhiệm/xử lý thay với cảnh báo và lưu ngoại lệ. Các điều kiện cấp duyệt/độc lập/cao hơn người lập vẫn áp dụng theo phiên bản cấu hình đã chốt của hồ sơ.

## Phân quyền và phân công

Admin toàn quyền. Các chức năng mới được cấp riêng trong nhóm Xử lý sai lệch:

- `deviations_department_approve`: Trưởng bộ phận phát hiện duyệt báo cáo.
- `deviations_specialist_approve`: TBP chuyên môn duyệt điều tra.
- `deviations_related_approve`: bộ phận liên quan duyệt CAPA.
- `deviations_control_approve`: KSNB duyệt theo mẫu, xem xét gia hạn, đánh giá và kết thúc hồ sơ được phân công.
- `deviations_director_approve`: Tổng giám đốc duyệt CAPA.

Các quyền tạo/phụ trách/thực hiện hiện có tiếp tục được cấp riêng. Tên chức danh không tự tạo ra quyền. Không tự cấp quyền mới cho tài khoản cũ. Tài khoản khác chỉ ký được bước hiện tại, đúng phân công và còn quyền khi bấm xác nhận. Quyền sai lệch không mở phiếu/tồn/duyệt kho.

## Ràng buộc và lưu trữ

- `Case.form_version=1` giữ luồng và dữ liệu cũ. Migration 0004–0005 không tạo ngày giờ, người ký, mức rủi ro hoặc chữ ký giả cho hồ sơ đã có. Tạo mới dùng phiên bản 2.
- Các cột mới thêm vào bảng cũ có giá trị mặc định tại PostgreSQL khi cần. Đã kiểm tra chương trình phiên bản cũ vẫn tạo được hồ sơ trong lúc triển khai luân phiên; không dùng giá trị giả để lấp các mốc thời gian hoặc kết luận.
- Mỗi lần gửi giữ bản nội dung, bằng chứng tham chiếu, người gửi, người được phân công và thứ tự duyệt. Đổi cấu hình sau này không tự đổi thứ tự đã gửi.
- Xác nhận giữ họ tên/chức danh và thời điểm của người thực sự thao tác; không dùng tên mới trên hồ sơ tài khoản để viết lại tên đã xác nhận trước đây.
- Không sửa nội dung hoặc bằng chứng khi đang duyệt. Người gửi/Admin có thể rút có lý do, hoặc cấp đang chờ trả lại; sửa rồi gửi tạo lần mới từ bước đầu.
- Nếu phát hiện báo cáo chưa đúng khi điều tra, KSNB yêu cầu bổ sung có lý do. Bản đã xác nhận trước trở thành bản được thay thế, không bị ghi đè.
- Điều tra đã được xác nhận không sửa trực tiếp; mở lại điều tra có lý do trước khi thay. CAPA đã gửi/đã duyệt không sửa trực tiếp.
- Kiểm tra revision và khóa hồ sơ/bước duyệt; double click không thể tạo hai quyết định hoặc nhảy hai cấp.
- Phiên bản 2 lưu thay đổi thực tế trong Event, dùng bản đầy đủ tại các lần gửi để tránh nhân đôi toàn bộ phân tích dài ở mỗi chữ ký. Hồ sơ cũ giữ định dạng lịch sử cũ.
- Tệp vẫn dùng Drive riêng tư đã kết nối, database giữ metadata. Bản thử lưu tệp giả lập riêng; không có tệp hay dữ liệu công ty được sao chép vào môi trường thử.

## Bản in và kiểm tra

In được bộ báo cáo–điều tra–CAPA–hiệu quả. Mỗi lần gửi có trang in riêng với đúng bản dữ liệu đã gửi và các xác nhận thực tế; không ghép chữ ký cũ lên nội dung mới. Chưa gửi thì ghi Bản đang soạn; các xác nhận trên phần mềm không bị trình bày thành chữ ký số/chữ ký scan.

Bản thử cần qua kiểm tra đầy đủ PostgreSQL, migration từ hồ sơ cũ, phân quyền, cả luồng nhiều tài khoản và Admin, double click/trả lại/rút/sửa/gửi lại, RIV độc lập phân loại, bằng chứng, in PDF, điện thoại và hồi quy kho. Không merge/deploy hoặc thay đổi Render khi chưa được xem và đồng ý bản thử này.

Cấu trúc code: `form_schema.py` giữ nhóm trường và chuỗi mặc định; `template_forms.py` giữ nhập liệu; `services/form_data.py` kiểm tra dữ liệu; `services/approvals.py` giữ bản gửi và chữ xác nhận; `services/form_workflow.py` giữ chuyển bước V2. Không sửa luồng V1 để áp mẫu mới. Khi đổi ý nghĩa dữ liệu/quy trình, thêm phiên bản và migration mới, giữ khả năng đọc bản cũ.

## Kết quả xác minh bản thử

- 365 kiểm thử đạt trên PostgreSQL 17, gồm hồi quy các phân hệ cũ, phân quyền nhiều tài khoản, duyệt đồng thời, phân loại của từng cấp và in kết quả thực hiện tách khỏi kế hoạch đã ký.
- Diễn tập nâng cấp database thử riêng từ deviations 0003 lên 0005 bằng `safe_migrate`: tạo và xác minh bản chụp `dhd_backup_deviations_form_0005`, giữ hồ sơ giả lập V1; inventory vẫn 0018. Không truy cập database chính.
- Chromium: lập báo cáo → hai xác nhận báo cáo → điều tra 5W1H/xương cá/5 Why/RIV → hai xác nhận điều tra → CAPA → ba xác nhận kế hoạch → thực hiện → KSNB kết thúc. Kiểm tra cảnh báo Admin tự duyệt và cấm thực hiện trước bước Tổng giám đốc.
- Đã xem ở bề rộng 390px và xuất bộ hồ sơ A4 5 trang với dữ liệu ngắn giả lập. Số trang tăng theo nội dung thực tế. Có bản in riêng cho từng lần gửi, bản đầy đủ có thêm kết quả thực hiện và kết luận hiệu quả.
- `ruff`, JavaScript syntax, Django check, `makemigrations --check`, stylesheet bundle và `collectstatic` đạt.
- Giới hạn: thao tác Drive dùng lớp lưu trữ hiện có và kiểm thử giả lập; không gọi Google Drive thật hoặc gửi email công ty trong bản thử. Xác nhận qua tài khoản là dấu vết trên phần mềm, chưa phải dịch vụ chữ ký số. Cần Admin cấp các quyền mới và phân công đúng người trước khi vận hành luồng mới.

Mã nguồn ở nhánh `preview/deviation-form-20261026`. Chủ phần mềm đã yêu cầu phát hành bản đã báo cáo và chạy thử vào ngày 26/10/2026. Chỉ xác nhận phát hành thành công sau khi kiểm thử trên đúng commit đạt và `/healthz/` production trả đúng commit cùng bản chụp nâng cấp sẵn sàng.
