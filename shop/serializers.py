from rest_framework import serializers
from .models import Product, Invoice, InvoiceItem, Category, Sale, CashbookEntry, OrderRecord
from shop.models.expense_models import Expense


# ===========================
#  CATEGORY SERIALIZER
# ===========================
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'created_at']


# ===========================
#  PRODUCT SERIALIZER
# ===========================
class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source='category', write_only=True, allow_null=True
    )
    image = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'category', 'category_id', 'price',
            'stock_quantity', 'barcode', 'image', 'created_at', 'updated_at',
            'show_on_website', 
            'description', # ← YE ADD KARO
        ]


# ===========================
#  SALE SERIALIZER
# ===========================
class SaleSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )

    class Meta:
        model = Sale
        fields = [
            'id', 'product', 'product_id', 'quantity', 'unit_price',
            'total_amount', 'created_at', 'sale_date', 'invoiced', 'invoice'
        ]


# ===========================
#  INVOICE ITEM SERIALIZER
# ===========================
class InvoiceItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )

    class Meta:
        model = InvoiceItem
        fields = ['id', 'product', 'product_id', 'quantity', 'unit_price']


# ===========================
#  INVOICE SERIALIZER
# ===========================
class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True, read_only=True)
    sale_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )

    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'total_amount', 'is_online',
            'customer_name', 'customer_phone', 'note',
            'items', 'sale_ids', 'created_at'
        ]

    def create(self, validated_data):
        sale_ids = validated_data.pop('sale_ids', [])
        invoice = Invoice.objects.create(**validated_data)

        if sale_ids:
            from .models import Sale, InvoiceItem
            sales = Sale.objects.filter(id__in=sale_ids)
            total_amount = 0

            for sale in sales:
                InvoiceItem.objects.create(
                    invoice=invoice,
                    product=sale.product,
                    quantity=sale.quantity,
                    unit_price=sale.unit_price
                )
                sale.invoiced = True
                sale.invoice = invoice
                sale.save(update_fields=['invoiced', 'invoice'])
                total_amount += sale.total_amount

            invoice.sales.add(*sales)
            invoice.total_amount = total_amount
            invoice.save()

        return invoice


# ===========================
#  EXPENSE SERIALIZER
# ===========================
class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = ['id', 'title', 'amount', 'category', 'date', 'note', 'created_at']

class CashbookEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = CashbookEntry
        fields = ['id', 'entry_type', 'amount', 'note', 'is_online', 'created_at', 'date']

class OrderRecordSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    invoice = serializers.StringRelatedField()

    class Meta:
        model = OrderRecord
        fields = '__all__'
