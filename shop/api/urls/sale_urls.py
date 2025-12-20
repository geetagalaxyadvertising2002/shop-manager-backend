# shop/urls.py
from rest_framework.routers import DefaultRouter

# ==== Import Sale-related Views ====
from shop.api.views.sale_views import SaleViewSet, PendingSaleViewSet
from shop.api.views.sale_bill_views import SaleBillViewSet

# ==== Import Purchase-related Views ====
from shop.api.views.purchase_views import PurchaseViewSet
from shop.api.views.return_views import PurchaseReturnViewSet, SaleReturnViewSet

# Create Default Router
router = DefaultRouter()

# ===================== SALES ROUTES =====================
router.register(r'sales', SaleViewSet, basename='sale')
router.register(r'pending-sales', PendingSaleViewSet, basename='pending-sale')
router.register(r'sales/bills', SaleBillViewSet, basename='sale-bill')

# ===================== PURCHASE ROUTES =====================
router.register(r'purchases', PurchaseViewSet, basename='purchase')

# ===================== RETURN ROUTES =====================
router.register(r'purchases/returns', PurchaseReturnViewSet, basename='purchase-return')
router.register(r'sales/returns', SaleReturnViewSet, basename='sale-return')

# Final URL patterns
urlpatterns = router.urls
