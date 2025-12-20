# shop/api/serializers/sale_bill_serializer.py
from rest_framework import serializers
from shop.models.sale_bill import SaleBill, SaleBillItem
from shop.models import Product
from customers.models import Customer

class SaleBillItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(write_only=True)
    name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = SaleBillItem
        fields = ['product_id', 'name', 'quantity', 'unit_price']


class SaleBillSerializer(serializers.ModelSerializer):
    items = SaleBillItemSerializer(many=True)
    customer = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(),
        write_only=True
    )
    customer_id = serializers.IntegerField(source='customer.id', read_only=True)

    class Meta:
        model = SaleBill
        fields = [
            'id', 'bill_number', 'bill_date', 'customer', 'customer_id',
            'subtotal', 'additional_charges', 'total_amount',
            'payment_type', 'paid_amount', 'balance_due', 'items'
        ]

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        customer = validated_data.pop('customer')  # This is Customer object
        shop = validated_data.pop('shop')  # From view

        sale_bill = SaleBill.objects.create(
            shop=shop,
            customer=customer,
            **validated_data
        )

        for item_data in items_data:
            product_id = item_data.pop('product_id')
            product = Product.objects.get(id=product_id)

            if product.stock_quantity < item_data['quantity']:
                raise serializers.ValidationError(f"Not enough stock for {product.name}")

            SaleBillItem.objects.create(
                sale_bill=sale_bill,
                product=product,
                **item_data
            )
            product.stock_quantity -= item_data['quantity']
            product.save()

        return sale_bill