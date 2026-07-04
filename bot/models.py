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
    languages = models.CharField(
        max_length=255,
        default='en_US',
        help_text="Comma-separated approved language codes (e.g. en_US,te)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        from django.core.exceptions import ValidationError
        
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
                from django.core.files.uploadedfile import UploadedFile
                file_exists = False
                if isinstance(self.header_file.file, UploadedFile):
                    file_exists = True
                else:
                    try:
                        file_exists = os.path.exists(self.header_file.path)
                    except (ValueError, AttributeError):
                        file_exists = False
                
                if not file_exists:
                    raise ValidationError(
                        "The template header file does not physically exist on the server's disk. "
                        "Please re-upload the image file manually via the admin first."
                    )
                
                # Upload to Meta
                try:
                    from bot.utils import upload_media_to_meta
                    media_id = upload_media_to_meta(self.header_file)
                    if media_id:
                        self.header_media_id = media_id
                except Exception as e:
                    raise ValidationError(f"Failed to upload header media to Meta Cloud API: {str(e)}")
            else:
                self.header_media_id = ''

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.template_name} ({self.description or 'No description'})"
