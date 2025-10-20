# backend/mailplans/signals.py
"""
Guarded signal handlers for MailPlan.

Previous behavior: this signal enqueued a send_mail_task on every MailPlan post_save,
causing newly-created plans to be sent immediately (regardless of trigger type or delays).

New behavior:
 - By default this file does NOTHING on MailPlan save.
 - To enable the old automatic behavior (only in controlled environments), set:
       ALLOW_AUTO_ENQUEUE=1
   in the environment. Even then, the code will only auto-enqueue for a
   conservative set of trigger types and only when the MailPlan is newly created.

If you want automatic sends on real user signup or other real events, wire
those events explicitly to a handler instead of using a generic model post_save.
"""

import os
import logging
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import MailPlan
from .tasks import send_mail_task

logger = logging.getLogger(__name__)

# Safety toggle: only allow auto-enqueue when this environment var is set.
ALLOW_AUTO_ENQUEUE = os.environ.get("ALLOW_AUTO_ENQUEUE", "0") in ("1", "true", "True")


def _enqueue_send(mailplan_id):
    """
    Enqueue the task to send a MailPlan. Kept as a helper so we can call it
    from controlled places (e.g. transaction.on_commit).
    """
    try:
        send_mail_task.delay(mailplan_id)
        logger.info("Enqueued send_mail_task for MailPlan %s (via guarded signal)", mailplan_id)
    except Exception as exc:
        logger.exception("Failed to enqueue send_mail_task for MailPlan %s: %s", mailplan_id, exc)


@receiver(post_save, sender=MailPlan)
def schedule_mailplan_send(sender, instance, created, **kwargs):
    """
    Guarded post_save handler.

    Default: do nothing (prevents automatic sends when creating or updating MailPlans).

    If ALLOW_AUTO_ENQUEUE is set, only auto-enqueue on created=True and for a
    conservative set of trigger types (so we don't accidentally send on every save).
    """
    if not ALLOW_AUTO_ENQUEUE:
        logger.debug(
            "Auto-enqueue disabled (ALLOW_AUTO_ENQUEUE not set). Ignoring MailPlan save for id=%s",
            getattr(instance, "id", None),
        )
        return

    # Only run on newly created objects
    if not created:
        logger.debug(
            "Auto-enqueue allowed but MailPlan was not 'created' — ignoring id=%s", getattr(instance, "id", None)
        )
        return

    # Conservative allowed trigger types (adjust as needed)
    allowed_triggers = {"scheduled", "after_1_day", "on_signup"}
    trigger = getattr(instance, "trigger_type", None)
    if trigger not in allowed_triggers:
        logger.info(
            "Auto-enqueue allowed but trigger_type=%s not in allowed set for id=%s. Skipping.",
            trigger,
            getattr(instance, "id", None),
        )
        return

    # Enqueue after transaction commit to ensure the MailPlan exists in DB
    try:
        transaction.on_commit(lambda: _enqueue_send(instance.id))
        logger.info("Scheduled enqueue_on_commit for MailPlan %s (auto-enqueue enabled).", instance.id)
    except Exception:
        logger.exception("Failed to schedule enqueue_on_commit for MailPlan %s", instance.id)
