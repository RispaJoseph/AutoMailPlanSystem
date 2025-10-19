# backend/mailplans/auth_views.py
import logging
import traceback
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.views import TokenObtainPairView

from .auth_serializers import FlexibleTokenObtainPairSerializer

logger = logging.getLogger(__name__)

class SafeTokenObtainPairView(TokenObtainPairView):
    """
    Safe wrapper around TokenObtainPairView that uses a flexible serializer
    and logs full tracebacks to server logs (so Render will capture them).
    """
    serializer_class = FlexibleTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("Exception in TokenObtainPairView: %s\n%s", exc, tb)
            return Response({
                "detail": "Internal server error during authentication.",
                "error": str(exc)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
