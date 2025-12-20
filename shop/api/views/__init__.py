from shop.models import Product, Category, Invoice, InvoiceItem
from shop.models.sale import Sale, PendingSale
from .views import CategoryViewSet, ProductViewSet, InvoiceViewSet
from .sale_views import SaleViewSet, PendingSaleViewSet