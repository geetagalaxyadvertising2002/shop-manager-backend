from django.db import models
from django.utils import timezone
from core.core_models import Shop


# ===========================
#  CATEGORY MODEL
# ===========================
class Category(models.Model):
    name = models.CharField(max_length=100)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# ===========================
#  PRODUCT MODEL
# ===========================
class Product(models.Model):
    name = models.CharField(max_length=100)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    show_on_website = models.BooleanField(default=True)  # ← YE NAYA FIELD
    stock_quantity = models.PositiveIntegerField(default=0)
    barcode = models.CharField(max_length=50, blank=True, unique=True)
    image = models.ImageField(upload_to='products/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


# ===========================
#  SALE MODEL
# ===========================
class Sale(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    sale_date = models.DateField(default=timezone.now)
    invoiced = models.BooleanField(default=False)
    invoice = models.ForeignKey('Invoice', on_delete=models.SET_NULL, null=True, blank=True)

    def save(self, *args, **kwargs):
        # reduce stock when sale created first time
        if not self.pk:
            self.product.stock_quantity -= self.quantity
            self.product.save()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} ({self.quantity}) - ₹{self.total_amount}"


# ===========================
#  INVOICE MODEL
# ===========================
class Invoice(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    invoice_number = models.CharField(max_length=50, unique=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_online = models.BooleanField(default=False)
    customer_name = models.CharField(max_length=200, blank=True, null=True)
    customer_phone = models.CharField(max_length=30, blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    sales = models.ManyToManyField(Sale, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.invoice_number


# ===========================
#  INVOICE ITEM MODEL
# ===========================
class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} - {self.quantity}"


# ===========================
#  EXPENSE MODEL
# ===========================
class Expense(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=100, blank=True, null=True)
    date = models.DateField(default=timezone.now)
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - ₹{self.amount}"

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
    date = models.DateField(default=timezone.now)

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
