import logging

import resend
from django.conf import settings
from django.core import signing
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

logger = logging.getLogger(__name__)


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

    subject = "Verify Your Email!"

    html_content = render_to_string(
        "verify_email.html", {"user": user, "verify_url": verify_url}
    )

    text_content = f"""
    Hi {user.first_name},

    Welcome to Receipt Admin! Please verify your email by clicking the link below:
    {verify_url}

    Thank you!
    """

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

    subject = "Reset your Receipt Admin password."

    html_content = render_to_string(
        "password_reset_email.html",
        {
            "user": user,
            "reset_url": reset_url,
        },
    )

    text_content = f"""
    Hi {user.first_name},

    You requested to reset your password. Click the link below:
    {reset_url}

    If you did not request this, ignore this email.
    """

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
