import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import RateCounter

logger = logging.getLogger(__name__)

HOUR = timedelta(hours=1)
DAY = timedelta(days=1)

SIGNUPS_PER_IP_PER_HOUR = 5
RESETS_PER_IP_PER_HOUR = 5
EMAILS_PER_RECIPIENT_PER_DAY = 3
RESEND_COOLDOWN = timedelta(seconds=60)

# Verification stops first, so password resets can still go out during an attack.
VERIFICATION_EMAILS_PER_DAY = 60
ALL_EMAILS_PER_DAY = 90
EMAIL_ALERT_AT = 50


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (
        request.META.get("HTTP_CF_CONNECTING_IP")
        or forwarded.split(",")[0].strip()
        or request.META.get("REMOTE_ADDR", "")
    )


def hashed_key(kind, value):
    return f"{kind}:{salted_hmac(kind, str(value)).hexdigest()}"


def consume(key, limit, period):
    now = timezone.now()
    with transaction.atomic():
        RateCounter.objects.filter(expires_at__lte=now).delete()
        counter, _ = RateCounter.objects.select_for_update().get_or_create(
            key=key, defaults={"expires_at": now + period}
        )
        if counter.count >= limit:
            return None
        counter.count += 1
        counter.save(update_fields=["count"])
        return counter.count


def allow_signup(request):
    key = hashed_key("signup-ip", client_ip(request))
    return consume(key, SIGNUPS_PER_IP_PER_HOUR, HOUR) is not None


def allow_password_reset(request):
    key = hashed_key("reset-ip", client_ip(request))
    return consume(key, RESETS_PER_IP_PER_HOUR, HOUR) is not None


def allow_resend(user):
    key = hashed_key("resend-user", user.pk)
    return consume(key, 1, RESEND_COOLDOWN) is not None


def allow_email(recipient, daily_limit):
    if settings.DEBUG and not settings.RESEND_API_KEY:
        return True

    key = hashed_key("email-to", recipient.lower())
    if consume(key, EMAILS_PER_RECIPIENT_PER_DAY, DAY) is None:
        return False

    today = timezone.now().date()
    sent = consume(f"emails-sent:{today}", daily_limit, 2 * DAY)
    if sent is None:
        logger.error(f"Daily email budget of {daily_limit} reached; email not sent")
        return False
    if sent == EMAIL_ALERT_AT:
        logger.error(f"{EMAIL_ALERT_AT} emails sent today; check for sign-up abuse")
    return True
