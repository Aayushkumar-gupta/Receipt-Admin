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


def home(request):
    return render(request, 'home.html')

@login_required
def my_receipts(request):
    receipts = Receipts.objects.filter(is_staged=True, user_id=request.user).order_by('-date')
    return render(request, 'my_receipts.html', {'receipts': receipts})

def about(request):
    return render(request, 'about.html')

def test(request):
    return render(request, 'test.html')

def staging_area(request):
    receipts = Receipts.objects.filter(is_staged=False, user_id=request.user).order_by('-date')
    return render(request, 'staging_area.html', {'receipts': receipts})

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


def receipt_pdf(request, pk):  # <-- add pk here
    receipt = get_object_or_404(Receipts, pk=pk)
    template = get_template("receipt_pdf.html")  # <-- correct template path
    html = template.render({"receipt": receipt})

    response = HttpResponse(content_type="application/pdf")
    response['Content-Disposition'] = f'attachment; filename="receipt_{receipt.invoice_number}.pdf"'

    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse("We had some errors while generating the PDF")
    return response


@login_required
def create_receipt(request):
    if request.method == 'POST':
        receipt = Receipts.objects.create(
            user_id=request.user,
            seller_name=request.POST.get('seller_name'),
            seller_address=request.POST.get('seller_address'),
            seller_phone_number=request.POST.get('seller_phone_number'),
            seller_email=request.POST.get('seller_email'),
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
            line_price = Decimal(item['quantity']) * Decimal(item['unit_price'])

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


def stage(request, pk):
    receipt = Receipts.objects.get(id = pk)
    receipt.is_staged = True
    receipt.save()
    return redirect('my_receipts')


def staging_edit(request, pk):
    receipt = get_object_or_404(Receipts, id=pk)

    # prevent editing confirmed receipts
    if receipt.is_staged:
        return redirect("staging_area")

    if request.method == "POST":
        form = ReceiptForm(request.POST, instance=receipt)
        if form.is_valid():
            # save receipt fields (seller + buyer + totals)
            updated_receipt = form.save()

            # handle items JSON (hidden field name = "items")
            items_json = request.POST.get("items", "[]")
            try:
                items = json.loads(items_json)
            except (ValueError, TypeError):
                items = []

            # replace existing items with new ones
            updated_receipt.items.all().delete()
            for it in items:
                desc = it.get("description", "") or ""
                qty = int(it.get("quantity") or 0)
                # ensure Decimal for unit_price to match model
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

            return redirect("staging_area")
        else:
            # optionally pass form errors to template (template can show them)
            pass
    else:
        form = ReceiptForm(instance=receipt)

    # pass items to template for JS to load
    items = list(receipt.items.values("description", "quantity", "unit_price"))

    return render(request, "staging_edit.html", {
        "form": form,
        "receipt": receipt,
        "items": items,
    })
