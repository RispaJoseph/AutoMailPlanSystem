from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from .models import MailPlan


class RecipientListView(APIView):
    """
    API endpoint to list all unique recipients with optional filters.
    GET /api/recipients/?email=&name=&tag=
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        email_filter = request.query_params.get('email')
        name_filter = request.query_params.get('name')
        tag_filter = request.query_params.get('tag')

        # Base queryset
        qs = MailPlan.objects.all()

        # Apply optional filters
        if email_filter:
            qs = qs.filter(recipient_email__icontains=email_filter)
        if name_filter:
            qs = qs.filter(recipient_name__icontains=name_filter)  # ✅ updated field
        if tag_filter:
            # Optional: filter by tags or template_vars content
            qs = qs.filter(template_vars__icontains=tag_filter)

        # Build unique recipient list with richer info
        recipients = {}
        for plan in qs:
            email = plan.recipient_email
            if email not in recipients:
                recipients[email] = {
                    "email": plan.recipient_email,
                    "name": plan.recipient_name or "",
                    "plan": plan.name,
                }

        recipient_list = list(recipients.values())

        return Response({
            "count": len(recipient_list),
            "recipients": recipient_list,
        })
