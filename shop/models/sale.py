from django.db import models
from core.core_models import Shop
from shop.models import Product
from customers.models import Customer, Khata, Transaction

class Sale(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_online = models.BooleanField(default=False)
    is_credit = models.BooleanField(default=False)  # True if sale is on credit (updates Khata)
    sale_date = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    customer_name = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"Sale: {self.product.name} - {self.quantity} units"

    def save(self, *args, **kwargs):
        # Calculate total_amount
        self.total_amount = self.quantity * self.unit_price
        super().save(*args, **kwargs)
        # Update product stock
        self.product.stock_quantity -= self.quantity
        self.product.save()
        # If credit sale, update customer's Khata
        if self.is_credit and self.customer:
            khata, _ = Khata.objects.get_or_create(customer=self.customer)
            Transaction.objects.create(
                khata=khata,
                amount=self.total_amount,
                is_credit=True,
                description=f"Credit sale: {self.quantity} units of {self.product.name}"
            )
            khata.total_due += self.total_amount
            khata.save()

class PendingSale(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_online = models.BooleanField(default=False)
    is_credit = models.BooleanField(default=False)  # True if scheduled sale is on credit
    scheduled_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=[
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('CANCELLED', 'Cancelled')
    ], default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Pending Sale: {self.product.name} - {self.quantity} units @ {self.scheduled_time}"