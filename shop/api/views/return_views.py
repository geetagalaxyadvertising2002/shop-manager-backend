import logging, random
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action

from shop.models.purchase_models import PurchaseReturn, SaleReturn, Purchase
from shop.models import Product, Invoice, InvoiceItem
from shop.api.serializers.purchase_serializer import (
    PurchaseReturnSerializer,
    SaleReturnSerializer
)
from core.core_models import Shop

logger = logging.getLogger(__name__)


# ============================================================
# ✅ PURCHASE RETURN VIEWSET
# ============================================================
class PurchaseReturnViewSet(viewsets.ModelViewSet):
    """
    ✅ Handles purchase returns to supplier
    ✅ Stock decreases
    ✅ Return allowed only for items actually purchased
    """

    serializer_class = PurchaseReturnSerializer

    def get_queryset(self):
        try:
            shop = Shop.objects.filter(owner=self.request.user).first()
            if not shop:
                return PurchaseReturn.objects.none()

            return PurchaseReturn.objects.filter(
                purchase__shop=shop
            ).order_by("-created_at")

        except Exception as e:
            logger.error("Error fetching purchase returns", exc_info=True)
            return PurchaseReturn.objects.none()

    def create(self, request, *args, **kwargs):
        try:
            shop = Shop.objects.filter(owner=request.user).first()
            if not shop:
                return Response({"error": "Shop not found"}, status=404)

            data = request.data

            purchase_id = data.get("purchase_id")
            product_id = data.get("product_id")
            quantity = data.get("quantity")
            reason = data.get("reason", "")

            # ===================== VALIDATION =====================

            if not all([purchase_id, product_id, quantity]):
                return Response(
                    {"error": "purchase_id, product_id and quantity are required"},
                    status=400
                )

            try:
                quantity = int(quantity)
                if quantity <= 0:
                    return Response({"error": "Quantity must be greater than zero"}, status=400)
            except ValueError:
                return Response({"error": "Invalid quantity"}, status=400)

            # ===================== PURCHASE =====================

            purchase = Purchase.objects.filter(
                id=purchase_id,
                shop=shop
            ).first()

            if not purchase:
                return Response({"error": "Purchase not found"}, status=404)

            # ===================== CHECK PURCHASE ITEM =====================

            invoice_item = InvoiceItem.objects.filter(
                invoice=purchase.invoice,
                product_id=product_id
            ).select_related("product").first()

            if not invoice_item:
                return Response(
                    {"error": "This product was not part of this purchase"},
                    status=400
                )

            product = invoice_item.product

            # ===================== STOCK VALIDATION =====================

            if product.stock_quantity < quantity:
                return Response(
                    {
                        "error": f"Cannot return {quantity}. Only {product.stock_quantity} items in stock."
                    },
                    status=400
                )

            # ===================== UPDATE STOCK =====================

            product.stock_quantity -= quantity
            product.save()

            # ===================== CREATE RETURN RECORD =====================

            return_record = PurchaseReturn.objects.create(
                purchase=purchase,
                product=product,
                quantity=quantity,
                reason=reason
            )

            # ===================== CREATE RETURN INVOICE =====================

            invoice_number = f"PUR-RET-{random.randint(10000, 99999)}"
            total_amount = float(invoice_item.unit_price) * quantity

            invoice = Invoice.objects.create(
                shop=shop,
                invoice_number=invoice_number,
                total_amount=total_amount,
                is_online=False,
                customer_name=getattr(purchase.supplier, "name", "Unknown Supplier"),
                customer_phone=getattr(purchase.supplier, "phone_number", None),
                note=f"Purchase Return | {reason or 'No reason specified'}",
                created_at=timezone.now()
            )

            InvoiceItem.objects.create(
                invoice=invoice,
                product=product,
                quantity=quantity,
                unit_price=invoice_item.unit_price
            )

            # ===================== RESPONSE =====================

            return Response(
                {
                    "status": "success",
                    "message": "Purchase return created successfully",
                    "return": {
                        "id": return_record.id,
                        "purchase_id": purchase.id,
                        "product": product.name,
                        "quantity": quantity,
                        "total_amount": total_amount,
                        "invoice_number": invoice.invoice_number,
                    }
                },
                status=201
            )

        except Exception as e:
            logger.error("Purchase return error", exc_info=True)
            return Response({"error": str(e)}, status=500)


# ============================================================
# ✅ SALE RETURN VIEWSET
# ============================================================
class SaleReturnViewSet(viewsets.ModelViewSet):
    """
    ✅ Handles returns from customer (stock increases)
    """
    serializer_class = SaleReturnSerializer

    def get_queryset(self):
        """Return all sale returns for the logged-in user's shop"""
        try:
            shop = Shop.objects.filter(owner=self.request.user).first()
            if not shop:
                return SaleReturn.objects.none()
            return SaleReturn.objects.filter(
                sale__shop=shop
            ).order_by('-created_at')
        except Exception as e:
            logger.error(f"Error fetching sale returns: {str(e)}", exc_info=True)
            return SaleReturn.objects.none()

    def create(self, request, *args, **kwargs):
        """
        ✅ Create Sale Return
        ✅ Increase product stock
        ✅ Create return invoice
        """
        try:
            shop = Shop.objects.filter(owner=request.user).first()
            if not shop:
                return Response({"error": "Shop not found"}, status=404)

            data = request.data
            sale_id = data.get("sale")
            product_id = data.get("product_id")
            quantity = data.get("quantity")
            reason = data.get("reason", "")

            # ✅ Validation
            if not all([sale_id, product_id, quantity]):
                return Response({"error": "Missing required fields"}, status=400)

            try:
                quantity = int(quantity)
                if quantity <= 0:
                    return Response({"error": "Quantity must be positive"}, status=400)
            except ValueError:
                return Response({"error": "Invalid quantity"}, status=400)

            product = Product.objects.filter(id=product_id, shop=shop).first()
            if not product:
                return Response({"error": "Product not found"}, status=404)

            # ✅ Increase stock
            product.stock_quantity += quantity
            product.save()

            # ✅ Create return record
            sale_return = SaleReturn.objects.create(
                sale_id=sale_id,
                product=product,
                quantity=quantity,
                reason=reason
            )

            # ✅ Create Return Invoice
            invoice_number = f"SALE-RET-{random.randint(10000, 99999)}"
            total_amount = float(product.price) * quantity

            invoice = Invoice.objects.create(
                shop=shop,
                invoice_number=invoice_number,
                total_amount=total_amount,
                is_online=False,
                customer_name="Walk-in Customer",
                note=f"Sale Return | {reason or 'No reason specified'}",
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
                "return": {
                    "id": sale_return.id,
                    "invoice_number": invoice.invoice_number,
                    "product": product.name,
                    "quantity": quantity,
                    "total_amount": total_amount
                },
                "message": "Sale return created successfully and stock updated."
            }, status=201)

        except Exception as e:
            logger.error("Error creating sale return:", exc_info=True)
            return Response({"error": str(e)}, status=500)
