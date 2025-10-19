from rest_framework import serializers
from .models import MailPlan
import json
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()

class MailPlanSerializer(serializers.ModelSerializer):
    # allow flow to be optional on input and default to empty dict
    flow = serializers.JSONField(required=False, default=dict)

    class Meta:
        model = MailPlan
        fields = '__all__'

    def _compute_recipient_from_flow(self, flow_obj):
        """
        Given a flow (dict or JSON string), return the first email node's recipient
        if present. Returns None when nothing found.
        """
        try:
            if not flow_obj:
                return None
            # if stored as string, parse it
            if isinstance(flow_obj, str):
                flow = json.loads(flow_obj or "{}")
            else:
                flow = flow_obj
            nodes = flow.get('nodes', []) if isinstance(flow, dict) else []
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                node_type = node.get('type')
                data = node.get('data') or {}
                # prefer explicit email node or presence of recipient_email/recipient
                if node_type == 'email' or data.get('recipient_email') or data.get('recipient'):
                    email = data.get('recipient_email') or data.get('recipient')
                    if email:
                        return email
        except Exception:
            # fail silently and return None so fallback works
            return None
        return None

    def to_representation(self, instance):
        """
        Represent instance as dict, but replace the 'recipient_email' value
        with the first found recipient in the flow (if any). Fall back to the DB field.
        This preserves writeability: client can still provide recipient_email in payload.
        """
        rep = super().to_representation(instance)

        # Compute recipient from the instance.flow (preferred) or from rep['flow']
        flow_val = getattr(instance, 'flow', None)
        recipient_from_flow = self._compute_recipient_from_flow(flow_val)

        if recipient_from_flow:
            rep['recipient_email'] = recipient_from_flow
        else:
            # fallback: keep whatever is serialized (top-level DB value)
            rep['recipient_email'] = rep.get('recipient_email') or getattr(instance, 'recipient_email', None)

        return rep



class SafeTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Accept 'email', 'username_or_email', 'identifier' or 'user' in request payload
    and map to the username field expected by the base TokenObtainPairSerializer.
    """
    username_field = User.USERNAME_FIELD  # usually 'username' or 'email'

    def validate(self, attrs):
        # attrs contains validated fields; self.initial_data has the raw request payload
        # If username is not present, map common candidate fields to it.
        if 'username' not in attrs:
            for candidate in ('email', 'username_or_email', 'identifier', 'user'):
                if candidate in self.initial_data and self.initial_data.get(candidate):
                    attrs['username'] = self.initial_data.get(candidate)
                    break
        return super().validate(attrs)