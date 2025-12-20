# shop/api/views/sale_bill_views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from shop.models.sale_bill import SaleBill
from shop.models.sale import Sale  # ✅ Import Sale model
from shop.api.serializers.sale_bill_serializer import SaleBillSerializer


class SaleBillViewSet(viewsets.ModelViewSet):
    queryset = SaleBill.objects.all()
    serializer_class = SaleBillSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        shop = self.request.user.shop_set.first()
        if not shop:
            return SaleBill.objects.none()
        return SaleBill.objects.filter(shop=shop).order_by('-created_at')

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        SaleBill बनाते समय:
        - SaleBill + SaleBillItem क्रिएट होंगे
        - स्टॉक अपडेट serializer में हो रहा है
        - हर item के लिए Sale entry बनेगी → reports में online/offline सही दिखे
        """
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        shop = self.request.user.shop_set.first()
        if not shop:
            return Response({"error": "No shop found for this user"}, status=status.HTTP_400_BAD_REQUEST)

        # 🔧 FIXED: Case-insensitive + ज्यादा payment methods को ONLINE मानें
        payment_type_raw = request.data.get('payment_type', 'CASH').strip().upper()
        
        # Debug log (production में remove कर सकते हो)
        print(f"DEBUG SaleBill: payment_type_raw = '{payment_type_raw}'")

        # ONLINE माने जाने वाले payment types
        ONLINE_PAYMENT_TYPES = {'ONLINE', 'UPI', 'CARD', 'GPAY', 'PHONEPE', 'PAYTM', 'NETBANKING'}
        
        is_online = payment_type_raw in ONLINE_PAYMENT_TYPES
        is_credit = payment_type_raw == 'UNPAID'

        print(f"DEBUG SaleBill: is_online = {is_online}, is_credit = {is_credit}")  # Debug

        # SaleBill क्रिएट करें (shop serializer में pass हो रहा है)
        sale_bill = serializer.save(shop=shop)

        # हर SaleBillItem के लिए Sale entry बनाएँ
        for item in sale_bill.items.all():
            Sale.objects.create(
                shop=shop,
                product=item.product,
                quantity=item.quantity,
                unit_price=item.unit_price,
                total_amount=item.quantity * item.unit_price,
                is_online=is_online,           # ← अब सही value आएगी (ONLINE/UPI आदि पर True)
                is_credit=is_credit,
                customer=sale_bill.customer,
                sale_date=sale_bill.bill_date or timezone.now(),  # fallback if bill_date null
            )

        # Response
        response_data = serializer.data
        response_data['message'] = 'Sale bill created successfully'
        response_data['is_online'] = is_online  # frontend को भी बताएं (optional)
        
        if hasattr(sale_bill, 'bill_number'):
            response_data['bill_number'] = sale_bill.bill_number

        return Response(response_data, status=status.HTTP_201_CREATED)

    # ✅ SaleBill के आइटम्स लाने का endpoint (Sale Return के लिए)
    @action(detail=True, methods=['get'], url_path='items')
    def get_items(self, request, pk=None):
        """
        Return all products of this SaleBill (for Sale Return auto-selection)
        Example URL: /api/sales/bills/10/items/
        """
        try:
            bill = self.get_object()
        except Exception:
            return Response({"error": "Sale Bill not found"}, status=status.HTTP_404_NOT_FOUND)

        items = bill.items.all()

        data = [
            {
                "product_id": item.product.id,
                "product_name": item.product.name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "total": float(item.quantity * item.unit_price),
            }
            for item in items
        ]
        return Response(data, status=status.HTTP_200_OK)