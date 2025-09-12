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
from xhtml2pdf import pisa
import json
from decimal import Decimal


def home(request):
    return render(request, 'home.html')

@login_required
def my_receipts(request):
    receipts = Receipts.objects.filter(user_id=request.user).order_by('-date')
    return render(request, 'my_receipts.html', {'receipts': receipts})

def about(request):
    return render(request, 'about.html')

def test(request):
    return render(request, 'test.html')

from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from .models import Receipts

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

        return redirect('my_receipts')

    return render(request, 'receipt_form.html')