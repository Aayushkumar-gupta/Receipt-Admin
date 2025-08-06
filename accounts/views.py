from django.shortcuts import render
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.views.decorators.csrf import csrf_exempt
from .models import UserProfile


def sign_up(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone_number = request.POST.get('phonenumber')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if User.objects.filter(email=email).exists():
            messages.error(request, "User already exists.")
            return render(request, 'sign_up.html')  # 🔥 add this

        elif password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'sign_up.html')  # 🔥 add this

        elif not first_name or not last_name:
            messages.error(request, "First name and last name are required.")
            return render(request, 'sign_up.html')  # 🔥 extra safety

        else:
            user = User.objects.create_user(
                username=email,
                first_name=first_name,
                last_name=last_name,
                email=email,
                password=password
            )
            UserProfile.objects.create(user=user, phone_number=phone_number)

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
