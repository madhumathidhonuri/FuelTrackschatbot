from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django import forms
import os
from .models import ChatMessage, FleetCustomer

class ExcelUploadForm(forms.Form):
    excel_file = forms.FileField(label="Select Excel or CSV File")

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'role', 'content', 'timestamp')
    list_filter = ('phone_number',)

@admin.register(FleetCustomer)
class FleetCustomerAdmin(admin.ModelAdmin):
    list_display = ('owner_name', 'phone_number', 'truck_number', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('owner_name', 'phone_number', 'truck_number')
    
    change_list_template = "admin/fleetcustomer_changelist.html"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-excel/', self.admin_site.admin_view(self.upload_excel), name='bot_fleetcustomer_upload_excel'),
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