from django.contrib import admin
from .models import ChatMessage

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'role', 'content', 'timestamp')
    list_filter = ('phone_number',)