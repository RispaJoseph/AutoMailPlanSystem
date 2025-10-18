# backend/mailplans/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import MailPlan
from .serializers import MailPlanSerializer
from .tasks import send_mail_task, execute_flow_task
import logging

logger = logging.getLogger(__name__)


class MailPlanViewSet(viewsets.ModelViewSet):
    queryset = MailPlan.objects.all().order_by('-created_at')
    serializer_class = MailPlanSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        """
        Save the MailPlan. If the plan's trigger type is 'on_signup' we enqueue
        the flow executor so any Delay/Email nodes in the flow are respected.
        """
        instance = serializer.save()
        if instance.trigger_type == 'on_signup':
            try:
                # Use the flow executor so node sequencing/delays are honored
                execute_flow_task.delay(instance.id)
                logger.info("Enqueued execute_flow_task for MailPlan %s (on_signup)", instance.id)
            except Exception as e:
                logger.warning(
                    "Could not enqueue execute_flow_task for MailPlan %s (on_create on_signup): %s",
                    instance.id, e
                )

    @action(detail=True, methods=['post'])
    def trigger(self, request, pk=None):
        """
        POST /api/mailplans/{id}/trigger/

        Enqueue execution of the plan's flow (execute_flow_task). This ensures
        Delay nodes are respected and the full flow is traversed.

        If enqueueing fails we attempt a synchronous fallback:
          1) execute_flow_task.apply(...)  (best-effort synchronous flow execution)
          2) send_mail_task.apply(...)     (final synchronous fallback that sends immediately)
        """
        mp = self.get_object()

        # Helpful debug log so you can inspect the flow snapshot at trigger time
        try:
            logger.info(
                "Trigger requested for MailPlan %s by user %s. trigger_type=%s, status=%s, flow_snapshot=%s",
                mp.id,
                getattr(request.user, "id", None),
                getattr(mp, "trigger_type", None),
                getattr(mp, "status", None),
                getattr(mp, "flow", None),
            )
        except Exception:
            # if flow is large, logging may fail — swallow to avoid breaking trigger
            logger.debug("Trigger log: unable to include full flow snapshot for MailPlan %s", mp.id)

        # Try to enqueue flow execution (preferred)
        try:
            execute_flow_task.delay(mp.id)
            return Response({"message": "Flow enqueued"}, status=status.HTTP_202_ACCEPTED)
        except Exception as exc:
            logger.warning("Failed to enqueue execute_flow_task for MailPlan %s: %s", mp.id, exc)

        # Fallback 1: attempt synchronous flow execution (will run in-process)
        try:
            execute_flow_task.apply(args=(mp.id,))
            return Response({"message": "Flow executed synchronously (fallback)"}, status=status.HTTP_200_OK)
        except Exception as exc2:
            logger.exception("Synchronous execute_flow_task fallback failed for MailPlan %s: %s", mp.id, exc2)

        # Final fallback: send immediately using send_mail_task synchronously
        try:
            send_mail_task.apply(args=(mp.id,))
            return Response({"message": "Sent synchronously (final fallback)"}, status=status.HTTP_200_OK)
        except Exception as exc3:
            logger.exception("Final fallback send_mail_task failed for MailPlan %s: %s", mp.id, exc3)
            return Response(
                {"error": "Unable to enqueue or send at this time."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
