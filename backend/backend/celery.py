import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

app = Celery('backend')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


# 🔁 Schedule periodic tasks
app.conf.beat_schedule = {
    'check-due-mailplans-every-minute': {
        'task': 'mailplans.tasks.schedule_due_mailplans',
        'schedule': crontab(minute='*/1'),  # every 1 minute
    },
}