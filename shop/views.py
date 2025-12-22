import logging
import random

from django.db import transaction
from django.utils import timezone
from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from .models import (
    Product, Invoice, Category, Expense, InvoiceItem,
    CashbookEntry, OrderRecord
)
from .serializers import (
    ProductSerializer, InvoiceSerializer, CategorySerializer,
    ExpenseSerializer, InvoiceItemSerializer,
    CashbookEntrySerializer, OrderRecordSerializer
)
from core.core_models import Shop
from shop.models.sale import Sale

logger = logging.getLogger(__name__)


# ===================== MY CURRENT SHOP ENDPOINT =====================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_current_shop(request):
    """
    GET /api/shops/my-shop/
    Returns current shop details for the authenticated user.
    Used by Flutter app to display owner name, phone, logo etc. in Business Profile.
    """
    shop = Shop.objects.filter(owner=request.user).first()
    
    if not shop:
        return Response(
            {
                "shop_id": None,
                "error": "No shop found for this user. Please create a shop first."
            },
            status=status.HTTP_404_NOT_FOUND
        )

    return Response({
        "shop_id": shop.id,
        "name": shop.name,
        "slug": shop.slug,
        "address": shop.address or "",
        "description": shop.description or "",
        "logo": shop.logo if shop.logo else None,          # Fixed: no .url
        "banner": shop.banner if shop.banner else None,    # Fixed: no .url
        "is_live": shop.is_live,
        "owner_name": request.user.username,               # For Business Profile
        "owner_phone": request.user.phone_number or "",    # Registered Number
        "created_at": shop.created_at.isoformat(),
        "updated_at": shop.updated_at.isoformat(),
    })


# ===================== CATEGORY VIEWSET =====================
class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        shop = Shop.objects.filter(owner=self.request.user).first()
        if not shop:
            logger.warning(f"No shop found for user {self.request.user}")
            return Category.objects.none()
        return Category.objects.filter(shop=shop).order_by('-created_at')

    def perform_create(self, serializer):
        shop = Shop.objects.filter(owner=self.request.user).first()
        if not shop:
            raise ValueError("No shop associated with this user. Please set up a shop first.")
        serializer.save(shop=shop)
        logger.info(f"Category created for shop {shop.name} by {self.request.user}")


# ===================== INVOICE VIEWSET =====================
class InvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        shop = Shop.objects.filter(owner=self.request.user).first()
        if not shop:
            return Invoice.objects.none()
        return Invoice.objects.filter(shop=shop).order_by('-created_at')

    def perform_create(self, serializer):
        shop = Shop.objects.filter(owner=self.request.user).first()
        if not shop:
            raise ValueError("No shop associated with this user.")
        serializer.save(shop=shop)

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def offline_purchase(self, request):
        """Public endpoint for COD/offline form purchase from website"""
        data = request.data
        product_id = data.get('product_id')
        name = data.get('name', 'Guest')
        phone = data.get('phone')
        note = data.get('note', '')
        quantity = int(data.get('quantity', 1))

        if quantity <= 0:
            return Response({"error": "Quantity must be at least 1"}, status=400)
        if not phone:
            return Response({"error": "Phone number is required"}, status=400)

        try:
            product = Product.objects.select_related('shop').get(
                id=product_id,
                show_on_website=True,
                shop__is_live=True
            )
        except Product.DoesNotExist:
            return Response({"error": "Product not found or not available"}, status=404)

        if product.stock_quantity < quantity:
            return Response({"error": "Insufficient stock"}, status=400)

        shop = product.shop
        total_amount = product.price * quantity
        invoice_number = f"OFF-{random.randint(10000, 99999)}"

        try:
            with transaction.atomic():
                # 1. Create Invoice
                invoice = Invoice.objects.create(
                    shop=shop,
                    invoice_number=invoice_number,
                    total_amount=total_amount,
                    note=note,
                    customer_name=name,
                    customer_phone=phone,
                    is_online=False
                )

                # 2. Create Invoice Item
                InvoiceItem.objects.create(
                    invoice=invoice,
                    product=product,
                    quantity=quantity,
                    unit_price=product.price
                )

                # 3. Create Sale Record
                Sale.objects.create(
                    shop=shop,
                    product=product,
                    quantity=quantity,
                    unit_price=product.price,
                    total_amount=total_amount,
                    is_online=False,
                    sale_date=timezone.now()
                )

                # 4. Create OrderRecord (ONLY VALID FIELDS - NO product_name, NO note)
                OrderRecord.objects.create(
                    shop=shop,
                    invoice=invoice,
                    product=product,
                    customer_name=name,
                    customer_phone=phone,
                    quantity=quantity,
                    total_amount=total_amount,
                    status='PENDING'
                )

                # 5. Update Stock
                product.stock_quantity -= quantity
                product.save(update_fields=['stock_quantity'])

            return Response({
                "invoice_number": invoice_number,
                "total_amount": float(total_amount),
                "message": "Order placed successfully! Shop will contact you soon."
            }, status=201)

        except Exception as e:
            logger.error(f"Offline purchase failed: {e}", exc_info=True)
            return Response({"error": "Order failed. Please try again later."}, status=500)

    @action(detail=False, methods=['post'], url_path='barcode-billing')
    def barcode_billing(self, request):
        barcode = request.data.get('barcode')
        quantity = int(request.data.get('quantity', 1))

        if not barcode:
            return Response({"error": "Barcode is required"}, status=400)
        if quantity <= 0:
            return Response({"error": "Invalid quantity"}, status=400)

        user_shop = Shop.objects.filter(owner=request.user).first()
        product_qs = Product.objects.all()
        if user_shop:
            product_qs = product_qs.filter(shop=user_shop)

        product = product_qs.filter(barcode=barcode).first()
        if not product:
            return Response({"error": "Product not found"}, status=404)

        if product.stock_quantity < quantity:
            return Response({"error": "Not enough stock"}, status=400)

        shop = product.shop
        total_amount = product.price * quantity
        invoice_number = f"INV-{random.randint(10000, 99999)}"

        try:
            with transaction.atomic():
                invoice = Invoice.objects.create(
                    shop=shop,
                    invoice_number=invoice_number,
                    total_amount=total_amount,
                    is_online=False
                )

                InvoiceItem.objects.create(
                    invoice=invoice,
                    product=product,
                    quantity=quantity,
                    unit_price=product.price
                )

                Sale.objects.create(
                    shop=shop,
                    product=product,
                    quantity=quantity,
                    unit_price=product.price,
                    total_amount=total_amount,
                    is_online=False,
                    sale_date=timezone.now()
                )

                product.stock_quantity -= quantity
                product.save(update_fields=['stock_quantity'])

            return Response({
                "status": "success",
                "invoice_number": invoice_number,
                "product": product.name,
                "total_amount": float(total_amount)
            }, status=201)

        except Exception as e:
            logger.error(f"Barcode billing failed: {e}", exc_info=True)
            return Response({"error": "Billing failed"}, status=500)

    @action(detail=False, methods=['get'], url_path='history')
    def history(self, request):
        shop = Shop.objects.filter(owner=request.user).first()
        if not shop:
            return Response({"error": "Shop not found"}, status=404)

        invoices = Invoice.objects.filter(shop=shop).prefetch_related('items__product').order_by('-created_at')
        data = []

        for inv in invoices:
            payment_type = "Online" if inv.is_online else "Cash"
            if inv.note and "UNPAID" in inv.note.upper():
                payment_type = "Unpaid"

            items = [{
                "product": item.product.name,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price)
            } for item in inv.items.all()]

            data.append({
                "invoice_number": inv.invoice_number,
                "created_at": inv.created_at.strftime("%d-%m-%Y %I:%M %p"),
                "total_amount": float(inv.total_amount),
                "payment_type": payment_type,
                "items": items
            })

        return Response({"history": data})


# ===================== EXPENSE VIEWSET =====================
class ExpenseViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        shop = Shop.objects.filter(owner=self.request.user).first()
        if not shop:
            return Expense.objects.none()
        return Expense.objects.filter(shop=shop).order_by('-date')

    def perform_create(self, serializer):
        shop = Shop.objects.filter(owner=self.request.user).first()
        if not shop:
            raise ValueError("No shop found")
        serializer.save(shop=shop)


# ===================== CASHBOOK VIEWSET =====================
class CashbookViewSet(viewsets.ModelViewSet):
    serializer_class = CashbookEntrySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        shop = Shop.objects.filter(owner=self.request.user).first()
        if not shop:
            return CashbookEntry.objects.none()
        return CashbookEntry.objects.filter(shop=shop).order_by('-created_at')

    def perform_create(self, serializer):
        shop = Shop.objects.filter(owner=self.request.user).first()
        if shop:
            serializer.save(shop=shop)


# ===================== ORDER RECORD VIEWSET =====================
class OrderRecordViewSet(viewsets.ModelViewSet):
    serializer_class = OrderRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        shop = Shop.objects.filter(owner=self.request.user).first()
        if not shop:
            return OrderRecord.objects.none()
        return OrderRecord.objects.filter(shop=shop).order_by('-created_at')

    @action(detail=False, methods=['get'])
    def summary(self, request):
        shop = Shop.objects.filter(owner=request.user).first()
        if not shop:
            return Response({"error": "Shop not found"}, status=404)

        pending_count = OrderRecord.objects.filter(shop=shop, status='PENDING').count()
        completed_count = OrderRecord.objects.filter(shop=shop, status='COMPLETED').count()

        return Response({
            "new_orders": pending_count,
            "pending_orders": pending_count,
            "completed_orders": completed_count
        })

    @action(detail=False, methods=['get'])
    def pending(self, request):
        shop = Shop.objects.filter(owner=request.user).first()
        if not shop:
            return Response([], status=200)
        orders = OrderRecord.objects.filter(shop=shop, status='PENDING').order_by('-created_at')
        return Response(OrderRecordSerializer(orders, many=True).data)

    @action(detail=False, methods=['get'])
    def completed(self, request):
        shop = Shop.objects.filter(owner=request.user).first()
        if not shop:
            return Response([], status=200)
        orders = OrderRecord.objects.filter(shop=shop, status='COMPLETED').order_by('-created_at')
        return Response(OrderRecordSerializer(orders, many=True).data)

    @action(detail=True, methods=['post'], url_path='mark_complete')
    def mark_complete(self, request, pk=None):
        try:
            order = self.get_queryset().get(pk=pk)
            order.status = 'COMPLETED'
            order.save(update_fields=['status'])
            return Response({"status": "Order marked as completed"})
        except OrderRecord.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)