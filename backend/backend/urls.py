# backend/backend/urls.py
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from mailplans.views import MailPlanViewSet
from mailplans.recipient_views import RecipientListView
from mailplans.auth_views import SafeTokenObtainPairView

# JWT token views
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

# DB health imports
from django.http import JsonResponse
from django.db import connections, OperationalError

# Router for main MailPlan endpoints
router = DefaultRouter()
router.register(r'mailplans', MailPlanViewSet, basename='mailplan')

# Simple health check endpoint to test DB connectivity
def health(request):
    try:
        c = connections['default']
        c.cursor()  # will raise OperationalError if DB can't be reached
        return JsonResponse({'status': 'ok'})
    except OperationalError as e:
        return JsonResponse({'status': 'error', 'detail': str(e)}, status=503)

urlpatterns = [
    path('admin/', admin.site.urls),

    # JWT authentication endpoints
    # path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/', SafeTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # MailPlan API endpoints
    path('api/', include(router.urls)),

    # Recipient list endpoint (with optional filters)
    path('api/recipients/', RecipientListView.as_view(), name='recipients-list'),

    # Health check (DB)
    path('healthz/', health),
]
