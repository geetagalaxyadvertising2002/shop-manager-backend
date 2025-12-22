# shop/api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views.views import ProductViewSet, CategoryViewSet, InvoiceViewSet, CashbookViewSet

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'cashbook', CashbookViewSet, basename='cashbook')

urlpatterns += [
    path(
        'sales/bills/by-bill-number/',
        SaleBillViewSet.as_view({'get': 'get_by_bill_number'}),
        name='sale-bill-by-number'
    ),
]