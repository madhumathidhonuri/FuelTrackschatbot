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
    
    
class FleetCustomer(models.Model):
    phone_number = models.CharField(max_length=20, unique=True, db_index=True)
    owner_name = models.CharField(max_length=100, blank=True, null=True)
    truck_number = models.CharField(max_length=30, blank=True, null=True)
    is_active = models.BooleanField(default=True) # Easily drop un-subscribed or past clients
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