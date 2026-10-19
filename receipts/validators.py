import re

from django.core.exceptions import ValidationError


class StrongPasswordValidator:
    def validate(self, password, user=None):
        errors = []

        if len(password) < 8:
            errors.append("Password must be at least 8 characters long.")

        if not re.search(r"[A-Z]", password):
            errors.append("Password must contain at least one uppercase letter.")

        if not re.search(r"[a-z]", password):
            errors.append("Password must contain at least one lowercase letter.")

        if not re.search(r"\d", password):
            errors.append("Password must contain at least one number.")

        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Password must contain at least one special character.")

        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return (
            "Your password must be at least 8 characters long and contain at least one uppercase letter, "
            "one lowercase letter, one number, and one special character."
        )
