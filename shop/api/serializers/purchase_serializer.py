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
