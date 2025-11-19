from django.urls import reverse
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.conf import settings
from django.template.loader import render_to_string
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


def send_verification_email(user, request):
    # Generate UID and token
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
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

    # Create the email message
    message = Mail(
        from_email=settings.DEFAULT_FROM_EMAIL,
        to_emails=user.email,
        subject=subject,
        html_content=html_content,
    )

    # Send the email
    try:
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message)
        print(f"Email sent to {user.email}, status code: {response.status_code}")
    except Exception as e:
        print(f"Error sending verification email: {e}")


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

    message = Mail(
        from_email=settings.DEFAULT_FROM_EMAIL,
        to_emails=user.email,
        subject=subject,
        html_content=html_content
    )

    try:
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        sg.send(message)
        print(f"Password reset email sent to {user.email}")
    except Exception as e:
        print(f"Error sending password reset email: {e}")



def send_otp_sms(phone_number, otp):
    print(f"[DEV] OTP for {phone_number} is {otp}")
    return otp