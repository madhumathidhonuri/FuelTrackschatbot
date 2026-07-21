from django.contrib import admin
from django.urls import path, reverse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django import forms
from django.utils import timezone
import os
import json
import requests
import threading
import time
from .models import ChatMessage, FleetCustomer, BroadcastTask, BroadcastRecipient, AdCampaign, WhatsAppTemplate, AgentNotificationLog


@admin.register(AdCampaign)
class AdCampaignAdmin(admin.ModelAdmin):
    list_display = (
        'campaign_name',
        'ad_id',
        'headline_keywords',
        'catalog_file',
        'is_active',
        'created_at')
    list_filter = ('is_active',)
    search_fields = ('campaign_name', 'ad_id', 'headline_keywords')


@admin.register(WhatsAppTemplate)
class WhatsAppTemplateAdmin(admin.ModelAdmin):
    list_display = (
        'template_name',
        'description',
        'category',
        'has_variables',
        'has_header',
        'header_type',
        'header_image_url',
        'header_file',
        'header_media_id',
        'media_id_updated_at',
        'languages',
        'created_at'
    )
    search_fields = (
        'template_name',
        'description',
        'custom_system_prompt',
        'header_image_url',
        'header_media_id')
    list_filter = ('category', 'has_variables', 'has_header', 'header_type')
    readonly_fields = ('media_id_updated_at',)
    actions = ['upload_header_file_to_meta']

    @admin.action(description="Upload header file to Meta")
    def upload_header_file_to_meta(self, request, queryset):
        success_count = 0
        for template in queryset:
            if not template.header_file:
                self.message_user(
                    request,
                    f"Template '{template.template_name}' has no header file configured.",
                    level=messages.WARNING
                )
                continue

            # Check if file exists on disk
            try:
                exists = os.path.exists(template.header_file.path)
            except Exception:
                exists = False

            if not exists:
                self.message_user(
                    request,
                    f"Template '{template.template_name}' header file does not physically exist on the server's disk. "
                    "Please re-upload the image file manually via the admin first.",
                    level=messages.ERROR
                )
                continue

            try:
                from bot.utils import upload_media_to_meta
                media_id = upload_media_to_meta(template.header_file)
                if media_id:
                    template.header_media_id = media_id
                    template.media_id_updated_at = timezone.now()
                    template.save()
                    success_count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Failed to upload '{template.template_name}' to Meta: {e}",
                    level=messages.ERROR
                )

        if success_count > 0:
            self.message_user(
                request,
                f"Successfully uploaded {success_count} templates' header media to Meta.")


class ExcelUploadForm(forms.Form):
    excel_file = forms.FileField(label="Select Excel or CSV File")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('phone_number_link', 'role', 'content', 'timestamp')
    list_filter = ('role',)
    search_fields = ('phone_number', 'content')
    list_display_links = ('timestamp',)
    ordering = ('-timestamp',)

    def phone_number_link(self, obj):
        from django.utils.html import format_html
        url = f"/admin/bot/fleetcustomer/live-chat/?phone={obj.phone_number}"
        return format_html('<a href="{}">{}</a>', url, obj.phone_number)
    phone_number_link.short_description = "Phone Number"


@admin.register(AgentNotificationLog)
class AgentNotificationLogAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'phone_number_link',
        'customer_name',
        'message_content_excerpt',
        'is_template_reply',
        'template_name',
        'notification_sent')
    list_filter = (
        'is_template_reply',
        'template_name',
        'notification_sent',
        'created_at')
    search_fields = ('phone_number', 'message_content', 'template_name')
    readonly_fields = ('created_at',)
    change_list_template = "admin/agentnotificationlog_changelist.html"

    def customer_name(self, obj):
        if obj.customer:
            return obj.customer.owner_name
        return "Unknown"
    customer_name.short_description = "Customer Name"

    def message_content_excerpt(self, obj):
        return obj.message_content[:75] + \
            ("..." if len(obj.message_content) > 75 else "")
    message_content_excerpt.short_description = "Message"

    def phone_number_link(self, obj):
        from django.utils.html import format_html
        url = f"/admin/bot/fleetcustomer/live-chat/?phone={obj.phone_number}"
        return format_html('<a href="{}">{}</a>', url, obj.phone_number)
    phone_number_link.short_description = "Phone Number"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'export-excel/',
                self.admin_site.admin_view(
                    self.export_excel),
                name='bot_agentnotificationlog_export_excel'),
        ]
        return custom_urls + urls

    def export_excel(self, request):
        if request.method == "POST":
            import pandas as pd
            from django.http import HttpResponse
            import datetime
            from django.utils import timezone

            from_date = request.POST.get('from_date')
            from_time = request.POST.get('from_time')
            to_date = request.POST.get('to_date')
            to_time = request.POST.get('to_time')

            qs = self.get_queryset(request)

            if from_date:
                if from_time:
                    try:
                        start_dt = timezone.make_aware(
                            datetime.datetime.strptime(
                                f"{from_date} {from_time}", "%Y-%m-%d %H:%M"))
                    except ValueError:
                        start_dt = timezone.make_aware(
                            datetime.datetime.strptime(
                                f"{from_date} {from_time}",
                                "%Y-%m-%d %H:%M:%S"))
                else:
                    start_dt = timezone.make_aware(
                        datetime.datetime.strptime(
                            f"{from_date} 00:00:00",
                            "%Y-%m-%d %H:%M:%S"))
                qs = qs.filter(created_at__gte=start_dt)

            if to_date:
                if to_time:
                    try:
                        end_dt = timezone.make_aware(
                            datetime.datetime.strptime(
                                f"{to_date} {to_time}", "%Y-%m-%d %H:%M"))
                    except ValueError:
                        end_dt = timezone.make_aware(
                            datetime.datetime.strptime(
                                f"{to_date} {to_time}",
                                "%Y-%m-%d %H:%M:%S"))
                else:
                    end_dt = timezone.make_aware(
                        datetime.datetime.strptime(
                            f"{to_date} 23:59:59",
                            "%Y-%m-%d %H:%M:%S"))
                qs = qs.filter(created_at__lte=end_dt)

            data = list(
                qs.values(
                    'customer__owner_name',
                    'phone_number',
                    'message_content',
                    'created_at'))
            df = pd.DataFrame(data)

            if not df.empty:
                if 'created_at' in df.columns:
                    df['created_at'] = df['created_at'].dt.tz_localize(None)
                df.rename(columns={
                    'customer__owner_name': 'Customer Name',
                    'phone_number': 'Phone Number',
                    'message_content': 'Message',
                    'created_at': 'Time'
                }, inplace=True)

            response = HttpResponse(
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="agent_notification_logs_{
                timezone.now().strftime("%Y%m%d%H%M%S")}.xlsx"'

            with pd.ExcelWriter(response, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Logs')

            return response

        context = {
            **self.admin_site.each_context(request),
            'title': 'Export Agent Notification Logs to Excel',
        }
        return render(
            request, "admin/agentnotificationlog_export.html", context)


def run_broadcast_thread(task_id, file_path, template_name, language_code):
    from django.db import connection
    connection.close()

    try:
        import concurrent.futures
        import threading as _threading
        from bot.models import BroadcastTask, FleetCustomer, WhatsAppTemplate
        from bot.utils import parse_excel_or_csv
        from bot.broadcast import send_whatsapp_template

        task = BroadcastTask.objects.get(id=task_id)
        task.status = 'running'
        task.save()

        customers_data = parse_excel_or_csv(file_path)

        # ── Bulk upsert all records in batches of 500 (replaces 50k individual update_or_create calls) ──
        to_create = [
            FleetCustomer(
                phone_number=cust['phone_number'],
                owner_name=cust.get('owner_name') or '',
                truck_number=cust.get('truck_number') or '',
                is_active=cust.get('is_active', True)
            )
            for cust in customers_data
            if cust.get('phone_number')
        ]
        # Deduplicate before bulk insert (avoid unique constraint violations)
        seen = set()
        unique_to_create = []
        for obj in to_create:
            if obj.phone_number not in seen:
                seen.add(obj.phone_number)
                unique_to_create.append(obj)

        try:
            FleetCustomer.objects.bulk_create(
                unique_to_create,
                update_conflicts=True,
                update_fields=['owner_name', 'truck_number', 'is_active'],
                unique_fields=['phone_number'],
                batch_size=500
            )
        except TypeError:
            # Django < 4.1 fallback: bulk_create without update_conflicts
            for cust in customers_data:
                FleetCustomer.objects.update_or_create(
                    phone_number=cust['phone_number'],
                    defaults={
                        'owner_name': cust.get('owner_name') or '',
                        'truck_number': cust.get('truck_number') or '',
                        'is_active': cust.get('is_active', True)
                    }
                )

        # Collect all active phone numbers from file
        target_phone_numbers = [c['phone_number'] for c in customers_data if c.get('is_active', True)]

        # Load as plain dicts — faster and safe to share across threads
        active_customers = list(
            FleetCustomer.objects.filter(
                phone_number__in=target_phone_numbers, is_active=True
            ).values('phone_number', 'owner_name', 'truck_number')
        )
        total_count = len(active_customers)

        task.total_records = total_count
        task.save()

        # ── Pre-fetch template config ONCE (eliminates 10k+ DB queries) ──────
        template_config = None
        try:
            template_obj = WhatsAppTemplate.objects.filter(
                template_name=template_name).first()
            if template_obj:
                site_url = os.getenv(
                    "SITE_URL", "https://whatsapp-ai-bot-dqot.onrender.com")
                if site_url.endswith("/"):
                    site_url = site_url[:-1]
                header_file_url = None
                if template_obj.header_file:
                    header_file_url = f"{site_url}{template_obj.header_file.url}"
                template_config = {
                    'has_variables': template_obj.has_variables,
                    'var_count': getattr(template_obj, 'var_count', 0),
                    'has_header': template_obj.has_header,
                    'header_type': template_obj.header_type,
                    'header_image_url': template_obj.header_image_url,
                    'header_media_id': template_obj.header_media_id,
                    'header_file_url': header_file_url,
                    'category': (
                        template_obj.category.lower()
                        if template_obj.category else 'utility'
                    ),
                }
        except Exception:
            pass

        success_count = 0
        failed_count = 0
        failed_details = []
        processed = 0
        lock = _threading.Lock()

        BATCH_SIZE = 25    # flush progress & check status every 25 completions (fast & 0 DB lag)
        MAX_WORKERS = 12   # parallel HTTP workers (balanced for server resource & rate limits)

        chat_history_batch = []
        chat_msg_content = f"[System Sent Broadcast: {template_name} - Broadcast template: {template_name}]"

        def send_one(cust):
            """Send a single message and return result — runs in worker thread."""
            try:
                success, error_reason = send_whatsapp_template(
                    to_phone=cust['phone_number'],
                    template_name=template_name,
                    customer_name=cust['owner_name'],
                    vehicle_number=cust['truck_number'],
                    language_code=language_code,
                    template_config=template_config,  # pre-fetched — no DB hit
                    record_chat_message=False         # skip DB write inside thread
                )
                return cust, success, error_reason
            finally:
                connection.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(send_one, c): c for c in active_customers}

            for future in concurrent.futures.as_completed(futures):
                try:
                    cust, success, error_reason = future.result()
                except Exception as exc:
                    cust = futures[future]
                    success, error_reason = False, str(exc)

                with lock:
                    processed += 1
                    if success:
                        success_count += 1
                        chat_history_batch.append(
                            ChatMessage(
                                phone_number=cust['phone_number'],
                                role='assistant',
                                content=chat_msg_content
                            )
                        )
                    else:
                        failed_count += 1
                        failed_details.append({
                            'phone_number': cust['phone_number'],
                            'name': cust['owner_name'],
                            'reason': error_reason
                        })

                    # ── Batch DB update & Status Check every BATCH_SIZE records (25) ──
                    if processed % BATCH_SIZE == 0 or processed == total_count:
                        curr_status = BroadcastTask.objects.filter(id=task_id).values_list('status', flat=True).first()

                        while curr_status == 'paused':
                            import time
                            time.sleep(1)
                            curr_status = BroadcastTask.objects.filter(id=task_id).values_list('status', flat=True).first()

                        if curr_status in ['stopped', 'failed', 'cancelled']:
                            print(f"[BROADCAST] Task #{task_id} status is '{curr_status}'. Stopping worker thread.")
                            executor.shutdown(wait=False, cancel_futures=True)
                            break

                        # Cap failed_details to last 500 entries to prevent unbounded JSON growth
                        failed_details_trimmed = failed_details[-500:] if len(failed_details) > 500 else failed_details
                        BroadcastTask.objects.filter(id=task_id).update(
                            processed_records=processed,
                            success_count=success_count,
                            failed_count=failed_count,
                            failed_details=json.dumps(failed_details_trimmed),
                            updated_at=timezone.now()
                        )

                        if chat_history_batch:
                            try:
                                ChatMessage.objects.bulk_create(
                                    chat_history_batch, ignore_conflicts=True)
                            except Exception:
                                pass
                            chat_history_batch.clear()

        # Mark completed only if not stopped/cancelled by user
        final_status = BroadcastTask.objects.filter(id=task_id).values_list('status', flat=True).first()
        if final_status not in ['stopped', 'failed', 'cancelled', 'paused']:
            BroadcastTask.objects.filter(id=task_id).update(status='completed', updated_at=timezone.now())

        if failed_details:
            try:
                failed_broadcast_txt_path = os.path.join(
                    os.path.dirname(file_path), "failed_broadcast.txt")
                with open(failed_broadcast_txt_path, "w") as f:
                    for fail in failed_details:
                        f.write(
                            f"{fail['phone_number']} | {fail['name']} | {fail['reason']}\n")
            except Exception:
                pass

    except Exception as e:
        try:
            BroadcastTask.objects.filter(id=task_id).update(
                status='failed',
                failed_details=json.dumps(
                    [{'phone_number': 'N/A', 'name': 'N/A', 'reason': str(e)}]),
                updated_at=timezone.now()
            )
        except Exception:
            pass
    finally:
        connection.close()



def sync_whatsapp_templates_from_meta():
    """
    Fetches templates from Meta Graph API using WHATSAPP_BUSINESS_ACCOUNT_ID and WHATSAPP_TOKEN.
    Synchronizes them into the local database and returns a dict mapping
    template name to a list of approved language codes, e.g.
    {'gps_tracking_device': ['en_US', 'te'], ...}

    If WABA ID or Token is missing, or the call fails, returns None.
    """
    import os
    import requests
    from bot.models import WhatsAppTemplate

    waba_id = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID")
    token = os.getenv("WHATSAPP_TOKEN")
    if not waba_id or not token:
        return None

    url = f"https://graph.facebook.com/v19.0/{waba_id}/message_templates"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    params = {
        "limit": 1000
    }
    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)
        if response.status_code == 200:
            templates_data = response.json().get("data", [])

            # Group by template name
            grouped = {}
            for item in templates_data:
                if item.get("status") != "APPROVED":
                    continue
                name = item.get("name")
                lang = item.get("language")
                if not name or not lang:
                    continue

                # Check if it has variables and headers
                has_vars = False
                var_count = 0
                has_header = False
                header_type = 'none'
                for comp in item.get("components", []):
                    comp_type = comp.get("type")
                    if comp_type == "BODY":
                        text = comp.get("text", "")
                        import re
                        matches = re.findall(r'\{\{(\d+)\}\}', text)
                        if matches:
                            has_vars = True
                            var_count = max(int(m) for m in matches)
                    elif comp_type == "HEADER":
                        has_header = True
                        header_type = comp.get("format", "TEXT").lower()

                if name not in grouped:
                    grouped[name] = {
                        "languages": set(),
                        "has_variables": False,
                        "var_count": 0,
                        "has_header": False,
                        "header_type": "none",
                        "category": item.get("category", "")
                    }
                grouped[name]["languages"].add(lang)
                if has_vars:
                    grouped[name]["has_variables"] = True
                    grouped[name]["var_count"] = max(grouped[name]["var_count"], var_count)
                if has_header:
                    grouped[name]["has_header"] = True
                    grouped[name]["header_type"] = header_type

            # Now update the database
            for name, info in grouped.items():
                langs_str = ",".join(sorted(list(info["languages"])))
                desc = f"Sync'd from Meta: {info['category']}"
                category_lower = info['category'].lower(
                ) if info['category'] else 'marketing'
                if category_lower not in (
                        'utility', 'marketing', 'authentication'):
                    category_lower = 'marketing'
                WhatsAppTemplate.objects.update_or_create(
                    template_name=name,
                    defaults={
                        "description": desc,
                        "category": category_lower,
                        "has_variables": info["has_variables"],
                        "var_count": info["var_count"],
                        "languages": langs_str,
                        "has_header": info["has_header"],
                        "header_type": info["header_type"]
                    }
                )
            return {name: sorted(list(info["languages"]))
                    for name, info in grouped.items()}
    except Exception as e:
        print(f"Error syncing templates from Meta API: {e}")
    return None


@admin.register(FleetCustomer)
class FleetCustomerAdmin(admin.ModelAdmin):
    list_display = (
        'owner_name',
        'phone_number_link',
        'truck_number',
        'is_active',
        'is_bot_paused',
        'referred_by',
        'created_at')
    list_filter = ('is_active', 'is_bot_paused', 'referred_by')
    search_fields = ('owner_name', 'phone_number', 'truck_number')

    def phone_number_link(self, obj):
        from django.utils.html import format_html
        url = f"/admin/bot/fleetcustomer/live-chat/?phone={obj.phone_number}"
        return format_html('<a href="{}">{}</a>', url, obj.phone_number)
    phone_number_link.short_description = "Phone Number"

    change_list_template = "admin/fleetcustomer_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'upload-excel/',
                self.admin_site.admin_view(
                    self.upload_excel),
                name='bot_fleetcustomer_upload_excel'),
            path(
                'broadcast/',
                self.admin_site.admin_view(
                    self.broadcast),
                name='bot_fleetcustomer_broadcast'),
            path(
                'broadcast-status/<int:task_id>/',
                self.admin_site.admin_view(
                    self.broadcast_status),
                name='bot_fleetcustomer_broadcast_status'),
            path(
                'broadcast-pause/<int:task_id>/',
                self.admin_site.admin_view(
                    self.pause_broadcast),
                name='bot_fleetcustomer_broadcast_pause'),
            path(
                'broadcast-resume/<int:task_id>/',
                self.admin_site.admin_view(
                    self.resume_broadcast),
                name='bot_fleetcustomer_broadcast_resume'),
            path(
                'broadcast-cancel/<int:task_id>/',
                self.admin_site.admin_view(
                    self.cancel_broadcast),
                name='bot_fleetcustomer_broadcast_cancel'),
            path(
                'download-broadcast-logs/',
                self.admin_site.admin_view(
                    self.download_broadcast_logs),
                name='bot_fleetcustomer_download_broadcast_logs'),
            path(
                'live-chat/',
                self.admin_site.admin_view(
                    self.live_chat_view),
                name='bot_fleetcustomer_live_chat'),
            path(
                'live-chat/api/list/',
                self.admin_site.admin_view(
                    self.api_chat_list),
                name='bot_fleetcustomer_chat_list'),
            path(
                'live-chat/api/messages/<str:phone_number>/',
                self.admin_site.admin_view(
                    self.api_chat_history),
                name='bot_fleetcustomer_chat_history'),
            path(
                'live-chat/api/send/<str:phone_number>/',
                self.admin_site.admin_view(
                    self.api_chat_send),
                name='bot_fleetcustomer_chat_send'),
            path(
                'live-chat/api/send-media/<str:phone_number>/',
                self.admin_site.admin_view(
                    self.api_chat_send_media),
                name='bot_fleetcustomer_chat_send_media'),
            path(
                'live-chat/api/toggle-pause/<str:phone_number>/',
                self.admin_site.admin_view(
                    self.api_chat_toggle_pause),
                name='bot_fleetcustomer_chat_toggle_pause'),
            path(
                'live-chat/api/customer/<str:phone_number>/',
                self.admin_site.admin_view(
                    self.api_chat_customer),
                name='bot_fleetcustomer_chat_customer'),
        ]
        return custom_urls + urls

    def upload_excel(self, request):
        if request.method == "POST":
            form = ExcelUploadForm(request.POST, request.FILES)
            if form.is_valid():
                file = request.FILES['excel_file']
                from django.conf import settings
                media_dir = os.path.join(settings.BASE_DIR, 'media')
                os.makedirs(media_dir, exist_ok=True)

                # Determine extension
                ext = os.path.splitext(file.name)[1].lower()
                if ext not in ('.xlsx', '.xls', '.csv'):
                    messages.error(
                        request,
                        "Invalid file format. Please upload an Excel (.xlsx, .xls) or CSV (.csv) file.")
                    return redirect("..")

                target_path = os.path.join(media_dir, f"broadcast_list{ext}")

                # Clean up existing broadcast_list files to prevent confusion
                for existing_ext in ('.xlsx', '.xls', '.csv'):
                    p = os.path.join(
                        media_dir, f"broadcast_list{existing_ext}")
                    if os.path.exists(p):
                        try:
                            os.remove(p)
                        except Exception:
                            pass

                with open(target_path, 'wb+') as destination:
                    for chunk in file.chunks():
                        destination.write(chunk)

                # Import customers from the uploaded file
                try:
                    from bot.utils import parse_excel_or_csv
                    customers_data = parse_excel_or_csv(target_path)

                    created_count = 0
                    updated_count = 0
                    for cust in customers_data:
                        customer, created = FleetCustomer.objects.update_or_create(
                            phone_number=cust['phone_number'],
                            defaults={
                                'owner_name': cust['owner_name'],
                                'truck_number': cust['truck_number'],
                                'is_active': cust['is_active']
                            }
                        )
                        if created:
                            created_count += 1
                        else:
                            updated_count += 1

                    messages.success(
                        request,
                        f"Successfully uploaded file. Imported {created_count} new customers and updated {updated_count} existing customers. "
                        f"Saved file to {target_path}. You can now run the broadcast script."
                    )
                except Exception as e:
                    messages.error(request, f"Error processing file: {e}")

                return redirect("..")
        else:
            form = ExcelUploadForm()

        context = {
            **self.admin_site.each_context(request),
            'form': form,
            'title': 'Upload Customers Excel/CSV'
        }
        return render(request, "admin/upload_excel.html", context)

    def broadcast(self, request):
        if request.method == "POST":
            is_ajax = request.headers.get(
                'x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax')

            excel_file = request.FILES.get('excel_file')
            template_name = request.POST.get('template_name')
            custom_template_name = request.POST.get('custom_template_name')
            language_code = request.POST.get('language_code', 'en_US')

            if template_name == 'custom' and custom_template_name:
                template_name = custom_template_name.strip()

            if not excel_file or not template_name:
                if is_ajax:
                    return JsonResponse(
                        {"success": False, "error": "Excel file and template name are required."})
                messages.error(
                    request, "Excel file and template name are required.")
                return redirect(".")

            ext = os.path.splitext(excel_file.name)[1].lower()
            if ext not in ('.xlsx', '.xls', '.csv'):
                if is_ajax:
                    return JsonResponse(
                        {"success": False, "error": "Invalid file format. Upload Excel or CSV."})
                messages.error(
                    request,
                    "Invalid file format. Please upload an Excel (.xlsx, .xls) or CSV (.csv) file.")
                return redirect(".")

            from django.conf import settings
            media_dir = os.path.join(settings.BASE_DIR, 'media')
            os.makedirs(media_dir, exist_ok=True)

            target_path = os.path.join(media_dir, f"broadcast_list{ext}")

            for existing_ext in ('.xlsx', '.xls', '.csv'):
                p = os.path.join(media_dir, f"broadcast_list{existing_ext}")
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass

            with open(target_path, 'wb+') as destination:
                for chunk in excel_file.chunks():
                    destination.write(chunk)

            task = BroadcastTask.objects.create(
                template_name=template_name,
                language_code=language_code,
                excel_file_name=excel_file.name,
                status='pending'
            )

            thread = threading.Thread(
                target=run_broadcast_thread,
                args=(task.id, target_path, template_name, language_code)
            )
            thread.daemon = False  # Must be False — daemon threads are killed when the HTTP worker thread ends (e.g. navigating away from the broadcast page)
            thread.start()

            if is_ajax:
                return JsonResponse({"success": True, "task_id": task.id})

            messages.success(
                request, f"Broadcast task #{
                    task.id} started successfully!")
            return redirect(".")
        # Ensure default templates are populated if missing (with correct
        # languages)
        default_templates = [
            ("hello_world", "Default Greetings", False,
             "en_US", False, "none", "", "utility"),
            ("gps_tracking_device", "GPS Tracking Devices promo",
             False, "en_US", False, "none", "", "marketing"),
            ("ais_140_gps_mining_device", "AIS 140 mining tracker template",
             False, "en_US,te", True, "image", "", "marketing"),
            ("fuel_alert", "Fuel theft/drop alerts", True,
             "en_US,te", False, "none", "", "utility"),
            ("fleet_update", "Fleet status summary updates",
             True, "en_US,te", False, "none", "", "utility"),
        ]
        for name, desc, has_vars, langs, has_header, header_type, header_img, category in default_templates:
            WhatsAppTemplate.objects.get_or_create(
                template_name=name,
                defaults={
                    "description": desc,
                    "has_variables": has_vars,
                    "languages": langs,
                    "has_header": has_header,
                    "header_type": header_type,
                    "header_image_url": header_img,
                    "category": category
                }
            )

        # Attempt to sync from Meta Graph API
        sync_whatsapp_templates_from_meta()

        templates = WhatsAppTemplate.objects.all().order_by('template_name')

        # Build mapping of template name to list of language codes
        templates_mapping = {}
        for t in templates:
            langs = [l.strip() for l in t.languages.split(",") if l.strip()]
            templates_mapping[t.template_name] = langs

        # Clean up any stale running task that hasn't updated in >300 seconds (5 mins) (e.g. killed by server restart)
        from django.utils import timezone
        from datetime import timedelta
        # 30 minutes: long enough for a 50k-number broadcast (was 5 min — killed tasks too early)
        stale_threshold = timezone.now() - timedelta(seconds=1800)
        BroadcastTask.objects.filter(
            status='running', updated_at__lt=stale_threshold
        ).update(status='failed')

        active_task = BroadcastTask.objects.filter(
            status__in=['pending', 'running']).order_by('-created_at').first()
        active_task_id = active_task.id if active_task else None

        context = {
            **self.admin_site.each_context(request),
            'title': 'WhatsApp Broadcast Panel',
            'templates': templates,
            'templates_mapping_json': json.dumps(templates_mapping),
            'active_task_id': active_task_id,
        }
        return render(request, "admin/broadcast.html", context)

    def broadcast_status(self, request, task_id):
        try:
            task = BroadcastTask.objects.get(id=task_id)
            failed_list = []
            if task.failed_details:
                try:
                    failed_list = json.loads(task.failed_details)
                except Exception:
                    pass
            return JsonResponse({
                "id": task.id,
                "status": task.status,
                "template_name": task.template_name,
                "language_code": task.language_code,
                "total_records": task.total_records,
                "processed_records": task.processed_records,
                "success_count": task.success_count,
                "failed_count": task.failed_count,
                "failed_details": failed_list,
            })
        except BroadcastTask.DoesNotExist:
            return JsonResponse({"error": "Task not found"}, status=404)

    def pause_broadcast(self, request, task_id):
        try:
            task = BroadcastTask.objects.get(id=task_id)
            task.status = 'paused'
            task.save()
            return JsonResponse({"success": True, "status": "paused"})
        except BroadcastTask.DoesNotExist:
            return JsonResponse({"error": "Task not found"}, status=404)

    def resume_broadcast(self, request, task_id):
        try:
            task = BroadcastTask.objects.get(id=task_id)
            task.status = 'running'
            task.save()
            return JsonResponse({"success": True, "status": "running"})
        except BroadcastTask.DoesNotExist:
            return JsonResponse({"error": "Task not found"}, status=404)

    def cancel_broadcast(self, request, task_id):
        try:
            task = BroadcastTask.objects.get(id=task_id)
            task.status = 'cancelled'
            task.save()
            return JsonResponse({"success": True, "status": "cancelled"})
        except BroadcastTask.DoesNotExist:
            return JsonResponse({"error": "Task not found"}, status=404)

    def download_broadcast_logs(self, request):
        import pandas as pd
        from django.http import HttpResponse
        import datetime
        from django.utils import timezone

        date_str = request.GET.get('date')
        if not date_str:
            messages.error(request, "Please select a date.")
            return redirect('admin:bot_fleetcustomer_broadcast')

        try:
            target_date = datetime.datetime.strptime(
                date_str, "%Y-%m-%d").date()
        except ValueError:
            messages.error(request, "Invalid date format.")
            return redirect('admin:bot_fleetcustomer_broadcast')

        start_datetime = timezone.make_aware(
            datetime.datetime.combine(
                target_date, datetime.time.min))
        end_datetime = timezone.make_aware(
            datetime.datetime.combine(
                target_date, datetime.time.max))

        qs = ChatMessage.objects.filter(
            role='assistant',
            content__startswith='[System Sent Broadcast:',
            timestamp__range=(start_datetime, end_datetime)
        ).order_by('timestamp')

        data = []
        phone_numbers = qs.values_list('phone_number', flat=True).distinct()
        customers = FleetCustomer.objects.filter(
            phone_number__in=phone_numbers)
        customer_map = {c.phone_number: c.owner_name for c in customers}

        for msg in qs:
            template_name = "Unknown"
            if " - " in msg.content:
                parts = msg.content.replace(
                    "[System Sent Broadcast:", "").replace(
                    "]", "").strip().split(" - ")
                if parts:
                    template_name = parts[0].strip()
            else:
                template_name = msg.content.replace(
                    "[System Sent Broadcast:", "").replace("]", "").strip()

            data.append({
                'Phone Number': msg.phone_number,
                'Customer Name': customer_map.get(msg.phone_number, 'Unknown'),
                'Template': template_name,
                'Time': msg.timestamp.astimezone().replace(tzinfo=None)
            })

        df = pd.DataFrame(data)

        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="broadcast_logs_{date_str}.xlsx"'

        if not df.empty:
            with pd.ExcelWriter(response, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Sent Templates')
        else:
            with pd.ExcelWriter(response, engine='openpyxl') as writer:
                df = pd.DataFrame(
                    columns=[
                        'Phone Number',
                        'Customer Name',
                        'Template',
                        'Time'])
                df.to_excel(writer, index=False, sheet_name='Sent Templates')

        return response

    def live_chat_view(self, request):
        context = {
            **self.admin_site.each_context(request),
            'title': 'Live Chat Dashboard',
            'api_list_url': reverse('admin:bot_fleetcustomer_chat_list'),
            'api_messages_url': reverse('admin:bot_fleetcustomer_chat_history', args=['PHONE_PLACEHOLDER']),
            'api_send_url': reverse('admin:bot_fleetcustomer_chat_send', args=['PHONE_PLACEHOLDER']),
            'api_send_media_url': reverse('admin:bot_fleetcustomer_chat_send_media', args=['PHONE_PLACEHOLDER']),
            'api_toggle_pause_url': reverse('admin:bot_fleetcustomer_chat_toggle_pause', args=['PHONE_PLACEHOLDER']),
            'api_customer_url': reverse('admin:bot_fleetcustomer_chat_customer', args=['PHONE_PLACEHOLDER']),
        }
        return render(request, "admin/live_chat.html", context)

    def api_chat_list(self, request):
        from django.db.models import Subquery, OuterRef, Q

        q = request.GET.get('q', '').strip().lower()

        # Correlated subquery: for each FleetCustomer, find the id of their latest ChatMessage
        latest_msg_subquery = ChatMessage.objects.filter(
            phone_number=OuterRef('phone_number')
        ).order_by('-id').values('id')[:1]

        qs = FleetCustomer.objects.annotate(last_msg_id=Subquery(latest_msg_subquery)).filter(last_msg_id__isnull=False)

        if q:
            qs = qs.filter(Q(owner_name__icontains=q) | Q(phone_number__icontains=q)).order_by('-last_msg_id')[:50]
        else:
            qs = qs.order_by('-last_msg_id')[:150]

        customers_list = list(qs)

        if not customers_list:
            return JsonResponse({"customers": []})

        # Batch-fetch all the "latest" messages in one query
        msg_id_to_msg = {
            m.id: m
            for m in ChatMessage.objects.filter(
                id__in=[c.last_msg_id for c in customers_list]
            ).only('id', 'phone_number', 'content', 'timestamp')
        }

        result = []
        for customer in customers_list:
            msg = msg_id_to_msg.get(customer.last_msg_id)
            if not msg:
                continue
            content = msg.content or ''
            result.append({
                "phone_number": customer.phone_number,
                "owner_name": customer.owner_name or "Unknown",
                "is_bot_paused": customer.is_bot_paused,
                "last_message": content[:50] + ("..." if len(content) > 50 else ""),
                "last_message_time": msg.timestamp.isoformat() if msg.timestamp else "",
                "timestamp_val": msg.timestamp.timestamp() if msg.timestamp else 0,
            })

        return JsonResponse({"customers": result})

    def api_chat_history(self, request, phone_number):
        # Limit to last 200 messages to avoid memory blowout on large conversations
        msgs = ChatMessage.objects.filter(
            phone_number=phone_number
        ).order_by('-id')[:200]
        data = [
            {
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp.isoformat(),
                "status": m.status,
            }
            for m in reversed(list(msgs))
        ]
        return JsonResponse({"messages": data})

    def api_chat_send(self, request, phone_number):
        if request.method == "POST":
            try:
                data = json.loads(request.body)
                content = data.get("message", "").strip()
            except Exception:
                content = request.POST.get("message", "").strip()

            if not content:
                return JsonResponse({"success": False, "error": "Message is empty"})

            from bot.views import send_whatsapp_message
            try:
                msg_id = send_whatsapp_message(phone_number, content)
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

            ChatMessage.objects.create(
                phone_number=phone_number,
                role='assistant',
                content=content,
                message_id=msg_id)
            return JsonResponse({"success": True})
        return JsonResponse({"success": False, "error": "Invalid request method"})

    def api_chat_send_media(self, request, phone_number):
        if request.method == "POST" and request.FILES.get('file'):
            upload_file = request.FILES['file']
            file_name = upload_file.name
            content_type = upload_file.content_type

            # Determine media type for WhatsApp API
            if content_type.startswith('image/'):
                media_type = 'image'
            elif content_type.startswith('video/'):
                media_type = 'video'
            elif content_type.startswith('audio/'):
                media_type = 'audio'
            else:
                media_type = 'document'

            from bot.views import send_whatsapp_message, WHATSAPP_TOKEN, PHONE_NUMBER_ID
            import tempfile
            import imageio_ffmpeg
            import subprocess
            caption_text = ""  # initialise early so finally block is always safe

            converted_file_path = None
            if media_type == 'audio':
                try:
                    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_webm:
                        temp_webm.write(upload_file.read())
                        temp_webm_path = temp_webm.name

                    converted_file_path = temp_webm_path.replace(
                        ".webm", ".mp4")
                    subprocess.run([
                        ffmpeg_exe, "-y", "-i", temp_webm_path, "-c:a", "aac", "-b:a", "128k", converted_file_path
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                    file_name = file_name.replace(
                        ".webm", ".mp4").replace(
                        ".mp4", "") + ".mp4"
                    content_type = "audio/mp4"
                    with open(converted_file_path, "rb") as f:
                        file_data = f.read()

                    os.remove(temp_webm_path)
                except Exception as e:
                    print(f"Audio conversion failed: {e}")
                    upload_file.seek(0)
                    file_data = upload_file.read()
            else:
                file_data = upload_file.read()

            # Step 1: Upload media to Meta
            url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/media"
            headers = {
                "Authorization": f"Bearer {WHATSAPP_TOKEN}"
            }
            # We must pass messaging_product as a regular field, and the file
            # as the file field
            files = {
                'file': (file_name, file_data, content_type)
            }
            data = {
                'messaging_product': 'whatsapp'
            }

            try:
                upload_res = requests.post(
                    url, headers=headers, files=files, data=data)
                upload_data = upload_res.json()
                if 'id' not in upload_data:
                    return JsonResponse(
                        {"success": False, "error": f"Upload failed: {upload_data}"})
                media_id = upload_data['id']
            except Exception as e:
                return JsonResponse(
                    {"success": False, "error": f"Failed to upload media: {str(e)}"})

            # Step 2: Send the media to the customer
            msg_id = None
            try:
                caption_text = request.POST.get("caption", "").strip()
                # For document, we need to pass the filename
                msg_id = send_whatsapp_message(
                    to_phone=phone_number,
                    text_content=caption_text if caption_text else None,
                    media_id=media_id,
                    media_type=media_type,
                    document_filename=file_name if media_type == 'document' else None
                )
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})
            finally:
                if converted_file_path and os.path.exists(converted_file_path):
                    os.remove(converted_file_path)

            # Step 3: Log in chat history
            log_content = f"[{media_type.capitalize()} Sent: {file_name}]"
            if caption_text:
                log_content += f"\nCaption: {caption_text}"
            ChatMessage.objects.create(
                phone_number=phone_number,
                role='assistant',
                content=log_content,
                message_id=msg_id)
            return JsonResponse({"success": True})

        return JsonResponse(
            {"success": False, "error": "Invalid request or missing file"})

    def api_chat_toggle_pause(self, request, phone_number):
        if request.method == "POST":
            try:
                customer = FleetCustomer.objects.get(phone_number=phone_number)
                customer.is_bot_paused = not customer.is_bot_paused
                customer.bot_paused_at = timezone.now() if customer.is_bot_paused else None
                customer.save()
                return JsonResponse({"success": True, "is_bot_paused": customer.is_bot_paused})
            except FleetCustomer.DoesNotExist:
                return JsonResponse({"success": False, "error": "Customer not found"})
        return JsonResponse({"success": False, "error": "Invalid request method"})

    def api_chat_customer(self, request, phone_number):
        """Fetch a single customer's info by phone number.
        Used as a fallback when the customer isn't in the sidebar list
        (e.g. navigating from AgentNotificationLog with ?phone=...).
        """
        try:
            c = FleetCustomer.objects.get(phone_number=phone_number)
            # Get their last message
            last_msg = ChatMessage.objects.filter(
                phone_number=phone_number
            ).order_by('-id').only('content', 'timestamp').first()
            content = (last_msg.content or '') if last_msg else ''
            return JsonResponse({
                "found": True,
                "phone_number": c.phone_number,
                "owner_name": c.owner_name or "Unknown",
                "is_bot_paused": c.is_bot_paused,
                "last_message": content[:50] + ("..." if len(content) > 50 else ""),
                "last_message_time": last_msg.timestamp.isoformat() if last_msg and last_msg.timestamp else "",
            })
        except FleetCustomer.DoesNotExist:
            # Customer not in FleetCustomer — still try to load chat history
            last_msg = ChatMessage.objects.filter(
                phone_number=phone_number
            ).order_by('-id').only('content', 'timestamp').first()
            if last_msg:
                content = last_msg.content or ''
                return JsonResponse({
                    "found": True,
                    "phone_number": phone_number,
                    "owner_name": "Unknown",
                    "is_bot_paused": False,
                    "last_message": content[:50] + ("..." if len(content) > 50 else ""),
                    "last_message_time": last_msg.timestamp.isoformat() if last_msg.timestamp else "",
                })
            return JsonResponse({"found": False})


@admin.register(BroadcastTask)
class BroadcastTaskAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'template_name',
        'status_badge',
        'total_records',
        'processed_records',
        'success_count',
        'failed_count',
        'delivered_count',
        'read_count',
        'rate_limit_per_sec',
        'created_at'
    )
    list_filter = ('status', 'template_name', 'created_at')
    search_fields = ('template_name', 'excel_file_name')
    readonly_fields = (
        'render_free_tier_dashboard',
        'processed_records',
        'success_count',
        'failed_count',
        'delivered_count',
        'read_count',
        'failed_details',
        'created_at',
        'updated_at'
    )
    actions = ['start_or_resume_campaign', 'pause_campaign', 'retry_failed_recipients']

    def render_free_tier_dashboard(self, obj):
        if not obj or not obj.id:
            return "Save task first to enable broadcast dashboard."

        from django.utils.html import format_html
        percent = round((obj.processed_records / obj.total_records) * 100, 1) if obj.total_records > 0 else 0
        cron_key = os.getenv("CRON_SECRET_KEY", "fueltracks_cron_2026")
        site_url = os.getenv("SITE_URL", "https://whatsapp-ai-bot-dqot.onrender.com").rstrip('/')
        cron_url = f"{site_url}/api/broadcast-cron/?key={cron_key}"

        html = f"""
        <div style="background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px; padding: 20px; max-width: 800px; margin-bottom: 15px;">
            <h3 style="margin-top: 0; color: #1a252f;">⚡ Render Free Tier Broadcast Runner</h3>
            
            <div style="margin-bottom: 15px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 5px; font-weight: bold;">
                    <span>Progress: <span id="bg-processed">{obj.processed_records}</span> / <span id="bg-total">{obj.total_records}</span></span>
                    <span id="bg-percent">{percent}%</span>
                </div>
                <div style="background: #e9ecef; border-radius: 10px; height: 22px; width: 100%; overflow: hidden;">
                    <div id="bg-progress-bar" style="background: linear-gradient(90deg, #28a745, #20c997); height: 100%; width: {percent}%; transition: width 0.3s;"></div>
                </div>
            </div>

            <div style="display: flex; gap: 15px; margin-bottom: 15px;">
                <div style="background: #e3f2fd; padding: 10px 15px; border-radius: 6px; flex: 1;">
                    <strong>✅ Success:</strong> <span id="bg-success">{obj.success_count}</span>
                </div>
                <div style="background: #ffebee; padding: 10px 15px; border-radius: 6px; flex: 1;">
                    <strong>❌ Failed:</strong> <span id="bg-failed">{obj.failed_count}</span>
                </div>
                <div style="background: #e8f5e9; padding: 10px 15px; border-radius: 6px; flex: 1;">
                    <strong>📬 Delivered:</strong> <span id="bg-delivered">{obj.delivered_count}</span>
                </div>
            </div>

            <div style="display: flex; gap: 10px; margin-bottom: 20px;">
                <button type="button" id="btn-start-chunk" onclick="runRenderChunkLoop()" style="background: #28a745; color: white; border: none; padding: 10px 20px; border-radius: 5px; font-weight: bold; cursor: pointer;">
                    🚀 Start / Resume Broadcast Loop (Render Free)
                </button>
                <button type="button" id="btn-pause-chunk" onclick="stopRenderChunkLoop()" style="background: #ffc107; color: #212529; border: none; padding: 10px 20px; border-radius: 5px; font-weight: bold; cursor: pointer;">
                    ⏸️ Pause Loop
                </button>
            </div>

            <div style="background: #eef2f5; padding: 12px 15px; border-left: 4px solid #17a2b8; border-radius: 4px; font-size: 13px;">
                <strong>💡 Free Automated Background Execution (cron-job.org):</strong><br>
                Add this URL to <a href="https://cron-job.org" target="_blank" style="color: #007bff; font-weight: bold;">cron-job.org</a> to ping every 1 minute. It will keep Render awake and complete all 50k broadcasts automatically in the background:<br>
                <code style="background: #fff; padding: 4px 8px; border-radius: 3px; display: inline-block; margin-top: 5px; word-break: break-all;">{cron_url}</code>
            </div>
        </div>

        <script>
        var isChunkLoopRunning = false;
        function runRenderChunkLoop() {{
            isChunkLoopRunning = true;
            document.getElementById('btn-start-chunk').disabled = true;
            document.getElementById('btn-start-chunk').innerText = "⏳ Processing Chunks...";
            fetchNextChunk();
        }}
        function stopRenderChunkLoop() {{
            isChunkLoopRunning = false;
            document.getElementById('btn-start-chunk').disabled = false;
            document.getElementById('btn-start-chunk').innerText = "🚀 Start / Resume Broadcast Loop (Render Free)";
        }}
        function fetchNextChunk() {{
            if (!isChunkLoopRunning) return;
            fetch('/api/broadcast/chunk/{obj.id}/')
                .then(res => res.json())
                .then(data => {{
                    if (data.error) {{
                        alert("Error: " + data.error);
                        stopRenderChunkLoop();
                        return;
                    }}
                    document.getElementById('bg-processed').innerText = data.processed;
                    document.getElementById('bg-total').innerText = data.total;
                    document.getElementById('bg-percent').innerText = data.percent + '%';
                    document.getElementById('bg-success').innerText = data.success;
                    document.getElementById('bg-failed').innerText = data.failed;
                    document.getElementById('bg-progress-bar').style.width = data.percent + '%';

                    if (data.status === 'completed' || data.processed >= data.total) {{
                        alert("🎉 Broadcast Completed Successfully!");
                        stopRenderChunkLoop();
                    }} else if (isChunkLoopRunning && (data.status === 'running' || data.status === 'pending')) {{
                        setTimeout(fetchNextChunk, 500);
                    }}
                }})
                .catch(err => {{
                    console.error(err);
                    setTimeout(fetchNextChunk, 2000);
                }});
        }}
        </script>
        """
        return format_html(html)
    render_free_tier_dashboard.short_description = 'Render Free Tier Dashboard'

    def status_badge(self, obj):
        from django.utils.html import format_html
        colors = {
            'pending': '#6c757d',
            'running': '#17a2b8',
            'paused': '#ffc107',
            'completed': '#28a745',
            'failed': '#dc3545',
            'stopped': '#343a40',
            'cancelled': '#6c757d',
        }
        color = colors.get(obj.status, '#000000')
        return format_html(
            '<span style="background-color: {}; color: #fff; padding: 4px 8px; border-radius: 4px; font-weight: bold;">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'

    @admin.action(description="🚀 Start / Resume Broadcast Campaign")
    def start_or_resume_campaign(self, request, queryset):
        for task in queryset:
            if task.status in ('completed', 'cancelled'):
                self.message_user(request, f"Task #{task.id} is already {task.status}.", level=messages.WARNING)
                continue

            task.status = 'running'
            task.save()

            from bot.broadcast import execute_broadcast_task_sync
            thread = threading.Thread(target=execute_broadcast_task_sync, args=(task.id,), daemon=True)
            thread.start()

            self.message_user(request, f"Started high-speed broadcast engine for Task #{task.id}.", level=messages.SUCCESS)

    @admin.action(description="⏸️ Pause Selected Campaigns")
    def pause_campaign(self, request, queryset):
        updated = queryset.filter(status='running').update(status='paused')
        self.message_user(request, f"Paused {updated} campaigns.", level=messages.SUCCESS)

    @admin.action(description="🔄 Retry Failed Recipients")
    def retry_failed_recipients(self, request, queryset):
        for task in queryset:
            failed_recs = BroadcastRecipient.objects.filter(task=task, status='failed')
            count = failed_recs.update(status='pending')
            if count > 0:
                task.status = 'pending'
                task.save()
                from bot.broadcast import execute_broadcast_task_sync
                thread = threading.Thread(target=execute_broadcast_task_sync, args=(task.id,), daemon=True)
                thread.start()
                self.message_user(request, f"Reset {count} failed recipients to pending and restarted Task #{task.id}.", level=messages.SUCCESS)
            else:
                self.message_user(request, f"No failed recipients found for Task #{task.id}.", level=messages.WARNING)



@admin.register(BroadcastRecipient)
class BroadcastRecipientAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'task_link',
        'phone_number',
        'owner_name',
        'truck_number',
        'status',
        'wamid',
        'error_code',
        'sent_at'
    )
    list_filter = ('status', 'task', 'error_code')
    search_fields = ('phone_number', 'owner_name', 'truck_number', 'wamid', 'error_message')
    readonly_fields = ('sent_at', 'updated_at')

    def task_link(self, obj):
        from django.utils.html import format_html
        return format_html('<a href="/admin/bot/broadcasttask/{}/change/">Task #{} ({})</a>', obj.task.id, obj.task.id, obj.task.template_name)
    task_link.short_description = 'Task'

