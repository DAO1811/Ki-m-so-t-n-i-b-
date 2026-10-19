from uuid import uuid4

from django import forms


class LoanReturnForm(forms.Form):
    submission_key = forms.UUIDField(widget=forms.HiddenInput(), initial=uuid4)
    revision = forms.IntegerField(
        widget=forms.HiddenInput(), required=False, min_value=1
    )
    note = forms.CharField(
        label="Ghi chú trả hàng",
        required=False,
        max_length=1000,
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "placeholder": "Tình trạng hàng, người bàn giao hoặc ghi chú nếu cần…",
            }
        ),
    )

    def __init__(self, *args, items, editing=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.items = items
        old = (
            dict(editing.lines.values_list("product_id", "quantity")) if editing else {}
        )
        if editing:
            self.fields["submission_key"].required = False
            self.fields["revision"].required = True
            self.initial.update(revision=editing.revision, note=editing.note)
        for item in items:
            product = item["product"]
            self.fields[f"quantity_{product.pk}"] = forms.DecimalField(
                label=f"Số trả {product.sku}",
                required=False,
                initial=old.get(product.pk, 0),
                min_value=0,
                max_value=item["available"],
                max_digits=16,
                decimal_places=3,
                widget=forms.NumberInput(
                    attrs={
                        "step": "0.001",
                        "min": "0",
                        "max": format(item["available"], "f"),
                        "data-available": format(item["available"], "f"),
                        "inputmode": "decimal",
                    }
                ),
            )

    def clean(self):
        data = super().clean()
        self.quantities = {
            item["product"].pk: data.get(f"quantity_{item['product'].pk}") or 0
            for item in self.items
        }
        if not self.errors and not any(self.quantities.values()):
            raise forms.ValidationError(
                "Nhập số thực trả cho ít nhất một mặt hàng; để 0 ở hàng chưa trả."
            )
        return data
