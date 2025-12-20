from rest_framework import serializers
from shop.models import Product, Invoice, InvoiceItem, Category, CashbookEntry
from shop.models.expense_models import Expense


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'created_at']


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source='category',
        write_only=True,
        allow_null=True,
        required=False
    )

    # image_url ab read + write dono me kaam karega
    image_url = serializers.URLField(
        required=False,
        allow_blank=True,
        allow_null=True
    )

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'category', 'category_id', 'price',
            'stock_quantity', 'barcode', 'image_url', 'description',
            'show_on_website', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def to_representation(self, instance):
        """
        Ensure image_url always returns the current value from DB
        (important for GET requests)
        """
        ret = super().to_representation(instance)
        ret['image_url'] = instance.image_url or ''
        return ret

    def create(self, validated_data):
        """
        Create new product with image_url if provided
        """
        image_url = validated_data.pop('image_url', None)
        product = Product.objects.create(**validated_data)
        
        if image_url is not None:  # includes empty string for removal
            product.image_url = image_url if image_url else None
            product.save(update_fields=['image_url'])
        
        return product

    def update(self, instance, validated_data):
        """
        Update product, handle image_url properly:
        - If image_url present → update
        - If image_url == '' → remove image (set to None)
        - If not sent → don't touch
        """
        image_url = validated_data.pop('image_url', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if image_url is not None:
            instance.image_url = image_url if image_url else None

        instance.save()
        return instance


class InvoiceItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )

    class Meta:
        model = InvoiceItem
        fields = ['id', 'product', 'product_id', 'quantity', 'unit_price']


class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = ['id', 'invoice_number', 'total_amount', 'is_online', 'items', 'created_at']

    def create(self, validated_data):
        items_data = self.context['request'].data.get('items', [])
        invoice = Invoice.objects.create(**validated_data)
        for item_data in items_data:
            InvoiceItem.objects.create(invoice=invoice, **item_data)
        return invoice


class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = ['id', 'title', 'amount', 'category', 'date', 'note', 'created_at']


class CashbookEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = CashbookEntry
        fields = ['id', 'entry_type', 'amount', 'note', 'is_online', 'created_at', 'date']