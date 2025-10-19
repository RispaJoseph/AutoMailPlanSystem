# backend/mailplans/auth_serializers.py
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()

class FlexibleTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Accept either the model's USERNAME_FIELD (usually 'username') OR 'email'.
    If the model's USERNAME_FIELD is missing from the request but 'email' is provided,
    copy 'email' into the expected username field before validation. Also accept
    'username' if model uses 'email' as USERNAME_FIELD.
    """
    username_field = User.USERNAME_FIELD  # e.g. 'username' or 'email'

    def validate(self, attrs):
        # If the serializer expects e.g. 'email' but request sent 'username', copy
        if self.username_field not in attrs and 'username' in attrs:
            attrs[self.username_field] = attrs.get('username')

        # If the serializer expects e.g. 'username' but request sent 'email', copy
        if self.username_field not in attrs and 'email' in attrs:
            attrs[self.username_field] = attrs.get('email')

        return super().validate(attrs)
