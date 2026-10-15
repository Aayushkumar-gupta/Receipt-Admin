from django.contrib.auth.models import User
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15)
    address = models.CharField(max_length=255, blank=True, default="")
    email_verified = models.BooleanField(default=False)
    goal = models.CharField(max_length=200, blank=True, default="")

    def __str__(self):
        return self.user.username
