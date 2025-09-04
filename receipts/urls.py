from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('create/', views.create_receipt, name='create_receipt'),
    path('my_receipts/', views.my_receipts, name='my_receipts'),
    path('about/', views.about, name='about'),
    path('test/', views.test, name='test'),
    path('download/<int:pk>/', views.receipt_pdf, name='receipt_pdf'),

]