from django.shortcuts import render, redirect
from .models import Receipts


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


def create_receipt(request):
    if request.method == 'POST':
        Receipts.objects.create(
            buyer_name=request.POST.get('buyer_name'),
            buyer_address=request.POST.get('buyer_address'),
            buyer_phone_number=request.POST.get('buyer_phone_number'),
            item_description=request.POST.get('item_description'),
            amount=request.POST.get('amount'),
            # seller fields not yet collected, so we'll skip them for now
        )
        return render(request, 'receipt_form.html')
  # Or render a template with the receipt data

    return render(request, 'receipt_form.html')
