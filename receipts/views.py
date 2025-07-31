from django.shortcuts import render, redirect
from .models import Receipts
from io import BytesIO
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.http import HttpResponse
from .models import Receipts
from django.shortcuts import get_object_or_404



def home(request):
    return render(request, 'home.html')

def login(request):
    return render(request, 'login.html')

def logout(request):
    return render(request, 'logout.html')

def my_receipts(request):
    return render(request, 'my_receipts.html')

def about(request):
    return render(request, 'about.html')

def test(request):
    return render(request, 'test.html')

def receipt_detail(request):
    return render(request, 'my_receipts.html')

def receipt_pdf(request):
    return render(request, 'my_receipts.html')


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


def my_receipts(request):
    receipts = Receipts.objects.filter().order_by('-date')
    return render(request, 'my_receipts.html', {'receipts': receipts})



def render_to_pdf(template_src, context_dict={}):
    template = get_template(template_src)
    html = template.render(context_dict)
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
    
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')
    return None



 View PDF in browser
def receipt_pdf_view(request, receipt_id):
    receipt = get_object_or_404(Receipts, id=receipt_id, user_id=request.user)
    pdf = render_to_pdf('receipt_pdf.html', {'receipt': receipt})
    return pdf

# Download PDF
def receipt_pdf_download(request, receipt_id):
    receipt = get_object_or_404(Receipts, id=receipt_id, user_id=request.user)
    pdf = render_to_pdf('receipt_pdf.html', {'receipt': receipt})
    if pdf:
        response = HttpResponse(pdf.content, content_type='application/pdf')
        filename = f"Receipt_{receipt.invoice_number}.pdf"
        content = f'attachment; filename="{filename}"'
        response['Content-Disposition'] = content
        return response
    return HttpResponse("PDF generation failed")