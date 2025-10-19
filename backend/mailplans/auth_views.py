# backend/mailplans/auth_views.py
import logging
import traceback
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)

class SafeTokenObtainPairView(TokenObtainPairView):
    """
    Wrap the SimpleJWT token obtain view so we log full traceback to server logs
    and return a JSON error instead of an HTML 500 page.
    """
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
