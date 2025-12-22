# shop/api/serializers/sale_bill_serializer.py

from rest_framework import serializers
from shop.models.sale_bill import SaleBill, SaleBillItem
from shop.models import Product
from customers.models import Customer


# Simple Product Serializer for nested display (list/detail views)
class SimpleProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'price']


# Simple Customer Serializer for nested display
class SimpleCustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'name', 'phone_number', 'address']


class SaleBillItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(write_only=True, required=True)
    product = SimpleProductSerializer(read_only=True)  # Nested for display only

    class Meta:
        model = SaleBillItem
        fields = ['id', 'product_id', 'product', 'quantity', 'unit_price']

    def validate_product_id(self, value):
        try:
            product = Product.objects.get(id=value)
            if product.stock_quantity < self.initial_data.get('quantity', 0):
                raise serializers.ValidationError(
                    f"Insufficient stock for {product.name}. Available: {product.stock_quantity}"
                )
            return value
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found")


class SaleBillSerializer(serializers.ModelSerializer):
    items = SaleBillItemSerializer(many=True)  # Works for both create & display
    customer_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    customer = SimpleCustomerSerializer(read_only=True)  # Nested for display only

    class Meta:
        model = SaleBill
        fields = [
            'id', 'bill_number', 'bill_date', 'customer_id', 'customer',
            'subtotal', 'additional_charges', 'total_amount',
            'payment_type', 'paid_amount', 'balance_due', 'items', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        # Extract nested data
        items_data = validated_data.pop('items', [])
        customer_id = validated_data.pop('customer_id', None)
        shop = validated_data.pop('shop', None)  # From view

        if not shop:
            raise serializers.ValidationError("Shop is required")

        # Get customer if provided
        customer = None
        if customer_id:
            try:
                customer = Customer.objects.get(id=customer_id)
            except Customer.DoesNotExist:
                raise serializers.ValidationError("Customer not found")

        # Create SaleBill
        sale_bill = SaleBill.objects.create(shop=shop, customer=customer, **validated_data)

        # Create items (stock check already done in validate_product_id)
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
        # Ensure nested data is always included (for billing history list view)
        data = super().to_representation(instance)
        
        # Force-load items if empty (for list view)
        if not data.get('items'):
            data['items'] = SaleBillItemSerializer(
                instance.items.select_related('product').all(), 
                many=True,
                context=self.context
            ).data
            
        # Force-load customer if empty
        if instance.customer_id and not data.get('customer'):
            customer = Customer.objects.get(id=instance.customer_id)
            data['customer'] = SimpleCustomerSerializer(customer, context=self.context).data
        
        return data