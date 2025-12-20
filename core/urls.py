# core/urls.py (UPDATED VERSION)
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core.views import RegisterView, ProfileView, ShopCreateView, ShopViewSet, AdminUserListView
from core.settings_views.settings_views import BusinessSettingsViewSet
from rest_framework.authtoken.views import obtain_auth_token
from core.otp_views import SendOTPView, VerifyOTPView

# Router for core
router = DefaultRouter()
router.register(r'shops', ShopViewSet, basename='shop')
router.register(r'settings', BusinessSettingsViewSet, basename='settings')

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', obtain_auth_token, name='login'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('shop/create/', ShopCreateView.as_view(), name='create-shop'),
    path('otp/send/', SendOTPView.as_view(), name='send-otp'),
    path('otp/verify/', VerifyOTPView.as_view(), name='verify-otp'),
    path('admin/users/', AdminUserListView.as_view(), name='admin-users'),
    # Core routes
    path('', include(router.urls)),

    # SHOP APP KE PRODUCTS KO YAHAN INCLUDE KARO
    path('shop/', include('shop.api.urls')),  # YE LINE ADD KARO
]