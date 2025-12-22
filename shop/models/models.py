from django.db import models
from core.core_models import Shop
from datetime import date
import uuid
from django.utils import timezone


# ===================== CATEGORY MODEL =====================
class Category(models.Model):
    name = models.CharField(max_length=100)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# ===================== PRODUCT MODEL =====================
class Product(models.Model):
    shop = models.ForeignKey('core.Shop', on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.IntegerField(default=0)

    barcode = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True
    )

    image_url = models.URLField(max_length=500, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    show_on_website = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # ✅ AUTO GENERATE BARCODE
        if not self.barcode:
            self.barcode = self.generate_unique_barcode()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_unique_barcode():
        while True:
            code = f"PRD-{uuid.uuid4().hex[:8].upper()}"
            if not Product.objects.filter(barcode=code).exists():
                return code



# ===================== INVOICE MODEL =====================
class Invoice(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    invoice_number = models.CharField(max_length=50, unique=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_online = models.BooleanField(default=False)

    # 🧾 Additional fields for offline purchases
    customer_name = models.CharField(max_length=100, blank=True, null=True)
    customer_phone = models.CharField(max_length=20, blank=True, null=True)
    note = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.invoice_number


# ===================== INVOICE ITEM MODEL =====================
class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} - {self.quantity}"

class CashbookEntry(models.Model):
    ENTRY_TYPES = (
        ('IN', 'Money In'),
        ('OUT', 'Money Out'),
    )

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    entry_type = models.CharField(max_length=3, choices=ENTRY_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    note = models.CharField(max_length=255, blank=True, null=True)
    is_online = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    date = models.DateField(default=date.today)

    def __str__(self):
        return f"{self.entry_type} ₹{self.amount} ({'Online' if self.is_online else 'Cash'})"

class OrderRecord(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
    ]

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    invoice = models.ForeignKey('Invoice', on_delete=models.CASCADE, related_name='orders')
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    customer_name = models.CharField(max_length=200, blank=True, null=True)
    customer_phone = models.CharField(max_length=30, blank=True, null=True)
    quantity = models.PositiveIntegerField(default=1)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.customer_name or 'Guest'} - {self.product.name} ({self.status})"
