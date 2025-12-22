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

    @action(detail=False, methods=['get'], url_path='by-bill-number')
    def get_by_bill_number(self, request):
        """
        New Endpoint: GET /api/sales/bills/by-bill-number/?bill_number=BILL-123
        Returns full SaleBill details including nested customer if exists
        """
        bill_number = request.query_params.get('bill_number')
        if not bill_number:
            return Response(
                {"error": "bill_number parameter is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            bill = SaleBill.objects.select_related('customer').get(
                shop=request.user.shop_set.first(),
                bill_number=bill_number
            )
        except SaleBill.DoesNotExist:
            return Response(
                {"error": "Sale bill not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.get_serializer(bill)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        shop = self.request.user.shop_set.first()
        if not shop:
            return Response(
                {"error": "No shop found for this user"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Payment type logic
        payment_type_raw = request.data.get('payment_type', 'CASH').strip().upper()
        ONLINE_PAYMENT_TYPES = {
            'ONLINE', 'UPI', 'CARD', 'GPAY', 'PHONEPE', 'PAYTM', 'NETBANKING'
        }
        is_online = payment_type_raw in ONLINE_PAYMENT_TYPES
        is_credit = payment_type_raw == 'UNPAID'

        # 🔥 यहाँ fix है — serializer को shop pass करो
        serializer.validated_data['shop'] = shop

        # 🔥 अब save करो — serializer का create() method चलेगा और customer assign होगा
        sale_bill = serializer.save()

        # Stock check & Sale entries
        for item in sale_bill.items.all():
            product = item.product

            if product.stock_quantity < item.quantity:
                raise Exception(f"Insufficient stock for {product.name}")

            # Optional: stock deduct यहाँ करो अगर model में auto नहीं होता
            # product.stock_quantity -= item.quantity
            # product.save()

            Sale.objects.create(
                shop=shop,
                product=product,
                quantity=item.quantity,
                unit_price=item.unit_price,
                total_amount=item.quantity * item.unit_price,
                is_online=is_online,
                is_credit=is_credit,
                customer=sale_bill.customer,  # अब यह None नहीं होगा
                sale_date=sale_bill.bill_date or timezone.now(),
            )

        # Response
        response_data = serializer.data
        response_data['message'] = 'Sale bill created successfully'
        response_data['is_online'] = is_online

        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='items')
    def get_items(self, request, pk=None):
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
                "unit_price": float(item.unit_price),
                "total": float(item.quantity * item.unit_price),
            }
            for item in items
        ]
        return Response(data, status=status.HTTP_200_OK)