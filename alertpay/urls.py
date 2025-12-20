from django.urls import path
from .views import (
    verify_upi_and_create_order,
    cashfree_webhook,
    my_alertpay_transactions
)

urlpatterns = [
    path("verify-upi/", verify_upi_and_create_order),
    path("webhook/", cashfree_webhook),
    path("transactions/", my_alertpay_transactions),
]
