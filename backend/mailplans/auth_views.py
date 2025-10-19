# backend/mailplans/auth_views.py
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.response import Response
from rest_framework import status
# import only serializers from same app
from .serializers import SafeTokenObtainPairSerializer

class SafeTokenObtainPairView(TokenObtainPairView):
    serializer_class = SafeTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        data = request.data.copy()
        if 'username' not in data:
            for candidate in ('email', 'username_or_email', 'identifier', 'user'):
                if candidate in data and data.get(candidate):
                    data['username'] = data.get(candidate)
                    break
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)
