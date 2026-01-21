from rest_framework import serializers
from core.core_models import User, Profile, Shop
from shop.models import Product
from shop.serializers import ProductSerializer


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'phone_number', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            phone_number=validated_data.get('phone_number', ''),
            password=validated_data['password']
        )
        return user


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['phone_number', 'address', 'created_at', 'updated_at']


class ShopSerializer(serializers.ModelSerializer):
    owner_name = serializers.ReadOnlyField(source='owner.username')
    logo = serializers.URLField(allow_null=True, required=False)
    banner = serializers.URLField(allow_null=True, required=False)

    class Meta:
        model = Shop
        fields = [
            'id', 'name', 'slug', 'address', 'description', 'logo', 'banner',
            'is_live', 'owner_name', 'created_at', 'updated_at'
        ]

class OTPRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15, required=True)

class OTPVerifySerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15, required=True)
    otp = serializers.CharField(max_length=6, required=True)