import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models, transaction


class Receipt(models.Model):
    refund = models.BooleanField(default=False)
    is_staged = models.BooleanField(default=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    invoice_number = models.CharField(max_length=20, blank=True, unique=True)
    seller_name = models.CharField(max_length=301)
    seller_address = models.TextField(max_length=255)
    seller_phone_number = models.CharField(max_length=20)
    seller_email = models.CharField(max_length=254, default="example@gmail.com")
    buyer_name = models.CharField(max_length=301)
    buyer_address = models.TextField(max_length=255)
    buyer_phone_number = models.CharField(max_length=20)
    buyer_email = models.CharField(max_length=254, default="example@gmail.com")
    date = models.DateField(auto_now_add=True)
    sub_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=8.25)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"Receipt #{self.invoice_number} for {self.buyer_name}"

    def save(self, *args, **kwargs):
        if self.invoice_number:
            return super().save(*args, **kwargs)
        # Number the invoice from the row's own id, so two receipts saved at once can't collide.
        with transaction.atomic():
            self.invoice_number = uuid.uuid4().hex[:20]
            super().save(*args, **kwargs)
            self.invoice_number = f"INV-{self.pk:04d}"
            super().save(update_fields=["invoice_number"])

    @property
    def tax_amount(self):
        return self.total_amount - self.sub_total


class ReceiptItem(models.Model):
    receipt = models.ForeignKey(Receipt, related_name="items", on_delete=models.CASCADE)
    description = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_price = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True
    )

    def __str__(self):
        return f"{self.quantity} x {self.description}"

    def save(self, *args, **kwargs):
        if self.quantity and self.unit_price:
            self.line_price = Decimal(self.quantity) * Decimal(self.unit_price)
        super().save(*args, **kwargs)
