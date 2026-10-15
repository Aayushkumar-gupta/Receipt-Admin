from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Profile"


class CustomUserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
        "get_email_verified",
    )

    def get_email_verified(self, obj):
        return hasattr(obj, "userprofile") and obj.userprofile.email_verified

    get_email_verified.short_description = "Email Verified"
    get_email_verified.boolean = True


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
