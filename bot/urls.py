from django.urls import path
from .views import (
    whatsapp_webhook,
    export_customers_excel,
    serve_catalog,
    run_broadcast_chunk_view,
    broadcast_cron_trigger_view
)

urlpatterns = [
    path('webhook/', whatsapp_webhook, name='whatsapp_webhook'),
    path(
        'export-customers/',
        export_customers_excel,
        name='export_customers_excel'),
    path('catalog/<str:filename>', serve_catalog, name='serve_catalog'),
    path('broadcast/chunk/<int:task_id>/', run_broadcast_chunk_view, name='run_broadcast_chunk_view'),
    path('broadcast-cron/', broadcast_cron_trigger_view, name='broadcast_cron_trigger_view'),
]

