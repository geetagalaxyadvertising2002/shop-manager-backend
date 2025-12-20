from django.urls import path
from .views import SalesReportView, StockReportView

app_name = "reports"

urlpatterns = [
    path('sales/', SalesReportView.as_view(), name='sales_report'),
    path('stock/', StockReportView.as_view(), name='stock_report'),
]