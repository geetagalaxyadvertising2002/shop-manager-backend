from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import CustomerViewSet, KhataViewSet

router = DefaultRouter()
router.register(r'', CustomerViewSet, basename='customer')
router.register(r'khatas', KhataViewSet, basename='khata')

urlpatterns = router.urls