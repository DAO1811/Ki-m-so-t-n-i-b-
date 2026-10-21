import csv
from decimal import Decimal

from django.http import HttpResponse


def export_csv(name, headers, rows):
    from io import StringIO

    buffer = StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(
            [
                ("'" + v)
                if isinstance(v, str) and v.startswith(("=", "+", "-", "@", "\t", "\r"))
                else format(v, "f")
                if isinstance(v, Decimal)
                else v
                for v in row
            ]
        )
    # Encode once. Encoding each response.write with utf-8-sig adds a BOM to every row.
    response = HttpResponse(
        buffer.getvalue().encode("utf-8-sig"),
        content_type="text/csv; charset=utf-8-sig",
    )
    response["Content-Disposition"] = f'attachment; filename="{name}.csv"'
    return response
