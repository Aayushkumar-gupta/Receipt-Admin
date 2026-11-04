from django.contrib.auth.models import User
from django.db import models


class RateCounter(models.Model):
    key = models.CharField(max_length=100, unique=True)
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)

    def __str__(self):
        return self.key


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15)
    address = models.CharField(max_length=255, blank=True, default="")
    email_verified = models.BooleanField(default=False)
    goal = models.CharField(max_length=200, blank=True, default="")

    def __str__(self):
        return self.user.username

    def missing_fields(self):
        values = {
            "first_name": self.user.first_name,
            "last_name": self.user.last_name,
            "phone_number": self.phone_number,
            "address": self.address,
        }
        return [field for field, value in values.items() if not value.strip()]
