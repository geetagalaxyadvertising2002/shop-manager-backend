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
        """Return all purchases for the logged-in user's shop"""
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
        """
        Create Purchase → Increase product stock → Create Invoice + Invoice Items
        """
        try:
            shop = Shop.objects.filter(owner=request.user).first()
            if not shop:
                return Response(
                    {"error": "No shop associated with this user."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            data = request.data
            supplier_id = data.get("supplier_id")
            items = data.get("items", [])
            note = data.get("note", "")
            payment_type = data.get("payment_type", "Cash")

            if not items:
                return Response({"error": "No items provided"}, status=400)

            supplier = Customer.objects.filter(id=supplier_id).first() if supplier_id else None

            # Calculate total amount
            total_amount = 0.0
            for item in items:
                product = Product.objects.filter(id=item["product_id"], shop=shop).first()
                if not product:
                    return Response({"error": f"Product {item.get('product_id')} not found"}, status=404)
                total_amount += float(item["unit_price"]) * int(item["quantity"])

            # Create Purchase record
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

            # Create Invoice for record keeping
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

            # Process Items
            for item in items:
                product = Product.objects.filter(id=item["product_id"], shop=shop).first()
                quantity = int(item["quantity"])
                unit_price = float(item["unit_price"])

                # Increase stock
                product.stock_quantity += quantity
                product.save()

                # Create invoice item
                InvoiceItem.objects.create(
                    invoice=invoice,
                    product=product,
                    quantity=quantity,
                    unit_price=unit_price
                )

            logger.info(f"Purchase created successfully for shop {shop.name}")

            return Response({
                "status": "success",
                "purchase": {
                    "id": purchase.id,
                    "invoice_number": purchase.invoice_number,
                    "total_amount": purchase.total_amount,
                    "supplier": getattr(supplier, "name", None),
                    "created_at": purchase.created_at.strftime("%Y-%m-%d %H:%M"),
                    "payment_type": purchase.payment_type,
                },
                "message": "Purchase added successfully and stock updated."
            }, status=201)

        except Exception as e:
            logger.error("Error creating purchase", exc_info=True)
            return Response({"error": str(e)}, status=500)

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """Return daily purchase summary"""
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
                "total_purchases": total_purchases,
                "purchase_count": count
            })
        except Exception as e:
            logger.error("Failed to get purchase summary", exc_info=True)
            return Response({"error": str(e)}, status=500)

    @action(detail=True, methods=['get'], url_path='items')
    def items(self, request, pk=None):
        """
        Return list of items (products) in this purchase
        Endpoint: GET /api/purchases/<id>/items/
        """
        try:
            purchase = self.get_object()

            # Using invoice_number to match (because no direct FK from Invoice → Purchase)
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