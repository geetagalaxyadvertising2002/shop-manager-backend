import logging
import random
from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, status, serializers
from rest_framework.response import Response
from rest_framework.decorators import action

from shop.models.purchase_models import Purchase
from shop.models import Product, Invoice, InvoiceItem
from core.core_models import Shop
from customers.models import Customer
from shop.api.serializers.purchase_serializer import PurchaseSerializer

logger = logging.getLogger(__name__)


# ============================================================
# INVOICE ITEM SERIALIZER
# ============================================================
class InvoiceItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_id = serializers.IntegerField(source="product.id", read_only=True)

    class Meta:
        model = InvoiceItem
        fields = [
            "id",
            "product_id",
            "product_name",
            "quantity",
            "unit_price",
        ]


# ============================================================
# PURCHASE VIEWSET
# ============================================================
class PurchaseViewSet(viewsets.ModelViewSet):
    """
    ✅ Purchase creation
    ✅ Invoice creation
    ✅ Stock increase
    ✅ Invoice always linked BEFORE items
    """

    serializer_class = PurchaseSerializer
    queryset = Purchase.objects.none()

    # --------------------------------------------------------
    # GET PURCHASE LIST
    # --------------------------------------------------------
    def get_queryset(self):
        shop = Shop.objects.filter(owner=self.request.user).first()
        if not shop:
            return Purchase.objects.none()

        return Purchase.objects.filter(shop=shop).order_by("-created_at")

    # --------------------------------------------------------
    # CREATE PURCHASE (FIXED)
    # --------------------------------------------------------
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        try:
            shop = Shop.objects.filter(owner=request.user).first()
            if not shop:
                return Response({"error": "Shop not found"}, status=400)

            data = request.data

            supplier_id = data.get("supplier_id")
            items = data.get("items", [])
            note = data.get("note", "")
            payment_type = data.get("payment_type", "CASH").upper()
            paid_amount = float(data.get("paid_amount", 0))

            if not items:
                return Response({"error": "Items list is required"}, status=400)

            supplier = None
            if supplier_id:
                supplier = Customer.objects.filter(id=supplier_id, shop=shop).first()
                if not supplier:
                    return Response({"error": "Invalid supplier"}, status=400)

            # ------------------------------------------------
            # VALIDATE ITEMS
            # ------------------------------------------------
            validated_items = []
            total_amount = 0

            for idx, item in enumerate(items, start=1):
                product_id = item.get("product_id")
                quantity = item.get("quantity")
                unit_price = item.get("unit_price")

                if not all([product_id, quantity, unit_price]):
                    return Response(
                        {"error": f"Item #{idx} missing fields"},
                        status=400
                    )

                product = Product.objects.filter(id=product_id, shop=shop).first()
                if not product:
                    return Response(
                        {"error": f"Product {product_id} not found"},
                        status=404
                    )

                qty = int(quantity)
                price = float(unit_price)

                if qty <= 0 or price < 0:
                    return Response(
                        {"error": f"Invalid quantity/price in item #{idx}"},
                        status=400
                    )

                subtotal = qty * price
                total_amount += subtotal

                validated_items.append({
                    "product": product,
                    "quantity": qty,
                    "unit_price": price
                })

            # ------------------------------------------------
            # CREATE INVOICE FIRST  ✅ MOST IMPORTANT
            # ------------------------------------------------
            invoice_number = f"PUR-{random.randint(100000, 999999)}"

            invoice = Invoice.objects.create(
                shop=shop,
                invoice_number=invoice_number,
                total_amount=total_amount,
                is_online=payment_type in ["UPI", "ONLINE", "CARD", "NETBANKING"],
                customer_name=getattr(supplier, "name", "Unknown Supplier"),
                customer_phone=getattr(supplier, "phone_number", None),
                note=f"Purchase | {note}".strip(),
                created_at=timezone.now(),
            )

            # ------------------------------------------------
            # CREATE PURCHASE WITH INVOICE LINKED
            # ------------------------------------------------
            purchase = Purchase.objects.create(
                shop=shop,
                supplier=supplier,
                invoice=invoice,          # 🔥 NEVER NULL
                invoice_number=invoice_number,
                total_amount=total_amount,
                payment_type=payment_type,
                paid_amount=paid_amount,
                note=note,
                received=True,
            )

            # ------------------------------------------------
            # CREATE ITEMS + UPDATE STOCK
            # ------------------------------------------------
            for item in validated_items:
                InvoiceItem.objects.create(
                    invoice=invoice,
                    product=item["product"],
                    quantity=item["quantity"],
                    unit_price=item["unit_price"]
                )

                item["product"].stock_quantity += item["quantity"]
                item["product"].save(update_fields=["stock_quantity"])

            logger.info(f"Purchase {purchase.id} created successfully")

            return Response({
                "status": "success",
                "purchase": {
                    "id": purchase.id,
                    "invoice_number": invoice_number,
                    "total_amount": float(total_amount),
                    "item_count": len(validated_items),
                    "payment_type": payment_type,
                },
                "message": "Purchase created successfully"
            }, status=201)

        except Exception as e:
            logger.exception("Purchase creation failed")
            return Response({"error": str(e)}, status=500)

    # --------------------------------------------------------
    # PURCHASE ITEMS API (RETURN SAFE)
    # --------------------------------------------------------
    @action(detail=True, methods=["get"], url_path="items")
    def items(self, request, pk=None):
        try:
            purchase = self.get_object()

            if not purchase.invoice:
                return Response({
                    "items": [],
                    "purchase_id": purchase.id,
                    "message": "Invoice not linked with this purchase"
                }, status=200)

            invoice_items = InvoiceItem.objects.filter(
                invoice=purchase.invoice
            ).select_related("product")

            serializer = InvoiceItemSerializer(invoice_items, many=True)

            return Response({
                "items": serializer.data,
                "purchase_id": purchase.id,
                "invoice_number": purchase.invoice_number,
                "total_items": invoice_items.count(),
                "message": "Items fetched successfully"
            })

        except Exception as e:
            logger.error("Failed to fetch purchase items", exc_info=True)
            return Response({"error": "Unable to fetch items"}, status=500)
