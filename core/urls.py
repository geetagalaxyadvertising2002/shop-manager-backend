# core/urls.py (UPDATED - OTP REMOVED)
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core.views import RegisterView, ProfileView, ShopCreateView, ShopViewSet, AdminUserListView, SendOTPView, VerifyOTPView
from core.settings_views.settings_views import BusinessSettingsViewSet
from rest_framework.authtoken.views import obtain_auth_token

# Router for core
router = DefaultRouter()
router.register(r'shops', ShopViewSet, basename='shop')
router.register(r'settings', BusinessSettingsViewSet, basename='settings')

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', obtain_auth_token, name='login'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('shop/create/', ShopCreateView.as_view(), name='create-shop'),
    path('admin/users/', AdminUserListView.as_view(), name='admin-users'),
    path('send-otp/', SendOTPView.as_view(), name='send-otp'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    
    # Core routes
    path('', include(router.urls)),

    # SHOP APP KE PRODUCTS
    path('shop/', include('shop.api.urls')),
]