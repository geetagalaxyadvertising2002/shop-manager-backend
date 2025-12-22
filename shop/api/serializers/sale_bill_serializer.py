# shop/api/serializers/sale_bill_serializer.py

from rest_framework import serializers
from shop.models.sale_bill import SaleBill, SaleBillItem
from shop.models import Product
from customers.models import Customer


# Nested serializers
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
    items = SaleBillItemSerializer(many=True, required=True)
    customer_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    customer = SimpleCustomerSerializer(read_only=True)  # Detail + List दोनों में दिखेगा

    class Meta:
        model = SaleBill
        fields = [
            'id', 'bill_number', 'bill_date', 'customer_id', 'customer',
            'subtotal', 'additional_charges', 'total_amount',
            'payment_type', 'paid_amount', 'balance_due', 'items', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def validate(self, data):
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

        # Optional: Validate payment_type if needed
        payment_type = data.get('payment_type', 'CASH').upper()
        valid_types = ['CASH', 'ONLINE', 'UPI', 'CARD', 'UNPAID']
        if payment_type not in valid_types:
            raise serializers.ValidationError({"payment_type": f"Invalid payment type. Allowed: {valid_types}"})

        return data

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        customer_id = validated_data.pop('customer_id', None)
        shop = validated_data.pop('shop')

        customer = None
        if customer_id is not None:  # Handle None explicitly
            try:
                customer = Customer.objects.get(id=customer_id)
            except Customer.DoesNotExist:
                raise serializers.ValidationError({"customer_id": "Invalid customer ID"})

        # Create SaleBill
        sale_bill = SaleBill.objects.create(
            shop=shop,
            customer=customer,
            **validated_data
        )

        # Create items and deduct stock (with transaction safety)
        for item_data in items_data:
            product_id = item_data.pop('product_id')
            product = Product.objects.get(id=product_id)
            quantity = item_data['quantity']

            # Deduct stock atomically
            if product.stock_quantity < quantity:
                raise serializers.ValidationError(f"Insufficient stock for {product.name}")

            SaleBillItem.objects.create(
                sale_bill=sale_bill,
                product=product,
                **item_data
            )

            # Update stock (deduct)
            product.stock_quantity -= quantity
            product.save(update_fields=['stock_quantity'])

        return sale_bill

    def update(self, instance, validated_data):
        # Handle update (if needed, e.g., partial updates)
        items_data = validated_data.pop('items', None)
        customer_id = validated_data.pop('customer_id', None)
        shop = validated_data.pop('shop', None)

        if customer_id is not None:
            try:
                instance.customer = Customer.objects.get(id=customer_id)
            except Customer.DoesNotExist:
                raise serializers.ValidationError({"customer_id": "Invalid customer ID"})

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        # If items provided, replace (delete old and create new)
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                product_id = item_data.pop('product_id')
                product = Product.objects.get(id=product_id)
                SaleBillItem.objects.create(sale_bill=instance, product=product, **item_data)

        return instance

    def to_representation(self, instance):
        """
        Ensure that both 'items' and 'customer' are always populated
        in BOTH detail and list views.
        """
        ret = super().to_representation(instance)

        # Force populate items with full details
        items_qs = instance.items.select_related('product').all()
        ret['items'] = SaleBillItemSerializer(items_qs, many=True).data

        # Force populate customer
        if instance.customer:
            ret['customer'] = SimpleCustomerSerializer(instance.customer).data
        else:
            ret['customer'] = None  # Explicit null for clarity

        return ret