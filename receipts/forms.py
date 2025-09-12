from django import forms
from .models import Receipts, ReceiptItem

class ReceiptForm(forms.ModelForm):
    class Meta:
        model = Receipts
        fields = ['buyer_name', 'buyer_address', 'buyer_phone_number', 'tax_rate', 'sub_total', 'total_amount']
        widgets = {
            'tax_rate': forms.NumberInput(attrs={'value': '8.25', 'step': '0.01'}),
            'sub_total': forms.NumberInput(attrs={'readonly': True}),
            'total_amount': forms.NumberInput(attrs={'readonly': True}),
        }

class ReceiptItemForm(forms.ModelForm):
    class Meta:
        model = ReceiptItem
        fields = ['description', 'quantity', 'unit_price', 'line_price']
        widgets = {
            'line_price': forms.NumberInput(attrs={'readonly': True}),
        }