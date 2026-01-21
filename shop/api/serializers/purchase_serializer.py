from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone

from shop.models import Product, Invoice, InvoiceItem
from shop.models.purchase_models import Purchase, PurchaseReturn, SaleReturn
from customers.models import Customer


# ===================== PRODUCT BASIC SERIALIZER =====================
class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'stock_quantity']


# ===================== SUPPLIER (CUSTOMER) SERIALIZER =====================
class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'name', 'phone_number']


# ===================== PURCHASE SERIALIZER =====================
class PurchaseSerializer(serializers.ModelSerializer):
    supplier = SupplierSerializer(read_only=True)
    supplier_id = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(),
        source='supplier',
        write_only=True,
        required=False
    )

    class Meta:
        model = Purchase
        fields = [
            'id',
            'shop',
            'supplier',
            'invoice_id',
            'supplier_id',
            'invoice_number',
            'total_amount',
            'note',
            'created_at',
            'received',
            'payment_type',
        ]
        read_only_fields = ['id', 'invoice_number', 'created_at']


# ===================== PURCHASE RETURN SERIALIZER (for create/update/retrieve) =====================
class PurchaseReturnSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )

    purchase_id = serializers.PrimaryKeyRelatedField(
        queryset=Purchase.objects.all(),
        source='purchase',
        write_only=True
    )

    class Meta:
        model = PurchaseReturn
        fields = [
            'id',
            'purchase',
            'purchase_id',
            'product',
            'product_id',
            'quantity',
            'reason',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


# ===================== PURCHASE RETURN LIST SERIALIZER (for list view - billing/history) =====================
class PurchaseReturnListSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_price = serializers.DecimalField(
        source='product.price',
        max_digits=12,
        decimal_places=2,
        read_only=True
    )
    
    # From the original purchase
    purchase_invoice_number = serializers.CharField(
        source='purchase.invoice_number',
        read_only=True,
        allow_null=True
    )
    
    # Return-specific invoice (the one created in view)
    return_invoice_number = serializers.SerializerMethodField()
    
    # Final amount shown in billing/history
    total_amount = serializers.SerializerMethodField()
    
    # Make billing screen happy
    payment_type = serializers.SerializerMethodField()
    paid_amount = serializers.SerializerMethodField()
    
    supplier_name = serializers.CharField(
        source='purchase.supplier.name',
        read_only=True,
        allow_null=True,
        default='Unknown Supplier'
    )
    
    created_at_formatted = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseReturn
        fields = [
            'id',
            'purchase',
            'purchase_invoice_number',
            'return_invoice_number',
            'product',
            'product_name',
            'product_price',
            'quantity',
            'reason',
            'total_amount',
            'payment_type',
            'paid_amount',
            'supplier_name',
            'created_at',
            'created_at_formatted',
        ]

    def get_return_invoice_number(self, obj):
        invoice = Invoice.objects.filter(
            note__startswith='Purchase Return',
            total_amount__gt=0,
            created_at__gte=obj.created_at - timezone.timedelta(minutes=10),
            created_at__lte=obj.created_at + timezone.timedelta(minutes=10),
        ).order_by('-created_at').first()
        
        return invoice.invoice_number if invoice else f"RET-{obj.id:06d}"

    def get_total_amount(self, obj):
        # 1. Prefer the actual return invoice
        invoice = Invoice.objects.filter(
            note__startswith='Purchase Return',
            total_amount__gt=0,
            created_at__range=(
                obj.created_at - timezone.timedelta(minutes=10),
                obj.created_at + timezone.timedelta(minutes=10),
            )
        ).first()

        if invoice:
            return float(invoice.total_amount)

        # 2. Fallback: original purchase price × returned quantity
        item = InvoiceItem.objects.filter(
            invoice=obj.purchase.invoice,
            product=obj.product
        ).first()

        if item:
            return float(item.unit_price * obj.quantity)

        # 3. Last resort: current product price
        return float(obj.quantity * (obj.product.price or Decimal('0.00')))

    def get_payment_type(self, obj):
        return 'RETURN'

    def get_paid_amount(self, obj):
        return self.get_total_amount(obj)

    def get_created_at_formatted(self, obj):
        return timezone.localtime(obj.created_at).strftime('%d %b %Y • %I:%M %p')


# ===================== SALE RETURN SERIALIZER =====================
class SaleReturnSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )

    class Meta:
        model = SaleReturn
        fields = [
            'id',
            'sale',
            'product',
            'product_id',
            'quantity',
            'reason',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']