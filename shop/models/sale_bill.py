# shop/models/sale_bill.py
from django.db import models
from core.core_models import Shop
from customers.models import Customer
from shop.models import Product


class SaleBill(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    bill_number = models.CharField(max_length=50, unique=True)
    bill_date = models.DateField()
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    additional_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_type = models.CharField(
        max_length=20,
        choices=[
            ('CASH', 'Cash'),
            ('ONLINE', 'Online'),
            ('UNPAID', 'Unpaid'),
        ]
    )
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance_due = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.bill_number


class SaleBillItem(models.Model):
    sale_bill = models.ForeignKey(SaleBill, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"