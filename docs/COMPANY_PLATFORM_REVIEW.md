# Rà soát vận hành và hướng phát triển quản lý công ty

**Cập nhật quyền:** chủ dự án đã chốt admin có toàn quyền; tài khoản khác cấp từng chức năng. Các mô tả quyền cũ bên dưới được thay bằng [quy tắc phân quyền mới](FUNCTION_ACCESS.md).
Ngày 16/10/2026, nhánh `feature/qr-stocktake-product-records`. Đây là đánh giá của bản phát triển hiện tại, chưa phải thông báo phát hành. Xem [kết quả kiểm tra](QR_VALIDATION.md) và [quy trình QR/Drive](QR_STOCKTAKE_AND_DRIVE.md).

## Những phần đã rà soát và sửa trong đợt này

| Nhóm | Trạng thái trong bản phát triển |
| --- | --- |
| Tài khoản nhân viên | Quản trị viên đặt tên đăng nhập/mật khẩu ban đầu, bật/tắt đăng nhập; người dùng tự đổi mật khẩu, phải xác nhận mật khẩu hiện tại. Không khóa chính tài khoản đang thao tác. |
| Vai trò và phạm vi | Vai trò nghiệp vụ và kho truy cập/duyệt được cấp riêng. Bỏ quyền kho thì không tiếp tục ghi số kiểm kê ở kho đó. Không cho nhân viên tự nâng quyền. |
| Tổng giám đốc | Quyền duyệt kiểm kê/điều chỉnh được cấp trực tiếp ở hồ sơ nhân viên; không kế thừa từ nhóm hoặc quyền quản trị. Không tự cấp cho ai trong migration. Người lập không tự duyệt. |
| Nhập/xuất | Nhập do quản lý kho nhận xác nhận; xuất do người được chỉ định duyệt. Kiểm tra đủ tồn tại lúc lập và khi ghi sổ. Chỉ ghi số thực nhận; thiếu/hỏng/không nhận có lý do. |
| Chuyển/mượn/trả | Chuyển đi và nhận là hai bước; hàng trung gian/tồn mượn tạm tách khỏi tồn khả dụng. Trả từng phần theo lệnh gốc, không vượt số còn mượn. |
| Kiểm kê | Một kho/phiên; QR cộng 1 hoặc ghi tổng, phân biệt chưa đếm với 0, kiểm tra mốc tồn, chốt biên bản rồi tạo phiếu chênh lệch. Chỉ phiếu được Tổng giám đốc duyệt mới thay đổi tồn. |
| Bảo toàn hồ sơ | Phiếu ghi sổ không được sửa số; dòng chứng từ và dòng kiểm kê lưu mã/tên/đơn vị tại thời điểm lập. Đổi tên danh mục không sửa nội dung biên bản cũ. |
| Yêu cầu sửa/hủy | Có lý do và lịch sử. Không hủy hàng đang chuyển hoặc phiếu đã ghi sổ bằng nút hủy thông thường. Phiếu điều chỉnh QR khóa theo biên bản; cần làm lại thì giữ bản cũ và kiểm đếm phiên mới. |
| Lịch sử thao tác | Phiếu có ảnh chụp dữ liệu và người/thời điểm từng bước; kiểm kê có lịch sử số trước/sau. Thay đổi quyền nhân viên được ghi vào nhật ký quản trị, không ghi mật khẩu. Chưa có một màn hình nhật ký tập trung cho toàn bộ phân hệ. |
| Ảnh/hóa đơn | Ảnh theo mã; hóa đơn theo đợt nhập, xem được từ từng sản phẩm liên quan. Quyền tải theo hồ sơ/kho, giữ bản cũ khi thay thế. Drive tích hợp bằng OAuth, cần cấu hình và nghiệm thu kết nối thật. |
| Dữ liệu nhập/xuất báo cáo | Excel đi qua xem trước → phiếu nháp → duyệt. CSV tránh thực thi công thức ô. Sửa xử lý mã số bộ lọc quá dài để không tạo lỗi máy chủ ở các màn thẻ kho, tồn khả dụng, kho và lệnh trả. |
| Phát hành | Phát triển ở nhánh riêng và database thử; không tác động website thật trong lúc sửa. Đợt này có migration, phải backup và thử nâng cấp trước khi chuyển bản chính. |

Quyền Tổng giám đốc là một quyền nghiệp vụ mà quản trị viên được giao trách nhiệm cấp; phần mềm không xác minh chức danh thực tế của người nhận. Nhân viên được cấp quyền này xem/duyệt các biên bản và phiếu kiểm kê/điều chỉnh toàn công ty, không mặc nhiên có quyền xem mọi hóa đơn nhập, sửa danh mục hay quản lý nhân viên.

## Những chức năng quản trị nên bổ sung tiếp

Thực hiện từng bước, giữ giao diện nhân viên chỉ hiển thị việc thuộc trách nhiệm của họ. Các mục dưới đây là **đề xuất, chưa triển khai trong đợt này**.

| Ưu tiên | Chức năng | Lợi ích và ràng buộc cần có |
| --- | --- | --- |
| 1 | Cơ cấu phòng ban, chức danh, người phụ trách | Một hồ sơ nhân viên dùng cho kho, mua sắm, tài sản và quy trình đề nghị. Kho có bộ phận chịu trách nhiệm; không tạo lại người dùng ở mỗi phân hệ. |
| 1 | Trung tâm công việc chờ xử lý | Một danh sách việc của tôi: phiếu chờ duyệt, hàng đang chuyển, mượn quá hạn, hóa đơn cần bổ sung, kỳ kiểm kê. Thông báo trong phần mềm; email/Zalo là tích hợp riêng khi được chấp thuận. |
| 1 | Nhật ký tập trung và lịch sử cấp quyền | Quản trị xem ai đổi quyền, dữ liệu trước/sau, lý do và thời điểm; lọc theo nhân viên/đối tượng. Chỉ người có quyền kiểm soát xem được; người dùng không tự xóa nhật ký. |
| 1 | Sao lưu, thử phục hồi và trạng thái dịch vụ | Có lịch backup database và hồ sơ; ghi lần thành công gần nhất, cảnh báo lỗi, thực hành khôi phục ở môi trường thử. Backup tự động không được coi là đã xong chỉ vì có cấu hình nhà cung cấp. |
| 1 | Sổ quy tắc duyệt dùng chung | Khai báo quy trình theo loại công việc, bộ phận, cấp duyệt và phạm vi. Quy tắc bắt buộc như Tổng giám đốc duyệt điều chỉnh không được bị cấu hình thường ghi đè. Không tự áp mô hình nhiều cấp cho các phiếu đơn giản hiện tại. |
| 2 | Lịch sử phiên đăng nhập và khóa phiên khi cần | Xem thiết bị/phiên, đóng các phiên của tài khoản khi bàn giao hoặc nghỉ việc; giới hạn người được thao tác. Hiện đã có bật/tắt tài khoản nhưng chưa có màn hình quản lý tất cả phiên. |
| 2 | Mẫu biểu và cấu hình công ty | Tên/logo, số biểu mẫu, phiên bản mẫu in, chữ ký phụ trách; thay mẫu không sửa số liệu hồ sơ cũ. Chỉ cấu hình phần phù hợp, không để người dùng sửa công thức tồn hoặc quyền đặc biệt bằng trường tự thêm. |

Không cần đưa tất cả mục vào menu ngay. Khi triển khai từng phần, thêm cùng kiểm tra quyền và tình huống lỗi, rồi nghiệm thu bằng công việc thực tế.

## Thứ tự mở rộng nghiệp vụ đề xuất

1. **Đề nghị mua sắm và mua hàng:** bộ phận đề nghị → người có quyền duyệt → đơn mua → nhận hàng → hóa đơn. Một nguồn tham chiếu thống nhất; quản lý số đề nghị/đặt/nhận/thiếu và không tự tạo tồn khi mới duyệt mua.
2. **Bàn giao tài sản, công cụ cho nhân viên:** mã tài sản cá thể/serial khi cần, người giữ, phòng ban, vị trí, tình trạng, ngày bàn giao/thu hồi, biên bản. Phân biệt cấp phát tiêu hao với tài sản phải thu hồi; một tài sản không đồng thời bàn giao cho hai người. Khi nhân viên nghỉ việc có danh sách cần thu hồi.
3. **Bảo trì, sửa chữa và xử lý hỏng/mất:** yêu cầu, phê duyệt, nhà sửa chữa, thời gian, chi phí và chứng từ. Không tự xóa tài sản khỏi sổ chỉ vì báo hỏng; thanh lý/tiêu hủy cần hồ sơ và người duyệt được phân công.
4. **Nhà cung cấp và hợp đồng:** mã nhà cung cấp, thông tin pháp nhân, điều khoản, thời hạn, hồ sơ và liên kết đơn mua/hóa đơn. Không nhân đôi danh mục đối tác ở kho, mua sắm và tài chính.
5. **Ngân sách, đề nghị thanh toán và báo cáo quản trị:** hạn mức theo bộ phận/dự án, cam kết mua, thực chi và hồ sơ thanh toán. Chỉ triển khai sau khi thống nhất quy trình kế toán; số liệu kho hiện tại chưa phải sổ kế toán/thuế đầy đủ.

Nhân sự/chấm công, khách hàng/bán hàng hoặc quản lý dự án có thể phát triển thành phân hệ riêng khi có quy trình cụ thể; không nên nhét toàn bộ vào chức năng kho.

## Báo cáo nên có thêm

- Bảng công việc tồn đọng: chờ duyệt bao lâu, hàng đang chuyển chưa nhận, mượn quá hạn, hồ sơ nhập còn thiếu.
- Chênh lệch kiểm kê theo kho, kỳ và người phụ trách; tách chưa duyệt/đã điều chỉnh/hủy, giá trị tăng/giảm và lý do.
- Hàng chậm luân chuyển theo lần giao dịch thực tế, nhu cầu mua và mức tồn tối thiểu; không dùng nhãn "tồn lâu" khi chưa tính dữ liệu.
- Tài sản theo phòng ban/người giữ, tài sản chưa bàn giao, hỏng/chờ sửa, đến hạn bảo trì.
- Chi mua sắm theo nhà cung cấp/bộ phận, đối chiếu đề nghị → đơn mua → nhận → hóa đơn → thanh toán khi các phân hệ nguồn đã có.

Hiện bản phát triển đã có báo cáo tồn/giá trị, thiếu hoặc không nhận, mượn quá hạn, phiếu chờ và biên bản QR. Các báo cáo liên phân hệ nói trên cần phát triển thêm; chưa thể suy ra chính xác bằng dữ liệu kho hiện có.

## Kiến trúc mở rộng phù hợp

Giữ một ứng dụng Django và một PostgreSQL trong giai đoạn hiện tại để dễ vận hành. Tách nghiệp vụ thành các ứng dụng nội bộ khi mở rộng, không cần tách thành nhiều máy chủ ngay:

```text
Nền dùng chung (phát triển từng phần)
  Tổ chức & nhân viên | Quyền & duyệt | Hồ sơ | Nhật ký | Thông báo
                              ↓
  Kho hiện tại | Mua sắm | Tài sản & bàn giao | Bảo trì | Ngân sách
                              ↓
             Báo cáo quản trị theo quyền truy cập
```

Database là nguồn chính cho dữ liệu nghiệp vụ; Drive là nơi lưu hồ sơ, không thay thế database. Mỗi đối tượng dùng ID ổn định, liên kết nguồn và trạng thái rõ ràng. Chức năng ghi sổ phải qua dịch vụ nghiệp vụ có transaction/khóa; không để từng màn hình tự sửa số dư. Duyệt nhiều lần, mất phản hồi hoặc mở hai tab phải có kiểm soát lặp và phiên bản. Trường tự thêm chỉ là thông tin mở rộng, không được thay đổi kiểm soát tài chính.

Mã hiện tại đã chia riêng dịch vụ ghi sổ, kiểm kê, hồ sơ, Drive và quyền dùng chung ở phạm vi đang có. Chưa có đầy đủ nền tảng tổ chức/quy trình chung theo sơ đồ này; đây là hướng phát triển để tránh phình ứng dụng kho. Hiện cũng chỉ quản lý **một công ty với nhiều kho**. Nếu sau này cần nhiều pháp nhân, phải thêm phạm vi công ty vào dữ liệu, quyền, mã số và báo cáo, kèm migration và kiểm tra tách dữ liệu; không chỉ thêm một ô chọn tên công ty.

## Điều kiện trước khi áp dụng bản này

- Có bản sao lưu database và kế hoạch khôi phục, thử migration 0007 → 0014 trên bản sao tách biệt; không chạy test trên Neon chính.
- Tạo tài khoản Tổng giám đốc thực tế và cấp đúng quyền bằng quản trị viên. Nếu chưa cấp, phiếu điều chỉnh nằm chờ, không cho quản lý thường thay thế duyệt.
- Cấu hình OAuth Google và chọn đúng thư mục; thử lưu/tải ảnh và PDF thật trên bản thử. Hiện chưa hoàn thành bước này vì chưa có cấu hình Google của chủ tài khoản.
- Chạy nghiệm thu các tình huống nhân viên/quản lý/Tổng giám đốc với một bộ dữ liệu mẫu được thống nhất; đếm thử trên điện thoại thật trước khi in tem hàng loạt.
- Phát hành theo yêu cầu chủ dự án, không tự đẩy thay đổi vào website chính trong quá trình phát triển. Việc đang phát triển riêng giữ bản đang dùng ổn định; migration có thể cần khoảng chuyển đổi có kiểm soát, không cam kết hai phiên bản ghi đồng thời mà không gián đoạn.
