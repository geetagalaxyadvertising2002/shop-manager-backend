from django.urls import path
from shop.api.views.dashboard_views import DashboardSummaryView, TodaySalesHourlyView

urlpatterns = [
    path('summary/', DashboardSummaryView.as_view(), name='shop_dashboard'),
    path('sales/today/', TodaySalesHourlyView.as_view(), name='sales-today'),
]
