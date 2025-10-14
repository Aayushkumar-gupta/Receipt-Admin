from django.shortcuts import render, redirect
from .models import Receipts
from django.shortcuts import get_object_or_404
from django.template.loader import get_template
from django.http import HttpResponse
from xhtml2pdf import pisa
from .models import Receipts, ReceiptItem
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.template.loader import get_template
import json
from decimal import Decimal
from .forms import ReceiptForm
from django.contrib import messages
from accounts.models import UserProfile


def home(request):
    return render(request, 'home.html')

@login_required
def dashboard(request):
    user = request.user
    profile = UserProfile.objects.get(user=user)

    # Handle goal update
    if request.method == "POST":
        goal = request.POST.get("goal")
        profile.goal = goal
        profile.save()
        messages.success(request, "Your goal has been updated!")
        return redirect('dashboard')

    # Query all receipts created by this user
    receipts = Receipts.objects.filter(user_id=user)

    total_receipts = receipts.count()
    total_revenue = sum(r.sub_total for r in receipts)
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
    receipts = Receipts.objects.filter(is_staged=True, user_id=request.user).order_by('-date')
    return render(request, 'my_receipts.html', {'receipts': receipts})

def about(request):
    return render(request, 'about.html')

@login_required
def profile(request):
    return render(request, 'profile.html')

def test(request):
    return render(request, 'test.html')

@login_required
def staging_area(request):
    receipts = Receipts.objects.filter(is_staged=False, user_id=request.user).order_by('-date')
    return render(request, 'staging_area.html', {'receipts': receipts})

@login_required
def view_receipt_pdf(request, pk):  # <-- view PDF in browser
    receipt = get_object_or_404(Receipts, pk=pk)
    template = get_template("receipt_pdf.html")
    html = template.render({"receipt": receipt})

    response = HttpResponse(content_type="application/pdf")
    # 'inline' tells the browser to display PDF instead of downloading
    response['Content-Disposition'] = f'inline; filename="receipt_{receipt.invoice_number}.pdf"'

    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse("We had some errors while generating the PDF")
    return response


@login_required
def receipt_pdf(request, pk):  # <-- add pk here
    receipt = get_object_or_404(Receipts, pk=pk)
    template = get_template("receipt_pdf.html")  # <-- correct template path
    html = template.render({"receipt": receipt, "is_staged": receipt.is_staged})

    response = HttpResponse(content_type="application/pdf")
    response['Content-Disposition'] = f'attachment; filename="receipt_{receipt.invoice_number}.pdf"'

    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse("We had some errors while generating the PDF")
    return response


@login_required
def create_receipt(request):
    profile = request.user.userprofile

    if not profile.email_verified or not profile.phone_verified:
        messages.info(request, "You must verify your email and phone number before creating a receipt.")
        return redirect("profile")
    
    if not profile.address or profile.address.strip() == "":
        messages.warning(request, "You must add your address in your profile before creating a receipt.")
        return redirect("profile")


    seller_name = f"{request.user.first_name} {request.user.last_name}"
    seller_email = request.user.email
    seller_phone = profile.phone_number
    seller_address = profile.address or "Default Address"

    if request.method == 'POST':
        receipt = Receipts.objects.create(
            user_id=request.user,
            seller_name=seller_name,
            seller_address=seller_address,
            seller_phone_number=seller_phone,
            seller_email=seller_email,
            buyer_name=request.POST.get('buyer_name'),
            buyer_address=request.POST.get('buyer_address'),
            buyer_phone_number=request.POST.get('buyer_phone_number'),
            buyer_email=request.POST.get('buyer_email'),
            tax_rate=Decimal(request.POST.get('tax_rate') or '0')
        )

        items_json = request.POST.get('items', '[]')  
        items = json.loads(items_json)

        sub_total = Decimal('0.00')
        for item in items:
            qty = int(item.get('quantity', 0))
            unit = Decimal(str(item.get('unit_price') or '0'))
            line_price = qty * unit

            ReceiptItem.objects.create(
                receipt=receipt,
                description=item.get('description', ''),
                quantity=qty,
                unit_price=unit,
                line_price=line_price
            )
            sub_total += line_price

        tax_rate = receipt.tax_rate or Decimal('0.00')
        total_amount = (sub_total + (sub_total * (tax_rate / Decimal('100')))).quantize(Decimal('0.01'))

        receipt.sub_total = sub_total
        receipt.total_amount = total_amount
        receipt.save()

        return redirect('staging_area')

    return render(request, 'receipt_form.html')



@login_required
def stage(request, pk):
    if request.method == 'POST':
        receipt = Receipts.objects.get(id = pk)
        receipt.is_staged = True
        receipt.save()
        messages.success(request, "Staging Successful!")
        return redirect('my_receipts')

@login_required
def staging_edit(request, pk):
    receipt = get_object_or_404(Receipts, id=pk)

    # prevent editing staged/confirmed receipts
    if receipt.is_staged:
        return redirect("staging_area")

    if request.method == "POST":
        # Only buyer info + totals are editable
        form = ReceiptForm(request.POST, instance=receipt)
        if form.is_valid():
            updated_receipt = form.save(commit=False)

            # Handle items from hidden JSON field
            items_json = request.POST.get("items", "[]")
            try:
                items = json.loads(items_json)
            except (ValueError, TypeError):
                items = []

            # Delete old items and create new ones
            updated_receipt.items.all().delete()
            for it in items:
                desc = it.get("description", "") or ""
                qty = int(it.get("quantity") or 0)
                try:
                    unit = Decimal(str(it.get("unit_price") or 0))
                except:
                    unit = Decimal("0")
                if desc or qty or unit:
                    ReceiptItem.objects.create(
                        receipt=updated_receipt,
                        description=desc,
                        quantity=qty,
                        unit_price=unit,
                    )

            updated_receipt.save()  # save buyer info and totals
            return redirect("staging_area")
    else:
        # GET request: prefill form with buyer info + totals
        form = ReceiptForm(instance=receipt)

    # pass items to template for JS to load
    items = list(receipt.items.values("description", "quantity", "unit_price"))

    return render(request, "staging_edit.html", {
        "form": form,
        "receipt": receipt,
        "items": items,
    })

@login_required
def staging_delete(request, pk):
    if request.method == 'POST':
        receipt = Receipts.objects.get(id=pk)
        receipt.delete()
        messages.error(request, "Receipt Deleted.")
        return redirect("staging_area")

@login_required
def update_profile(request):
    if request.method == "POST":
        user = request.user
        profile = user.userprofile

        # Get posted data
        new_email = request.POST.get("email")
        new_phone = request.POST.get("phone_number")
        new_address = request.POST.get("address")
        current_password = request.POST.get("current_password")

        # Always allow address update (no password needed)
        if new_address and new_address != profile.address:
            profile.address = new_address

        # Check if email or phone number is changing
        sensitive_change = (new_email != user.email) or (new_phone != profile.phone_number)

        if sensitive_change:
            # Password required for sensitive changes
            if not current_password or not user.check_password(current_password):
                messages.error(request, "Incorrect password. Cannot update email or phone number ❌")
                return redirect("profile")

            # Update email if changed
            if new_email != user.email:
                user.email = new_email
                user.username = new_email
                profile.email_verified = False  # reset verification

            # Update phone if changed
            if new_phone != profile.phone_number:
                profile.phone_number = new_phone
                profile.phone_verified = False  # reset verification

        # Update first/last name (no password needed)
        user.first_name = request.POST.get("first_name")
        user.last_name = request.POST.get("last_name")

        # Save changes
        user.save()
        profile.save()

        messages.success(request, "Profile updated successfully ✅")
        return redirect("profile")

    return redirect("profile")
