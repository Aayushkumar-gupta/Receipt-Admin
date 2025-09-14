from django.db import models
from django.contrib.auth.models import User 
from decimal import Decimal

class Receipts(models.Model):
    is_staged = models.BooleanField(default=False)
    user_id = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    invoice_number = models.CharField(max_length=20, blank=True, unique=True)
    seller_name = models.CharField(max_length=100)
    seller_address = models.TextField(max_length=100)
    seller_phone_number = models.CharField(max_length=20)
    seller_email = models.CharField(max_length=50, default='example@gmail.com')
    buyer_name = models.CharField(max_length=100)
    buyer_address = models.TextField(max_length=100)
    buyer_phone_number = models.CharField(max_length=20)
    buyer_email = models.CharField(max_length=50, default='example@gmail.com')
    date = models.DateField(auto_now_add=True)
    sub_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=8.25)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            last_receipt = Receipts.objects.all().order_by('id').last()
            new_id = last_receipt.id + 1 if last_receipt else 1
            self.invoice_number = f"INV-{new_id:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Receipt #{self.invoice_number} for {self.buyer_name}"

class ReceiptItem(models.Model):
    receipt = models.ForeignKey(Receipts, related_name="items", on_delete=models.CASCADE)
    description = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_price = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.quantity and self.unit_price:
            # Ensure both are Decimals
            self.line_price = Decimal(self.quantity) * Decimal(self.unit_price)
        super().save(*args, **kwargs)
    

class Driver(models.Model):
    driver_name = models.CharField(max_length=100)
    driver_date_of_birth = models.DateField()
    driver_phone_number = models.CharField(max_length=14)
    vehicle_number = models.CharField()

    def __self__(self):
        return self.driver_name
    
    class Meta:
        verbose_name_plural = "Driver"  
    