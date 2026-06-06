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