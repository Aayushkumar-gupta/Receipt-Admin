from django.urls import reverse
from django.core import signing
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.conf import settings
from django.template.loader import render_to_string
import resend


def send_verification_email(user, request):
    # Generate UID and token
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = signing.dumps({"pk": user.pk, "email": user.email}, salt="accounts.verify-email")
    verify_url = request.build_absolute_uri(reverse('verify_email', args=[uid, token]))

    # Email subject
    subject = "Verify Your Email!"

    # Render HTML email template
    html_content = render_to_string('verify_email.html', {
        'user': user,
        'verify_url': verify_url
    })

    # Fallback plain text
    text_content = f"""
    Hi {user.first_name},

    Welcome to Receipt Admin! Please verify your email by clicking the link below:
    {verify_url}

    Thank you!
    """

    # Send the email
    try:
        resend.api_key = settings.RESEND_API_KEY
        response = resend.Emails.send({
            "from": settings.DEFAULT_FROM_EMAIL,
            "to": [user.email],
            "subject": subject,
            "html": html_content,
            "text": text_content,
        })
        print(f"Email sent to {user.email}, id: {response['id']}")
        return True
    except Exception as e:
        print(f"Error sending verification email: {e}")
        return False


def send_password_reset_email(user, reset_url):
    subject = "Reset your Receipt Admin password."

    # Render custom HTML email template
    html_content = render_to_string('password_reset_email.html', {
        'user': user,
        'reset_url': reset_url,
    })

    # Plain text fallback
    text_content = f"""
    Hi {user.first_name},

    You requested to reset your password. Click the link below:
    {reset_url}

    If you did not request this, ignore this email.
    """

    try:
        resend.api_key = settings.RESEND_API_KEY
        resend.Emails.send({
            "from": settings.DEFAULT_FROM_EMAIL,
            "to": [user.email],
            "subject": subject,
            "html": html_content,
            "text": text_content,
        })
        print(f"Password reset email sent to {user.email}")
    except Exception as e:
        print(f"Error sending password reset email: {e}")


def send_otp_sms(phone_number, otp):
    print(f"[DEV] OTP for {phone_number} is {otp}")
    return otp
