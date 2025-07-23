from django.shortcuts import render


def home(request):
    return render(request, 'receipt_form.html')

def dashboard(request):
    return render(request, 'dashboard.html')

def login(request):
    return render(request, 'login.html')

def logout(request):
    return render(request, 'logout.html')

def signup(request):
    return render(request, 'signup.html')