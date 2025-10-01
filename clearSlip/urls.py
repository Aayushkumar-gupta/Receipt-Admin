"""
URL configuration for clearSlip project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from accounts import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('receipts.urls')),
    path('accounts/', include('accounts.urls')),
    path("password_reset/", 
         auth_views.PasswordResetView.as_view(template_name="password_reset.html"), 
         name="password_reset"),

    path("password_reset/done/", 
         auth_views.PasswordResetDoneView.as_view(template_name="password_reset_done.html"), 
         name="password_reset_done"),

    path("reset/<uidb64>/<token>/", 
         auth_views.PasswordResetConfirmView.as_view(template_name="password_reset_confirm.html"), 
         name="password_reset_confirm"),

    path("reset/done/", 
         auth_views.PasswordResetCompleteView.as_view(template_name="password_reset_complete.html"), 
         name="password_reset_complete"),

    path('sign-up/', views.sign_up, name='sign_up'),
    path('verify-email/<uidb64>/<token>/', views.verify_email, name='verify_email'),
    path('verify-account/', views.verify_account, name='verify_account')
]
