# shop/api/serializers/sale_bill_serializer.py

from rest_framework import serializers
from shop.models.sale_bill import SaleBill, SaleBillItem
from shop.models import Product
from customers.models import Customer
from customers.serializers import CustomerSerializer  # ← Add this import
from shop.api.serializers import ProductSerializer   # ← Add this (or create minimal one)


# Minimal Product serializer for nesting (to avoid circular import issues)
class SimpleProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'price']


class SaleBillItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(write_only=True)
    product = SimpleProductSerializer(read_only=True)  # ← Nested product details

    class Meta:
        model = SaleBillItem
        fields = ['product_id', 'product', 'quantity', 'unit_price']


class SaleBillSerializer(serializers.ModelSerializer):
    items = SaleBillItemSerializer(many=True, read_only=True)  # ← read_only for list
    customer = CustomerSerializer(read_only=True)              # ← Full customer details
    customer_id = serializers.IntegerField(write_only=True)    # ← For create

    class Meta:
        model = SaleBill
        fields = [
            'id', 'bill_number', 'bill_date', 'customer', 'customer_id',
            'subtotal', 'additional_charges', 'total_amount',
            'payment_type', 'paid_amount', 'balance_due',
            'created_at', 'items'
        ]
        read_only_fields = ['created_at']

    # Writeable items for create
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only include writeable items field during create
        if self.context['request'].method in ['POST', 'PUT', 'PATCH']:
            self.fields['items_write'] = SaleBillItemSerializer(many=True, write_only=True)

    def create(self, validated_data):
        items_data = validated_data.pop('items_write', [])
        customer_id = validated_data.pop('customer_id', None)
        shop = validated_data.pop('shop')

        if customer_id:
            customer = Customer.objects.get(id=customer_id)
        else:
            customer = None

        sale_bill = SaleBill.objects.create(
            shop=shop,
            customer=customer,
            **validated_data
        )

        for item_data in items_data:
            product_id = item_data.pop('product_id')
            product = Product.objects.get(id=product_id)

            if product.stock_quantity < item_data['quantity']:
                raise serializers.ValidationError(
                    f"Not enough stock for {product.name}. Available: {product.stock_quantity}"
                )

            SaleBillItem.objects.create(
                sale_bill=sale_bill,
                product=product,
                **item_data
            )

        return sale_bill

    def to_representation(self, instance):
        """
        Ensure nested data is included in list and detail views
        """
        ret = super().to_representation(instance)
        # Force populate items and customer if not already
        if 'items' not in ret or not ret['items']:
            ret['items'] = SaleBillItemSerializer(instance.items.all(), many=True).data
        if 'customer' not in ret or not ret['customer']:
            if instance.customer:
                ret['customer'] = CustomerSerializer(instance.customer).data
            else:
                ret['customer'] = None
        return ret