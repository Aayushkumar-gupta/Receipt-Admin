from django import forms
from .models import Receipts

class ReceiptForm(forms.ModelForm):
    class Meta:
        model = Receipts
        fields = ['product_name', 'product_type', 'quantity', 'price', 'payment_method']  # adjust as per your model
