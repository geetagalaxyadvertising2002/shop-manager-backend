# core/views/settings_views.py

from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import Http404

from core.core_models import Shop
from core.models.settings_models import BusinessSettings


# ====================================
# SERIALIZER
# ====================================
class BusinessSettingsSerializer(serializers.ModelSerializer):
    shop_logo = serializers.URLField(allow_null=True, required=False)  # Explicitly define

    class Meta:
        model = BusinessSettings
        fields = [
            'id', 'shop', 'theme', 'shop_logo', 'business_name',
            'business_category', 'business_type', 'address', 'gstin',
            'bank_account', 'staff_count', 'map_lat', 'map_lng',
            'staff_permissions', 'free_business_card_banner'
        ]
        read_only_fields = ['shop', 'id']

# ====================================
# VIEWSET (ModelViewSet for PATCH/PUT support)
# ====================================
class BusinessSettingsViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    queryset = BusinessSettings.objects.all()
    serializer_class = BusinessSettingsSerializer

    # Custom object fetcher: always return the user's shop settings
    def get_object(self):
        shop = Shop.objects.filter(owner=self.request.user).first()
        if not shop:
            raise Http404("Shop not found for this user.")
        obj, created = BusinessSettings.objects.get_or_create(shop=shop)
        return obj

    # ===============================
    # GET METHOD
    # ===============================
    def list(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = BusinessSettingsSerializer(obj)
        return Response(serializer.data)

    # ===============================
    # PUT METHOD
    # ===============================
    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = BusinessSettingsSerializer(obj, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    # ===============================
    # PATCH METHOD
    # ===============================
    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = BusinessSettingsSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    # ===============================
    # LOGO UPLOAD
    # ===============================
    @action(detail=False, methods=['post'])
    def upload_logo(self, request):
        obj = self.get_object()

        file_obj = request.FILES.get('shop_logo')
        if not file_obj:
            return Response({"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        obj.shop_logo = file_obj
        obj.save()

        return Response({
            "status": "logo_uploaded",
            "shop_logo": obj.shop_logo.url if obj.shop_logo else None
        })

    # ===============================
    # BACKUP Placeholder
    # ===============================
    @action(detail=False, methods=['post'])
    def backup(self, request):
        return Response({
            "status": "backup_triggered",
            "message": "Backup task queued (implement Celery Task)."
        })
