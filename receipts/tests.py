import json
import logging
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.db import DatabaseError
from django.template.loader import get_template
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile

from .models import Receipt, ReceiptItem

PASSWORD = "Passw0rd!"


def setUpModule():
    # Keep expected 4xx warnings (and deliberate 500s) out of the test output.
    logging.getLogger("django.request").setLevel(logging.CRITICAL)


def tearDownModule():
    logging.getLogger("django.request").setLevel(logging.NOTSET)


def make_user(email="ann@example.com", verified=True, address="1 Main St"):
    user = User.objects.create_user(
        username=email,
        email=email,
        password=PASSWORD,
        first_name="Ann",
        last_name="Lee",
    )
    UserProfile.objects.create(
        user=user, phone_number="1234567890", address=address, email_verified=verified
    )
    return user


def make_receipt(user, staged=False, refunded=False, **fields):
    receipt = Receipt.objects.create(
        user=user,
        is_staged=staged,
        refund=refunded,
        seller_name="Ann Lee",
        seller_address="1 Main St",
        seller_phone_number="1234567890",
        buyer_name=fields.pop("buyer_name", "Bob"),
        buyer_address="2 Oak Ave",
        buyer_phone_number="5551234567",
        sub_total=fields.pop("sub_total", Decimal("10.00")),
        total_amount=fields.pop("total_amount", Decimal("10.83")),
        **fields,
    )
    ReceiptItem.objects.create(
        receipt=receipt, description="Widget", quantity=2, unit_price=Decimal("5.00")
    )
    return receipt


def items_json(*rows):
    return json.dumps(
        [{"description": d, "quantity": q, "unit_price": p} for d, q, p in rows]
    )


def messages_of(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


RECEIPT_FORM = {
    "buyer_name": "Bob",
    "buyer_phone_number": "5551234567",
    "buyer_email": "",
    "buyer_address": "",
    "tax_rate": "8.25",
    "items": items_json(("Widget", "2", "10.00"), ("Gadget", "1", "5.50")),
}
INVALID_VALUES_MESSAGE = (
    "Some receipt values are invalid. Please check the items and tax rate."
)


class HealthCheckTests(TestCase):
    def test_health_returns_ok(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_old_test_url_is_gone(self):
        self.assertEqual(self.client.get("/test/").status_code, 404)


class SeoTests(TestCase):
    def test_robots_txt_blocks_private_pages_and_points_to_sitemap(self):
        response = self.client.get(reverse("robots"))

        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertContains(response, "Disallow: /dashboard/")
        self.assertContains(response, "Sitemap: http://testserver/sitemap.xml")

    def test_sitemap_lists_only_public_pages(self):
        response = self.client.get(reverse("sitemap"))

        for name in ("home", "about", "sign_up", "login"):
            with self.subTest(name):
                self.assertContains(response, f"<loc>http://testserver{reverse(name)}")
        self.assertNotContains(response, reverse("dashboard"))

    def test_favicon_redirects_to_the_static_icon(self):
        response = self.client.get("/favicon.ico")

        self.assertEqual(response.status_code, 301)
        self.assertTrue(response["Location"].endswith("receipts/favicon.ico"))

    def test_home_has_search_and_social_metadata(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, "<title>Receipt Admin | Receipts for sellers")
        self.assertContains(response, '<meta name="robots" content="index, follow">')
        self.assertContains(
            response, '<link rel="canonical" href="http://testserver/">'
        )
        self.assertContains(response, 'property="og:image"')
        self.assertContains(response, '"@type": "WebApplication"')

    def test_private_pages_are_not_indexed(self):
        self.client.force_login(make_user())

        for name in ("dashboard", "password_reset"):
            with self.subTest(name):
                response = self.client.get(reverse(name))
                self.assertContains(response, '<meta name="robots" content="noindex">')


class PublicPagesTests(TestCase):
    def test_public_pages_load(self):
        for name in ("home", "about", "login", "sign_up", "password_reset"):
            with self.subTest(name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_footer_shows_the_current_year(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, f"&copy; {timezone.now().year}")

    def test_private_pages_require_login(self):
        for name in ("dashboard", "my_receipts", "staging_area", "create_receipt"):
            with self.subTest(name):
                response = self.client.get(reverse(name))
                self.assertRedirects(
                    response, f"{reverse('login')}?next={reverse(name)}"
                )


class AccessControlTests(TestCase):
    """A user can never see or change another user's receipts."""

    def setUp(self):
        self.owner = make_user()
        self.draft = make_receipt(self.owner)
        self.final = make_receipt(self.owner, staged=True)
        self.client.force_login(make_user("eve@example.com"))

    def test_other_users_receipts_return_404(self):
        requests = {
            "view PDF": ("get", reverse("view_receipt_pdf", args=[self.final.pk])),
            "download PDF": ("get", reverse("receipt_pdf", args=[self.final.pk])),
            "edit": ("get", reverse("staging_edit", args=[self.draft.pk])),
            "stage": ("post", reverse("stage", args=[self.draft.pk])),
            "delete": ("post", reverse("staging_delete", args=[self.draft.pk])),
            "refund": ("post", reverse("refund", args=[self.final.pk])),
        }
        for name, (method, url) in requests.items():
            with self.subTest(name):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 404)

        self.draft.refresh_from_db()
        self.final.refresh_from_db()
        self.assertFalse(self.draft.is_staged)
        self.assertFalse(self.final.refund)

    def test_other_users_receipts_are_not_listed(self):
        for name in ("my_receipts", "staging_area", "dashboard"):
            with self.subTest(name):
                response = self.client.get(reverse(name))
                self.assertNotContains(response, self.final.invoice_number)
                self.assertNotContains(response, self.draft.invoice_number)

    def test_state_changes_require_post(self):
        self.client.force_login(self.owner)
        for name, receipt in (
            ("stage", self.draft),
            ("staging_delete", self.draft),
            ("refund", self.final),
        ):
            with self.subTest(name):
                response = self.client.get(reverse(name, args=[receipt.pk]))
                self.assertEqual(response.status_code, 405)


class ReceiptListTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.first = make_receipt(self.user, staged=True)
        self.second = make_receipt(self.user, staged=True)

    def test_search_filters_by_invoice_number(self):
        response = self.client.get(reverse("my_receipts"), {"search": "0002"})

        self.assertEqual(list(response.context["receipts"]), [self.second])

    def test_staging_area_lists_drafts_only(self):
        draft = make_receipt(self.user)

        response = self.client.get(reverse("staging_area"), {"search": "INV"})

        self.assertEqual(list(response.context["receipts"]), [draft])

    def test_lists_show_buyer_status_and_confirmations(self):
        make_receipt(self.user, refunded=True, staged=True, buyer_name="Robert")
        draft = make_receipt(self.user, buyer_name="Linda")

        staging = self.client.get(reverse("staging_area"))
        mine = self.client.get(reverse("my_receipts"))

        self.assertContains(staging, "Linda")
        self.assertContains(staging, 'class="badge badge-draft"')
        self.assertContains(staging, f"Confirm {draft.invoice_number}?")
        self.assertContains(mine, 'class="badge badge-refunded"', count=1)
        self.assertContains(mine, 'class="badge badge-final"', count=2)

    def test_search_without_matches_offers_to_clear_it(self):
        response = self.client.get(reverse("my_receipts"), {"search": "nothing"})

        self.assertContains(response, "No receipts match")
        self.assertContains(response, "Clear search")


class PdfTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.receipt = make_receipt(self.user, staged=True)
        self.client.force_login(self.user)

    def test_view_pdf_inline(self):
        response = self.client.get(reverse("view_receipt_pdf", args=[self.receipt.pk]))

        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response["Content-Disposition"].startswith("inline"))
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_pdf_generation_errors_are_reported(self):
        with mock.patch("receipts.views.pisa.CreatePDF") as create_pdf:
            create_pdf.return_value.err = 1
            for name in ("view_receipt_pdf", "receipt_pdf"):
                with self.subTest(name):
                    response = self.client.get(reverse(name, args=[self.receipt.pk]))
                    self.assertContains(
                        response, "We had some errors while generating the PDF"
                    )

    def test_pdf_shows_the_tax_amount_and_the_receipt_status(self):
        draft = make_receipt(self.user)
        refunded = make_receipt(self.user, staged=True, refunded=True)
        cases = {self.receipt: "Paid", draft: "Draft", refunded: "Refunded"}

        for receipt, status in cases.items():
            with self.subTest(status):
                html = get_template("receipt_pdf.html").render({"receipt": receipt})
                self.assertIn("$0.83", html)
                self.assertRegex(html, rf"status[^>]*>{status}</td>")
                for other in set(cases.values()) - {status}:
                    self.assertNotRegex(html, rf"status[^>]*>{other}</td>")

    def test_download_pdf_as_attachment(self):
        response = self.client.get(reverse("receipt_pdf", args=[self.receipt.pk]))

        self.assertTrue(response["Content-Disposition"].startswith("attachment"))
        self.assertIn(self.receipt.invoice_number, response["Content-Disposition"])


class CreateReceiptTests(TestCase):
    url = reverse("create_receipt")

    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def post(self, **overrides):
        return self.client.post(self.url, {**RECEIPT_FORM, **overrides})

    def test_form_page_loads_with_the_default_tax_rate(self):
        response = self.client.get(self.url)

        self.assertTemplateUsed(response, "receipt_form.html")
        self.assertContains(response, 'value="8.25"')

    def test_rejected_form_keeps_what_was_entered(self):
        response = self.post(buyer_name="Bob Ray", tax_rate="250")

        self.assertContains(response, 'value="Bob Ray"')
        self.assertContains(response, 'value="250"')
        self.assertContains(response, "&quot;description&quot;: &quot;Widget&quot;")

    def test_requires_a_verified_email(self):
        UserProfile.objects.filter(user=self.user).update(email_verified=False)

        response = self.client.get(self.url)

        self.assertRedirects(response, reverse("profile"))

    def test_requires_an_address(self):
        UserProfile.objects.filter(user=self.user).update(address="")

        response = self.client.get(self.url)

        self.assertRedirects(response, reverse("profile"))
        self.assertIn(
            "You must add your address in your profile before creating a receipt.",
            messages_of(response),
        )

    def test_valid_receipt_is_saved_with_server_side_totals(self):
        response = self.post(sub_total="1.00", total_amount="1.00")

        self.assertRedirects(response, reverse("staging_area"))
        receipt = Receipt.objects.get()
        self.assertEqual(receipt.user, self.user)
        self.assertEqual(receipt.sub_total, Decimal("25.50"))
        self.assertEqual(receipt.total_amount, Decimal("27.60"))
        self.assertEqual(
            sorted(receipt.items.values_list("line_price", flat=True)),
            [Decimal("5.50"), Decimal("20.00")],
        )
        self.assertEqual(receipt.seller_name, "Ann Lee")
        self.assertEqual(receipt.buyer_email, "N/A")

    def test_total_rounds_half_up(self):
        self.post(items=items_json(("Widget", "1", "10.00")))

        self.assertEqual(Receipt.objects.get().total_amount, Decimal("10.83"))

    def test_unreadable_values_are_rejected(self):
        cases = {
            "tax rate not a number": {"tax_rate": "abc"},
            "tax rate NaN": {"tax_rate": "NaN"},
            "tax rate over 100": {"tax_rate": "150"},
            "negative tax rate": {"tax_rate": "-1"},
            "items not JSON": {"items": "{oops"},
            "items not a list": {"items": '{"a": 1}'},
            "no items": {"items": "[]"},
            "item not an object": {"items": '["x"]'},
            "blank quantity": {"items": items_json(("W", "", "1"))},
            "decimal quantity": {"items": items_json(("W", "1.5", "1"))},
            "zero quantity": {"items": items_json(("W", "0", "1"))},
            "negative price": {"items": items_json(("W", "1", "-5"))},
            "infinite price": {"items": items_json(("W", "1", "Infinity"))},
        }
        for name, overrides in cases.items():
            with self.subTest(name):
                response = self.post(**overrides)
                self.assertEqual(response.status_code, 200)
                self.assertIn(INVALID_VALUES_MESSAGE, messages_of(response))
        self.assertFalse(Receipt.objects.exists())

    def test_field_limits_are_enforced(self):
        cases = {
            "blank buyer name": (
                {"buyer_name": " "},
                "Buyer name: This field cannot be blank.",
            ),
            "buyer name too long": (
                {"buyer_name": "B" * 302},
                "Buyer name: Ensure this value has at most 301 characters (it has 302).",
            ),
            "blank description": (
                {"items": items_json((" ", "1", "1"))},
                "Description: This field cannot be blank.",
            ),
            "too many decimals": (
                {"items": items_json(("W", "1", "1.005"))},
                "Unit price: Ensure that there are no more than 2 decimal places.",
            ),
        }
        for name, (overrides, message) in cases.items():
            with self.subTest(name):
                response = self.post(**overrides)
                self.assertIn(message, messages_of(response))
        self.assertFalse(Receipt.objects.exists())

    def test_failure_while_saving_items_leaves_no_receipt(self):
        with (
            mock.patch.object(ReceiptItem, "save", side_effect=DatabaseError),
            self.assertRaises(DatabaseError),
        ):
            self.post()

        self.assertFalse(Receipt.objects.exists())


class StagingEditTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.receipt = make_receipt(self.user)
        self.url = reverse("staging_edit", args=[self.receipt.pk])
        self.client.force_login(self.user)

    def test_form_shows_saved_values_without_placeholders(self):
        Receipt.objects.filter(pk=self.receipt.pk).update(
            buyer_email="N/A", tax_rate=Decimal("0.00")
        )

        response = self.client.get(self.url)

        self.assertContains(response, 'value="Bob"')
        self.assertContains(response, 'value="0.00"')
        self.assertNotContains(response, 'value="N/A"')
        self.assertContains(response, 'id="items-data"')

    def post(self, **overrides):
        return self.client.post(self.url, {**RECEIPT_FORM, **overrides})

    def descriptions(self):
        return list(self.receipt.items.values_list("description", flat=True))

    def test_edit_replaces_items_and_recalculates_totals(self):
        response = self.post(
            items=items_json(("New", "3", "4.00")), tax_rate="10", total_amount="0.01"
        )

        self.assertRedirects(response, reverse("staging_area"))
        self.receipt.refresh_from_db()
        self.assertEqual(self.descriptions(), ["New"])
        self.assertEqual(self.receipt.sub_total, Decimal("12.00"))
        self.assertEqual(self.receipt.total_amount, Decimal("13.20"))

    def test_invalid_edit_keeps_the_existing_items(self):
        for items in (items_json(("W", "-1", "1")), "{oops"):
            with self.subTest(items=items):
                response = self.post(items=items)
                self.assertRedirects(response, self.url, fetch_redirect_response=False)
                self.assertIn(INVALID_VALUES_MESSAGE, messages_of(response))
                self.assertEqual(self.descriptions(), ["Widget"])

    def test_field_errors_are_reported_and_nothing_changes(self):
        response = self.post(buyer_name=" ")

        self.assertIn("Buyer name: This field cannot be blank.", messages_of(response))
        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.buyer_name, "Bob")

    def test_failure_while_saving_keeps_the_old_receipt(self):
        with (
            mock.patch.object(ReceiptItem, "save", side_effect=DatabaseError),
            self.assertRaises(DatabaseError),
        ):
            self.post(buyer_name="Changed", items=items_json(("New", "1", "1")))

        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.buyer_name, "Bob")
        self.assertEqual(self.descriptions(), ["Widget"])

    def test_staged_receipts_cannot_be_edited(self):
        staged = make_receipt(self.user, staged=True)

        response = self.client.post(
            reverse("staging_edit", args=[staged.pk]), {**RECEIPT_FORM}
        )

        self.assertRedirects(response, reverse("staging_area"))
        staged.refresh_from_db()
        self.assertEqual(staged.buyer_name, "Bob")
        self.assertEqual(staged.items.get().description, "Widget")

    def test_edit_page_does_not_prefill_na(self):
        self.receipt.buyer_email = "N/A"
        self.receipt.save()

        response = self.client.get(self.url)

        self.assertNotContains(response, 'value="N/A"')

    def test_item_descriptions_are_escaped_in_the_page(self):
        self.receipt.items.update(description='"><img src=x onerror=alert(1)>')

        response = self.client.get(self.url)

        self.assertNotContains(response, "<img src=x")


class StageDeleteRefundTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def test_stage_moves_a_draft_to_my_receipts(self):
        draft = make_receipt(self.user)

        response = self.client.post(reverse("stage", args=[draft.pk]))

        self.assertRedirects(response, reverse("my_receipts"))
        draft.refresh_from_db()
        self.assertTrue(draft.is_staged)

    def test_delete_removes_drafts_only(self):
        draft = make_receipt(self.user)
        final = make_receipt(self.user, staged=True)

        self.client.post(reverse("staging_delete", args=[draft.pk]))
        response = self.client.post(reverse("staging_delete", args=[final.pk]))

        self.assertFalse(Receipt.objects.filter(pk=draft.pk).exists())
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Receipt.objects.filter(pk=final.pk).exists())

    def test_refund_only_once_and_only_for_staged_receipts(self):
        final = make_receipt(self.user, staged=True)
        draft = make_receipt(self.user)

        response = self.client.post(reverse("refund", args=[final.pk]))
        self.assertRedirects(response, reverse("my_receipts"))
        final.refresh_from_db()
        self.assertTrue(final.refund)

        self.assertEqual(
            self.client.post(reverse("refund", args=[final.pk])).status_code, 404
        )
        self.assertEqual(
            self.client.post(reverse("refund", args=[draft.pk])).status_code, 404
        )


class InvoiceNumberTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_invoice_numbers_are_sequential_and_unique(self):
        numbers = [make_receipt(self.user).invoice_number for _ in range(3)]
        Receipt.objects.order_by("pk").last().delete()
        numbers.append(make_receipt(self.user).invoice_number)

        self.assertEqual(numbers, ["INV-0001", "INV-0002", "INV-0003", "INV-0004"])

    def test_editing_keeps_the_invoice_number(self):
        receipt = make_receipt(self.user)

        receipt.buyer_name = "Changed"
        receipt.save()

        receipt.refresh_from_db()
        self.assertEqual(receipt.invoice_number, "INV-0001")

    def test_long_seller_name_and_emails_are_stored(self):
        receipt = make_receipt(
            self.user,
            seller_email="s" * 240 + "@example.com",
            buyer_email="b" * 240 + "@example.com",
        )
        receipt.seller_name = "F" * 150 + " " + "L" * 150
        receipt.full_clean()
        receipt.save()

        receipt.refresh_from_db()
        self.assertEqual(len(receipt.seller_name), 301)

    def test_string_representations(self):
        receipt = make_receipt(self.user)

        self.assertEqual(str(receipt), "Receipt #INV-0001 for Bob")
        self.assertEqual(str(receipt.items.get()), "2 x Widget")


class DashboardTests(TestCase):
    url = reverse("dashboard")

    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def test_revenue_counts_finalized_receipts_before_tax(self):
        make_receipt(self.user, staged=True, sub_total=Decimal("10.00"))
        make_receipt(self.user, staged=True, sub_total=Decimal("5.00"))
        make_receipt(self.user, staged=True, refunded=True, sub_total=Decimal("99"))
        make_receipt(self.user, sub_total=Decimal("50.00"))

        response = self.client.get(self.url)

        self.assertEqual(response.context["total_revenue"], Decimal("15.00"))
        self.assertEqual(response.context["total_receipts"], 4)
        self.assertEqual(response.context["pending_receipts"], 1)

    def test_goal_is_saved_and_limited_to_200_characters(self):
        self.client.post(self.url, {"goal": "  Ship it  "})
        response = self.client.post(self.url, {"goal": "g" * 201})

        self.assertIn(
            "Your goal must be 200 characters or fewer.", messages_of(response)
        )
        self.assertEqual(UserProfile.objects.get(user=self.user).goal, "Ship it")

    def test_works_for_users_without_a_profile(self):
        admin = User.objects.create_superuser("admin", "admin@example.com", PASSWORD)
        self.client.force_login(admin)

        for name in ("dashboard", "profile", "create_receipt"):
            with self.subTest(name):
                response = self.client.get(reverse(name))
                self.assertIn(response.status_code, (200, 302))
        self.assertTrue(UserProfile.objects.filter(user=admin).exists())


class ProfileUpdateTests(TestCase):
    url = reverse("update_profile")

    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.form = {
            "first_name": "Ann",
            "last_name": "Lee",
            "email": "ann@example.com",
            "phone_number": "1234567890",
            "address": "1 Main St",
        }

    def post(self, **overrides):
        data = {**self.form, **overrides}
        return self.client.post(
            self.url, {k: v for k, v in data.items() if v is not None}
        )

    def reload(self):
        self.user.refresh_from_db()
        self.user.userprofile.refresh_from_db()
        return self.user, self.user.userprofile

    def test_get_redirects_to_the_profile_page(self):
        self.assertRedirects(self.client.get(self.url), reverse("profile"))

    def test_profile_page_never_reveals_the_password(self):
        response = self.client.get(reverse("profile"))

        self.assertNotContains(response, "data-password-toggle")
        self.assertNotContains(response, PASSWORD)
        self.assertNotContains(response, self.user.password)

    def test_name_and_address_change_without_password(self):
        response = self.post(first_name="Annie", address="2 Oak Ave")

        self.assertIn("Profile updated successfully!", messages_of(response))
        user, profile = self.reload()
        self.assertEqual(user.first_name, "Annie")
        self.assertEqual(profile.address, "2 Oak Ave")

    def test_phone_change_requires_the_password(self):
        for password in (None, "wrong"):
            with self.subTest(password=password):
                response = self.post(
                    phone_number="9999999999", current_password=password
                )
                self.assertIn(
                    "Incorrect password. Cannot update email or phone number!",
                    messages_of(response),
                )
        self.post(phone_number="9999999999", current_password=PASSWORD)

        self.assertEqual(self.reload()[1].phone_number, "9999999999")

    def test_email_change_updates_username_and_resets_verification(self):
        self.post(email="new@example.com", current_password=PASSWORD)

        user, profile = self.reload()
        self.assertEqual(user.username, "new@example.com")
        self.assertFalse(profile.email_verified)

    def test_invalid_changes_are_rejected(self):
        make_user("bo@example.com")
        cases = {
            "email in use": (
                {"email": "BO@example.com"},
                "That email is already used by another account.",
            ),
            "invalid email": (
                {"email": "not-an-email"},
                "Email: Enter a valid email address.",
            ),
            "email too long": (
                {"email": "a" * 145 + "@x.com"},
                "Email must be 150 characters or fewer.",
            ),
            "phone with letters": (
                {"phone_number": "12345abcde"},
                "Phone number must be 10 to 15 digits.",
            ),
            "blank first name": (
                {"first_name": " "},
                "First name and last name are required.",
            ),
            "address too long": (
                {"address": "x" * 256},
                "Address: Ensure this value has at most 255 characters (it has 256).",
            ),
        }
        for name, (overrides, message) in cases.items():
            with self.subTest(name):
                response = self.post(current_password=PASSWORD, **overrides)
                self.assertIn(message, messages_of(response))
        user, profile = self.reload()
        self.assertEqual(user.email, "ann@example.com")
        self.assertEqual(profile.address, "1 Main St")

    def test_missing_fields_keep_their_current_values(self):
        self.client.post(self.url, {"address": "3 Elm St"})

        user, profile = self.reload()
        self.assertEqual((user.first_name, user.email), ("Ann", "ann@example.com"))
        self.assertEqual(profile.address, "3 Elm St")

    def test_empty_address_is_not_shown_as_none(self):
        UserProfile.objects.filter(user=self.user).update(address="")

        response = self.client.get(reverse("profile"))

        self.assertNotContains(response, 'value="None"')
