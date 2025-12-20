from django.db import models
from core.core_models import Shop

class Customer(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Khata(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    total_due = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Khata for {self.customer.name}"

class Transaction(models.Model):
    khata = models.ForeignKey(Khata, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_credit = models.BooleanField(default=True)  # True for credit, False for payment
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.amount} - {'Credit' if self.is_credit else 'Payment'}"