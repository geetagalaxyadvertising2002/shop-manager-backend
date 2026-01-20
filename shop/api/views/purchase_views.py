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
                logger.warning(f"No shop found for {self.request.user}")
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
                logger.warning("No items provided in purchase creation")
                return Response({"error": "No items provided. 'items' array is required and cannot be empty."}, status=400)

            note = data.get("note", "")
            payment_type = data.get("payment_type", "Cash")

            supplier = Customer.objects.filter(id=supplier_id).first() if supplier_id else None

            # Calculate total & validate items
            total_amount = 0.0
            validated_items = []

            for idx, item in enumerate(items, 1):
                try:
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
                            "error": f"Product {product_id} not found in shop"
                        }, status=404)

                    qty = int(quantity)
                    price = float(unit_price)

                    if qty <= 0:
                        return Response({"error": f"Quantity must be positive (item #{idx})"}, status=400)

                    subtotal = qty * price
                    total_amount += subtotal

                    validated_items.append({
                        "product": product,
                        "quantity": qty,
                        "unit_price": price
                    })

                except (ValueError, TypeError) as e:
                    logger.error(f"Invalid data in item #{idx}: {item} → {str(e)}")
                    return Response({
                        "error": f"Invalid quantity or unit_price in item #{idx}"
                    }, status=400)

            if not validated_items:
                return Response({"error": "No valid items after validation"}, status=400)

            # Create Purchase
            invoice_number = f"PUR-{random.randint(10000, 99999)}"
            purchase = Purchase.objects.create(
                shop=shop,
                supplier=supplier,
                invoice_number=invoice_number,
                total_amount=total_amount,
                payment_type=payment_type,
                note=note,
                received=True
            )

            # Create Invoice
            invoice = Invoice.objects.create(
                shop=shop,
                invoice_number=invoice_number,
                total_amount=total_amount,
                is_online=payment_type.lower() == "online",
                customer_name=getattr(supplier, "name", "Unknown Supplier"),
                customer_phone=getattr(supplier, "phone_number", None),
                note=f"Purchase via {payment_type}",
                created_at=timezone.now()
            )

            # Create Invoice Items + Update stock
            created_items_count = 0
            for vi in validated_items:
                InvoiceItem.objects.create(
                    invoice=invoice,
                    product=vi["product"],
                    quantity=vi["quantity"],
                    unit_price=vi["unit_price"]
                )
                vi["product"].stock_quantity += vi["quantity"]
                vi["product"].save()
                created_items_count += 1

            logger.info(f"Purchase {purchase.id} created with {created_items_count} items")

            return Response({
                "status": "success",
                "purchase": {
                    "id": purchase.id,
                    "invoice_number": purchase.invoice_number,
                    "total_amount": purchase.total_amount,
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
            purchases = Purchase.objects.filter(shop=shop, created_at__date=today)

            total_purchases = sum(p.total_amount for p in purchases)
            count = purchases.count()

            return Response({
                "date": today.strftime("%d %b %Y"),
                "total_purchases": total_amount,
                "purchase_count": count
            })
        except Exception as e:
            logger.error("Failed to get purchase summary", exc_info=True)
            return Response({"error": str(e)}, status=500)

    @action(detail=True, methods=['get'], url_path='items')
    def items(self, request, pk=None):
        try:
            purchase = self.get_object()

            invoice_items = InvoiceItem.objects.filter(
                invoice__invoice_number=purchase.invoice_number
            ).select_related('product')

            serializer = InvoiceItemSerializer(invoice_items, many=True)

            return Response({
                "items": serializer.data,
                "purchase_id": purchase.id,
                "invoice_number": purchase.invoice_number,
                "total_items": invoice_items.count(),
                "message": "Items fetched successfully" if invoice_items.exists() else "No items found for this purchase"
            })

        except Purchase.DoesNotExist:
            return Response({"error": "Purchase not found"}, status=404)
        except Exception as e:
            logger.error(f"Error fetching purchase items: {str(e)}", exc_info=True)
            return Response({"error": "Failed to load purchase items"}, status=500)