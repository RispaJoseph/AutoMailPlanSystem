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
    subject = models.CharField(max_length=200)
    content = models.TextField()
    trigger_type = models.CharField(max_length=50, choices=PLAN_TRIGGER_CHOICES)
    scheduled_time = models.DateTimeField(null=True, blank=True)
    recipient_email = models.EmailField(db_index=True)
    recipient_name = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # store the visual flow (React Flow nodes + edges) so frontend can load it
    flow = models.JSONField(default=dict, blank=True, help_text='Visual flow JSON: {nodes: [], edges: []}')

    # existing template vars
    template_vars = models.JSONField(default=dict, blank=True, help_text='Merge variables, e.g. {"first_name": "Rispa"}')

    def __str__(self):
        if self.recipient_name:
            return f"{self.name} -> {self.recipient_name} <{self.recipient_email}>"
        return f"{self.name} -> {self.recipient_email}"


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
