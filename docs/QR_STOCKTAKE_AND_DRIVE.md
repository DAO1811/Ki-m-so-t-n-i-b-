# Kiểm kê QR, ảnh hàng hóa và hồ sơ từng đợt nhập

**Cập nhật quyền:** chủ dự án đã chốt admin có toàn quyền; tài khoản khác cấp từng chức năng. Các mô tả quyền cũ bên dưới được thay bằng [quy tắc phân quyền mới](FUNCTION_ACCESS.md).
Ngày rà soát: 16/10/2026. Nhánh `feature/qr-stocktake-product-records`, kế thừa bản chi tiết chứng từ `feature/asset-control-details`. Đây là bản phát triển, chưa phát hành lên website chính. Các quy tắc trong tài liệu này thay thế mô tả quyền duyệt kiểm kê ở tài liệu các phiên bản trước.

## Kiểm kê theo từng kho

1. Chọn **Kiểm kê QR → kho → Bắt đầu đếm bằng QR**. Phần mềm lưu số lượng, giá trị và mốc giao dịch của tồn thường tại lúc mở phiên. Không gộp tồn mượn tạm vào tồn thường.
2. Mỗi mã hàng có một QR tự sinh ngay khi tạo, kể cả không có ảnh. Mở hồ sơ hàng hóa để tải tem hoặc in nhãn. Mã đã có trước khi nâng cấp được bổ sung QR riêng; không đổi mã hàng cũ.
3. Quét bằng camera, máy quét USB có phím Enter, hoặc đọc ảnh QR. Mỗi lượt hợp lệ cộng **1 đơn vị tính của mã hàng**. Với camera, đưa tem ra khỏi khung khoảng một giây rồi quét đơn vị tiếp theo; giữ yên một tem không cộng liên tục. QR chung theo mã hàng không chứng minh hai lượt quét là hai tài sản khác nhau; nhân viên phải đưa từng đơn vị qua điểm đếm đúng quy trình.
4. Nếu đếm thủ công hoặc cần sửa, chọn **Ghi / sửa tổng số thực đếm**, nhập tổng rồi ghi. Số này thay thế tổng cũ, có lịch sử trước/sau và người sửa. Mã chưa đếm được đánh dấu riêng; không tự đổi thành 0. Không tìm thấy hàng phải xác nhận thực đếm 0.
5. Mã có hàng thực tế ngoài sổ vẫn có thể thêm vào phiên. Phần tăng chưa có giá bình quân phải nhập đơn giá, được nhập 0 nếu có căn cứ hàng không thu tiền. Phần giảm tính theo giá trị bình quân của tồn thường, không tự chọn giá giảm.
6. Ghi kết luận/lý do, bấm **Chốt biên bản & lập phiếu điều chỉnh**. Có chênh lệch: lập phiếu `ADJUST` chỉ chứa phần tăng/giảm. Không chênh lệch: hoàn tất biên bản, không tạo phiếu điều chỉnh. Cả hai trường hợp này đều chưa tự ghi thay đổi tồn.
7. Tổng giám đốc mở **Chờ tôi duyệt**, kiểm tra biên bản nguồn và từng dòng, rồi duyệt **phiếu điều chỉnh**. Chỉ lúc duyệt thành công, giao dịch ghi sổ mới thay đổi tồn. Không có một thao tác duyệt biên bản riêng có thể tự điều chỉnh trước phiếu.

Quản trị viên cấp quyền riêng **Tổng giám đốc: duyệt biên bản kiểm kê và điều chỉnh tồn** tại màn hình nhân viên. Không tự cấp quyền này cho tài khoản hiện có, nhóm quản lý kho hoặc ngay cả tài khoản quản trị. Người lập không được tự duyệt. Các phiếu kiểm kê nhập số thủ công và điều chỉnh trực tiếp của luồng cũ cũng phải qua quyền đặc biệt này, không trở thành đường vòng cho quản lý kho.

Phiên QR đã chốt không sửa số đếm hoặc sửa phiếu điều chỉnh nguồn. Khi cần làm lại, giữ biên bản cũ, hủy phiếu chưa ghi sổ với lý do rồi mở phiên mới. Nếu Tổng giám đốc yêu cầu sửa, phải kiểm đếm lại bằng phiên mới. Phiên bỏ dở có thể được người mở hoặc quản trị viên hủy với lý do, giữ lịch sử.

Biên bản giữ bản chụp mã, tên và đơn vị tính tại thời điểm đưa hàng vào phiên; sửa tên danh mục sau này không làm thay tên trên biên bản cũ. Mã và đơn vị tính không được đổi khi đã tham gia chứng từ hoặc kiểm kê; khác quy cách thì tạo mã mới. Trạng thái biên bản hiển thị theo phiếu liên kết: chờ Tổng giám đốc, đã điều chỉnh, yêu cầu kiểm đếm lại hoặc đã hủy.

## Tránh dùng số kiểm kê đã cũ

Phần mềm không khóa mọi hoạt động kho suốt thời gian đếm. Thay vào đó, nếu kho phát sinh giao dịch làm thay đổi tồn sau lúc mở phiên, hệ thống chặn chốt và chặn duyệt điều chỉnh dựa trên mốc cũ, kể cả giao dịch mới của mã chưa có trong danh sách hoặc tổng biến động về 0. Cần thống nhất thời gian kiểm kê với nhân viên kho rồi mở phiên mới để đếm lại. Phiên phải mở và ghi số trong ngày hôm nay; phiên sang ngày không tiếp tục ghi số.

Ghi số có mã yêu cầu duy nhất và phiên bản dòng. Mất phản hồi sau khi máy chủ đã nhận: phần mềm giữ lượt chưa xác nhận, chặn quét tiếp/chốt phiếu, cho **xác minh/gửi lại** cùng lượt đó. Không quét bù vì có thể đã được ghi. Dữ liệu đã được máy chủ xác nhận nằm trong database; máy quét không hỗ trợ kiểm đếm ngoại tuyến.

Biên bản in theo kho có số sổ, thực đếm, chênh lệch, kết luận, trạng thái phiếu điều chỉnh và vị trí ký. Đây là mẫu nội bộ hiện tại; chưa phải chữ ký số hoặc biểu mẫu pháp lý đã được công ty phê chuẩn. Có thể thay mẫu sau khi chủ dự án cung cấp.

## Hồ sơ hàng hóa và hóa đơn

- **Ảnh:** tùy chọn lúc tạo hoặc bổ sung trong hồ sơ; tối đa 5 ảnh/mã. JPG, PNG, WebP tối đa 8 MB đầu vào, 20 triệu điểm ảnh; ảnh nhận diện được thu nhỏ và bỏ EXIF trước khi lưu.
- **Hóa đơn/hồ sơ nhận hàng:** thêm tại phiếu nhập, tối đa 20 bản ghi hồ sơ/đợt. Nhận PDF, ảnh hoặc XML; tối đa 8 MB/tệp, PDF không mật khẩu và tối đa 200 trang. Lưu loại hồ sơ, số/ngày hóa đơn, tên tệp, người và thời điểm tải. Số bản ghi bị đánh dấu không dùng vẫn tính trong hạn mức để giữ lịch sử.
- **Cách sắp xếp:** hóa đơn thuộc đợt nhập, không nhân bản theo từng dòng sản phẩm. Một hóa đơn cho nhiều mã hàng được lưu một lần; khi mở mỗi mã liên quan, phần lịch sử hiển thị hóa đơn bên trong đúng đợt nhập. Lần nhập A thứ nhất và thứ hai là hai nhóm riêng; phân trang 20 đợt/trang.
- **Sửa hồ sơ:** không ghi đè hóa đơn cũ. Đánh dấu không sử dụng với lý do rồi thêm hồ sơ đúng; giữ bản gốc và lịch sử. Có thể gắn lại cùng nội dung tệp với metadata đúng bằng bản ghi mới. Nội dung, số lượng và giá trị phiếu đã ghi sổ không bị đổi bởi thao tác hồ sơ.
- **Quyền:** xem tệp qua đăng nhập và kiểm tra quyền phiếu/kho. Nhân viên không có quyền kho không tải được hóa đơn chỉ nhờ biết UUID. Ảnh nhận diện dùng chung cho người dùng đã đăng nhập. Bổ sung hồ sơ nhập dành cho người lập còn quyền, quản lý kho nhận hoặc quản trị viên.

Ảnh nhận diện có thể được tối ưu; hóa đơn/PDF/XML giữ nguyên bytes và SHA-256 lúc nhận. Tải lại từ Drive phải khớp kích thước và SHA-256; tệp bị sửa ngoài phần mềm sẽ bị báo cần khôi phục bản gốc. Không có chức năng xác thực chữ ký số hóa đơn điện tử trong đợt này.

Một QR hiện đại diện **mã hàng**, không đại diện số serial/tài sản cá thể. Lịch sử hóa đơn theo đợt nhập là hồ sơ mua hàng; chưa phân bổ đơn vị xuất ra thuộc hóa đơn nào theo FIFO hoặc số lô. Tồn vẫn định giá bình quân. Khi phát triển bàn giao tài sản cá thể, cần bổ sung mã tài sản/serial riêng.

## Google Drive: cấu trúc và giới hạn

Thư mục đã được chủ dự án cho phép:

`1ZR6b7rB5KJOh9LjSkoVIcFqEKHp5o0Mp`

```text
Thư mục gốc của bạn/
  Hàng hóa/
    MÃ-HÀNG/
      ảnh...
  Hóa đơn/
    2026/
      PK-000001/
        hóa đơn, giao nhận, chất lượng...
```

Thư mục con được tạo khi có tệp đầu tiên. Phần mềm không tạo quyền chia sẻ công khai. Quyền chia sẻ sẵn có từ thư mục gốc vẫn do chủ Drive quản lý. Database chỉ lưu liên kết nội bộ, mã tệp Drive, thông tin hồ sơ, kích thước và mã đối chiếu; bản online không lưu bytes ảnh/PDF trong database hoặc ổ đĩa tạm Render, và không tự chuyển sang nơi lưu khác khi Drive lỗi.

**Trạng thái hiện tại:** đã có mã tích hợp và kiểm thử giao thức bằng mô phỏng; chưa có kết nối Google OAuth thật, chưa tạo thư mục hoặc tải tệp thật lên Drive của bạn. Liên kết thư mục không tự cấp quyền API. Các ảnh/PDF demo nằm trong database thử nghiệm riêng với `DEBUG=1`.

## Cấu hình Google một lần trước khi dùng tệp online

Thực hiện trên bản thử trước, sau đó dùng cấu hình riêng của website chính. Không gửi client secret, refresh token, mật khẩu hoặc file `.env` vào chat/Git.

1. Tạo/chọn Google Cloud project dưới tài khoản công ty sở hữu Drive. Trong **APIs & Services**, bật **Google Drive API** và **Google Picker API**. Việc bật API không tự thay đổi gói dung lượng Drive; lưu trữ vẫn dùng hạn mức của tài khoản được kết nối.
2. Cấu hình OAuth consent screen: tên ứng dụng, email hỗ trợ, người dùng phù hợp và phạm vi `https://www.googleapis.com/auth/drive.file`. Với Gmail cá nhân dùng External; khi đang Testing phải thêm đúng tài khoản vào Test users. Refresh token của ứng dụng External ở Testing thường hết hạn sau 7 ngày với phạm vi Drive, nên cần xử lý trạng thái Production theo yêu cầu của Google trước khi vận hành dài hạn. Phạm vi `drive.file` được Google xếp loại non-sensitive; Google vẫn có thể yêu cầu các bước xác minh tùy cấu hình ứng dụng.
3. Tạo OAuth client loại **Web application**. Authorized JavaScript origin là chính xác origin HTTPS của website, không có đường dẫn. Authorized redirect URI là địa chỉ hiển thị tại **Cấu hình → Google Drive**. Với domain hiện tại: `https://ki-m-so-t-n-i-b.onrender.com/settings/drive/callback/`. Domain mới cần đăng ký URI tương ứng, không tự thay thế cấu hình production khi chưa chuyển.
4. Tạo API key cho Picker trong cùng project, giới hạn API cần dùng cho Picker và HTTP referrer của website, ví dụ `https://ki-m-so-t-n-i-b.onrender.com/*`. Lấy **Project number** dạng số, không dùng Project ID dạng chữ.
5. Tại Environment của hosting bản thử, đặt:

   | Tên | Giá trị |
   | --- | --- |
   | `PRIVATE_MEDIA_PROVIDER` | `drive` |
   | `GOOGLE_DRIVE_CLIENT_ID` | OAuth Web client ID |
   | `GOOGLE_DRIVE_CLIENT_SECRET` | Client secret, nhập bảo mật |
   | `GOOGLE_PICKER_API_KEY` | API key đã giới hạn referrer/API |
   | `GOOGLE_CLOUD_PROJECT_NUMBER` | Project number |
   | `GOOGLE_DRIVE_EXPECTED_FOLDER_ID` | `1ZR6b7rB5KJOh9LjSkoVIcFqEKHp5o0Mp` |
   | `INVENTORY_COMPANY_NAME` | Tên công ty in trên biên bản |

6. Đăng nhập phần mềm bằng quản trị viên, mở **Google Drive**, chọn **Kết nối tài khoản Google của bạn**, đăng nhập đúng tài khoản sở hữu thư mục và chấp thuận. Tiếp tục **Chọn thư mục qua Google**, chọn đúng thư mục trên. Picker cấp quyền theo phạm vi `drive.file`; không thay bằng dán link thư mục hoặc bật chia sẻ công khai.
7. Tải một ảnh và một PDF thử, mở lại hồ sơ bằng tài khoản đúng quyền; thử tài khoản không có quyền kho; đối chiếu thư mục và dung lượng trên Drive. Chỉ ghi nhận hoàn tất tích hợp khi thử thật các bước này thành công.

Refresh token được mã hóa trong database bằng khóa dẫn xuất từ `SECRET_KEY`; access token ngắn hạn chỉ lưu cache bộ nhớ và chỉ cấp cho Picker sau kiểm tra quản trị + CSRF. Không đổi `SECRET_KEY` hoặc tài khoản/thư mục lưu trữ khi đã có hồ sơ mà chưa chuyển khóa/dữ liệu. Cấu hình hiện chặn đổi tài khoản/thư mục nếu đã có tệp. Tài khoản dịch vụ không phải lựa chọn phù hợp để tận dụng dung lượng Drive cá nhân theo cách chỉ chia sẻ thư mục.

## Vận hành và sao lưu

Sao lưu database và hồ sơ Drive là hai việc riêng. Khôi phục database không tự khôi phục file đã bị xóa/sửa trên Drive. Giữ tài khoản lưu trữ ổn định, theo dõi dung lượng, sao lưu/kiểm tra khôi phục cả hai. Lỗi Google, hết hạn quyền hoặc hết dung lượng phải báo chưa lưu, cho thử lại và không tạo hồ sơ giả thành công. Một lần Google đã lưu nhưng transaction database thất bại có thể để lại tệp chưa gắn hồ sơ; lần thử lại tìm theo mã đối chiếu trong đúng thư mục để hạn chế nhân bản, không tự xóa file trên Drive.

Tài liệu triển khai và giới hạn kiểm tra: [phát hành](RELEASE_PROCESS.md), [kết quả kiểm tra](QR_VALIDATION.md), [định hướng quản lý công ty](COMPANY_PLATFORM_REVIEW.md).

## Nguồn tham khảo

- [Odoo: kiểm kê và barcode](https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/barcode/operations/adjustments.html): tách số đếm và thao tác áp dụng điều chỉnh.
- [ERPNext: Purchase Receipt](https://docs.frappe.io/erpnext/user/manual/en/purchase-receipt): thực nhận, thiếu/không nhận và chứng từ nhận hàng.
- [Google: chọn phạm vi Drive](https://developers.google.com/workspace/drive/api/guides/api-specific-auth), [OAuth web server](https://developers.google.com/identity/protocols/oauth2/web-server), [Google Picker](https://developers.google.com/workspace/drive/picker/guides/overview), [xử lý lỗi Drive](https://developers.google.com/workspace/drive/api/guides/handle-errors).
- [html5-qrcode](https://scanapp.org/html5-qrcode-docs/docs/intro): đọc QR camera/ảnh trong trình duyệt. Bản vendored 2.3.8, có giấy phép và thông tin nguồn tại `static/vendor/`.
