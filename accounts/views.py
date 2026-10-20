import logging
import re
import threading

from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import PasswordResetView
from django.core import signing
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.encoding import force_bytes, force_str
from django.utils.http import (
    url_has_allowed_host_and_scheme,
    urlencode,
    urlsafe_base64_decode,
    urlsafe_base64_encode,
)
from django.views.decorators.http import require_POST

from receipts.models import Receipt

from .models import UserProfile
from .utils import send_password_reset_email, send_verification_email

logger = logging.getLogger(__name__)


def sign_up(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        phone_number = request.POST.get("phonenumber", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        errors = []
        if not first_name or not last_name:
            errors.append("First name and last name are required.")
        elif len(first_name) > 150 or len(last_name) > 150:
            errors.append("First and last name must be 150 characters or fewer.")

        try:
            validate_email(email)
            if len(email) > 150:
                errors.append("Email must be 150 characters or fewer.")
        except ValidationError:
            errors.append("Enter a valid email address.")

        if not re.fullmatch(r"\d{10,15}", phone_number):
            errors.append("Phone number must be 10 to 15 digits.")

        if password != confirm_password:
            errors.append("Passwords do not match.")
        else:
            try:
                validate_password(
                    password,
                    user=User(
                        username=email,
                        email=email,
                        first_name=first_name,
                        last_name=last_name,
                    ),
                )
            except ValidationError as e:
                errors.extend(e.messages)

        if (
            not errors
            and User.objects.filter(
                Q(email__iexact=email) | Q(username__iexact=email)
            ).exists()
        ):
            errors.append("An account with this email already exists.")

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, "sign_up.html")

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=email,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    password=password,
                    is_active=True,
                )
                UserProfile.objects.create(user=user, phone_number=phone_number)
        except IntegrityError:
            messages.error(request, "An account with this email already exists.")
            return render(request, "sign_up.html")

        # Send in the background so sign-up does not wait on the email API.
        threading.Thread(target=send_email_async, args=(user, request)).start()

        messages.success(
            request,
            "Your account is ready. "
            "Check your inbox for a link to confirm your email address.",
        )
        return redirect("login")

    return render(request, "sign_up.html")


def user_login(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    next_url = request.POST.get("next") or request.GET.get("next", "")
    login_url = reverse("login") + (
        f"?{urlencode({'next': next_url})}" if next_url else ""
    )

    if request.method == "POST":
        username = request.POST.get("username", "").strip().lower()
        password = request.POST.get("password", "")
        fail_key = f"login-fails:{username}"

        if cache.get(fail_key, 0) >= 5:
            messages.error(
                request,
                "Too many failed login attempts. Please try again in 15 minutes.",
            )
            return redirect(login_url)

        user = authenticate(request, username=username, password=password)

        if user is not None:
            logger.info(f"Login succeeded for user {user.pk}")
            cache.delete(fail_key)
            auth_login(request, user)
            if url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect("dashboard")

        cache.set(fail_key, cache.get(fail_key, 0) + 1, 15 * 60)
        messages.error(request, "Incorrect email or password.")
        return redirect(login_url)

    return render(request, "login.html")


@require_POST
def user_logout(request):
    auth_logout(request)
    request.session.flush()
    return redirect("home")


def forgot_password(request):
    return redirect("password_reset")


def verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
        data = signing.loads(
            token, salt="accounts.verify-email", max_age=60 * 60 * 24 * 3
        )
    except (
        User.DoesNotExist,
        signing.BadSignature,
        ValueError,
        TypeError,
        OverflowError,
    ):
        user = None

    if user and data["pk"] == user.pk and data["email"] == user.email:
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.email_verified = True
        profile.save()
        messages.success(request, "Your email address is confirmed.")
        if request.user.is_authenticated and request.user.id == user.id:
            return redirect("profile")
        else:
            return redirect("login")
    else:
        messages.error(request, "This confirmation link has expired or is not valid.")
        return redirect("sign_up")


def send_email_async(user, request):
    try:
        send_verification_email(user, request)
    except Exception:
        logger.exception(f"Failed to send verification email to {user.email}")


@login_required
@require_POST
def resend_verification_email(request):
    if not cache.add(f"verify-email-sent:{request.user.pk}", True, 60):
        messages.error(
            request,
            "Please wait a minute before requesting another verification email.",
        )
    elif send_verification_email(request.user, request):
        messages.success(request, "We sent a new confirmation email. Check your inbox.")
    else:
        messages.error(
            request,
            "We could not send the confirmation email. Try again in a few minutes.",
        )
    return redirect("profile")


class CustomPasswordResetView(PasswordResetView):
    template_name = "password_reset.html"
    success_url = reverse_lazy("password_reset_done")

    def form_valid(self, form):
        email = form.cleaned_data["email"]
        users = list(form.get_users(email))
        for user in users:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = self.request.build_absolute_uri(
                reverse(
                    "password_reset_confirm", kwargs={"uidb64": uid, "token": token}
                )
            )
            send_password_reset_email(user, reset_url)
        return redirect(self.success_url)


@login_required
@require_POST
def delete_account(request):
    user = request.user
    if not user.check_password(request.POST.get("password", "")):
        messages.error(
            request, "Your password is incorrect. Your account was not deleted."
        )
        return redirect("profile")

    with transaction.atomic():
        Receipt.objects.filter(user=user).delete()
        user.delete()

    auth_logout(request)
    messages.success(request, "Your account and all your receipts are deleted.")
    return redirect("home")
