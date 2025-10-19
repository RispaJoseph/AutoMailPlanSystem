# backend/mailplans/tasks.py
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.core.mail import EmailMessage, get_connection
from django.template import Template, Context
from django.conf import settings

from .models import MailPlan, EmailLog
import logging
import json
import os

logger = logging.getLogger(__name__)


def _safe_update_log(log, **kwargs):
    """Safely update EmailLog fields without breaking task flow."""
    try:
        for k, v in kwargs.items():
            setattr(log, k, v)
        log.save(update_fields=list(kwargs.keys()))
    except Exception:
        logger.exception("Failed to update EmailLog record safely.")


def _extract_first_email_node(flow_value):
    """
    Given a flow (maybe dict or JSON string), return the first node dict
    whose type is 'email' OR which contains recipient_email in data.
    Returns None if not found.
    """
    try:
        if not flow_value:
            return None
        flow = flow_value
        if isinstance(flow_value, str):
            try:
                flow = json.loads(flow_value or "{}")
            except Exception:
                flow = {}
        if not isinstance(flow, dict):
            return None
        nodes = flow.get("nodes", []) or []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_type = node.get("type")
            data = node.get("data") or {}
            if node_type == "email" or data.get("recipient_email") or data.get("recipient"):
                return {"node": node, "data": data}
    except Exception:
        logger.exception("Failed to parse flow to find email node.")
    return None


def _extract_email_node_by_id(flow_value, node_id):
    """
    Find a node in flow with the given id and return its dict and data.
    """
    try:
        if not flow_value:
            return None
        flow = flow_value
        if isinstance(flow_value, str):
            try:
                flow = json.loads(flow_value or "{}")
            except Exception:
                flow = {}
        if not isinstance(flow, dict):
            return None
        nodes = flow.get("nodes", []) or []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if node.get("id") == node_id:
                return {"node": node, "data": node.get("data") or {}}
    except Exception:
        logger.exception("Failed to parse flow to find node by id.")
    return None


def _render_with_template(text, context_vars):
    """
    Render a Django template string with context_vars using Template/Context.
    Falls back to returning the original text on errors.
    """
    try:
        if text is None:
            return ""
        # ensure text is str
        tpl = Template(str(text))
        ctx = Context(context_vars or {})
        return tpl.render(ctx)
    except Exception:
        logger.exception("Template rendering error for text: %r", text)
        # fallback: do a simple replacement for basic {{ key }} tokens to be forgiving
        try:
            result = str(text)
            for k, v in (context_vars or {}).items():
                result = result.replace("{{ " + str(k) + " }}", str(v))
                result = result.replace("{{" + str(k) + "}}", str(v))
            return result
        except Exception:
            return str(text)


@shared_task(bind=True, max_retries=5)
def send_mail_task(self, mailplan_id, node_id=None):
    """
    Celery task to send an email for a given MailPlan ID.
    Optionally accepts node_id to target a specific email node in the flow.
    """
    # --- EMERGENCY SAFETY LOCK ---
    # Set environment variable DISABLE_EMAIL_SEND=1 to skip actual sending while debugging.
    if os.environ.get("DISABLE_EMAIL_SEND", "0") in ("1", "true", "True"):
        logger.warning(f"[MailPlan:{mailplan_id}] send_mail_task skipped because DISABLE_EMAIL_SEND is set.")
        try:
            mp = MailPlan.objects.filter(id=mailplan_id).first()
            if mp:
                try:
                    EmailLog.objects.create(
                        mailplan=mp,
                        to_email="(skipped)",
                        subject="(skipped)",
                        body="Skipped sending due to DISABLE_EMAIL_SEND flag",
                        status="skipped",
                        response_message="send_skipped_by_debug_flag"
                    )
                except Exception:
                    logger.exception("Failed to create skip EmailLog entry for MailPlan %s", mailplan_id)
        except Exception:
            logger.exception("Error while recording skip for MailPlan %s", mailplan_id)
        return {"status": "skipped", "reason": "DISABLE_EMAIL_SEND set"}
    # --- END SAFETY LOCK ---

    try:
        mp = MailPlan.objects.get(id=mailplan_id)
    except MailPlan.DoesNotExist:
        logger.error(f"[MailPlan:{mailplan_id}] Not found.")
        return {"status": "error", "reason": "MailPlan not found"}

    # Extract node-level data: prefer provided node_id, otherwise find first email node
    node_info = None
    if node_id:
        node_info = _extract_email_node_by_id(mp.flow, node_id)
    if not node_info:
        node_info = _extract_first_email_node(mp.flow)

    node_data = node_info.get("data") if node_info else {}

    # Determine recipient (node-level takes precedence)
    recipient = None
    if node_data:
        recipient = node_data.get("recipient_email") or node_data.get("recipient")
    if not recipient:
        recipient = getattr(mp, "recipient_email", None)

    # Prepare template_vars: merge top-level and node-level (node wins)
    top_vars = mp.template_vars or {}
    node_vars = node_data.get("template_vars") if node_data and isinstance(node_data.get("template_vars"), dict) else {}
    # ensure types are dicts
    if not isinstance(top_vars, dict):
        try:
            top_vars = json.loads(top_vars or "{}")
        except Exception:
            top_vars = {}
    if not isinstance(node_vars, dict):
        try:
            node_vars = json.loads(node_vars or "{}")
        except Exception:
            node_vars = {}

    merged_vars = {**top_vars, **node_vars}  # node_vars override top_vars

    # Determine subject and content (node overrides top-level)
    raw_subject = (node_data.get("subject") if node_data and node_data.get("subject") else mp.subject) or ""
    raw_content = (node_data.get("body") if node_data and node_data.get("body") else getattr(mp, "content", None)) or ""

    # Create EmailLog entry (best-effort)
    log = None
    try:
        log = EmailLog.objects.create(
            mailplan=mp,
            to_email=recipient or '',
            subject=raw_subject,
            body=raw_content,
            status="pending"
        )
    except Exception:
        logger.exception(f"[MailPlan:{mailplan_id}] Failed to create EmailLog.")
        log = None

    # Render templates
    try:
        rendered_subject = _render_with_template(raw_subject, merged_vars)
        rendered_content = _render_with_template(raw_content, merged_vars)
    except Exception as e:
        logger.exception(f"[MailPlan:{mailplan_id}] Template rendering failed: {e}")
        rendered_subject = raw_subject
        rendered_content = raw_content

    # Build HTML + plain text fallback
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background: #f9fafb; padding: 20px;">
        <div style="max-width:600px;margin:auto;background:white;border-radius:10px;
                    box-shadow:0 4px 10px rgba(0,0,0,0.05);padding:20px;">
          <h2 style="color:#2563eb;">📧 {rendered_subject}</h2>
          <div style="font-size:16px;line-height:1.6;color:#333;">{rendered_content}</div>
          <hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
          <p style="font-size:13px;color:#888;">Sent automatically by <strong>Auto Mail Plan System</strong></p>
        </div>
      </body>
    </html>
    """

    text_body = rendered_content if isinstance(rendered_content, str) else str(rendered_content)

    # Store rendered body in EmailLog
    if log:
        try:
            if hasattr(log, "rendered_body"):
                log.rendered_body = html_body
            log.subject = rendered_subject
            log.body = text_body
            log.save(update_fields=[f for f in ("rendered_body", "subject", "body") if hasattr(log, f)])
        except Exception:
            logger.exception(f"[MailPlan:{mailplan_id}] Failed to save rendered content to EmailLog.")

    # Validate recipient
    if not recipient:
        logger.error(f"[MailPlan:{mailplan_id}] No recipient found (node or top-level). Aborting send.")
        if log:
            _safe_update_log(log, status="failed", response_message="no_recipient")
        try:
            mp.status = "failed"
            mp.save(update_fields=["status"])
        except Exception:
            logger.exception(f"[MailPlan:{mailplan_id}] Failed to update MailPlan status to failed.")
        return {"status": "failed", "reason": "no_recipient"}

    # Support multiple recipients if node_data/recipient is a list
    recipients = []
    if isinstance(recipient, str):
        # allow comma or newline separated addresses
        recipients = [r.strip() for r in recipient.replace("\n", ",").split(",") if r.strip()]
    elif isinstance(recipient, (list, tuple)):
        recipients = list(recipient)
    else:
        recipients = [str(recipient)]

    # Send the email
    try:
        connection = get_connection()
        email = EmailMessage(
            subject=rendered_subject,
            body=html_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
            connection=connection,
        )
        email.content_subtype = "html"

        sent_count = email.send(fail_silently=False)

        # Mark as sent
        if log:
            _safe_update_log(
                log,
                status="sent" if sent_count else "failed",
                sent_at=timezone.now(),
                response_message=f"sent_count={sent_count}",
            )

        try:
            mp.status = "sent" if sent_count else "failed"
            mp.save(update_fields=["status"])
        except Exception:
            logger.exception(f"[MailPlan:{mailplan_id}] Failed to update MailPlan status.")

        logger.info(f"[MailPlan:{mp.id}] Email sent to {recipients}")
        return {"status": "sent", "mailplan_id": mp.id, "recipient": recipients}

    except Exception as exc:
        # Handle transient failures (SMTP/network)
        logger.exception(f"[MailPlan:{mailplan_id}] Failed to send email: {exc}")

        if log:
            _safe_update_log(log, status="failed", response_message=str(exc))

        try:
            mp.status = "failed"
            mp.save(update_fields=["status"])
        except Exception:
            logger.exception(f"[MailPlan:{mailplan_id}] Failed to update MailPlan to 'failed'.")

        # Exponential backoff retry
        retries = getattr(self.request, "retries", 0)
        countdown = min(60 * (2 ** retries), 3600)

        try:
            raise self.retry(exc=exc, countdown=countdown)
        except self.MaxRetriesExceededError:
            logger.error(f"[MailPlan:{mailplan_id}] Max retries exceeded.")
            return {"status": "failed", "reason": "max_retries_exceeded"}


# helper to convert flow into graph (unchanged)
def _flow_to_graph(flow):
    """
    Convert flow dict into adjacency mapping and node map.
    """
    nodes_map = {}
    adjacency = {}
    nodes = flow.get("nodes", []) or []
    edges = flow.get("edges", []) or []

    for n in nodes:
        nodes_map[n.get("id")] = n

    for e in edges:
        src = e.get("source")
        tgt = e.get("target")
        if not src or not tgt:
            continue
        adjacency.setdefault(src, []).append(tgt)

    return nodes_map, adjacency


def _duration_seconds(duration, unit):
    if not duration:
        return 0
    unit = (unit or "").lower()
    try:
        dur_val = int(duration)
    except Exception:
        try:
            dur_val = float(duration)
            dur_val = int(dur_val)
        except Exception:
            dur_val = 0
    if unit == "minutes":
        return dur_val * 60
    if unit == "hours":
        return dur_val * 3600
    if unit == "days":
        return dur_val * 86400
    # fallback to seconds when numeric provided
    return dur_val


@shared_task(bind=True)
def execute_flow_task(self, mailplan_id):
    """
    Traverse the saved flow and schedule send_mail_task calls
    respecting Delay nodes. This runs once per trigger.

    The implementation schedules send_mail_task.apply_async with ETA when there
    is an accumulated delay; otherwise it enqueues immediate send.
    """
    try:
        mp = MailPlan.objects.get(id=mailplan_id)
    except MailPlan.DoesNotExist:
        logger.error("MailPlan %s not found", mailplan_id)
        return

    flow_val = getattr(mp, "flow", {}) or {}
    if isinstance(flow_val, str):
        try:
            flow_val = json.loads(flow_val or "{}")
        except Exception:
            flow_val = {}

    if not isinstance(flow_val, dict):
        logger.warning("Flow for MailPlan %s is not a dict, aborting execute_flow_task", mailplan_id)
        return

    nodes_map, adjacency = _flow_to_graph(flow_val)

    # find a start node: preference: node with type 'start' else any trigger node
    start_id = None
    for nid, n in nodes_map.items():
        if (n.get("type") == "start") or (n.get("id") == "start"):
            start_id = nid
            break
    if not start_id:
        # find any trigger node
        for nid, n in nodes_map.items():
            if n.get("type") == "trigger":
                start_id = nid
                break

    if not start_id:
        logger.warning("No start or trigger node found for MailPlan %s; fallback to scheduling immediate send", mailplan_id)
        # fallback: call send_mail_task directly (no node)
        try:
            send_mail_task.delay(mp.id)
        except Exception as e:
            logger.exception("Fallback send failed: %s", e)
        return

    logger.info("execute_flow_task: starting traversal for MailPlan %s from node %s", mailplan_id, start_id)

    # DFS traversal from start: follow all paths and schedule sends at email nodes
    stack = [(start_id, 0)]  # (node_id, accumulated_seconds)
    visited = set()
    max_steps = 5000
    steps = 0

    while stack:
        if steps > max_steps:
            logger.warning("Flow traversal exceeded max steps for MailPlan %s", mailplan_id)
            break
        steps += 1

        node_id, acc_seconds = stack.pop()
        node = nodes_map.get(node_id)
        if not node:
            continue

        logger.debug("Visiting node %s (type=%s) acc_seconds=%s", node_id, node.get("type"), acc_seconds)

        # If this node is a delay node, add its duration
        if node.get("type") == "delay" or (node.get("data") and ("duration" in node.get("data") or "unit" in node.get("data"))):
            data = node.get("data") or {}
            dur = data.get("duration") or 0
            unit = data.get("unit") or "hours"
            add_seconds = _duration_seconds(dur, unit)
            old_acc = acc_seconds
            acc_seconds = acc_seconds + add_seconds
            logger.info(
                "Delay node %s adds %s seconds (unit=%s duration=%s). acc_seconds: %s -> %s",
                node_id, add_seconds, unit, dur, old_acc, acc_seconds
            )

    # If this node is an email node -> schedule send with the current acc_seconds
        if node.get("type") == "email" or (node.get("data") and (node.get("data").get("recipient_email") or node.get("data").get("recipient"))):
            # compute ETA for clarity
            try:
                if acc_seconds and acc_seconds > 0:
                    eta_time = timezone.now() + timedelta(seconds=acc_seconds)
                    # schedule using ETA (timezone-aware)
                    send_mail_task.apply_async(args=(mp.id, node.get("id")), eta=eta_time)
                    logger.info(
                        "Scheduled send_mail_task for MailPlan %s node %s with ETA %s (after %s seconds)",
                        mp.id, node.get("id"), eta_time.isoformat(), acc_seconds
                    )
                else:
                    # immediate enqueue
                    send_mail_task.delay(mp.id, node.get("id"))
                    logger.info(
                        "Scheduled immediate send_mail_task for MailPlan %s node %s",
                        mp.id, node.get("id")
                    )
            except Exception as e:
                logger.exception("Failed to schedule send for MailPlan %s node %s: %s", mp.id, node.get("id"), e)

        # push child nodes with updated accumulated seconds
        targets = adjacency.get(node_id, []) or []
        for tgt in targets:
            key = (tgt, acc_seconds)
            if key in visited:
                continue
            visited.add(key)
            stack.append((tgt, acc_seconds))

    logger.info("execute_flow_task: finished scheduling for MailPlan %s (steps=%s)", mailplan_id, steps)
    return {"status": "scheduled_flow", "mailplan_id": mp.id}


@shared_task
def schedule_due_mailplans():
    """
    Periodic task that finds MailPlans ready to send:
      - trigger_type='scheduled' and scheduled_time <= now
      - trigger_type='after_1_day' created 24h ago
    Enqueues each for delivery.
    """
    now = timezone.now()

    # Scheduled mails
    scheduled_plans = MailPlan.objects.filter(status="scheduled", scheduled_time__lte=now)

    for mp in scheduled_plans:
        send_mail_task.delay(mp.id)

    # After 1 day mails
    one_day_ago = now - timedelta(days=1)
    day_later_plans = MailPlan.objects.filter(
        trigger_type="after_1_day",
        status="active",
        created_at__lte=one_day_ago,
    )

    for mp in day_later_plans:
        try:
            execute_flow_task.delay(mp.id)
        except Exception:
            send_mail_task.delay(mp.id)

    logger.info(
        f"schedule_due_mailplans ran: {scheduled_plans.count()} scheduled, {day_later_plans.count()} after_1_day."
    )

    return {"scheduled_sent": scheduled_plans.count(), "one_day_triggered": day_later_plans.count()}
