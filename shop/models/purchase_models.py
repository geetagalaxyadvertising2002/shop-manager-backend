from django.db import models
from core.core_models import Shop
from customers.models import Customer  # supplier stored as Customer model (nullable)
from shop.models.sale import Sale  # For SaleReturn relation
from shop.models import Product  # For product reference


class Purchase(models.Model):
    """
    ✅ Main Purchase model for supplier bills / purchases
    """
    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name='purchases'
    )
    supplier = models.ForeignKey(
        Customer, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='supplier_purchases'
    )
    invoice_number = models.CharField(max_length=120, blank=True, null=True)
    total_amount = models.FloatField(default=0.0)
    note = models.TextField(blank=True, null=True)
    payment_type = models.CharField(max_length=20, default='CASH')
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    received = models.BooleanField(default=True)  # Mark if goods received

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Purchase'
        verbose_name_plural = 'Purchases'

    def __str__(self):
        return f"Purchase {self.invoice_number or self.id} - {self.shop.name}"


class PurchaseReturn(models.Model):
    """
    ✅ Records items returned to supplier (stock decreases)
    """
    purchase = models.ForeignKey(
        Purchase, on_delete=models.CASCADE, related_name='returns'
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='purchase_returns'
    )
    quantity = models.PositiveIntegerField()
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Purchase Return'
        verbose_name_plural = 'Purchase Returns'

    def __str__(self):
        return f"PurchaseReturn #{self.id} | Product: {self.product.name}"


class SaleReturn(models.Model):
    """
    ✅ Records items returned by customer (stock increases)
    """
    sale = models.ForeignKey(
        Sale, on_delete=models.CASCADE, related_name='returns'
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='sale_returns'
    )
    quantity = models.PositiveIntegerField()
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Sale Return'
        verbose_name_plural = 'Sale Returns'

    def __str__(self):
        return f"SaleReturn #{self.id} | Product: {self.product.name}"
