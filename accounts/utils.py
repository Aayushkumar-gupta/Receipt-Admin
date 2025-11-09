from django.core.mail import send_mail
from django.urls import reverse
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.conf import settings

def send_verification_email(user, request):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    verify_url = request.build_absolute_uri(reverse('verify_email', args=[uid, token]))

    subject = "Verify your Clear Slip account"
    message = f"Hello {user.first_name},\n\nPlease click the link below to verify your email:\n{verify_url}\n\nThank you!"
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])


def send_otp_sms(phone_number, otp):
    print(f"[DEV] OTP for {phone_number} is {otp}")
    return otp