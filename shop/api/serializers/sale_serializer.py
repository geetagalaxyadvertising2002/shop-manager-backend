from rest_framework import serializers
from shop.models.sale import Sale, PendingSale
from shop.models import Product
from customers.models import Customer
from customers.serializers import CustomerSerializer


# ========================== SALE SERIALIZER ==========================
class SaleSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all(), allow_null=True, required=False)
    product_details = serializers.SerializerMethodField()
    customer_details = serializers.SerializerMethodField()

    class Meta:
        model = Sale
        fields = [
            'id', 'product', 'product_details',
            'customer', 'customer_details',
            'quantity', 'unit_price', 'total_amount',
            'is_online', 'is_credit',
            'sale_date', 'created_at'
        ]

    def create(self, validated_data):
        """
        Create a new sale safely — fixes duplicate shop assignment issue.
        Automatically links sale with the logged-in user's first shop.
        """
        request = self.context.get('request')
        shop = None

        # ✅ Always use first() instead of get() to avoid MultipleObjectsReturned
        if request and hasattr(request.user, 'shop_set'):
            shop = request.user.shop_set.first()

        if not shop:
            raise serializers.ValidationError("⚠️ No shop found for this user.")

        # ✅ Remove 'shop' if already passed by perform_create()
        validated_data.pop('shop', None)

        sale = Sale.objects.create(shop=shop, **validated_data)
        return sale

    def get_product_details(self, obj):
        """
        Return minimal product details for sale list API.
        """
        if hasattr(obj, "product") and obj.product:
            return {
                'id': obj.product.id,
                'name': obj.product.name,
                'barcode': obj.product.barcode,
                'price': str(obj.product.price),
            }
        return None

    def get_customer_details(self, obj):
        """
        Return nested customer details safely.
        """
        if hasattr(obj, "customer") and obj.customer:
            return CustomerSerializer(obj.customer).data
        return None

    def to_representation(self, instance):
        """
        Ensure correct serialization even if instance is a dict (fixes API mix issues).
        """
        if isinstance(instance, dict):
            try:
                sale = Sale.objects.filter(
                    product=instance.get('product'),
                    quantity=instance.get('quantity'),
                    total_amount=instance.get('total_amount')
                ).last()
                instance = sale if sale else instance
            except Exception:
                pass
        return super().to_representation(instance)


# ========================== PENDING SALE SERIALIZER ==========================
class PendingSaleSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all(), allow_null=True, required=False)
    product_details = serializers.SerializerMethodField()
    customer_details = serializers.SerializerMethodField()

    class Meta:
        model = PendingSale
        fields = [
            'id', 'product', 'product_details',
            'customer', 'customer_details',
            'quantity', 'unit_price',
            'is_online', 'is_credit',
            'scheduled_time', 'status', 'created_at'
        ]

    def create(self, validated_data):
        """
        Create a pending sale safely linked to the logged-in user's shop.
        """
        request = self.context.get('request')
        shop = None

        if request and hasattr(request.user, 'shop_set'):
            shop = request.user.shop_set.first()

        if not shop:
            raise serializers.ValidationError("⚠️ No shop found for this user.")

        # ✅ Avoid duplicate shop key
        validated_data.pop('shop', None)

        pending_sale = PendingSale.objects.create(shop=shop, **validated_data)
        return pending_sale

    def get_product_details(self, obj):
        if hasattr(obj, "product") and obj.product:
            return {
                'id': obj.product.id,
                'name': obj.product.name,
                'barcode': obj.product.barcode,
                'price': str(obj.product.price),
            }
        return None

    def get_customer_details(self, obj):
        if hasattr(obj, "customer") and obj.customer:
            return CustomerSerializer(obj.customer).data
        return None

    def to_representation(self, instance):
        if isinstance(instance, dict):
            try:
                pending_sale = PendingSale.objects.filter(
                    product=instance.get('product'),
                    quantity=instance.get('quantity'),
                    unit_price=instance.get('unit_price')
                ).last()
                instance = pending_sale if pending_sale else instance
            except Exception:
                pass
        return super().to_representation(instance)
