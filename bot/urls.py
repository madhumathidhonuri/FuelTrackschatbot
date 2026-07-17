from django.urls import path
from .views import whatsapp_webhook, export_customers_excel, serve_catalog

urlpatterns = [
    path('webhook/', whatsapp_webhook, name='whatsapp_webhook'),
    path(
        'export-customers/',
        export_customers_excel,
        name='export_customers_excel'),
    path('catalog/<str:filename>', serve_catalog, name='serve_catalog'),
]
