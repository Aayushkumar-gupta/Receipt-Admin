import re
from django.core.exceptions import ValidationError

class StrongPasswordValidator:
    # List of common passwords
    common_passwords = ["password", "123456", "12345678", "qwerty", "abc123"]

    def validate(self, password, user=None):
        errors = []

        # Minimum length
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long.")

        # Uppercase
        if not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter.")

        # Lowercase
        if not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter.")

        # Number
        if not re.search(r'\d', password):
            errors.append("Password must contain at least one number.")

        # Special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Password must contain at least one special character.")

        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return (
            "Your password must be at least 8 characters long, contain at least one uppercase letter, one lowercase letter, one number, one special character, not be entirely numeric."
        )
