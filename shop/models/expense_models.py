from django.db import models
from django.utils import timezone
from core.core_models import Shop


# ✅ Ye function upar hona chahiye Expense class ke
def current_date():
    """Return only date (no time) for Expense default."""
    return timezone.now().date()


class Expense(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=100, blank=True, null=True)
    date = models.DateField(default=current_date)  # ✅ Ab ye callable function hai
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - ₹{self.amount}"