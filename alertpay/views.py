import json
import uuid
import requests

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import AlertPayAccount, AlertPayTransaction
from .serializers import AlertPayTransactionSerializer


# ======================================================
# 🔹 1. VERIFY UPI + CREATE CASHFREE ORDER
# ======================================================
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_upi_and_create_order(request):
    """
    User UPI verify karega
    Cashfree order create hoga
    Flutter ko payment_session_id milega
    """

    upi_id = request.data.get("upi_id")

    if not upi_id:
        return Response(
            {"error": "UPI ID required"},
            status=400
        )

    order_id = f"order_{uuid.uuid4().hex[:12]}"

    headers = {
        "x-client-id": settings.CASHFREE_APP_ID,
        "x-client-secret": settings.CASHFREE_SECRET_KEY,
        "x-api-version": "2023-08-01",
        "Content-Type": "application/json"
    }

    payload = {
        "order_id": order_id,
        "order_amount": 1.00,  # ₹1 verification transaction
        "order_currency": "INR",
        "customer_details": {
            "customer_id": str(request.user.id),
            "customer_phone": "9999999999"  # demo, prod me real number
        },
        "order_meta": {
            "return_url": "https://example.com/payment-success"
        }
    }

    try:
        res = requests.post(
            "https://sandbox.cashfree.com/pg/orders",
            json=payload,
            headers=headers,
            timeout=10
        )
        data = res.json()
    except Exception as e:
        return Response(
            {"error": "Cashfree connection failed", "details": str(e)},
            status=500
        )

    if "payment_session_id" not in data:
        return Response(
            {"error": "Cashfree order failed", "data": data},
            status=400
        )

    # Save / Update user AlertPay account
    AlertPayAccount.objects.update_or_create(
        user=request.user,
        defaults={
            "upi_id": upi_id,
            "cashfree_customer_id": data.get("cf_order_id"),
            "verified": True
        }
    )

    return Response({
        "success": True,
        "order_id": order_id,
        "payment_session_id": data["payment_session_id"]
    })


# ======================================================
# 🔹 2. CASHFREE WEBHOOK (REAL PAYMENT ALERT)
# ======================================================
@csrf_exempt
def cashfree_webhook(request):
    """
    Cashfree yaha se payment success / failed notify karega
    """

    try:
        payload = json.loads(request.body)
    except Exception:
        return HttpResponse(status=400)

    event_type = payload.get("type")

    if event_type == "PAYMENT_SUCCESS":
        data = payload.get("data", {})

        order_data = data.get("order", {})
        payment_data = data.get("payment", {})
        customer_data = data.get("customer_details", {})

        user_id = customer_data.get("customer_id")

        if not user_id:
            return HttpResponse(status=200)

        AlertPayTransaction.objects.get_or_create(
            order_id=order_data.get("order_id"),
            defaults={
                "user_id": user_id,
                "cf_payment_id": payment_data.get("cf_payment_id"),
                "amount": payment_data.get("payment_amount", 0),
                "status": "SUCCESS"
            }
        )

        # 🔔 YAHAN FCM / SOCKET / PUSH NOTIFICATION TRIGGER HOGA

    return HttpResponse(status=200)


# ======================================================
# 🔹 3. USER TRANSACTION LIST API (FLUTTER SCREEN)
# ======================================================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_alertpay_transactions(request):
    """
    User apne saare incoming payments dekhega
    """

    qs = AlertPayTransaction.objects.filter(
        user=request.user
    ).order_by('-created_at')

    serializer = AlertPayTransactionSerializer(qs, many=True)

    return Response({
        "success": True,
        "transactions": serializer.data
    })
