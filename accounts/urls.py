from django.urls import path
from . import views

urlpatterns = [
    path('signup/', views.sign_up, name='sign_up'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('forgot_password', views.forgot_password, name='forgot_password'),
    path('verify-email/<uidb64>/<token>/', views.verify_email, name='verify_email'),
    path("resend-verification-email/", views.resend_verification_email, name="resend_verification_email"),
    path("resend-phone-otp/", views.resend_phone_otp, name="resend_phone_otp"),
    path("verify-phone-otp/", views.verify_account, name="verify_phone_otp"),
    path('verify-email/<uidb64>/<token>/', views.verify_email, name='verify_email'),
    path('verify-account/', views.verify_account, name='verify_account'),
    path('test-email/', views.test_email, name='test_email'),
]