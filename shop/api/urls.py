# shop/api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views.views import ProductViewSet, CategoryViewSet, InvoiceViewSet, CashbookViewSet

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'cashbook', CashbookViewSet, basename='cashbook')

urlpatterns = [
    path('', include(router.urls)),
]