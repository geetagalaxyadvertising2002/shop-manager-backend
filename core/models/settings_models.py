# core/models/settings_models.py
from django.db import models
from core.core_models import Shop as CoreShop  # careful: import main Shop
try:
    from django.contrib.postgres.fields import JSONField
except ImportError:
    from django.db.models import JSONField


# To avoid optional dependency on Postgres JSONField in older Django,
# we'll use models.JSONField (available in Django>=3.1)
from django.db.models import JSONField


# core/models/settings_models.py

class BusinessSettings(models.Model):
    shop = models.OneToOneField(CoreShop, on_delete=models.CASCADE, related_name='business_settings')
    theme = models.CharField(max_length=20, default='light')
    shop_logo = models.URLField(max_length=500, blank=True, null=True)
    business_name = models.CharField(max_length=100, blank=True, null=True)
    business_category = models.CharField(max_length=60, blank=True, null=True)
    business_type = models.CharField(max_length=60, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    gstin = models.CharField(max_length=20, blank=True, null=True)
    bank_account = models.CharField(max_length=50, blank=True, null=True)
    staff_count = models.PositiveIntegerField(default=0)
    map_lat = models.FloatField(blank=True, null=True)
    map_lng = models.FloatField(blank=True, null=True)
    staff_permissions = models.JSONField(default=dict, blank=True)
    free_business_card_banner = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Settings for {self.shop.name}"

