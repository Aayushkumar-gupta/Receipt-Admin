from django.db import models
from django.contrib.auth.models import User 

# Create your models here.
class Receipts(models.Model):
    user_id = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    invoice_number = models.CharField(max_length=10, default="INV-0001")


    seller_name = models.CharField(max_length=100)
    seller_address = models.TextField(max_length=100)
    seller_phone_number = models.CharField(max_length=14)
    seller_email = models.CharField(max_length=50, default='example@gmail.com')

    buyer_name = models.CharField(max_length=100)
    buyer_address = models.TextField(max_length=100)
    buyer_phone_number = models.CharField(max_length=14)
    date = models.DateField(auto_now_add=True)

    item_description = models.TextField()
    item_quantity = models.CharField(max_length=10, default="1")
    unit_price = models.CharField(max_length=10, default="1")
    line_price = models.CharField(max_length=10, default="1")

    sub_total = models.DecimalField(max_digits=10, decimal_places=2)
    tax_rate = models.CharField(max_length=10, default="1")
    total_amount = models.CharField(max_length=10, default="1")
    

    def __self__(self):
        return f"Receipt #{self.id} for {self.buyer_name} on {self.date}"
    
    class Meta:
        verbose_name_plural = "Receipts"  
    

class Driver(models.Model):
    driver_name = models.CharField(max_length=100)
    driver_date_of_birth = models.DateField()
    driver_phone_number = models.CharField(max_length=14)
    vehicle_number = models.CharField()

    def __self__(self):
        return self.driver_name
    
    class Meta:
        verbose_name_plural = "Driver"  
    