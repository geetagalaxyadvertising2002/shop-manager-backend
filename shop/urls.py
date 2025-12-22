from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import InvoiceViewSet, ExpenseViewSet, CashbookViewSet, OrderRecordViewSet, my_current_shop
from .category_views import CategoryViewSet
from shop.api.urls import sale_urls  # ✅ import here instead of include()
from shop.api.views.sale_bill_views import SaleBillViewSet
from shop.api.views import ProductViewSet
from shop.api.views.return_views import PurchaseReturnViewSet, SaleReturnViewSet

router = DefaultRouter()

router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'expenses', ExpenseViewSet, basename='expense')
router.register(r'cashbook', CashbookViewSet, basename='cashbook')
router.register(r'sales/bills', SaleBillViewSet, basename='sale-bill')
router.register(r'orders', OrderRecordViewSet, basename='order-record')
router.register(r'products', ProductViewSet, basename='product')

# ===================== RETURN ROUTES =====================
router.register(r'purchases/returns', PurchaseReturnViewSet, basename='purchase-return')
router.register(r'sales/returns', SaleReturnViewSet, basename='sale-return')

urlpatterns = [
    path('', include(router.urls)),
    *sale_urls.urlpatterns,  # ✅ unpack sale endpoints

    # ✅ यहाँ नया endpoint add करो
    path('shops/my-shop/', my_current_shop, name='my-shop'),
]
