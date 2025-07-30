from django import forms
from .models import Receipt

class ReceiptForm(forms.ModelForm):
    class Meta:
        model = Receipt
        fields = ['buyer_name', 'buyer_address', 'buyer_phone', 'product_name', 'quantity', 'price_per_unit', 'tax_rate', 'sub_total', 'total']
        widgets = {
            'tax_rate': forms.NumberInput(attrs={'value': '8.25', 'step': '0.01'}),
            'sub_total': forms.NumberInput(attrs={'readonly': True}),
            'total': forms.NumberInput(attrs={'readonly': True}),
        }
