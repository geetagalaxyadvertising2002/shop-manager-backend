# shop/api/views/sale_views.py

import logging
import random
import io
import qrcode
from datetime import datetime
from django.utils import timezone
from django.http import FileResponse
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
    Handles Sale creation, stock update, invoice generation,
    and digital perchi (QR, PDF share).
    """
    serializer_class = SaleSerializer

    def get_queryset(self):
        """Fetch all sales for the logged-in user's shop"""
        try:
            shop = Shop.objects.filter(owner=self.request.user).first()
            if not shop:
                logger.warning(f"No shop found for user: {self.request.user}")
                return Sale.objects.none()
            return Sale.objects.filter(shop=shop).order_by('-sale_date')
        except Exception as e:
            logger.error(f"Error fetching sales: {str(e)}", exc_info=True)
            return Sale.objects.none()

    def create(self, request, *args, **kwargs):
        """
        ✅ Create Sale + Auto Invoice + Stock Update
        ✅ Return invoice info for Flutter frontend (Digital Perchi)
        ✅ Now includes payment_type with case-insensitive handling
        """
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            shop = Shop.objects.filter(owner=request.user).first()

            if not shop:
                return Response(
                    {"error": "No shop associated with this user. Please set up a shop first."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # FIX: Case-insensitive & strip whitespace
            payment_type_raw = request.data.get("payment_type", "Cash")
            payment_type = str(payment_type_raw).strip().title()  # "online" → "Online", "ONLINE" → "Online"
            is_online = (payment_type == "Online")

            # Create Sale record
            sale = serializer.save(shop=shop, is_online=is_online)
            product = sale.product

            # Update product stock
            if product.stock_quantity >= sale.quantity:
                product.stock_quantity -= sale.quantity
                product.save()
            else:
                return Response({"error": f"Not enough stock available for {product.name}"}, status=400)

            sale.sale_date = timezone.make_aware(datetime.now(), timezone.get_current_timezone())
            sale.save()

            invoice_number = f"INV-{random.randint(10000, 99999)}"
            invoice = Invoice.objects.create(
                shop=shop,
                invoice_number=invoice_number,
                total_amount=sale.total_amount,
                is_online=is_online,
                customer_name=getattr(sale.customer, "name", "Walk-in Customer"),
                customer_phone=getattr(sale.customer, "phone_number", None),
                note=f"Payment Type: {payment_type}",
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
            }, status=201)

        except Exception as e:
            logger.error("Error creating sale:", exc_info=True)
            return Response({"error": str(e)}, status=500)

    @action(detail=False, methods=['post'], url_path='quick-sale')
    def quick_sale(self, request):
        """
        ✅ Quick Sale — Auto Payment Type = Cash
        """
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

            sale = Sale.objects.create(
                shop=shop,
                product=product,
                quantity=quantity,
                unit_price=product.price,
                total_amount=total_amount,
                is_online=False  # Quick sale always cash/offline
            )
            product.stock_quantity -= quantity
            product.save()

            invoice_number = f"INV-{random.randint(10000, 99999)}"
            invoice = Invoice.objects.create(
                shop=shop,
                invoice_number=invoice_number,
                total_amount=total_amount,
                is_online=False,
                customer_name="Walk-in Customer",
                note="Payment Type: Cash",
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
                "message": "Sale completed successfully!"
            }, status=201)

        except Exception as e:
            logger.error("Quick sale failed:", exc_info=True)
            return Response({"error": str(e)}, status=500)

    @action(detail=False, methods=['post'], url_path='bulk-sale')
    def bulk_sale(self, request):
        """
        ✅ Multi-product invoice + Stock Update
        ✅ Includes payment_type with case-insensitive handling
        """
        try:
            items = request.data.get('items', [])
            payment_type_raw = request.data.get("payment_type", "Cash")
            payment_type = str(payment_type_raw).strip().title()  # ← FIX: "ONLINE" → "Online"
            is_online = (payment_type == "Online")

            if not items:
                return Response({"error": "No items provided"}, status=400)

            total_amount = 0.0
            shop = None

            # Validate items and calculate total
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
                total_amount += float(product.price) * quantity

            # Create Invoice
            invoice_number = f"INV-{random.randint(10000, 99999)}"
            invoice = Invoice.objects.create(
                shop=shop,
                invoice_number=invoice_number,
                total_amount=total_amount,
                is_online=is_online,
                customer_name="Walk-in Customer",
                note=f"Payment Type: {payment_type}",
                created_at=timezone.now()
            )

            # Create Sale entries and update stock
            for item in items:
                product = Product.objects.get(id=item['product_id'])
                quantity = int(item['quantity'])

                Sale.objects.create(
                    shop=shop,
                    product=product,
                    quantity=quantity,
                    unit_price=product.price,
                    total_amount=float(product.price) * quantity,
                    is_online=is_online,  # ← अब सही से True होगा अगर ONLINE हो
                    is_credit=False,
                )

                InvoiceItem.objects.create(
                    invoice=invoice,
                    product=product,
                    quantity=quantity,
                    unit_price=product.price
                )

                product.stock_quantity -= quantity
                product.save()

            return Response({
                "status": "success",
                "invoice_number": invoice.invoice_number,
                "total_amount": total_amount,
                "message": "Invoice generated successfully!",
                "payment_type": payment_type
            })

        except Exception as e:
            logger.error("Bulk sale failed:", exc_info=True)
            return Response({"error": str(e)}, status=500)

    # बाकी actions unchanged (qr, share_invoice, summary)
    @action(detail=True, methods=['get'])
    def qr(self, request, pk=None):
        try:
            sale = self.get_object()
            qr_data = f"Invoice ID: {sale.id} | Amount: ₹{sale.total_amount} | Shop: {sale.shop.name}"
            qr_img = qrcode.make(qr_data)
            buffer = io.BytesIO()
            qr_img.save(buffer, format='PNG')
            buffer.seek(0)
            return FileResponse(buffer, content_type='image/png')
        except Exception:
            return Response({"error": "Failed"}, status=500)

    @action(detail=True, methods=['get'])
    def share_invoice(self, request, pk=None):
        try:
            sale = self.get_object()
            invoice = Invoice.objects.filter(shop=sale.shop, total_amount=sale.total_amount).first()
            buffer = io.BytesIO()
            p = canvas.Canvas(buffer)
            p.drawString(100, 780, f"Invoice: {invoice.invoice_number}")
            p.drawString(100, 760, f"Amount: ₹{sale.total_amount}")
            p.drawString(100, 740, f"Payment: {invoice.note}")
            p.showPage()
            p.save()
            buffer.seek(0)
            return FileResponse(buffer, as_attachment=True,
                                filename=f"Invoice_{invoice.invoice_number}.pdf")
        except Exception:
            return Response({"error": "Failed to create PDF"}, status=500)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        try:
            shop = Shop.objects.filter(owner=request.user).first()
            if not shop:
                return Response({"error": "Shop not found"}, status=404)
            today = timezone.now().date()
            sales = Sale.objects.filter(shop=shop, sale_date__date=today)
            return Response({
                "total_sales": sum([s.total_amount for s in sales]),
                "total_items": sum([s.quantity for s in sales]),
                "count": sales.count(),
            })
        except Exception:
            return Response({"error": "Failed"}, status=500)


# ===================== PENDING SALE VIEWSET =====================
class PendingSaleViewSet(viewsets.ModelViewSet):
    serializer_class = PendingSaleSerializer

    def get_queryset(self):
        shop = Shop.objects.filter(owner=self.request.user).first()
        if not shop:
            return PendingSale.objects.none()
        return PendingSale.objects.filter(shop=shop).order_by('-created_at')

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            shop = Shop.objects.filter(owner=request.user).first()
            pending_sale = serializer.save(shop=shop)
            return Response({
                "status": "success",
                "sale_id": pending_sale.id,
            }, status=201)
        except Exception as e:
            return Response({"error": str(e)}, status=500)