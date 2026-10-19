import logging
import re
from unittest import mock

from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.contrib.messages import get_messages
from django.core import signing
from django.core.cache import cache
from django.db import IntegrityError
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode

from receipts.models import Receipt, ReceiptItem
from receipts.tests import make_receipt

from .models import UserProfile
from .utils import send_password_reset_email, send_verification_email
from .views import send_email_async

PASSWORD = "Passw0rd!"


def setUpModule():
    # Keep expected 4xx warnings and info logs out of the test output.
    logging.getLogger("django.request").setLevel(logging.ERROR)
    logging.getLogger("accounts").setLevel(logging.WARNING)


def tearDownModule():
    logging.getLogger("django.request").setLevel(logging.NOTSET)
    logging.getLogger("accounts").setLevel(logging.NOTSET)


def make_user(email="ann@example.com", verified=True, address="1 Main St", **kwargs):
    user = User.objects.create_user(
        username=email,
        email=email,
        password=PASSWORD,
        first_name=kwargs.pop("first_name", "Ann"),
        last_name=kwargs.pop("last_name", "Lee"),
    )
    UserProfile.objects.create(
        user=user,
        phone_number=kwargs.pop("phone_number", "1234567890"),
        address=address,
        email_verified=verified,
    )
    return user


def messages_of(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


def verification_link(user):
    uid = urlsafe_base64_encode(str(user.pk).encode())
    token = signing.dumps(
        {"pk": user.pk, "email": user.email}, salt="accounts.verify-email"
    )
    return reverse("verify_email", args=[uid, token])


SIGNUP_DATA = {
    "first_name": "Bo",
    "last_name": "Li",
    "email": "bo@example.com",
    "phonenumber": "1234567890",
    "password": PASSWORD,
    "confirm_password": PASSWORD,
}


@mock.patch("accounts.views.threading.Thread")
class SignUpTests(TestCase):
    url = reverse("sign_up")

    def post(self, **overrides):
        return self.client.post(self.url, {**SIGNUP_DATA, **overrides})

    def test_valid_sign_up_creates_user_and_profile(self, thread):
        response = self.post()

        self.assertRedirects(response, reverse("login"))
        user = User.objects.get(email="bo@example.com")
        self.assertEqual(user.username, "bo@example.com")
        self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(user.userprofile.phone_number, "1234567890")
        self.assertFalse(user.userprofile.email_verified)
        thread.return_value.start.assert_called_once()

    def test_surrounding_spaces_are_trimmed(self, thread):
        self.post(email="  bo@example.com ", phonenumber=" 1234567890 ")

        self.assertTrue(User.objects.filter(email="bo@example.com").exists())

    def test_duplicate_email_is_rejected_case_insensitively(self, thread):
        make_user("bo@example.com")

        response = self.post(email="BO@Example.com")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "An account with this email already exists.", messages_of(response)
        )
        self.assertEqual(User.objects.count(), 1)

    def test_weak_password_is_rejected_on_the_server(self, thread):
        response = self.post(password="weak", confirm_password="weak")

        self.assertIn(
            "Password must be at least 8 characters long.", messages_of(response)
        )
        self.assertFalse(User.objects.exists())

    def test_mismatched_passwords_are_rejected(self, thread):
        response = self.post(confirm_password="Different1!")

        self.assertIn("Passwords do not match.", messages_of(response))
        self.assertFalse(User.objects.exists())

    def test_invalid_fields_are_rejected(self, thread):
        cases = {
            "email": ("not-an-email", "Enter a valid email address."),
            "phonenumber": ("12345abcde", "Phone number must be 10 to 15 digits."),
            "first_name": ("   ", "First name and last name are required."),
        }
        for field, (value, message) in cases.items():
            with self.subTest(field=field):
                response = self.post(**{field: value})
                self.assertIn(message, messages_of(response))
                self.assertFalse(User.objects.exists())

    def test_phone_length_limits(self, thread):
        for phone in ("123456789", "1" * 16):
            with self.subTest(phone=phone):
                response = self.post(phonenumber=phone)
                self.assertIn(
                    "Phone number must be 10 to 15 digits.", messages_of(response)
                )

    def test_overlong_email_and_name_are_rejected(self, thread):
        response = self.post(email="a" * 145 + "@x.com")
        self.assertIn("Email must be 150 characters or fewer.", messages_of(response))

        response = self.post(first_name="A" * 151)
        self.assertIn(
            "First and last name must be 150 characters or fewer.",
            messages_of(response),
        )
        self.assertFalse(User.objects.exists())

    def test_empty_post_shows_errors_instead_of_crashing(self, thread):
        response = self.client.post(self.url, {})

        self.assertEqual(response.status_code, 200)
        self.assertIn("Enter a valid email address.", messages_of(response))
        self.assertFalse(User.objects.exists())

    def test_failed_profile_creation_rolls_back_the_user(self, thread):
        with mock.patch(
            "accounts.views.UserProfile.objects.create", side_effect=IntegrityError
        ):
            response = self.post()

        self.assertIn(
            "An account with this email already exists.", messages_of(response)
        )
        self.assertFalse(User.objects.exists())

    def test_error_message_is_shown_once(self, thread):
        response = self.post(email="not-an-email")

        self.assertContains(response, "Enter a valid email address.", count=1)
        self.assertContains(response, 'data-level="danger"')


class LoginTests(TestCase):
    url = reverse("login")

    def setUp(self):
        cache.clear()
        self.user = make_user()

    def login(self, password=PASSWORD, username="ann@example.com", url=None):
        return self.client.post(
            url or self.url, {"username": username, "password": password}
        )

    def test_valid_login_redirects_to_dashboard(self):
        response = self.login()

        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_login_redirects_to_safe_next_url(self):
        response = self.login(url=f"{self.url}?next=/my_receipts/")

        self.assertRedirects(response, reverse("my_receipts"))

    def test_login_ignores_next_urls_on_other_sites(self):
        for next_url in ("https://evil.example/", "//evil.example"):
            with self.subTest(next_url=next_url):
                self.client.logout()
                response = self.login(url=f"{self.url}?next={next_url}")
                self.assertRedirects(response, reverse("dashboard"))

    def test_wrong_password_keeps_next_and_shows_error(self):
        response = self.login(password="wrong", url=f"{self.url}?next=/my_receipts/")

        self.assertRedirects(
            response,
            f"{self.url}?next=%2Fmy_receipts%2F",
            fetch_redirect_response=False,
        )
        self.assertIn("Incorrect email or password.", messages_of(response))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_five_failures_lock_out_even_the_correct_password(self):
        for _ in range(5):
            self.login(password="wrong")

        response = self.login()

        self.assertIn(
            "Too many failed login attempts. Please try again in 15 minutes.",
            messages_of(response),
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_lockout_ignores_email_case_and_spares_other_users(self):
        make_user("bo@example.com")
        for _ in range(5):
            self.login(password="wrong")

        self.login(username="ANN@example.com")
        self.assertNotIn("_auth_user_id", self.client.session)

        response = self.login(username="bo@example.com")
        self.assertRedirects(response, reverse("dashboard"))

    def test_successful_login_resets_the_failure_count(self):
        for _ in range(4):
            self.login(password="wrong")
        self.login()

        self.assertIsNone(cache.get("login-fails:ann@example.com"))


class LogoutTests(TestCase):
    url = reverse("logout")

    def setUp(self):
        self.client.force_login(make_user())

    def test_logout_requires_post(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

    def test_post_logs_out(self):
        response = self.client.post(self.url)

        self.assertRedirects(response, reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_requires_csrf_token(self):
        client = self.client_class(enforce_csrf_checks=True)
        client.force_login(User.objects.get())

        response = client.post(self.url)

        self.assertEqual(response.status_code, 403)

    def test_navbar_logout_is_a_post_form(self):
        response = self.client.get(reverse("dashboard"))

        self.assertContains(response, f'<form method="post" action="{self.url}"')


class EmailVerificationTests(TestCase):
    def setUp(self):
        self.user = make_user(verified=False)

    def verified(self):
        self.user.userprofile.refresh_from_db()
        return self.user.userprofile.email_verified

    def test_link_verifies_the_email(self):
        response = self.client.get(verification_link(self.user))

        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        self.assertTrue(self.verified())

    def test_link_still_works_after_logging_in(self):
        link = verification_link(self.user)
        self.client.post(
            reverse("login"), {"username": self.user.email, "password": PASSWORD}
        )

        response = self.client.get(link)

        self.assertRedirects(response, reverse("profile"))
        self.assertTrue(self.verified())

    def test_link_expires_after_three_days(self):
        link = verification_link(self.user)
        future = signing.time.time() + 3 * 24 * 60 * 60 + 60

        with mock.patch("django.core.signing.time.time", return_value=future):
            response = self.client.get(link)

        self.assertIn(
            "This confirmation link has expired or is not valid.", messages_of(response)
        )
        self.assertFalse(self.verified())

    def test_tampered_or_mismatched_links_are_rejected(self):
        other = make_user("bo@example.com", verified=False)
        token = verification_link(self.user).rstrip("/").split("/")[-1]
        other_uid = urlsafe_base64_encode(str(other.pk).encode())
        old_style = default_token_generator.make_token(self.user)
        uid = urlsafe_base64_encode(str(self.user.pk).encode())
        bad_links = {
            "tampered token": verification_link(self.user)[:-4] + "abc/",
            "someone else's uid": reverse("verify_email", args=[other_uid, token]),
            "garbage uid": reverse("verify_email", args=["zzzz", token]),
            "old password-reset token": reverse("verify_email", args=[uid, old_style]),
        }
        for name, link in bad_links.items():
            with self.subTest(name):
                response = self.client.get(link)
                self.assertRedirects(response, reverse("sign_up"))
        self.assertFalse(self.verified())

    def test_link_stops_working_after_the_email_changes(self):
        link = verification_link(self.user)
        self.user.email = "new@example.com"
        self.user.save()

        self.client.get(link)

        self.assertFalse(self.verified())


@override_settings(RESEND_API_KEY="test-key")
class SendEmailTests(TestCase):
    def setUp(self):
        self.user = make_user(verified=False)
        self.request = RequestFactory().get("/")

    @mock.patch("accounts.utils.resend.Emails.send", return_value={"id": "abc"})
    def test_verification_email_contains_a_working_link(self, send):
        self.assertTrue(send_verification_email(self.user, self.request))

        payload = send.call_args.args[0]
        self.assertEqual(payload["to"], [self.user.email])
        link = re.search(r"http://testserver(\S+)", payload["text"]).group(1)
        self.client.get(link)
        self.user.userprofile.refresh_from_db()
        self.assertTrue(self.user.userprofile.email_verified)

    @mock.patch("accounts.utils.resend.Emails.send", side_effect=Exception("down"))
    def test_verification_email_failure_returns_false_and_is_logged(self, send):
        with self.assertLogs("accounts.utils", level="ERROR"):
            self.assertFalse(send_verification_email(self.user, self.request))

    @mock.patch("accounts.utils.resend.Emails.send", return_value={"id": "abc"})
    def test_password_reset_email_is_sent(self, send):
        send_password_reset_email(self.user, "http://testserver/reset/x/y/")

        payload = send.call_args.args[0]
        self.assertEqual(payload["to"], [self.user.email])
        self.assertIn("http://testserver/reset/x/y/", payload["text"])
        self.assertIn('href="http://testserver/reset/x/y/"', payload["html"])

    @mock.patch("accounts.utils.resend.Emails.send", side_effect=Exception("down"))
    def test_password_reset_email_failure_is_logged(self, send):
        with self.assertLogs("accounts.utils", level="ERROR"):
            send_password_reset_email(self.user, "http://testserver/reset/x/y/")

    @mock.patch("accounts.views.send_verification_email", side_effect=Exception("x"))
    def test_background_sign_up_email_failure_is_logged(self, send):
        with self.assertLogs("accounts.views", level="ERROR"):
            send_email_async(self.user, self.request)

    @override_settings(DEBUG=True, RESEND_API_KEY=None)
    @mock.patch("accounts.utils.resend.Emails.send")
    def test_local_development_logs_the_link_instead_of_emailing(self, send):
        with self.assertLogs("accounts.utils", level="INFO") as logs:
            self.assertTrue(send_verification_email(self.user, self.request))

        send.assert_not_called()
        self.assertIn("verification link for ann@example.com", logs.output[0])

    @override_settings(DEBUG=True, RESEND_API_KEY=None)
    @mock.patch("accounts.utils.resend.Emails.send")
    def test_local_development_logs_the_reset_link(self, send):
        with self.assertLogs("accounts.utils", level="INFO") as logs:
            send_password_reset_email(self.user, "http://testserver/reset/x/y/")

        send.assert_not_called()
        self.assertIn("password reset link for ann@example.com", logs.output[0])


@override_settings(RESEND_API_KEY="test-key")
class ResendVerificationTests(TestCase):
    url = reverse("resend_verification_email")

    def setUp(self):
        cache.clear()
        self.client.force_login(make_user(verified=False))

    def test_requires_post(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    @mock.patch("accounts.utils.resend.Emails.send", return_value={"id": "abc"})
    def test_success_and_one_minute_cooldown(self, send):
        response = self.client.post(self.url)
        self.assertIn(
            "We sent a new confirmation email. Check your inbox.", messages_of(response)
        )

        response = self.client.post(self.url)
        self.assertIn(
            "Please wait a minute before requesting another verification email.",
            messages_of(response),
        )
        send.assert_called_once()

    @mock.patch("accounts.utils.resend.Emails.send", side_effect=Exception("down"))
    def test_failure_is_reported(self, send):
        with self.assertLogs("accounts.utils", level="ERROR"):
            response = self.client.post(self.url)

        self.assertIn(
            "We could not send the confirmation email. Try again in a few minutes.",
            messages_of(response),
        )


class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = make_user()

    @mock.patch("accounts.views.send_password_reset_email")
    def test_reset_email_is_sent_to_existing_users(self, send):
        response = self.client.post(
            reverse("password_reset"), {"email": "ann@example.com"}
        )

        self.assertRedirects(response, reverse("password_reset_done"))
        user, reset_url = send.call_args.args
        self.assertEqual(user, self.user)
        self.assertIn("/reset/", reset_url)

    @mock.patch("accounts.views.send_password_reset_email")
    def test_unknown_email_looks_the_same(self, send):
        response = self.client.post(
            reverse("password_reset"), {"email": "nobody@example.com"}
        )

        self.assertRedirects(response, reverse("password_reset_done"))
        send.assert_not_called()

    def test_forgot_password_redirects_to_reset_page(self):
        response = self.client.get(reverse("forgot_password"))

        self.assertRedirects(response, reverse("password_reset"))

    def test_invalid_link_shows_message_instead_of_form(self):
        uid = urlsafe_base64_encode(str(self.user.pk).encode())

        response = self.client.get(f"/reset/{uid}/bad-token/", follow=True)

        self.assertContains(response, "invalid or has expired")
        self.assertNotContains(response, 'name="new_password1"')

    def test_valid_link_rejects_weak_password_and_accepts_strong_one(self):
        uid = urlsafe_base64_encode(str(self.user.pk).encode())
        token = default_token_generator.make_token(self.user)
        response = self.client.get(f"/reset/{uid}/{token}/", follow=True)
        form_url = response.redirect_chain[-1][0]

        response = self.client.post(
            form_url, {"new_password1": "weakpass", "new_password2": "weakpass"}
        )
        self.assertContains(
            response, "Password must contain at least one uppercase letter."
        )

        response = self.client.post(
            form_url,
            {"new_password1": "NewPassw0rd!", "new_password2": "NewPassw0rd!"},
        )
        self.assertRedirects(response, reverse("password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPassw0rd!"))


class ProfileModelTests(TestCase):
    def test_string_representation_is_the_username(self):
        self.assertEqual(str(make_user().userprofile), "ann@example.com")


class AdminTests(TestCase):
    def test_user_list_works_for_users_without_a_profile(self):
        admin = User.objects.create_superuser("admin", "admin@example.com", PASSWORD)
        self.client.force_login(admin)

        response = self.client.get(reverse("admin:auth_user_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Email Verified")


class DeleteAccountTests(TestCase):
    url = reverse("delete_account")

    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def test_requires_post(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_requires_login(self):
        self.client.logout()

        response = self.client.post(self.url, {"password": PASSWORD})

        self.assertRedirects(response, f"{reverse('login')}?next={self.url}")
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_wrong_password_keeps_the_account(self):
        receipt = make_receipt(self.user)

        response = self.client.post(self.url, {"password": "wrong"})

        self.assertRedirects(response, reverse("profile"))
        self.assertIn(
            "Your password is incorrect. Your account was not deleted.",
            messages_of(response),
        )
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertTrue(Receipt.objects.filter(pk=receipt.pk).exists())

    def test_deletes_the_user_and_their_receipts_and_logs_out(self):
        mine = make_receipt(self.user)
        theirs = make_receipt(make_user("bob@example.com"))

        response = self.client.post(self.url, {"password": PASSWORD})

        self.assertRedirects(response, reverse("home"))
        self.assertIn(
            "Your account and all your receipts are deleted.", messages_of(response)
        )
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(UserProfile.objects.filter(user_id=self.user.pk).exists())
        self.assertFalse(Receipt.objects.filter(pk=mine.pk).exists())
        self.assertFalse(ReceiptItem.objects.filter(receipt_id=mine.pk).exists())
        self.assertTrue(Receipt.objects.filter(pk=theirs.pk).exists())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_profile_page_shows_the_delete_form(self):
        response = self.client.get(reverse("profile"))

        self.assertContains(response, f'action="{self.url}"')
        self.assertContains(response, 'id="delete_password"')
