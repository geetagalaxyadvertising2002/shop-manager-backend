# shop_manager_backend/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import run_makemigrations, run_migrate

# Optional: keep alias import for reports (not required but clean)
from reports import urls as report_urls

urlpatterns = [
    # -------------------------
    # 🔐 Admin Panel
    # -------------------------
    path('admin/', admin.site.urls),

    # -------------------------
    # 🧠 Core (User, Auth, Shop)
    # -------------------------
    path('api/core/', include('core.urls')),
    path("api/system/makemigrations/", run_makemigrations),
    path("api/system/migrate/", run_migrate),

    # -------------------------
    # 👥 Customers / Parties
    # -------------------------
    path('api/customers/', include('customers.urls')),

    # -------------------------
    # 📊 Reports & Analytics
    # -------------------------
    path('api/reports/', include('reports.urls')),

    # -------------------------
    # 🏠 Dashboard (Home Analytics)
    # -------------------------
    path('api/dashboard/', include('shop.api.urls.dashboard_urls')), 
    path("api/alertpay/", include("alertpay.urls")), # ✅ Dashboard route

    # -------------------------
    # 🏪 Shop (Sales, Items, Purchases, Expenses, etc.)
    # -------------------------
    path('api/', include('shop.urls')),  # Keep at last — it has broad patterns
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)