from django.shortcuts import render
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from .models import UserProfile
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from .models import UserProfile
from .utils import send_verification_email, send_otp_sms
import random
import logging
logger = logging.getLogger(__name__)

def sign_up(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone_number = request.POST.get('phonenumber')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        # Basic validations
        if User.objects.filter(email=email).exists():
            messages.error(request, "User already exists.")
            return render(request, 'sign_up.html')
        elif password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'sign_up.html')
        elif not first_name or not last_name:
            messages.error(request, "First name and last name are required.")
            return render(request, 'sign_up.html')

        # Create inactive user (cannot login until email verified)
        user = User.objects.create_user(
            username=email,
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password,
            is_active=True,
        )

        # Create profile with email_verified and phone_verified set to False
        profile = UserProfile.objects.create(
            user=user,
            phone_number=phone_number,
            email_verified=False,
            phone_verified=False
        )

        # Step 1: Generate and send phone OTP
        otp = random.randint(100000, 999999)  # 6-digit OTP
        request.session['phone_otp'] = otp
        request.session['phone_user_id'] = user.id
        send_otp_sms(phone_number, otp)  # send OTP via SMS

        # Step 2: Send email verification
        send_verification_email(user, request)

        # Notify user to verify email and phone
        messages.success(request, "Account created! Please complete Email and Phone Verification.")
        return redirect('verify_account')  # page where user enters OTP

    return render(request, 'sign_up.html')

@csrf_exempt
def user_login(request):  
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            logger.info(f"LOGIN SUCCESS for {username}")
            if user.is_active:
                auth_login(request, user)
                return redirect('home')
            else:
                messages.error(request, "Account not verified. Please verify your email and phone.")
        else:
            logger.warning(f"LOGIN FAIL for {username} with password {password}")
            messages.error(request, "Invalid username or password")

        return redirect('login')

    return render(request, 'login.html')


def user_logout(request):
    auth_logout(request) 
    return redirect('login')

def forgot_password(request):
    return render(request, 'forgot_password.html')

def verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
        profile = UserProfile.objects.get(user=user)
    except:
        user = profile = None

    if user and default_token_generator.check_token(user, token):
        profile.email_verified = True
        profile.save()
        if request.user.is_authenticated and request.user.id == user.id:
            messages.success(request, "Email Verified!")
            return redirect('profile')
        else:
            messages.success(request, "Email verified! You'r all set.")
            return redirect('login')
    else:
        messages.error(request, "Invalid or expired verification link.")
        return redirect('sign_up')
    
def verify_account(request):
    if request.method == 'POST':
        entered_otp = request.POST.get('otp')
        user_id = request.session.get('phone_user_id')
        real_otp = request.session.get('phone_otp')

        if str(entered_otp) == str(real_otp):
            user = User.objects.get(id=user_id)
            profile = UserProfile.objects.get(user=user)
            profile.phone_verified = True
            profile.save()

            # Activate account if email is verified
            if profile.email_verified:
                user.is_active = True
                user.save()

            if request.user.is_authenticated and request.user.id == user.id:
                messages.success(request, "Phone Number Verified!")
                return redirect('profile')
            else:
                messages.success(request, "Phone verified! Verify your Email now.")
                return redirect('login')
        else:
            messages.error(request, "Incorrect OTP. Try again.")
            return redirect('profile')

    return render(request, 'verify_account.html')

@login_required
def resend_verification_email(request):
    if request.method == "POST":
        user = request.user
        profile = UserProfile.objects.get(user=user)

        if profile.email_verified:
            messages.info(request, "Your email is already verified.")
        else:
            # Send a new verification email
            send_verification_email(user, request)
            messages.success(request, "Verification Emai sent! Check you email.")
        return redirect('profile')
    
@login_required
def resend_phone_otp(request):
    if request.method == "POST":
        user = request.user
        profile = UserProfile.objects.get(user=user)

        # Generate OTP
        otp = random.randint(100000, 999999)
        request.session['phone_otp'] = otp
        request.session['phone_user_id'] = user.id

        # Send OTP to user's phone
        messages.success(request, "OTP sent! Check your Phone.")
        send_otp_sms(profile.phone_number, otp)
        
        return redirect('profile')