import logging
import random
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import serializers

from shop.models.purchase_models import Purchase
from shop.models import Product, Invoice, InvoiceItem
from core.core_models import Shop
from customers.models import Customer
from shop.api.serializers.purchase_serializer import PurchaseSerializer

logger = logging.getLogger(__name__)


class InvoiceItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_id = serializers.IntegerField(source='product.id', read_only=True)

    class Meta:
        model = InvoiceItem
        fields = [
            'id',
            'product_id',
            'product_name',
            'quantity',
            'unit_price',
        ]


class PurchaseViewSet(viewsets.ModelViewSet):
    """
    Handles Purchase creation, stock update (increase), invoice generation.
    """
    serializer_class = PurchaseSerializer
    queryset = Purchase.objects.none()  # overridden in get_queryset

    def get_queryset(self):
        try:
            shop = Shop.objects.filter(owner=self.request.user).first()
            if not shop:
                logger.warning(f"No shop found for user {self.request.user}")
                return Purchase.objects.none()
            return Purchase.objects.filter(shop=shop).order_by('-created_at')
        except Exception as e:
            logger.error(f"Error fetching purchases: {str(e)}", exc_info=True)
            return Purchase.objects.none()

    def create(self, request, *args, **kwargs):
        try:
            shop = Shop.objects.filter(owner=request.user).first()
            if not shop:
                return Response({"error": "No shop associated with this user."}, status=400)

            data = request.data
            logger.info(f"Purchase create request data: {data}")

            supplier_id = data.get("supplier_id")
            items = data.get("items", [])

            if not items:
                return Response({"error": "No items provided. 'items' array is required."}, status=400)

            note = data.get("note", "")
            payment_type = data.get("payment_type", "Cash").strip()

            supplier = None
            if supplier_id:
                supplier = Customer.objects.filter(id=supplier_id, shop=shop).first()
                if not supplier:
                    return Response({"error": "Invalid supplier ID"}, status=400)

            # Validate and calculate total
            total_amount = 0.0
            validated_items = []

            for idx, item in enumerate(items, 1):
                product_id = item.get("product_id")
                quantity = item.get("quantity")
                unit_price = item.get("unit_price")

                if not all([product_id, quantity, unit_price]):
                    return Response({
                        "error": f"Item #{idx} missing required fields (product_id, quantity, unit_price)"
                    }, status=400)

                product = Product.objects.filter(id=product_id, shop=shop).first()
                if not product:
                    return Response({
                        "error": f"Product ID {product_id} not found in this shop"
                    }, status=404)

                try:
                    qty = int(quantity)
                    price = float(unit_price)
                except (ValueError, TypeError):
                    return Response({
                        "error": f"Invalid number format in item #{idx}"
                    }, status=400)

                if qty <= 0:
                    return Response({"error": f"Quantity must be positive (item #{idx})"}, status=400)
                if price < 0:
                    return Response({"error": f"Unit price cannot be negative (item #{idx})"}, status=400)

                subtotal = qty * price
                total_amount += subtotal

                validated_items.append({
                    "product": product,
                    "quantity": qty,
                    "unit_price": price
                })

            if not validated_items:
                return Response({"error": "No valid items after validation"}, status=400)

            # Generate unique invoice number
            invoice_number = f"PUR-{random.randint(100000, 999999)}"

            # Create Purchase record first (without invoice)
            purchase = Purchase.objects.create(
                shop=shop,
                supplier=supplier,
                invoice_number=invoice_number,
                total_amount=total_amount,
                payment_type=payment_type.upper(),
                note=note,
                received=True,
                paid_amount=float(data.get("paid_amount", 0)),
            )

            # Create Invoice
            invoice = Invoice.objects.create(
                shop=shop,
                invoice_number=invoice_number,
                total_amount=total_amount,
                is_online=payment_type.lower() in ["online", "upi", "card", "netbanking"],
                customer_name=getattr(supplier, "name", "Unknown Supplier"),
                customer_phone=getattr(supplier, "phone_number", None),
                note=f"Purchase via {payment_type} | {note}".strip(),
                created_at=timezone.now()
            )

            # IMPORTANT: Link invoice to purchase
            purchase.invoice = invoice
            purchase.save(update_fields=['invoice'])

            # Create Invoice Items & Update stock
            created_items_count = 0
            for vi in validated_items:
                InvoiceItem.objects.create(
                    invoice=invoice,
                    product=vi["product"],
                    quantity=vi["quantity"],
                    unit_price=vi["unit_price"]
                )
                vi["product"].stock_quantity += vi["quantity"]
                vi["product"].save(update_fields=['stock_quantity'])
                created_items_count += 1

            logger.info(f"Purchase #{purchase.id} created | Invoice: {invoice_number} | {created_items_count} items")

            return Response({
                "status": "success",
                "purchase": {
                    "id": purchase.id,
                    "invoice_number": invoice_number,
                    "total_amount": float(total_amount),
                    "supplier": getattr(supplier, "name", None),
                    "created_at": purchase.created_at.strftime("%Y-%m-%d %H:%M"),
                    "payment_type": purchase.payment_type,
                    "item_count": created_items_count
                },
                "message": "Purchase added successfully and stock updated."
            }, status=201)

        except Exception as e:
            logger.exception("Critical error during purchase creation")
            return Response({"error": str(e)}, status=500)

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        try:
            shop = Shop.objects.filter(owner=request.user).first()
            if not shop:
                return Response({"error": "Shop not found"}, status=404)

            today = timezone.now().date()
            purchases_today = Purchase.objects.filter(shop=shop, created_at__date=today)

            total_today = sum(float(p.total_amount) for p in purchases_today)
            count = purchases_today.count()

            return Response({
                "date": today.strftime("%d %b %Y"),
                "total_purchases": total_today,
                "purchase_count": count
            })
        except Exception as e:
            logger.error("Failed to get purchase summary", exc_info=True)
            return Response({"error": str(e)}, status=500)

    @action(detail=True, methods=['get'], url_path='items')
    def items(self, request, pk=None):
        try:
            purchase = self.get_object()

            if not purchase.invoice:
                logger.warning(f"Purchase #{purchase.id} has no linked invoice")
                return Response({
                    "items": [],
                    "purchase_id": purchase.id,
                    "invoice_number": purchase.invoice_number,
                    "total_items": 0,
                    "message": "No invoice linked to this purchase"
                }, status=200)

            invoice_items = InvoiceItem.objects.filter(
                invoice=purchase.invoice
            ).select_related('product')

            serializer = InvoiceItemSerializer(invoice_items, many=True)

            return Response({
                "items": serializer.data,
                "purchase_id": purchase.id,
                "invoice_number": purchase.invoice_number,
                "total_items": invoice_items.count(),
                "message": f"{invoice_items.count()} items fetched successfully"
                        if invoice_items.exists() else "No items found in this purchase"
            })

        except Purchase.DoesNotExist:
            return Response({"error": "Purchase not found"}, status=404)
        except Exception as e:
            logger.error(f"Error fetching purchase items: {str(e)}", exc_info=True)
            return Response({"error": "Failed to load purchase items"}, status=500)