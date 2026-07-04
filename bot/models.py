from django.db import models

# Create your models here.
class ChatMessage(models.Model):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
    ]
    
    phone_number = models.CharField(max_length=20, db_index=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.phone_number} - {self.role}: {self.content[:30]}"
    
    
class AdCampaign(models.Model):
    campaign_name = models.CharField(max_length=100)
    ad_id = models.CharField(max_length=100, blank=True, db_index=True)
    headline_keywords = models.CharField(
        max_length=255, 
        blank=True, 
        help_text="Comma-separated keywords to match in referral ad headline or body."
    )
    welcome_message = models.TextField(
        blank=True, 
        help_text="Optional custom greeting message sent immediately on ad click."
    )
    custom_system_prompt = models.TextField(
        blank=True, 
        help_text="Custom instructions to inject into the AI agent prompt."
    )
    catalog_file = models.CharField(
        max_length=100, 
        blank=True, 
        help_text="Catalog PDF file name to send (e.g. Wifi_Camera_Catalog.pdf)"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.campaign_name


class FleetCustomer(models.Model):
    phone_number = models.CharField(max_length=20, unique=True, db_index=True)
    owner_name = models.CharField(max_length=100, blank=True, null=True)
    truck_number = models.CharField(max_length=30, blank=True, null=True)
    is_active = models.BooleanField(default=True) # Easily drop un-subscribed or past clients
    referred_by = models.ForeignKey(
        'AdCampaign', 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL, 
        related_name='referred_customers'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.owner_name} ({self.truck_number})"


class BroadcastTask(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    template_name = models.CharField(max_length=100)
    language_code = models.CharField(max_length=10, default='en')
    excel_file_name = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_records = models.IntegerField(default=0)
    processed_records = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    failed_details = models.TextField(blank=True, null=True)  # JSON list of errors/successes
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Task {self.id}: {self.template_name} ({self.status})"


class ProcessedMessage(models.Model):
    message_id = models.CharField(max_length=255, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.message_id


class WhatsAppTemplate(models.Model):
    template_name = models.CharField(
        max_length=100, 
        unique=True, 
        help_text="Approved Meta template name (e.g. gps_tracking_device)"
    )
    description = models.CharField(
        max_length=255, 
        blank=True, 
        help_text="Brief description/label shown in dropdown"
    )
    custom_system_prompt = models.TextField(
        blank=True,
        default='',
        help_text="Custom instructions to inject into the AI agent prompt when a customer responds to this template."
    )
    has_variables = models.BooleanField(
        default=False, 
        help_text="Check if this template has placeholders (e.g., {{1}} for Customer Name, {{2}} for Vehicle Number)"
    )
    has_header = models.BooleanField(
        default=False,
        help_text="Does this template have a header?"
    )
    header_type = models.CharField(
        max_length=20,
        choices=[
            ('none', 'None'),
            ('image', 'Image'),
            ('text', 'Text'),
            ('video', 'Video'),
            ('document', 'Document'),
        ],
        default='none',
        help_text="Type of header template requires"
    )
    header_image_url = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text="URL or Meta Media ID of the header image if header type is Image/Video/Document"
    )
    header_file = models.FileField(
        upload_to='whatsapp_templates/',
        blank=True,
        null=True,
        help_text="Upload header file (image, video, document) from local system"
    )
    header_media_id = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Meta's media ID once uploaded"
    )
    media_id_updated_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Timestamp when the Meta media ID was last refreshed/uploaded"
    )
    languages = models.CharField(
        max_length=255,
        default='en_US',
        help_text="Comma-separated approved language codes (e.g. en_US,te)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        import logging
        import os
        logger = logging.getLogger(__name__)
        
        try:
            # Check if header_file has changed or was newly uploaded
            is_changed = False
            if not self.pk:
                if self.header_file:
                    is_changed = True
            else:
                try:
                    orig = WhatsAppTemplate.objects.get(pk=self.pk)
                    if self.header_file != orig.header_file:
                        is_changed = True
                except WhatsAppTemplate.DoesNotExist:
                    is_changed = True

            if is_changed:
                if self.header_file:
                    file_exists = False
                    try:
                        from django.core.files.uploadedfile import UploadedFile
                        if hasattr(self.header_file, 'file') and isinstance(self.header_file.file, UploadedFile):
                            file_exists = True
                        elif hasattr(self.header_file, 'path') and os.path.exists(self.header_file.path):
                            file_exists = True
                    except Exception as check_err:
                        logger.warning(f"Error checking if header_file exists: {check_err}")
                        file_exists = False
                    
                    if not file_exists:
                        logger.warning("The template header file does not physically exist on the server's disk. Left header_media_id blank.")
                        self.header_media_id = ''
                        self.media_id_updated_at = None
                    else:
                        # Upload to Meta
                        try:
                            from bot.utils import upload_media_to_meta
                            media_id = upload_media_to_meta(self.header_file)
                            if media_id:
                                self.header_media_id = media_id
                                from django.utils import timezone
                                self.media_id_updated_at = timezone.now()
                            else:
                                self.header_media_id = ''
                                self.media_id_updated_at = None
                        except Exception as upload_err:
                            logger.error(f"[ERROR] Meta upload failed: {upload_err}")
                            self.header_media_id = ''
                            self.media_id_updated_at = None
                else:
                    self.header_media_id = ''
                    self.media_id_updated_at = None
        except Exception as outer_err:
            logger.error(f"[ERROR] WhatsAppTemplate save hook failed: {outer_err}")
            try:
                if not hasattr(self, 'header_media_id') or not self.header_media_id:
                    self.header_media_id = ''
                if not hasattr(self, 'media_id_updated_at'):
                    self.media_id_updated_at = None
            except Exception:
                pass

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.template_name} ({self.description or 'No description'})"
