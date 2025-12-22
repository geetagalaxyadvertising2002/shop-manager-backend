# shop/api/serializers/sale_bill_serializer.py

from rest_framework import serializers
from shop.models.sale_bill import SaleBill, SaleBillItem
from shop.models import Product
from customers.models import Customer


# Nested serializers for display only
class SimpleProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'price']


class SimpleCustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'name', 'phone_number', 'address']


class SaleBillItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(write_only=True)
    product = SimpleProductSerializer(read_only=True)

    class Meta:
        model = SaleBillItem
        fields = ['product_id', 'product', 'quantity', 'unit_price']


class SaleBillSerializer(serializers.ModelSerializer):
    items = SaleBillItemSerializer(many=True)
    customer_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    customer = SimpleCustomerSerializer(read_only=True)

    class Meta:
        model = SaleBill
        fields = [
            'id', 'bill_number', 'bill_date', 'customer_id', 'customer',
            'subtotal', 'additional_charges', 'total_amount',
            'payment_type', 'paid_amount', 'balance_due', 'items', 'created_at'
        ]
        read_only_fields = ['created_at']

    def validate(self, data):
        """
        Full validation at parent level - safe access to quantity & product_id
        """
        items_data = data.get('items', [])
        if not items_data:
            raise serializers.ValidationError({"items": "At least one item is required."})

        for item in items_data:
            product_id = item.get('product_id')
            quantity = item.get('quantity', 0)

            if not product_id:
                raise serializers.ValidationError({"items": "product_id is required for each item."})

            if quantity <= 0:
                raise serializers.ValidationError({"items": "Quantity must be greater than 0."})

            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                raise serializers.ValidationError({"items": f"Product with id {product_id} not found."})

            if product.stock_quantity < quantity:
                raise serializers.ValidationError({
                    "items": f"Insufficient stock for {product.name}. Available: {product.stock_quantity}, Requested: {quantity}"
                })

        return data

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        customer_id = validated_data.pop('customer_id', None)
        shop = validated_data.pop('shop')

        customer = None
        if customer_id:
            try:
                customer = Customer.objects.get(id=customer_id)
            except Customer.DoesNotExist:
                raise serializers.ValidationError("Invalid customer_id")

        # Create SaleBill
        sale_bill = SaleBill.objects.create(
            shop=shop,
            customer=customer,
            **validated_data
        )

        # Create items
        for item_data in items_data:
            product_id = item_data.pop('product_id')
            product = Product.objects.get(id=product_id)
            SaleBillItem.objects.create(
                sale_bill=sale_bill,
                product=product,
                **item_data
            )

        return sale_bill

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        
        # Ensure items are populated in list view
        if not ret.get('items'):
            ret['items'] = SaleBillItemSerializer(
                instance.items.select_related('product').all(),
                many=True
            ).data

        # Ensure customer is populated
        if instance.customer and not ret.get('customer'):
            ret['customer'] = SimpleCustomerSerializer(instance.customer).data

        return ret