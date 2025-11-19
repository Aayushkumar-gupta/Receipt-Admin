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
import threading
from django.contrib.auth.views import PasswordResetView
from django.urls import reverse_lazy
from .utils import send_password_reset_email
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.urls import reverse
from django.contrib.auth import logout
from django.http import HttpResponse



def sign_up(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone_number = request.POST.get('phonenumber')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        # Validations
        if User.objects.filter(email=email).exists():
            messages.error(request, "User already exists.")
            return render(request, 'sign_up.html')
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'sign_up.html')
        if not first_name or not last_name:
            messages.error(request, "First name and last name are required.")
            return render(request, 'sign_up.html')

        # Create user
        user = User.objects.create_user(
            username=email,
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password,
            is_active=True,  # Can login only after phone+email verification
        )

        profile = UserProfile.objects.create(
            user=user,
            phone_number=phone_number,
            email_verified=False,
            phone_verified=False
        )

        # Step 1: Phone OTP
        #otp = random.randint(100000, 999999)
        #request.session['phone_otp'] = otp
        #request.session['phone_user_id'] = user.id
        #send_otp_sms(phone_number, otp)

        # Step 2: Email verification (async)
        threading.Thread(target=send_email_async, args=(user, request)).start()

        messages.success(request, "Account created! Check you email inbox for verification.")
        return redirect('login')

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
                return redirect('dashboard')
            else:
                messages.error(request, "Account not verified. Please verify your email and phone.")
        else:
            logger.warning(f"LOGIN FAIL for {username} with password {password}")
            messages.error(request, "Invalid username or password")

        return redirect('login')

    return render(request, 'login.html')


def user_logout(request):
    auth_logout(request) 
    request.session.flush()   
    return redirect('home')

@csrf_exempt
def auto_logout(request):
    if request.user.is_authenticated:
        logout(request)
        request.session.flush()  
    return HttpResponse(status=204)

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
        messages.success(request, "Email verified successfully!")
        if request.user.is_authenticated and request.user.id == user.id:
            return redirect('profile')
        else:
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

def send_email_async(user, request):
    try:
        send_verification_email(user, request)
    except Exception as e:
        print("Failed to send verification email:", e)

@login_required
def resend_verification_email(request):
    if request.method == 'POST':
        user = request.user
        try:
            send_verification_email(user, request)  # pass user first, then request
            messages.success(request, "Verification email sent successfully!")
        except Exception as e:
            messages.error(request, f"Failed to send email: {e}")
        return redirect('profile')
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
    
class CustomPasswordResetView(PasswordResetView):
    template_name = 'password_reset.html'  # The form page
    success_url = reverse_lazy('password_reset_done')

    def form_valid(self, form):
        email = form.cleaned_data["email"]
        users = list(form.get_users(email))
        for user in users:
            # Generate UID and token
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            # Build full reset URL
            reset_url = self.request.build_absolute_uri(
                reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
            )
            # Send custom email with reset URL
            send_password_reset_email(user, reset_url)
        return redirect(self.success_url)

    