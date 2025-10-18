# mailplans/signals.py
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .models import MailPlan
from .tasks import send_mail_task

logger = logging.getLogger(__name__)

def _enqueue_send(mailplan_id):
    """
    Try to enqueue the Celery task. If broker is unavailable,
    fall back to a synchronous send (safe for demo) and update DB.
    """
    try:
        # primary: enqueue async task (non-blocking)
        send_mail_task.delay(mailplan_id)
        logger.info(f"Enqueued send_mail_task for MailPlan {mailplan_id}")
    except Exception as exc:
        # Broker unavailable — don't raise (prevents 500)
        logger.warning(f"Celery broker unavailable for MailPlan {mailplan_id}: {exc}. Falling back to synchronous send.")
        try:
            # synchronous fallback (runs in web process) — okay for demo only
            send_mail_task(mailplan_id)
            logger.info(f"Synchronous send_mail_task executed for MailPlan {mailplan_id}")
        except Exception as e2:
            logger.exception(f"Failed to send mail synchronously for MailPlan {mailplan_id}: {e2}")
            # mark the MailPlan so you can retry later
            try:
                mp = MailPlan.objects.filter(id=mailplan_id).first()
                if mp:
                    mp.status = 'failed'
                    mp.save(update_fields=['status'])
            except Exception:
                logger.exception("Failed to mark MailPlan as failed after fallback send error.")

@receiver(post_save, sender=MailPlan)
def schedule_mailplan_send(sender, instance, created, **kwargs):
    if not created:
        return

    # enqueue only after the surrounding DB transaction commits successfully
    transaction.on_commit(lambda: _enqueue_send(instance.id))
