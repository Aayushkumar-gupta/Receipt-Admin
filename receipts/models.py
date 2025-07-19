from django.db import models

# Create your models here.
class Receipts(models.Model):
    seller_name = models.CharField(max_length=100)
    seller_address = models.TextField(max_length=100)
    seller_phone_number = models.IntegerField(max_length=14)
    buyer_name = models.CharField(max_length=100)
    buyer_address = models.TextField(max_length=100)
    buyer_phone_number = models.IntegerField(max_length=14)
    date = models.DateField(auto_now_add=True)
    item_description = models.TextField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    

    def __self__(self):
        return f"Receipt #{self.id} for {self.buyer_name} on {self.date}"
    
    class Meta:
        verbose_name_plural = "Receipts"  
    

class Driver(models.Model):
    driver_name = models.CharField(max_length=100)
    driver_date_of_birth = models.DateField()
    driver_phone_number = models.IntegerField(max_length=14)
    vehicle_number = models.CharField()

    def __self__(self):
        return self.driver_name
    
    class Meta:
        verbose_name_plural = "Driver"  
    