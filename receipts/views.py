from django.shortcuts import render, redirect
from .models import Receipts
from django.shortcuts import get_object_or_404
from django.template.loader import get_template
from django.http import HttpResponse
from xhtml2pdf import pisa
from .models import Receipts
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa

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

def receipt_detail(request):
    return render(request, 'my_receipts.html')

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
        Receipts.objects.create(
            user_id=request.user,
            seller_name=request.POST.get('seller_name'),
            seller_address=request.POST.get('seller_address'),
            seller_phone_number=request.POST.get('seller_phone_number'),
            seller_email=request.POST.get('seller_email'),

            buyer_name=request.POST.get('buyer_name'),
            buyer_address=request.POST.get('buyer_address'),
            buyer_phone_number=request.POST.get('buyer_phone_number'),

            item_description=request.POST.get('item_description'),
            item_quantity=request.POST.get('item_quantity'),
            unit_price=request.POST.get('unit_price'),
            line_price=request.POST.get('line_price'),

            sub_total=request.POST.get('sub_total'),
            tax_rate=request.POST.get('tax_rate'),
            total_amount=request.POST.get('total_amount'),
        )
        return redirect('my_receipts')  # Redirect to receipt list page after creation

    return render(request, 'receipt_form.html')

