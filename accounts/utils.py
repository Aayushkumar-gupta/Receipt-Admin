from django.urls import reverse
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


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
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send()


def send_otp_sms(phone_number, otp):
    print(f"[DEV] OTP for {phone_number} is {otp}")
    return otp