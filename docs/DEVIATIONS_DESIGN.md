# Đề xuất khung phân hệ Xử lý sai lệch

Ngày đề xuất: 22/10/2026 · Trạng thái: BẢN ĐỀ XUẤT, CHƯA ÁP DỤNG QUY TRÌNH.

## 1. Những nội dung đã thống nhất

- Phân hệ Xử lý sai lệch ngang cấp Quản lý kho, Quy trình và Quản lý nhân sự.
- Quản lý mọi sai lệch trong hoạt động công ty, không giới hạn chênh lệch tồn kho.
- Mọi nhân viên đã đăng nhập được xem tất cả hồ sơ sai lệch trong phân hệ. Quyền tạo, sửa, phân công, phê duyệt và kết thúc là các quyền riêng, sẽ chốt theo quy trình.
- Trước mắt xây dựng khung. Chủ phần mềm sẽ quyết định quy trình chi tiết từ tạo đến kết thúc sau khi xem đề xuất.
- Chỉ cập nhật phần mềm chính sau khi bản thử cụ thể được xem và đồng ý.

Bản này tham khảo cách tổ chức công việc trong PDF do chủ phần mềm cung cấp: trách nhiệm và luồng ở trang 9–17, phiếu ghi nhận ở trang 19–20, sổ theo dõi ở trang 21 và ý tưởng phân loại trong các phụ lục. Chỉ sử dụng nguyên tắc quản lý chung. Không đưa vào tên tổ chức, chức danh riêng, mã biểu mẫu, danh sách lỗi chuyên ngành, thang xử phạt hoặc thời hạn của tài liệu nguồn.

## 2. Cách tổ chức giao diện

Đề xuất bốn mục con để người dùng dễ tìm:

| Mục | Nội dung |
| --- | --- |
| Tổng quan | Hồ sơ đang xử lý, quá hạn, chờ đánh giá, đã kết thúc; các số liệu lấy từ hồ sơ thật khi có nghiệp vụ. |
| Hồ sơ sai lệch | Danh sách chính và nơi mở từng hồ sơ; tìm theo mã, tiêu đề, phòng ban, nhóm sai lệch, người phụ trách, mức độ, thời gian và trạng thái. |
| Báo cáo | Theo dõi tiến độ, nguyên nhân, sai lệch tái diễn và kết quả khắc phục theo phòng ban/thời kỳ. |
| Danh mục & cấu hình | Admin quản lý nhóm sai lệch và cấu hình được công ty phê duyệt; chưa có cơ chế tự dựng quy trình tùy ý. |

Trong danh sách dùng các bộ lọc Tất cả, Tôi ghi nhận, Tôi được giao, Quá hạn, Đã kết thúc. Các bộ lọc cùng trỏ về một hồ sơ; không tạo nhiều bản phiếu cho cùng một sự việc. Chưa có dữ liệu thật thì hiển thị trạng thái chuẩn bị, không dựng bộ đếm hoặc biểu đồ minh họa gây hiểu nhầm.

## 3. Một vụ việc, một hồ sơ xuyên suốt

Đề xuất mã dễ đọc như SL-2026-000001, tự sinh và duy nhất; mã không đổi khi chuyển bộ phận, bổ sung hành động hoặc đánh giá lại. Quy tắc cấp số cụ thể sẽ chốt khi xây nghiệp vụ.

Một hồ sơ chia năm phần, chỉ yêu cầu thông tin phù hợp với giai đoạn đang thực hiện:

| Phần | Thông tin chính |
| --- | --- |
| Thông tin sự việc | Người ghi nhận, thời điểm xảy ra/phát hiện/gửi báo cáo, phòng ban/địa điểm, mô tả thực tế, yêu cầu cần đáp ứng, ảnh/PDF và hồ sơ liên quan. |
| Xác minh & nguyên nhân | Nội dung xác minh, mức độ, phạm vi ảnh hưởng, nguyên nhân trực tiếp, nguyên nhân gốc rễ, người/bộ phận liên quan và căn cứ. |
| Kế hoạch & thực hiện | Từng hành động xử lý, người chịu trách nhiệm, người phối hợp, hạn, kết quả, bằng chứng và các đề nghị gia hạn. |
| Đánh giá & kết thúc | Tiêu chí đánh giá, ngày kiểm tra, bằng chứng hiệu quả, kết luận đạt/chưa đạt, yêu cầu bổ sung và kết luận kết thúc. |
| Lịch sử & tệp | Toàn bộ thao tác, thay đổi, ý kiến, các lần duyệt/bổ sung và tệp được phân nhóm theo giai đoạn. |

Không bắt nhân viên điền nguyên nhân hoặc kết quả ngay lúc báo sự việc. Khi chưa xác minh, ghi Người liên quan; không tự kết luận người gây lỗi chỉ từ thông tin báo cáo.

## 4. Khung ghi nhận ban đầu

Đề xuất thông tin tối thiểu khi gửi ghi nhận:

- Tiêu đề/tóm tắt sai lệch; nhóm sai lệch.
- Phòng ban/địa điểm xảy ra; thời điểm phát hiện.
- Mô tả điều đã xảy ra, kèm căn cứ hoặc yêu cầu cần đáp ứng nếu đã biết.
- Người ghi nhận và thời điểm tạo/gửi do hệ thống ghi nhận.

Các trường bổ sung khi có thông tin: thời điểm xảy ra; cách phát hiện; người/bộ phận liên quan; đối tượng ảnh hưởng; giá trị ảnh hưởng ước tính; biện pháp tức thời đã thực hiện; ảnh/PDF; mã hàng, tài sản, phiếu hoặc biên bản kiểm kê liên quan.

Tách rõ ba nội dung Thực tế đã xảy ra / Yêu cầu cần đáp ứng / Điểm sai lệch. Tránh dùng một ô Diễn giải quá dài khiến người xử lý không biết thiếu thông tin gì. Thời điểm xảy ra có thể chưa xác định: cần cho ghi Chưa xác định thay vì điền ngày giả. Ngày tạo/gửi là thời điểm hệ thống ghi, không được sửa để làm mất dấu báo cáo trễ. Quy tắc phiếu kho chỉ dùng ngày hôm nay không tự áp vào ngày xảy ra sự việc.

## 5. Phân nhóm và đánh giá mức độ

Nhóm đề xuất: Kho & hàng hóa; Tài sản & thiết bị; Nhân sự; Quy trình & tuân thủ; Tài chính & chứng từ; Hoạt động khác.

Mức độ đề xuất để thảo luận:

| Mức | Căn cứ đánh giá của công ty cần xây dựng |
| --- | --- |
| Nhỏ | Ảnh hưởng hạn chế, được kiểm soát, chưa lan rộng; vẫn cần ghi nhận và kiểm tra. |
| Lớn | Ảnh hưởng đáng kể tới vận hành, tài sản, dữ liệu hoặc tuân thủ; cần kế hoạch và người chịu trách nhiệm rõ. |
| Nghiêm trọng | Nguy cơ hoặc thiệt hại lớn; cần ưu tiên kiểm soát và chuyển cấp có thẩm quyền. |

Phân biệt Mức độ ảnh hưởng và Mức ưu tiên xử lý. Người ghi nhận có thể nêu đánh giá ban đầu; người được phân quyền xác minh sẽ kết luận mức độ, có lý do và lịch sử nếu đổi.

Không sao chép tiêu chí chuyên ngành hoặc ngưỡng tiền từ tài liệu nguồn. Không tự nâng mức chỉ vì giống từ khóa hay người đó từng có hồ sơ; phần mềm chỉ hỗ trợ tìm vụ việc tương tự để người có trách nhiệm đánh giá tái diễn.

## 6. Luồng tham khảo để chủ phần mềm xem trước

Ghi nhận → Tiếp nhận/xác minh → Phân tích nguyên nhân → Thống nhất kế hoạch → Thực hiện → Đánh giá hiệu quả → Kết thúc.

Đây là luồng đề xuất, chưa phải quy trình đang áp dụng hoặc một hệ thống duyệt đã được xây dựng. Chưa ấn định ai duyệt bước nào, số cấp duyệt hoặc quyền tự duyệt ngoài quy tắc chung đã có.

Các nhánh cần có khi chốt quy trình:

- Thiếu thông tin: yêu cầu bổ sung, chỉ rõ nội dung cần làm rõ; giữ lần gửi cũ.
- Không tiếp nhận: ghi căn cứ và lý do, không xóa báo cáo như chưa từng có.
- Không đồng ý kế hoạch: trả lại kế hoạch để sửa, giữ ý kiến và phiên bản trước.
- Kết quả chưa hiệu quả: bổ sung hành động trong cùng hồ sơ, giữ mã và các lần xử lý cũ.
- Hồ sơ trùng: liên kết hồ sơ gốc, ghi lý do; không âm thầm xóa một báo cáo.
- Mở lại sau kết thúc: cần quyền và lý do, giữ nguyên kết luận của lần kết thúc trước.

Mức chi tiết của từng bước cần phù hợp độ phức tạp vụ việc. Sai lệch đơn giản có thể ghi ngắn gọn theo quy trình được duyệt; không bắt mọi vụ việc lập nhiều biểu mẫu giống nhau.

## 7. Theo dõi hành động xử lý

Phân biệt ba loại công việc:

| Loại | Mục đích | Ví dụ phù hợp hoạt động công ty |
| --- | --- | --- |
| Xử lý tức thời | Kiểm soát ảnh hưởng ngay khi phát hiện. | Đánh dấu hàng cần kiểm tra, bảo vệ bằng chứng, thông báo người phụ trách. |
| Khắc phục nguyên nhân | Giải quyết nguyên nhân đã được xác minh. | Sửa cách bàn giao hoặc sửa thao tác đã được phê duyệt. |
| Phòng ngừa tái diễn | Giảm khả năng lặp lại. | Bổ sung bước đối chiếu, hướng dẫn hoặc kiểm tra định kỳ. |

Một hồ sơ có nhiều hành động và nhiều người thực hiện. Mỗi hành động cần nội dung, một người chịu trách nhiệm chính, người phối hợp khi cần, hạn, kết quả và bằng chứng. Không giao chung cho cả phòng mà thiếu người theo dõi cụ thể.

Hoàn thành công việc là một mốc; hiệu quả khắc phục là mốc đánh giá riêng. Tiêu chí đánh giá phải rõ trước khi đánh giá; ví dụ đối chiếu các giao dịch tiếp theo hoặc kiểm tra lại đúng hạng mục, theo phạm vi/thời gian được công ty chốt. Nếu không cần hành động phòng ngừa riêng, người có thẩm quyền ghi lý do phù hợp vụ việc, thay vì tạo công việc giả cho đủ bước.

Quá hạn phải được nhìn thấy. Gia hạn cần lý do, hạn mới, người đề nghị và quyết định của người có quyền; giữ hạn cũ trong lịch sử. Thời hạn và số lần gia hạn không lấy mặc định từ tài liệu nguồn, chưa được áp dụng khi chủ phần mềm chưa chốt.

## 8. Quyền và trách nhiệm

- Mọi nhân viên đã đăng nhập: xem tất cả hồ sơ sai lệch theo yêu cầu đã chốt.
- Quyền lập, sửa, tiếp nhận, phân công, cập nhật hành động, xét kế hoạch, đánh giá hiệu quả, kết thúc/mở lại: tách riêng và cấp theo quy trình sắp thống nhất.
- Admin: quản trị và xử lý tổng theo quyền hiện có; những thao tác ảnh hưởng kết luận phải được ghi lịch sử.
- Đề xuất KSNB giữ vai trò điều phối, theo dõi và tổng hợp. Đây chưa phải quyết định cấp quyền duyệt/kết thúc cho một nhóm tài khoản.
- Nguyên tắc tự duyệt của Admin cần cảnh báo/xác nhận và lịch sử, kế thừa quy tắc chung đang có. Cơ chế kiểm tra độc lập và cấp duyệt của hồ sơ sẽ được chốt khi duyệt quy trình.

Quyền xem mọi hồ sơ sai lệch không tự cấp quyền sửa dữ liệu hoặc mở toàn bộ phiếu/hồ sơ gốc ở các phân hệ khác. Liên kết sang phiếu kho, nhân sự và tài chính vẫn kiểm tra quyền của chức năng gốc.

## 9. Ràng buộc nên đưa vào thiết kế

- Hồ sơ giữ một mã xuyên suốt, không tạo mã mới mỗi lần bổ sung hoặc đánh giá lại.
- Không âm thầm thay nội dung đã gửi, kết luận đã xác nhận hoặc tệp gốc; lưu phiên bản, người thay đổi, thời điểm và lý do theo quy trình.
- Không kết thúc hồ sơ chỉ vì người thực hiện bấm Đã làm xong; phải có kết luận kiểm tra phù hợp và đúng quyền đã thống nhất.
- Không tự kết luận vi phạm, bồi thường, kỷ luật hoặc khấu trừ lương từ một báo cáo sai lệch.
- Không dùng kết thúc hồ sơ sai lệch để cộng/trừ tồn hoặc sửa chứng từ đã ghi sổ. Điều chỉnh kho vẫn qua phiếu và thẩm quyền hiện có.
- Chống gửi/duyệt lặp và sửa đồng thời; lỗi phải báo rõ, không tạo kết quả thành công giả.
- Tệp giữ theo giai đoạn và lượt xử lý, không nhân bản để phục vụ mỗi màn hình.

## 10. Hồ sơ và báo cáo đề xuất

Một hồ sơ tổng hợp có thể xuất thành báo cáo gồm thông tin sự việc, kết quả xác minh, kế hoạch, thực hiện, đánh giá và kết luận; tránh bắt người dùng lập lại nhiều phiếu rời có thông tin trùng.

Sổ theo dõi là danh sách lấy trực tiếp từ hồ sơ: mã, ngày ghi nhận, phòng ban, nhóm, mức độ, người phụ trách, nguyên nhân, hành động, hạn, tình trạng và kết quả kiểm tra. Không nhập thêm một sổ theo dõi độc lập.

Báo cáo đề xuất: đang xử lý/quá hạn; thời gian xử lý theo phòng ban; nhóm/nguyên nhân thường gặp; các sai lệch tái diễn đã được xác nhận; kết quả khắc phục và ảnh hưởng ước tính/thực tế khi có căn cứ. Cách tính chỉ số và thời kỳ sẽ thống nhất trước khi sử dụng.

Ảnh/PDF dự kiến lưu trong thư mục Drive đã kết nối, có nhánh riêng theo năm và mã hồ sơ, ví dụ XuLySaiLech/2026/SL-2026-000001/. Database giữ nội dung nghiệp vụ, metadata và liên kết. Quy tắc tệp thực tế sẽ dùng cơ chế quyền và kiểm tra toàn vẹn đang có; bản thử không truy cập Drive công ty.

## 11. Phần thực hiện trước và phần chờ duyệt

Trước mắt: cấu trúc phân hệ độc lập, giao diện ban đầu và bản khung này để xem xét.

Sau khi chủ phần mềm duyệt khung và cung cấp quy trình: chốt biểu mẫu bắt buộc, vai trò, chuyển bước, thời hạn, điều kiện duyệt/kết thúc/mở lại, thông báo và cách lưu kết luận; sau đó mới xây nghiệp vụ trên bản thử.

Không tự áp dụng quy trình hay thời hạn trong tài liệu tham khảo vào phần mềm chính. Việc cập nhật chính thức vẫn cần chủ phần mềm duyệt đúng bản thử.
