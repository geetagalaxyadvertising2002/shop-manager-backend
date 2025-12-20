import logging
import csv
import random
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound
from shop.models import Product, Category, Invoice, InvoiceItem, CashbookEntry
from shop.api.serializers import ProductSerializer, InvoiceSerializer, CategorySerializer, CashbookEntrySerializer
from core.core_models import Shop
from shop.models.sale import Sale

logger = logging.getLogger(__name__)

def get_user_shop(user):
    if not user.is_authenticated:
        return None
    return Shop.objects.filter(owner=user).first()


# ===================== CATEGORY VIEWSET =====================
class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer

    def get_queryset(self):
        try:
            shop = Shop.objects.get(owner=self.request.user)
            logger.info(f"Found shop: {shop.name} for user: {self.request.user}")
            return Category.objects.filter(shop=shop)
        except Shop.DoesNotExist:
            logger.warning(f"No shop found for user: {self.request.user}")
            return Category.objects.none()

    def perform_create(self, serializer):
        try:
            shop = Shop.objects.get(owner=self.request.user)
            serializer.save(shop=shop)
            logger.info(f"Category created by user: {self.request.user}, shop: {shop.name}")
        except Shop.DoesNotExist:
            return Response(
                {"error": "No shop associated with this user. Please set up a shop first."},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating category: {e}", exc_info=True)
            return Response(
                {"error": f"Failed to create category: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ===================== PRODUCT VIEWSET =====================
class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        slug = self.request.query_params.get("slug")
        if slug:
            return Product.objects.filter(
                shop__slug=slug,
                shop__is_live=True,
                show_on_website=True
            ).order_by('-created_at')

        user = self.request.user
        shop = get_user_shop(user)
        if not shop:
            return Product.objects.none()

        return Product.objects.filter(shop=shop)

    def perform_create(self, serializer):
        user = self.request.user
        if not user.is_authenticated:
            raise PermissionDenied("Authentication required")

        shop = get_user_shop(user)
        if not shop:
            raise NotFound("Shop not found")

        category = serializer.validated_data.get('category')
        if not category:
            category, _ = Category.objects.get_or_create(
                name='General',
                shop=shop,
                defaults={'created_at': timezone.now()}
            )

        serializer.save(shop=shop, category=category)

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        threshold = request.query_params.get('threshold', '10')
        try:
            threshold_value = int(threshold)
            if threshold_value < 0:
                return Response({'error': 'Threshold must be a positive number'}, status=400)
        except ValueError:
            return Response({'error': 'Invalid threshold value'}, status=400)

        products = self.get_queryset().filter(stock_quantity__lte=threshold_value)
        serializer = self.get_serializer(products, many=True)
        logger.info(f"Fetched {len(products)} low stock products for user {self.request.user}")
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def barcode(self, request):
        barcode = request.query_params.get('barcode')
        if not barcode:
            return Response({'error': 'Barcode is required'}, status=400)
        try:
            shop = Shop.objects.filter(owner=request.user).first()
            if not shop:
                return Response({'error': 'Shop not found for this user'}, status=404)

            product = Product.objects.filter(barcode=barcode, shop_id=shop.id).first()
            if not product:
                return Response({'error': 'Product not found'}, status=404)

            serializer = self.get_serializer(product)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error fetching product by barcode: {e}", exc_info=True)
            return Response({'error': f'Failed to fetch product: {str(e)}'}, status=500)

    @action(detail=False, methods=['get'])
    def export_csv(self, request):
        products = self.get_queryset()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="products.csv"'
        writer = csv.writer(response)
        writer.writerow(['Name', 'Category', 'Price', 'Stock', 'Barcode'])
        for product in products:
            writer.writerow([
                product.name,
                product.category.name if product.category else '',
                product.price,
                product.stock_quantity,
                product.barcode
            ])
        return response

    @action(detail=False, methods=['post'])
    def import_csv(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'CSV file required'}, status=400)

        decoded = file.read().decode('utf-8').splitlines()
        reader = csv.DictReader(decoded)
        shop = Shop.objects.filter(owner=request.user).first()

        created = 0
        for row in reader:
            Product.objects.create(
                shop=shop,
                name=row.get('Name'),
                price=row.get('Price') or 0,
                stock_quantity=row.get('Stock') or 0,
                barcode=row.get('Barcode') or ""
            )
            created += 1

        return Response({"message": f"{created} products imported successfully."})

    @action(detail=False, methods=['post'], url_path='barcode-billing')
    def barcode_billing(self, request):
        try:
            barcode = request.data.get('barcode')
            quantity = int(request.data.get('quantity', 1))

            if not barcode:
                return Response({"error": "Barcode is required"}, status=400)

            product = self.get_queryset().filter(barcode=barcode).first()
            if not product:
                return Response({"error": "Product not found"}, status=404)

            shop = product.shop

            if product.stock_quantity < quantity:
                return Response({"error": f"Not enough stock for {product.name}"}, status=400)

            total_amount = float(product.price) * quantity
            invoice_number = f"INV-{random.randint(10000, 99999)}"

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
                sale_date=timezone.localtime(invoice.created_at),
            )

            product.stock_quantity -= quantity
            product.save()

            return Response({
                "status": "success",
                "invoice_number": invoice_number,
                "product": product.name,
                "quantity": quantity,
                "total_amount": total_amount,
                "message": "Product billed successfully!"
            }, status=201)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"error": f"Failed to bill product: {str(e)}"}, status=500)


# ===================== INVOICE VIEWSET =====================
class InvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        try:
            shop = Shop.objects.get(owner=self.request.user)
            return Invoice.objects.filter(shop=shop)
        except Shop.DoesNotExist:
            logger.warning(f"No shop found for {self.request.user}")
            return Invoice.objects.none()

    def perform_create(self, serializer):
        try:
            shop = Shop.objects.get(owner=self.request.user)
            serializer.save(shop=shop)
            logger.info(f"Invoice created for {shop.name} by {self.request.user}")
        except Shop.DoesNotExist:
            return Response(
                {"error": "No shop associated with this user."},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating invoice: {e}", exc_info=True)
            return Response(
                {"error": f"Failed to create invoice: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='history')
    def history(self, request):
        try:
            shop = Shop.objects.filter(owner=request.user).first()
            if not shop:
                return Response({"error": "Shop not found"}, status=404)

            invoices = Invoice.objects.filter(shop=shop).order_by('-created_at')

            data = []
            for inv in invoices:
                payment_type = "Online" if inv.is_online else "Cash"
                if hasattr(inv, "is_credit") and inv.is_credit:
                    payment_type = "Unpaid"
                elif inv.note and "UNPAID" in inv.note.upper():
                    payment_type = "Unpaid"

                items_data = []
                for item in inv.items.all():
                    items_data.append({
                        "product": item.product.name,
                        "quantity": item.quantity,
                        "unit_price": float(item.unit_price)
                    })

                data.append({
                    "invoice_number": inv.invoice_number,
                    "created_at": inv.created_at.strftime("%d-%m-%Y %I:%M %p"),
                    "total_amount": float(inv.total_amount),
                    "payment_type": payment_type,
                    "items": items_data
                })

            return Response({"history": data}, status=200)

        except Exception as e:
            return Response({"error": f"Failed to load invoice history: {str(e)}"}, status=500)


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
        serializer.save(shop=shop)

    @action(detail=False, methods=['get'])
    def report(self, request):
        shop = Shop.objects.filter(owner=request.user).first()
        if not shop:
            return Response({"error": "Shop not found"}, status=404)

        today = timezone.now().date()
        entries = CashbookEntry.objects.filter(shop=shop, date=today)
        serializer = self.get_serializer(entries, many=True)

        total_in = sum(e.amount for e in entries if e.entry_type == 'IN')
        total_out = sum(e.amount for e in entries if e.entry_type == 'OUT')

        return Response({
            "today": today.strftime("%d %b %Y"),
            "total_in": total_in,
            "total_out": total_out,
            "entries": serializer.data
        })

    @action(detail=False, methods=['get'])
    def balance(self, request):
        shop = Shop.objects.filter(owner=request.user).first()
        if not shop:
            return Response({"error": "Shop not found"}, status=404)

        cash_in = sum(e.amount for e in CashbookEntry.objects.filter(shop=shop, entry_type='IN', is_online=False))
        cash_out = sum(e.amount for e in CashbookEntry.objects.filter(shop=shop, entry_type='OUT', is_online=False))

        online_in = sum(e.amount for e in CashbookEntry.objects.filter(shop=shop, entry_type='IN', is_online=True))
        online_out = sum(e.amount for e in CashbookEntry.objects.filter(shop=shop, entry_type='OUT', is_online=True))

        return Response({
            "cash_in_hand": cash_in - cash_out,
            "online_balance": online_in - online_out
        })


# ===================== NEW: MY CURRENT SHOP ENDPOINT =====================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_current_shop(request):
    """
    Return the current shop details for the logged-in user.
    Used by Flutter app to show correct shop card even when no orders exist.
    Endpoint: GET /api/shops/my-shop/
    """
    shop = Shop.objects.filter(owner=request.user).first()
    if not shop:
        return Response({
            "shop_id": None,
            "error": "No shop found for this user. Please create a shop first."
        }, status=404)

    return Response({
        "shop_id": shop.id,
        "name": shop.name,
        "slug": shop.slug,
        "logo": shop.logo,
        "banner": shop.banner,
        "is_live": shop.is_live,
    })