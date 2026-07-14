from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django import forms
import os
import json
import requests
import threading
import time
from .models import ChatMessage, FleetCustomer, BroadcastTask, AdCampaign, WhatsAppTemplate, AgentNotificationLog

@admin.register(AdCampaign)
class AdCampaignAdmin(admin.ModelAdmin):
    list_display = ('campaign_name', 'ad_id', 'headline_keywords', 'catalog_file', 'is_active', 'created_at')
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
    search_fields = ('template_name', 'description', 'custom_system_prompt', 'header_image_url', 'header_media_id')
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
            import os
            try:
                path = template.header_file.path
                exists = os.path.exists(path)
            except Exception:
                exists = False

            if not exists:
                self.message_user(
                    request, 
                    f"Template '{template.template_name}' header file does not physically exist on the server's disk. "
                    f"Please re-upload the image file manually via the admin first.", 
                    level=messages.ERROR
                )
                continue

            try:
                from bot.utils import upload_media_to_meta
                media_id = upload_media_to_meta(template.header_file)
                if media_id:
                    template.header_media_id = media_id
                    from django.utils import timezone
                    template.media_id_updated_at = timezone.now()
                    template.save()
                    success_count += 1
            except Exception as e:
                self.message_user(
                    request, 
                    f"Failed to upload '{template.template_name}' to Meta: {str(e)}", 
                    level=messages.ERROR
                )

        if success_count > 0:
            self.message_user(request, f"Successfully uploaded {success_count} templates' header media to Meta.")


class ExcelUploadForm(forms.Form):
    excel_file = forms.FileField(label="Select Excel or CSV File")

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('phone_number_link', 'role', 'content', 'timestamp')
    list_filter = ('phone_number', 'role')
    search_fields = ('phone_number', 'content')
    list_display_links = ('timestamp',)

    def phone_number_link(self, obj):
        from django.utils.html import format_html
        url = f"/admin/bot/chatmessage/?phone_number={obj.phone_number}"
        return format_html('<a href="{}">{}</a>', url, obj.phone_number)
    phone_number_link.short_description = "Phone Number"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if getattr(request, '_is_changelist', False):
            # Check if request has phone_number or search filter
            has_filter = any(
                k in request.GET for k in (
                    'phone_number',
                    'phone_number__exact',
                    'q'
                )
            )
            if not has_filter:
                return qs.none()
        return qs

    def changelist_view(self, request, extra_context=None):
        request._is_changelist = True
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(AgentNotificationLog)
class AgentNotificationLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'phone_number_link', 'customer_name', 'message_content_excerpt', 'is_template_reply', 'template_name', 'notification_sent')
    list_filter = ('is_template_reply', 'template_name', 'notification_sent', 'created_at')
    search_fields = ('phone_number', 'message_content', 'template_name')
    readonly_fields = ('created_at',)
    change_list_template = "admin/agentnotificationlog_changelist.html"

    def customer_name(self, obj):
        if obj.customer:
            return obj.customer.owner_name
        return "Unknown"
    customer_name.short_description = "Customer Name"

    def message_content_excerpt(self, obj):
        return obj.message_content[:75] + ("..." if len(obj.message_content) > 75 else "")
    message_content_excerpt.short_description = "Message"

    def phone_number_link(self, obj):
        from django.utils.html import format_html
        url = f"/admin/bot/chatmessage/?phone_number={obj.phone_number}"
        return format_html('<a href="{}">{}</a>', url, obj.phone_number)
    phone_number_link.short_description = "Phone Number"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('export-excel/', self.admin_site.admin_view(self.export_excel), name='bot_agentnotificationlog_export_excel'),
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
                        start_dt = timezone.make_aware(datetime.datetime.strptime(f"{from_date} {from_time}", "%Y-%m-%d %H:%M"))
                    except ValueError:
                        start_dt = timezone.make_aware(datetime.datetime.strptime(f"{from_date} {from_time}", "%Y-%m-%d %H:%M:%S"))
                else:
                    start_dt = timezone.make_aware(datetime.datetime.strptime(f"{from_date} 00:00:00", "%Y-%m-%d %H:%M:%S"))
                qs = qs.filter(created_at__gte=start_dt)
                
            if to_date:
                if to_time:
                    try:
                        end_dt = timezone.make_aware(datetime.datetime.strptime(f"{to_date} {to_time}", "%Y-%m-%d %H:%M"))
                    except ValueError:
                        end_dt = timezone.make_aware(datetime.datetime.strptime(f"{to_date} {to_time}", "%Y-%m-%d %H:%M:%S"))
                else:
                    end_dt = timezone.make_aware(datetime.datetime.strptime(f"{to_date} 23:59:59", "%Y-%m-%d %H:%M:%S"))
                qs = qs.filter(created_at__lte=end_dt)
                
            data = list(qs.values('customer__owner_name', 'phone_number', 'message_content', 'created_at'))
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
                
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="agent_notification_logs_{timezone.now().strftime("%Y%m%d%H%M%S")}.xlsx"'
            
            with pd.ExcelWriter(response, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Logs')
                
            return response
            
        context = {
            **self.admin_site.each_context(request),
            'title': 'Export Agent Notification Logs to Excel',
        }
        return render(request, "admin/agentnotificationlog_export.html", context)


def run_broadcast_thread(task_id, file_path, template_name, language_code):
    from django.db import connection
    connection.close()
    
    try:
        from bot.models import BroadcastTask, FleetCustomer
        from bot.utils import parse_excel_or_csv
        from bot.broadcast import send_whatsapp_template
        
        task = BroadcastTask.objects.get(id=task_id)
        task.status = 'running'
        task.save()
        
        customers_data = parse_excel_or_csv(file_path)
        
        target_phone_numbers = []
        for cust in customers_data:
            customer, created = FleetCustomer.objects.update_or_create(
                phone_number=cust['phone_number'],
                defaults={
                    'owner_name': cust['owner_name'],
                    'truck_number': cust['truck_number'],
                    'is_active': cust['is_active']
                }
            )
            if customer.is_active:
                target_phone_numbers.append(customer.phone_number)
                
        active_customers = FleetCustomer.objects.filter(phone_number__in=target_phone_numbers, is_active=True)
        total_count = active_customers.count()
        
        task.total_records = total_count
        task.save()
        
        success_count = 0
        failed_count = 0
        failed_details = []
        
        for index, customer in enumerate(active_customers, 1):
            try:
                task = BroadcastTask.objects.get(id=task_id)
            except BroadcastTask.DoesNotExist:
                break
                
            success, error_reason = send_whatsapp_template(
                to_phone=customer.phone_number,
                template_name=template_name,
                customer_name=customer.owner_name,
                vehicle_number=customer.truck_number,
                language_code=language_code
            )
            
            if success:
                success_count += 1
            else:
                failed_count += 1
                failed_details.append({
                    'phone_number': customer.phone_number,
                    'name': customer.owner_name,
                    'reason': error_reason
                })
                
            task.processed_records = index
            task.success_count = success_count
            task.failed_count = failed_count
            task.failed_details = json.dumps(failed_details)
            task.save()
            
            time.sleep(0.02)
            
        task = BroadcastTask.objects.get(id=task_id)
        task.status = 'completed'
        task.save()
        
        if failed_details:
            try:
                failed_broadcast_txt_path = os.path.join(os.path.dirname(file_path), "failed_broadcast.txt")
                with open(failed_broadcast_txt_path, "w") as f:
                    for fail in failed_details:
                        f.write(f"{fail['phone_number']} | {fail['name']} | {fail['reason']}\n")
            except Exception:
                pass
                
    except Exception as e:
        try:
            task = BroadcastTask.objects.get(id=task_id)
            task.status = 'failed'
            task.failed_details = json.dumps([{'phone_number': 'N/A', 'name': 'N/A', 'reason': str(e)}])
            task.save()
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
                has_header = False
                header_type = 'none'
                for comp in item.get("components", []):
                    text = comp.get("text", "")
                    if text and "{{" in text:
                        has_vars = True
                    if comp.get("type") == "HEADER":
                        has_header = True
                        header_type = comp.get("format", "TEXT").lower()
                        
                if name not in grouped:
                    grouped[name] = {
                        "languages": set(),
                        "has_variables": False,
                        "has_header": False,
                        "header_type": "none",
                        "category": item.get("category", "")
                    }
                grouped[name]["languages"].add(lang)
                if has_vars:
                    grouped[name]["has_variables"] = True
                if has_header:
                    grouped[name]["has_header"] = True
                    grouped[name]["header_type"] = header_type
            
            # Now update the database
            for name, info in grouped.items():
                langs_str = ",".join(sorted(list(info["languages"])))
                desc = f"Sync'd from Meta: {info['category']}"
                category_lower = info['category'].lower() if info['category'] else 'marketing'
                if category_lower not in ('utility', 'marketing', 'authentication'):
                    category_lower = 'marketing'
                WhatsAppTemplate.objects.update_or_create(
                    template_name=name,
                    defaults={
                        "description": desc,
                        "category": category_lower,
                        "has_variables": info["has_variables"],
                        "languages": langs_str,
                        "has_header": info["has_header"],
                        "header_type": info["header_type"]
                    }
                )
            return {name: sorted(list(info["languages"])) for name, info in grouped.items()}
    except Exception as e:
        print(f"Error syncing templates from Meta API: {e}")
    return None


@admin.register(FleetCustomer)
class FleetCustomerAdmin(admin.ModelAdmin):
    list_display = ('owner_name', 'phone_number_link', 'truck_number', 'is_active', 'is_bot_paused', 'referred_by', 'created_at')
    list_filter = ('is_active', 'is_bot_paused', 'referred_by')
    search_fields = ('owner_name', 'phone_number', 'truck_number')
    
    def phone_number_link(self, obj):
        from django.utils.html import format_html
        url = f"/admin/bot/chatmessage/?phone_number={obj.phone_number}"
        return format_html('<a href="{}">{}</a>', url, obj.phone_number)
    phone_number_link.short_description = "Phone Number"
    
    change_list_template = "admin/fleetcustomer_changelist.html"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-excel/', self.admin_site.admin_view(self.upload_excel), name='bot_fleetcustomer_upload_excel'),
            path('broadcast/', self.admin_site.admin_view(self.broadcast), name='bot_fleetcustomer_broadcast'),
            path('broadcast-status/<int:task_id>/', self.admin_site.admin_view(self.broadcast_status), name='bot_fleetcustomer_broadcast_status'),
            path('live-chat/', self.admin_site.admin_view(self.live_chat_view), name='bot_fleetcustomer_live_chat'),
            path('live-chat/api/list/', self.admin_site.admin_view(self.api_chat_list), name='bot_fleetcustomer_chat_list'),
            path('live-chat/api/messages/<str:phone_number>/', self.admin_site.admin_view(self.api_chat_history), name='bot_fleetcustomer_chat_history'),
            path('live-chat/api/send/<str:phone_number>/', self.admin_site.admin_view(self.api_chat_send), name='bot_fleetcustomer_chat_send'),
            path('live-chat/api/toggle-pause/<str:phone_number>/', self.admin_site.admin_view(self.api_chat_toggle_pause), name='bot_fleetcustomer_chat_toggle_pause'),
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
                    messages.error(request, "Invalid file format. Please upload an Excel (.xlsx, .xls) or CSV (.csv) file.")
                    return redirect("..")
                    
                target_path = os.path.join(media_dir, f"broadcast_list{ext}")
                
                # Clean up existing broadcast_list files to prevent confusion
                for existing_ext in ('.xlsx', '.xls', '.csv'):
                    p = os.path.join(media_dir, f"broadcast_list{existing_ext}")
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
            is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax')
            
            excel_file = request.FILES.get('excel_file')
            template_name = request.POST.get('template_name')
            custom_template_name = request.POST.get('custom_template_name')
            language_code = request.POST.get('language_code', 'en_US')
            
            if template_name == 'custom' and custom_template_name:
                template_name = custom_template_name.strip()
                
            if not excel_file or not template_name:
                if is_ajax:
                    return JsonResponse({"success": False, "error": "Excel file and template name are required."})
                messages.error(request, "Excel file and template name are required.")
                return redirect(".")
                
            ext = os.path.splitext(excel_file.name)[1].lower()
            if ext not in ('.xlsx', '.xls', '.csv'):
                if is_ajax:
                    return JsonResponse({"success": False, "error": "Invalid file format. Upload Excel or CSV."})
                messages.error(request, "Invalid file format. Please upload an Excel (.xlsx, .xls) or CSV (.csv) file.")
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
            thread.daemon = True
            thread.start()
            
            if is_ajax:
                return JsonResponse({"success": True, "task_id": task.id})
                
            messages.success(request, f"Broadcast task #{task.id} started successfully!")
            return redirect(".")
        # Ensure default templates are populated if missing (with correct languages)
        default_templates = [
            ("hello_world", "Default Greetings", False, "en_US", False, "none", "", "utility"),
            ("gps_tracking_device", "GPS Tracking Devices promo", False, "en_US", False, "none", "", "marketing"),
            ("ais_140_gps_mining_device", "AIS 140 mining tracker template", False, "en_US,te", True, "image", "", "marketing"),
            ("fuel_alert", "Fuel theft/drop alerts", True, "en_US,te", False, "none", "", "utility"),
            ("fleet_update", "Fleet status summary updates", True, "en_US,te", False, "none", "", "utility"),
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

        context = {
            **self.admin_site.each_context(request),
            'title': 'WhatsApp Broadcast Panel',
            'templates': templates,
            'templates_mapping_json': json.dumps(templates_mapping),
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

    def live_chat_view(self, request):
        context = {
            **self.admin_site.each_context(request),
            'title': 'Live Chat Dashboard',
        }
        return render(request, "admin/live_chat.html", context)
        
    def api_chat_list(self, request):
        from bot.models import ChatMessage
        customers = FleetCustomer.objects.all().order_by('-created_at')
        data = []
        for c in customers:
            last_msg = ChatMessage.objects.filter(phone_number=c.phone_number).order_by('-timestamp').first()
            if not last_msg:
                continue
            data.append({
                "phone_number": c.phone_number,
                "owner_name": c.owner_name or "Unknown",
                "is_bot_paused": c.is_bot_paused,
                "last_message": last_msg.content[:50] + ("..." if len(last_msg.content) > 50 else ""),
                "last_message_time": last_msg.timestamp.isoformat(),
                "timestamp_val": last_msg.timestamp.timestamp()
            })
        data.sort(key=lambda x: x["timestamp_val"], reverse=True)
        return JsonResponse({"customers": data})

    def api_chat_history(self, request, phone_number):
        from bot.models import ChatMessage
        messages = ChatMessage.objects.filter(phone_number=phone_number).order_by('timestamp')
        data = []
        for m in messages:
            data.append({
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp.isoformat()
            })
        return JsonResponse({"messages": data})

    def api_chat_send(self, request, phone_number):
        if request.method == "POST":
            import json
            try:
                data = json.loads(request.body)
                content = data.get("message", "").strip()
            except Exception:
                content = request.POST.get("message", "").strip()
                
            if not content:
                return JsonResponse({"success": False, "error": "Message is empty"})
                
            from bot.models import ChatMessage
            from bot.views import send_whatsapp_message
            
            # Send message using WhatsApp Graph API
            success = False
            try:
                # We reuse the existing send_whatsapp_message utility
                send_whatsapp_message(phone_number, content)
                success = True
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})
                
            if success:
                ChatMessage.objects.create(phone_number=phone_number, role='assistant', content=content)
                return JsonResponse({"success": True})
        return JsonResponse({"success": False, "error": "Invalid request method"})

    def api_chat_toggle_pause(self, request, phone_number):
        if request.method == "POST":
            try:
                customer = FleetCustomer.objects.get(phone_number=phone_number)
                customer.is_bot_paused = not customer.is_bot_paused
                customer.save()
                return JsonResponse({"success": True, "is_bot_paused": customer.is_bot_paused})
            except FleetCustomer.DoesNotExist:
                return JsonResponse({"success": False, "error": "Customer not found"})
        return JsonResponse({"success": False, "error": "Invalid request method"})