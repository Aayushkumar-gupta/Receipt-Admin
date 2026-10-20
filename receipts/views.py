import csv
import json
import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import get_template
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.views.decorators.http import require_POST
from xhtml2pdf import pisa

from accounts.models import UserProfile

from .models import Receipt, ReceiptItem

FIELD_LABELS = {
    "first_name": "first name",
    "last_name": "last name",
    "phone_number": "phone number",
    "address": "address",
}


def add_field_errors(request, error):
    for field, errors in error.message_dict.items():
        messages.error(request, f"Check the {field.replace('_', ' ')}. {errors[0]}")


def complete_profile_url(next_url):
    return f"{reverse('complete_profile')}?{urlencode({'next': next_url})}"


def join_words(words):
    if len(words) < 2:
        return "".join(words)
    return f"{', '.join(words[:-1])} and {words[-1]}"


def home(request):
    return render(request, "home.html")


@login_required
def dashboard(request):
    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)

    if request.method == "POST":
        goal = request.POST.get("goal", "").strip()
        if len(goal) > 200:
            messages.error(request, "Your goal must be 200 characters or fewer.")
        else:
            profile.goal = goal
            profile.save()
            messages.success(request, "Your goal is saved.")
        return redirect("dashboard")

    receipts = Receipt.objects.filter(user=user)

    total_receipts = receipts.count()
    total_revenue = sum(r.sub_total for r in receipts if not r.refund and r.is_staged)
    pending_receipts = receipts.filter(is_staged=False).count()
    recent_receipts = receipts.order_by("-date", "-pk")[:5]

    context = {
        "total_receipts": total_receipts,
        "total_revenue": total_revenue,
        "pending_receipts": pending_receipts,
        "recent_receipts": recent_receipts,
        "profile": profile,
    }

    return render(request, "dashboard.html", context)


@login_required
def my_receipts(request):
    search_query = request.GET.get("search", "")
    receipts = Receipt.objects.filter(is_staged=True, user=request.user)
    if search_query:
        receipts = receipts.filter(invoice_number__icontains=search_query)
    receipts = receipts.order_by("-date", "-pk")
    return render(request, "my_receipts.html", {"receipts": receipts})


EXPORT_COLUMNS = [
    "Invoice",
    "Date",
    "Buyer",
    "Buyer email",
    "Buyer phone",
    "Quantity",
    "Subtotal",
    "Tax rate",
    "Tax",
    "Total",
    "Status",
]


def spreadsheet_safe(value):
    # Spreadsheets run cells starting with these characters as formulas.
    value = "" if value == "N/A" else str(value)
    return f"'{value}" if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


def export_period(params):
    today = timezone.localdate()
    period = params.get("range", "this_year")
    if period == "last_year":
        year = today.year - 1
        return date(year, 1, 1), date(year, 12, 31), str(year)
    if period == "all":
        return None, None, "all"
    if period == "custom":
        try:
            start = date.fromisoformat(params.get("from", ""))
            end = date.fromisoformat(params.get("to", ""))
        except ValueError as e:
            raise ValueError(
                "Enter a start date and an end date for a custom range."
            ) from e
        if start > end:
            raise ValueError("Choose a start date that is before the end date.")
        return start, end, f"{start}-to-{end}"
    return date(today.year, 1, 1), today, str(today.year)


@login_required
def export_receipts(request):
    try:
        start, end, label = export_period(request.GET)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("my_receipts")

    receipts = Receipt.objects.filter(user=request.user, is_staged=True)
    if start:
        receipts = receipts.filter(date__gte=start, date__lte=end)
    receipts = receipts.prefetch_related("items").order_by("date", "pk")

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="receipts-{label}.csv"'
    # The byte order mark tells Excel the file is UTF-8, so accented names show correctly.
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(EXPORT_COLUMNS)
    for receipt in receipts:
        writer.writerow(
            [
                receipt.invoice_number,
                receipt.date.isoformat(),
                spreadsheet_safe(receipt.buyer_name),
                spreadsheet_safe(receipt.buyer_email),
                spreadsheet_safe(receipt.buyer_phone_number),
                sum(item.quantity for item in receipt.items.all()),
                receipt.sub_total,
                receipt.tax_rate,
                receipt.tax_amount,
                receipt.total_amount,
                "Refunded" if receipt.refund else "Final",
            ]
        )
    return response


def about(request):
    return render(request, "about.html")


def privacy(request):
    return render(request, "privacy.html")


def terms(request):
    return render(request, "terms.html")


@login_required
def profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    missing = [FIELD_LABELS[field] for field in profile.missing_fields()]
    return render(request, "profile.html", {"missing": join_words(missing)})


@login_required
def complete_profile(request):
    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)
    next_url = request.POST.get("next") or request.GET.get("next", "")
    if not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        next_url = reverse("dashboard")

    missing = profile.missing_fields()
    if not missing:
        return redirect(next_url)

    values = {field: request.POST.get(field, "").strip() for field in missing}
    if request.method == "POST":
        errors = [
            f"Enter your {FIELD_LABELS[field]}."
            for field, value in values.items()
            if not value
        ]
        phone = values.get("phone_number")
        if phone and not re.fullmatch(r"\d{10,15}", phone):
            errors.append("Phone number must be 10 to 15 digits.")

        if not errors:
            for field, value in values.items():
                setattr(user if field.endswith("_name") else profile, field, value)
            try:
                user.full_clean()
                profile.full_clean()
            except ValidationError as e:
                add_field_errors(request, e)
            else:
                user.save()
                profile.save()
                messages.success(request, "Your profile is complete.")
                return redirect(next_url)

        for error in errors:
            messages.error(request, error)

    return render(
        request,
        "complete_profile.html",
        {"missing": missing, "values": values, "next": next_url},
    )


@login_required
def staging_area(request):
    search_query = request.GET.get("search", "")
    receipts = Receipt.objects.filter(is_staged=False, user=request.user)
    if search_query:
        receipts = receipts.filter(invoice_number__icontains=search_query)
    receipts = receipts.order_by("-date", "-pk")
    return render(request, "staging_area.html", {"receipts": receipts})


@login_required
def view_receipt_pdf(request, pk):
    receipt = get_object_or_404(Receipt, pk=pk, user=request.user)
    template = get_template("receipt_pdf.html")
    html = template.render({"receipt": receipt})

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="receipt_{receipt.invoice_number}.pdf"'
    )

    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse("We had some errors while generating the PDF")
    return response


@login_required
def receipt_pdf(request, pk):
    receipt = get_object_or_404(Receipt, pk=pk, user=request.user)
    template = get_template("receipt_pdf.html")
    html = template.render({"receipt": receipt, "is_staged": receipt.is_staged})

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="receipt_{receipt.invoice_number}.pdf"'
    )

    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse("We had some errors while generating the PDF")
    return response


@login_required
def create_receipt(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if profile.missing_fields():
        return redirect(complete_profile_url(request.path))

    if not profile.email_verified:
        messages.info(request, "You must verify your email before creating a receipt.")
        return redirect("profile")

    seller_name = f"{request.user.first_name} {request.user.last_name}"
    seller_email = request.user.email
    seller_phone = profile.phone_number
    seller_address = profile.address

    if request.method == "POST":
        receipt = Receipt(
            user=request.user,
            seller_name=seller_name,
            seller_address=seller_address,
            seller_phone_number=seller_phone,
            seller_email=seller_email,
            buyer_name=request.POST.get("buyer_name", "").strip(),
            buyer_address=request.POST.get("buyer_address", "").strip() or "N/A",
            buyer_phone_number=request.POST.get("buyer_phone_number", "").strip(),
            buyer_email=request.POST.get("buyer_email", "").strip() or "N/A",
        )
        try:
            receipt.tax_rate = Decimal(request.POST.get("tax_rate") or "0")
            items = [
                ReceiptItem(
                    description=str(item.get("description", "")).strip(),
                    quantity=int(item.get("quantity")),
                    unit_price=Decimal(str(item.get("unit_price"))),
                )
                for item in json.loads(request.POST.get("items", "[]"))
            ]
            if (
                not items
                or not 0 <= receipt.tax_rate <= 100
                or any(i.quantity < 1 or i.unit_price < 0 for i in items)
            ):
                raise ValueError
            receipt.sub_total = sum(
                (i.quantity * i.unit_price for i in items), Decimal("0.00")
            )
            receipt.total_amount = (
                receipt.sub_total * (1 + receipt.tax_rate / 100)
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            for item in items:
                item.full_clean(exclude=["receipt"])
            receipt.full_clean()
        except (ValueError, TypeError, AttributeError, InvalidOperation):
            messages.error(
                request,
                "Some receipt values are invalid. Please check the items and tax rate.",
            )
            return render(request, "receipt_form.html")
        except ValidationError as e:
            add_field_errors(request, e)
            return render(request, "receipt_form.html")

        with transaction.atomic():
            receipt.save()
            for item in items:
                item.receipt = receipt
                item.line_price = item.quantity * item.unit_price
                item.save()

        return redirect("staging_area")

    return render(request, "receipt_form.html")


@login_required
@require_POST
def stage(request, pk):
    receipt = get_object_or_404(Receipt, pk=pk, user=request.user, is_staged=False)
    receipt.is_staged = True
    receipt.save()
    messages.success(request, f"Receipt {receipt.invoice_number} confirmed.")
    return redirect("my_receipts")


@login_required
def staging_edit(request, pk):
    receipt = get_object_or_404(Receipt, pk=pk, user=request.user)

    if receipt.is_staged:
        return redirect("staging_area")

    if request.method == "POST":
        receipt.buyer_name = request.POST.get("buyer_name", "").strip()
        receipt.buyer_address = request.POST.get("buyer_address", "").strip() or "N/A"
        receipt.buyer_phone_number = request.POST.get("buyer_phone_number", "").strip()
        receipt.buyer_email = request.POST.get("buyer_email", "").strip() or "N/A"
        try:
            receipt.tax_rate = Decimal(request.POST.get("tax_rate") or "0")
            items = [
                ReceiptItem(
                    description=str(item.get("description", "")).strip(),
                    quantity=int(item.get("quantity")),
                    unit_price=Decimal(str(item.get("unit_price"))),
                )
                for item in json.loads(request.POST.get("items", "[]"))
            ]
            if (
                not items
                or not 0 <= receipt.tax_rate <= 100
                or any(i.quantity < 1 or i.unit_price < 0 for i in items)
            ):
                raise ValueError
            receipt.sub_total = sum(
                (i.quantity * i.unit_price for i in items), Decimal("0.00")
            )
            receipt.total_amount = (
                receipt.sub_total * (1 + receipt.tax_rate / 100)
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            for item in items:
                item.full_clean(exclude=["receipt"])
            receipt.full_clean()
        except (ValueError, TypeError, AttributeError, InvalidOperation):
            messages.error(
                request,
                "Some receipt values are invalid. Please check the items and tax rate.",
            )
            return redirect("staging_edit", pk=receipt.pk)
        except ValidationError as e:
            add_field_errors(request, e)
            return redirect("staging_edit", pk=receipt.pk)

        with transaction.atomic():
            receipt.save()
            receipt.items.all().delete()
            for item in items:
                item.receipt = receipt
                item.line_price = item.quantity * item.unit_price
                item.save()

        return redirect("staging_area")

    items = list(receipt.items.values("description", "quantity", "unit_price"))

    return render(
        request,
        "staging_edit.html",
        {
            "receipt": receipt,
            "items": items,
        },
    )


@login_required
@require_POST
def staging_delete(request, pk):
    receipt = get_object_or_404(Receipt, pk=pk, user=request.user, is_staged=False)
    receipt.delete()
    messages.success(request, "Draft deleted.")
    return redirect("staging_area")


@login_required
def update_profile(request):
    if request.method == "POST":
        user = request.user
        profile, _ = UserProfile.objects.get_or_create(user=user)

        new_email = request.POST.get("email", user.email).strip().lower()
        new_phone = request.POST.get("phone_number", profile.phone_number).strip()
        new_address = request.POST.get("address", "").strip()
        current_password = request.POST.get("current_password", "")

        if not new_address:
            messages.error(request, "Enter your address.")
            return redirect("profile")
        profile.address = new_address

        # Email and phone appear on receipts, so changing them needs the password.
        sensitive_change = new_email != user.email or new_phone != profile.phone_number
        if sensitive_change and not user.check_password(current_password):
            messages.error(
                request,
                "Your current password is incorrect. "
                "Enter it to change your email or phone number.",
            )
            return redirect("profile")

        if new_email != user.email:
            if len(new_email) > 150:
                messages.error(request, "Email must be 150 characters or fewer.")
                return redirect("profile")
            if (
                User.objects.filter(
                    Q(email__iexact=new_email) | Q(username__iexact=new_email)
                )
                .exclude(pk=user.pk)
                .exists()
            ):
                messages.error(
                    request, "That email is already used by another account."
                )
                return redirect("profile")
            user.email = new_email
            user.username = new_email
            profile.email_verified = False

        if new_phone != profile.phone_number:
            if not re.fullmatch(r"\d{10,15}", new_phone):
                messages.error(request, "Phone number must be 10 to 15 digits.")
                return redirect("profile")
            profile.phone_number = new_phone

        user.first_name = request.POST.get("first_name", user.first_name).strip()
        user.last_name = request.POST.get("last_name", user.last_name).strip()
        if not user.first_name or not user.last_name:
            messages.error(request, "First name and last name are required.")
            return redirect("profile")

        try:
            user.full_clean()
            profile.full_clean(exclude=["phone_number"])
        except ValidationError as e:
            add_field_errors(request, e)
            return redirect("profile")

        user.save()
        profile.save()

        messages.success(request, "Your profile is saved.")
        return redirect("profile")

    return redirect("profile")


@login_required
@require_POST
def refund(request, pk):
    receipt = get_object_or_404(
        Receipt, pk=pk, user=request.user, is_staged=True, refund=False
    )
    receipt.refund = True
    receipt.save()
    messages.success(request, f"Receipt {receipt.invoice_number} refunded.")
    return redirect("my_receipts")


def health(request):
    return JsonResponse({"status": "ok"})


def favicon(request):
    return redirect(static("receipts/favicon.ico"), permanent=True)
