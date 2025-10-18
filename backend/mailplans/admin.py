# mailplans/admin.py
from django.contrib import admin
from .models import MailPlan, EmailLog

@admin.register(MailPlan)
class MailPlanAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'trigger_type', 'recipient_email', 'status', 'created_at')
    search_fields = ('name', 'recipient_email')

@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'mailplan', 'to_email', 'status', 'created_at', 'sent_at')
    search_fields = ('to_email', 'subject', 'response_message')
    list_filter = ('status',)
