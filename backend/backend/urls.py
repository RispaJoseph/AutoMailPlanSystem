# backend/backend/urls.py
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Router & API views
from mailplans.views import MailPlanViewSet
from mailplans.recipient_views import RecipientListView

# Use your custom serializer (already present at backend/mailplans/auth_serializers.py)
from mailplans.auth_serializers import FlexibleTokenObtainPairSerializer

# Simple JWT views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

# DRF utilities
from rest_framework.response import Response
from rest_framework import status

# DB health imports
from django.http import JsonResponse
from django.db import connections, OperationalError

# Router for main MailPlan endpoints
router = DefaultRouter()
router.register(r'mailplans', MailPlanViewSet, basename='mailplan')


def health(request):
    """
    Basic DB health check endpoint: attempts to open a cursor on the default DB.
    """
    try:
        c = connections['default']
        c.cursor()  # will raise OperationalError if DB can't be reached
        return JsonResponse({'status': 'ok'})
    except OperationalError as e:
        return JsonResponse({'status': 'error', 'detail': str(e)}, status=503)


# Define a token view inline using your FlexibleTokenObtainPairSerializer
class FlexibleTokenObtainPairView(TokenObtainPairView):
    """
    Inline view that uses FlexibleTokenObtainPairSerializer and maps common
    incoming keys (email, username, username_or_email, identifier) to the
    serializer's expected username field to avoid the 'username is required'
    ValidationError.
    """
    serializer_class = FlexibleTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        data = request.data.copy()  # make mutable copy
        username_field = self.serializer_class.username_field

        # If the expected username_field is not present, attempt to map common keys to it
        if username_field not in data or not data.get(username_field):
            for candidate in (username_field, 'username', 'email', 'username_or_email', 'identifier', 'user'):
                if candidate in data and data.get(candidate):
                    data[username_field] = data.get(candidate)
                    break

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


urlpatterns = [
    path('admin/', admin.site.urls),

    # MailPlan API endpoints
    path('api/', include(router.urls)),

    # Recipient list endpoint (with optional filters)
    path('api/recipients/', RecipientListView.as_view(), name='recipients-list'),

    # JWT authentication endpoints (using inline view above)
    path('api/token/', FlexibleTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Health check (DB)
    path('healthz/', health),
]
