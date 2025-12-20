from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL


class AlertPayAccount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    upi_id = models.CharField(max_length=100)
    cashfree_customer_id = models.CharField(max_length=100)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.upi_id}"


class AlertPayTransaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    order_id = models.CharField(max_length=100, unique=True)
    cf_payment_id = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.order_id
