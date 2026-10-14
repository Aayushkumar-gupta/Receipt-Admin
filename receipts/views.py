from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404
from django.template.loader import get_template
from django.http import HttpResponse, JsonResponse
from xhtml2pdf import pisa
from .models import Receipts, ReceiptItem
from django.contrib.auth.decorators import login_required
import json
import re
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from django.contrib import messages
from accounts.models import UserProfile
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.contrib.auth.models import User


def home(request):
    return render(request, 'home.html')


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
            messages.success(request, "Your goal has been updated!")
        return redirect('dashboard')

    receipts = Receipts.objects.filter(user_id=user)

    total_receipts = receipts.count()
    total_revenue = sum(r.sub_total for r in receipts if not r.refund and r.is_staged)
    pending_receipts = receipts.filter(is_staged=False).count()
    recent_receipts = receipts.order_by('-date')[:5]

    context = {
        'total_receipts': total_receipts,
        'total_revenue': total_revenue,
        'pending_receipts': pending_receipts,
        'recent_receipts': recent_receipts,
        'profile': profile,
    }

    return render(request, 'dashboard.html', context)


@login_required
def my_receipts(request):
    search_query = request.GET.get('search', '')
    receipts = Receipts.objects.filter(is_staged=True, user_id=request.user)
    if search_query:
        receipts = receipts.filter(invoice_number__icontains=search_query)
    receipts = receipts.order_by('-date')
    return render(request, 'my_receipts.html', {'receipts': receipts})


def about(request):
    return render(request, 'about.html')


@login_required
def profile(request):
    UserProfile.objects.get_or_create(user=request.user)
    return render(request, 'profile.html')


@login_required
def staging_area(request):
    search_query = request.GET.get('search', '')
    receipts = Receipts.objects.filter(is_staged=False, user_id=request.user)
    if search_query:
        receipts = receipts.filter(invoice_number__icontains=search_query)
    receipts = receipts.order_by('-date')
    return render(request, 'staging_area.html', {'receipts': receipts})


@login_required
def view_receipt_pdf(request, pk):
    receipt = get_object_or_404(Receipts, pk=pk, user_id=request.user)
    template = get_template("receipt_pdf.html")
    html = template.render({"receipt": receipt})

    response = HttpResponse(content_type="application/pdf")
    response['Content-Disposition'] = f'inline; filename="receipt_{receipt.invoice_number}.pdf"'

    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse("We had some errors while generating the PDF")
    return response


@login_required
def receipt_pdf(request, pk):
    receipt = get_object_or_404(Receipts, pk=pk, user_id=request.user)
    template = get_template("receipt_pdf.html")
    html = template.render({"receipt": receipt, "is_staged": receipt.is_staged})

    response = HttpResponse(content_type="application/pdf")
    response['Content-Disposition'] = f'attachment; filename="receipt_{receipt.invoice_number}.pdf"'

    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse("We had some errors while generating the PDF")
    return response


@login_required
def create_receipt(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if not profile.email_verified:
        messages.info(request, "You must verify your email before creating a receipt.")
        return redirect("profile")

    if not profile.address or profile.address.strip() == "":
        messages.warning(request, "You must add your address in your profile before creating a receipt.")
        return redirect("profile")

    seller_name = f"{request.user.first_name} {request.user.last_name}"
    seller_email = request.user.email
    seller_phone = profile.phone_number
    seller_address = profile.address or "Default Address"

    if request.method == 'POST':
        receipt = Receipts(
            user_id=request.user,
            seller_name=seller_name,
            seller_address=seller_address,
            seller_phone_number=seller_phone,
            seller_email=seller_email,
            buyer_name=request.POST.get('buyer_name', '').strip(),
            buyer_address=request.POST.get('buyer_address', '').strip() or "N/A",
            buyer_phone_number=request.POST.get('buyer_phone_number', '').strip(),
            buyer_email=request.POST.get('buyer_email', '').strip() or "N/A",
        )
        try:
            receipt.tax_rate = Decimal(request.POST.get('tax_rate') or '0')
            items = [
                ReceiptItem(
                    description=str(item.get('description', '')).strip(),
                    quantity=int(item.get('quantity')),
                    unit_price=Decimal(str(item.get('unit_price'))),
                )
                for item in json.loads(request.POST.get('items', '[]'))
            ]
            if not items or not 0 <= receipt.tax_rate <= 100 or any(i.quantity < 1 or i.unit_price < 0 for i in items):
                raise ValueError
            receipt.sub_total = sum((i.quantity * i.unit_price for i in items), Decimal('0.00'))
            receipt.total_amount = (receipt.sub_total * (1 + receipt.tax_rate / 100)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            for item in items:
                item.full_clean(exclude=['receipt'])
            receipt.full_clean()
        except (ValueError, TypeError, AttributeError, InvalidOperation):
            messages.error(request, "Some receipt values are invalid. Please check the items and tax rate.")
            return render(request, 'receipt_form.html')
        except ValidationError as e:
            for field, errors in e.message_dict.items():
                messages.error(request, f"{field.replace('_', ' ').capitalize()}: {errors[0]}")
            return render(request, 'receipt_form.html')

        with transaction.atomic():
            receipt.save()
            for item in items:
                item.receipt = receipt
                item.line_price = item.quantity * item.unit_price
                item.save()

        return redirect('staging_area')

    return render(request, 'receipt_form.html')


@login_required
@require_POST
def stage(request, pk):
    receipt = get_object_or_404(Receipts, pk=pk, user_id=request.user, is_staged=False)
    receipt.is_staged = True
    receipt.save()
    messages.success(request, "Staging Successful!")
    return redirect('my_receipts')


@login_required
def staging_edit(request, pk):
    receipt = get_object_or_404(Receipts, pk=pk, user_id=request.user)

    # prevent editing staged/confirmed receipts
    if receipt.is_staged:
        return redirect("staging_area")

    if request.method == "POST":
        receipt.buyer_name = request.POST.get('buyer_name', '').strip()
        receipt.buyer_address = request.POST.get('buyer_address', '').strip() or "N/A"
        receipt.buyer_phone_number = request.POST.get('buyer_phone_number', '').strip()
        receipt.buyer_email = request.POST.get('buyer_email', '').strip() or "N/A"
        try:
            receipt.tax_rate = Decimal(request.POST.get('tax_rate') or '0')
            items = [
                ReceiptItem(
                    description=str(item.get('description', '')).strip(),
                    quantity=int(item.get('quantity')),
                    unit_price=Decimal(str(item.get('unit_price'))),
                )
                for item in json.loads(request.POST.get('items', '[]'))
            ]
            if not items or not 0 <= receipt.tax_rate <= 100 or any(i.quantity < 1 or i.unit_price < 0 for i in items):
                raise ValueError
            receipt.sub_total = sum((i.quantity * i.unit_price for i in items), Decimal('0.00'))
            receipt.total_amount = (receipt.sub_total * (1 + receipt.tax_rate / 100)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            for item in items:
                item.full_clean(exclude=['receipt'])
            receipt.full_clean()
        except (ValueError, TypeError, AttributeError, InvalidOperation):
            messages.error(request, "Some receipt values are invalid. Please check the items and tax rate.")
            return redirect("staging_edit", pk=receipt.pk)
        except ValidationError as e:
            for field, errors in e.message_dict.items():
                messages.error(request, f"{field.replace('_', ' ').capitalize()}: {errors[0]}")
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

    return render(request, "staging_edit.html", {
        "receipt": receipt,
        "items": items,
    })


@login_required
@require_POST
def staging_delete(request, pk):
    receipt = get_object_or_404(Receipts, pk=pk, user_id=request.user, is_staged=False)
    receipt.delete()
    messages.error(request, "Receipt Deleted.")
    return redirect("staging_area")


@login_required
def update_profile(request):
    if request.method == "POST":
        user = request.user
        profile, _ = UserProfile.objects.get_or_create(user=user)

        new_email = request.POST.get("email", user.email).strip()
        new_phone = request.POST.get("phone_number", profile.phone_number).strip()
        new_address = request.POST.get("address", "").strip()
        current_password = request.POST.get("current_password", "")

        # Always allow address update (no password needed)
        if new_address:
            profile.address = new_address

        # Password required for sensitive changes
        if new_email != user.email or new_phone != profile.phone_number:
            if not user.check_password(current_password):
                messages.error(request, "Incorrect password. Cannot update email or phone number!")
                return redirect("profile")

        if new_email != user.email:
            if len(new_email) > 150:
                messages.error(request, "Email must be 150 characters or fewer.")
                return redirect("profile")
            if User.objects.filter(Q(email__iexact=new_email) | Q(username__iexact=new_email)).exclude(pk=user.pk).exists():
                messages.error(request, "That email is already used by another account.")
                return redirect("profile")
            user.email = new_email
            user.username = new_email
            profile.email_verified = False  # reset verification

        if new_phone != profile.phone_number:
            if not re.fullmatch(r'\d{10,15}', new_phone):
                messages.error(request, "Phone number must be 10 to 15 digits.")
                return redirect("profile")
            profile.phone_number = new_phone

        # Update first/last name (no password needed)
        user.first_name = request.POST.get("first_name", user.first_name).strip()
        user.last_name = request.POST.get("last_name", user.last_name).strip()
        if not user.first_name or not user.last_name:
            messages.error(request, "First name and last name are required.")
            return redirect("profile")

        try:
            user.full_clean()
            profile.full_clean(exclude=['phone_number'])
        except ValidationError as e:
            for field, errors in e.message_dict.items():
                messages.error(request, f"{field.replace('_', ' ').capitalize()}: {errors[0]}")
            return redirect("profile")

        user.save()
        profile.save()

        messages.success(request, "Profile updated successfully!")
        return redirect("profile")

    return redirect("profile")


@login_required
@require_POST
def refund(request, pk):
    receipt = get_object_or_404(Receipts, pk=pk, user_id=request.user, is_staged=True, refund=False)
    receipt.refund = True
    receipt.save()
    messages.info(request, "Refund Granted!")
    return redirect("my_receipts")


def test(request):
    return JsonResponse({"status": "ok"})
