from rest_framework import serializers
from .models import Customer, Khata, Transaction

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['id', 'amount', 'is_credit', 'description', 'created_at']

class KhataSerializer(serializers.ModelSerializer):
    transactions = TransactionSerializer(many=True, read_only=True)

    class Meta:
        model = Khata
        fields = ['id', 'customer', 'total_due', 'transactions', 'created_at', 'updated_at']

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'name', 'phone_number', 'address', 'created_at']