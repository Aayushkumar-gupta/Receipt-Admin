from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("create/", views.create_receipt, name="create_receipt"),
    path("my_receipts/", views.my_receipts, name="my_receipts"),
    path("about/", views.about, name="about"),
    path("privacy/", views.privacy, name="privacy"),
    path("terms/", views.terms, name="terms"),
    path("health/", views.health, name="health"),
    path("download/<int:pk>/", views.receipt_pdf, name="receipt_pdf"),
    path("view/<int:pk>/", views.view_receipt_pdf, name="view_receipt_pdf"),
    path("staging_area/", views.staging_area, name="staging_area"),
    path("stage/<int:pk>/", views.stage, name="stage"),
    path("staging-edit/<int:pk>/", views.staging_edit, name="staging_edit"),
    path("staging-delete/<int:pk>/", views.staging_delete, name="staging_delete"),
    path("profile/", views.profile, name="profile"),
    path("profile/complete/", views.complete_profile, name="complete_profile"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("refund/<int:pk>/", views.refund, name="refund"),
]
