# backend/mailplans/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import MailPlan
from .serializers import MailPlanSerializer
from .tasks import send_mail_task, execute_flow_task
import logging
import json

logger = logging.getLogger(__name__)


def flow_has_delay(flow_value):
    try:
        if not flow_value:
            return False
        flow = flow_value
        if isinstance(flow_value, str):
            try:
                flow = json.loads(flow_value or "{}")
            except Exception:
                flow = {}
        if not isinstance(flow, dict):
            return False
        nodes = flow.get("nodes", []) or []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            ntype = (node.get("type") or "").lower()
            data = node.get("data") or {}
            if ntype in ("delay", "wait", "delay_node"):
                return True
            if any(k in data for k in ("duration", "delay_minutes", "delay_seconds", "delay_hours", "unit")):
                return True
        return False
    except Exception:
        logger.exception("Error while checking flow for delay nodes.")
        return False


class MailPlanViewSet(viewsets.ModelViewSet):
    queryset = MailPlan.objects.all().order_by('-created_at')
    serializer_class = MailPlanSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        """
        Save the MailPlan.

        NOTE: We used to automatically enqueue execute_flow_task here when
        trigger_type == 'on_signup'. That caused unexpected sends when
        MailPlans were created. Signup-triggered sends should be fired by the
        actual user-signup event (signal) or another explicit trigger, not on
        MailPlan creation. So we intentionally do NOT enqueue here.
        """
        instance = serializer.save()
        # NO automatic enqueue here — keep creation safe
        logger.info("MailPlan created id=%s trigger_type=%s by user=%s",
                    instance.id, getattr(instance, 'trigger_type', None), getattr(self.request.user, 'id', None))

    @action(detail=True, methods=['post'])
    def trigger(self, request, pk=None):
        """
        POST /api/mailplans/{id}/trigger/

        This endpoint now *requires* explicit confirmation from the caller to
        perform a manual trigger. The caller must either:
          - send JSON body: {"confirm": true}
          - OR send header: X-MANUAL-TRIGGER: "1"

        This prevents accidental triggers from UI redirects or other code.
        """
        mp = self.get_object()

        # only allow manual trigger for button_click
        if getattr(mp, "trigger_type", None) != 'button_click':
            return Response(
                {"error": "Manual trigger is allowed only for plans with trigger_type='button_click'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # require explicit confirmation
        confirm_body = request.data.get('confirm') if isinstance(request.data, dict) else None
        header_confirm = request.META.get('HTTP_X_MANUAL_TRIGGER') in ('1', 'true', 'True')
        if not (confirm_body is True or header_confirm):
            # log caller info for debugging
            logger.warning(
                "Manual trigger denied for MailPlan %s: missing confirm flag. Caller: user=%s, remote=%s, referer=%s, data=%s",
                mp.id,
                getattr(request.user, 'id', None),
                request.META.get('REMOTE_ADDR'),
                request.META.get('HTTP_REFERER'),
                request.data
            )
            return Response(
                {"error": "Manual trigger requires explicit confirmation ('confirm': true in JSON body or header X-MANUAL-TRIGGER: 1)."},
                status=status.HTTP_400_BAD_REQUEST
            )

        logger.info(
            "Manual trigger confirmed for MailPlan %s by user %s. status=%s, remote=%s, referer=%s",
            mp.id, getattr(request.user, 'id', None), getattr(mp, 'status', None),
            request.META.get('REMOTE_ADDR'), request.META.get('HTTP_REFERER')
        )

        flow_val = getattr(mp, "flow", {}) or {}

        try:
            if flow_has_delay(flow_val):
                execute_flow_task.delay(mp.id)
                try:
                    mp.status = 'scheduled'
                    mp.save(update_fields=['status'])
                except Exception:
                    logger.exception("Failed to update MailPlan status to scheduled after enqueueing flow.")
                logger.info("Enqueued execute_flow_task for MailPlan %s (contains delay nodes).", mp.id)
                return Response({"message": "Flow enqueued; will honor delay nodes."}, status=status.HTTP_202_ACCEPTED)
            else:
                send_mail_task.delay(mp.id)
                try:
                    mp.status = 'sent'
                    mp.save(update_fields=['status'])
                except Exception:
                    logger.exception("Failed to update MailPlan status to sent after enqueueing send_mail_task.")
                logger.info("Enqueued send_mail_task for MailPlan %s (no delay nodes).", mp.id)
                return Response({"message": "Mail send enqueued (no delays in flow)."}, status=status.HTTP_202_ACCEPTED)
        except Exception as exc:
            logger.exception("Trigger processing failed for MailPlan %s: %s", mp.id, exc)

        # fallback behavior unchanged...
        try:
            execute_flow_task.delay(mp.id)
            try:
                mp.status = 'scheduled'
                mp.save(update_fields=['status'])
            except Exception:
                logger.exception("Failed to update MailPlan status to scheduled in fallback.")
            return Response({"message": "Flow enqueued (fallback)."}, status=status.HTTP_202_ACCEPTED)
        except Exception as exc2:
            logger.warning("Fallback enqueue execute_flow_task failed for MailPlan %s: %s", mp.id, exc2)

        try:
            send_mail_task.apply(args=(mp.id,))
            try:
                mp.status = 'sent'
                mp.save(update_fields=['status'])
            except Exception:
                logger.exception("Failed to update MailPlan status to sent in final fallback.")
            return Response({"message": "Sent synchronously (final fallback)"}, status=status.HTTP_200_OK)
        except Exception as exc3:
            logger.exception("Final synchronous send failed for MailPlan %s: %s", mp.id, exc3)
            return Response({"error": "Unable to enqueue or send at this time."},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
