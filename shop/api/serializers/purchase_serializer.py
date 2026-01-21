from rest_framework import serializers
from shop.models.purchase_models import Purchase, PurchaseReturn, SaleReturn
from shop.models import Product
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
            'payment_type',  # ← ADD THIS
        ]
        read_only_fields = ['id', 'invoice_number', 'created_at']


# ===================== PURCHASE RETURN SERIALIZER =====================
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
        # Try to find the invoice created for this return
        invoice = Invoice.objects.filter(
            note__startswith='Purchase Return',
            total_amount__gt=0,
            created_at__gte=obj.created_at - timezone.timedelta(minutes=5),
            created_at__lte=obj.created_at + timezone.timedelta(minutes=5),
        ).order_by('-created_at').first()
        
        return invoice.invoice_number if invoice else None

    def get_total_amount(self, obj):
        """
        Most reliable way: use the invoice created for the return
        Fallback: calculate from original purchase price
        """
        # 1. Try to find return invoice
        invoice = Invoice.objects.filter(
            note__startswith='Purchase Return',
            total_amount__gt=0,
            created_at__range=(
                obj.created_at - timezone.timedelta(minutes=5),
                obj.created_at + timezone.timedelta(minutes=5),
            )
        ).first()

        if invoice:
            return float(invoice.total_amount)

        # 2. Fallback: calculate using original unit price
        item = InvoiceItem.objects.filter(
            invoice=obj.purchase.invoice,
            product=obj.product
        ).first()

        if item:
            return float(item.unit_price * obj.quantity)

        # 3. Ultimate fallback
        return float(obj.quantity * (obj.product.price or Decimal('0.00')))

    def get_payment_type(self, obj):
        # Purchase returns are usually treated as adjustments / cash-back
        return 'RETURN'  # or 'CASH' or obj.purchase.payment_type

    def get_paid_amount(self, obj):
        # For display in billing screen - treat return as fully "settled"
        return self.get_total_amount(obj)

    def get_created_at_formatted(self, obj):
        from django.utils import timezone
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
