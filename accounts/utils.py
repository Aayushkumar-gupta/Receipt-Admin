import logging

import resend
from django.conf import settings
from django.core import signing
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

logger = logging.getLogger(__name__)


def greeting(user):
    return f"Hi {user.first_name}," if user.first_name else "Hi,"


def send_verification_email(user, request):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = signing.dumps(
        {"pk": user.pk, "email": user.email}, salt="accounts.verify-email"
    )
    verify_url = request.build_absolute_uri(reverse("verify_email", args=[uid, token]))

    # Local development without a Resend key: print the link instead of emailing it.
    if settings.DEBUG and not settings.RESEND_API_KEY:
        logger.info(
            f"RESEND_API_KEY not set; verification link for {user.email}: {verify_url}"
        )
        return True

    subject = "Confirm your email address for Receipt Admin"

    html_content = render_to_string(
        "verify_email.html", {"user": user, "action_url": verify_url}
    )

    text_content = (
        f"{greeting(user)}\n\n"
        "Thanks for creating a Receipt Admin account. Open the link below to confirm "
        "your email address and start making receipts.\n\n"
        f"{verify_url}\n\n"
        "This link works for 3 days. If you did not sign up, you can ignore this email.\n"
    )

    try:
        resend.api_key = settings.RESEND_API_KEY
        response = resend.Emails.send(
            {
                "from": settings.DEFAULT_FROM_EMAIL,
                "to": [user.email],
                "subject": subject,
                "html": html_content,
                "text": text_content,
            }
        )
        logger.info(f"Verification email sent to {user.email}, id: {response['id']}")
        return True
    except Exception:
        logger.exception(f"Error sending verification email to {user.email}")
        return False


def send_password_reset_email(user, reset_url):
    if settings.DEBUG and not settings.RESEND_API_KEY:
        logger.info(
            f"RESEND_API_KEY not set; password reset link for {user.email}: {reset_url}"
        )
        return

    subject = "Reset your Receipt Admin password"

    html_content = render_to_string(
        "password_reset_email.html", {"user": user, "action_url": reset_url}
    )

    text_content = (
        f"{greeting(user)}\n\n"
        "We received a request to reset the password for your Receipt Admin account. "
        "Open the link below to choose a new one.\n\n"
        f"{reset_url}\n\n"
        "This link works for 1 hour. If you did not ask to reset your password, "
        "you can ignore this email.\n"
    )

    try:
        resend.api_key = settings.RESEND_API_KEY
        resend.Emails.send(
            {
                "from": settings.DEFAULT_FROM_EMAIL,
                "to": [user.email],
                "subject": subject,
                "html": html_content,
                "text": text_content,
            }
        )
        logger.info(f"Password reset email sent to {user.email}")
    except Exception:
        logger.exception(f"Error sending password reset email to {user.email}")
