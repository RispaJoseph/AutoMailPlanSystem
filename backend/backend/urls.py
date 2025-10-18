from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from mailplans.views import MailPlanViewSet
from mailplans.recipient_views import RecipientListView  # ⬅️ new import

# JWT token views
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

# Router for main MailPlan endpoints
router = DefaultRouter()
router.register(r'mailplans', MailPlanViewSet, basename='mailplan')

urlpatterns = [
    path('admin/', admin.site.urls),

    # JWT authentication endpoints
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # MailPlan API endpoints
    path('api/', include(router.urls)),

    # Recipient list endpoint (with optional filters)
    path('api/recipients/', RecipientListView.as_view(), name='recipients-list'),
]
