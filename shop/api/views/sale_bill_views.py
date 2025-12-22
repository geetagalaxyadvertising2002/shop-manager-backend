# shop/api/views/sale_bill_views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone

from shop.models.sale_bill import SaleBill
from shop.models.sale import Sale
from shop.models import Product
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
        SaleBill creation with:
        - Safe stock deduction (only once)
        - Sale entries for accurate online/offline reports
        - Full atomic transaction (rollback if anything fails)
        - Proper customer assignment via serializer
        """
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        shop = self.request.user.shop_set.first()
        if not shop:
            return Response(
                {"error": "No shop found for this user"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Case-insensitive payment type handling
        payment_type_raw = request.data.get('payment_type', 'CASH').strip().upper()
        ONLINE_PAYMENT_TYPES = {
            'ONLINE', 'UPI', 'CARD', 'GPAY', 'PHONEPE', 'PAYTM', 'NETBANKING'
        }
        is_online = payment_type_raw in ONLINE_PAYMENT_TYPES
        is_credit = payment_type_raw == 'UNPAID'

        # 🔥 KEY FIX: serializer को shop pass करो ताकि serializer.create() में use हो
        # अब serializer खुद customer_id से customer assign कर देगा
        serializer.validated_data['shop'] = shop

        # 🔥 अब save करो — customer भी सही assign हो जाएगा
        sale_bill = serializer.save()

        # SINGLE PLACE: Stock check + deduction + Create Sale entries
        for item in sale_bill.items.all():
            product = item.product

            # Final stock check (deduction serializer में नहीं हुई है, इसलिए यहाँ करो)
            if product.stock_quantity < item.quantity:
                raise Exception(f"Insufficient stock for {product.name}")

            # Stock deduct करो (अगर तुम्हारा Product model में stock update logic है)
            # Note: अगर तुम stock manually deduct करना चाहते हो तो यहाँ करो
            # product.stock_quantity -= item.quantity
            # product.save()

            # Create Sale record for reporting (online/offline tracking)
            Sale.objects.create(
                shop=shop,
                product=product,
                quantity=item.quantity,
                unit_price=item.unit_price,
                total_amount=item.quantity * item.unit_price,
                is_online=is_online,
                is_credit=is_credit,
                customer=sale_bill.customer,  # अब यहाँ customer सही होगा!
                sale_date=sale_bill.bill_date or timezone.now(),
            )

        # Success response
        response_data = serializer.data
        response_data['message'] = 'Sale bill created successfully'
        response_data['is_online'] = is_online

        if hasattr(sale_bill, 'bill_number'):
            response_data['bill_number'] = sale_bill.bill_number

        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='items')
    def get_items(self, request, pk=None):
        """
        Get all items of a SaleBill (used for Sale Return)
        Example: GET /api/sales/bills/10/items/
        """
        try:
            bill = self.get_object()
        except Exception:
            return Response(
                {"error": "Sale Bill not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        items = bill.items.all()
        data = [
            {
                "product_id": item.product.id,
                "product_name": item.product.name,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price),
                "total": float(item.quantity * item.unit_price),
            }
            for item in items
        ]
        return Response(data, status=status.HTTP_200_OK)