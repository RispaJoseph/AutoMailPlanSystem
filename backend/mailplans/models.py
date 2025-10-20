# backend/mailplans/models.py
from django.db import models

class MailPlan(models.Model):
    PLAN_TRIGGER_CHOICES = [
        ('on_signup', 'On Signup'),
        ('after_1_day', 'After 1 Day'),
        ('button_click', 'On Button Click'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('scheduled', 'Scheduled'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('paused', 'Paused'),
    ]

    name = models.CharField(max_length=100)
    # restore subject (this is the missing column)
    subject = models.CharField(max_length=200, null=True, blank=True)
    content = models.TextField(null=True, blank=True)
    trigger_type = models.CharField(max_length=50, choices=PLAN_TRIGGER_CHOICES, default='on_signup')
    scheduled_time = models.DateTimeField(blank=True, null=True)
    recipient_email = models.EmailField(blank=True, null=True)
    recipient_name = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    # flow field added in migration 0005
    flow = models.JSONField(blank=True, default=dict, help_text='Visual flow JSON: {nodes: [], edges: []}')
    # template_vars / other JSON fields (kept nullable/defaults per migration)
    template_vars = models.JSONField(blank=True, default=dict, null=True)

    def __str__(self):
        display = self.name
        if self.recipient_email:
            display += f" -> {self.recipient_email}"
        return display


class EmailLog(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]

    mailplan = models.ForeignKey(MailPlan, on_delete=models.CASCADE, related_name='email_logs')
    to_email = models.EmailField()
    subject = models.CharField(max_length=300)
    body = models.TextField()
    rendered_body = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    response_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"EmailLog {self.id} -> {self.to_email} ({self.status})"
