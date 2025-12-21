# shop/api/views/sale_views.py

import logging
import random
import io
from datetime import datetime
from django.utils import timezone
from django.http import FileResponse
from django.db import transaction
from reportlab.pdfgen import canvas
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from shop.models.sale import Sale, PendingSale
from shop.models import Product, Invoice, InvoiceItem
from core.core_models import Shop
from shop.api.serializers.sale_serializer import SaleSerializer, PendingSaleSerializer

logger = logging.getLogger(__name__)


# ===================== SALE VIEWSET =====================
class SaleViewSet(viewsets.ModelViewSet):
    """
    Handles:
    - Single product sale
    - Quick sale
    - Bulk (multi-product) sale
    - Invoice generation & PDF share
    - Stock update (सिर्फ एक ही जगह!)
    """
    serializer_class = SaleSerializer

    def get_queryset(self):
        """User के shop की sales ही दिखाएं"""
        try:
            shop = Shop.objects.filter(owner=self.request.user).first()
            if not shop:
                logger.warning(f"No shop found for user: {self.request.user}")
                return Sale.objects.none()
            return Sale.objects.filter(shop=shop).order_by('-sale_date')
        except Exception as e:
            logger.error(f"Error fetching sales: {str(e)}", exc_info=True)
            return Sale.objects.none()

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Single Product Sale
        - Stock deduction सिर्फ यहाँ
        - Invoice auto generate
        - Payment type case-insensitive
        """
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            shop = Shop.objects.filter(owner=request.user).first()
            if not shop:
                return Response(
                    {"error": "No shop associated with this user."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Case-insensitive payment type
            payment_type_raw = request.data.get("payment_type", "CASH").strip().upper()
            ONLINE_TYPES = {'ONLINE', 'UPI', 'CARD', 'GPAY', 'PHONEPE', 'PAYTM', 'NETBANKING'}
            is_online = payment_type_raw in ONLINE_TYPES

            # Create Sale (serializer handles shop assignment)
            sale = serializer.save(shop=shop, is_online=is_online)
            product = sale.product

            # SINGLE PLACE: Stock update
            if product.stock_quantity < sale.quantity:
                raise ValueError(f"Not enough stock for {product.name}")

            product.stock_quantity -= sale.quantity
            product.save()

            # Set sale date
            sale.sale_date = timezone.now()
            sale.save()

            # Generate Invoice
            invoice_number = f"INV-{random.randint(10000, 99999)}"
            invoice = Invoice.objects.create(
                shop=shop,
                invoice_number=invoice_number,
                total_amount=sale.total_amount,
                is_online=is_online,
                customer_name=getattr(sale.customer, "name", "Walk-in Customer"),
                customer_phone=getattr(sale.customer, "phone_number", None),
                note=f"Payment Type: {payment_type_raw}",
                created_at=timezone.now()
            )

            InvoiceItem.objects.create(
                invoice=invoice,
                product=product,
                quantity=sale.quantity,
                unit_price=sale.unit_price
            )

            return Response({
                "status": "success",
                "invoice": {
                    "id": invoice.id,
                    "invoice_number": invoice.invoice_number,
                    "product": product.name,
                    "quantity": sale.quantity,
                    "total_amount": float(sale.total_amount),
                    "invoice_date": invoice.created_at.strftime("%Y-%m-%d %H:%M"),
                },
                "message": "Sale completed successfully!"
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error("Error creating single sale:", exc_info=True)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='quick-sale')
    @transaction.atomic
    def quick_sale(self, request):
        """Quick Sale — हमेशा Cash (Offline)"""
        try:
            product_id = request.data.get('product_id')
            quantity = int(request.data.get('quantity', 1))

            if not product_id:
                return Response({"error": "Product ID is required"}, status=400)

            product = Product.objects.filter(id=product_id).first()
            if not product:
                return Response({"error": "Product not found"}, status=404)
            if product.stock_quantity < quantity:
                return Response({"error": "Not enough stock"}, status=400)

            shop = product.shop
            total_amount = float(product.price) * quantity

            # Create Sale
            sale = Sale.objects.create(
                shop=shop,
                product=product,
                quantity=quantity,
                unit_price=product.price,
                total_amount=total_amount,
                is_online=False,
                is_credit=False,
            )

            # SINGLE PLACE: Stock deduction
            product.stock_quantity -= quantity
            product.save()

            # Generate Invoice
            invoice_number = f"INV-{random.randint(10000, 99999)}"
            invoice = Invoice.objects.create(
                shop=shop,
                invoice_number=invoice_number,
                total_amount=total_amount,
                is_online=False,
                customer_name="Walk-in Customer",
                note="Payment Type: CASH",
                created_at=timezone.now()
            )

            InvoiceItem.objects.create(
                invoice=invoice,
                product=product,
                quantity=quantity,
                unit_price=product.price
            )

            return Response({
                "status": "success",
                "invoice_number": invoice.invoice_number,
                "total_amount": total_amount,
                "message": "Quick sale completed!"
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error("Quick sale failed:", exc_info=True)
            return Response({"error": str(e)}, status=500)

    @action(detail=False, methods=['post'], url_path='bulk-sale')
    @transaction.atomic
    def bulk_sale(self, request):
        """
        Multi-product Sale (Bulk)
        - Stock deduction सिर्फ एक जगह
        - Payment type case-insensitive
        - Full rollback on error
        """
        try:
            items = request.data.get('items', [])
            if not items:
                return Response({"error": "No items provided"}, status=400)

            payment_type_raw = request.data.get("payment_type", "CASH").strip().upper()
            ONLINE_TYPES = {'ONLINE', 'UPI', 'CARD', 'GPAY', 'PHONEPE', 'PAYTM', 'NETBANKING'}
            is_online = payment_type_raw in ONLINE_TYPES

            total_amount = 0.0
            shop = None
            products_to_update = []

            # First Pass: Validation + Calculate total
            for item in items:
                product_id = item.get('product_id')
                quantity = int(item.get('quantity', 1))
                product = Product.objects.filter(id=product_id).first()

                if not product:
                    return Response({"error": f"Product {product_id} not found"}, status=404)
                if product.stock_quantity < quantity:
                    return Response({"error": f"Not enough stock for {product.name}"}, status=400)

                if shop is None:
                    shop = product.shop
                elif shop != product.shop:
                    return Response({"error": "All products must belong to the same shop"}, status=400)

                total_amount += float(product.price) * quantity
                products_to_update.append((product, quantity))

            # Create Invoice
            invoice_number = f"INV-{random.randint(10000, 99999)}"
            invoice = Invoice.objects.create(
                shop=shop,
                invoice_number=invoice_number,
                total_amount=total_amount,
                is_online=is_online,
                customer_name="Walk-in Customer",
                note=f"Payment Type: {payment_type_raw}",
                created_at=timezone.now()
            )

            # Second Pass: Create Sales + Update Stock + Invoice Items
            for product, quantity in products_to_update:
                Sale.objects.create(
                    shop=shop,
                    product=product,
                    quantity=quantity,
                    unit_price=product.price,
                    total_amount=float(product.price) * quantity,
                    is_online=is_online,
                    is_credit=False,
                )

                InvoiceItem.objects.create(
                    invoice=invoice,
                    product=product,
                    quantity=quantity,
                    unit_price=product.price
                )

                # SINGLE PLACE: Stock deduction
                product.stock_quantity -= quantity
                product.save()

            return Response({
                "status": "success",
                "invoice_number": invoice.invoice_number,
                "total_amount": total_amount,
                "message": "Bulk sale completed successfully!",
                "payment_type": payment_type_raw
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error("Bulk sale failed:", exc_info=True)
            return Response({"error": str(e)}, status=500)

    @action(detail=True, methods=['get'])
    def share_invoice(self, request, pk=None):
        """PDF Invoice Download"""
        try:
            sale = self.get_object()
            invoice = Invoice.objects.filter(
                shop=sale.shop,
                total_amount=sale.total_amount
            ).first()

            if not invoice:
                return Response({"error": "Invoice not found"}, status=404)

            buffer = io.BytesIO()
            p = canvas.Canvas(buffer)
            p.drawString(100, 780, f"Invoice: {invoice.invoice_number}")
            p.drawString(100, 760, f"Amount: ₹{sale.total_amount}")
            p.drawString(100, 740, f"Payment: {invoice.note}")
            p.showPage()
            p.save()
            buffer.seek(0)

            return FileResponse(
                buffer,
                as_attachment=True,
                filename=f"Invoice_{invoice.invoice_number}.pdf"
            )
        except Exception as e:
            logger.error("PDF generation failed:", exc_info=True)
            return Response({"error": "Failed to create PDF"}, status=500)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Today की sales summary"""
        try:
            shop = Shop.objects.filter(owner=request.user).first()
            if not shop:
                return Response({"error": "Shop not found"}, status=404)

            today = timezone.now().date()
            sales = Sale.objects.filter(shop=shop, sale_date__date=today)

            return Response({
                "total_sales": sum(s.total_amount for s in sales),
                "total_items": sum(s.quantity for s in sales),
                "count": sales.count(),
            })
        except Exception as e:
            logger.error("Sale summary failed:", exc_info=True)
            return Response({"error": "Failed to fetch summary"}, status=500)


# ===================== PENDING SALE VIEWSET =====================
class PendingSaleViewSet(viewsets.ModelViewSet):
    serializer_class = PendingSaleSerializer

    def get_queryset(self):
        shop = Shop.objects.filter(owner=self.request.user).first()
        if not shop:
            return PendingSale.objects.none()
        return PendingSale.objects.filter(shop=shop).order_by('-created_at')

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Pending Sale (स्टॉक अभी नहीं कटेगा)"""
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            shop = Shop.objects.filter(owner=request.user).first()
            if not shop:
                return Response({"error": "No shop found"}, status=400)

            pending_sale = serializer.save(shop=shop)

            return Response({
                "status": "success",
                "sale_id": pending_sale.id,
                "message": "Pending sale created"
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error("Pending sale creation failed:", exc_info=True)
            return Response({"error": str(e)}, status=500)