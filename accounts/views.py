from django.shortcuts import render
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import authenticate, login as auth_login
from django.views.decorators.csrf import csrf_exempt


def sign_up(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exits.")

        else:
            User.objects.create_user(username=username, password=password)
            messages.success(request, "Account Created Successfully.")
            return redirect('login')
    return render(request, 'sign_up.html')

@csrf_exempt
def user_login(request):  # ✅ Renamed to avoid conflict
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            auth_login(request, user)
            return redirect('home')  # Replace with your actual redirect URL name
        else:
            messages.error(request, "Invalid username or password")
            return redirect('login')  # Replace with your login URL name

    return render(request, 'login.html') 


def user_logout(request):
    auth_logout(request) 
    return redirect('login')
