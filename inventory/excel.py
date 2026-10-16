from decimal import Decimal, InvalidOperation
from zipfile import ZipFile
from django.core.exceptions import ValidationError
from openpyxl import load_workbook, Workbook
from .models import Product

HEADERS = ["ma_hang", "so_luong", "don_gia"]


def parse_receipt(file):
    errors = []
    try:
        with ZipFile(file) as archive:
            if (
                len(archive.infolist()) > 1000
                or sum(f.file_size for f in archive.infolist()) > 20 * 1024 * 1024
            ):
                raise ValidationError(
                    "Nội dung giải nén quá lớn, vui lòng dùng file mẫu đơn giản."
                )
        file.seek(0)
        workbook = load_workbook(
            file, read_only=True, data_only=False, keep_links=False
        )
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(
            "Không đọc được Excel. Hãy lưu file .xlsx theo mẫu rồi thử lại."
        ) from exc
    try:
        sheet = workbook.worksheets[0]
        if sheet.max_row and sheet.max_row > 1000:
            raise ValidationError(
                "File có quá nhiều dòng, hãy dùng file mẫu mới (tối đa 50 mã hàng / phiếu)."
            )
        if sheet.max_column and sheet.max_column > 20:
            raise ValidationError("File có quá nhiều cột. Chỉ dùng 3 cột của mẫu.")
        rows = sheet.iter_rows(max_row=1001, max_col=4)
        header = next(rows, None)
        if (
            not header
            or [str(c.value or "").strip() for c in header[:3]] != HEADERS
            or header[3].value is not None
        ):
            raise ValidationError(
                "Hàng đầu tiên phải gồm đúng 3 cột: ma_hang, so_luong, don_gia. Tải file mẫu để sử dụng."
            )
        result = []
        seen = set()
        for number, cells in enumerate(rows, start=2):
            if all(c.value is None for c in cells):
                continue
            if len(result) >= 50:
                raise ValidationError(
                    "Mỗi phiếu tối đa 50 mã hàng. Hãy chia thành nhiều file."
                )
            if any(c.data_type == "f" for c in cells):
                errors.append(f"Dòng {number}: không dùng công thức, hãy dán giá trị.")
                continue
            sku = str(cells[0].value or "").strip()
            if sku in seen:
                errors.append(f"Dòng {number}: mã {sku} bị trùng.")
                continue
            seen.add(sku)
            product = Product.objects.filter(sku=sku).first()
            if not product:
                errors.append(
                    f"Dòng {number}: mã hàng {sku or '(trống)'} chưa có trong danh mục."
                )
                continue
            try:
                if isinstance(cells[1].value, bool) or isinstance(cells[2].value, bool):
                    raise ValueError
                q = Decimal(str(cells[1].value))
                price = Decimal(str(cells[2].value))
                if (
                    not q.is_finite()
                    or not price.is_finite()
                    or q <= 0
                    or price < 0
                    or q >= Decimal("1e13")
                    or price >= Decimal("1e14")
                ):
                    raise ValueError
                if q != q.quantize(Decimal(".001")) or price != price.quantize(
                    Decimal(".0001")
                ):
                    raise ValueError
                if q * price >= Decimal("1e20"):
                    raise ValueError
            except (InvalidOperation, ValueError, TypeError):
                errors.append(
                    f"Dòng {number}: số lượng phải dương (tối đa 3 số lẻ), đơn giá không âm (tối đa 4 số lẻ), không để trống hoặc thêm dấu phân cách trong ô văn bản."
                )
                continue
            if cells[3].value is not None:
                errors.append(f"Dòng {number}: có dữ liệu ngoài 3 cột mẫu.")
                continue
            result.append(
                {
                    "product_id": product.pk,
                    "sku": product.sku,
                    "name": product.name,
                    "quantity": str(q),
                    "unit_price": str(price),
                    "amount": str((q * price).quantize(Decimal(".01"))),
                }
            )
        if errors:
            raise ValidationError(errors[:30])
        if not result:
            raise ValidationError("File chưa có dòng hàng hợp lệ.")
        return result
    finally:
        workbook.close()


def receipt_template():
    book = Workbook()
    sheet = book.active
    sheet.title = "Nhap kho"
    sheet.append(HEADERS)
    sheet.column_dimensions["A"].width = 25
    sheet.column_dimensions["B"].width = 20
    sheet.column_dimensions["C"].width = 25
    sheet.freeze_panes = "A2"
    return book
