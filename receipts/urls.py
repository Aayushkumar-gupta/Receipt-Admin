from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('create/', views.create_receipt, name='create_receipt'),
    path('my_receipts/', views.my_receipts, name='my_receipts'),
    path('about/', views.about, name='about'),
    path('test/', views.test, name='test')

]