from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.db import transaction
from django.utils import timezone

from shop.models.sale_bill import SaleBill
from shop.models.sale import Sale
from shop.api.serializers.sale_bill_serializer import SaleBillSerializer


class SaleBillViewSet(viewsets.ModelViewSet):
    serializer_class = SaleBillSerializer
    permission_classes = [IsAuthenticated]

    # -----------------------------------
    # Queryset (shop based)
    # -----------------------------------
    def get_queryset(self):
        shop = self.request.user.shop_set.first()
        if not shop:
            return SaleBill.objects.none()
        return SaleBill.objects.filter(shop=shop).order_by('-created_at')

    # -----------------------------------
    # GET bill by bill number
    # /api/sales/bills/by-bill-number/?bill_number=XXXX
    # -----------------------------------
    @action(detail=False, methods=['get'], url_path='by-bill-number')
    def get_by_bill_number(self, request):
        bill_number = request.query_params.get('bill_number', '').strip().rstrip('/')

        if not bill_number:
            return Response(
                {"error": "bill_number parameter is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        shop = request.user.shop_set.first()
        if not shop:
            return Response(
                {"error": "No shop found for this user"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            bill = SaleBill.objects.select_related('customer').get(
                shop=shop,
                bill_number=bill_number
            )
        except SaleBill.DoesNotExist:
            return Response(
                {"error": "Sale bill not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.get_serializer(bill)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # -----------------------------------
    # CREATE Sale Bill
    # -----------------------------------
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        shop = request.user.shop_set.first()
        if not shop:
            return Response(
                {"error": "No shop found for this user"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ----------------------------
        # Payment type logic
        # ----------------------------
        payment_type = request.data.get('payment_type', 'CASH').strip().upper()

        ONLINE_PAYMENT_TYPES = {
            'ONLINE', 'UPI', 'CARD', 'GPAY', 'PHONEPE', 'PAYTM', 'NETBANKING'
        }

        is_online = payment_type in ONLINE_PAYMENT_TYPES
        is_credit = payment_type == 'UNPAID'

        # ----------------------------
        # Save SaleBill
        # ----------------------------
        serializer.validated_data['shop'] = shop
        sale_bill = serializer.save()

        # ----------------------------
        # Create Sale entries (NO stock double deduction)
        # ----------------------------
        for item in sale_bill.items.all():
            product = item.product

            if product.stock_quantity < item.quantity:
                raise Exception(f"Insufficient stock for {product.name}")

            Sale.objects.create(
                shop=shop,
                product=product,
                quantity=item.quantity,
                unit_price=item.unit_price,
                total_amount=item.quantity * item.unit_price,
                is_online=is_online,
                is_credit=is_credit,
                customer=sale_bill.customer,
                sale_date=sale_bill.bill_date or timezone.now(),
            )

        response_data = serializer.data
        response_data['message'] = 'Sale bill created successfully'
        response_data['is_online'] = is_online

        return Response(response_data, status=status.HTTP_201_CREATED)

    # -----------------------------------
    # GET items of a sale bill
    # /api/sales/bills/{id}/items/
    # -----------------------------------
    @action(detail=True, methods=['get'], url_path='items')
    def get_items(self, request, pk=None):
        bill = self.get_object()

        data = [
            {
                "product_id": item.product.id,
                "product_name": item.product.name,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price),
                "total": float(item.quantity * item.unit_price),
            }
            for item in bill.items.all()
        ]

        return Response(data, status=status.HTTP_200_OK)
